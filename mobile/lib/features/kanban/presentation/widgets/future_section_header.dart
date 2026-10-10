import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';

/// Reusable section header for V4 future timeline view.
///
/// Displays an icon, title, optional count badge, and optional trailing text.
class FutureSectionHeader extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String title;
  final int? count;
  final Color? countColor;
  final String? trailingText;
  final VoidCallback? onTrailingTap;

  const FutureSectionHeader({
    super.key,
    required this.icon,
    required this.iconColor,
    required this.title,
    this.count,
    this.countColor,
    this.trailingText,
    this.onTrailingTap,
  });

  @override
  Widget build(BuildContext context) {
    final badgeColor = countColor ?? iconColor;

    return Row(
      children: [
        Icon(icon, size: 18, color: iconColor),
        const SizedBox(width: 6),
        Text(
          title,
          style: const TextStyle(
            fontSize: 17,
            fontWeight: FontWeight.w600,
            color: AppColors.textPrimary,
            height: 1.3,
          ),
        ),
        const Spacer(),
        if (count != null)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: badgeColor.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(100),
            ),
            child: Text(
              '$count',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: badgeColor,
                height: 1.2,
              ),
            ),
          ),
        if (trailingText != null) ...[
          if (count != null) const SizedBox(width: 8),
          GestureDetector(
            onTap: onTrailingTap,
            child: Text(
              trailingText!,
              style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w500,
                color: AppColors.textTertiary,
                height: 1.3,
              ),
            ),
          ),
        ],
      ],
    );
  }
}
