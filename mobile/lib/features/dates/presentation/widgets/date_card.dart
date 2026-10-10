import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/important_date.dart';

class DateCard extends StatelessWidget {
  final ImportantDate date;
  final VoidCallback? onTap;
  final VoidCallback? onDelete;

  const DateCard({
    super.key,
    required this.date,
    this.onTap,
    this.onDelete,
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
          onTap: onTap ?? () => context.push('/dates/${date.id}'),
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                _buildDateBadge(),
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

  Widget _buildDateBadge() {
    return Container(
      width: 56,
      height: 56,
      decoration: BoxDecoration(
        gradient: _getGradientForType(),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            date.dateTypeIcon,
            style: const TextStyle(fontSize: 24),
          ),
        ],
      ),
    );
  }

  LinearGradient _getGradientForType() {
    switch (date.dateType) {
      case DateType.birthday:
        return const LinearGradient(
          colors: [Color(0xFFFF6B6B), Color(0xFFFFE66D)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      case DateType.anniversary:
        return const LinearGradient(
          colors: [Color(0xFFFF6B9D), Color(0xFFC44569)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      case DateType.holiday:
        return const LinearGradient(
          colors: [Color(0xFF4ECDC4), Color(0xFF44BD32)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      case DateType.memorial:
        return const LinearGradient(
          colors: [Color(0xFF636E72), Color(0xFF2D3436)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      case DateType.custom:
        return AppColors.primaryGradient;
    }
  }

  Widget _buildInfo() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          date.title,
          style: AppTextStyles.subtitle1,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        const SizedBox(height: 4),
        Row(
          children: [
            const Icon(
              Icons.calendar_today_outlined,
              size: 14,
              color: AppColors.textSecondary,
            ),
            const SizedBox(width: 4),
            Text(
              DateFormat('M月d日').format(date.date),
              style: AppTextStyles.caption.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
            if (date.memberName != null) ...[
              const SizedBox(width: 12),
              const Icon(
                Icons.person_outline,
                size: 14,
                color: AppColors.textSecondary,
              ),
              const SizedBox(width: 4),
              Text(
                date.memberName!,
                style: AppTextStyles.caption.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ],
        ),
      ],
    );
  }

  Widget _buildCountdown() {
    final days = date.daysUntilNext;
    final isToday = days == 0;
    final isUrgent = days <= 7;

    Color bgColor;
    Color textColor;
    String text;

    if (isToday) {
      bgColor = AppColors.error.withValues(alpha: 0.1);
      textColor = AppColors.error;
      text = '今天';
    } else if (isUrgent) {
      bgColor = AppColors.warning.withValues(alpha: 0.1);
      textColor = AppColors.warning;
      text = '$days天后';
    } else {
      bgColor = AppColors.primary.withValues(alpha: 0.1);
      textColor = AppColors.primary;
      text = '$days天后';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        text,
        style: AppTextStyles.caption.copyWith(
          color: textColor,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class CompactDateCard extends StatelessWidget {
  final ImportantDate date;

  const CompactDateCard({super.key, required this.date});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 140,
      margin: const EdgeInsets.only(right: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(date.dateTypeIcon, style: const TextStyle(fontSize: 20)),
              const Spacer(),
              _buildDaysChip(),
            ],
          ),
          const Spacer(),
          Text(
            date.title,
            style: AppTextStyles.bodyText2.copyWith(
              fontWeight: FontWeight.w600,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 4),
          Text(
            DateFormat('M月d日').format(date.date),
            style: AppTextStyles.caption.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDaysChip() {
    final days = date.daysUntilNext;
    final isToday = days == 0;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: isToday
            ? AppColors.error.withValues(alpha: 0.1)
            : AppColors.primary.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        isToday ? '今天' : '$days天',
        style: AppTextStyles.overline.copyWith(
          color: isToday ? AppColors.error : AppColors.primary,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
