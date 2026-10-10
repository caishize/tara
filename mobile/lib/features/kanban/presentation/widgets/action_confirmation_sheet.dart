import 'dart:async';

import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_dimensions.dart';
import '../../data/models/insight_feed_models.dart';
import 'action_type_registry.dart';

/// Bottom sheet that displays a PendingAction for user confirmation.
///
/// Shows the action type, title, description, detail items, and expiry
/// countdown when the pending action has an expiration time.
/// User can confirm (execute) or cancel (reject) the action.
class ActionConfirmationSheet extends StatefulWidget {
  final PendingActionResponseModel pendingAction;
  final VoidCallback onConfirm;
  final VoidCallback onReject;

  const ActionConfirmationSheet({
    super.key,
    required this.pendingAction,
    required this.onConfirm,
    required this.onReject,
  });

  /// Show this sheet as a modal bottom sheet.
  static Future<bool?> show({
    required BuildContext context,
    required PendingActionResponseModel pendingAction,
    required VoidCallback onConfirm,
    required VoidCallback onReject,
  }) {
    return showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(AppDimensions.cardRadius),
        ),
      ),
      builder: (_) => ActionConfirmationSheet(
        pendingAction: pendingAction,
        onConfirm: onConfirm,
        onReject: onReject,
      ),
    );
  }

  @override
  State<ActionConfirmationSheet> createState() =>
      _ActionConfirmationSheetState();
}

class _ActionConfirmationSheetState extends State<ActionConfirmationSheet> {
  Timer? _expiryTimer;
  bool _isExpired = false;
  Duration _remaining = Duration.zero;

  @override
  void initState() {
    super.initState();
    _isExpired = widget.pendingAction.isExpired;
    _startExpiryTimer();
  }

  void _startExpiryTimer() {
    final expiresAtStr = widget.pendingAction.expiresAt;
    if (expiresAtStr == null || _isExpired) return;

    final expiresAt = DateTime.tryParse(expiresAtStr);
    if (expiresAt == null) return;

    _updateRemaining(expiresAt);
    _expiryTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      _updateRemaining(expiresAt);
    });
  }

  void _updateRemaining(DateTime expiresAt) {
    final now = DateTime.now().toUtc();
    final diff = expiresAt.difference(now);
    if (diff.isNegative) {
      setState(() {
        _isExpired = true;
        _remaining = Duration.zero;
      });
      _expiryTimer?.cancel();
    } else {
      setState(() => _remaining = diff);
    }
  }

  @override
  void dispose() {
    _expiryTimer?.cancel();
    super.dispose();
  }

  String _formatRemaining() {
    if (_remaining.inHours > 0) {
      return '${_remaining.inHours}\u5C0F\u65F6${_remaining.inMinutes.remainder(60)}\u5206\u949F';
    }
    if (_remaining.inMinutes > 0) {
      return '${_remaining.inMinutes}\u5206${_remaining.inSeconds.remainder(60)}\u79D2';
    }
    return '${_remaining.inSeconds}\u79D2';
  }

  @override
  Widget build(BuildContext context) {
    final actionDef = ActionTypeRegistry.lookup(widget.pendingAction.actionType);
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          AppDimensions.cardPaddingH,
          AppDimensions.spacing16,
          AppDimensions.cardPaddingH,
          AppDimensions.spacing24,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Drag handle
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: AppColors.divider,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: AppDimensions.spacing16),

            // Icon + title row
            Row(
              children: [
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: colorScheme.primary.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(AppDimensions.chipRadius),
                  ),
                  child: Icon(
                    actionDef.icon,
                    color: colorScheme.primary,
                    size: AppDimensions.iconSizeLarge,
                  ),
                ),
                const SizedBox(width: AppDimensions.spacing12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        widget.pendingAction.displayTitle.isNotEmpty
                            ? widget.pendingAction.displayTitle
                            : actionDef.label,
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      if (widget.pendingAction.description.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 2),
                          child: Text(
                            widget.pendingAction.description,
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: AppColors.textSecondary,
                            ),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                    ],
                  ),
                ),
              ],
            ),

            // Detail items
            if (widget.pendingAction.displayDetails.isNotEmpty) ...[
              const SizedBox(height: AppDimensions.spacing16),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(AppDimensions.cardPadding),
                decoration: BoxDecoration(
                  color: AppColors.inputBackground,
                  borderRadius: BorderRadius.circular(AppDimensions.chipRadius),
                ),
                child: Column(
                  children: [
                    for (final detail in widget.pendingAction.displayDetails)
                      Padding(
                        padding: const EdgeInsets.symmetric(
                          vertical: AppDimensions.spacing2,
                        ),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            SizedBox(
                              width: 80,
                              child: Text(
                                detail.label,
                                style: theme.textTheme.bodySmall?.copyWith(
                                  color: AppColors.textTertiary,
                                ),
                              ),
                            ),
                            Expanded(
                              child: Text(
                                detail.value,
                                style: theme.textTheme.bodySmall?.copyWith(
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            ],

            // Expiry display
            if (widget.pendingAction.expiresAt != null) ...[
              const SizedBox(height: AppDimensions.spacing12),
              Row(
                children: [
                  Icon(
                    _isExpired ? Icons.timer_off_outlined : Icons.timer_outlined,
                    size: 14,
                    color: _isExpired ? colorScheme.error : AppColors.textTertiary,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    _isExpired
                        ? '\u8BE5\u64CD\u4F5C\u5DF2\u8FC7\u671F'
                        : '\u5269\u4F59 ${_formatRemaining()}',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: _isExpired
                          ? colorScheme.error
                          : AppColors.textTertiary,
                    ),
                  ),
                ],
              ),
            ],

            const SizedBox(height: AppDimensions.spacing24),

            // Action buttons
            Row(
              children: [
                Expanded(
                  child: Semantics(
                    label: 'Cancel action',
                    button: true,
                    child: OutlinedButton(
                      onPressed: () {
                        widget.onReject();
                        Navigator.of(context).pop(false);
                      },
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        side: const BorderSide(color: AppColors.divider),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(
                            AppDimensions.chipRadius,
                          ),
                        ),
                      ),
                      child: const Text('\u53D6\u6D88'),
                    ),
                  ),
                ),
                const SizedBox(width: AppDimensions.spacing12),
                Expanded(
                  flex: 2,
                  child: Semantics(
                    label: 'Confirm ${actionDef.label}',
                    button: true,
                    child: FilledButton(
                      onPressed: _isExpired
                          ? null
                          : () {
                              widget.onConfirm();
                              Navigator.of(context).pop(true);
                            },
                      style: FilledButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(
                            AppDimensions.chipRadius,
                          ),
                        ),
                      ),
                      child: Text('\u786E\u8BA4${actionDef.label}'),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
