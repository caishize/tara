import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../domain/entities/daily_briefing.dart';
import '../../data/models/memory_model.dart';

/// Density-adaptive daily briefing card with DayTheme banner,
/// secretary annotations, recovery slots, and smart deferred content.
///
/// Display modes driven by backend density_level:
/// - FOCUSED: Priority-ordered events, low-priority collapsed, recovery visible
/// - STANDARD: Chronological events with annotations
/// - RELAXED: Expanded with insights, trips, household, tomorrow preview
class BriefingMessageCard extends StatefulWidget {
  final DailyBriefing briefing;
  final List<InsightModel> insights;
  final Function(BriefingSuggestion)? onSuggestionTap;

  const BriefingMessageCard({
    super.key,
    required this.briefing,
    required this.insights,
    this.onSuggestionTap,
  });

  @override
  State<BriefingMessageCard> createState() => _BriefingMessageCardState();
}

class _BriefingMessageCardState extends State<BriefingMessageCard> {
  bool _deferredExpanded = false;
  bool _allEventsVisible = false;

  DailyBriefing get briefing => widget.briefing;
  List<InsightModel> get insights => widget.insights;

  /// Max visible events based on density mode and expansion state
  int get _maxVisibleEvents {
    if (_allEventsVisible) return 999;
    if (briefing.isFocused) return 3;
    if (briefing.isRelaxed) return 8;
    return 5;
  }

  @override
  Widget build(BuildContext context) {
    final ext = Theme.of(context).extension<AppColorsExtension>()!;
    return Container(
      margin: const EdgeInsets.only(bottom: 16, right: 40),
      decoration: BoxDecoration(
        color: ext.cardBackground,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04 * ext.shadowOpacity),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildHeader(context),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // DayTheme banner
                if (briefing.hasDayTheme) ...[
                  _buildDayThemeBanner(context),
                  const SizedBox(height: 8),
                ],
                // Secretary summary
                if (briefing.secretarySummary != null) ...[
                  _buildSecretarySummary(context),
                  const SizedBox(height: 12),
                ],
                // Today schedule with annotations + recovery slots
                if (briefing.todayEvents.isNotEmpty) ...[
                  _buildScheduleSection(context),
                  const SizedBox(height: 12),
                ],
                // Deferred content expander
                if (briefing.deferredCount > 0 && !_deferredExpanded) ...[
                  _buildDeferredExpander(context),
                  const SizedBox(height: 12),
                ],
                // Highlight card for important dates
                if (insights.isNotEmpty) ...[
                  _buildHighlightCard(context),
                  const SizedBox(height: 12),
                ],
                // Briefing insights (from backend orchestration)
                if (briefing.hasInsights && !briefing.isFocused) ...[
                  _buildInsightsSection(context),
                  const SizedBox(height: 12),
                ],
                // Alerts section (suggestions in blue, warnings in orange)
                if (briefing.hasAlerts) ...[
                  _buildAlertsSection(context),
                  const SizedBox(height: 12),
                ],
                // Family / preparation section
                if (briefing.preparationReminders.isNotEmpty) ...[
                  _buildFamilySection(context),
                  const SizedBox(height: 12),
                ],
                // Upcoming trips (RELAXED + STANDARD morning only)
                if (briefing.hasUpcomingTrips && !briefing.isFocused) ...[
                  _buildUpcomingTripsSection(context),
                  const SizedBox(height: 12),
                ],
                // Household status (RELAXED only)
                if (briefing.householdStatus.isNotEmpty && briefing.isRelaxed) ...[
                  _buildHouseholdSection(context),
                  const SizedBox(height: 12),
                ],
                // Tomorrow preview (evening briefing)
                if (briefing.hasTomorrowPreview &&
                    briefing.period == 'evening') ...[
                  _buildTomorrowPreview(context),
                  const SizedBox(height: 12),
                ],
                // Empty state
                if (briefing.todayEvents.isEmpty &&
                    insights.isEmpty &&
                    briefing.preparationReminders.isEmpty &&
                    briefing.alerts.isEmpty)
                  _buildEmptyState(context),
                // Weather / greeting footer
                _buildWeatherFooter(context),
                // Smart suggestion chips
                if (briefing.smartSuggestions.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  _buildSuggestionChips(context),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ---- Header ----

  Widget _buildHeader(BuildContext context) {
    final todoCount = briefing.todayEventCount + insights.length;
    final countText = todoCount > 0 ? ' $todoCount件待办' : '';
    final periodTitle = _periodTitle(briefing.period);

    // Density badge
    final densityBadge = briefing.isFocused
        ? ' · 忙碌'
        : briefing.isRelaxed
            ? ' · 轻松'
            : '';

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: const BoxDecoration(
        gradient: AppColors.primaryGradient,
        borderRadius: BorderRadius.only(
          topLeft: Radius.circular(16),
          topRight: Radius.circular(16),
        ),
      ),
      child: Row(
        children: [
          Text(
            briefing.isFocused ? '\u{1F525}' : '\u{2728}',
            style: const TextStyle(fontSize: 16),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '$periodTitle$countText$densityBadge',
              style: const TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w600,
                color: Colors.white,
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _periodTitle(String period) {
    switch (period.toLowerCase()) {
      case 'afternoon':
        return '午间简报';
      case 'evening':
        return '晚间简报';
      case 'morning':
      default:
        return '晨间简报';
    }
  }

  // ---- DayTheme Banner ----

  Widget _buildDayThemeBanner(BuildContext context) {
    final theme = briefing.dayTheme!;
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(top: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppColors.primary.withValues(alpha: 0.08),
            AppColors.accent3.withValues(alpha: 0.12),
          ],
        ),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: AppColors.primary.withValues(alpha: 0.15),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Theme title
          Row(
            children: [
              const Text('🏷', style: TextStyle(fontSize: 14)),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  theme.title,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppColors.primaryDark,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          // Focus description
          Padding(
            padding: const EdgeInsets.only(left: 22),
            child: Text(
              theme.focus,
              style: TextStyle(
                fontSize: 13,
                color: Theme.of(context).colorScheme.onSurface,
                height: 1.4,
              ),
            ),
          ),
          // Preparation note
          if (theme.prepNote != null) ...[
            const SizedBox(height: 4),
            Padding(
              padding: const EdgeInsets.only(left: 22),
              child: Text(
                theme.prepNote!,
                style: TextStyle(
                  fontSize: 12,
                  color: Theme.of(context)
                      .extension<AppColorsExtension>()!
                      .textTertiary,
                  fontStyle: FontStyle.italic,
                  height: 1.4,
                ),
              ),
            ),
          ],
          // Evening forward (next-day warning)
          if (theme.eveningForward != null &&
              briefing.period == 'evening') ...[
            const SizedBox(height: 6),
            Padding(
              padding: const EdgeInsets.only(left: 22),
              child: Row(
                children: [
                  const Text('⏰', style: TextStyle(fontSize: 12)),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Text(
                      theme.eveningForward!,
                      style: TextStyle(
                        fontSize: 12,
                        color: AppColors.warning,
                        fontWeight: FontWeight.w500,
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  // ---- Secretary Summary ----

  Widget _buildSecretarySummary(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Text(
        briefing.secretarySummary!,
        style: TextStyle(
          fontSize: 13,
          color: Theme.of(context).colorScheme.onSurfaceVariant,
          height: 1.5,
        ),
      ),
    );
  }

  // ---- Schedule Section with Annotations + Recovery Slots ----

  Widget _buildScheduleSection(BuildContext context) {
    // Use priority-ordered events in FOCUSED mode
    final events = briefing.isFocused
        ? briefing.orderedEvents
        : briefing.todayEvents;

    final visibleEvents = events.take(_maxVisibleEvents).toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Row(
          children: [
            Text('📋', style: TextStyle(fontSize: 14)),
            SizedBox(width: 6),
            Text(
              '今日安排',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: AppColors.primary,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ...visibleEvents.map((event) {
          final annotations = briefing.annotationsForEvent(event.id);
          return _buildEventItem(context, event, annotations);
        }),
        // Recovery slots between events (FOCUSED & STANDARD)
        ..._buildRecoverySlots(context),
        // Show remaining count if truncated
        if (events.length > _maxVisibleEvents) ...[
          _buildViewMoreEvents(
            context,
            events.length - _maxVisibleEvents,
          ),
        ],
      ],
    );
  }

  Widget _buildEventItem(
    BuildContext context,
    BriefingEvent event,
    List<SecretaryAnnotation> annotations,
  ) {
    final theme = Theme.of(context);
    final ext = theme.extension<AppColorsExtension>()!;
    final time = event.time ?? '全天';
    final desc = event.description;

    return Padding(
      padding: const EdgeInsets.only(left: 22, bottom: 2),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Event line with icon
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(event.icon, style: const TextStyle(fontSize: 13)),
              const SizedBox(width: 6),
              Expanded(
                child: RichText(
                  text: TextSpan(
                    style: TextStyle(
                      fontSize: 14,
                      color: theme.colorScheme.onSurface,
                      height: 1.5,
                    ),
                    children: [
                      TextSpan(
                        text: time,
                        style: TextStyle(
                          color: ext.textTertiary,
                          fontSize: 13,
                        ),
                      ),
                      const TextSpan(text: ' '),
                      TextSpan(
                        text: event.title,
                        style: const TextStyle(fontWeight: FontWeight.w500),
                      ),
                      if (desc != null && desc.isNotEmpty)
                        TextSpan(
                          text: ' — $desc',
                          style: TextStyle(
                            color: theme.colorScheme.onSurfaceVariant,
                            fontSize: 13,
                          ),
                        ),
                      if (event.memberName != null)
                        TextSpan(
                          text: ' (${event.memberName})',
                          style: TextStyle(
                            color: ext.textTertiary,
                            fontSize: 12,
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ],
          ),
          // Secretary annotations below event
          ...annotations.map((ann) => Padding(
                padding: const EdgeInsets.only(left: 20, top: 2, bottom: 4),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      ann.source == 'preparation_timeline' ? '📝' : '💬',
                      style: const TextStyle(fontSize: 11),
                    ),
                    const SizedBox(width: 4),
                    Expanded(
                      child: Text(
                        ann.text,
                        style: TextStyle(
                          fontSize: 12,
                          color: ext.textTertiary,
                          fontStyle: FontStyle.italic,
                          height: 1.4,
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

  List<Widget> _buildRecoverySlots(BuildContext context) {
    final recoverySlots = briefing.recoverySlots;
    if (recoverySlots.isEmpty) return [];

    return recoverySlots.take(3).map((slot) {
      final note = slot.note ?? '休息一下';
      return Container(
        margin: const EdgeInsets.only(left: 22, top: 4, bottom: 4),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: AppColors.accentGreenLight.withValues(alpha: 0.5),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: AppColors.accentGreen.withValues(alpha: 0.2),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('☕', style: TextStyle(fontSize: 12)),
            const SizedBox(width: 6),
            Text(
              '${slot.start}-${slot.end} $note',
              style: TextStyle(
                fontSize: 12,
                color: AppColors.accentGreen,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      );
    }).toList();
  }

  Widget _buildViewMoreEvents(BuildContext context, int remaining) {
    return Padding(
      padding: const EdgeInsets.only(left: 22, top: 4),
      child: GestureDetector(
        onTap: () => setState(() => _allEventsVisible = true),
        child: Text(
          '还有 $remaining 个日程...',
          style: const TextStyle(
            fontSize: 13,
            color: AppColors.accentBlue,
            fontWeight: FontWeight.w500,
          ),
        ),
      ),
    );
  }

  // ---- Deferred Content Expander ----

  Widget _buildDeferredExpander(BuildContext context) {
    return GestureDetector(
      onTap: () => setState(() => _deferredExpanded = true),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: AppColors.bgMuted,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.expand_more,
              size: 16,
              color: AppColors.textSecondary,
            ),
            const SizedBox(width: 4),
            Text(
              '查看更多 (${briefing.deferredCount})',
              style: const TextStyle(
                fontSize: 12,
                color: AppColors.textSecondary,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ---- Insights Section ----

  Widget _buildInsightsSection(BuildContext context) {
    final theme = Theme.of(context);
    final visibleInsights = briefing.insights.take(3).toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Row(
          children: [
            Text('💡', style: TextStyle(fontSize: 14)),
            SizedBox(width: 6),
            Text(
              '秘书提醒',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: AppColors.primary,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ...visibleInsights.map((insight) => Padding(
              padding: const EdgeInsets.only(left: 22, bottom: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    insight.isUrgent ? '🔔' : '·',
                    style: TextStyle(
                      fontSize: insight.isUrgent ? 12 : 14,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      insight.content,
                      style: TextStyle(
                        fontSize: 13,
                        color: theme.colorScheme.onSurface,
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),
            )),
      ],
    );
  }

  // ---- Alerts Section (with suggestion style) ----

  Widget _buildAlertsSection(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: briefing.alerts.take(3).map((alert) {
        final color = Color(alert.severityColorValue);
        return Container(
          margin: const EdgeInsets.only(bottom: 6),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.06),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: color.withValues(alpha: 0.15)),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(alert.icon, style: const TextStyle(fontSize: 14)),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      alert.title,
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: color,
                      ),
                    ),
                    if (alert.description.isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Text(
                        alert.description,
                        style: TextStyle(
                          fontSize: 12,
                          color: Theme.of(context)
                              .colorScheme
                              .onSurfaceVariant,
                          height: 1.4,
                        ),
                      ),
                    ],
                    // Actionable button for suggestions
                    if (alert.isSuggestion &&
                        alert.actionLabel != null) ...[
                      const SizedBox(height: 6),
                      GestureDetector(
                        onTap: () => widget.onSuggestionTap?.call(
                          BriefingSuggestion(
                            label: alert.actionLabel!,
                            actionType: 'open_chat',
                            actionData: {
                              'prefill_text': alert.description,
                              'alert_id': alert.id,
                            },
                          ),
                        ),
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: color.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            alert.actionLabel!,
                            style: TextStyle(
                              fontSize: 12,
                              color: color,
                              fontWeight: FontWeight.w500,
                            ),
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
      }).toList(),
    );
  }

  // ---- Highlight Card ----

  Widget _buildHighlightCard(BuildContext context) {
    final insight = insights.first;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.accent2.withValues(alpha: 0.18),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '🥰 对了，${insight.content}',
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: AppColors.primary,
            ),
          ),
          const SizedBox(height: 8),
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Expanded(
                child: Text(
                  insights.length > 1
                      ? '还有 ${insights.length} 条提醒需要关注'
                      : '提前准备一下，别忘了',
                  style: TextStyle(
                    fontSize: 14,
                    color: Theme.of(context).colorScheme.onSurface,
                    height: 1.4,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              GestureDetector(
                onTap: () =>
                    widget.onSuggestionTap?.call(BriefingSuggestion(
                  label: '看礼物',
                  actionType: 'view_gifts',
                  actionData: {
                    'insight_content': insight.content,
                  },
                )),
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: AppColors.primary,
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: const Text(
                    '看礼物',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      color: Colors.white,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // ---- Family Section ----

  Widget _buildFamilySection(BuildContext context) {
    final theme = Theme.of(context);
    final maxReminders = briefing.isFocused ? 1 : 3;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Row(
          children: [
            Text('🏠', style: TextStyle(fontSize: 14)),
            SizedBox(width: 6),
            Text(
              '家庭',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: AppColors.secondary,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ...briefing.preparationReminders.take(maxReminders).map(
              (item) => Padding(
                padding: const EdgeInsets.only(left: 22, bottom: 4),
                child: Text(
                  item,
                  style: TextStyle(
                    fontSize: 14,
                    color: theme.colorScheme.onSurface,
                    height: 1.5,
                  ),
                ),
              ),
            ),
      ],
    );
  }

  // ---- Upcoming Trips ----

  Widget _buildUpcomingTripsSection(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Row(
          children: [
            Text('✈️', style: TextStyle(fontSize: 14)),
            SizedBox(width: 6),
            Text(
              '即将出行',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: AppColors.accentBlue,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ...briefing.upcomingTrips.take(2).map((trip) {
          final days = trip.daysUntilStart;
          final daysText = days == 0
              ? '今天'
              : days == 1
                  ? '明天'
                  : '$days天后';
          return Padding(
            padding: const EdgeInsets.only(left: 22, bottom: 4),
            child: Text(
              '$daysText ${trip.destination}${trip.tripName != null ? " · ${trip.tripName}" : ""}',
              style: TextStyle(
                fontSize: 13,
                color: trip.isImminent
                    ? AppColors.warning
                    : Theme.of(context).colorScheme.onSurface,
                height: 1.5,
              ),
            ),
          );
        }),
      ],
    );
  }

  // ---- Household Status ----

  Widget _buildHouseholdSection(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Row(
          children: [
            Text('🔧', style: TextStyle(fontSize: 14)),
            SizedBox(width: 6),
            Text(
              '家务提醒',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: AppColors.secondary,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ...briefing.householdStatus.take(2).map((item) => Padding(
              padding: const EdgeInsets.only(left: 22, bottom: 4),
              child: Row(
                children: [
                  Text(item.icon, style: const TextStyle(fontSize: 13)),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      item.description,
                      style: TextStyle(
                        fontSize: 13,
                        color: item.isUrgent
                            ? AppColors.warning
                            : Theme.of(context).colorScheme.onSurface,
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),
            )),
      ],
    );
  }

  // ---- Tomorrow Preview ----

  Widget _buildTomorrowPreview(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Row(
          children: [
            Text('📅', style: TextStyle(fontSize: 14)),
            SizedBox(width: 6),
            Text(
              '明日预览',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: AppColors.primary,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ...briefing.tomorrowPreview.take(3).map((event) {
          final time = event.time ?? '全天';
          return Padding(
            padding: const EdgeInsets.only(left: 22, bottom: 4),
            child: Text(
              '$time ${event.title}',
              style: TextStyle(
                fontSize: 13,
                color: theme.colorScheme.onSurfaceVariant,
                height: 1.5,
              ),
            ),
          );
        }),
      ],
    );
  }

  // ---- Weather Footer ----

  Widget _buildWeatherFooter(BuildContext context) {
    final ext = Theme.of(context).extension<AppColorsExtension>()!;
    final greeting = briefing.greeting;
    if (greeting.isEmpty) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Text(
        greeting,
        style: TextStyle(
          fontSize: 12,
          color: ext.textTertiary,
          height: 1.4,
        ),
      ),
    );
  }

  // ---- Suggestion Chips ----

  Widget _buildSuggestionChips(BuildContext context) {
    final primary = Theme.of(context).colorScheme.primary;
    final maxSuggestions = briefing.isFocused ? 2 : 4;
    return Wrap(
      spacing: 8,
      runSpacing: 6,
      children:
          briefing.smartSuggestions.take(maxSuggestions).map((suggestion) {
        return GestureDetector(
          onTap: () => widget.onSuggestionTap?.call(suggestion),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: primary.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: primary.withValues(alpha: 0.2),
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  _getActionIcon(suggestion.actionType),
                  size: 14,
                  color: primary,
                ),
                const SizedBox(width: 4),
                Text(
                  suggestion.label,
                  style: TextStyle(
                    fontSize: 12,
                    color: primary,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }

  IconData _getActionIcon(String actionType) {
    switch (actionType) {
      case 'navigate_to_trip':
        return Icons.flight_takeoff;
      case 'navigate_to_kanban':
        return Icons.dashboard_outlined;
      case 'open_chat':
        return Icons.chat_bubble_outline;
      case 'view_graph':
        return Icons.hub_outlined;
      case 'view_insights':
        return Icons.lightbulb_outline;
      case 'view_gifts':
        return Icons.card_giftcard;
      default:
        return Icons.touch_app_outlined;
    }
  }

  // ---- Empty State ----

  Widget _buildEmptyState(BuildContext context) {
    final message = briefing.isRelaxed
        ? '今天没什么大事，享受轻松的一天吧！'
        : '今天没有特别安排，享受美好的一天吧！';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Text(
        message,
        style: TextStyle(
          fontSize: 14,
          color: Theme.of(context).colorScheme.onSurfaceVariant,
        ),
      ),
    );
  }
}

/// Smart suggestion card that appears in chat flow.
/// Shows contextual AI suggestions based on conversation.
class SmartSuggestionCard extends StatelessWidget {
  final String title;
  final List<SmartSuggestionItem> suggestions;
  final Function(String)? onSuggestionTap;

  const SmartSuggestionCard({
    super.key,
    required this.title,
    required this.suggestions,
    this.onSuggestionTap,
  });

  @override
  Widget build(BuildContext context) {
    final primary = Theme.of(context).colorScheme.primary;
    final ext = Theme.of(context).extension<AppColorsExtension>()!;
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: ext.cardBackground,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: primary.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: BoxDecoration(
              color: primary.withValues(alpha: 0.1),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(16),
                topRight: Radius.circular(16),
              ),
            ),
            child: Row(
              children: [
                Icon(Icons.location_on_outlined, size: 16, color: primary),
                const SizedBox(width: 6),
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: primary,
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: suggestions
                  .map((s) => _buildSuggestionItem(context, s))
                  .toList(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSuggestionItem(BuildContext context, SmartSuggestionItem item) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: GestureDetector(
        onTap: () => onSuggestionTap?.call(item.action ?? item.content),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(item.icon, size: 16, color: item.iconColor),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                item.content,
                style: TextStyle(
                  fontSize: 14,
                  color: Theme.of(context).colorScheme.onSurface,
                  height: 1.4,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class SmartSuggestionItem {
  final IconData icon;
  final Color iconColor;
  final String content;
  final String? action;

  const SmartSuggestionItem({
    required this.icon,
    required this.iconColor,
    required this.content,
    this.action,
  });
}
