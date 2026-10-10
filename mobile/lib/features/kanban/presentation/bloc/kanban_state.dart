import 'package:equatable/equatable.dart';
import '../../data/models/kanban_models.dart';

/// Kanban view states
abstract class KanbanState extends Equatable {
  const KanbanState();

  @override
  List<Object?> get props => [];
}

/// Initial state
class KanbanInitial extends KanbanState {
  const KanbanInitial();
}

/// Loading state
class KanbanLoading extends KanbanState {
  const KanbanLoading();
}

/// Kanban view loaded
class KanbanLoaded extends KanbanState {
  final KanbanResponseModel kanban;
  final bool isRefreshing;

  const KanbanLoaded({
    required this.kanban,
    this.isRefreshing = false,
  });

  KanbanLoaded copyWith({
    KanbanResponseModel? kanban,
    bool? isRefreshing,
  }) {
    return KanbanLoaded(
      kanban: kanban ?? this.kanban,
      isRefreshing: isRefreshing ?? this.isRefreshing,
    );
  }

  @override
  List<Object?> get props => [kanban, isRefreshing];
}

/// Search results state
class KanbanSearchResults extends KanbanState {
  final String query;
  final List<KanbanEventModel> results;
  final int total;
  final bool isSearching;

  const KanbanSearchResults({
    required this.query,
    this.results = const [],
    this.total = 0,
    this.isSearching = false,
  });

  KanbanSearchResults copyWith({
    String? query,
    List<KanbanEventModel>? results,
    int? total,
    bool? isSearching,
  }) {
    return KanbanSearchResults(
      query: query ?? this.query,
      results: results ?? this.results,
      total: total ?? this.total,
      isSearching: isSearching ?? this.isSearching,
    );
  }

  @override
  List<Object?> get props => [query, results, total, isSearching];
}

/// Error state
class KanbanError extends KanbanState {
  final String message;

  const KanbanError({required this.message});

  @override
  List<Object?> get props => [message];
}
