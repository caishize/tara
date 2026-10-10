import 'dart:convert';
import 'dart:io' show Platform;
import 'package:flutter/foundation.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import '../network/api_client.dart';
import '../storage/auth_storage.dart';

/// Background message handler (must be top-level function).
@pragma('vm:entry-point')
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  // No-op for now — handled on tap via getInitialMessage / onMessageOpenedApp.
}

/// Service for managing Firebase Cloud Messaging push notifications.
///
/// Responsibilities:
/// - Request notification permissions
/// - Register FCM token with backend
/// - Handle token refresh
/// - Display foreground notifications via flutter_local_notifications
/// - Handle notification taps (navigate to pending action)
class PushNotificationService {
  final ApiClient _apiClient;
  final AuthStorage _authStorage;
  final void Function(String actionId)? onPendingActionTapped;

  final FlutterLocalNotificationsPlugin _localNotifications =
      FlutterLocalNotificationsPlugin();

  static const _androidChannel = AndroidNotificationChannel(
    'pending_actions',
    '待确认操作',
    description: '需要您确认的操作通知',
    importance: Importance.high,
  );

  PushNotificationService({
    required ApiClient apiClient,
    required AuthStorage authStorage,
    this.onPendingActionTapped,
  })  : _apiClient = apiClient,
        _authStorage = authStorage;

  /// Initialize push notifications.
  ///
  /// Call after Firebase.initializeApp() and user login.
  Future<void> initialize() async {
    final messaging = FirebaseMessaging.instance;

    // Register background handler
    FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);

    // Request permissions
    final settings = await messaging.requestPermission(
      alert: true,
      badge: true,
      sound: true,
    );

    if (settings.authorizationStatus == AuthorizationStatus.denied) {
      debugPrint('PushNotification: User denied permissions');
      return;
    }

    // Initialize local notifications for foreground display
    await _initLocalNotifications();

    // Get and register token
    final token = await messaging.getToken();
    if (token != null) {
      await _registerToken(token);
    }

    // Listen for token refresh
    messaging.onTokenRefresh.listen(_registerToken);

    // Handle foreground messages
    FirebaseMessaging.onMessage.listen(_handleForegroundMessage);

    // Handle notification taps (app in background)
    FirebaseMessaging.onMessageOpenedApp.listen(_handleMessageTap);

    // Handle notification tap that launched the app (app terminated)
    final initialMessage = await messaging.getInitialMessage();
    if (initialMessage != null) {
      _handleMessageTap(initialMessage);
    }
  }

  Future<void> _initLocalNotifications() async {
    const androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosSettings = DarwinInitializationSettings(
      requestAlertPermission: false,
      requestBadgePermission: false,
      requestSoundPermission: false,
    );

    await _localNotifications.initialize(
      const InitializationSettings(
        android: androidSettings,
        iOS: iosSettings,
      ),
      onDidReceiveNotificationResponse: (details) {
        // Handle local notification tap
        final payload = details.payload;
        if (payload != null) {
          try {
            final data = jsonDecode(payload) as Map<String, dynamic>;
            _handleDataPayload(data);
          } catch (e) {
            debugPrint('PushNotification: Failed to parse payload: $e');
          }
        }
      },
    );

    // Create the Android notification channel
    await _localNotifications
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(_androidChannel);
  }

  Future<void> _registerToken(String token) async {
    if (_authStorage.getAccessToken() == null) return;

    try {
      await _apiClient.post(
        '/device-tokens',
        data: {
          'fcm_token': token,
          'device_type': _getDeviceType(),
        },
      );
      debugPrint('PushNotification: Token registered');
    } catch (e) {
      debugPrint('PushNotification: Failed to register token: $e');
    }
  }

  void _handleForegroundMessage(RemoteMessage message) {
    final notification = message.notification;
    if (notification == null) return;

    _localNotifications.show(
      notification.hashCode,
      notification.title,
      notification.body,
      NotificationDetails(
        android: AndroidNotificationDetails(
          _androidChannel.id,
          _androidChannel.name,
          channelDescription: _androidChannel.description,
          importance: Importance.high,
          priority: Priority.high,
        ),
        iOS: const DarwinNotificationDetails(
          presentAlert: true,
          presentBadge: true,
          presentSound: true,
        ),
      ),
      payload: jsonEncode(message.data),
    );
  }

  void _handleMessageTap(RemoteMessage message) {
    _handleDataPayload(message.data);
  }

  void _handleDataPayload(Map<String, dynamic> data) {
    final type = data['type'] as String?;
    if (type == 'pending_action') {
      final actionId = data['action_id'] as String?;
      if (actionId != null) {
        onPendingActionTapped?.call(actionId);
      }
    }
  }

  /// Deregister the current FCM token (call on logout).
  Future<void> deregisterToken() async {
    try {
      final token = await FirebaseMessaging.instance.getToken();
      if (token != null) {
        await _apiClient.delete(
          '/device-tokens',
          data: {'fcm_token': token},
        );
      }
    } catch (e) {
      debugPrint('PushNotification: Failed to deregister token: $e');
    }
  }

  String _getDeviceType() {
    return Platform.isIOS ? 'ios' : 'android';
  }
}
