import 'package:flutter/material.dart';

/// Confirmation tier for action types.
///
/// Determines how much user confirmation is needed before execution.
enum ConfirmationTier {
  /// No confirmation needed — navigational or purely informational.
  direct,

  /// Lightweight inline confirmation (e.g., "Send greeting to Mom?").
  inline,

  /// Full bottom-sheet confirmation with details (financial, irreversible).
  full,
}

/// Describes the visual and behavioral properties of a single action type.
///
/// Immutable — use [ActionTypeRegistry.lookup] to obtain instances.
class ActionTypeDef {
  final IconData icon;
  final String label;
  final ConfirmationTier confirmationTier;

  const ActionTypeDef({
    required this.icon,
    required this.label,
    required this.confirmationTier,
  });
}

/// Central registry mapping backend action-type tokens to UI definitions.
///
/// Covers all 12 [ActionType] values defined in
/// `backend/src/modules/conversation/pending_action.py`.
///
/// Usage:
/// ```dart
/// final def = ActionTypeRegistry.lookup('suggest_meeting');
/// print(def.label); // '安排见面'
/// ```
abstract final class ActionTypeRegistry {
  static const _registry = <String, ActionTypeDef>{
    // ── Suggest actions (reversible, inline confirmation) ──
    'suggest_meeting': ActionTypeDef(
      icon: Icons.calendar_today,
      label: '安排见面',
      confirmationTier: ConfirmationTier.inline,
    ),
    'suggest_greeting': ActionTypeDef(
      icon: Icons.message_outlined,
      label: '发送祝福',
      confirmationTier: ConfirmationTier.inline,
    ),
    'suggest_gift': ActionTypeDef(
      icon: Icons.card_giftcard,
      label: '挑选礼物',
      confirmationTier: ConfirmationTier.inline,
    ),
    'suggest_defer': ActionTypeDef(
      icon: Icons.snooze,
      label: '稍后处理',
      confirmationTier: ConfirmationTier.inline,
    ),

    // ── Navigational (no side effect) ──
    'open_event_detail': ActionTypeDef(
      icon: Icons.info_outline,
      label: '查看详情',
      confirmationTier: ConfirmationTier.direct,
    ),
    'open_trip_detail': ActionTypeDef(
      icon: Icons.flight_takeoff,
      label: '查看行程详情',
      confirmationTier: ConfirmationTier.direct,
    ),

    'set_reminder': ActionTypeDef(
      icon: Icons.alarm,
      label: '设置提醒',
      confirmationTier: ConfirmationTier.inline,
    ),

    // ── Event management (medium risk) ──
    'create_event': ActionTypeDef(
      icon: Icons.event,
      label: '创建日程',
      confirmationTier: ConfirmationTier.inline,
    ),
    'reschedule_event': ActionTypeDef(
      icon: Icons.update,
      label: '重新安排',
      confirmationTier: ConfirmationTier.inline,
    ),
    'send_message': ActionTypeDef(
      icon: Icons.send,
      label: '发送消息',
      confirmationTier: ConfirmationTier.inline,
    ),

    // ── High-risk actions (irreversible / financial) ──
    'purchase': ActionTypeDef(
      icon: Icons.shopping_cart,
      label: '购买',
      confirmationTier: ConfirmationTier.full,
    ),
    'book_ticket': ActionTypeDef(
      icon: Icons.airplane_ticket,
      label: '预订车票',
      confirmationTier: ConfirmationTier.full,
    ),
    'cancel_booking': ActionTypeDef(
      icon: Icons.cancel,
      label: '取消预订',
      confirmationTier: ConfirmationTier.full,
    ),
    'delete_event': ActionTypeDef(
      icon: Icons.delete_outline,
      label: '删除日程',
      confirmationTier: ConfirmationTier.full,
    ),
    'transfer_money': ActionTypeDef(
      icon: Icons.account_balance_wallet,
      label: '转账',
      confirmationTier: ConfirmationTier.full,
    ),
  };

  /// Default fallback for unknown action types.
  static const _fallback = ActionTypeDef(
    icon: Icons.bolt_outlined,
    label: '立即处理',
    confirmationTier: ConfirmationTier.inline,
  );

  /// Look up the [ActionTypeDef] for the given backend action-type token.
  ///
  /// Returns a sensible fallback if the token is not recognised.
  static ActionTypeDef lookup(String actionType) {
    return _registry[actionType] ?? _fallback;
  }

  /// Whether [actionType] requires user confirmation before execution.
  static bool requiresConfirmation(String actionType) {
    return lookup(actionType).confirmationTier != ConfirmationTier.direct;
  }

  /// All known action type tokens.
  static Iterable<String> get knownTypes => _registry.keys;
}
