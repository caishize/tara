import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/repositories/guardian_repository.dart';

/// Activity item in the trip planning timeline
class TimelineActivityItem extends StatelessWidget {
  final GuardianActivity activity;
  final bool isFirst;
  final bool isLast;
  final VoidCallback? onTap;

  const TimelineActivityItem({
    super.key,
    required this.activity,
    this.isFirst = false,
    this.isLast = false,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Timeline line and dot
              SizedBox(
                width: 50,
                child: Column(
                  children: [
                    // Top line
                    if (!isFirst)
                      Container(
                        width: 2,
                        height: 12,
                        color: AppColors.divider,
                      )
                    else
                      const SizedBox(height: 12),

                    // Dot
                    Container(
                      width: 12,
                      height: 12,
                      decoration: BoxDecoration(
                        color: AppColors.primary,
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: AppColors.primary.withValues(alpha: 0.3),
                          width: 3,
                        ),
                      ),
                    ),

                    // Bottom line
                    Expanded(
                      child: Container(
                        width: 2,
                        color: isLast ? Colors.transparent : AppColors.divider,
                      ),
                    ),
                  ],
                ),
              ),

              // Time
              SizedBox(
                width: 50,
                child: Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    activity.time,
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.primary,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ),

              const SizedBox(width: 8),

              // Content card
              Expanded(
                child: Container(
                  margin: const EdgeInsets.only(bottom: 12),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.cardBackground,
                    borderRadius: BorderRadius.circular(12),
                    boxShadow: AppColors.cardShadow,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              activity.title,
                              style: AppTextStyles.subtitle2.copyWith(
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                          if (activity.status != null)
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8,
                                vertical: 2,
                              ),
                              decoration: BoxDecoration(
                                color: AppColors.success.withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                activity.status!,
                                style: AppTextStyles.overline.copyWith(
                                  color: AppColors.success,
                                ),
                              ),
                            ),
                        ],
                      ),
                      if (activity.subtitle != null) ...[
                        const SizedBox(height: 4),
                        Text(
                          activity.subtitle!,
                          style: AppTextStyles.caption.copyWith(
                            color: AppColors.textSecondary,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Card showing secretary advice
class SecretaryAdviceCard extends StatelessWidget {
  final String advice;

  const SecretaryAdviceCard({
    super.key,
    required this.advice,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.primary.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: AppColors.primary.withValues(alpha: 0.2),
          width: 1,
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: AppColors.primary.withValues(alpha: 0.1),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.lightbulb_outline,
              size: 16,
              color: AppColors.primary,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '秘书建议',
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.primary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  advice,
                  style: AppTextStyles.bodyText2.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
