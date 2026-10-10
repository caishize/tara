import 'package:flutter/material.dart';
import '../../data/models/memory_model.dart';

/// Compact horizontal strip showing urgent insight preview or briefing label.
///
/// Designed as a collapsed state for the daily briefing card. Supports
/// an external [pulse] trigger for drawing attention when new insights arrive.
class BriefingCompactStrip extends StatefulWidget {
  final List<InsightModel> urgentInsights;
  final VoidCallback onTap;
  final VoidCallback? onPulseComplete;

  const BriefingCompactStrip({
    super.key,
    required this.urgentInsights,
    required this.onTap,
    this.onPulseComplete,
  });

  @override
  State<BriefingCompactStrip> createState() => BriefingCompactStripState();
}

class BriefingCompactStripState extends State<BriefingCompactStrip>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;
  late Animation<double> _scaleAnimation;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    );
    _scaleAnimation = TweenSequence<double>([
      TweenSequenceItem(
        tween: Tween(begin: 1.0, end: 1.02),
        weight: 50,
      ),
      TweenSequenceItem(
        tween: Tween(begin: 1.02, end: 1.0),
        weight: 50,
      ),
    ]).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  /// Trigger a scale pulse animation. Can be called via GlobalKey:
  /// `(key.currentState as BriefingCompactStripState).pulse()`
  void pulse() {
    _pulseController.forward(from: 0).then((_) {
      widget.onPulseComplete?.call();
    });
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final hasUrgent = widget.urgentInsights.isNotEmpty;
    final title = hasUrgent
        ? _truncate(widget.urgentInsights.first.title, 30)
        : '📋 今日简报';

    return ScaleTransition(
      scale: _scaleAnimation,
      child: Material(
        color: scheme.surface,
        elevation: 2,
        borderRadius: BorderRadius.circular(8),
        child: InkWell(
          onTap: widget.onTap,
          borderRadius: BorderRadius.circular(8),
          child: Container(
            constraints: const BoxConstraints(minHeight: 44),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            child: Row(
              children: [
                if (hasUrgent)
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: Icon(
                      Icons.notifications_active_outlined,
                      size: 16,
                      color: scheme.error,
                    ),
                  ),
                Expanded(
                  child: Text(
                    title,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: scheme.onSurface,
                        ),
                    overflow: TextOverflow.ellipsis,
                    maxLines: 1,
                  ),
                ),
                const SizedBox(width: 4),
                Icon(
                  Icons.keyboard_arrow_down,
                  size: 20,
                  color: scheme.onSurfaceVariant,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  String _truncate(String text, int maxLen) {
    if (text.length <= maxLen) return text;
    return '${text.substring(0, maxLen)}...';
  }
}
