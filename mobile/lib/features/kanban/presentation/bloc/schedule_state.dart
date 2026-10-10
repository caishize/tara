import 'package:equatable/equatable.dart';
import '../../domain/entities/unified_event.dart';

abstract class ScheduleState extends Equatable {
  const ScheduleState();

  @override
  List<Object?> get props => [];
}

class ScheduleInitial extends ScheduleState {
  const ScheduleInitial();
}

class ScheduleLoading extends ScheduleState {
  const ScheduleLoading();
}

class ScheduleLoaded extends ScheduleState {
  final List<UnifiedEvent> allEvents;
  final Map<TimePeriod, List<UnifiedEvent>> eventsByPeriod;
  final EventSource? currentFilter;
  final TimePeriod? timePeriodFilter;  // Filter by time period (e.g., "this week" from briefing)
  final DateTime? selectedDate;
  final List<UnifiedEvent>? selectedDateEvents;
  final DateTime currentMonth;
  // Pagination state for future events
  final bool hasMoreFutureEvents;
  final bool isLoadingMoreFuture;
  final DateTime? futureEventsEndDate;  // Current end date for future events query

  // Cached filtered results for performance
  late final List<UnifiedEvent> _cachedFilteredEvents;
  late final Map<TimePeriod, List<UnifiedEvent>> _cachedFilteredEventsByPeriod;

  ScheduleLoaded({
    required this.allEvents,
    required this.eventsByPeriod,
    this.currentFilter,
    this.timePeriodFilter,
    this.selectedDate,
    this.selectedDateEvents,
    DateTime? currentMonth,
    this.hasMoreFutureEvents = true,
    this.isLoadingMoreFuture = false,
    this.futureEventsEndDate,
  }) : currentMonth = currentMonth ?? DateTime.now() {
    // Pre-compute filtered results once
    _computeFilteredResults();
  }

  void _computeFilteredResults() {
    // Start with all events
    var filteredEvents = allEvents.toList();
    var filteredByPeriod = Map<TimePeriod, List<UnifiedEvent>>.from(eventsByPeriod);

    // Apply source filter if set
    if (currentFilter != null) {
      filteredEvents = filteredEvents.where((e) => e.source == currentFilter).toList();
      filteredByPeriod = {};
      for (final entry in eventsByPeriod.entries) {
        final filteredList = entry.value.where((e) => e.source == currentFilter).toList();
        if (filteredList.isNotEmpty) {
          filteredByPeriod[entry.key] = filteredList;
        }
      }
    }

    // Apply time period filter if set (for "this week" navigation)
    if (timePeriodFilter != null) {
      // For "thisWeek" filter, include today, tomorrow, and thisWeek periods
      final periodsToInclude = _getPeriodsForFilter(timePeriodFilter!);
      filteredEvents = filteredEvents.where((e) {
        final eventPeriod = _getEventPeriod(e);
        return eventPeriod != null && periodsToInclude.contains(eventPeriod);
      }).toList();

      final newFilteredByPeriod = <TimePeriod, List<UnifiedEvent>>{};
      for (final period in periodsToInclude) {
        if (filteredByPeriod.containsKey(period)) {
          newFilteredByPeriod[period] = filteredByPeriod[period]!;
        }
      }
      filteredByPeriod = newFilteredByPeriod;
    }

    _cachedFilteredEvents = filteredEvents;
    _cachedFilteredEventsByPeriod = filteredByPeriod;
  }

  /// Get which periods to include for a given time period filter
  List<TimePeriod> _getPeriodsForFilter(TimePeriod filter) {
    switch (filter) {
      case TimePeriod.thisWeek:
        // "This week" includes today, tomorrow, and the rest of this week
        return [TimePeriod.today, TimePeriod.tomorrow, TimePeriod.thisWeek];
      case TimePeriod.today:
        return [TimePeriod.today];
      case TimePeriod.tomorrow:
        return [TimePeriod.tomorrow];
      case TimePeriod.nextWeek:
        return [TimePeriod.nextWeek];
      default:
        return TimePeriod.values;
    }
  }

  /// Determine which period an event belongs to
  TimePeriod? _getEventPeriod(UnifiedEvent event) {
    for (final entry in eventsByPeriod.entries) {
      if (entry.value.contains(event)) {
        return entry.key;
      }
    }
    return null;
  }

  /// Alias for allEvents for calendar view compatibility
  List<UnifiedEvent> get events => allEvents;

  /// Get filtered events based on current filter (cached)
  List<UnifiedEvent> get filteredEvents => _cachedFilteredEvents;

  /// Get filtered events grouped by period (cached)
  Map<TimePeriod, List<UnifiedEvent>> get filteredEventsByPeriod => _cachedFilteredEventsByPeriod;

  /// Get today's events count
  int get todayCount => eventsByPeriod[TimePeriod.today]?.length ?? 0;

  /// Get tomorrow's events count
  int get tomorrowCount => eventsByPeriod[TimePeriod.tomorrow]?.length ?? 0;

  /// Get this week's events count (excluding today and tomorrow)
  int get thisWeekCount => eventsByPeriod[TimePeriod.thisWeek]?.length ?? 0;

  /// Get total upcoming events count
  int get upcomingCount {
    int count = 0;
    for (final period in [TimePeriod.today, TimePeriod.tomorrow, TimePeriod.thisWeek, TimePeriod.nextWeek]) {
      count += eventsByPeriod[period]?.length ?? 0;
    }
    return count;
  }

  /// Check if there are any events
  bool get hasEvents => allEvents.isNotEmpty;

  /// Get count by source
  Map<EventSource, int> get countBySource {
    final counts = <EventSource, int>{};
    for (final event in allEvents) {
      counts[event.source] = (counts[event.source] ?? 0) + 1;
    }
    return counts;
  }

  ScheduleLoaded copyWith({
    List<UnifiedEvent>? allEvents,
    Map<TimePeriod, List<UnifiedEvent>>? eventsByPeriod,
    EventSource? currentFilter,
    bool clearFilter = false,
    TimePeriod? timePeriodFilter,
    bool clearTimePeriodFilter = false,
    DateTime? selectedDate,
    bool clearSelectedDate = false,
    List<UnifiedEvent>? selectedDateEvents,
    DateTime? currentMonth,
    bool? hasMoreFutureEvents,
    bool? isLoadingMoreFuture,
    DateTime? futureEventsEndDate,
  }) {
    return ScheduleLoaded(
      allEvents: allEvents ?? this.allEvents,
      eventsByPeriod: eventsByPeriod ?? this.eventsByPeriod,
      currentFilter: clearFilter ? null : (currentFilter ?? this.currentFilter),
      timePeriodFilter: clearTimePeriodFilter ? null : (timePeriodFilter ?? this.timePeriodFilter),
      selectedDate: clearSelectedDate ? null : (selectedDate ?? this.selectedDate),
      selectedDateEvents: selectedDateEvents ?? this.selectedDateEvents,
      currentMonth: currentMonth ?? this.currentMonth,
      hasMoreFutureEvents: hasMoreFutureEvents ?? this.hasMoreFutureEvents,
      isLoadingMoreFuture: isLoadingMoreFuture ?? this.isLoadingMoreFuture,
      futureEventsEndDate: futureEventsEndDate ?? this.futureEventsEndDate,
    );
  }

  /// Check if any time filter is active
  bool get hasTimePeriodFilter => timePeriodFilter != null;

  /// Get display name for current time period filter
  String? get timePeriodFilterName {
    switch (timePeriodFilter) {
      case TimePeriod.thisWeek:
        return '本周';
      case TimePeriod.today:
        return '今天';
      case TimePeriod.tomorrow:
        return '明天';
      case TimePeriod.nextWeek:
        return '下周';
      default:
        return null;
    }
  }

  @override
  List<Object?> get props => [
    allEvents,
    eventsByPeriod,
    currentFilter,
    timePeriodFilter,
    selectedDate,
    selectedDateEvents,
    currentMonth,
    hasMoreFutureEvents,
    isLoadingMoreFuture,
    futureEventsEndDate,
  ];
}

class ScheduleError extends ScheduleState {
  final String message;

  const ScheduleError(this.message);

  @override
  List<Object?> get props => [message];
}

/// State for event creation in progress
class ScheduleEventCreating extends ScheduleState {
  const ScheduleEventCreating();
}

/// State for event creation success
class ScheduleEventCreated extends ScheduleState {
  final String eventId;
  final String title;

  const ScheduleEventCreated({required this.eventId, required this.title});

  @override
  List<Object?> get props => [eventId, title];
}

/// State for event update success
class ScheduleEventUpdated extends ScheduleState {
  final String eventId;

  const ScheduleEventUpdated({required this.eventId});

  @override
  List<Object?> get props => [eventId];
}

/// State for event deletion success
class ScheduleEventDeleted extends ScheduleState {
  final String eventId;

  const ScheduleEventDeleted({required this.eventId});

  @override
  List<Object?> get props => [eventId];
}

/// State for event operation failure
class ScheduleEventOperationError extends ScheduleState {
  final String message;

  const ScheduleEventOperationError(this.message);

  @override
  List<Object?> get props => [message];
}
