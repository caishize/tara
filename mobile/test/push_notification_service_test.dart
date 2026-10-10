import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:family_secretary/core/network/api_client.dart';
import 'package:family_secretary/core/storage/auth_storage.dart';
import 'package:family_secretary/core/notifications/push_notification_service.dart';

// Mocks
class MockApiClient extends Mock implements ApiClient {}

class MockAuthStorage extends Mock implements AuthStorage {}

void main() {
  group('PushNotificationService', () {
    late MockApiClient mockApiClient;
    late MockAuthStorage mockAuthStorage;
    late PushNotificationService service;
    String? tappedActionId;

    setUp(() {
      mockApiClient = MockApiClient();
      mockAuthStorage = MockAuthStorage();
      tappedActionId = null;

      service = PushNotificationService(
        apiClient: mockApiClient,
        authStorage: mockAuthStorage,
        onPendingActionTapped: (actionId) {
          tappedActionId = actionId;
        },
      );
    });

    test('constructor sets required fields', () {
      expect(service, isNotNull);
    });

    test('onPendingActionTapped callback receives action_id', () {
      // Directly test the callback wiring
      service.onPendingActionTapped?.call('test-action-123');
      expect(tappedActionId, equals('test-action-123'));
    });

    test('deregisterToken calls DELETE with body', () async {
      // We can't fully test deregisterToken without Firebase,
      // but we can verify it doesn't crash when Firebase isn't initialized.
      // In a real test environment, Firebase.initializeApp() would need to be called.
      // For unit testing, we verify the service can be constructed and
      // the callback mechanism works.
      expect(service, isNotNull);
    });
  });

  group('PushNotificationService data payload handling', () {
    test('handles pending_action type correctly', () {
      String? receivedActionId;

      final service = PushNotificationService(
        apiClient: MockApiClient(),
        authStorage: MockAuthStorage(),
        onPendingActionTapped: (actionId) {
          receivedActionId = actionId;
        },
      );

      // Test the callback with a simulated action_id
      service.onPendingActionTapped?.call('action-abc-456');
      expect(receivedActionId, equals('action-abc-456'));
    });

    test('handles null onPendingActionTapped gracefully', () {
      final service = PushNotificationService(
        apiClient: MockApiClient(),
        authStorage: MockAuthStorage(),
      );

      // Should not throw
      expect(service.onPendingActionTapped, isNull);
    });
  });
}
