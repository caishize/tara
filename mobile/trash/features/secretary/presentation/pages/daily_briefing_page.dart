import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:shimmer/shimmer.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/daily_briefing.dart';
import '../../data/models/memory_model.dart';
import '../bloc/daily_briefing_bloc.dart';
import '../widgets/briefing_header.dart';
import '../widgets/briefing_event_card.dart';
import '../widgets/briefing_reminder_section.dart';
import '../widgets/insight_card.dart';

/// Daily briefing page showing today's events and reminders.
class DailyBriefingPage extends StatefulWidget {
  const DailyBriefingPage({super.key});

  @override
  State<DailyBriefingPage> createState() => _DailyBriefingPageState();
}

class _DailyBriefingPageState extends State<DailyBriefingPage> {
  @override
  void initState() {
    super.initState();
    // Load briefing when page is initialized
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      context.read<DailyBriefingBloc>().add(const LoadDailyBriefingRequested());
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: BlocBuilder<DailyBriefingBloc, DailyBriefingState>(
        builder: (context, state) {
          Widget child;
          if (state is DailyBriefingLoading) {
            child = _buildLoadingState();
          } else if (state is DailyBriefingError) {
            child = _buildErrorState(state);
          } else if (state is DailyBriefingLoaded) {
            child = _buildLoadedState(state);
          } else {
            child = _buildLoadingState();
          }

          return AnimatedSwitcher(
            duration: const Duration(milliseconds: 300),
            switchInCurve: Curves.easeInOut,
            switchOutCurve: Curves.easeInOut,
            child: KeyedSubtree(
              key: ValueKey(state.runtimeType),
              child: child,
            ),
          );
        },
      ),
    );
  }

  Widget _buildLoadingState() {
    return SafeArea(
      child: Shimmer.fromColors(
        baseColor: Colors.grey.shade300,
        highlightColor: Colors.grey.shade100,
        child: SingleChildScrollView(
          physics: const NeverScrollableScrollPhysics(),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header skeleton
              Container(
                height: 180,
                decoration: const BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.only(
                    bottomLeft: Radius.circular(24),
                    bottomRight: Radius.circular(24),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              // Section title skeleton
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Container(
                  height: 20,
                  width: 100,
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              // Event card skeletons
              ...List.generate(3, (index) => Padding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 12),
                child: Container(
                  height: 100,
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
              )),
              const SizedBox(height: 8),
              // Week summary skeleton
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Container(
                  height: 56,
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildErrorState(DailyBriefingError errorState) {
    // Choose color and illustration based on error type
    Color iconColor;
    String illustration;
    switch (errorState.errorType) {
      case BriefingErrorType.network:
        iconColor = AppColors.warning;
        illustration = '📡';
        break;
      case BriefingErrorType.auth:
        iconColor = AppColors.error;
        illustration = '🔐';
        break;
      case BriefingErrorType.server:
        iconColor = AppColors.info;
        illustration = '☁️';
        break;
      default:
        iconColor = AppColors.error;
        illustration = '😕';
    }

    return SafeArea(
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              // Animated illustration
              TweenAnimationBuilder<double>(
                tween: Tween(begin: 0.8, end: 1.0),
                duration: const Duration(milliseconds: 600),
                curve: Curves.elasticOut,
                builder: (context, value, child) {
                  return Transform.scale(
                    scale: value,
                    child: child,
                  );
                },
                child: Container(
                  width: 120,
                  height: 120,
                  decoration: BoxDecoration(
                    color: iconColor.withValues(alpha: 0.1),
                    shape: BoxShape.circle,
                  ),
                  child: Center(
                    child: Text(
                      illustration,
                      style: const TextStyle(fontSize: 48),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 24),
              Text(
                errorState.isNetworkError ? '网络异常' : '加载失败',
                style: AppTextStyles.headline5.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                errorState.message,
                style: AppTextStyles.bodyText2.copyWith(
                  color: AppColors.textSecondary,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 32),
              if (errorState.canRetry)
                SizedBox(
                  width: 160,
                  height: 48,
                  child: ElevatedButton.icon(
                    onPressed: () {
                      HapticFeedback.mediumImpact();
                      context.read<DailyBriefingBloc>().add(
                            const LoadDailyBriefingRequested(),
                          );
                    },
                    icon: const Icon(Icons.refresh_rounded, size: 20),
                    label: const Text('重试'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.primary,
                      foregroundColor: Colors.white,
                      elevation: 0,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                  ),
                ),
              if (errorState.requiresAuth) ...[
                const SizedBox(height: 12),
                SizedBox(
                  width: 160,
                  height: 48,
                  child: OutlinedButton.icon(
                    onPressed: () {
                      HapticFeedback.mediumImpact();
                      context.go('/login');
                    },
                    icon: const Icon(Icons.login_rounded, size: 20),
                    label: const Text('重新登录'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppColors.primary,
                      side: const BorderSide(color: AppColors.primary),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildLoadedState(DailyBriefingLoaded state) {
    final briefing = state.briefing;
    final insights = state.insights;

    return RefreshIndicator(
      onRefresh: () async {
        HapticFeedback.mediumImpact();
        context.read<DailyBriefingBloc>().add(
              const RefreshDailyBriefingRequested(),
            );
        // Wait a bit for the refresh to complete for better UX
        await Future.delayed(const Duration(milliseconds: 500));
      },
      color: AppColors.primary,
      strokeWidth: 2.5,
      child: CustomScrollView(
        physics: const BouncingScrollPhysics(
          parent: AlwaysScrollableScrollPhysics(),
        ),
        slivers: [
          // Header with gradient
          SliverToBoxAdapter(
            child: BriefingHeader(briefing: briefing),
          ),

          // Secretary-style alerts section (time conflicts, urgent items)
          if (briefing.hasAlerts) ...[
            SliverToBoxAdapter(
              child: _buildAlertsSection(briefing.alerts),
            ),
          ],

          // Insights section (high priority first)
          if (state.hasInsights || state.insightsError != null) ...[
            SliverToBoxAdapter(
              child: _buildInsightsSection(
                insights,
                state.isLoadingInsights,
                state.insightsError,
              ),
            ),
          ],

          // Events section
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
              child: Text(
                '今日事项',
                style: AppTextStyles.headline6,
              ),
            ),
          ),

          if (briefing.todayEvents.isEmpty)
            SliverToBoxAdapter(
              child: _buildEmptyEventsState(),
            )
          else
            SliverPadding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              sliver: SliverList(
                delegate: SliverChildBuilderDelegate(
                  (context, index) {
                    final event = briefing.todayEvents[index];
                    return TweenAnimationBuilder<double>(
                      tween: Tween(begin: 0.0, end: 1.0),
                      duration: Duration(milliseconds: 300 + (index * 100)),
                      curve: Curves.easeOutCubic,
                      builder: (context, value, child) {
                        return Opacity(
                          opacity: value,
                          child: Transform.translate(
                            offset: Offset(0, 20 * (1 - value)),
                            child: child,
                          ),
                        );
                      },
                      child: BriefingEventCard(
                        event: event,
                        onTap: () => _onEventTap(event),
                        onActionTap: () => _onEventActionTap(event),
                      ),
                    );
                  },
                  childCount: briefing.todayEvents.length,
                ),
              ),
            ),

          // Preparation reminders section
          if (briefing.hasReminders) ...[
            SliverToBoxAdapter(
              child: const Padding(
                padding: EdgeInsets.fromLTRB(20, 8, 20, 12),
                child: Divider(color: AppColors.divider),
              ),
            ),
            SliverToBoxAdapter(
              child: BriefingReminderSection(
                reminders: briefing.preparationReminders,
              ),
            ),
          ],

          // Week summary (clickable to navigate to schedule)
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: _buildWeekSummary(briefing),
            ),
          ),

          // Smart suggestions
          if (briefing.smartSuggestions.isNotEmpty)
            SliverToBoxAdapter(
              child: _buildSmartSuggestions(briefing.smartSuggestions),
            ),

          // Bottom padding
          const SliverPadding(padding: EdgeInsets.only(bottom: 40)),
        ],
      ),
    );
  }

  Widget _buildInsightsSection(
    List<InsightModel> insights,
    bool isLoading,
    String? error,
  ) {
    // Sort by priority (highest first)
    final sortedInsights = List<InsightModel>.from(insights)
      ..sort((a, b) => b.priority.compareTo(a.priority));

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.psychology,
                color: AppColors.accent1,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                '智能提醒',
                style: AppTextStyles.subtitle2.copyWith(
                  color: AppColors.accent1,
                  fontWeight: FontWeight.w600,
                ),
              ),
              if (isLoading) ...[
                const SizedBox(width: 8),
                const SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: AppColors.accent1,
                  ),
                ),
              ],
              const Spacer(),
              // Retry button if there was an error
              if (error != null && !isLoading)
                GestureDetector(
                  onTap: () => context.read<DailyBriefingBloc>().add(
                        const LoadInsightsRequested(),
                      ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(
                        Icons.refresh,
                        color: AppColors.textSecondary,
                        size: 16,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        '重试',
                        style: AppTextStyles.caption.copyWith(
                          color: AppColors.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
          const SizedBox(height: 12),
          // Show error message if present
          if (error != null)
            Container(
              padding: const EdgeInsets.all(12),
              margin: const EdgeInsets.only(bottom: 8),
              decoration: BoxDecoration(
                color: AppColors.error.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.warning_amber_rounded,
                    color: AppColors.error,
                    size: 18,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      error,
                      style: AppTextStyles.caption.copyWith(
                        color: AppColors.error,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ...sortedInsights.take(5).toList().asMap().entries.map((entry) {
            final index = entry.key;
            final insight = entry.value;
            return TweenAnimationBuilder<double>(
              tween: Tween(begin: 0.0, end: 1.0),
              duration: Duration(milliseconds: 400 + (index * 80).toInt()),
              curve: Curves.easeOutCubic,
              builder: (context, value, child) {
                return Opacity(
                  opacity: value,
                  child: Transform.translate(
                    offset: Offset(30 * (1 - value), 0),
                    child: child,
                  ),
                );
              },
              child: Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: InsightCard(
                  insight: insight,
                  onAction: (action) => _onInsightAction(insight, action),
                  onDismiss: () => _onInsightDismiss(insight),
                ),
              ),
            );
          }),
        ],
      ),
    );
  }

  /// Build alerts section (secretary-style warnings)
  Widget _buildAlertsSection(List<BriefingAlert> alerts) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.warning_amber_rounded,
                color: AppColors.warning,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                '注意事项',
                style: AppTextStyles.subtitle2.copyWith(
                  color: AppColors.warning,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: AppColors.warning.withAlpha(30),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '${alerts.length}',
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.warning,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ...alerts.map((alert) => _buildAlertCard(alert)),
        ],
      ),
    );
  }

  /// Build single alert card
  Widget _buildAlertCard(BriefingAlert alert) {
    final alertColor = Color(alert.severityColorValue);
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: alertColor.withAlpha(15),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: alertColor.withAlpha(50)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            alert.icon,
            style: const TextStyle(fontSize: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  alert.title,
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    color: alertColor,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  alert.description,
                  style: TextStyle(
                    fontSize: 13,
                    color: AppColors.textSecondary,
                  ),
                ),
                if (alert.actionLabel != null) ...[
                  const SizedBox(height: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: alertColor.withAlpha(20),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      alert.actionLabel!,
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                        color: alertColor,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }


  void _onInsightAction(InsightModel insight, String action) {
    HapticFeedback.mediumImpact();
    context.read<DailyBriefingBloc>().add(
          ExecuteInsightActionRequested(
            insightId: insight.id,
            action: action,
            params: insight.actionData,
          ),
        );

    // Show polished feedback
    _showSuccessSnackBar('已处理: ${insight.title}');
  }

  void _showSuccessSnackBar(String message) {
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.2),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.check_rounded,
                color: Colors.white,
                size: 16,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                message,
                style: const TextStyle(
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          ],
        ),
        behavior: SnackBarBehavior.floating,
        backgroundColor: AppColors.success,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        margin: const EdgeInsets.all(16),
        duration: const Duration(seconds: 2),
      ),
    );
  }

  void _onInsightDismiss(InsightModel insight) {
    HapticFeedback.lightImpact();
    context.read<DailyBriefingBloc>().add(
          ExecuteInsightActionRequested(
            insightId: insight.id,
            action: 'dismiss',
          ),
        );

    // Show subtle feedback with undo option
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            Icon(
              Icons.visibility_off_rounded,
              color: Colors.white.withValues(alpha: 0.8),
              size: 18,
            ),
            const SizedBox(width: 10),
            const Expanded(
              child: Text(
                '已忽略该提醒',
                style: TextStyle(fontSize: 14),
              ),
            ),
          ],
        ),
        behavior: SnackBarBehavior.floating,
        backgroundColor: AppColors.textSecondary,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
        ),
        margin: const EdgeInsets.all(16),
        duration: const Duration(seconds: 2),
      ),
    );
  }

  Widget _buildEmptyEventsState() {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.0, end: 1.0),
      duration: const Duration(milliseconds: 500),
      curve: Curves.easeOutBack,
      builder: (context, value, child) {
        return Opacity(
          // Clamp because easeOutBack overshoots beyond 1.0
          opacity: value.clamp(0.0, 1.0),
          child: Transform.scale(
            scale: 0.8 + (0.2 * value),
            child: child,
          ),
        );
      },
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 20),
        padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 24),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              AppColors.success.withValues(alpha: 0.05),
              AppColors.info.withValues(alpha: 0.05),
            ],
          ),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: AppColors.success.withValues(alpha: 0.2),
            width: 1,
          ),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                color: AppColors.success.withValues(alpha: 0.1),
                shape: BoxShape.circle,
              ),
              child: const Center(
                child: Text(
                  '🌴',
                  style: TextStyle(fontSize: 36),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              '今天没有特殊事项',
              style: AppTextStyles.subtitle1.copyWith(
                color: AppColors.textPrimary,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              '享受轻松的一天吧 ✨',
              style: AppTextStyles.bodyText2.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildWeekSummary(DailyBriefing briefing) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () {
          HapticFeedback.lightImpact();
          // Navigate to schedule with "this week" filter
          context.push(Routes.scheduleWithFilter(timePeriod: 'thisWeek'));
        },
        borderRadius: BorderRadius.circular(14),
        splashColor: AppColors.info.withValues(alpha: 0.1),
        highlightColor: AppColors.info.withValues(alpha: 0.05),
        child: Ink(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.info.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: AppColors.info.withValues(alpha: 0.15),
              width: 1,
            ),
          ),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppColors.info.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(
                  Icons.date_range_rounded,
                  color: AppColors.info,
                  size: 20,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      briefing.weekRemainingCount > 0
                          ? '本周还有 ${briefing.weekRemainingCount} 件事待完成'
                          : '本周已无其他事项',
                      style: AppTextStyles.bodyText1.copyWith(
                        color: AppColors.info,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '查看完整日程',
                      style: AppTextStyles.caption.copyWith(
                        color: AppColors.info.withValues(alpha: 0.7),
                      ),
                    ),
                  ],
                ),
              ),
              Icon(
                Icons.arrow_forward_ios_rounded,
                color: AppColors.info.withValues(alpha: 0.5),
                size: 16,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSmartSuggestions(List<BriefingSuggestion> suggestions) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.lightbulb_outline,
                color: AppColors.accent1,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                '智能建议',
                style: AppTextStyles.subtitle2.copyWith(
                  color: AppColors.accent1,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ...suggestions.map((suggestion) => Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '  -  ',
                      style: AppTextStyles.caption,
                    ),
                    Expanded(
                      child: Text(
                        suggestion.label,
                        style: AppTextStyles.caption.copyWith(
                          color: AppColors.textSecondary,
                        ),
                      ),
                    ),
                  ],
                ),
              )),
        ],
      ),
    );
  }

  void _onEventTap(BriefingEvent event) {
    HapticFeedback.lightImpact();
    // Navigate based on event type
    if (event.eventType == 'travel') {
      // Travel event - navigate to travel detail
      context.push(Routes.travelDetail(event.id));
    } else if (event.memberId != null) {
      // Event with associated member - navigate to member detail
      context.push(Routes.memberDetail(event.memberId!));
    } else {
      // Default to dates/schedule
      context.push(Routes.schedule);
    }
  }

  void _onEventActionTap(BriefingEvent event) {
    HapticFeedback.mediumImpact();
    if (event.eventType == 'travel') {
      // Travel event - navigate to travel detail
      context.push(Routes.travelDetail(event.id));
    } else if (event.eventType == 'birthday' && event.memberId != null) {
      // Navigate to gift recommendation
      context.push(Routes.giftRecommend(event.memberId!, occasion: 'birthday'));
    } else if (event.eventType == 'anniversary' ||
        event.eventType == 'wedding_anniversary') {
      // Navigate to memories or dates
      context.push(Routes.dates);
    } else if (event.eventType == 'vaccine' || event.eventType == 'checkup') {
      // Navigate to health
      context.push(Routes.health);
    } else if (event.eventType.startsWith('holiday')) {
      // Holiday events - navigate to schedule
      context.push(Routes.schedule);
    }
  }
}
