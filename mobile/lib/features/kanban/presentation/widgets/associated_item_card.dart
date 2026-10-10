import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../../app/theme/app_colors.dart';
import '../../domain/entities/associated_item.dart';
import 'context_hint_chip.dart';
import 'priority_badge.dart';

/// 关联事项卡片组件
class AssociatedItemCard extends StatelessWidget {
  final AssociatedItem item;
  final VoidCallback? onTap;
  final VoidCallback? onDismiss;
  final VoidCallback? onConfirm;

  const AssociatedItemCard({
    super.key,
    required this.item,
    this.onTap,
    this.onDismiss,
    this.onConfirm,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(16),
        boxShadow: AppColors.cardShadow,
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // 主要内容行
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // 图标
                    _buildLeadingIcon(),
                    const SizedBox(width: 12),
                    // 标题和副标题
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            item.title,
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                              color: AppColors.textPrimary,
                            ),
                          ),
                          if (item.subtitle != null) ...[
                            const SizedBox(height: 4),
                            Text(
                              item.subtitle!,
                              style: const TextStyle(
                                fontSize: 13,
                                color: AppColors.textSecondary,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                    // 优先级徽章
                    PriorityBadge(priority: item.priority),
                  ],
                ),
                // 上下文提示
                if (item.hasContextHint) ...[
                  const SizedBox(height: 12),
                  ContextHintChip(hint: item.contextHint!),
                ],
                // 操作按钮行
                if (onConfirm != null || onDismiss != null)
                  _buildActionRow(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  /// 确认/忽略操作按钮行
  Widget _buildActionRow() {
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.end,
        children: [
          if (onDismiss != null)
            _ActionChip(
              icon: Icons.close,
              label: '忽略',
              onTap: onDismiss!,
              color: AppColors.textTertiary,
            ),
          if (onDismiss != null && onConfirm != null)
            const SizedBox(width: 12),
          if (onConfirm != null)
            _ActionChip(
              icon: Icons.check,
              label: '确认',
              onTap: onConfirm!,
              color: AppColors.primary,
              filled: true,
            ),
        ],
      ),
    );
  }

  Widget _buildLeadingIcon() {
    return Container(
      width: 44,
      height: 44,
      decoration: BoxDecoration(
        color: _getIconBackgroundColor(),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Icon(
        _getItemIcon(),
        color: _getIconColor(),
        size: 22,
      ),
    );
  }

  IconData _getItemIcon() {
    switch (item.itemType) {
      case ItemType.person:
        return Icons.person_outline;
      case ItemType.task:
        return Icons.check_circle_outline;
      case ItemType.gift:
        return Icons.card_giftcard_outlined;
      case ItemType.place:
        return Icons.place_outlined;
      case ItemType.business:
        return Icons.business_outlined;
    }
  }

  Color _getIconBackgroundColor() {
    switch (item.itemType) {
      case ItemType.person:
        return AppColors.badgePurple;
      case ItemType.task:
        return AppColors.badgeBlue;
      case ItemType.gift:
        return AppColors.badgePink;
      case ItemType.place:
        return AppColors.badgeGreen;
      case ItemType.business:
        return AppColors.badgeGreen;
    }
  }

  Color _getIconColor() {
    switch (item.itemType) {
      case ItemType.person:
        return const Color(0xFF8B5CF6);
      case ItemType.task:
        return const Color(0xFF1976D2);
      case ItemType.gift:
        return const Color(0xFFEC4899);
      case ItemType.place:
        return AppColors.primary;
      case ItemType.business:
        return AppColors.primary;
    }
  }
}

/// 操作按钮组件
class _ActionChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final Color color;
  final bool filled;

  const _ActionChip({
    required this.icon,
    required this.label,
    required this.onTap,
    required this.color,
    this.filled = false,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () {
        HapticFeedback.lightImpact();
        onTap();
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: filled
              ? color.withValues(alpha: 0.15)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(8),
          border: filled
              ? null
              : Border.all(color: color.withValues(alpha: 0.3)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: color),
            const SizedBox(width: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w500,
                color: color,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
