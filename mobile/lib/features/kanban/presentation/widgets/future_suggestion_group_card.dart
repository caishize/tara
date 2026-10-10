import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../data/models/insight_feed_models.dart';
import '../../data/models/future_view_models.dart';

/// Accordion card for a group of related AI suggestions.
///
/// Collapsed: shows representative tag + group label + "N条建议" badge + chevron.
/// Expanded: each child suggestion as its own row with independent action chips.
class FutureSuggestionGroupCard extends StatefulWidget {
  final SuggestionGroup group;
  final void Function(FutureViewSuggestionModel suggestion) onAction;
  final void Function(FutureViewSuggestionModel suggestion) onDismiss;
  final void Function(FutureViewSuggestionModel suggestion, String feedbackType)
      onDismissWithFeedback;
  final void Function(
          FutureViewSuggestionModel suggestion, ActionOptionModel option)
      onActionOptionTap;
  final VoidCallback? onDismissGroup;

  const FutureSuggestionGroupCard({
    super.key,
    required this.group,
    required this.onAction,
    required this.onDismiss,
    required this.onDismissWithFeedback,
    required this.onActionOptionTap,
    this.onDismissGroup,
  });

  @override
  State<FutureSuggestionGroupCard> createState() =>
      _FutureSuggestionGroupCardState();
}

class _FutureSuggestionGroupCardState extends State<FutureSuggestionGroupCard>
    with SingleTickerProviderStateMixin {
  bool _expanded = false;
  late final AnimationController _animController;
  late final Animation<double> _expandAnimation;

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      duration: const Duration(milliseconds: 200),
      vsync: this,
    );
    _expandAnimation = CurvedAnimation(
      parent: _animController,
      curve: Curves.easeInOut,
    );
  }

  @override
  void dispose() {
    _animController.dispose();
    super.dispose();
  }

  void _toggleExpand() {
    setState(() {
      _expanded = !_expanded;
      if (_expanded) {
        _animController.forward();
      } else {
        _animController.reverse();
      }
    });
  }

  FutureViewSuggestionModel get _representative =>
      widget.group.suggestions.first;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.divider, width: 1),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _buildCollapsedHeader(),
          SizeTransition(
            sizeFactor: _expandAnimation,
            axisAlignment: -1.0,
            child: _buildExpandedChildren(),
          ),
        ],
      ),
    );
  }

  Widget _buildCollapsedHeader() {
    final rep = _representative;
    final tagColor = rep.tagColorValue;

    return GestureDetector(
      onTap: _toggleExpand,
      behavior: HitTestBehavior.opaque,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Tag row with count badge
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        rep.tagEmoji,
                        style: const TextStyle(fontSize: 12, height: 1.2),
                      ),
                      const SizedBox(width: 4),
                      Text(
                        rep.tagLabel,
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: tagColor,
                          height: 1.2,
                        ),
                      ),
                      const SizedBox(width: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 6, vertical: 1),
                        decoration: BoxDecoration(
                          color: tagColor.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          '${widget.group.suggestions.length}条建议',
                          style: TextStyle(
                            fontSize: 9,
                            fontWeight: FontWeight.w600,
                            color: tagColor,
                            height: 1.2,
                          ),
                        ),
                      ),
                    ],
                  ),
                  // Group label
                  if (widget.group.groupLabel.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(
                      widget.group.groupLabel,
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w500,
                        color: AppColors.textPrimary,
                        height: 1.3,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(width: 8),
            // Group-level dismiss
            if (widget.onDismissGroup != null)
              _buildSmallButton(
                label: '全部忽略',
                color: AppColors.textTertiary,
                bgColor: const Color(0xFFEDECEA),
                onTap: widget.onDismissGroup,
              ),
            const SizedBox(width: 4),
            AnimatedRotation(
              turns: _expanded ? 0.5 : 0.0,
              duration: const Duration(milliseconds: 200),
              child: const Icon(
                Icons.keyboard_arrow_down,
                size: 18,
                color: AppColors.textTertiary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildExpandedChildren() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Divider(height: 1, color: AppColors.divider),
        for (int i = 0; i < widget.group.suggestions.length; i++)
          _buildChildRow(widget.group.suggestions[i],
              isLast: i == widget.group.suggestions.length - 1),
      ],
    );
  }

  Widget _buildChildRow(FutureViewSuggestionModel suggestion,
      {required bool isLast}) {
    final tagColor = suggestion.tagColorValue;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: isLast
          ? null
          : const BoxDecoration(
              border: Border(
                bottom: BorderSide(color: AppColors.divider, width: 0.5),
              ),
            ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Title
          Text(
            suggestion.title,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: AppColors.textPrimary,
              height: 1.3,
            ),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          // Description (if any)
          if (suggestion.description.isNotEmpty) ...[
            const SizedBox(height: 2),
            Text(
              suggestion.description,
              style: const TextStyle(
                fontSize: 11,
                color: AppColors.textTertiary,
                height: 1.3,
              ),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ],
          const SizedBox(height: 6),
          // Action chips for this child
          _buildChildActions(suggestion, tagColor),
        ],
      ),
    );
  }

  Widget _buildChildActions(
      FutureViewSuggestionModel suggestion, Color tagColor) {
    if (suggestion.hasActionOptions) {
      return Wrap(
        spacing: 4,
        runSpacing: 4,
        children: [
          for (final option in suggestion.actionOptions)
            _buildSmallButton(
              label: option.label,
              color: option.actionType == 'dismiss'
                  ? AppColors.textTertiary
                  : AppColors.accentGreen,
              bgColor: option.actionType == 'dismiss'
                  ? const Color(0xFFEDECEA)
                  : AppColors.accentGreen.withValues(alpha: 0.08),
              onTap: () => widget.onActionOptionTap(suggestion, option),
            ),
          if (!suggestion.actionOptions.any((o) => o.actionType == 'dismiss'))
            _buildSmallButton(
              label: '忽略',
              color: AppColors.textTertiary,
              bgColor: const Color(0xFFEDECEA),
              onTap: () => widget.onDismiss(suggestion),
            ),
        ],
      );
    }

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        _buildSmallButton(
          label: suggestion.actionLabel.isNotEmpty
              ? suggestion.actionLabel
              : (suggestion.hasTripContext ? '采纳' : '了解'),
          color: AppColors.accentGreen,
          bgColor: AppColors.accentGreen.withValues(alpha: 0.08),
          onTap: () => widget.onAction(suggestion),
        ),
        const SizedBox(width: 4),
        _buildSmallButton(
          label: '忽略',
          color: AppColors.textTertiary,
          bgColor: const Color(0xFFEDECEA),
          onTap: () => widget.onDismiss(suggestion),
        ),
      ],
    );
  }

  Widget _buildSmallButton({
    required String label,
    required Color color,
    required Color bgColor,
    VoidCallback? onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: bgColor,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: color,
            height: 1.2,
          ),
        ),
      ),
    );
  }
}
