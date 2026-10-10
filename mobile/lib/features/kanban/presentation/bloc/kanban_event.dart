import 'package:equatable/equatable.dart';

/// Kanban view events
abstract class KanbanEvent extends Equatable {
  const KanbanEvent();

  @override
  List<Object?> get props => [];
}

/// Load kanban view
class LoadKanbanView extends KanbanEvent {
  const LoadKanbanView();
}

/// Toggle a preparation item checkbox
class TogglePreparationItem extends KanbanEvent {
  final String eventId;
  final int itemIndex;
  final String? itemKey;
  final bool done;

  const TogglePreparationItem({
    required this.eventId,
    required this.itemIndex,
    this.itemKey,
    required this.done,
  });

  @override
  List<Object?> get props => [eventId, itemIndex, itemKey, done];
}

/// Search events by query
class SearchEvents extends KanbanEvent {
  final String query;
  final List<String>? eventTypes;

  const SearchEvents({required this.query, this.eventTypes});

  @override
  List<Object?> get props => [query, eventTypes];
}

/// Clear search results and return to kanban
class ClearSearch extends KanbanEvent {
  const ClearSearch();
}

