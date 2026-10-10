import 'package:equatable/equatable.dart';
import '../../data/models/future_view_models.dart';

abstract class FutureViewState extends Equatable {
  const FutureViewState();
  @override
  List<Object?> get props => [];
}

class FutureViewInitial extends FutureViewState {
  const FutureViewInitial();
}

class FutureViewLoading extends FutureViewState {
  const FutureViewLoading();
}

class FutureViewLoaded extends FutureViewState {
  final FutureViewResponseModel data;
  final Set<String> dismissedSuggestionIds;
  final DateTime? lastLoadedAt;
  final bool isLoadingMore;

  const FutureViewLoaded({
    required this.data,
    this.dismissedSuggestionIds = const {},
    this.lastLoadedAt,
    this.isLoadingMore = false,
  });

  @override
  List<Object?> get props => [data, dismissedSuggestionIds, lastLoadedAt, isLoadingMore];
}

class FutureViewError extends FutureViewState {
  final String message;
  const FutureViewError(this.message);
  @override
  List<Object?> get props => [message];
}
