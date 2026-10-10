import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_dimensions.dart';
import '../../data/models/insight_feed_models.dart';
import '../utils/insight_style.dart';
import 'insight_card_parts.dart';

/// Compact, single-line insight card for embedding in other views.
///
/// Designed for trip detail, member detail, and future view pages.
/// Unlike the full [InsightCard], this widget has no bloc dependency
/// and delegates all interaction to callbacks.
///
/// Visual layout:
/// ```
/// ┌─────────────────────────────────────────────────┐
/// │ 🔵 [icon] Title text here              2小时前  │
/// │    Content preview text (max 2 lines)...        │
/// │    [Action Chip]  [Action Chip]                 │
/// └─────────────────────────────────────────────────┘
/// ```
class InsightCardCompact extends StatelessWidget {
  final InsightFeedItemModel insight;
  final VoidCallback? onTap;
  final Future<bool> Function()? onDismiss;
  final void Function(String actionType, Map<String, dynamic>? payload)?
      onActionTap;
  final bool showActions;
  final int maxContentLines;

  const InsightCardCompact({
    super.key,
    required this.insight,
    this.onTap,
    this.onDismiss,
    this.onActionTap,
    this.showActions = true,
    this.maxContentLines = 2,
  });

  @override
  Widget build(BuildContext context) {
    final style = InsightStyle.resolve(
      context: context,
      insightType: insight.insightType,
      urgency: insight.urgency,
      visualWeight: insight.visualWeight,
      priority: insight.priority,
    );

    final card = GestureDetector(
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surface,
          borderRadius: BorderRadius.circular(AppDimensions.cardRadiusSmall),
          border: Border.all(
            color: Theme.of(context).colorScheme.outlineVariant,
            width: AppDimensions.cardBorderWidth,
          ),
          boxShadow: AppColors.cardShadow,
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _AccentBar(color: style.accentColor),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 8,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _HeaderRow(insight: insight, style: style),
                    const SizedBox(height: 3),
                    _ContentPreview(
                      content: insight.content,
                      maxLines: maxContentLines,
                    ),
                    if (showActions && insight.actionOptions.isNotEmpty) ...[
                      const SizedBox(height: 6),
                      _ActionChipsRow(
                        options: insight.actionOptions,
                        accentColor: style.accentColor,
                        onActionTap: onActionTap,
                        actionData: insight.actionData,
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );

    if (onDismiss == null) return card;

    return Dismissible(
      key: Key('insight-compact-${insight.id}'),
      direction: DismissDirection.endToStart,
      confirmDismiss: (_) async {
        if (onDismiss != null) {
          return await onDismiss!();
        }
        return true;
      },
      background: const InsightCardDismissBackground(),
      child: card,
    );
  }
}

// =============================================================================
// Left accent bar (4px, colored by insight type)
// =============================================================================

class _AccentBar extends StatelessWidget {
  final Color color;

  const _AccentBar({required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: AppDimensions.accentBarWidth,
      constraints: const BoxConstraints(minHeight: 48),
      decoration: BoxDecoration(
        color: color,
        borderRadius: const BorderRadius.horizontal(
          left: Radius.circular(AppDimensions.cardRadiusSmall),
        ),
      ),
    );
  }
}

// =============================================================================
// Header row: type icon + title + timestamp
// =============================================================================

class _HeaderRow extends StatelessWidget {
  final InsightFeedItemModel insight;
  final InsightStyle style;

  const _HeaderRow({required this.insight, required this.style});

  @override
  Widget build(BuildContext context) {
    final ext = Theme.of(context).extension<AppColorsExtension>();
    final colorScheme = Theme.of(context).colorScheme;

    return Row(
      children: [
        Text(style.emoji, style: const TextStyle(fontSize: 13)),
        const SizedBox(width: 4),
        Expanded(
          child: Text(
            insight.title,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: colorScheme.onSurface,
              height: 1.3,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ),
        if (insight.createdAt != null) ...[
          const SizedBox(width: 6),
          Text(
            InsightCardParts.formatTimestamp(insight.createdAt!),
            style: TextStyle(
              fontSize: 11,
              color: ext?.textTertiary ?? AppColors.textTertiary,
            ),
          ),
        ],
      ],
    );
  }
}

// =============================================================================
// Content preview
// =============================================================================

class _ContentPreview extends StatelessWidget {
  final String content;
  final int maxLines;

  const _ContentPreview({required this.content, required this.maxLines});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Padding(
      // Align with title text (after emoji + spacing)
      padding: const EdgeInsets.only(left: 17),
      child: Text(
        content,
        style: TextStyle(
          fontSize: 13,
          color: colorScheme.onSurfaceVariant,
          height: 1.4,
        ),
        maxLines: maxLines,
        overflow: TextOverflow.ellipsis,
      ),
    );
  }
}

// =============================================================================
// Action chips row
// =============================================================================

class _ActionChipsRow extends StatelessWidget {
  final List<ActionOptionModel> options;
  final Color accentColor;
  final void Function(String actionType, Map<String, dynamic>? payload)?
      onActionTap;
  final Map<String, dynamic>? actionData;

  const _ActionChipsRow({
    required this.options,
    required this.accentColor,
    this.onActionTap,
    this.actionData,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 17),
      child: Wrap(
        spacing: 6,
        runSpacing: 4,
        children: options.map((option) {
          return GestureDetector(
            onTap: () => onActionTap?.call(
              option.actionType,
              option.payload.isNotEmpty ? option.payload : actionData,
            ),
            child: Container(
              height: 28,
              padding: const EdgeInsets.symmetric(horizontal: 10),
              decoration: BoxDecoration(
                color: accentColor.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(14),
                border: Border.all(
                  color: accentColor.withValues(alpha: 0.25),
                ),
              ),
              child: Center(
                child: Text(
                  option.label,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                    color: accentColor,
                  ),
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }
}
