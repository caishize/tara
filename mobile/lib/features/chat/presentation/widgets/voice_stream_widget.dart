import 'dart:async';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:record/record.dart';
import '../bloc/assistant_bloc.dart';

/// Inline compact voice recording strip replacing the old BottomSheet recorder.
///
/// Layout: [Cancel X] [Waveform ~~~~~~] [Timer 00:05]
/// Shows partial transcription below waveform as it arrives from backend.
///
/// PLAN-007: Inline VoiceStreamWidget
/// PLAN-008: Client-side amplitude VAD with auto-stop
class VoiceStreamWidget extends StatefulWidget {
  const VoiceStreamWidget({super.key});

  @override
  State<VoiceStreamWidget> createState() => _VoiceStreamWidgetState();
}

class _VoiceStreamWidgetState extends State<VoiceStreamWidget> {
  final AudioRecorder _recorder = AudioRecorder();
  StreamSubscription<Uint8List>? _audioStreamSub;
  StreamSubscription<Amplitude>? _amplitudeSub;
  Timer? _durationTimer;
  Timer? _silenceTimer;

  int _elapsedSeconds = 0;
  double _amplitude = 0.0;
  bool _isRecording = false;

  // VAD config
  static const double _silenceThresholdDb = -40.0;
  static const Duration _silenceTimeout = Duration(milliseconds: 1500);
  static const int _maxDurationSeconds = 60;

  // Waveform history for visualization (last 30 samples)
  final List<double> _waveformHistory = [];
  static const int _waveformMaxSamples = 30;

  @override
  void initState() {
    super.initState();
    _startRecording();
  }

  @override
  void dispose() {
    _stopRecording(cancelled: true);
    _recorder.dispose();
    super.dispose();
  }

  Future<void> _startRecording() async {
    if (!await _recorder.hasPermission()) {
      if (mounted) {
        context.read<AssistantBloc>().add(const VoiceStreamCancelRequested());
      }
      return;
    }
    // H-4: Guard against widget being unmounted after async permission check
    if (!mounted) return;

    setState(() {
      _isRecording = true;
      _elapsedSeconds = 0;
      _amplitude = 0.0;
      _waveformHistory.clear();
    });

    context.read<AssistantBloc>().add(const VoiceStreamStartRequested());

    // V-M-4: Start streaming audio as PCM 16kHz mono, catching failures
    // (e.g. microphone busy, unsupported config).
    Stream<Uint8List> stream;
    try {
      stream = await _recorder.startStream(
        const RecordConfig(
          encoder: AudioEncoder.pcm16bits,
          sampleRate: 16000,
          numChannels: 1,
          bitRate: 256000,
        ),
      );
    } catch (e) {
      debugPrint('Failed to start audio stream: $e');
      if (mounted) {
        setState(() => _isRecording = false);
        context.read<AssistantBloc>().add(const VoiceStreamCancelRequested());
      }
      return;
    }

    _audioStreamSub = stream.listen((chunk) {
      if (!_isRecording) return;
      context.read<AssistantBloc>().add(VoiceStreamChunkReady(chunk));
    });

    // Subscribe to amplitude for VAD and waveform
    _amplitudeSub = _recorder
        .onAmplitudeChanged(const Duration(milliseconds: 100))
        .listen((amp) {
      if (!mounted || !_isRecording) return;
      final normalized = _normalizeAmplitude(amp.current);
      setState(() {
        _amplitude = normalized;
        _waveformHistory.add(normalized);
        if (_waveformHistory.length > _waveformMaxSamples) {
          _waveformHistory.removeAt(0);
        }
      });

      // M-1: VAD with 2s grace period — don't auto-stop before user speaks
      if (_elapsedSeconds >= 2 && amp.current < _silenceThresholdDb) {
        _silenceTimer ??= Timer(_silenceTimeout, () {
          if (_isRecording && mounted) {
            _stopRecording(cancelled: false);
          }
        });
      } else {
        _silenceTimer?.cancel();
        _silenceTimer = null;
      }
    });

    // Duration timer
    _durationTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      setState(() => _elapsedSeconds++);
      if (_elapsedSeconds >= _maxDurationSeconds) {
        _stopRecording(cancelled: false);
      }
    });
  }

  Future<void> _stopRecording({required bool cancelled}) async {
    if (!_isRecording) return;
    _isRecording = false;

    _durationTimer?.cancel();
    _durationTimer = null;
    _silenceTimer?.cancel();
    _silenceTimer = null;

    await _audioStreamSub?.cancel();
    _audioStreamSub = null;
    await _amplitudeSub?.cancel();
    _amplitudeSub = null;

    try {
      await _recorder.stop();
    } catch (_) {}

    if (!mounted) return;

    if (cancelled) {
      context.read<AssistantBloc>().add(const VoiceStreamCancelRequested());
    } else {
      context.read<AssistantBloc>().add(const VoiceStreamEndRequested());
    }
  }

  double _normalizeAmplitude(double dbValue) {
    // Convert dB (-160..0) to 0.0..1.0
    const minDb = -60.0;
    const maxDb = 0.0;
    return ((dbValue - minDb) / (maxDb - minDb)).clamp(0.0, 1.0);
  }

  String _formatDuration(int seconds) {
    final m = (seconds ~/ 60).toString().padLeft(2, '0');
    final s = (seconds % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<AssistantBloc, AssistantState>(
      buildWhen: (prev, next) {
        if (prev is! AssistantLoaded || next is! AssistantLoaded) return true;
        return prev.partialTranscription != next.partialTranscription ||
            prev.isVoiceStreaming != next.isVoiceStreaming;
      },
      builder: (context, state) {
        final loaded = state is AssistantLoaded ? state : null;
        final partialText = loaded?.partialTranscription;

        return Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Partial transcription preview
            if (partialText != null && partialText.isNotEmpty)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                child: Text(
                  partialText,
                  style: TextStyle(
                    fontSize: 14,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                    fontStyle: FontStyle.italic,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            // Inline recording strip
            Container(
              height: 48,
              padding: const EdgeInsets.symmetric(horizontal: 8),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(24),
              ),
              child: Row(
                children: [
                  // Cancel button
                  IconButton(
                    icon: Icon(
                      Icons.close,
                      color: Theme.of(context).colorScheme.error,
                      size: 20,
                    ),
                    onPressed: () => _stopRecording(cancelled: true),
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(
                      minWidth: 36,
                      minHeight: 36,
                    ),
                  ),
                  // Waveform — H-2: pass immutable copy so shouldRepaint works
                  Expanded(
                    child: CustomPaint(
                      painter: _WaveformPainter(
                        amplitudes: List<double>.of(_waveformHistory),
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      size: const Size(double.infinity, 32),
                    ),
                  ),
                  const SizedBox(width: 8),
                  // Recording indicator + timer
                  Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: Colors.red,
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 4),
                  Text(
                    _formatDuration(_elapsedSeconds),
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                      color: Theme.of(context).colorScheme.onSurface,
                      fontFeatures: const [FontFeature.tabularFigures()],
                    ),
                  ),
                  const SizedBox(width: 4),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}

/// Custom painter for waveform visualization.
class _WaveformPainter extends CustomPainter {
  final List<double> amplitudes;
  final Color color;

  _WaveformPainter({required this.amplitudes, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    if (amplitudes.isEmpty) return;
    final paint = Paint()
      ..color = color
      ..strokeWidth = 2.0
      ..strokeCap = StrokeCap.round;

    final barWidth = size.width / _VoiceStreamWidgetState._waveformMaxSamples;
    final centerY = size.height / 2;
    final maxBarHeight = size.height * 0.8;

    for (int i = 0; i < amplitudes.length; i++) {
      final barHeight = maxBarHeight * amplitudes[i].clamp(0.05, 1.0);
      final x = i * barWidth + barWidth / 2;
      canvas.drawLine(
        Offset(x, centerY - barHeight / 2),
        Offset(x, centerY + barHeight / 2),
        paint,
      );
    }
  }

  // H-2: Always repaint — called at 100ms intervals, cheap for 30 bars
  @override
  bool shouldRepaint(_WaveformPainter oldDelegate) => true;
}
