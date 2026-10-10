import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../../../app/theme/app_colors.dart';
import '../../domain/entities/trip.dart';
import '../../domain/entities/itinerary.dart';

/// Schedule tab for Trip Detail V2.
/// Shows day-by-day timeline with:
/// - All days collapsible (past collapsed by default, current/future expanded)
/// - Activities grouped by AM/PM within each expanded day
/// - "今天" badge on current day
/// - Bottom CTA
class TripScheduleTab extends StatefulWidget {
  final Trip trip;
  final List<DayItinerary> itinerary;
  final VoidCallback? onAdjustSchedule;

  const TripScheduleTab({
    super.key,
    required this.trip,
    this.itinerary = const [],
    this.onAdjustSchedule,
  });

  @override
  State<TripScheduleTab> createState() => _TripScheduleTabState();
}

class _TripScheduleTabState extends State<TripScheduleTab> {
  /// Tracks which days are expanded. Past days start collapsed,
  /// current and future days start expanded.
  late Set<int> _expandedDays;
  bool _initialized = false;

  void _initExpanded() {
    _expandedDays = {};
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);

    for (final day in widget.itinerary) {
      final dayDate = widget.trip.startDate
          .add(Duration(days: day.dayNumber - 1));
      final dayNorm = DateTime(dayDate.year, dayDate.month, dayDate.day);
      // Expand current day and future days by default
      if (!dayNorm.isBefore(today)) {
        _expandedDays.add(day.dayNumber);
      }
    }
    _initialized = true;
  }

  @override
  Widget build(BuildContext context) {
    if (!_initialized) _initExpanded();

    if (widget.itinerary.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.route, size: 64, color: AppColors.textTertiary),
            const SizedBox(height: 16),
            const Text(
              '还没有行程安排',
              style: TextStyle(color: AppColors.textSecondary),
            ),
          ],
        ),
      );
    }

    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 14, 20, 14),
      children: [
        ...widget.itinerary.map((day) => _buildDaySection(day)),
        const SizedBox(height: 12),
        if (widget.trip.notes != null && widget.trip.notes!.isNotEmpty)
          _buildNotesSection(),
        const SizedBox(height: 16),
        _buildAdjustButton(),
        const SizedBox(height: 24),
      ],
    );
  }

  // ---------------------------------------------------------------------------
  // Day section
  // ---------------------------------------------------------------------------

  Widget _buildDaySection(DayItinerary day) {
    final dayDate =
        widget.trip.startDate.add(Duration(days: day.dayNumber - 1));
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final dayNorm = DateTime(dayDate.year, dayDate.month, dayDate.day);

    final isPast = dayNorm.isBefore(today);
    final isToday = dayNorm.isAtSameMomentAs(today);
    final isExpanded = _expandedDays.contains(day.dayNumber);

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Day header — tap to toggle collapse
          GestureDetector(
            onTap: () {
              setState(() {
                if (_expandedDays.contains(day.dayNumber)) {
                  _expandedDays.remove(day.dayNumber);
                } else {
                  _expandedDays.add(day.dayNumber);
                }
              });
            },
            child: isPast && !isExpanded
                ? _buildCollapsedDayHeader(day, dayDate)
                : isToday
                    ? _buildTodayHeader(day, dayDate, isExpanded)
                    : isPast
                        ? _buildPastExpandedHeader(day, dayDate)
                        : _buildFutureDayHeader(day, dayDate, isExpanded),
          ),
          // Activities grouped by AM / PM
          if (isExpanded && day.activities.isNotEmpty) ...[
            const SizedBox(height: 8),
            _buildGroupedActivities(day, isPast),
          ],
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Day headers
  // ---------------------------------------------------------------------------

  /// Collapsed past day
  Widget _buildCollapsedDayHeader(DayItinerary day, DateTime dayDate) {
    final summary =
        day.activities.map((a) => a.title).take(3).join(' \u2192 ');
    final weekday = DateFormat('E', 'zh_CN').format(dayDate);

    return Opacity(
      opacity: 0.6,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: AppColors.bgMuted,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            const Icon(Icons.check_circle_outline,
                size: 16, color: AppColors.textTertiary),
            const SizedBox(width: 8),
            Text(
              'Day ${day.dayNumber} \u00B7 ${DateFormat('M/d').format(dayDate)} $weekday',
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w700,
                color: AppColors.textTertiary,
              ),
            ),
            if (summary.isNotEmpty) ...[
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  summary,
                  style: const TextStyle(
                      fontSize: 12, color: AppColors.textTertiary),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ] else
              const Spacer(),
            const Icon(Icons.keyboard_arrow_down,
                size: 18, color: AppColors.textTertiary),
          ],
        ),
      ),
    );
  }

  /// Past day expanded header
  Widget _buildPastExpandedHeader(DayItinerary day, DateTime dayDate) {
    final weekday = DateFormat('E', 'zh_CN').format(dayDate);

    return Opacity(
      opacity: 0.6,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: AppColors.bgMuted,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            const Icon(Icons.check_circle_outline,
                size: 16, color: AppColors.textTertiary),
            const SizedBox(width: 8),
            Text(
              'Day ${day.dayNumber} \u00B7 ${DateFormat('M/d').format(dayDate)} $weekday',
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w700,
                color: AppColors.textTertiary,
              ),
            ),
            const Spacer(),
            const Icon(Icons.keyboard_arrow_up,
                size: 18, color: AppColors.textTertiary),
          ],
        ),
      ),
    );
  }

  /// Current day header
  Widget _buildTodayHeader(
      DayItinerary day, DateTime dayDate, bool isExpanded) {
    final weekday = DateFormat('E', 'zh_CN').format(dayDate);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: const BoxDecoration(
              color: AppColors.accentGreen,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            'Day ${day.dayNumber} \u00B7 ${DateFormat('M/d').format(dayDate)} $weekday',
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w800,
              color: AppColors.accentGreen,
            ),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
              color: AppColors.accentGreenLight,
              borderRadius: BorderRadius.circular(6),
            ),
            child: const Text(
              '今天',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: AppColors.accentGreen,
              ),
            ),
          ),
          const Spacer(),
          Icon(
            isExpanded
                ? Icons.keyboard_arrow_up
                : Icons.keyboard_arrow_down,
            size: 18,
            color: AppColors.accentGreen,
          ),
        ],
      ),
    );
  }

  /// Future day header
  Widget _buildFutureDayHeader(
      DayItinerary day, DateTime dayDate, bool isExpanded) {
    final weekday = DateFormat('E', 'zh_CN').format(dayDate);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          Text(
            'Day ${day.dayNumber}',
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w700,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            '${DateFormat('M\u6708d\u65E5', 'zh_CN').format(dayDate)} $weekday',
            style: const TextStyle(
              fontSize: 13,
              color: AppColors.textSecondary,
            ),
          ),
          const Spacer(),
          Icon(
            isExpanded
                ? Icons.keyboard_arrow_up
                : Icons.keyboard_arrow_down,
            size: 18,
            color: AppColors.textTertiary,
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Activities grouped by AM / PM
  // ---------------------------------------------------------------------------

  Widget _buildGroupedActivities(DayItinerary day, bool isPast) {
    // Group activities by the server-provided `period` field.
    final groups = <String, List<ItineraryActivity>>{};
    for (final activity in day.activities) {
      final period = activity.period ?? '上午';
      groups.putIfAbsent(period, () => []).add(activity);
    }

    // Maintain natural order: 上午 → 下午 → 晚上
    const orderedKeys = ['上午', '下午', '晚上'];
    final ordered = <String, List<ItineraryActivity>>{};
    for (final key in orderedKeys) {
      if (groups.containsKey(key)) {
        ordered[key] = groups[key]!;
      }
    }
    // Append any remaining keys not in the standard order
    for (final key in groups.keys) {
      if (!ordered.containsKey(key)) {
        ordered[key] = groups[key]!;
      }
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: ordered.entries.map((entry) {
        return _buildPeriodGroup(entry.key, entry.value, isPast);
      }).toList(),
    );
  }

  Widget _buildPeriodGroup(
    String period,
    List<ItineraryActivity> activities,
    bool isPast,
  ) {
    return Opacity(
      opacity: isPast ? 0.6 : 1.0,
      child: Padding(
        padding: const EdgeInsets.only(left: 8, bottom: 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Period label (上午 / 下午 / 晚上)
            Padding(
              padding: const EdgeInsets.only(bottom: 6, left: 26),
              child: Text(
                period,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  color: isPast
                      ? AppColors.textTertiary
                      : AppColors.accentGreen,
                  letterSpacing: 1,
                ),
              ),
            ),
            // Timeline items
            ...activities.asMap().entries.map((entry) {
              final isLast = entry.key == activities.length - 1;
              return _buildTimelineItem(
                entry.value,
                isLast: isLast,
                isPast: isPast,
              );
            }),
          ],
        ),
      ),
    );
  }

  Widget _buildTimelineItem(
    ItineraryActivity activity, {
    required bool isLast,
    required bool isPast,
  }) {
    return Padding(
      padding: const EdgeInsets.only(left: 0),
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Left dot + line
            SizedBox(
              width: 24,
              child: Column(
                children: [
                  const SizedBox(height: 6),
                  Container(
                    width: 10,
                    height: 10,
                    decoration: BoxDecoration(
                      color: isPast
                          ? Colors.transparent
                          : AppColors.accentGreen,
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: isPast
                            ? AppColors.textTertiary
                            : AppColors.accentGreenLight,
                        width: 2,
                      ),
                    ),
                  ),
                  if (!isLast)
                    Expanded(
                      child: Container(
                        width: 2,
                        color: isPast
                            ? AppColors.divider
                            : AppColors.accentGreenLight,
                      ),
                    ),
                ],
              ),
            ),
            // Right content
            Expanded(
              child: Padding(
                padding: EdgeInsets.only(bottom: isLast ? 0 : 16, left: 8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Time
                    if (activity.time != null)
                      Text(
                        _formatTimeLabel(activity.time!),
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: isPast
                              ? AppColors.textTertiary
                              : AppColors.accentGreen,
                        ),
                      ),
                    const SizedBox(height: 2),
                    // Title
                    Text(
                      activity.title,
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    // Description
                    if (activity.description != null) ...[
                      const SizedBox(height: 2),
                      Text(
                        activity.description!,
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppColors.textSecondary,
                          height: 1.4,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                    // Location
                    if (activity.location != null) ...[
                      const SizedBox(height: 2),
                      Row(
                        children: [
                          const Icon(Icons.location_on_outlined,
                              size: 12, color: AppColors.textTertiary),
                          const SizedBox(width: 2),
                          Text(
                            activity.location!,
                            style: const TextStyle(
                              fontSize: 11,
                              color: AppColors.textTertiary,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Display the raw time label as provided by the backend.
  String _formatTimeLabel(String time) => time;

  // ---------------------------------------------------------------------------
  // Notes section
  // ---------------------------------------------------------------------------

  Widget _buildNotesSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Row(
          children: [
            Icon(Icons.sticky_note_2_outlined,
                size: 14, color: AppColors.textSecondary),
            SizedBox(width: 6),
            Text(
              '行程备注',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: AppColors.textSecondary,
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppColors.borderSubtle, width: 1),
          ),
          child: Text(
            widget.trip.notes!,
            style: const TextStyle(
              fontSize: 12,
              color: AppColors.textSecondary,
              height: 1.5,
            ),
          ),
        ),
      ],
    );
  }

  // ---------------------------------------------------------------------------
  // Bottom CTA
  // ---------------------------------------------------------------------------

  Widget _buildAdjustButton() {
    return GestureDetector(
      onTap: widget.onAdjustSchedule,
      child: Container(
        width: double.infinity,
        height: 42,
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.borderSubtle, width: 1),
        ),
        child: const Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.chat_bubble_outline,
                size: 16, color: AppColors.textSecondary),
            SizedBox(width: 8),
            Text(
              '在对话中调整日程',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w500,
                color: AppColors.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
