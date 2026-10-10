import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../data/models/insight_feed_models.dart';
import 'insight_card_compact.dart';
import 'insight_detail_sheet.dart';

/// A reusable section that displays a list of compact insight cards with a header.
///
/// Designed for embedding in trip detail, member detail, and other pages.
/// Shows a configurable number of insights initially with an expand/collapse
/// toggle to reveal the rest.
///
/// Visual layout:
/// ```
/// ┌─────────────────────────────────────────────────┐
/// │ ✨ AI 洞察  (3)                                  │
/// ├─────────────────────────────────────────────────┤
/// │ [InsightCardCompact 1]                          │
/// │ [InsightCardCompact 2]                          │
/// │ [InsightCardCompact 3]                          │
/// │                                                 │
/// │         查看更多 (2) ▼                           │
/// └─────────────────────────────────────────────────┘
/// ```
class InsightSection extends StatefulWidget {
  final List<InsightFeedItemModel> insights;
  final String title;
  final IconData? icon;
  final int maxVisible;
  final void Function(InsightFeedItemModel)? onInsightTap;
  final Future<bool> Function(InsightFeedItemModel)? onInsightDismiss;
  final void Function(
    InsightFeedItemModel insight,
    String actionType,
    Map<String, dynamic>? payload,
  )? onInsightActionTap;
  final bool showActions;
  final String? emptyMessage;

  const InsightSection({
    super.key,
    required this.insights,
    this.title = 'AI \u6D1E\u5BDF',
    this.icon,
    this.maxVisible = 3,
    this.onInsightTap,
    this.onInsightDismiss,
    this.onInsightActionTap,
    this.showActions = true,
    this.emptyMessage,
  });

  @override
  State<InsightSection> createState() => _InsightSectionState();
}

class _InsightSectionState extends State<InsightSection>
    with SingleTickerProviderStateMixin {
  bool _expanded = false;

  bool get _hasOverflow => widget.insights.length > widget.maxVisible;

  int get _hiddenCount => _hasOverflow
      ? widget.insights.length - widget.maxVisible
      : 0;

  List<InsightFeedItemModel> get _visibleInsights => _expanded
      ? widget.insights
      : widget.insights.take(widget.maxVisible).toList();

  @override
  Widget build(BuildContext context) {
    // Empty state: hide entirely or show message
    if (widget.insights.isEmpty) {
      if (widget.emptyMessage == null) return const SizedBox.shrink();
      return _buildEmptyState(context);
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SectionHeader(
          title: widget.title,
          icon: widget.icon ?? Icons.auto_awesome,
          count: widget.insights.length,
        ),
        const SizedBox(height: 8),
        // Insight cards with animated expand/collapse
        AnimatedSize(
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOutCubic,
          clipBehavior: Clip.hardEdge,
          alignment: Alignment.topCenter,
          child: Column(
            children: _visibleInsights.map((insight) {
              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: InsightCardCompact(
                  insight: insight,
                  showActions: widget.showActions,
                  onTap: () => _handleInsightTap(context, insight),
                  onDismiss: widget.onInsightDismiss != null
                      ? () => widget.onInsightDismiss!(insight)
                      : null,
                  onActionTap: widget.onInsightActionTap != null
                      ? (actionType, payload) => widget.onInsightActionTap!(
                            insight,
                            actionType,
                            payload,
                          )
                      : null,
                ),
              );
            }).toList(),
          ),
        ),
        // Expand/collapse toggle
        if (_hasOverflow) _buildExpandToggle(context),
      ],
    );
  }

  void _handleInsightTap(BuildContext context, InsightFeedItemModel insight) {
    if (widget.onInsightTap != null) {
      widget.onInsightTap!(insight);
      return;
    }

    // Default behavior: open detail sheet
    InsightDetailSheet.show(
      context,
      insight: insight,
      onFeedback: (_) {},
      onActionTap: widget.onInsightActionTap != null
          ? (actionType, actionData) => widget.onInsightActionTap!(
                insight,
                actionType,
                actionData,
              )
          : null,
    );
  }

  Widget _buildExpandToggle(BuildContext context) {
    final ext = Theme.of(context).extension<AppColorsExtension>();
    final toggleColor = ext?.insightDefault ?? AppColors.accentGreen;

    return GestureDetector(
      onTap: () => setState(() => _expanded = !_expanded),
      behavior: HitTestBehavior.opaque,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              _expanded
                  ? '\u6536\u8D77'
                  : '\u67E5\u770B\u66F4\u591A ($_hiddenCount)',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w500,
                color: toggleColor,
              ),
            ),
            const SizedBox(width: 4),
            AnimatedRotation(
              turns: _expanded ? 0.5 : 0.0,
              duration: const Duration(milliseconds: 200),
              child: Icon(
                Icons.keyboard_arrow_down,
                size: 18,
                color: toggleColor,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    final ext = Theme.of(context).extension<AppColorsExtension>();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SectionHeader(
          title: widget.title,
          icon: widget.icon ?? Icons.auto_awesome,
          count: 0,
        ),
        const SizedBox(height: 12),
        Center(
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Text(
              widget.emptyMessage!,
              style: TextStyle(
                fontSize: 13,
                color: ext?.textTertiary ?? AppColors.textTertiary,
              ),
            ),
          ),
        ),
      ],
    );
  }
}

// =============================================================================
// Section header: icon + title + count badge
// =============================================================================

class _SectionHeader extends StatelessWidget {
  final String title;
  final IconData icon;
  final int count;

  const _SectionHeader({
    required this.title,
    required this.icon,
    required this.count,
  });

  @override
  Widget build(BuildContext context) {
    final ext = Theme.of(context).extension<AppColorsExtension>();
    final colorScheme = Theme.of(context).colorScheme;
    final accentColor = ext?.insightDefault ?? AppColors.accentGreen;

    return Row(
      children: [
        Icon(icon, size: 18, color: accentColor),
        const SizedBox(width: 6),
        Text(
          title,
          style: TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.w700,
            color: colorScheme.onSurface,
          ),
        ),
        if (count > 0) ...[
          const SizedBox(width: 6),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
            decoration: BoxDecoration(
              color: accentColor.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              '$count',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: accentColor,
              ),
            ),
          ),
        ],
      ],
    );
  }
}
