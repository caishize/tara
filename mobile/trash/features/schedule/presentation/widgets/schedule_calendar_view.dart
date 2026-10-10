import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../domain/entities/unified_event.dart';
import '../bloc/schedule_bloc.dart';
import '../bloc/schedule_event.dart';
import '../bloc/schedule_state.dart';
import 'calendar_day_cell.dart';
import 'calendar_event_dots.dart';

/// Main calendar view widget for the schedule page
class ScheduleCalendarView extends StatefulWidget {
  const ScheduleCalendarView({super.key});

  @override
  State<ScheduleCalendarView> createState() => _ScheduleCalendarViewState();
}

class _ScheduleCalendarViewState extends State<ScheduleCalendarView> {
  late PageController _pageController;
  static const int _initialPage = 1200; // ~100 years of months

  @override
  void initState() {
    super.initState();
    _pageController = PageController(initialPage: _initialPage);
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  DateTime _getMonthFromPage(int page, DateTime baseMonth) {
    final diff = page - _initialPage;
    return DateTime(baseMonth.year, baseMonth.month + diff);
  }

  int _getPageFromMonth(DateTime month, DateTime baseMonth) {
    final yearDiff = month.year - baseMonth.year;
    final monthDiff = month.month - baseMonth.month;
    return _initialPage + (yearDiff * 12) + monthDiff;
  }

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<ScheduleBloc, ScheduleState>(
      builder: (context, state) {
        if (state is! ScheduleLoaded) {
          return const Center(child: CircularProgressIndicator());
        }

        final now = DateTime.now();
        final baseMonth = DateTime(now.year, now.month);

        return Column(
          children: [
            // Month header with navigation
            _MonthHeader(
              currentMonth: state.currentMonth,
              onPreviousMonth: () => _navigateMonth(-1, state, baseMonth),
              onNextMonth: () => _navigateMonth(1, state, baseMonth),
              onTodayPressed: () => _goToToday(baseMonth),
            ),

            const SizedBox(height: 8),

            // Weekday header
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 16),
              child: CalendarWeekdayHeader(),
            ),

            const SizedBox(height: 8),

            // Calendar grid with swipe support
            SizedBox(
              height: 320, // 6 rows * ~50 pixels + padding
              child: PageView.builder(
                controller: _pageController,
                onPageChanged: (page) {
                  final newMonth = _getMonthFromPage(page, baseMonth);
                  context.read<ScheduleBloc>().add(ScheduleMonthChanged(newMonth));
                },
                itemBuilder: (context, page) {
                  final month = _getMonthFromPage(page, baseMonth);
                  return _CalendarGrid(
                    month: month,
                    selectedDate: state.selectedDate,
                    events: state.events,
                    onDateSelected: (date) {
                      context.read<ScheduleBloc>().add(ScheduleDateSelected(date));
                    },
                  );
                },
              ),
            ),

            const SizedBox(height: 8),

            // Event legend
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 16),
              child: CalendarEventLegend(),
            ),

            const Divider(height: 24),

            // Selected date events
            Expanded(
              child: _SelectedDateEvents(
                selectedDate: state.selectedDate,
                events: state.selectedDateEvents ?? const [],
              ),
            ),
          ],
        );
      },
    );
  }

  void _navigateMonth(int delta, ScheduleLoaded state, DateTime baseMonth) {
    final newMonth = DateTime(
      state.currentMonth.year,
      state.currentMonth.month + delta,
    );
    final newPage = _getPageFromMonth(newMonth, baseMonth);
    _pageController.animateToPage(
      newPage,
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeInOut,
    );
  }

  void _goToToday(DateTime baseMonth) {
    final now = DateTime.now();
    final todayMonth = DateTime(now.year, now.month);
    final page = _getPageFromMonth(todayMonth, baseMonth);
    _pageController.animateToPage(
      page,
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeInOut,
    );
    context.read<ScheduleBloc>().add(ScheduleDateSelected(now));
  }
}

/// Month header with navigation buttons
class _MonthHeader extends StatelessWidget {
  final DateTime currentMonth;
  final VoidCallback onPreviousMonth;
  final VoidCallback onNextMonth;
  final VoidCallback onTodayPressed;

  const _MonthHeader({
    required this.currentMonth,
    required this.onPreviousMonth,
    required this.onNextMonth,
    required this.onTodayPressed,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    // Format month display
    final monthNames = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ];
    final monthDisplay = '${monthNames[currentMonth.month - 1]} ${currentMonth.year}';

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          // Previous month button
          IconButton(
            icon: const Icon(Icons.chevron_left),
            onPressed: onPreviousMonth,
            tooltip: 'Previous month',
          ),

          // Month and year display
          Expanded(
            child: Text(
              monthDisplay,
              textAlign: TextAlign.center,
              style: theme.textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
          ),

          // Today button
          TextButton(
            onPressed: onTodayPressed,
            child: const Text('Today'),
          ),

          // Next month button
          IconButton(
            icon: const Icon(Icons.chevron_right),
            onPressed: onNextMonth,
            tooltip: 'Next month',
          ),
        ],
      ),
    );
  }
}

/// Calendar grid showing days of the month
class _CalendarGrid extends StatelessWidget {
  final DateTime month;
  final DateTime? selectedDate;
  final List<UnifiedEvent> events;
  final ValueChanged<DateTime> onDateSelected;

  const _CalendarGrid({
    required this.month,
    required this.selectedDate,
    required this.events,
    required this.onDateSelected,
  });

  @override
  Widget build(BuildContext context) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);

    // Calculate first day of month and days to show
    final firstOfMonth = DateTime(month.year, month.month, 1);

    // Start from Sunday of the week containing the first day
    final startDate = firstOfMonth.subtract(
      Duration(days: firstOfMonth.weekday % 7),
    );

    // Generate 6 weeks (42 days) of cells
    final days = List.generate(42, (index) {
      return startDate.add(Duration(days: index));
    });

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: GridView.builder(
        physics: const NeverScrollableScrollPhysics(),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 7,
          childAspectRatio: 1.0,
        ),
        itemCount: 42,
        itemBuilder: (context, index) {
          final date = days[index];
          final isCurrentMonth = date.month == month.month;
          final isToday = DateTime(date.year, date.month, date.day) == today;
          final isSelected = selectedDate != null &&
              DateTime(date.year, date.month, date.day) ==
                  DateTime(selectedDate!.year, selectedDate!.month, selectedDate!.day);

          // Get event sources for this date
          final eventSources = events
              .where((e) => e.occursOnDate(date))
              .map((e) => e.source)
              .toSet();

          return CalendarDayCell(
            date: date,
            isCurrentMonth: isCurrentMonth,
            isToday: isToday,
            isSelected: isSelected,
            eventSources: eventSources,
            onTap: () => onDateSelected(date),
          );
        },
      ),
    );
  }
}

/// Shows events for the selected date
class _SelectedDateEvents extends StatelessWidget {
  final DateTime? selectedDate;
  final List<UnifiedEvent> events;

  const _SelectedDateEvents({
    required this.selectedDate,
    required this.events,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    if (selectedDate == null) {
      return Center(
        child: Text(
          'Select a date to view events',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
      );
    }

    // Format date display
    final weekdays = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    final months = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ];
    final dateDisplay = '${weekdays[selectedDate!.weekday % 7]}, ${months[selectedDate!.month - 1]} ${selectedDate!.day}';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Text(
            dateDisplay,
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
        ),

        const SizedBox(height: 8),

        if (events.isEmpty)
          Expanded(
            child: Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    Icons.event_available,
                    size: 48,
                    color: theme.colorScheme.onSurfaceVariant.withValues(alpha: 0.5),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'No events on this day',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
          )
        else
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: events.length,
              itemBuilder: (context, index) {
                final event = events[index];
                return _EventCard(event: event);
              },
            ),
          ),
      ],
    );
  }
}

/// Card displaying a single event
class _EventCard extends StatelessWidget {
  final UnifiedEvent event;

  const _EventCard({required this.event});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: Container(
          width: 4,
          height: 40,
          decoration: BoxDecoration(
            color: event.color,
            borderRadius: BorderRadius.circular(2),
          ),
        ),
        title: Text(
          event.title,
          style: theme.textTheme.bodyLarge?.copyWith(
            fontWeight: FontWeight.w500,
          ),
        ),
        subtitle: event.description != null
            ? Text(
                event.description!,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              )
            : null,
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: event.color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            event.sourceName,
            style: theme.textTheme.labelSmall?.copyWith(
              color: event.color,
              fontWeight: FontWeight.w500,
            ),
          ),
        ),
      ),
    );
  }
}
