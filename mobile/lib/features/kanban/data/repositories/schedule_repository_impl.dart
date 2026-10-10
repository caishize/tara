import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../../domain/entities/unified_event.dart';
import '../../domain/repositories/schedule_repository.dart';
import '../datasources/schedule_aggregator.dart';

class ScheduleRepositoryImpl implements ScheduleRepository {
  final ScheduleAggregator aggregator;

  // Cache for events to avoid repeated fetching
  List<UnifiedEvent>? _cachedEvents;
  DateTime? _lastFetchTime;
  static const _cacheDuration = Duration(minutes: 5);

  ScheduleRepositoryImpl({required this.aggregator});

  bool get _isCacheValid {
    if (_cachedEvents == null || _lastFetchTime == null) return false;
    return DateTime.now().difference(_lastFetchTime!) < _cacheDuration;
  }

  @override
  Future<Either<Failure, List<UnifiedEvent>>> getUnifiedEvents({
    List<EventSource>? sources,
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    // Use cache if valid and no specific filters
    if (_isCacheValid && sources == null && startDate == null && endDate == null) {
      return Right(_cachedEvents!);
    }

    final result = await aggregator.aggregateEvents(
      sources: sources,
      startDate: startDate,
      endDate: endDate,
    );

    // Update cache if fetching all events
    result.fold(
      (_) {},
      (events) {
        if (sources == null && startDate == null && endDate == null) {
          _cachedEvents = events;
          _lastFetchTime = DateTime.now();
        }
      },
    );

    return result;
  }

  @override
  Future<Either<Failure, Map<TimePeriod, List<UnifiedEvent>>>> getEventsByPeriod({
    List<EventSource>? sources,
  }) async {
    final eventsResult = await getUnifiedEvents(sources: sources);

    return eventsResult.map((events) => aggregator.groupByPeriod(events));
  }

  @override
  Future<Either<Failure, List<UnifiedEvent>>> getEventsForDate(DateTime date) async {
    final eventsResult = await getUnifiedEvents();

    return eventsResult.map((events) => aggregator.filterByDate(events, date));
  }

  @override
  Future<Either<Failure, List<UnifiedEvent>>> getUpcomingEvents({
    int daysAhead = 30,
    List<EventSource>? sources,
  }) async {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final endDate = today.add(Duration(days: daysAhead));

    final result = await getUnifiedEvents(
      sources: sources,
      startDate: today,
      endDate: endDate,
    );

    return result.map((events) => events.where((e) => !e.isOverdue).toList());
  }

  @override
  Future<Either<Failure, List<UnifiedEvent>>> getTodayEvents() async {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    return getEventsForDate(today);
  }

  @override
  Future<Either<Failure, void>> refresh() async {
    _cachedEvents = null;
    _lastFetchTime = null;

    final result = await getUnifiedEvents();
    return result.map((_) {});
  }

  @override
  Future<Either<Failure, FutureEventsResult>> loadMoreFutureEvents({
    required DateTime startDate,
    required DateTime endDate,
    int limit = 20,
  }) async {
    final result = await aggregator.loadMoreFutureEvents(
      startDate: startDate,
      endDate: endDate,
      limit: limit,
    );

    return result.map((data) {
      final (events, hasMore) = data;
      return FutureEventsResult(events: events, hasMore: hasMore);
    });
  }
}
