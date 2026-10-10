import 'package:flutter/material.dart';
import '../../app/theme/app_colors.dart';

/// A horizontal progress bar showing relationship health percentage.
class RelationshipHealthBar extends StatelessWidget {
  final double percentage;
  final Color? color;
  final Color? backgroundColor;
  final double height;
  final bool showLabel;
  final String? label;

  const RelationshipHealthBar({
    super.key,
    required this.percentage,
    this.color,
    this.backgroundColor,
    this.height = 6,
    this.showLabel = false,
    this.label,
  });

  Color get _color {
    if (color != null) return color!;
    if (percentage >= 80) return AppColors.success;
    if (percentage >= 50) return AppColors.primary;
    if (percentage >= 30) return AppColors.warning;
    return AppColors.error;
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (showLabel || label != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                if (label != null)
                  Text(
                    label!,
                    style: const TextStyle(
                      fontSize: 12,
                      color: AppColors.textSecondary,
                    ),
                  ),
                if (showLabel)
                  Text(
                    '${percentage.toInt()}%',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: _color,
                    ),
                  ),
              ],
            ),
          ),
        Container(
          height: height,
          decoration: BoxDecoration(
            color: backgroundColor ?? AppColors.divider,
            borderRadius: BorderRadius.circular(height / 2),
          ),
          child: FractionallySizedBox(
            alignment: Alignment.centerLeft,
            widthFactor: (percentage / 100).clamp(0.0, 1.0),
            child: Container(
              decoration: BoxDecoration(
                color: _color,
                borderRadius: BorderRadius.circular(height / 2),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

/// A compact relationship health indicator with icon and percentage.
class RelationshipHealthIndicator extends StatelessWidget {
  final double percentage;
  final String? label;
  final bool compact;

  const RelationshipHealthIndicator({
    super.key,
    required this.percentage,
    this.label,
    this.compact = false,
  });

  Color get _color {
    if (percentage >= 80) return AppColors.success;
    if (percentage >= 50) return AppColors.primary;
    if (percentage >= 30) return AppColors.warning;
    return AppColors.error;
  }

  IconData get _icon {
    if (percentage >= 80) return Icons.sentiment_very_satisfied;
    if (percentage >= 50) return Icons.sentiment_satisfied;
    if (percentage >= 30) return Icons.sentiment_neutral;
    return Icons.sentiment_dissatisfied;
  }

  @override
  Widget build(BuildContext context) {
    if (compact) {
      return Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(_icon, size: 16, color: _color),
          const SizedBox(width: 4),
          Text(
            '${percentage.toInt()}%',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: _color,
            ),
          ),
        ],
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(_icon, size: 20, color: _color),
            const SizedBox(width: 8),
            if (label != null)
              Text(
                label!,
                style: const TextStyle(
                  fontSize: 13,
                  color: AppColors.textSecondary,
                ),
              ),
            const Spacer(),
            Text(
              '${percentage.toInt()}%',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: _color,
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        RelationshipHealthBar(percentage: percentage, color: _color),
      ],
    );
  }
}
