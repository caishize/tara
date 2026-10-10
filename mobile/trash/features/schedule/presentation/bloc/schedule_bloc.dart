import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/network/api_client.dart';
import '../../domain/entities/unified_event.dart';
import '../../domain/repositories/schedule_repository.dart';
import 'schedule_event.dart';
import 'schedule_state.dart';

class ScheduleBloc extends Bloc<ScheduleEvent, ScheduleState> {
  final ScheduleRepository repository;
  final ApiClient? apiClient;

  // Pagination configuration
  static const int _futureEventsDaysStep = 14; // Load 2 weeks at a time

  ScheduleBloc({required this.repository, this.apiClient}) : super(const ScheduleInitial()) {
    on<ScheduleLoadRequested>(_onLoadRequested);
    on<ScheduleRefreshRequested>(_onRefreshRequested);
    on<ScheduleFilterChanged>(_onFilterChanged);
    on<ScheduleTimePeriodFilterChanged>(_onTimePeriodFilterChanged);
    on<ScheduleDateSelected>(_onDateSelected);
    on<ScheduleMonthChanged>(_onMonthChanged);
    on<ScheduleLoadMoreFutureRequested>(_onLoadMoreFutureRequested);
    on<ScheduleCancelEventRequested>(_onCancelEventRequested);
    on<ScheduleCreateEventRequested>(_onCreateEventRequested);
    on<ScheduleUpdateEventRequested>(_onUpdateEventRequested);
    on<ScheduleDeleteEventRequested>(_onDeleteEventRequested);
  }

  Future<void> _onLoadRequested(
    ScheduleLoadRequested event,
    Emitter<ScheduleState> emit,
  ) async {
    emit(const ScheduleLoading());

    final result = await repository.getEventsByPeriod(sources: event.sources);

    result.fold(
      (failure) => emit(ScheduleError(failure.message)),
      (eventsByPeriod) {
        // Flatten to get all events
        final allEvents = <UnifiedEvent>[];
        for (final events in eventsByPeriod.values) {
          allEvents.addAll(events);
        }

        // Calculate initial end date for future events (7 days from today)
        final now = DateTime.now();
        final today = DateTime(now.year, now.month, now.day);
        final initialFutureEndDate = today.add(const Duration(days: 7));

        emit(ScheduleLoaded(
          allEvents: allEvents,
          eventsByPeriod: eventsByPeriod,
          currentFilter: event.sources?.length == 1 ? event.sources!.first : null,
          timePeriodFilter: event.initialTimePeriodFilter,
          hasMoreFutureEvents: true, // Assume there are more events initially
          futureEventsEndDate: initialFutureEndDate,
        ));
      },
    );
  }

  Future<void> _onRefreshRequested(
    ScheduleRefreshRequested event,
    Emitter<ScheduleState> emit,
  ) async {
    final currentState = state;
    EventSource? currentFilter;
    if (currentState is ScheduleLoaded) {
      currentFilter = currentState.currentFilter;
    }

    // Clear cache and reload
    await repository.refresh();

    final result = await repository.getEventsByPeriod();

    result.fold(
      (failure) => emit(ScheduleError(failure.message)),
      (eventsByPeriod) {
        final allEvents = <UnifiedEvent>[];
        for (final events in eventsByPeriod.values) {
          allEvents.addAll(events);
        }

        // Reset pagination state on refresh
        final now = DateTime.now();
        final today = DateTime(now.year, now.month, now.day);
        final initialFutureEndDate = today.add(const Duration(days: 7));

        emit(ScheduleLoaded(
          allEvents: allEvents,
          eventsByPeriod: eventsByPeriod,
          currentFilter: currentFilter,
          hasMoreFutureEvents: true, // Reset to allow loading more
          futureEventsEndDate: initialFutureEndDate,
        ));
      },
    );
  }

  Future<void> _onFilterChanged(
    ScheduleFilterChanged event,
    Emitter<ScheduleState> emit,
  ) async {
    final currentState = state;
    if (currentState is ScheduleLoaded) {
      emit(currentState.copyWith(
        currentFilter: event.source,
        clearFilter: event.source == null,
      ));
    }
  }

  Future<void> _onDateSelected(
    ScheduleDateSelected event,
    Emitter<ScheduleState> emit,
  ) async {
    final currentState = state;
    if (currentState is ScheduleLoaded) {
      final result = await repository.getEventsForDate(event.date);

      result.fold(
        (failure) {
          // Keep current state but clear selected date
          emit(currentState.copyWith(
            clearSelectedDate: true,
          ));
        },
        (dateEvents) {
          emit(currentState.copyWith(
            selectedDate: event.date,
            selectedDateEvents: dateEvents,
          ));
        },
      );
    }
  }

  void _onMonthChanged(
    ScheduleMonthChanged event,
    Emitter<ScheduleState> emit,
  ) {
    final currentState = state;
    if (currentState is ScheduleLoaded) {
      emit(currentState.copyWith(currentMonth: event.month));
    }
  }

  void _onTimePeriodFilterChanged(
    ScheduleTimePeriodFilterChanged event,
    Emitter<ScheduleState> emit,
  ) {
    final currentState = state;
    if (currentState is ScheduleLoaded) {
      emit(currentState.copyWith(
        timePeriodFilter: event.timePeriod,
        clearTimePeriodFilter: event.timePeriod == null,
      ));
    }
  }

  Future<void> _onLoadMoreFutureRequested(
    ScheduleLoadMoreFutureRequested event,
    Emitter<ScheduleState> emit,
  ) async {
    final currentState = state;
    if (currentState is! ScheduleLoaded) return;

    // Don't load if already loading or no more events
    if (currentState.isLoadingMoreFuture || !currentState.hasMoreFutureEvents) {
      return;
    }

    // Set loading state
    emit(currentState.copyWith(isLoadingMoreFuture: true));

    // Calculate next date range
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final currentEndDate = currentState.futureEventsEndDate ??
        today.add(const Duration(days: 7));
    final newStartDate = currentEndDate.add(const Duration(days: 1));
    final newEndDate = newStartDate.add(Duration(days: _futureEventsDaysStep));

    final result = await repository.loadMoreFutureEvents(
      startDate: newStartDate,
      endDate: newEndDate,
    );

    result.fold(
      (failure) {
        // On failure, just reset loading state
        emit(currentState.copyWith(isLoadingMoreFuture: false));
      },
      (futureResult) {
        // Merge new events with existing events
        final newAllEvents = [...currentState.allEvents, ...futureResult.events];

        // Sort by date
        newAllEvents.sort((a, b) {
          if (a.dateTime == null && b.dateTime == null) return 0;
          if (a.dateTime == null) return 1;
          if (b.dateTime == null) return -1;
          return a.dateTime!.compareTo(b.dateTime!);
        });

        // Regroup events by period
        final newEventsByPeriod = _groupEventsByPeriod(newAllEvents);

        emit(currentState.copyWith(
          allEvents: newAllEvents,
          eventsByPeriod: newEventsByPeriod,
          isLoadingMoreFuture: false,
          hasMoreFutureEvents: futureResult.hasMore,
          futureEventsEndDate: newEndDate,
        ));
      },
    );
  }

  /// Helper to group events by period
  Map<TimePeriod, List<UnifiedEvent>> _groupEventsByPeriod(List<UnifiedEvent> events) {
    final grouped = <TimePeriod, List<UnifiedEvent>>{};

    for (final period in TimePeriod.values) {
      grouped[period] = [];
    }

    for (final event in events) {
      grouped[event.timePeriod]!.add(event);
    }

    // Remove empty periods
    grouped.removeWhere((_, events) => events.isEmpty);

    return grouped;
  }

  /// Cancel/delete an event
  Future<void> _onCancelEventRequested(
    ScheduleCancelEventRequested event,
    Emitter<ScheduleState> emit,
  ) async {
    if (apiClient == null) return;

    final currentState = state;
    if (currentState is! ScheduleLoaded) return;

    // Find the event in current state to get its full data
    UnifiedEvent? targetEvent;
    try {
      targetEvent = currentState.allEvents.firstWhere(
        (e) => e.id == event.eventId,
      );
    } catch (_) {
      // Event not found in state, cannot proceed
      return;
    }

    // Optimistic update: remove the event from UI immediately
    final updatedEvents = currentState.allEvents
        .where((e) => e.id != event.eventId)
        .toList();
    final newEventsByPeriod = _groupEventsByPeriod(updatedEvents);

    emit(currentState.copyWith(
      allEvents: updatedEvents,
      eventsByPeriod: newEventsByPeriod,
    ));

    try {
      // Check if this is a curated event (from AI secretary curation)
      final isCurated = targetEvent.sourceData['curated'] == true;

      if (isCurated) {
        // For curated events, we need to:
        // 1. Cancel the curated event itself in the timeline service
        // 2. Also delete the original source if needed

        await apiClient!.patch<Map<String, dynamic>>(
          '/secretary/timeline/events/${event.eventId}/status',
          data: {'status': 'cancelled'},
        );

        // Then, if it has an original source, delete that too
        final originalId = targetEvent.sourceData['originalId'] as String?;
        final sourceTypes = targetEvent.sourceData['sourceTypes'] as List<dynamic>?;

        if (originalId != null && sourceTypes != null && sourceTypes.isNotEmpty) {
          if (sourceTypes.contains('travel_plan')) {
            try {
              await apiClient!.delete('/travel/plans/$originalId');
            } catch (_) {
              // Ignore if original deletion fails, curated event is already cancelled
            }
          } else if (sourceTypes.contains('important_date')) {
            try {
              await apiClient!.delete('/dates/$originalId');
            } catch (_) {
              // Ignore if original deletion fails
            }
          }
        }
      } else if (event.eventId.startsWith('date_')) {
        final actualId = event.eventId.substring(5);
        await apiClient!.delete('/dates/$actualId');
      } else if (event.eventId.startsWith('travel_')) {
        final actualId = event.eventId.substring(7);
        await apiClient!.delete('/travel/plans/$actualId');
      } else if (event.eventId.startsWith('task_')) {
        // FamilyTask events → handled separately if needed
        final actualId = event.eventId.substring(5);
        await apiClient!.patch<Map<String, dynamic>>(
          '/tasks/$actualId',
          data: {'status': 'cancelled'},
        );
      } else {
        await apiClient!.patch<Map<String, dynamic>>(
          '/secretary/timeline/events/${event.eventId}/status',
          data: {'status': 'cancelled'},
        );
      }
      await repository.refresh();
    } catch (_) {
      // Restore the original state so the event reappears in UI
      emit(currentState);
    }
  }

  Future<void> _onCreateEventRequested(
    ScheduleCreateEventRequested event,
    Emitter<ScheduleState> emit,
  ) async {
    if (apiClient == null) return;

    emit(const ScheduleEventCreating());

    try {
      final response = await apiClient!.post<Map<String, dynamic>>(
        '/secretary/events',
        data: {
          'title': event.title,
          'start_time': event.startTime.toUtc().toIso8601String(),
          'end_time': event.endTime?.toUtc().toIso8601String(),
          'event_type': event.eventType,
          'location': event.location,
          'priority': event.priority,
          'notes': event.notes,
          'tags': <String>[],
        },
        queryParameters: {
          // user_id and family_id are added by the API interceptor
        },
      );

      final eventId = response['id'] as String? ?? '';
      emit(ScheduleEventCreated(eventId: eventId, title: event.title));

      // Refresh the schedule to include the new event
      await repository.refresh();
      add(const ScheduleLoadRequested());
    } catch (e) {
      emit(ScheduleEventOperationError('创建日程失败: $e'));
    }
  }

  Future<void> _onUpdateEventRequested(
    ScheduleUpdateEventRequested event,
    Emitter<ScheduleState> emit,
  ) async {
    if (apiClient == null) return;

    try {
      final updates = <String, dynamic>{};
      if (event.title != null) updates['title'] = event.title;
      if (event.startTime != null) {
        updates['start_time'] = event.startTime!.toUtc().toIso8601String();
      }
      if (event.endTime != null) {
        updates['end_time'] = event.endTime!.toUtc().toIso8601String();
      }
      if (event.eventType != null) updates['event_type'] = event.eventType;
      if (event.location != null) updates['location'] = event.location;
      if (event.priority != null) updates['priority'] = event.priority;
      if (event.notes != null) updates['notes'] = event.notes;
      if (event.status != null) updates['status'] = event.status;

      await apiClient!.patch<Map<String, dynamic>>(
        '/secretary/events/${event.eventId}',
        data: updates,
      );

      emit(ScheduleEventUpdated(eventId: event.eventId));

      // Refresh
      await repository.refresh();
      add(const ScheduleLoadRequested());
    } catch (e) {
      emit(ScheduleEventOperationError('更新日程失败: $e'));
    }
  }

  Future<void> _onDeleteEventRequested(
    ScheduleDeleteEventRequested event,
    Emitter<ScheduleState> emit,
  ) async {
    if (apiClient == null) return;

    try {
      await apiClient!.delete<dynamic>(
        '/secretary/events/${event.eventId}',
      );

      emit(ScheduleEventDeleted(eventId: event.eventId));

      // Refresh
      await repository.refresh();
      add(const ScheduleLoadRequested());
    } catch (e) {
      emit(ScheduleEventOperationError('删除日程失败: $e'));
    }
  }
}
