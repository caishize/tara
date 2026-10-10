import 'package:flutter/material.dart';
import '../../app/theme/app_colors.dart';

/// A timeline item card for displaying scheduled events (with time).
/// Matches the design: left accent bar | time column | divider | content
class TimelineItemCard extends StatelessWidget {
  final String title;
  final String? subtitle;
  final String? time;
  final String? amPm;
  final Widget? leading;
  final Widget? trailing;
  final Color? accentColor;
  final Color? backgroundColor;
  final VoidCallback? onTap;
  final VoidCallback? onDelete;
  final List<String>? tags;
  final String? eventId;

  const TimelineItemCard({
    super.key,
    required this.title,
    this.subtitle,
    this.time,
    this.amPm,
    this.leading,
    this.trailing,
    this.accentColor,
    this.backgroundColor,
    this.onTap,
    this.onDelete,
    this.tags,
    this.eventId,
  });

  @override
  Widget build(BuildContext context) {
    final card = GestureDetector(
      onTap: onTap,
      onLongPress: onDelete != null ? () => _showContextMenu(context) : null,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        decoration: BoxDecoration(
          color: backgroundColor ?? AppColors.cardBackground,
          borderRadius: BorderRadius.circular(12),
          boxShadow: AppColors.cardShadow,
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: Row(
            children: [
              // Left accent bar
              Container(
                width: 4,
                height: 80,
                color: accentColor ?? AppColors.warning,
              ),
              // Content
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: [
                      // Time column
                      if (time != null)
                        SizedBox(
                          width: 50,
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Text(
                                time!,
                                style: const TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.w700,
                                  color: AppColors.textPrimary,
                                ),
                              ),
                              if (amPm != null)
                                Text(
                                  amPm!,
                                  style: const TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w500,
                                    color: AppColors.textSecondary,
                                  ),
                                ),
                            ],
                          ),
                        ),
                      // Divider
                      if (time != null)
                        Container(
                          width: 1,
                          height: 40,
                          margin: const EdgeInsets.symmetric(horizontal: 12),
                          color: AppColors.divider,
                        ),
                      // Title and subtitle
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text(
                              title,
                              style: const TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w600,
                                color: AppColors.textPrimary,
                              ),
                            ),
                            if (subtitle != null) ...[
                              const SizedBox(height: 4),
                              Text(
                                subtitle!,
                                style: const TextStyle(
                                  fontSize: 13,
                                  color: AppColors.textSecondary,
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
                      // More button if delete is available
                      if (onDelete != null)
                        IconButton(
                          icon: const Icon(
                            Icons.more_vert,
                            color: AppColors.textTertiary,
                            size: 20,
                          ),
                          onPressed: () => _showContextMenu(context),
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints(),
                        )
                      else if (trailing != null)
                        trailing!,
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );

    if (onDelete == null) return card;

    // Capture ScaffoldMessenger before async operations to avoid "deactivated widget" error
    final scaffoldMessenger = ScaffoldMessenger.of(context);

    return Dismissible(
      key: Key('timeline_item_${eventId ?? title}'),
      direction: DismissDirection.endToStart,
      background: Container(
        margin: const EdgeInsets.only(bottom: 12),
        decoration: BoxDecoration(
          color: Colors.red.shade400,
          borderRadius: BorderRadius.circular(12),
        ),
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 20),
        child: const Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.delete_outline, color: Colors.white, size: 24),
            SizedBox(height: 4),
            Text(
              '取消',
              style: TextStyle(
                color: Colors.white,
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
      confirmDismiss: (direction) => _showCancelConfirmDialog(context),
      onDismissed: (_) {
        onDelete?.call();
        // Use captured scaffoldMessenger to avoid context issues
        scaffoldMessenger.showSnackBar(
          SnackBar(
            content: Row(
              children: [
                const Icon(Icons.check_circle, color: Colors.white, size: 20),
                const SizedBox(width: 12),
                Expanded(
                  child: Text('已取消「$title」'),
                ),
              ],
            ),
            backgroundColor: AppColors.success,
            behavior: SnackBarBehavior.floating,
            duration: const Duration(seconds: 3),
          ),
        );
      },
      child: card,
    );
  }

  void _showCancelSuccessSnackBar(BuildContext context) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.check_circle, color: Colors.white, size: 20),
            const SizedBox(width: 12),
            Expanded(
              child: Text('已取消「$title」'),
            ),
          ],
        ),
        backgroundColor: AppColors.success,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 3),
      ),
    );
  }

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
                title,
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
                  _showCancelSuccessSnackBar(context);
                }
              },
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  Future<bool?> _showCancelConfirmDialog(BuildContext context) {
    return showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('确认取消'),
        content: Text('确定要取消「$title」吗？\n\n取消后秘书会自动重新整理您的日程安排。'),
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
}

/// A date separator for timeline grouping.
/// Design: [Tag Badge] Date Weekday
class TimelineDateHeader extends StatelessWidget {
  final String date;
  final String? weekday;
  final String? tagLabel;
  final bool isToday;

  const TimelineDateHeader({
    super.key,
    required this.date,
    this.weekday,
    this.tagLabel,
    this.isToday = false,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 20, bottom: 12),
      child: Row(
        children: [
          // Tag badge (今天/明天/下周一 etc.)
          if (tagLabel != null)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              margin: const EdgeInsets.only(right: 12),
              decoration: BoxDecoration(
                color: isToday ? AppColors.primary : AppColors.chipBackground,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                tagLabel!,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: isToday ? Colors.white : AppColors.textSecondary,
                ),
              ),
            ),
          // Date and weekday
          Text(
            date,
            style: const TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
            ),
          ),
          if (weekday != null) ...[
            const SizedBox(width: 8),
            Text(
              weekday!,
              style: const TextStyle(
                fontSize: 14,
                color: AppColors.textSecondary,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// A reminder/event card for special events (birthdays, trips).
/// Design: Icon box | Title + green subtitle
class TimelineReminderCard extends StatelessWidget {
  final String title;
  final String subtitle;
  final String? countdown;
  final Color? accentColor;
  final IconData? icon;
  final VoidCallback? onTap;
  final VoidCallback? onDelete;
  final String? eventId;

  const TimelineReminderCard({
    super.key,
    required this.title,
    required this.subtitle,
    this.countdown,
    this.accentColor,
    this.icon,
    this.onTap,
    this.onDelete,
    this.eventId,
  });

  @override
  Widget build(BuildContext context) {
    final color = accentColor ?? AppColors.primary;

    final card = GestureDetector(
      onTap: onTap,
      onLongPress: onDelete != null ? () => _showContextMenu(context, color) : null,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.cardBackground,
          borderRadius: BorderRadius.circular(12),
          boxShadow: AppColors.cardShadow,
        ),
        child: Row(
          children: [
            // Icon box
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(
                icon ?? Icons.card_giftcard,
                color: color,
                size: 22,
              ),
            ),
            const SizedBox(width: 14),
            // Title and subtitle
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    subtitle,
                    style: TextStyle(
                      fontSize: 13,
                      color: color,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ),
            // More button if delete is available
            if (onDelete != null)
              IconButton(
                icon: const Icon(
                  Icons.more_vert,
                  color: AppColors.textTertiary,
                  size: 20,
                ),
                onPressed: () => _showContextMenu(context, color),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
              ),
          ],
        ),
      ),
    );

    if (onDelete == null) return card;

    // Capture ScaffoldMessenger before async operations to avoid "deactivated widget" error
    final scaffoldMessenger = ScaffoldMessenger.of(context);

    return Dismissible(
      key: Key('timeline_reminder_${eventId ?? title}'),
      direction: DismissDirection.endToStart,
      background: Container(
        margin: const EdgeInsets.only(bottom: 12),
        decoration: BoxDecoration(
          color: Colors.red.shade400,
          borderRadius: BorderRadius.circular(12),
        ),
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 20),
        child: const Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.delete_outline, color: Colors.white, size: 24),
            SizedBox(height: 4),
            Text(
              '取消',
              style: TextStyle(
                color: Colors.white,
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
      confirmDismiss: (direction) => _showCancelConfirmDialog(context),
      onDismissed: (_) {
        onDelete?.call();
        // Use captured scaffoldMessenger to avoid context issues
        scaffoldMessenger.showSnackBar(
          SnackBar(
            content: Row(
              children: [
                const Icon(Icons.check_circle, color: Colors.white, size: 20),
                const SizedBox(width: 12),
                Expanded(
                  child: Text('已取消「$title」'),
                ),
              ],
            ),
            backgroundColor: AppColors.success,
            behavior: SnackBarBehavior.floating,
            duration: const Duration(seconds: 3),
          ),
        );
      },
      child: card,
    );
  }

  void _showCancelSuccessSnackBar(BuildContext context) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.check_circle, color: Colors.white, size: 20),
            const SizedBox(width: 12),
            Expanded(
              child: Text('已取消「$title」'),
            ),
          ],
        ),
        backgroundColor: AppColors.success,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 3),
      ),
    );
  }

  void _showContextMenu(BuildContext context, Color color) {
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
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(icon ?? Icons.card_giftcard, color: color, size: 20),
                  const SizedBox(width: 8),
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textPrimary,
                    ),
                  ),
                ],
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
                  _showCancelSuccessSnackBar(context);
                }
              },
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  Future<bool?> _showCancelConfirmDialog(BuildContext context) {
    return showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('确认取消'),
        content: Text('确定要取消「$title」吗？\n\n取消后秘书会自动重新整理您的日程安排。'),
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
}
