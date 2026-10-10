import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';

/// Section header with emoji, title, and item count badge.
class InsightSectionHeader extends StatelessWidget {
  final String title;
  final String emoji;
  final int count;

  const InsightSectionHeader({
    super.key,
    required this.title,
    required this.emoji,
    required this.count,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 8),
      child: Row(
        children: [
          Text(emoji, style: const TextStyle(fontSize: 18)),
          const SizedBox(width: 8),
          Text(
            title,
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(width: 8),
          if (count > 0)
            Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: AppColors.bgMuted,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(
                '$count',
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textSecondary,
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// "Show more" expand button for collapsed list sections.
class InsightShowMoreButton extends StatelessWidget {
  final VoidCallback onTap;
  final int remaining;

  const InsightShowMoreButton({
    super.key,
    required this.onTap,
    required this.remaining,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(vertical: 10),
          decoration: BoxDecoration(
            color: AppColors.bgMuted,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: AppColors.borderSubtle),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(
                Icons.expand_more,
                size: 16,
                color: AppColors.textSecondary,
              ),
              const SizedBox(width: 6),
              Text(
                '\u67E5\u770B\u66F4\u591A ($remaining)',
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Empty state shown when no insights are available.
///
/// Features a subtle pulse animation on the AI icon, contextual messaging
/// for new vs returning users, and a pull-to-refresh hint.
class InsightEmptyState extends StatefulWidget {
  /// When true, shows onboarding-style "AI is learning" messaging.
  /// When false, shows "All caught up!" messaging for returning users.
  final bool isNewUser;

  const InsightEmptyState({super.key, this.isNewUser = true});

  @override
  State<InsightEmptyState> createState() => _InsightEmptyStateState();
}

class _InsightEmptyStateState extends State<InsightEmptyState>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulseController;
  late final Animation<double> _pulseAnimation;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2000),
    )..repeat(reverse: true);
    _pulseAnimation = Tween<double>(begin: 0.6, end: 1.0).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final ext = Theme.of(context).extension<AppColorsExtension>();

    final headline = widget.isNewUser
        ? 'AI \u6B63\u5728\u4E86\u89E3\u4F60\u7684\u5BB6\u5EAD'
        : '\u5168\u90E8\u5904\u7406\u5B8C\u6BD5!';
    final subtitle = widget.isNewUser
        ? '\u7A0D\u540E\u8FD9\u91CC\u5C06\u51FA\u73B0\u4E13\u5C5E\u4E8E\u4F60\u7684\u667A\u80FD\u6D1E\u5BDF'
        : '\u6682\u65E0\u65B0\u7684\u6D1E\u5BDF\uFF0C\u4F11\u606F\u4E00\u4E0B\u5427';

    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            AnimatedBuilder(
              animation: _pulseAnimation,
              builder: (context, child) {
                return Opacity(
                  opacity: _pulseAnimation.value,
                  child: child,
                );
              },
              child: Icon(
                widget.isNewUser ? Icons.auto_awesome : Icons.check_circle_outline,
                size: 56,
                color: ext?.insightDefault ?? AppColors.accentGreen,
              ),
            ),
            const SizedBox(height: 16),
            Text(
              headline,
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w600,
                color: colorScheme.onSurface,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 6),
            Text(
              subtitle,
              style: TextStyle(
                fontSize: 14,
                color: colorScheme.onSurfaceVariant,
                height: 1.4,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  Icons.arrow_downward,
                  size: 14,
                  color: ext?.textHint ?? AppColors.textHint,
                ),
                const SizedBox(width: 4),
                Text(
                  '\u4E0B\u62C9\u5237\u65B0',
                  style: TextStyle(
                    fontSize: 12,
                    color: ext?.textHint ?? AppColors.textHint,
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

/// Error state with retry button.
class InsightErrorState extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const InsightErrorState({
    super.key,
    required this.message,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, size: 48, color: AppColors.error),
          const SizedBox(height: 12),
          Text(
            message,
            style: const TextStyle(
              fontSize: 14,
              color: AppColors.textSecondary,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          TextButton(
            onPressed: onRetry,
            child: const Text('\u91CD\u8BD5'),
          ),
        ],
      ),
    );
  }
}
