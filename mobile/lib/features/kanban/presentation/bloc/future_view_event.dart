import 'package:equatable/equatable.dart';
import '../../data/models/future_view_models.dart';

abstract class FutureViewEvent extends Equatable {
  const FutureViewEvent();
  @override
  List<Object?> get props => [];
}

class LoadFutureView extends FutureViewEvent {
  const LoadFutureView();
}

class RefreshFutureView extends FutureViewEvent {
  const RefreshFutureView();
}

class DismissSuggestion extends FutureViewEvent {
  final String insightId;
  final String feedbackType;
  final String? reason;
  const DismissSuggestion(
    this.insightId, {
    this.feedbackType = 'not_useful',
    this.reason,
  });
  @override
  List<Object?> get props => [insightId, feedbackType, reason];
}

class DismissAllSuggestions extends FutureViewEvent {
  const DismissAllSuggestions();
}

/// Adopt an insight to a trip (creates trip entity link, status → acted).
class AdoptInsight extends FutureViewEvent {
  final String insightId;
  final String tripId;
  const AdoptInsight({required this.insightId, required this.tripId});
  @override
  List<Object?> get props => [insightId, tripId];
}

/// Accept/acknowledge a top-level suggestion.
class AcceptSuggestion extends FutureViewEvent {
  final String insightId;
  final String actionType;
  final Map<String, dynamic>? actionData;
  const AcceptSuggestion({
    required this.insightId,
    required this.actionType,
    this.actionData,
  });
  @override
  List<Object?> get props => [insightId, actionType, actionData];
}

/// Confirm a sub-item: if trip-related, add as prep item to trip.
class ConfirmSubItem extends FutureViewEvent {
  final FutureViewSuggestionSubItem subItem;
  final String? relatedTripId;
  final String? insightId;
  const ConfirmSubItem(this.subItem, {this.relatedTripId, this.insightId});
  @override
  List<Object?> get props => [subItem.id, relatedTripId, insightId];
}

/// Dismiss a sub-item.
class DismissSubItem extends FutureViewEvent {
  final FutureViewSuggestionSubItem subItem;
  const DismissSubItem(this.subItem);
  @override
  List<Object?> get props => [subItem.id];
}

class ToggleTaskDone extends FutureViewEvent {
  final String tripId;
  final String taskId;
  final bool done;
  const ToggleTaskDone({required this.tripId, required this.taskId, required this.done});
  @override
  List<Object?> get props => [tripId, taskId, done];
}

/// Batch-dismiss all suggestions in a group.
class DismissSuggestionGroup extends FutureViewEvent {
  final List<String> insightIds;
  const DismissSuggestionGroup(this.insightIds);
  @override
  List<Object?> get props => [insightIds];
}

/// Load more upcoming items (lazy loading).
class LoadMoreUpcoming extends FutureViewEvent {
  const LoadMoreUpcoming();
}
