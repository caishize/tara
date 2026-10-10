import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/daily_briefing.dart';

/// Card widget for displaying a single briefing event.
class BriefingEventCard extends StatelessWidget {
  final BriefingEvent event;
  final VoidCallback? onTap;
  final VoidCallback? onActionTap;

  const BriefingEventCard({
    super.key,
    required this.event,
    this.onTap,
    this.onActionTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: AppColors.cardShadow,
      ),
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Icon
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: _getEventColor().withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Center(
                    child: Text(
                      event.icon,
                      style: const TextStyle(fontSize: 22),
                    ),
                  ),
                ),
                const SizedBox(width: 12),

                // Content
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Title row with time
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              event.title,
                              style: AppTextStyles.subtitle1.copyWith(
                                fontWeight: FontWeight.w600,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          if (!event.isAllDay)
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8,
                                vertical: 2,
                              ),
                              decoration: BoxDecoration(
                                color: AppColors.chipBackground,
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Text(
                                event.displayTime,
                                style: AppTextStyles.caption.copyWith(
                                  color: AppColors.primary,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ),
                        ],
                      ),

                      // Description
                      if (event.description != null) ...[
                        const SizedBox(height: 4),
                        Text(
                          event.description!,
                          style: AppTextStyles.bodyText2.copyWith(
                            color: AppColors.textSecondary,
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],

                      // Member name
                      if (event.memberName != null) ...[
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            Icon(
                              Icons.person_outline,
                              size: 14,
                              color: AppColors.textTertiary,
                            ),
                            const SizedBox(width: 4),
                            Text(
                              event.memberName!,
                              style: AppTextStyles.caption,
                            ),
                          ],
                        ),
                      ],

                      // Action button
                      if (event.actionLabel != null) ...[
                        const SizedBox(height: 8),
                        GestureDetector(
                          onTap: onActionTap,
                          child: Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 6,
                            ),
                            decoration: BoxDecoration(
                              color: AppColors.primary.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              event.actionLabel!,
                              style: AppTextStyles.caption.copyWith(
                                color: AppColors.primary,
                                fontWeight: FontWeight.w600,
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
          ),
        ),
      ),
    );
  }

  Color _getEventColor() {
    switch (event.eventType) {
      case 'birthday':
        return AppColors.accent1;
      case 'anniversary':
      case 'wedding_anniversary':
        return AppColors.accent2;
      case 'holiday':
      case 'holiday_legal':
      case 'holiday_lunar':
      case 'holiday_solar_term':
        return AppColors.secondary;
      case 'vaccine':
      case 'checkup':
        return AppColors.info;
      case 'memorial':
        return AppColors.textSecondary;
      case 'travel':
        return Colors.blue;
      default:
        return AppColors.primary;
    }
  }
}
