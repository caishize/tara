import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_dimensions.dart';
import '../../data/models/kanban_models.dart';

/// Timeline row for "稍后查看" section.
/// Left: colored dot + connecting line. Right: card with event-type accent,
/// date, info, and subtitle.
class TimelineEventRow extends StatelessWidget {
  final KanbanEventModel event;
  final bool isLast;
  final VoidCallback? onTap;

  const TimelineEventRow({
    super.key,
    required this.event,
    this.isLast = false,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final ext = Theme.of(context).extension<AppColorsExtension>();
    final colorScheme = Theme.of(context).colorScheme;
    final dotColor = _resolveDotColor(ext);
    final eventColor = _resolveEventTypeColor();

    return GestureDetector(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Left column: dot + line
              SizedBox(
                width: 44,
                child: Column(
                  children: [
                    const SizedBox(height: 14),
                    // Dot with outer glow
                    Container(
                      width: 14,
                      height: 14,
                      decoration: BoxDecoration(
                        color: dotColor,
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: dotColor.withValues(alpha: 0.25),
                          width: 3,
                        ),
                      ),
                    ),
                    // Connecting line
                    if (!isLast)
                      Expanded(
                        child: Container(
                          width: 2,
                          color: ext?.insightDefault.withValues(alpha: 0.15)
                              ?? const Color(0xFFD4E8DC),
                        ),
                      ),
                  ],
                ),
              ),
              // Right column: card with event-type accent
              Expanded(
                child: Container(
                  margin: const EdgeInsets.only(bottom: 10),
                  decoration: BoxDecoration(
                    color: colorScheme.surface,
                    borderRadius: BorderRadius.circular(AppDimensions.cardRadius),
                    border: Border.all(
                      color: colorScheme.outlineVariant,
                      width: 1,
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.03),
                        blurRadius: 6,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      // Left accent bar colored by event type
                      Container(
                        width: 4,
                        decoration: BoxDecoration(
                          color: eventColor,
                          borderRadius: const BorderRadius.only(
                            topLeft: Radius.circular(AppDimensions.cardRadius),
                            bottomLeft: Radius.circular(AppDimensions.cardRadius),
                          ),
                        ),
                      ),
                      // Card content
                      Expanded(
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              // Date row + type badge + priority
                              Row(
                                children: [
                                  if (event.startTime != null)
                                    Text(
                                      DateFormat('M月d日 EEEE', 'zh_CN')
                                          .format(event.startTime!.toLocal()),
                                      style: TextStyle(
                                        fontSize: 12,
                                        fontWeight: FontWeight.w600,
                                        color: colorScheme.onSurfaceVariant,
                                      ),
                                    ),
                                  const Spacer(),
                                  // Event type badge
                                  if (event.eventType != null)
                                    Container(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 6,
                                        vertical: 2,
                                      ),
                                      decoration: BoxDecoration(
                                        color: eventColor.withValues(alpha: 0.1),
                                        borderRadius: BorderRadius.circular(6),
                                      ),
                                      child: Text(
                                        event.eventType!.displayName,
                                        style: TextStyle(
                                          fontSize: 10,
                                          fontWeight: FontWeight.w600,
                                          color: eventColor,
                                        ),
                                      ),
                                    ),
                                  if (event.priority == 'high') ...[
                                    const SizedBox(width: 6),
                                    Container(
                                      width: 8,
                                      height: 8,
                                      decoration: const BoxDecoration(
                                        color: AppColors.error,
                                        shape: BoxShape.circle,
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                              const SizedBox(height: 6),
                              // Info row: icon + title + location
                              Row(
                                children: [
                                  Text(
                                    event.eventType?.icon ?? '',
                                    style: const TextStyle(fontSize: 18),
                                  ),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(
                                      event.title,
                                      style: TextStyle(
                                        fontSize: 15,
                                        fontWeight: FontWeight.w600,
                                        color: colorScheme.onSurface,
                                      ),
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                  if (event.location != null) ...[
                                    const SizedBox(width: 4),
                                    Icon(
                                      Icons.location_on_outlined,
                                      size: 13,
                                      color: ext?.textTertiary ?? AppColors.textTertiary,
                                    ),
                                    const SizedBox(width: 2),
                                    Flexible(
                                      child: Text(
                                        event.location!,
                                        style: TextStyle(
                                          fontSize: 11,
                                          color: ext?.textTertiary ?? AppColors.textTertiary,
                                        ),
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                              // Subtitle
                              if (event.notes != null &&
                                  event.notes!.isNotEmpty) ...[
                                const SizedBox(height: 4),
                                Text(
                                  event.notes!,
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: colorScheme.onSurfaceVariant,
                                    height: 1.4,
                                  ),
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ],
                              // Countdown badge for imminent events
                              if (_daysUntil != null && _daysUntil! <= 7) ...[
                                const SizedBox(height: 6),
                                _buildCountdownChip(),
                              ],
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  int? get _daysUntil {
    if (event.startTime == null) return null;
    final eventDate = DateUtils.dateOnly(event.startTime!.toLocal());
    return eventDate.difference(DateUtils.dateOnly(DateTime.now())).inDays;
  }

  Widget _buildCountdownChip() {
    final days = _daysUntil!;
    if (days < 0) return const SizedBox.shrink();
    final label = switch (days) {
      0 => '今天',
      1 => '明天',
      2 => '后天',
      _ => '$days天后',
    };
    final isImminent = days <= 2;
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
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
      ),
    );
  }

  Color _resolveDotColor(AppColorsExtension? ext) {
    // Focus events get warm accent to stand out
    if (event.isFocusEvent) return AppColors.accentWarm;
    if (event.priority == 'high') return AppColors.error;
    // Use event type color for the dot
    if (event.eventType != null) return _resolveEventTypeColor();
    if (event.startTime != null) {
      final now = DateTime.now();
      final diff = event.startTime!.difference(now).inDays;
      if (diff <= 7) return ext?.insightDefault ?? AppColors.accentGreen;
    }
    return ext?.textTertiary ?? const Color(0xFFB0B0AE);
  }

  Color _resolveEventTypeColor() {
    if (event.eventType == null) return AppColors.accentGreen;
    return Color(event.eventType!.colorValue);
  }
}
