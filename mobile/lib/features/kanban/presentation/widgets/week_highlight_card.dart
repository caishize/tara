import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_dimensions.dart';
import '../../../../shared/widgets/countdown_badge.dart';
import '../../../../shared/widgets/progress_ring.dart';
import '../../data/models/kanban_models.dart';

/// Horizontal scrolling card for "this week" highlight events.
/// 3-zone layout: gradient header, content body, bottom bar.
class WeekHighlightCard extends StatefulWidget {
  final KanbanEventModel event;
  final VoidCallback? onTap;

  const WeekHighlightCard({
    super.key,
    required this.event,
    this.onTap,
  });

  @override
  State<WeekHighlightCard> createState() => _WeekHighlightCardState();
}

class _WeekHighlightCardState extends State<WeekHighlightCard> {
  double _scale = 1.0;

  @override
  Widget build(BuildContext context) {
    final typeColor = Color(widget.event.eventType?.colorValue ?? 0xFF78909C);

    final colorScheme = Theme.of(context).colorScheme;

    return GestureDetector(
      onTapDown: (_) => setState(() => _scale = 0.97),
      onTapUp: (_) {
        setState(() => _scale = 1.0);
        widget.onTap?.call();
      },
      onTapCancel: () => setState(() => _scale = 1.0),
      child: AnimatedScale(
        scale: _scale,
        duration: const Duration(milliseconds: 120),
        child: Container(
          width: 200,
          margin: const EdgeInsets.only(right: 12),
          decoration: BoxDecoration(
            color: colorScheme.surface,
            borderRadius: BorderRadius.circular(AppDimensions.cardRadius),
            boxShadow: AppColors.cardShadowMedium,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Gradient header (52px)
              _buildGradientHeader(typeColor),
              // Content body
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(12, 10, 12, 0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Title
                      Text(
                        widget.event.title,
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                          color: colorScheme.onSurface,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 4),
                      // Weekday + date
                      if (widget.event.startTime != null)
                        Text(
                          _formatWeekdayDate(widget.event.startTime!),
                          style: TextStyle(
                            fontSize: 13,
                            color: colorScheme.onSurfaceVariant,
                          ),
                        ),
                      const SizedBox(height: 2),
                      // Location
                      if (widget.event.location != null)
                        Row(
                          children: [
                            Icon(
                              Icons.location_on_outlined,
                              size: 12,
                              color: colorScheme.onSurfaceVariant,
                            ),
                            const SizedBox(width: 3),
                            Expanded(
                              child: Text(
                                widget.event.location!,
                                style: TextStyle(
                                  fontSize: 12,
                                  color: colorScheme.onSurfaceVariant,
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                    ],
                  ),
                ),
              ),
              // Bottom bar
              _buildBottomBar(typeColor),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildGradientHeader(Color typeColor) {
    return Container(
      height: 52,
      width: double.infinity,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            typeColor,
            typeColor.withValues(alpha: 0.75),
          ],
        ),
        borderRadius: const BorderRadius.vertical(top: Radius.circular(AppDimensions.cardRadius)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      child: Row(
        children: [
          // Emoji in white circle
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.25),
              shape: BoxShape.circle,
            ),
            child: Center(
              child: Text(
                widget.event.eventType?.icon ?? '',
                style: const TextStyle(fontSize: 16),
              ),
            ),
          ),
          const Spacer(),
          // Countdown badge
          if (widget.event.startTime != null)
            CountdownBadge(targetDate: widget.event.startTime!),
        ],
      ),
    );
  }

  Widget _buildBottomBar(Color typeColor) {
    final hasPrepItems = widget.event.preparationItems.isNotEmpty;
    final isHighPriority = widget.event.priority == 'high';

    if (!hasPrepItems && !isHighPriority) {
      return const SizedBox(height: 10);
    }

    final colorScheme = Theme.of(context).colorScheme;

    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 4, 12, 10),
      child: Row(
        children: [
          if (hasPrepItems) ...[
            ProgressRing(
              progress: widget.event.prepTotalCount > 0
                  ? widget.event.prepDoneCount /
                      widget.event.prepTotalCount
                  : 0,
              size: 16,
              foregroundColor: widget.event.allPrepDone
                  ? AppColors.success
                  : typeColor,
            ),
            const SizedBox(width: 6),
            Text(
              widget.event.allPrepDone
                  ? '已准备'
                  : '${widget.event.prepDoneCount}/${widget.event.prepTotalCount}',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w500,
                color: widget.event.allPrepDone
                    ? AppColors.success
                    : colorScheme.onSurfaceVariant,
              ),
            ),
          ],
          const Spacer(),
          if (isHighPriority)
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                color: colorScheme.error,
                shape: BoxShape.circle,
              ),
            ),
        ],
      ),
    );
  }

  String _formatWeekdayDate(DateTime dt) {
    final local = dt.toLocal();
    return DateFormat('EEEE M月d日', 'zh_CN').format(local);
  }
}
