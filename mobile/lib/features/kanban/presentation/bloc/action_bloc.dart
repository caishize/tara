import 'package:flutter_bloc/flutter_bloc.dart';

import '../../domain/repositories/insight_feed_repository.dart';
import '../widgets/action_type_registry.dart';
import 'action_event.dart';
import 'action_state.dart';

/// Dedicated BLoC for the PendingAction confirmation lifecycle.
///
/// Owns the full create -> confirm/reject flow independently from
/// [InsightFeedBloc]. The two blocs communicate through a shared
/// [InsightFeedRepository], never via direct BLoC-to-BLoC calls.
///
/// State machine:
/// ```
/// ActionIdle
///   -> RequestAction
///     -> (direct tier) ActionConfirmed -> ActionIdle
///     -> (inline/full) ActionCreating -> ActionPendingConfirm
///       -> ConfirmAction -> ActionConfirming -> ActionConfirmed -> ActionIdle
///       -> RejectAction -> ActionIdle
///     -> (error) ActionFailed
///   -> ResetAction -> ActionIdle
/// ```
class ActionBloc extends Bloc<ActionEvent, ActionState> {
  final InsightFeedRepository _repository;

  /// Duration before auto-resetting from [ActionConfirmed] to [ActionIdle].
  static const _confirmResetDelay = Duration(seconds: 2);

  ActionBloc({required InsightFeedRepository repository})
      : _repository = repository,
        super(const ActionIdle()) {
    on<RequestAction>(_onRequestAction);
    on<ConfirmAction>(_onConfirmAction);
    on<RejectAction>(_onRejectAction);
    on<ResetAction>(_onResetAction);
  }

  /// Initiate an action.
  ///
  /// For `direct` tier actions (e.g. open_event_detail), emits
  /// [ActionConfirmed] immediately without any backend call.
  /// For `inline`/`full` tier actions, creates a PendingAction via the
  /// repository, then waits for user confirmation.
  Future<void> _onRequestAction(
    RequestAction event,
    Emitter<ActionState> emit,
  ) async {
    final actionDef = ActionTypeRegistry.lookup(event.actionType);

    // Direct actions need no backend PendingAction flow
    if (actionDef.confirmationTier == ConfirmationTier.direct) {
      emit(ActionConfirmed(insightId: event.insightId));
      await _scheduleResetToIdle(event.insightId);
      return;
    }

    emit(ActionCreating(insightId: event.insightId));

    final result = await _repository.executeInsightAction(
      insightId: event.insightId,
      actionType: event.actionType,
      actionData: event.actionData,
    );

    if (isClosed) return;

    result.fold(
      (failure) {
        emit(ActionFailed(
          insightId: event.insightId,
          message: failure.message,
        ));
      },
      (pendingAction) {
        // PLAN-008: Pass confirmation tier so UI can differentiate
        // inline (lightweight) vs full (bottom sheet) confirmation.
        final tierName = actionDef.confirmationTier == ConfirmationTier.inline
            ? 'inline'
            : 'full';
        emit(ActionPendingConfirm(
          insightId: event.insightId,
          pendingAction: pendingAction,
          confirmationTier: tierName,
        ));
      },
    );
  }

  /// User confirmed the pending action.
  ///
  /// Calls the confirm endpoint, transitions through [ActionConfirming] ->
  /// [ActionConfirmed], then auto-resets to [ActionIdle] after a short delay.
  Future<void> _onConfirmAction(
    ConfirmAction event,
    Emitter<ActionState> emit,
  ) async {
    final currentState = state;
    final insightId = _insightIdFromState(currentState);
    if (insightId == null) return;

    emit(ActionConfirming(
      insightId: insightId,
      actionId: event.actionId,
    ));

    final result = await _repository.confirmAction(
      actionId: event.actionId,
    );

    if (isClosed) return;

    result.fold(
      (failure) {
        emit(ActionFailed(
          insightId: insightId,
          message: failure.message,
        ));
      },
      (_) async {
        emit(ActionConfirmed(insightId: insightId));
        await _scheduleResetToIdle(insightId);
      },
    );
  }

  /// User rejected the pending action — reset to idle.
  void _onRejectAction(
    RejectAction event,
    Emitter<ActionState> emit,
  ) {
    emit(const ActionIdle());
  }

  /// Explicit reset — clear all action state.
  void _onResetAction(
    ResetAction event,
    Emitter<ActionState> emit,
  ) {
    emit(const ActionIdle());
  }

  /// After a successful confirmation, wait [_confirmResetDelay] then
  /// transition back to [ActionIdle] — but only if the state hasn't
  /// been changed by another event in the meantime.
  Future<void> _scheduleResetToIdle(String insightId) async {
    await Future.delayed(_confirmResetDelay);

    if (isClosed) return;

    final currentState = state;
    if (currentState is ActionConfirmed &&
        currentState.insightId == insightId) {
      add(const ResetAction());
    }
  }

  /// Extract the [insightId] from the current state, if available.
  String? _insightIdFromState(ActionState actionState) {
    return switch (actionState) {
      ActionCreating(:final insightId) => insightId,
      ActionPendingConfirm(:final insightId) => insightId,
      ActionConfirming(:final insightId) => insightId,
      ActionConfirmed(:final insightId) => insightId,
      ActionFailed(:final insightId) => insightId,
      ActionIdle() => null,
    };
  }
}
