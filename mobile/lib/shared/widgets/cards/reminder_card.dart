import 'package:flutter/material.dart';

/// A card widget for displaying upcoming reminders.
///
/// Used in kanban columns and daily briefing to show
/// date-based reminders with countdown information.
class ReminderCard extends StatelessWidget {
  final String title;
  final String? subtitle;
  final DateTime? dueDate;
  final IconData icon;
  final Color? color;
  final bool isUrgent;
  final VoidCallback? onTap;
  final VoidCallback? onDismiss;

  const ReminderCard({
    super.key,
    required this.title,
    this.subtitle,
    this.dueDate,
    this.icon = Icons.notifications_outlined,
    this.color,
    this.isUrgent = false,
    this.onTap,
    this.onDismiss,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cardColor = color ?? (isUrgent ? theme.colorScheme.error : theme.colorScheme.primary);

    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: cardColor.withValues(alpha: 0.2),
        ),
      ),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: cardColor.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: cardColor, size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: theme.textTheme.titleSmall?.copyWith(
                        color: isUrgent ? cardColor : null,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (subtitle != null) ...[
                      const SizedBox(height: 2),
                      Text(
                        subtitle!,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                    if (dueDate != null) ...[
                      const SizedBox(height: 4),
                      _buildCountdown(context, cardColor),
                    ],
                  ],
                ),
              ),
              if (onDismiss != null)
                IconButton(
                  icon: Icon(
                    Icons.close,
                    size: 18,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                  onPressed: onDismiss,
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(
                    minWidth: 32,
                    minHeight: 32,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildCountdown(BuildContext context, Color cardColor) {
    final now = DateTime.now();
    final diff = dueDate!.difference(now);
    final String label;

    if (diff.isNegative) {
      label = '已过期';
    } else if (diff.inDays == 0) {
      label = '今天';
    } else if (diff.inDays == 1) {
      label = '明天';
    } else if (diff.inDays < 7) {
      label = '${diff.inDays}天后';
    } else {
      label = '${diff.inDays}天后';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: cardColor.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
          color: cardColor,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }
}
