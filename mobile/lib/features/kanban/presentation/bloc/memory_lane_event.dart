import 'package:equatable/equatable.dart';

/// Memory lane events
abstract class MemoryLaneEvent extends Equatable {
  const MemoryLaneEvent();

  @override
  List<Object?> get props => [];
}

/// Load memory lane (past stories + yearly summaries)
class LoadMemoryLane extends MemoryLaneEvent {
  const LoadMemoryLane();
}

/// Load on-this-day items
class LoadOnThisDay extends MemoryLaneEvent {
  const LoadOnThisDay();
}

/// Dismiss an on-this-day card
class DismissOnThisDay extends MemoryLaneEvent {
  final String eventId;

  const DismissOnThisDay(this.eventId);

  @override
  List<Object?> get props => [eventId];
}

/// Load AI memory highlights (memory_reflection insights)
class LoadMemoryHighlights extends MemoryLaneEvent {
  const LoadMemoryHighlights();
}

/// Load detail for a specific year
class LoadYearDetail extends MemoryLaneEvent {
  final int year;

  const LoadYearDetail(this.year);

  @override
  List<Object?> get props => [year];
}
