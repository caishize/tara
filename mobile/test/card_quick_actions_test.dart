import 'package:flutter_test/flutter_test.dart';
import 'package:family_secretary/features/chat/domain/entities/chat_message.dart';
import 'package:family_secretary/features/chat/presentation/widgets/card_quick_actions.dart';

void main() {
  group('resolveQuickActions', () {
    test('returns message quick actions when present', () {
      final message = ChatMessage(
        id: '1',
        sessionId: 's1',
        role: MessageRole.assistant,
        content: 'test',
        quickActions: const [
          QuickAction(label: 'Custom', action: 'custom action'),
        ],
        createdAt: DateTime(2026, 1, 1),
      );

      final result = resolveQuickActions(message, 'event_card');

      expect(result.length, 1);
      expect(result.first.label, 'Custom');
    });

    test('returns default quick actions when message has no quick actions', () {
      final message = ChatMessage(
        id: '1',
        sessionId: 's1',
        role: MessageRole.assistant,
        content: 'test',
        createdAt: DateTime(2026, 1, 1),
      );

      final result = resolveQuickActions(message, 'event_card');

      expect(result.length, 2);
      expect(result[0].label, '调整日期');
      expect(result[1].label, '取消日程');
    });

    test('returns default quick actions when message quickActions is empty', () {
      final message = ChatMessage(
        id: '1',
        sessionId: 's1',
        role: MessageRole.assistant,
        content: 'test',
        quickActions: const [],
        createdAt: DateTime(2026, 1, 1),
      );

      final result = resolveQuickActions(message, 'task_card');

      expect(result.length, 2);
      expect(result[0].label, '新建任务');
      expect(result[1].label, '完成任务');
    });

    test('returns empty list for unknown intent key', () {
      final message = ChatMessage(
        id: '1',
        sessionId: 's1',
        role: MessageRole.assistant,
        content: 'test',
        createdAt: DateTime(2026, 1, 1),
      );

      final result = resolveQuickActions(message, 'unknown_intent');

      expect(result, isEmpty);
    });

    test('all known intent keys have default quick actions', () {
      const knownIntents = [
        'event_card',
        'task_card',
        'member_profile',
        'recommend_gift',
        'upcoming_dates',
        'favor_balance',
      ];

      for (final intent in knownIntents) {
        expect(
          defaultCardQuickActions[intent],
          isNotEmpty,
          reason: 'Intent "$intent" should have default quick actions',
        );
      }
    });
  });
}
