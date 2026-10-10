import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../../../app/theme/app_colors.dart';
import '../../data/models/kanban_models.dart';

/// Compact full-width event row for standalone events not linked to any insight.
/// Height: ~60-72px. Layout: [emoji | Column[title, subtitle] | countdown badge].
class EventMiniCard extends StatelessWidget {
  final KanbanEventModel event;
  final VoidCallback? onTap;

  const EventMiniCard({super.key, required this.event, this.onTap});

  static const _kCountdownLabels = [
    '\u4ECA\u5929', // 今天 (0)
    '\u660E\u5929', // 明天 (1)
    '\u540E\u5929', // 后天 (2)
  ];

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final ext = Theme.of(context).extension<AppColorsExtension>();

    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          color: colorScheme.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: colorScheme.outlineVariant, width: 1),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.03),
              blurRadius: 6,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Row(
          children: [
            _buildIcon(context),
            const SizedBox(width: 12),
            Expanded(child: _buildInfo(context)),
            if (_buildCountdownBadge() case final badge?) ...[
              const SizedBox(width: 8),
              badge,
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildIcon(BuildContext context) {
    final emoji = event.eventType?.icon ?? '';
    if (emoji.isNotEmpty) return Text(emoji, style: const TextStyle(fontSize: 22));
    final ext = Theme.of(context).extension<AppColorsExtension>();
    return Icon(Icons.calendar_today_outlined, size: 22,
        color: ext?.textTertiary ?? AppColors.textTertiary);
  }

  Widget _buildInfo(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          event.title,
          style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: colorScheme.onSurface),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        const SizedBox(height: 2),
        Text(
          _subtitle,
          style: TextStyle(fontSize: 12, fontWeight: FontWeight.w400, color: colorScheme.onSurfaceVariant),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ],
    );
  }

  String get _subtitle {
    final parts = <String>[];
    if (event.startTime != null) {
      parts.add(DateFormat('M\u6708d\u65E5 EEEE', 'zh_CN').format(event.startTime!.toLocal()));
    }
    if (event.location != null && event.location!.isNotEmpty) parts.add(event.location!);
    return parts.join(' \u00B7 ');
  }

  Widget? _buildCountdownBadge() {
    if (event.startTime == null) return null;
    final eventDate = DateUtils.dateOnly(event.startTime!.toLocal());
    final daysUntil = eventDate.difference(DateUtils.dateOnly(DateTime.now())).inDays;
    if (daysUntil < 0 || daysUntil > 7) return null;
    final label = daysUntil < _kCountdownLabels.length
        ? _kCountdownLabels[daysUntil]
        : '$daysUntil\u5929\u540E'; // N天后
    final isImminent = daysUntil <= 1;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: isImminent ? AppColors.accentWarmLight : AppColors.accentGreenLight,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: isImminent ? AppColors.accentWarm : AppColors.accentGreen,
        ),
      ),
    );
  }
}
