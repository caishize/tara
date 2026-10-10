import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';

/// Priority levels for snapshot items.
enum SnapshotPriority {
  urgent,   // Red - must handle today
  normal,   // Blue - today's items
  optional, // Gray - optional tasks
}

/// A snapshot item representing a task or event.
class SnapshotItem {
  final String id;
  final String title;
  final String subtitle;
  final String? icon;
  final SnapshotPriority priority;
  final SnapshotItemType type;
  final bool isCompleted;
  final String? actionLabel;
  final VoidCallback? onAction;
  final VoidCallback? onTap;

  const SnapshotItem({
    required this.id,
    required this.title,
    required this.subtitle,
    this.icon,
    this.priority = SnapshotPriority.normal,
    this.type = SnapshotItemType.task,
    this.isCompleted = false,
    this.actionLabel,
    this.onAction,
    this.onTap,
  });
}

/// Type of snapshot item for icon selection.
enum SnapshotItemType {
  meeting,
  gift,
  maintenance,
  birthday,
  travel,
  reminder,
  task,
}

/// Daily Snapshot section following demo design.
/// Shows today's key items with priority labels.
class DailySnapshotSection extends StatelessWidget {
  final List<SnapshotItem> items;
  final VoidCallback? onViewAll;
  final Function(String itemId, bool completed)? onItemToggle;

  const DailySnapshotSection({
    super.key,
    required this.items,
    this.onViewAll,
    this.onItemToggle,
  });

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return _buildEmptyState();
    }

    // Sort items by priority (urgent first)
    final sortedItems = List<SnapshotItem>.from(items)
      ..sort((a, b) => a.priority.index.compareTo(b.priority.index));

    // Check if there are urgent items
    final hasUrgent = sortedItems.any((item) => item.priority == SnapshotPriority.urgent);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Section header with priority badge
          Row(
            children: [
              Text(
                '今日快照',
                style: AppTextStyles.headline6.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(width: 8),
              if (hasUrgent)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: AppColors.warning,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    'PRIORITY',
                    style: AppTextStyles.overline.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                      fontSize: 10,
                      letterSpacing: 0.5,
                    ),
                  ),
                ),
              const Spacer(),
              if (onViewAll != null)
                GestureDetector(
                  onTap: onViewAll,
                  child: Text(
                    '查看全部',
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.primary,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 12),
          // Snapshot items container
          Container(
            decoration: BoxDecoration(
              color: const Color(0xFF1E2432), // Dark card background like demo
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(
              children: sortedItems.asMap().entries.map((entry) {
                final index = entry.key;
                final item = entry.value;
                final isLast = index == sortedItems.length - 1;
                return _buildSnapshotItem(item, isLast);
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSnapshotItem(SnapshotItem item, bool isLast) {
    return GestureDetector(
      onTap: item.onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          border: isLast
              ? null
              : Border(
                  bottom: BorderSide(
                    color: Colors.white.withValues(alpha: 0.1),
                    width: 1,
                  ),
                ),
        ),
        child: Row(
          children: [
            // Icon container
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: _getIconBackgroundColor(item.type, item.priority),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Center(
                child: item.icon != null
                    ? Text(item.icon!, style: const TextStyle(fontSize: 20))
                    : Icon(
                        _getItemIcon(item.type),
                        color: _getIconColor(item.type, item.priority),
                        size: 22,
                      ),
              ),
            ),
            const SizedBox(width: 12),
            // Content
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.title,
                    style: AppTextStyles.subtitle1.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    item.subtitle,
                    style: AppTextStyles.caption.copyWith(
                      color: item.priority == SnapshotPriority.urgent
                          ? AppColors.warning
                          : Colors.white.withValues(alpha: 0.6),
                      fontWeight: item.priority == SnapshotPriority.urgent
                          ? FontWeight.w500
                          : FontWeight.normal,
                    ),
                  ),
                ],
              ),
            ),
            // Trailing action
            _buildTrailingAction(item),
          ],
        ),
      ),
    );
  }

  Widget _buildTrailingAction(SnapshotItem item) {
    // If has action button
    if (item.actionLabel != null && item.onAction != null) {
      return GestureDetector(
        onTap: () {
          HapticFeedback.mediumImpact();
          item.onAction!();
        },
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            color: AppColors.primary,
            borderRadius: BorderRadius.circular(20),
          ),
          child: Text(
            item.actionLabel!,
            style: AppTextStyles.caption.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      );
    }

    // If can be toggled (checkbox)
    if (item.type == SnapshotItemType.maintenance ||
        item.type == SnapshotItemType.task) {
      return GestureDetector(
        onTap: () {
          HapticFeedback.lightImpact();
          onItemToggle?.call(item.id, !item.isCompleted);
        },
        child: Container(
          width: 24,
          height: 24,
          decoration: BoxDecoration(
            color: item.isCompleted ? AppColors.success : Colors.transparent,
            borderRadius: BorderRadius.circular(6),
            border: Border.all(
              color: item.isCompleted
                  ? AppColors.success
                  : Colors.white.withValues(alpha: 0.3),
              width: 2,
            ),
          ),
          child: item.isCompleted
              ? const Icon(
                  Icons.check,
                  color: Colors.white,
                  size: 16,
                )
              : null,
        ),
      );
    }

    // Default: arrow indicator
    return Icon(
      Icons.chevron_right,
      color: Colors.white.withValues(alpha: 0.5),
      size: 24,
    );
  }

  Color _getIconBackgroundColor(SnapshotItemType type, SnapshotPriority priority) {
    if (priority == SnapshotPriority.urgent) {
      return AppColors.warning.withValues(alpha: 0.2);
    }

    switch (type) {
      case SnapshotItemType.meeting:
        return const Color(0xFF3B82F6).withValues(alpha: 0.2);
      case SnapshotItemType.gift:
        return const Color(0xFF8B5CF6).withValues(alpha: 0.2);
      case SnapshotItemType.maintenance:
        return const Color(0xFF06B6D4).withValues(alpha: 0.2);
      case SnapshotItemType.birthday:
        return const Color(0xFFEC4899).withValues(alpha: 0.2);
      case SnapshotItemType.travel:
        return const Color(0xFF10B981).withValues(alpha: 0.2);
      case SnapshotItemType.reminder:
        return const Color(0xFFF59E0B).withValues(alpha: 0.2);
      case SnapshotItemType.task:
        return const Color(0xFF6B7280).withValues(alpha: 0.2);
    }
  }

  Color _getIconColor(SnapshotItemType type, SnapshotPriority priority) {
    if (priority == SnapshotPriority.urgent) {
      return AppColors.warning;
    }

    switch (type) {
      case SnapshotItemType.meeting:
        return const Color(0xFF3B82F6);
      case SnapshotItemType.gift:
        return const Color(0xFF8B5CF6);
      case SnapshotItemType.maintenance:
        return const Color(0xFF06B6D4);
      case SnapshotItemType.birthday:
        return const Color(0xFFEC4899);
      case SnapshotItemType.travel:
        return const Color(0xFF10B981);
      case SnapshotItemType.reminder:
        return const Color(0xFFF59E0B);
      case SnapshotItemType.task:
        return const Color(0xFF6B7280);
    }
  }

  IconData _getItemIcon(SnapshotItemType type) {
    switch (type) {
      case SnapshotItemType.meeting:
        return Icons.calendar_today;
      case SnapshotItemType.gift:
        return Icons.card_giftcard;
      case SnapshotItemType.maintenance:
        return Icons.water_drop;
      case SnapshotItemType.birthday:
        return Icons.cake;
      case SnapshotItemType.travel:
        return Icons.flight;
      case SnapshotItemType.reminder:
        return Icons.notifications;
      case SnapshotItemType.task:
        return Icons.check_circle_outline;
    }
  }

  Widget _buildEmptyState() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '今日快照',
            style: AppTextStyles.headline6.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: const Color(0xFF1E2432),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: AppColors.success.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Center(
                    child: Text('🌴', style: TextStyle(fontSize: 24)),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '今天没有待办事项',
                        style: AppTextStyles.subtitle1.copyWith(
                          color: Colors.white,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '享受轻松的一天吧 ✨',
                        style: AppTextStyles.caption.copyWith(
                          color: Colors.white.withValues(alpha: 0.6),
                        ),
                      ),
                    ],
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

/// Aggregated meeting item that groups multiple meetings.
class AggregatedMeetingItem extends SnapshotItem {
  final int meetingCount;
  final String? nextMeetingTime;
  final String? nextMeetingTitle;

  AggregatedMeetingItem({
    required super.id,
    required this.meetingCount,
    this.nextMeetingTime,
    this.nextMeetingTitle,
    super.onTap,
  }) : super(
          title: '$meetingCount 个会议',
          subtitle: nextMeetingTime != null && nextMeetingTitle != null
              ? '下一个: $nextMeetingTime - $nextMeetingTitle'
              : '点击查看详情',
          icon: '📅',
          type: SnapshotItemType.meeting,
          priority: SnapshotPriority.normal,
        );
}
