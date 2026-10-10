import 'package:equatable/equatable.dart';

import '../../data/models/insight_feed_models.dart';

/// States for the dedicated PendingAction confirmation lifecycle BLoC.
///
/// Each state carries the [insightId] that originated the action so the UI
/// can correlate state changes back to the correct insight card.
sealed class ActionState extends Equatable {
  const ActionState();

  @override
  List<Object?> get props => [];
}

/// No action in progress.
class ActionIdle extends ActionState {
  const ActionIdle();
}

/// API call in progress to create a PendingAction.
class ActionCreating extends ActionState {
  final String insightId;

  const ActionCreating({required this.insightId});

  @override
  List<Object?> get props => [insightId];
}

/// PendingAction created — waiting for user to confirm or reject.
///
/// PLAN-008: [confirmationTier] determines the UI treatment:
/// - `inline`: lightweight chip expansion with preview
/// - `full`: full bottom-sheet with details
class ActionPendingConfirm extends ActionState {
  final String insightId;
  final PendingActionResponseModel pendingAction;
  final String confirmationTier;

  const ActionPendingConfirm({
    required this.insightId,
    required this.pendingAction,
    this.confirmationTier = 'full',
  });

  @override
  List<Object?> get props => [insightId, pendingAction, confirmationTier];
}

/// Confirm API call in progress.
class ActionConfirming extends ActionState {
  final String insightId;
  final String actionId;

  const ActionConfirming({
    required this.insightId,
    required this.actionId,
  });

  @override
  List<Object?> get props => [insightId, actionId];
}

/// Action was successfully confirmed and executed.
class ActionConfirmed extends ActionState {
  final String insightId;

  const ActionConfirmed({required this.insightId});

  @override
  List<Object?> get props => [insightId];
}

/// Action failed — the UI can offer a retry option.
class ActionFailed extends ActionState {
  final String insightId;
  final String message;

  const ActionFailed({
    required this.insightId,
    required this.message,
  });

  @override
  List<Object?> get props => [insightId, message];
}
