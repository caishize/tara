import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../domain/entities/conflict_alert.dart';

/// 冲突/提醒卡片组件
class ConflictAlertCard extends StatelessWidget {
  final ConflictAlert alert;
  final VoidCallback? onTap;
  final VoidCallback? onDismiss;
  final VoidCallback? onAction;

  const ConflictAlertCard({
    super.key,
    required this.alert,
    this.onTap,
    this.onDismiss,
    this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: _getBorderColor(),
          width: 1,
        ),
        boxShadow: AppColors.cardShadow,
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // 警告图标
                _buildLeadingIcon(),
                const SizedBox(width: 12),
                // 内容
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        alert.title,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: AppColors.textPrimary,
                        ),
                      ),
                      if (alert.description != null) ...[
                        const SizedBox(height: 4),
                        Text(
                          alert.description!,
                          style: TextStyle(
                            fontSize: 13,
                            color: _getDescriptionColor(),
                          ),
                        ),
                      ],
                      if (alert.autoResolved && alert.resolutionNote != null) ...[
                        const SizedBox(height: 8),
                        _buildAutoResolvedChip(),
                      ] else if (alert.needsUserConfirm) ...[
                        const SizedBox(height: 12),
                        _buildConfirmButton(),
                      ] else if (alert.hasSuggestedAction) ...[
                        const SizedBox(height: 12),
                        _buildActionButton(),
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

  Widget _buildLeadingIcon() {
    return Container(
      width: 44,
      height: 44,
      decoration: BoxDecoration(
        color: _getIconBackgroundColor(),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Icon(
        _getAlertIcon(),
        color: _getIconColor(),
        size: 22,
      ),
    );
  }

  Widget _buildActionButton() {
    return GestureDetector(
      onTap: onAction,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: _getActionButtonColor(),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(
          alert.suggestedAction!,
          style: TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w500,
            color: _getActionTextColor(),
          ),
        ),
      ),
    );
  }

  Widget _buildConfirmButton() {
    return GestureDetector(
      onTap: onAction,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: AppColors.primary.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(8),
        ),
        child: const Text(
          '确认调整',
          style: TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w500,
            color: AppColors.primary,
          ),
        ),
      ),
    );
  }

  Widget _buildAutoResolvedChip() {
    return GestureDetector(
      onTap: onAction,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: AppColors.success.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.check_circle_outline,
              size: 14,
              color: AppColors.success,
            ),
            const SizedBox(width: 4),
            Text(
              alert.resolutionNote ?? '已自动调整',
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w500,
                color: AppColors.success,
              ),
            ),
          ],
        ),
      ),
    );
  }

  IconData _getAlertIcon() {
    switch (alert.alertType) {
      case AlertType.dateConflict:
        return Icons.event_busy;
      case AlertType.timeSensitive:
        return Icons.access_time;
      case AlertType.reminder:
        return Icons.notifications_outlined;
      case AlertType.warning:
        return Icons.warning_amber_outlined;
    }
  }

  Color _getIconBackgroundColor() {
    switch (alert.alertType) {
      case AlertType.dateConflict:
        return AppColors.badgeOrange;
      case AlertType.timeSensitive:
        return AppColors.badgePink;
      case AlertType.reminder:
        return AppColors.badgeBlue;
      case AlertType.warning:
        return const Color(0xFFFFF8E1);
    }
  }

  Color _getIconColor() {
    switch (alert.alertType) {
      case AlertType.dateConflict:
        return AppColors.warning;
      case AlertType.timeSensitive:
        return const Color(0xFFE91E63);
      case AlertType.reminder:
        return const Color(0xFF1976D2);
      case AlertType.warning:
        return AppColors.warning;
    }
  }

  Color _getBorderColor() {
    if (alert.isHighPriority) {
      return AppColors.warning.withValues(alpha: 0.3);
    }
    return Colors.transparent;
  }

  Color _getDescriptionColor() {
    if (alert.isConflict || alert.isHighPriority) {
      return AppColors.warning;
    }
    return AppColors.textSecondary;
  }

  Color _getActionButtonColor() {
    if (alert.isHighPriority) {
      return AppColors.warning.withValues(alpha: 0.15);
    }
    return AppColors.chipBackground;
  }

  Color _getActionTextColor() {
    if (alert.isHighPriority) {
      return AppColors.warning;
    }
    return AppColors.primary;
  }
}
