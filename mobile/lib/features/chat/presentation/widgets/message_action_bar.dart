import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';

/// Configuration for what actions to show in the action bar.
class MessageActionBarConfig {
  final bool showCopy;
  final bool showRegenerate;
  final bool showFeedback;
  final bool showEdit;
  final VoidCallback? onCopy;
  final VoidCallback? onRegenerate;
  final void Function(bool isLike, String? reason)? onFeedback;
  final VoidCallback? onEdit;

  /// Initial feedback state from persisted data: true=positive, false=negative, null=none.
  final bool? initialFeedback;

  const MessageActionBarConfig({
    this.showCopy = true,
    this.showRegenerate = false,
    this.showFeedback = false,
    this.showEdit = false,
    this.onCopy,
    this.onRegenerate,
    this.onFeedback,
    this.onEdit,
    this.initialFeedback,
  });
}

/// Unified action bar for all message bubbles (ChatGPT-style).
///
/// Replaces the duplicated `_buildActionButtonsRow` / `_buildActionButton`
/// pattern found in ChatBubble, TripBubble, EventCardBubble,
/// PendingActionBubble, and GiftRecommendationBubble.
class MessageActionBar extends StatefulWidget {
  final DateTime createdAt;
  final MessageActionBarConfig config;
  final bool showActionsHighlighted;

  const MessageActionBar({
    super.key,
    required this.createdAt,
    required this.config,
    this.showActionsHighlighted = false,
  });

  @override
  State<MessageActionBar> createState() => _MessageActionBarState();
}

class _MessageActionBarState extends State<MessageActionBar> {
  bool? _feedbackState;
  bool _initialized = false;

  @override
  void didUpdateWidget(MessageActionBar oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Sync feedback state when the external prop changes (e.g. history load)
    if (widget.config.initialFeedback != oldWidget.config.initialFeedback) {
      _feedbackState = widget.config.initialFeedback;
    }
  }

  @override
  Widget build(BuildContext context) {
    // Initialize from config on first build
    if (!_initialized) {
      _feedbackState = widget.config.initialFeedback;
      _initialized = true;
    }

    final config = widget.config;

    return AnimatedSize(
      duration: const Duration(milliseconds: 200),
      child: AnimatedOpacity(
        opacity: widget.showActionsHighlighted ? 1.0 : 0.6,
        duration: const Duration(milliseconds: 200),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              _formatTime(widget.createdAt),
              style: AppTextStyles.overline.copyWith(
                color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
              ),
            ),
            const SizedBox(width: 8),
            if (config.showCopy)
              _ActionButton(
                icon: Icons.copy_outlined,
                tooltip: '\u590d\u5236',
                onTap: config.onCopy,
              ),
            if (config.showRegenerate)
              _ActionButton(
                icon: Icons.refresh_outlined,
                tooltip: '\u91cd\u65b0\u751f\u6210',
                onTap: config.onRegenerate != null
                    ? () {
                        HapticFeedback.lightImpact();
                        config.onRegenerate!();
                      }
                    : null,
              ),
            if (config.showFeedback) ...[
              _ActionButton(
                icon: _feedbackState == true
                    ? Icons.thumb_up
                    : Icons.thumb_up_outlined,
                tooltip: '\u6709\u5e2e\u52a9',
                isActive: _feedbackState == true,
                onTap: () => _handleFeedback(true),
              ),
              _ActionButton(
                icon: _feedbackState == false
                    ? Icons.thumb_down
                    : Icons.thumb_down_outlined,
                tooltip: '\u6ca1\u5e2e\u52a9',
                isActive: _feedbackState == false,
                onTap: () => _handleFeedback(false),
              ),
            ],
            if (config.showEdit)
              _ActionButton(
                icon: Icons.edit_outlined,
                tooltip: '\u7f16\u8f91',
                onTap: config.onEdit,
              ),
          ],
        ),
      ),
    );
  }

  void _handleFeedback(bool isLike) {
    HapticFeedback.lightImpact();

    if (isLike) {
      // Toggle positive feedback
      final newState = _feedbackState == true ? null : true;
      setState(() => _feedbackState = newState);
      if (newState == true) {
        widget.config.onFeedback?.call(true, null);
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Row(
            children: [
              Icon(Icons.thumb_up, color: Colors.white, size: 18),
              SizedBox(width: 8),
              Text('\u611f\u8c22\u60a8\u7684\u53cd\u9988!'),
            ],
          ),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          duration: const Duration(seconds: 2),
          margin: const EdgeInsets.all(16),
        ),
      );
    } else {
      // Negative feedback: show reason picker bottom sheet
      _showNegativeFeedbackSheet();
    }
  }

  void _showNegativeFeedbackSheet() {
    const reasons = [
      '\u4e0d\u51c6\u786e',
      '\u4e0d\u662f\u6211\u60f3\u8981\u7684',
      '\u4fe1\u606f\u8fc7\u65f6',
      '\u5176\u4ed6',
    ];

    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surface,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                margin: const EdgeInsets.only(top: 12),
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: Theme.of(context).dividerColor,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(16),
                child: Text(
                  '\u8bf7\u9009\u62e9\u539f\u56e0',
                  style: AppTextStyles.subtitle1.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              ...reasons.map((reason) => ListTile(
                leading: const Icon(Icons.radio_button_unchecked, size: 20),
                title: Text(reason),
                onTap: () {
                  Navigator.pop(ctx);
                  setState(() => _feedbackState = false);
                  widget.config.onFeedback?.call(false, reason);
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: const Row(
                        children: [
                          Icon(Icons.thumb_down, color: Colors.white, size: 18),
                          SizedBox(width: 8),
                          Text('\u6211\u4f1a\u52aa\u529b\u6539\u8fdb'),
                        ],
                      ),
                      behavior: SnackBarBehavior.floating,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      duration: const Duration(seconds: 2),
                      margin: const EdgeInsets.all(16),
                    ),
                  );
                },
              )),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }

  String _formatTime(DateTime time) {
    final hour = time.hour.toString().padLeft(2, '0');
    final minute = time.minute.toString().padLeft(2, '0');
    return '$hour:$minute';
  }
}

/// Single icon button used in the action bar.
class _ActionButton extends StatelessWidget {
  final IconData icon;
  final String tooltip;
  final VoidCallback? onTap;
  final bool isActive;

  const _ActionButton({
    required this.icon,
    required this.tooltip,
    this.onTap,
    this.isActive = false,
  });

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(4),
        child: Padding(
          padding: const EdgeInsets.all(6),
          child: Builder(
            builder: (context) {
              final theme = Theme.of(context);
              final ext = theme.extension<AppColorsExtension>()!;
              return Icon(
                icon,
                size: 16,
                color: isActive
                    ? theme.colorScheme.primary
                    : (onTap != null ? ext.textTertiary : theme.dividerColor),
              );
            },
          ),
        ),
      ),
    );
  }
}
