import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as status;
import '../storage/auth_storage.dart';

/// Connection status exposed by [WebSocketService].
enum WsConnectionStatus {
  connected,
  disconnected,
  reconnecting,
}

class WebSocketService {
  final AuthStorage _authStorage;
  final String _baseUrl;

  WebSocketChannel? _channel;
  StreamController<dynamic>? _controller;
  String? _currentUserId;
  bool _isReconnecting = false;
  int _reconnectAttempts = 0;

  /// Active job tracking for resume-on-reconnect
  String? _activeJobId;
  int _lastSeq = 0;

  /// Maximum backoff duration in seconds.
  static const int _maxBackoffSeconds = 30;

  /// Broadcast stream emitting an event on each successful reconnection.
  final StreamController<void> _reconnectController =
      StreamController<void>.broadcast();

  /// Stream that fires after every successful reconnection (not initial connect).
  Stream<void> get onReconnected => _reconnectController.stream;

  /// Broadcast stream of connection status changes.
  final StreamController<WsConnectionStatus> _statusController =
      StreamController<WsConnectionStatus>.broadcast();

  /// Stream of [WsConnectionStatus] changes.
  Stream<WsConnectionStatus> get onStatusChanged => _statusController.stream;

  /// Current connection status.
  WsConnectionStatus get connectionStatus {
    if (_channel != null) return WsConnectionStatus.connected;
    if (_isReconnecting) return WsConnectionStatus.reconnecting;
    return WsConnectionStatus.disconnected;
  }

  // Connection state
  bool get isConnected => _channel != null;

  WebSocketService(this._authStorage, String httpBaseUrl)
      : _baseUrl = httpBaseUrl.replaceFirst('http', 'ws');

  Future<void> connect(String userId) async {
    if (_currentUserId == userId && isConnected) return;

    // Don't disconnect if we are just ensuring connection for same user
    if (_channel != null) {
      await disconnect();
    }

    _currentUserId = userId;
    _reconnectAttempts = 0;
    await _connectInternal(isReconnect: false);
  }

  Future<void> _connectInternal({required bool isReconnect}) async {
    final userId = _currentUserId;
    if (userId == null) return;

    final token = _authStorage.getAccessToken();
    if (token == null) {
      assert(() { debugPrint('WebSocket: No access token available'); return true; }());
      return;
    }

    // Ensure URL doesn't end with slash if we are appending path
    final baseUrl = _baseUrl.endsWith('/')
        ? _baseUrl.substring(0, _baseUrl.length - 1)
        : _baseUrl;
    final url = Uri.parse('$baseUrl/ws/$userId?token=$token');
    assert(() { debugPrint('WebSocket: connecting to $userId'); return true; }());

    try {
      _channel = WebSocketChannel.connect(url);

      // Initialize controller if null or closed
      if (_controller == null || _controller!.isClosed) {
        _controller = StreamController<dynamic>.broadcast();
      }

      _channel!.stream.listen(
        (message) {
          if (_controller != null && !_controller!.isClosed) {
            _controller!.add(message);
          }
        },
        onError: (error) {
          debugPrint(
              '[WS] onError user=$_currentUserId activeJob=$_activeJobId lastSeq=$_lastSeq error=$error');
          _scheduleReconnect();
        },
        onDone: () {
          debugPrint(
              '[WS] onDone user=$_currentUserId activeJob=$_activeJobId lastSeq=$_lastSeq');
          _channel = null;
          _emitStatus(WsConnectionStatus.disconnected);
          // Only reconnect if not explicitly disconnected
          if (_currentUserId != null) {
            _scheduleReconnect();
          }
        },
      );

      // Reset backoff on successful connection
      _reconnectAttempts = 0;
      _emitStatus(WsConnectionStatus.connected);
      debugPrint(
          '[WS] connected user=$userId reconnect=$isReconnect activeJob=$_activeJobId lastSeq=$_lastSeq');

      // Resume active job on reconnect (gap recovery)
      if (isReconnect && _activeJobId != null) {
        debugPrint(
            '[WS] sending resume user=$userId job=$_activeJobId lastSeq=$_lastSeq');
        sendJson({
          'type': 'resume',
          'job_id': _activeJobId,
          'last_seq': _lastSeq,
        });
      }

      // Fire reconnected event (only on reconnect, not initial connect)
      if (isReconnect && !_reconnectController.isClosed) {
        _reconnectController.add(null);
      }
    } catch (e) {
      assert(() { debugPrint('WebSocket connection failed: $e'); return true; }());
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    if (_isReconnecting || _currentUserId == null) return;

    _isReconnecting = true;
    _reconnectAttempts++;
    _emitStatus(WsConnectionStatus.reconnecting);

    // Exponential backoff: 3s, 6s, 12s, 24s, 30s (capped)
    final backoffSeconds = min(
      3 * pow(2, _reconnectAttempts - 1).toInt(),
      _maxBackoffSeconds,
    );

    debugPrint(
        '[WS] schedule reconnect in ${backoffSeconds}s attempt=$_reconnectAttempts user=$_currentUserId activeJob=$_activeJobId lastSeq=$_lastSeq');

    Future.delayed(Duration(seconds: backoffSeconds), () async {
      _isReconnecting = false;
      if (_currentUserId != null) {
        debugPrint(
            '[WS] attempting reconnect user=$_currentUserId activeJob=$_activeJobId lastSeq=$_lastSeq');
        await _connectInternal(isReconnect: true);
      }
    });
  }

  Future<void> disconnect() async {
    _currentUserId = null; // Prevent reconnect
    _reconnectAttempts = 0;
    if (_channel != null) {
      await _channel!.sink.close(status.goingAway);
      _channel = null;
    }
    if (_controller != null) {
      await _controller!.close();
      _controller = null;
    }
    _emitStatus(WsConnectionStatus.disconnected);
  }

  void _emitStatus(WsConnectionStatus s) {
    if (!_statusController.isClosed) {
      _statusController.add(s);
    }
  }

  Stream<dynamic> get messages {
    if (_controller == null || _controller!.isClosed) {
      _controller = StreamController<dynamic>.broadcast();
    }
    return _controller!.stream;
  }

  /// Send a JSON message over the WebSocket.
  void sendJson(Map<String, dynamic> data) {
    if (_channel == null) {
      assert(() { debugPrint('WebSocket: cannot send, not connected'); return true; }());
      return;
    }
    try {
      _channel!.sink.add(jsonEncode(data));
    } catch (e) {
      assert(() { debugPrint('WebSocket send error: $e'); return true; }());
    }
  }

  /// Binary frame header bytes for voice streaming protocol.
  static const int headerAudioChunk = 0x01;
  static const int headerAudioEnd = 0x02;
  static const int headerAudioCancel = 0x03;

  /// Send a binary frame over the WebSocket.
  ///
  /// Used for voice streaming: prepends [header] byte to [payload].
  void sendBinary(int header, Uint8List payload) {
    if (_channel == null) {
      assert(() { debugPrint('WebSocket: cannot send binary, not connected'); return true; }());
      return;
    }
    try {
      final frame = Uint8List(1 + payload.length);
      frame[0] = header;
      frame.setRange(1, frame.length, payload);
      _channel!.sink.add(frame);
    } catch (e) {
      assert(() { debugPrint('WebSocket binary send error: $e'); return true; }());
    }
  }

  /// Send an audio chunk for voice streaming.
  void sendAudioChunk(Uint8List audioData) {
    sendBinary(headerAudioChunk, audioData);
  }

  /// Signal end of voice utterance.
  void sendAudioEnd() {
    sendBinary(headerAudioEnd, Uint8List(0));
  }

  /// Cancel active voice stream.
  void sendAudioCancel() {
    sendBinary(headerAudioCancel, Uint8List(0));
  }

  /// Mark the currently active job for resume-on-reconnect tracking.
  void setActiveJob(String jobId) {
    _activeJobId = jobId;
    _lastSeq = 0;
    debugPrint('[WS] setActiveJob job=$jobId');
  }

  /// Clear the active job (called when job completes or errors).
  void clearActiveJob() {
    debugPrint('[WS] clearActiveJob job=$_activeJobId lastSeq=$_lastSeq');
    _activeJobId = null;
    _lastSeq = 0;
  }

  /// Update the last received sequence number for the active job.
  void updateLastSeq(int seq) {
    if (seq > _lastSeq) {
      _lastSeq = seq;
      if (seq <= 3 || seq % 50 == 0) {
        debugPrint('[WS] updateLastSeq activeJob=$_activeJobId seq=$seq');
      }
    }
  }

  /// Get auth storage (exposed for debugging/setup if needed)
  AuthStorage get authStorage => _authStorage;
}
