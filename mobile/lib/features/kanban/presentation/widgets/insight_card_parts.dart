import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../../app/theme/app_colors.dart';
import '../../data/models/insight_feed_models.dart';
import '../bloc/insight_feed_state.dart';
import 'action_type_registry.dart';

/// Utility helpers and sub-widgets used exclusively by [InsightCard].
///
/// Extracted into a separate file to keep insight_card.dart under the
/// 400-line limit while preserving full cohesion.

// =============================================================================
// Stateless utility class (pure functions only)
// =============================================================================

abstract final class InsightCardParts {
  static String formatTimestamp(DateTime dt) {
    final now = DateTime.now();
    final diff = now.difference(dt);
    if (diff.inMinutes < 1) return '刚刚';
    if (diff.inHours < 1) return '${diff.inMinutes}分钟前';
    if (diff.inDays < 1) return '${diff.inHours}小时前';
    if (diff.inDays == 1) return '昨天';
    return '${dt.month}/${dt.day}';
  }

  /// Formats a future event time as relative duration (e.g., "2小时后").
  static String formatRelativeTime(DateTime dt) {
    final now = DateTime.now();
    final diff = dt.difference(now);
    if (diff.isNegative) return formatTimestamp(dt);
    if (diff.inMinutes < 60) return '${diff.inMinutes}分钟后';
    if (diff.inHours < 24) return '${diff.inHours}小时后';
    if (diff.inDays == 1) return '明天';
    if (diff.inDays < 7) return '${diff.inDays}天后';
    return '${dt.month}/${dt.day}';
  }
}

// =============================================================================
// Dismiss background
// =============================================================================

class InsightCardDismissBackground extends StatelessWidget {
  const InsightCardDismissBackground({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      alignment: Alignment.centerRight,
      padding: const EdgeInsets.only(right: 20),
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.error.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(16),
      ),
      child: const Icon(Icons.delete_outline, color: AppColors.error),
    );
  }
}

// =============================================================================
// Left accent bar
// =============================================================================

class InsightAccentBar extends StatelessWidget {
  final Color accentColor;

  const InsightAccentBar({super.key, required this.accentColor});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 4,
      constraints: const BoxConstraints(minHeight: 72),
      decoration: BoxDecoration(
        color: accentColor,
        borderRadius: const BorderRadius.horizontal(
          left: Radius.circular(16),
        ),
      ),
    );
  }
}

// =============================================================================
// Urgency dot
// =============================================================================

class InsightUrgencyDot extends StatelessWidget {
  final String urgency;

  const InsightUrgencyDot({super.key, required this.urgency});

  @override
  Widget build(BuildContext context) {
    final ext = Theme.of(context).extension<AppColorsExtension>();
    final color = switch (urgency) {
      'urgent' => ext?.insightUrgent ?? const Color(0xFFD32F2F),
      'important' => ext?.insightImportant ?? const Color(0xFFE6A000),
      _ => ext?.insightDefault ?? const Color(0xFF2D7A46),
    };
    return Container(
      width: 8,
      height: 8,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
    );
  }
}

// =============================================================================
// Priority badge (shown when priority <= 2)
// =============================================================================

class InsightPriorityBadge extends StatelessWidget {
  final int priority;

  const InsightPriorityBadge({super.key, required this.priority});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: AppColors.error.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        'P$priority',
        style: const TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w700,
          color: AppColors.error,
        ),
      ),
    );
  }
}

// =============================================================================
// Action chip spec — maps actionType string to icon + label
// =============================================================================

class ActionChipSpec {
  final IconData icon;
  final String label;

  const ActionChipSpec({required this.icon, required this.label});

  /// Maps a backend action-type token to icon + label via [ActionTypeRegistry].
  factory ActionChipSpec.from(String actionType) {
    final def = ActionTypeRegistry.lookup(actionType);
    return ActionChipSpec(icon: def.icon, label: def.label);
  }

  /// Maps an [ActionOptionModel] to icon + label.
  factory ActionChipSpec.fromOption(ActionOptionModel option) {
    final def = ActionTypeRegistry.lookup(option.actionType);
    final label = option.label.isNotEmpty ? option.label : def.label;
    return ActionChipSpec(icon: def.icon, label: label);
  }

  /// Maps an [ActionOptionModel] to icon + context-enriched label.
  ///
  /// For navigational actions (open_event_detail, open_trip_detail),
  /// rewrites the label to include the entity name from the insight.
  /// E.g., "打开事件详情" → "查看「北京出差」" (capped at 8 chars for entity).
  factory ActionChipSpec.fromOptionWithContext(
    ActionOptionModel option,
    InsightFeedItemModel insight,
  ) {
    final def = ActionTypeRegistry.lookup(option.actionType);
    final baseLabel = option.label.isNotEmpty ? option.label : def.label;

    // Enrich navigational action labels with entity name
    final enriched = _enrichNavigationalLabel(option.actionType, insight);
    final label = enriched ?? baseLabel;

    return ActionChipSpec(icon: def.icon, label: label);
  }

  static String? _enrichNavigationalLabel(
    String actionType,
    InsightFeedItemModel insight,
  ) {
    if (actionType == 'open_event_detail' && insight.relatedEvents.isNotEmpty) {
      final title = insight.relatedEvents.first.title;
      if (title.isNotEmpty) {
        final truncated = title.length > 8 ? '${title.substring(0, 7)}\u2026' : title;
        return '\u67E5\u770B\u300C$truncated\u300D';
      }
    }
    if (actionType == 'open_trip_detail' && insight.relatedTrip != null) {
      final title = insight.relatedTrip!.name;
      if (title.isNotEmpty) {
        final truncated = title.length > 8 ? '${title.substring(0, 7)}\u2026' : title;
        return '\u67E5\u770B\u300C$truncated\u300D';
      }
    }
    return null;
  }
}

// =============================================================================
// Action chip button — handles idle / pending / confirmed / failed lifecycle
// PLAN-005: Haptic feedback + enhanced visual "processing" state
// =============================================================================

class InsightActionChipButton extends StatefulWidget {
  final ActionChipSpec spec;
  final InsightActionState actionState;
  final Color accentColor;
  final VoidCallback? onTap;

  const InsightActionChipButton({
    super.key,
    required this.spec,
    required this.actionState,
    required this.accentColor,
    this.onTap,
  });

  @override
  State<InsightActionChipButton> createState() =>
      _InsightActionChipButtonState();
}

class _InsightActionChipButtonState extends State<InsightActionChipButton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulseController;
  late final Animation<double> _pulseAnimation;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    );
    _pulseAnimation = Tween<double>(begin: 0.3, end: 0.6).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void didUpdateWidget(covariant InsightActionChipButton oldWidget) {
    super.didUpdateWidget(oldWidget);
    final isPending = widget.actionState == InsightActionState.pending;
    if (isPending && !_pulseController.isAnimating) {
      _pulseController.repeat(reverse: true);
    } else if (!isPending && _pulseController.isAnimating) {
      _pulseController.stop();
      _pulseController.reset();
    }
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isConfirmed = widget.actionState == InsightActionState.confirmed;
    final isPending = widget.actionState == InsightActionState.pending;
    final isPendingConfirm =
        widget.actionState == InsightActionState.pendingConfirm;
    final isFailed = widget.actionState == InsightActionState.failed;
    final isBusy = isPending || isConfirmed || isPendingConfirm;

    final bgColor = isFailed
        ? AppColors.error.withValues(alpha: 0.1)
        : isConfirmed
            ? AppColors.success.withValues(alpha: 0.12)
            : isPendingConfirm
                ? AppColors.warning.withValues(alpha: 0.12)
                : widget.accentColor.withValues(alpha: 0.12);

    final fgColor = isFailed
        ? AppColors.error
        : isConfirmed
            ? AppColors.success
            : isPendingConfirm
                ? AppColors.warning
                : widget.accentColor;

    // PLAN-005: Label changes to "处理中..." during pending state
    final label = isConfirmed
        ? '\u5DF2\u5B89\u6392'
        : isPending
            ? '\u5904\u7406\u4E2D...'
            : isPendingConfirm
                ? '\u5F85\u786E\u8BA4'
                : isFailed
                    ? '\u5931\u8D25\uFF0C\u70B9\u51FB\u91CD\u8BD5'
                    : widget.spec.label;

    return Semantics(
      label: '${widget.spec.label} action',
      button: true,
      enabled: !isBusy,
      child: GestureDetector(
        onTap: isBusy
            ? null
            : () {
                // PLAN-005: Haptic feedback on tap
                HapticFeedback.lightImpact();
                widget.onTap?.call();
              },
        child: AnimatedBuilder(
          animation: _pulseAnimation,
          builder: (context, child) {
            final borderAlpha = isPending ? _pulseAnimation.value : 0.3;
            return Container(
              height: 36,
              padding: const EdgeInsets.symmetric(horizontal: 14),
              decoration: BoxDecoration(
                color: bgColor,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(
                  color: fgColor.withValues(alpha: borderAlpha),
                  width: isPending ? 1.5 : 1.0,
                ),
              ),
              child: child,
            );
          },
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (isPending)
                SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(
                    strokeWidth: 1.5,
                    valueColor: AlwaysStoppedAnimation<Color>(fgColor),
                  ),
                )
              else if (isConfirmed)
                Icon(Icons.check, size: 14, color: fgColor)
              else if (isPendingConfirm)
                Icon(Icons.pending_outlined, size: 14, color: fgColor)
              else if (isFailed)
                Icon(Icons.error_outline, size: 14, color: fgColor)
              else
                Icon(widget.spec.icon, size: 14, color: fgColor),
              const SizedBox(width: 6),
              Text(
                label,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: fgColor,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
