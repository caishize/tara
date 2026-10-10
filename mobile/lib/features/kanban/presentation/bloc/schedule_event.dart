import 'package:equatable/equatable.dart';
import '../../domain/entities/unified_event.dart';

abstract class ScheduleEvent extends Equatable {
  const ScheduleEvent();

  @override
  List<Object?> get props => [];
}

/// Load all schedule events
class ScheduleLoadRequested extends ScheduleEvent {
  final List<EventSource>? sources;
  final TimePeriod? initialTimePeriodFilter;

  const ScheduleLoadRequested({this.sources, this.initialTimePeriodFilter});

  @override
  List<Object?> get props => [sources, initialTimePeriodFilter];
}

/// Refresh schedule data
class ScheduleRefreshRequested extends ScheduleEvent {
  const ScheduleRefreshRequested();
}

/// Filter by event source
class ScheduleFilterChanged extends ScheduleEvent {
  final EventSource? source;  // null means all sources

  const ScheduleFilterChanged(this.source);

  @override
  List<Object?> get props => [source];
}

/// Load events for a specific date
class ScheduleDateSelected extends ScheduleEvent {
  final DateTime date;

  const ScheduleDateSelected(this.date);

  @override
  List<Object?> get props => [date];
}

/// Change the current month for calendar view
class ScheduleMonthChanged extends ScheduleEvent {
  final DateTime month;

  const ScheduleMonthChanged(this.month);

  @override
  List<Object?> get props => [month];
}

/// Filter by time period (for "this week" navigation from briefing)
class ScheduleTimePeriodFilterChanged extends ScheduleEvent {
  final TimePeriod? timePeriod;  // null means show all periods

  const ScheduleTimePeriodFilterChanged(this.timePeriod);

  @override
  List<Object?> get props => [timePeriod];
}

/// Load more future events (lazy loading)
class ScheduleLoadMoreFutureRequested extends ScheduleEvent {
  const ScheduleLoadMoreFutureRequested();
}

/// Cancel/delete an event
class ScheduleCancelEventRequested extends ScheduleEvent {
  final String eventId;
  final String eventTitle;
  final String? sourceType; // e.g., 'travel', 'importantDate', 'curated'

  const ScheduleCancelEventRequested({
    required this.eventId,
    required this.eventTitle,
    this.sourceType,
  });

  @override
  List<Object?> get props => [eventId, eventTitle, sourceType];
}

/// Create a new user event
class ScheduleCreateEventRequested extends ScheduleEvent {
  final String title;
  final DateTime startTime;
  final DateTime? endTime;
  final String eventType;
  final String? location;
  final String priority;
  final String? notes;

  const ScheduleCreateEventRequested({
    required this.title,
    required this.startTime,
    this.endTime,
    this.eventType = 'other',
    this.location,
    this.priority = 'normal',
    this.notes,
  });

  @override
  List<Object?> get props => [title, startTime, endTime, eventType, location, priority, notes];
}

/// Update an existing event
class ScheduleUpdateEventRequested extends ScheduleEvent {
  final String eventId;
  final String? title;
  final DateTime? startTime;
  final DateTime? endTime;
  final String? eventType;
  final String? location;
  final String? priority;
  final String? notes;
  final String? status;

  const ScheduleUpdateEventRequested({
    required this.eventId,
    this.title,
    this.startTime,
    this.endTime,
    this.eventType,
    this.location,
    this.priority,
    this.notes,
    this.status,
  });

  @override
  List<Object?> get props => [eventId, title, startTime, endTime, eventType, location, priority, notes, status];
}

/// Delete an event
class ScheduleDeleteEventRequested extends ScheduleEvent {
  final String eventId;

  const ScheduleDeleteEventRequested({required this.eventId});

  @override
  List<Object?> get props => [eventId];
}
