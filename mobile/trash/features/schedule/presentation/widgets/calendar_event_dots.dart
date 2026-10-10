import 'package:flutter/material.dart';
import '../../domain/entities/unified_event.dart';

/// Displays small colored dots to indicate events on a calendar day
class CalendarEventDots extends StatelessWidget {
  final Set<EventSource> eventSources;
  final double dotSize;
  final double spacing;

  const CalendarEventDots({
    super.key,
    required this.eventSources,
    this.dotSize = 6.0,
    this.spacing = 2.0,
  });

  @override
  Widget build(BuildContext context) {
    if (eventSources.isEmpty) return const SizedBox.shrink();

    // Sort event sources for consistent display order
    final sortedSources = eventSources.toList()
      ..sort((a, b) => a.index.compareTo(b.index));

    // Limit to max 3 dots to avoid overflow
    final displaySources = sortedSources.take(3).toList();

    return Row(
      mainAxisSize: MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: displaySources.map((source) {
        return Container(
          width: dotSize,
          height: dotSize,
          margin: EdgeInsets.symmetric(horizontal: spacing / 2),
          decoration: BoxDecoration(
            color: source.color,
            shape: BoxShape.circle,
          ),
        );
      }).toList(),
    );
  }
}

/// A legend widget explaining the event dot colors
class CalendarEventLegend extends StatelessWidget {
  const CalendarEventLegend({super.key});

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 16,
      runSpacing: 8,
      alignment: WrapAlignment.center,
      children: EventSource.values.map((source) {
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                color: source.color,
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 4),
            Text(
              source.label,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        );
      }).toList(),
    );
  }
}
