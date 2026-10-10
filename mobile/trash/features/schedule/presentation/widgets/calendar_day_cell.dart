import 'package:flutter/material.dart';
import '../../domain/entities/unified_event.dart';
import 'calendar_event_dots.dart';

/// A single day cell in the calendar grid
class CalendarDayCell extends StatelessWidget {
  final DateTime date;
  final bool isCurrentMonth;
  final bool isToday;
  final bool isSelected;
  final Set<EventSource> eventSources;
  final VoidCallback? onTap;

  const CalendarDayCell({
    super.key,
    required this.date,
    required this.isCurrentMonth,
    required this.isToday,
    required this.isSelected,
    required this.eventSources,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    // Determine text color
    Color textColor;
    if (!isCurrentMonth) {
      textColor = colorScheme.onSurface.withValues(alpha: 0.3);
    } else if (isSelected) {
      textColor = colorScheme.onPrimary;
    } else if (isToday) {
      textColor = colorScheme.primary;
    } else {
      textColor = colorScheme.onSurface;
    }

    // Determine background decoration
    BoxDecoration? decoration;
    if (isSelected) {
      decoration = BoxDecoration(
        color: colorScheme.primary,
        shape: BoxShape.circle,
      );
    } else if (isToday) {
      decoration = BoxDecoration(
        border: Border.all(
          color: colorScheme.primary,
          width: 2,
        ),
        shape: BoxShape.circle,
      );
    }

    return InkWell(
      onTap: isCurrentMonth ? onTap : null,
      borderRadius: BorderRadius.circular(20),
      child: Container(
        padding: const EdgeInsets.all(2),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Day number with background
            Container(
              width: 32,
              height: 32,
              decoration: decoration,
              alignment: Alignment.center,
              child: Text(
                '${date.day}',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: textColor,
                  fontWeight: isToday || isSelected
                      ? FontWeight.bold
                      : FontWeight.normal,
                ),
              ),
            ),
            // Event dots
            const SizedBox(height: 2),
            SizedBox(
              height: 8,
              child: isCurrentMonth
                  ? CalendarEventDots(
                      eventSources: eventSources,
                      dotSize: 5,
                      spacing: 1,
                    )
                  : null,
            ),
          ],
        ),
      ),
    );
  }
}

/// Header showing weekday names
class CalendarWeekdayHeader extends StatelessWidget {
  final List<String> weekdays;

  const CalendarWeekdayHeader({
    super.key,
    this.weekdays = const ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Row(
      children: weekdays.map((day) {
        return Expanded(
          child: Center(
            child: Text(
              day,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        );
      }).toList(),
    );
  }
}
