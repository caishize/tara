import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/unified_event.dart';
import 'unified_event_card.dart';

/// Section header with events grouped by time period
class ScheduleSection extends StatelessWidget {
  final TimePeriod period;
  final List<UnifiedEvent> events;
  final bool initiallyExpanded;

  const ScheduleSection({
    super.key,
    required this.period,
    required this.events,
    this.initiallyExpanded = true,
  });

  @override
  Widget build(BuildContext context) {
    if (events.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildHeader(),
        const SizedBox(height: 8),
        ...events.map((event) => UnifiedEventCard(event: event)),
        const SizedBox(height: 8),
      ],
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 4),
      child: Row(
        children: [
          Container(
            width: 4,
            height: 16,
            decoration: BoxDecoration(
              color: _getHeaderColor(),
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 8),
          Text(
            _getHeaderTitle(),
            style: AppTextStyles.subtitle2.copyWith(
              color: _getHeaderColor(),
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
              color: _getHeaderColor().withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              '${events.length}',
              style: AppTextStyles.caption.copyWith(
                color: _getHeaderColor(),
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _getHeaderTitle() {
    switch (period) {
      case TimePeriod.overdue:
        return '已过期';
      case TimePeriod.today:
        return '今天';
      case TimePeriod.tomorrow:
        return '明天';
      case TimePeriod.thisWeek:
        return '本周';
      case TimePeriod.nextWeek:
        return '下周';
      case TimePeriod.later:
        return '更远';
    }
  }

  Color _getHeaderColor() {
    switch (period) {
      case TimePeriod.overdue:
        return AppColors.textTertiary;
      case TimePeriod.today:
        return AppColors.error;
      case TimePeriod.tomorrow:
        return AppColors.warning;
      case TimePeriod.thisWeek:
        return AppColors.primary;
      case TimePeriod.nextWeek:
        return AppColors.secondary;
      case TimePeriod.later:
        return AppColors.textSecondary;
    }
  }
}

/// Filter chip for event sources
class SourceFilterChip extends StatelessWidget {
  final EventSource? source;  // null means "All"
  final bool isSelected;
  final int? count;
  final VoidCallback onTap;

  const SourceFilterChip({
    super.key,
    this.source,
    required this.isSelected,
    this.count,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected ? _getColor() : Colors.white,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isSelected ? _getColor() : AppColors.divider,
          ),
          boxShadow: isSelected ? [
            BoxShadow(
              color: _getColor().withValues(alpha: 0.3),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ] : null,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              _getIcon(),
              style: const TextStyle(fontSize: 14),
            ),
            const SizedBox(width: 6),
            Text(
              _getLabel(),
              style: AppTextStyles.caption.copyWith(
                color: isSelected ? Colors.white : AppColors.textSecondary,
                fontWeight: FontWeight.w600,
              ),
            ),
            if (count != null && count! > 0) ...[
              const SizedBox(width: 4),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: isSelected
                      ? Colors.white.withValues(alpha: 0.2)
                      : _getColor().withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  '$count',
                  style: AppTextStyles.overline.copyWith(
                    color: isSelected ? Colors.white : _getColor(),
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  String _getLabel() {
    if (source == null) return '全部';
    switch (source!) {
      case EventSource.importantDate:
        return '日期';
      case EventSource.travelPlan:
        return '旅行';
      case EventSource.familyTask:
        return '任务';
      case EventSource.extractedSchedule:
        return '日程';
      case EventSource.extractedPlan:
        return '计划';
      case EventSource.externalCalendar:
        return '外部';
      case EventSource.externalTravel:
        return '行程';
    }
  }

  String _getIcon() {
    if (source == null) return '📋';
    switch (source!) {
      case EventSource.importantDate:
        return '🎂';
      case EventSource.travelPlan:
        return '✈️';
      case EventSource.familyTask:
        return '✅';
      case EventSource.extractedSchedule:
        return '📅';
      case EventSource.extractedPlan:
        return '📝';
      case EventSource.externalCalendar:
        return '📆';
      case EventSource.externalTravel:
        return '🎫';
    }
  }

  Color _getColor() {
    if (source == null) return AppColors.primary;
    switch (source!) {
      case EventSource.importantDate:
        return const Color(0xFFE91E63);
      case EventSource.travelPlan:
        return const Color(0xFF2196F3);
      case EventSource.familyTask:
        return const Color(0xFF6366F1);
      case EventSource.extractedSchedule:
        return const Color(0xFF4CAF50);
      case EventSource.extractedPlan:
        return const Color(0xFFFF9800);
      case EventSource.externalCalendar:
        return const Color(0xFF009688);
      case EventSource.externalTravel:
        return const Color(0xFFFF9800);
    }
  }
}

/// Stats summary bar
class ScheduleStatsBar extends StatelessWidget {
  final int todayCount;
  final int tomorrowCount;
  final int weekCount;

  const ScheduleStatsBar({
    super.key,
    required this.todayCount,
    required this.tomorrowCount,
    required this.weekCount,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        if (todayCount > 0)
          _buildStatChip('今天 $todayCount', AppColors.error),
        if (todayCount > 0 && (tomorrowCount > 0 || weekCount > 0))
          const SizedBox(width: 8),
        if (tomorrowCount > 0)
          _buildStatChip('明天 $tomorrowCount', AppColors.warning),
        if (tomorrowCount > 0 && weekCount > 0)
          const SizedBox(width: 8),
        if (weekCount > 0)
          _buildStatChip('本周 $weekCount', AppColors.primary),
      ],
    );
  }

  Widget _buildStatChip(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        label,
        style: AppTextStyles.caption.copyWith(
          color: color,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
