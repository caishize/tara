import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../../../app/theme/app_colors.dart';
import '../../domain/entities/curated_event.dart';

/// 整理后事件卡片
class CuratedEventCard extends StatelessWidget {
  final CuratedEvent event;
  final bool isExpanded;
  final VoidCallback? onTap;
  final VoidCallback? onToggleExpand;
  final VoidCallback? onDelete;

  const CuratedEventCard({
    super.key,
    required this.event,
    this.isExpanded = false,
    this.onTap,
    this.onToggleExpand,
    this.onDelete,
  });

  /// Whether this event is a trip-level card (multi-day business_trip/travel)
  bool get _isTripHeader =>
      event.isMultiDay &&
      (event.eventType == CuratedEventType.businessTrip ||
          event.eventType == CuratedEventType.travel);

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final card = Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      decoration: BoxDecoration(
        color: colorScheme.surface,
        borderRadius: BorderRadius.circular(16),
        boxShadow: AppColors.cardShadow,
        // Conflict highlighting: red border
        border: event.hasConflict
            ? Border.all(color: AppColors.error, width: 2)
            : null,
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap ?? onToggleExpand,
          onLongPress: onDelete != null ? () => _showContextMenu(context) : null,
          borderRadius: BorderRadius.circular(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Conflict warning banner
              if (event.hasConflict) _buildConflictBanner(),
              if (_isTripHeader) _buildTripHeader(context) else _buildHeader(context),
              if (isExpanded && event.timelineItems.isNotEmpty)
                _buildTimelineItems(),
              if (event.hasUnconfirmedItems) _buildUnconfirmedBadge(),
            ],
          ),
        ),
      ),
    );

    return card;
  }

  /// Build conflict warning banner
  Widget _buildConflictBanner() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.red.shade50,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(14)),
      ),
      child: Row(
        children: [
          Icon(Icons.warning_amber_rounded, size: 16, color: Colors.red.shade700),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '⚠️ 时间冲突：与其他 ${event.conflictWith.length} 项日程重叠',
              style: TextStyle(
                fontSize: 12,
                color: Colors.red.shade700,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }


  /// Show context menu on long press
  void _showContextMenu(BuildContext context) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 40,
              height: 4,
              margin: const EdgeInsets.symmetric(vertical: 12),
              decoration: BoxDecoration(
                color: AppColors.divider,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
              child: Text(
                event.title,
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
                textAlign: TextAlign.center,
              ),
            ),
            const Divider(),
            ListTile(
              leading: const Icon(Icons.cancel_outlined, color: Colors.red),
              title: const Text('取消此日程', style: TextStyle(color: Colors.red)),
              subtitle: const Text('取消后秘书会重新整理安排'),
              onTap: () async {
                Navigator.pop(context);
                final confirmed = await _showCancelConfirmDialog(context);
                if (confirmed == true) {
                  onDelete?.call();
                }
              },
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  /// Show cancel confirmation dialog
  Future<bool?> _showCancelConfirmDialog(BuildContext context) {
    return showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('确认取消'),
        content: Text('确定要取消「${event.title}」吗？\n\n取消后秘书会自动重新整理您的日程安排。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('返回'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('确认取消'),
          ),
        ],
      ),
    );
  }

  /// Trip-level header: gradient banner with destination, date span, and icon
  Widget _buildTripHeader(BuildContext context) {
    final dateFormat = DateFormat('M/d');
    final localStart = event.startTime.toLocal();
    final localEnd = event.endTime?.toLocal();
    final dateSpan = localEnd != null
        ? '${dateFormat.format(localStart)}-${dateFormat.format(localEnd)}'
        : dateFormat.format(localStart);

    final isBusiness = event.eventType == CuratedEventType.businessTrip;
    final gradientColors = isBusiness
        ? [AppColors.accentBlue, AppColors.accentBlue.withAlpha(200)]
        : [const Color(0xFF26A69A), const Color(0xFF00897B)];

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: gradientColors,
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
      ),
      child: Row(
        children: [
          // Trip icon
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: Colors.white.withAlpha(50),
              borderRadius: BorderRadius.circular(12),
            ),
            alignment: Alignment.center,
            child: Icon(
              isBusiness ? Icons.business_center : Icons.flight_takeoff,
              color: Colors.white,
              size: 22,
            ),
          ),
          const SizedBox(width: 12),
          // Title + date span + destination
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  event.title,
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    const Icon(Icons.calendar_today, size: 12, color: Colors.white70),
                    const SizedBox(width: 4),
                    Text(
                      '$dateSpan (${event.durationDays}天)',
                      style: const TextStyle(fontSize: 13, color: Colors.white70),
                    ),
                    if (event.location != null) ...[
                      const SizedBox(width: 12),
                      const Icon(Icons.location_on_outlined, size: 12, color: Colors.white70),
                      const SizedBox(width: 2),
                      Flexible(
                        child: Text(
                          event.location!,
                          style: const TextStyle(fontSize: 13, color: Colors.white70),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),
          // Expand/collapse or more button
          if (onDelete != null)
            IconButton(
              icon: const Icon(Icons.more_vert, color: Colors.white70, size: 20),
              onPressed: () => _showContextMenu(context),
              tooltip: '更多操作',
            )
          else if (event.timelineItems.isNotEmpty)
            IconButton(
              icon: Icon(
                isExpanded ? Icons.keyboard_arrow_up : Icons.keyboard_arrow_down,
                color: Colors.white70,
              ),
              onPressed: onToggleExpand,
            ),
        ],
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          // 事件类型图标
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: _getEventTypeColor().withAlpha((0.1 * 255).round()),
              borderRadius: BorderRadius.circular(12),
            ),
            alignment: Alignment.center,
            child: Text(
              event.eventType?.icon ?? '📅',
              style: const TextStyle(fontSize: 20),
            ),
          ),
          const SizedBox(width: 12),
          // 标题和时间
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        event.title,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: AppColors.textPrimary,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    if (event.mergedCount > 1)
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 2,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.primary.withAlpha((0.1 * 255).round()),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Text(
                          '合并${event.mergedCount}项',
                          style: TextStyle(
                            fontSize: 10,
                            color: AppColors.primary,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                  ],
                ),
                if (event.belongsToTrip)
                  Container(
                    margin: const EdgeInsets.only(top: 4),
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: AppColors.accentBlue.withAlpha(20),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.luggage_outlined, size: 12, color: AppColors.accentBlue),
                        const SizedBox(width: 4),
                        Text(
                          event.tripDayLabel ?? event.tripName ?? '',
                          style: const TextStyle(fontSize: 10, color: AppColors.accentBlue),
                        ),
                      ],
                    ),
                  ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Text(
                      _formatEventTime(),
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppColors.textSecondary,
                      ),
                    ),
                    if (event.location != null) ...[
                      const SizedBox(width: 8),
                      const Icon(
                        Icons.location_on_outlined,
                        size: 14,
                        color: AppColors.textTertiary,
                      ),
                      const SizedBox(width: 2),
                      Text(
                        event.location!,
                        style: const TextStyle(
                          fontSize: 13,
                          color: AppColors.textSecondary,
                        ),
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),
          // 更多操作按钮
          if (onDelete != null)
            IconButton(
              icon: const Icon(
                Icons.more_vert,
                color: AppColors.textTertiary,
                size: 20,
              ),
              onPressed: () => _showContextMenu(context),
              tooltip: '更多操作',
            )
          // 展开/收起按钮
          else if (event.timelineItems.isNotEmpty)
            IconButton(
              icon: Icon(
                isExpanded
                    ? Icons.keyboard_arrow_up
                    : Icons.keyboard_arrow_down,
                color: AppColors.textSecondary,
              ),
              onPressed: onToggleExpand,
            ),
        ],
      ),
    );
  }

  Widget _buildTimelineItems() {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: event.timelineItems.asMap().entries.map((entry) {
          final index = entry.key;
          final item = entry.value;
          final isLast = index == event.timelineItems.length - 1;

          return _buildTimelineItem(item, isLast);
        }).toList(),
      ),
    );
  }

  Widget _buildTimelineItem(TimelineItem item, bool isLast) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // 时间线
        Column(
          children: [
            Container(
              width: 10,
              height: 10,
              decoration: BoxDecoration(
                color: item.confirmed ? AppColors.primary : AppColors.warning,
                shape: BoxShape.circle,
              ),
            ),
            if (!isLast)
              Container(
                width: 2,
                height: 40,
                color: AppColors.divider,
              ),
          ],
        ),
        const SizedBox(width: 12),
        // 内容
        Expanded(
          child: Padding(
            padding: EdgeInsets.only(bottom: isLast ? 0 : 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      _formatItemTime(item.time),
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppColors.textTertiary,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    if (!item.confirmed) ...[
                      const SizedBox(width: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 6,
                          vertical: 1,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.warning.withAlpha((0.1 * 255).round()),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text(
                          '待确认',
                          style: TextStyle(
                            fontSize: 10,
                            color: AppColors.warning,
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  item.item,
                  style: TextStyle(
                    fontSize: 14,
                    color: item.confirmed
                        ? AppColors.textPrimary
                        : AppColors.textSecondary,
                  ),
                ),
                if (item.note != null) ...[
                  const SizedBox(height: 2),
                  Text(
                    item.note!,
                    style: const TextStyle(
                      fontSize: 12,
                      color: AppColors.textTertiary,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildUnconfirmedBadge() {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.warning.withAlpha((0.1 * 255).round()),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.warning.withAlpha((0.3 * 255).round())),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.info_outline,
            size: 16,
            color: AppColors.warning,
          ),
          const SizedBox(width: 8),
          Text(
            '有 ${event.unconfirmedCount} 项待确认',
            style: const TextStyle(
              fontSize: 13,
              color: AppColors.warning,
            ),
          ),
          const Spacer(),
          const Text(
            '点击确认',
            style: TextStyle(
              fontSize: 12,
              color: AppColors.warning,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  String _formatEventTime() {
    final dateFormat = DateFormat('M月d日');
    final timeFormat = DateFormat('HH:mm');

    // Convert to local time for display
    final localStart = event.startTime.toLocal();
    final localEnd = event.endTime?.toLocal();

    if (event.isMultiDay) {
      final startStr = dateFormat.format(localStart);
      final endStr = localEnd != null ? dateFormat.format(localEnd) : '';
      return '$startStr - $endStr (${event.durationDays}天)';
    } else {
      final dateStr = dateFormat.format(localStart);
      final timeStr = timeFormat.format(localStart);
      return '$dateStr $timeStr';
    }
  }

  String _formatItemTime(String time) {
    try {
      final dt = DateTime.parse(time).toLocal();
      return DateFormat('HH:mm').format(dt);
    } on FormatException {
      // Invalid time format, return original string as fallback
      return time;
    }
  }

  Color _getEventTypeColor() {
    final type = event.eventType;
    if (type == null) return AppColors.textSecondary;
    return Color(type.colorValue);
  }
}
