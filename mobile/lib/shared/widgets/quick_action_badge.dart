import 'package:flutter/material.dart';
import '../../app/theme/app_colors.dart';

/// Quick action badge widget for displaying counts with icons/emojis.
/// Used for "今日3项", "人情2项" style badges in the conversation screen.
class QuickActionBadge extends StatelessWidget {
  final String? emoji;
  final IconData? icon;
  final String label;
  final int? count;
  final Color? backgroundColor;
  final Color? textColor;
  final Color? iconColor;
  final VoidCallback? onTap;

  const QuickActionBadge({
    super.key,
    this.emoji,
    this.icon,
    required this.label,
    this.count,
    this.backgroundColor,
    this.textColor,
    this.iconColor,
    this.onTap,
  }) : assert(emoji != null || icon != null, 'Either emoji or icon must be provided');

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: backgroundColor ?? AppColors.chipBackground,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null)
              Icon(
                icon,
                size: 16,
                color: iconColor ?? textColor ?? AppColors.textPrimary,
              )
            else if (emoji != null)
              Text(
                emoji!,
                style: const TextStyle(fontSize: 14),
              ),
            const SizedBox(width: 6),
            Text(
              count != null ? '$label$count项' : label,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w500,
                color: textColor ?? AppColors.textPrimary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// A row of quick action badges with horizontal scrolling.
class QuickActionBadgeRow extends StatelessWidget {
  final List<QuickActionBadgeData> badges;
  final EdgeInsets? padding;

  const QuickActionBadgeRow({
    super.key,
    required this.badges,
    this.padding,
  });

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: padding ?? const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: badges.map((badge) {
          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: QuickActionBadge(
              emoji: badge.emoji,
              icon: badge.icon,
              label: badge.label,
              count: badge.count,
              backgroundColor: badge.backgroundColor,
              textColor: badge.textColor,
              iconColor: badge.iconColor,
              onTap: badge.onTap,
            ),
          );
        }).toList(),
      ),
    );
  }
}

/// Data class for QuickActionBadge.
class QuickActionBadgeData {
  final String? emoji;
  final IconData? icon;
  final String label;
  final int? count;
  final Color? backgroundColor;
  final Color? textColor;
  final Color? iconColor;
  final VoidCallback? onTap;

  const QuickActionBadgeData({
    this.emoji,
    this.icon,
    required this.label,
    this.count,
    this.backgroundColor,
    this.textColor,
    this.iconColor,
    this.onTap,
  }) : assert(emoji != null || icon != null, 'Either emoji or icon must be provided');
}
