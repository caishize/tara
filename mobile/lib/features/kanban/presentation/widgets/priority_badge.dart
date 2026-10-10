import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../domain/entities/associated_item.dart';

/// 优先级徽章组件
class PriorityBadge extends StatelessWidget {
  final ItemPriority priority;
  final bool compact;

  const PriorityBadge({
    super.key,
    required this.priority,
    this.compact = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: compact ? 8 : 10,
        vertical: compact ? 3 : 4,
      ),
      decoration: BoxDecoration(
        color: _backgroundColor,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: _borderColor, width: 1),
      ),
      child: Text(
        _label,
        style: TextStyle(
          fontSize: compact ? 11 : 12,
          fontWeight: FontWeight.w500,
          color: _textColor,
        ),
      ),
    );
  }

  String get _label {
    switch (priority) {
      case ItemPriority.stronglyRecommend:
        return '强烈推荐';
      case ItemPriority.convenient:
        return '顺便';
      case ItemPriority.optional:
        return '可选';
    }
  }

  Color get _backgroundColor {
    switch (priority) {
      case ItemPriority.stronglyRecommend:
        return AppColors.primary;
      case ItemPriority.convenient:
        return AppColors.badgeGreen;
      case ItemPriority.optional:
        return AppColors.chipBackground;
    }
  }

  Color get _borderColor {
    switch (priority) {
      case ItemPriority.stronglyRecommend:
        return AppColors.primary;
      case ItemPriority.convenient:
        return AppColors.primary.withValues(alpha: 0.3);
      case ItemPriority.optional:
        return AppColors.divider;
    }
  }

  Color get _textColor {
    switch (priority) {
      case ItemPriority.stronglyRecommend:
        return Colors.white;
      case ItemPriority.convenient:
        return AppColors.primary;
      case ItemPriority.optional:
        return AppColors.textSecondary;
    }
  }
}

/// 数量徽章组件
class CountBadge extends StatelessWidget {
  final int count;
  final String suffix;
  final Color? backgroundColor;
  final Color? textColor;

  const CountBadge({
    super.key,
    required this.count,
    this.suffix = '',
    this.backgroundColor,
    this.textColor,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: backgroundColor ?? AppColors.badgeGreen,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        '$count$suffix',
        style: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w600,
          color: textColor ?? AppColors.primary,
        ),
      ),
    );
  }
}
