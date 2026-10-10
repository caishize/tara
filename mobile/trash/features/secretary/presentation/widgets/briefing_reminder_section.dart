import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';

/// Section widget for displaying preparation reminders.
class BriefingReminderSection extends StatelessWidget {
  final List<String> reminders;

  const BriefingReminderSection({
    super.key,
    required this.reminders,
  });

  @override
  Widget build(BuildContext context) {
    if (reminders.isEmpty) {
      return const SizedBox.shrink();
    }

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.warning.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: AppColors.warning.withValues(alpha: 0.3),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            children: [
              Icon(
                Icons.notifications_active,
                size: 20,
                color: AppColors.warning,
              ),
              const SizedBox(width: 8),
              Text(
                '提醒准备',
                style: AppTextStyles.subtitle1.copyWith(
                  color: AppColors.warning,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),

          // Reminder list
          ...reminders.map((reminder) => _buildReminderItem(reminder)),
        ],
      ),
    );
  }

  Widget _buildReminderItem(String reminder) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 6,
            height: 6,
            margin: const EdgeInsets.only(top: 6, right: 10),
            decoration: BoxDecoration(
              color: AppColors.warning,
              shape: BoxShape.circle,
            ),
          ),
          Expanded(
            child: Text(
              reminder,
              style: AppTextStyles.bodyText2.copyWith(
                color: AppColors.textPrimary,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
