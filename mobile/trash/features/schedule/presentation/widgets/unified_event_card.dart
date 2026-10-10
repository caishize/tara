import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/unified_event.dart';
import 'event_detail_sheet.dart';

class UnifiedEventCard extends StatelessWidget {
  final UnifiedEvent event;
  final VoidCallback? onTap;

  const UnifiedEventCard({
    super.key,
    required this.event,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap ?? () => _navigateToDetail(context),
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                _buildIcon(),
                const SizedBox(width: 16),
                Expanded(child: _buildInfo()),
                _buildCountdown(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildIcon() {
    return Container(
      width: 52,
      height: 52,
      decoration: BoxDecoration(
        color: event.color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Center(
        child: Text(
          event.icon,
          style: const TextStyle(fontSize: 24),
        ),
      ),
    );
  }

  Widget _buildInfo() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Title
        Text(
          event.title,
          style: AppTextStyles.subtitle1,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        const SizedBox(height: 4),
        // Metadata row
        Row(
          children: [
            // Source badge
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: event.color.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                event.sourceName,
                style: AppTextStyles.overline.copyWith(
                  color: event.color,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            const SizedBox(width: 8),
            // Date
            if (event.dateTime != null) ...[
              Icon(
                Icons.calendar_today_outlined,
                size: 12,
                color: AppColors.textSecondary,
              ),
              const SizedBox(width: 4),
              Text(
                _formatDate(),
                style: AppTextStyles.caption.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ],
        ),
        // Location or member info
        if (event.location != null || event.memberName != null) ...[
          const SizedBox(height: 4),
          Row(
            children: [
              if (event.location != null) ...[
                Icon(
                  Icons.location_on_outlined,
                  size: 12,
                  color: AppColors.textTertiary,
                ),
                const SizedBox(width: 4),
                Flexible(
                  child: Text(
                    event.location!,
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.textTertiary,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
              if (event.location != null && event.memberName != null)
                const SizedBox(width: 8),
              if (event.memberName != null) ...[
                Icon(
                  Icons.person_outline,
                  size: 12,
                  color: AppColors.textTertiary,
                ),
                const SizedBox(width: 4),
                Flexible(
                  child: Text(
                    event.memberName!,
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.textTertiary,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ],
          ),
        ],
      ],
    );
  }

  Widget _buildCountdown() {
    final Color bgColor;
    final Color textColor;

    if (event.isOverdue) {
      bgColor = AppColors.textTertiary.withValues(alpha: 0.1);
      textColor = AppColors.textTertiary;
    } else if (event.isToday) {
      bgColor = AppColors.error.withValues(alpha: 0.1);
      textColor = AppColors.error;
    } else if (event.daysUntil <= 7) {
      bgColor = AppColors.warning.withValues(alpha: 0.1);
      textColor = AppColors.warning;
    } else {
      bgColor = AppColors.primary.withValues(alpha: 0.1);
      textColor = AppColors.primary;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Text(
        event.countdownDisplay,
        style: AppTextStyles.caption.copyWith(
          color: textColor,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  String _formatDate() {
    if (event.dateTime == null) return '';

    // Convert to local time for display
    final localStart = event.dateTime!.toLocal();
    final startDate = DateFormat('M/d').format(localStart);

    if (event.endDateTime != null &&
        event.endDateTime!.difference(event.dateTime!).inDays > 0) {
      final localEnd = event.endDateTime!.toLocal();
      final endDate = DateFormat('M/d').format(localEnd);
      return '$startDate - $endDate';
    }

    return startDate;
  }

  void _navigateToDetail(BuildContext context) {
    // Navigate based on source type
    switch (event.source) {
      case EventSource.importantDate:
        final originalId = event.sourceData['originalId'];
        if (originalId != null) {
          context.push('/dates/$originalId');
        }
        break;
      case EventSource.travelPlan:
        final originalId = event.sourceData['originalId'];
        if (originalId != null) {
          context.push('/travel/$originalId');
        }
        break;
      case EventSource.familyTask:
      case EventSource.extractedSchedule:
      case EventSource.extractedPlan:
      case EventSource.externalCalendar:
      case EventSource.externalTravel:
        EventDetailSheet.show(context, event);
        break;
    }
  }

}

/// Compact version of the event card for list views
class CompactEventCard extends StatelessWidget {
  final UnifiedEvent event;
  final VoidCallback? onTap;

  const CompactEventCard({
    super.key,
    required this.event,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: event.color.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: event.color.withValues(alpha: 0.1)),
      ),
      child: InkWell(
        onTap: onTap,
        child: Row(
          children: [
            // Icon
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: event.color.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Center(
                child: Text(event.icon, style: const TextStyle(fontSize: 18)),
              ),
            ),
            const SizedBox(width: 12),
            // Info
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    event.title,
                    style: AppTextStyles.bodyText2.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (event.dateTime != null)
                    Text(
                      DateFormat('M月d日').format(event.dateTime!.toLocal()),
                      style: AppTextStyles.caption.copyWith(
                        color: AppColors.textTertiary,
                      ),
                    ),
                ],
              ),
            ),
            // Countdown
            Text(
              event.countdownDisplay,
              style: AppTextStyles.caption.copyWith(
                color: event.isToday ? AppColors.error : AppColors.textSecondary,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
