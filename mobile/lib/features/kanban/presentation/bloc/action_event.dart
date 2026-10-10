import 'package:equatable/equatable.dart';

/// Events for the dedicated PendingAction confirmation lifecycle BLoC.
///
/// Decoupled from InsightFeedBloc — the two communicate through
/// [CuratedTimelineRepository], not direct BLoC-to-BLoC calls.
sealed class ActionEvent extends Equatable {
  const ActionEvent();

  @override
  List<Object?> get props => [];
}

/// Initiate action creation for a given insight.
///
/// The BLoC checks [ConfirmationTier] via [ActionTypeRegistry]:
/// - `direct` tier: emits [ActionConfirmed] immediately (no API call).
/// - `inline`/`full` tier: calls `repository.executeInsightAction()` to
///   create a PendingAction, then emits [ActionPendingConfirm].
class RequestAction extends ActionEvent {
  final String insightId;
  final String actionType;
  final Map<String, dynamic>? actionData;

  const RequestAction({
    required this.insightId,
    required this.actionType,
    this.actionData,
  });

  @override
  List<Object?> get props => [insightId, actionType, actionData];
}

/// User confirmed the pending action via the confirmation sheet.
class ConfirmAction extends ActionEvent {
  final String actionId;

  const ConfirmAction({required this.actionId});

  @override
  List<Object?> get props => [actionId];
}

/// User rejected/cancelled the pending action.
class RejectAction extends ActionEvent {
  final String actionId;

  const RejectAction({required this.actionId});

  @override
  List<Object?> get props => [actionId];
}

/// Clear current action state back to idle.
class ResetAction extends ActionEvent {
  const ResetAction();
}
