import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../../../dates/domain/repositories/date_repository.dart';
import '../../../trip/domain/repositories/trip_repository.dart';
import '../../../trip/domain/entities/trip.dart';
import '../../domain/entities/unified_event.dart';
import '../models/unified_event_model.dart';
import 'curated_timeline_datasource.dart';

/// Aggregates schedule data from multiple sources
/// Prefers AI-curated timeline when available
class ScheduleAggregator {
  final DateRepository dateRepository;
  final TripRepository tripRepository;
  final CuratedTimelineDataSource? curatedTimelineDataSource;

  /// Last curation timestamp (from API)
  DateTime? lastCuratedAt;

  /// Whether we have unconfirmed items
  bool hasUnconfirmedItems = false;
  int unconfirmedCount = 0;

  ScheduleAggregator({
    required this.dateRepository,
    required this.tripRepository,
    this.curatedTimelineDataSource,
  });

  /// Fetch and aggregate all events from different sources
  /// Prefers AI-curated timeline for future events, uses legacy aggregation for history
  Future<Either<Failure, List<UnifiedEvent>>> aggregateEvents({
    List<EventSource>? sources,
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);

    // For historical data (before today), use legacy aggregation directly
    // AI curation is optimized for future events planning
    final isHistoricalQuery = endDate != null && endDate.isBefore(today);

    // If this is a full timeline request (no date range), we need both:
    // - Curated events for future
    // - Legacy events for historical (overdue)
    final isFullTimelineRequest = startDate == null && endDate == null;

    // Try AI-curated timeline for non-historical queries
    if (!isHistoricalQuery && curatedTimelineDataSource != null) {
      try {
        final curatedResponse = await curatedTimelineDataSource!.fetchCuratedTimeline(
          startDate: startDate,
          endDate: endDate,
        );

        // Store curation metadata
        lastCuratedAt = curatedResponse.lastCuratedAt;
        hasUnconfirmedItems = curatedResponse.hasUnconfirmed;
        unconfirmedCount = curatedResponse.unconfirmedCount;

        if (curatedResponse.events.isNotEmpty) {
          // Convert curated events to unified events
          final unifiedEvents = curatedResponse.toUnifiedEvents();

          // For full timeline request, also fetch historical events from legacy sources
          // Note: Only fetch sources that have actual historical data (travel, tasks, external)
          // Important dates are excluded because they always calculate next occurrence (future),
          // and they're already included in the curated events
          if (isFullTimelineRequest) {
            final historicalSources = [
              EventSource.travelPlan,
              EventSource.familyTask,
              EventSource.externalCalendar,
              EventSource.externalTravel,
            ];
            final historicalResult = await _aggregateFromLegacySources(
              sources: historicalSources,
              startDate: today.subtract(const Duration(days: 90)), // Last 90 days
              endDate: today.subtract(const Duration(days: 1)), // Up to yesterday
            );

            historicalResult.fold(
              (failure) {
                // Ignore historical fetch failure, just use curated events
              },
              (historicalEvents) {
                // Add historical events to the list
                unifiedEvents.addAll(historicalEvents);
              },
            );
          }

          // Sort by date
          unifiedEvents.sort((a, b) {
            if (a.dateTime == null && b.dateTime == null) return 0;
            if (a.dateTime == null) return 1;
            if (b.dateTime == null) return -1;
            return a.dateTime!.compareTo(b.dateTime!);
          });

          return Right(unifiedEvents);
        }
        // If no curated events, fall back to legacy aggregation
      } catch (e) {
        // Curated API failed, fall back to legacy aggregation
      }
    }

    // Legacy aggregation: fetch from multiple sources directly
    return _aggregateFromLegacySources(
      sources: sources,
      startDate: startDate,
      endDate: endDate,
    );
  }

  /// Legacy aggregation from multiple data sources
  Future<Either<Failure, List<UnifiedEvent>>> _aggregateFromLegacySources({
    List<EventSource>? sources,
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    final List<UnifiedEvent> allEvents = [];
    final errors = <String>[];

    // Determine which sources to fetch
    final sourcesToFetch = sources ?? EventSource.values;

    // Fetch from ImportantDates
    if (sourcesToFetch.contains(EventSource.importantDate)) {
      final datesResult = await _fetchImportantDates(startDate, endDate);
      datesResult.fold(
        (failure) => errors.add('重要日期: ${failure.message}'),
        (events) => allEvents.addAll(events),
      );
    }

    // Fetch from Trips
    if (sourcesToFetch.contains(EventSource.travelPlan)) {
      final tripResult = await _fetchTrips(startDate, endDate);
      tripResult.fold(
        (failure) => errors.add('旅行计划: ${failure.message}'),
        (events) => allEvents.addAll(events),
      );
    }

    // TODO: Re-add task and external calendar sources when those features are implemented

    // Sort events by date
    allEvents.sort((a, b) {
      if (a.dateTime == null && b.dateTime == null) return 0;
      if (a.dateTime == null) return 1;
      if (b.dateTime == null) return -1;
      return a.dateTime!.compareTo(b.dateTime!);
    });

    // If all sources failed, return error
    if (allEvents.isEmpty && errors.isNotEmpty) {
      return Left(ServerFailure(errors.join('\n')));
    }

    return Right(allEvents);
  }

  /// Fetch important dates and convert to UnifiedEvent
  Future<Either<Failure, List<UnifiedEvent>>> _fetchImportantDates(
    DateTime? startDate,
    DateTime? endDate,
  ) async {
    final result = await dateRepository.getDates();
    return result.map((dates) {
      final events = dates.map((date) => UnifiedEventModel.fromImportantDate(date)).toList();

      // Deduplicate events by title for recurring events
      // The database may store multiple years' records for the same recurring event
      // (e.g., Spring Festival 2025, 2026, 2027 or New Year's Day 2025, 2026, 2027)
      // For recurring events, we only want to show once with the calculated next occurrence
      final seen = <String>{};
      final deduplicatedEvents = events.where((event) {
        final isRecurring = event.sourceData['isRecurring'] as bool? ?? false;

        // For recurring events, deduplicate by title only
        // This ensures the same recurring event (holiday, birthday, etc.) shows only once
        if (isRecurring) {
          final key = '${event.title}_recurring';
          if (seen.contains(key)) {
            return false;
          }
          seen.add(key);
          return true;
        }

        // For non-recurring events, use title + date for deduplication
        // Use local time for date key to ensure correct day boundary
        final localDateTime = event.dateTime?.toLocal();
        final dateStr = localDateTime != null
            ? '${localDateTime.year}-${localDateTime.month}-${localDateTime.day}'
            : 'no-date';
        final key = '${event.title}_$dateStr';
        if (seen.contains(key)) {
          return false;
        }
        seen.add(key);
        return true;
      }).toList();

      // Filter by date range if specified
      if (startDate != null || endDate != null) {
        return deduplicatedEvents.where((event) {
          if (event.dateTime == null) return true;
          if (startDate != null && event.dateTime!.isBefore(startDate)) return false;
          if (endDate != null && event.dateTime!.isAfter(endDate)) return false;
          return true;
        }).toList();
      }

      return deduplicatedEvents;
    });
  }

  /// Fetch travel plans and convert to UnifiedEvent
  Future<Either<Failure, List<UnifiedEvent>>> _fetchTrips(
    DateTime? startDate,
    DateTime? endDate,
  ) async {
    // Only fetch active travel plans (not completed or cancelled)
    final result = await tripRepository.getTrips();
    return result.map((plans) {
      // Filter out completed and cancelled plans
      final activePlans = plans.where((plan) =>
        plan.status != TripStatus.completed &&
        plan.status != TripStatus.cancelled
      ).toList();

      final events = activePlans.map((plan) => UnifiedEventModel.fromTrip(plan)).toList();

      // Filter by date range if specified
      if (startDate != null || endDate != null) {
        return events.where((event) {
          if (event.dateTime == null) return true;
          // For travel plans, check if any part of the trip overlaps with the range
          final tripEnd = event.endDateTime ?? event.dateTime;
          if (startDate != null && tripEnd!.isBefore(startDate)) return false;
          if (endDate != null && event.dateTime!.isAfter(endDate)) return false;
          return true;
        }).toList();
      }

      return events;
    });
  }

  /// Group events by time period
  Map<TimePeriod, List<UnifiedEvent>> groupByPeriod(List<UnifiedEvent> events) {
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

  /// Load more future events for lazy loading
  /// Returns (events, hasMore)
  Future<Either<Failure, (List<UnifiedEvent>, bool)>> loadMoreFutureEvents({
    required DateTime startDate,
    required DateTime endDate,
    int limit = 20,
    int offset = 0,
  }) async {
    if (curatedTimelineDataSource == null) {
      return const Right(([], false));
    }

    try {
      final curatedResponse = await curatedTimelineDataSource!.fetchCuratedTimeline(
        startDate: startDate,
        endDate: endDate,
        limit: limit,
        offset: offset,
      );

      // Update metadata
      hasUnconfirmedItems = curatedResponse.hasUnconfirmed;
      unconfirmedCount = curatedResponse.unconfirmedCount;

      // Convert to unified events
      final events = curatedResponse.toUnifiedEvents();

      return Right((events, curatedResponse.hasMore));
    } catch (e) {
      return Left(ServerFailure('加载更多失败: $e'));
    }
  }

  /// Get events for a specific date
  List<UnifiedEvent> filterByDate(List<UnifiedEvent> events, DateTime date) {
    final targetDate = DateTime(date.year, date.month, date.day);

    return events.where((event) {
      if (event.dateTime == null) return false;

      // Convert to local time before extracting date components
      final localStart = event.dateTime!.toLocal();
      final eventStart = DateTime(
        localStart.year,
        localStart.month,
        localStart.day,
      );

      // For single-day events
      if (event.endDateTime == null) {
        return eventStart.isAtSameMomentAs(targetDate);
      }

      // For multi-day events (like travel)
      // Convert end time to local as well
      final localEnd = event.endDateTime!.toLocal();
      final eventEnd = DateTime(
        localEnd.year,
        localEnd.month,
        localEnd.day,
      );

      return !targetDate.isBefore(eventStart) && !targetDate.isAfter(eventEnd);
    }).toList();
  }
}
