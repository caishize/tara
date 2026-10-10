import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:family_secretary/features/chat/presentation/widgets/briefing_message_card.dart';
import 'package:family_secretary/features/chat/domain/entities/daily_briefing.dart';
import 'package:family_secretary/app/theme/app_theme.dart';

void main() {
  group('BriefingMessageCard', () {
    testWidgets('shows empty state when no data', (tester) async {
      final briefing = DailyBriefing(
        date: DateTime(2026, 2, 8),
        greeting: '早安',
        period: 'morning',
        todayEventCount: 0,
        todayEvents: const [],
        preparationReminders: const [],
        weekRemainingCount: 0,
        smartSuggestions: const [],
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: Scaffold(
            body: SingleChildScrollView(
              child: BriefingMessageCard(
                briefing: briefing,
                insights: const [],
              ),
            ),
          ),
        ),
      );

      // Header uses period-aware title
      expect(find.textContaining('晨间简报'), findsOneWidget);
      expect(find.text('今天没有特别安排，享受美好的一天吧！'), findsOneWidget);
    });

    testWidgets('shows events section when briefing has events',
        (tester) async {
      final briefing = DailyBriefing(
        date: DateTime(2026, 2, 8),
        greeting: '早安',
        todayEventCount: 1,
        todayEvents: const [
          BriefingEvent(
            id: 'e1',
            title: '团队周会',
            time: '09:00',
            icon: 'meeting',
          ),
        ],
        preparationReminders: const [],
        weekRemainingCount: 3,
        smartSuggestions: const [],
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: Scaffold(
            body: SingleChildScrollView(
              child: BriefingMessageCard(
                briefing: briefing,
                insights: const [],
              ),
            ),
          ),
        ),
      );

      // Section title is "今日安排"
      expect(find.text('今日安排'), findsOneWidget);
      // Event title is rendered via RichText with separate TextSpan nodes for time and title
      expect(
        find.byWidgetPredicate((widget) {
          if (widget is RichText) {
            return widget.text.toPlainText().contains('团队周会');
          }
          return false;
        }),
        findsOneWidget,
      );
    });

    testWidgets('shows alerts when briefing has alerts', (tester) async {
      final briefing = DailyBriefing(
        date: DateTime(2026, 2, 8),
        greeting: '早安',
        todayEventCount: 0,
        todayEvents: const [],
        preparationReminders: const [],
        weekRemainingCount: 0,
        smartSuggestions: const [],
        alerts: const [
          BriefingAlert(
            id: 'a1',
            alertType: 'conflict',
            severity: 'warning',
            title: '时间冲突',
            description: '会议A 与 会议B 冲突',
          ),
        ],
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: Scaffold(
            body: SingleChildScrollView(
              child: BriefingMessageCard(
                briefing: briefing,
                insights: const [],
              ),
            ),
          ),
        ),
      );

      expect(find.text('时间冲突'), findsOneWidget);
      expect(find.text('会议A 与 会议B 冲突'), findsOneWidget);
    });

    testWidgets('shows suggestion chips that fire callback', (tester) async {
      BriefingSuggestion? tappedSuggestion;
      final briefing = DailyBriefing(
        date: DateTime(2026, 2, 8),
        greeting: '早安',
        todayEventCount: 0,
        todayEvents: const [],
        preparationReminders: const [],
        weekRemainingCount: 0,
        smartSuggestions: const [
          BriefingSuggestion(
            label: '查看智能洞察',
            actionType: 'view_insights',
          ),
          BriefingSuggestion(
            label: '查看行程详情',
            actionType: 'navigate_to_trip',
            actionData: {'trip_id': 'trip_123'},
          ),
        ],
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: Scaffold(
            body: SingleChildScrollView(
              child: BriefingMessageCard(
                briefing: briefing,
                insights: const [],
                onSuggestionTap: (s) => tappedSuggestion = s,
              ),
            ),
          ),
        ),
      );

      expect(find.text('查看智能洞察'), findsOneWidget);
      expect(find.text('查看行程详情'), findsOneWidget);

      await tester.tap(find.text('查看智能洞察'));
      await tester.pumpAndSettle();
      expect(tappedSuggestion?.label, '查看智能洞察');
      expect(tappedSuggestion?.actionType, 'view_insights');
    });
  });
}
