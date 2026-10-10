import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../data/models/memory_model.dart';

/// Card widget to display a secretary insight
class InsightCard extends StatelessWidget {
  final InsightModel insight;
  final VoidCallback? onTap;
  final VoidCallback? onDismiss;
  final void Function(String action)? onAction;

  const InsightCard({
    super.key,
    required this.insight,
    this.onTap,
    this.onDismiss,
    this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    final isUrgent = insight.isUrgent || insight.isHighPriority;

    return GestureDetector(
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [AppColors.shadowLight],
          border: isUrgent
              ? Border.all(color: AppColors.warning.withValues(alpha: 0.5), width: 1.5)
              : null,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 12, 8, 0),
              child: Row(
                children: [
                  // Type icon
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: _getTypeColor().withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      insight.typeIcon,
                      style: const TextStyle(fontSize: 16),
                    ),
                  ),
                  const SizedBox(width: 10),
                  // Title
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            if (isUrgent) ...[
                              Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 6,
                                  vertical: 2,
                                ),
                                decoration: BoxDecoration(
                                  color: AppColors.warning.withValues(alpha: 0.15),
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(
                                  '重要',
                                  style: AppTextStyles.caption.copyWith(
                                    color: AppColors.warning,
                                    fontWeight: FontWeight.w600,
                                    fontSize: 10,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 6),
                            ],
                            Expanded(
                              child: Text(
                                insight.title,
                                style: AppTextStyles.subtitle2.copyWith(
                                  fontWeight: FontWeight.w600,
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 2),
                        Text(
                          insight.typeDisplayName,
                          style: AppTextStyles.caption.copyWith(
                            color: _getTypeColor(),
                            fontSize: 11,
                          ),
                        ),
                      ],
                    ),
                  ),
                  // Dismiss button
                  if (onDismiss != null)
                    IconButton(
                      onPressed: onDismiss,
                      icon: const Icon(
                        Icons.close,
                        size: 18,
                        color: AppColors.textHint,
                      ),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(
                        minWidth: 32,
                        minHeight: 32,
                      ),
                    ),
                ],
              ),
            ),

            // Content
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 8, 14, 10),
              child: Text(
                insight.content,
                style: AppTextStyles.bodyText2.copyWith(
                  color: AppColors.textSecondary,
                  height: 1.4,
                ),
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
              ),
            ),

            // Action buttons
            if (insight.actionOptions.isNotEmpty && onAction != null) ...[
              const Divider(height: 1, color: AppColors.divider),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: insight.actionOptions
                      .where((action) => action != 'ignore')
                      .take(3)
                      .map((action) => _buildActionButton(action))
                      .toList(),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildActionButton(String action) {
    final label = _getActionLabel(action);
    final icon = _getActionIcon(action);

    return Padding(
      padding: const EdgeInsets.only(left: 8),
      child: TextButton.icon(
        onPressed: () => onAction?.call(action),
        icon: Icon(icon, size: 16),
        label: Text(label),
        style: TextButton.styleFrom(
          foregroundColor: AppColors.primary,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          textStyle: AppTextStyles.caption.copyWith(
            fontWeight: FontWeight.w600,
          ),
          minimumSize: Size.zero,
          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
        ),
      ),
    );
  }

  Color _getTypeColor() {
    switch (insight.insightType) {
      case 'reminder':
        return AppColors.warning;
      case 'suggestion':
        return AppColors.success;
      case 'observation':
        return AppColors.info;
      case 'correlation':
        return AppColors.accent1;
      case 'followup':
        return AppColors.primary;
      default:
        return AppColors.textSecondary;
    }
  }

  String _getActionLabel(String action) {
    switch (action) {
      case 'send_message':
        return '发消息';
      case 'schedule_meeting':
        return '约见面';
      case 'set_reminder':
        return '设提醒';
      case 'view_details':
        return '查看详情';
      case 'complete_plan':
        return '已完成';
      case 'still_planning':
        return '还在计划';
      case 'cancel_plan':
        return '取消计划';
      default:
        return action;
    }
  }

  IconData _getActionIcon(String action) {
    switch (action) {
      case 'send_message':
        return Icons.message_outlined;
      case 'schedule_meeting':
        return Icons.calendar_today_outlined;
      case 'set_reminder':
        return Icons.alarm_outlined;
      case 'view_details':
        return Icons.visibility_outlined;
      case 'complete_plan':
        return Icons.check_circle_outline;
      case 'still_planning':
        return Icons.pending_outlined;
      case 'cancel_plan':
        return Icons.cancel_outlined;
      default:
        return Icons.arrow_forward;
    }
  }
}

/// Compact insight card for lists
class InsightListTile extends StatelessWidget {
  final InsightModel insight;
  final VoidCallback? onTap;

  const InsightListTile({
    super.key,
    required this.insight,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      onTap: onTap,
      leading: Container(
        width: 40,
        height: 40,
        decoration: BoxDecoration(
          color: AppColors.primary.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Center(
          child: Text(insight.typeIcon, style: const TextStyle(fontSize: 18)),
        ),
      ),
      title: Text(
        insight.title,
        style: AppTextStyles.bodyText1,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
      subtitle: Text(
        insight.content,
        style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
      ),
      trailing: insight.isHighPriority
          ? Container(
              width: 8,
              height: 8,
              decoration: const BoxDecoration(
                color: AppColors.warning,
                shape: BoxShape.circle,
              ),
            )
          : null,
    );
  }
}
