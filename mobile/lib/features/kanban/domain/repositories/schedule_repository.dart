import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/unified_event.dart';

/// Repository interface for unified schedule
abstract class ScheduleRepository {
  /// Get all unified events from all sources
  /// [sources] - Optional filter for specific sources
  /// [startDate] - Optional start date filter
  /// [endDate] - Optional end date filter
  Future<Either<Failure, List<UnifiedEvent>>> getUnifiedEvents({
    List<EventSource>? sources,
    DateTime? startDate,
    DateTime? endDate,
  });

  /// Get events grouped by time period
  Future<Either<Failure, Map<TimePeriod, List<UnifiedEvent>>>> getEventsByPeriod({
    List<EventSource>? sources,
  });

  /// Get events for a specific date
  Future<Either<Failure, List<UnifiedEvent>>> getEventsForDate(DateTime date);

  /// Get upcoming events (next N days)
  Future<Either<Failure, List<UnifiedEvent>>> getUpcomingEvents({
    int daysAhead = 30,
    List<EventSource>? sources,
  });

  /// Get today's events
  Future<Either<Failure, List<UnifiedEvent>>> getTodayEvents();

  /// Refresh data from all sources
  Future<Either<Failure, void>> refresh();

  /// Load more future events (for lazy loading)
  /// Returns events and hasMore flag
  Future<Either<Failure, FutureEventsResult>> loadMoreFutureEvents({
    required DateTime startDate,
    required DateTime endDate,
    int limit = 20,
  });
}

/// Result for loading future events with pagination info
class FutureEventsResult {
  final List<UnifiedEvent> events;
  final bool hasMore;

  FutureEventsResult({required this.events, required this.hasMore});
}
