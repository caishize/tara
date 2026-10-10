import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../data/models/insight_feed_models.dart';
import '../../data/models/future_view_models.dart';
import 'dismiss_bottom_sheet.dart';

/// Expandable AI suggestion card for V4 future timeline view.
///
/// Collapsed: shows tag + title + action + dismiss buttons.
/// Expanded: shows description + sub-items, each with confirm/dismiss.
///
/// Actions follow the design doc 3-tier model:
/// - 采纳 (adopt): trip-related insights → adopt to trip
/// - 了解 (acknowledge): non-trip insights → 90-day snooze
/// - 忽略 (dismiss): tap = quick dismiss, long-press = 3-tier options
class FutureSuggestionCard extends StatefulWidget {
  final FutureViewSuggestionModel suggestion;
  final VoidCallback? onAction;
  final VoidCallback? onDismiss;
  final void Function(String feedbackType)? onDismissWithFeedback;
  final void Function(FutureViewSuggestionSubItem subItem)? onSubItemConfirm;
  final void Function(FutureViewSuggestionSubItem subItem)? onSubItemDismiss;
  final VoidCallback? onNavigateTrip;
  final void Function(ActionOptionModel actionOption)? onActionOptionTap;

  const FutureSuggestionCard({
    super.key,
    required this.suggestion,
    this.onAction,
    this.onDismiss,
    this.onDismissWithFeedback,
    this.onSubItemConfirm,
    this.onSubItemDismiss,
    this.onNavigateTrip,
    this.onActionOptionTap,
  });

  @override
  State<FutureSuggestionCard> createState() => _FutureSuggestionCardState();
}

class _FutureSuggestionCardState extends State<FutureSuggestionCard>
    with SingleTickerProviderStateMixin {
  bool _expanded = false;
  late final AnimationController _animController;
  late final Animation<double> _expandAnimation;

  // Track dismissed sub-items locally
  final Set<String> _dismissedSubItemIds = {};

  FutureViewSuggestionModel get suggestion => widget.suggestion;

  bool get _hasExpandableContent =>
      suggestion.description.isNotEmpty || suggestion.hasSubItems;

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
    if (!_hasExpandableContent) return;
    setState(() {
      _expanded = !_expanded;
      if (_expanded) {
        _animController.forward();
      } else {
        _animController.reverse();
      }
    });
  }

  void _handleDismissLongPress() async {
    final feedbackType = await DismissBottomSheet.show(context);
    if (!mounted) return;
    if (feedbackType != null) {
      widget.onDismissWithFeedback?.call(feedbackType);
    }
  }

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
          _buildHeader(),
          SizeTransition(
            sizeFactor: _expandAnimation,
            axisAlignment: -1.0,
            child: _buildExpandedContent(),
          ),
        ],
      ),
    );
  }

  Widget _buildTagRow(Color tagColor) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          suggestion.tagEmoji,
          style: const TextStyle(fontSize: 12, height: 1.2),
        ),
        const SizedBox(width: 4),
        Text(
          suggestion.tagLabel,
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: tagColor,
            height: 1.2,
          ),
        ),
        if (suggestion.hasSubItems) ...[
          const SizedBox(width: 6),
          Container(
            padding: const EdgeInsets.symmetric(
                horizontal: 6, vertical: 1),
            decoration: BoxDecoration(
              color: tagColor.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              '${_visibleSubItems.length}项',
              style: TextStyle(
                fontSize: 9,
                fontWeight: FontWeight.w600,
                color: tagColor,
                height: 1.2,
              ),
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildHeader() {
    final tagColor = suggestion.tagColorValue;
    // Use vertical layout when there are many action options to prevent overflow
    final useVerticalLayout = suggestion.actionOptions.length > 2;

    return GestureDetector(
      onTap: _toggleExpand,
      behavior: HitTestBehavior.opaque,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: useVerticalLayout
            ? _buildVerticalHeader(tagColor)
            : _buildHorizontalHeader(tagColor),
      ),
    );
  }

  /// Standard layout: tag + title on left, action buttons on right.
  Widget _buildHorizontalHeader(Color tagColor) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildTagRow(tagColor),
              if (suggestion.title.isNotEmpty) ...[
                const SizedBox(height: 4),
                Text(
                  suggestion.title,
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
        _buildHeaderActions(),
      ],
    );
  }

  /// Vertical layout for many action options: title on top, wrapped buttons below.
  Widget _buildVerticalHeader(Color tagColor) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildTagRow(tagColor),
        if (suggestion.title.isNotEmpty) ...[
          const SizedBox(height: 4),
          Text(
            suggestion.title,
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
        const SizedBox(height: 8),
        _buildWrappedActionChips(),
      ],
    );
  }

  Widget _buildHeaderActions() {
    if (suggestion.hasActionOptions) {
      return _buildActionOptionChips();
    }
    return _buildDefaultActions();
  }

  /// Renders action chips from backend `action_options`, plus a dismiss button.
  /// Used in horizontal layout (≤2 action options).
  Widget _buildActionOptionChips() {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (int i = 0; i < suggestion.actionOptions.length; i++) ...[
          if (i > 0) const SizedBox(width: 4),
          _buildSmallButton(
            label: suggestion.actionOptions[i].label,
            color: suggestion.actionOptions[i].actionType == 'dismiss'
                ? AppColors.textTertiary
                : AppColors.accentGreen,
            bgColor: suggestion.actionOptions[i].actionType == 'dismiss'
                ? const Color(0xFFEDECEA)
                : AppColors.accentGreen.withValues(alpha: 0.08),
            onTap: () =>
                widget.onActionOptionTap?.call(suggestion.actionOptions[i]),
          ),
        ],
        // Always show dismiss if none of the action_options is a dismiss type
        if (!suggestion.actionOptions.any((o) => o.actionType == 'dismiss')) ...[
          const SizedBox(width: 4),
          GestureDetector(
            onLongPress: _handleDismissLongPress,
            child: _buildSmallButton(
              label: '忽略',
              color: AppColors.textTertiary,
              bgColor: const Color(0xFFEDECEA),
              onTap: widget.onDismiss,
            ),
          ),
        ],
        // Expand arrow for expandable cards
        if (_hasExpandableContent) ...[
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
      ],
    );
  }

  /// Wrapped action chips for vertical layout (>2 action options).
  /// Uses Wrap to prevent horizontal overflow.
  Widget _buildWrappedActionChips() {
    return Wrap(
      spacing: 4,
      runSpacing: 6,
      crossAxisAlignment: WrapCrossAlignment.center,
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
            onTap: () => widget.onActionOptionTap?.call(option),
          ),
        if (!suggestion.actionOptions.any((o) => o.actionType == 'dismiss'))
          GestureDetector(
            onLongPress: _handleDismissLongPress,
            child: _buildSmallButton(
              label: '忽略',
              color: AppColors.textTertiary,
              bgColor: const Color(0xFFEDECEA),
              onTap: widget.onDismiss,
            ),
          ),
        if (_hasExpandableContent)
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
    );
  }

  /// Default two-button layout: primary action + dismiss.
  Widget _buildDefaultActions() {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        // Primary action: 采纳 (trip) / 了解 (non-trip)
        _buildSmallButton(
          label: suggestion.actionLabel.isNotEmpty
              ? suggestion.actionLabel
              : (suggestion.hasTripContext ? '采纳' : '了解'),
          color: AppColors.accentGreen,
          bgColor: AppColors.accentGreen.withValues(alpha: 0.08),
          onTap: widget.onAction,
        ),
        const SizedBox(width: 6),
        // Dismiss: tap = quick dismiss, long-press = 3-tier options
        GestureDetector(
          onLongPress: _handleDismissLongPress,
          child: _buildSmallButton(
            label: '忽略',
            color: AppColors.textTertiary,
            bgColor: const Color(0xFFEDECEA),
            onTap: widget.onDismiss,
          ),
        ),
        // Expand arrow for expandable cards
        if (_hasExpandableContent) ...[
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
      ],
    );
  }

  List<FutureViewSuggestionSubItem> get _visibleSubItems =>
      suggestion.subItems
          .where((s) => !_dismissedSubItemIds.contains(s.id))
          .toList();

  Widget _buildExpandedContent() {
    final visibleSubs = _visibleSubItems;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Description
        if (suggestion.description.isNotEmpty)
          Container(
            padding: const EdgeInsets.fromLTRB(14, 0, 14, 10),
            child: Text(
              suggestion.description,
              style: const TextStyle(
                fontSize: 13,
                color: AppColors.textSecondary,
                height: 1.4,
              ),
            ),
          ),

        // Trip navigation link
        if (suggestion.hasTripContext)
          GestureDetector(
            onTap: widget.onNavigateTrip,
            child: Container(
              padding: const EdgeInsets.fromLTRB(14, 0, 14, 10),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.open_in_new, size: 12,
                      color: AppColors.accentGreen.withValues(alpha: 0.8)),
                  const SizedBox(width: 4),
                  Text(
                    '查看行程',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      color: AppColors.accentGreen.withValues(alpha: 0.8),
                      height: 1.2,
                    ),
                  ),
                ],
              ),
            ),
          ),

        // Sub-items
        if (visibleSubs.isNotEmpty) ...[
          const Divider(height: 1, color: AppColors.divider),
          ...visibleSubs.map(_buildSubItemRow),
        ],
      ],
    );
  }

  Widget _buildSubItemRow(FutureViewSuggestionSubItem subItem) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: const BoxDecoration(
        border: Border(
          bottom: BorderSide(color: AppColors.divider, width: 0.5),
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(
              color: suggestion.tagColorValue.withValues(alpha: 0.5),
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  subItem.label,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                    color: AppColors.textPrimary,
                    height: 1.3,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                if (subItem.description.isNotEmpty) ...[
                  const SizedBox(height: 2),
                  Text(
                    subItem.description,
                    style: const TextStyle(
                      fontSize: 11,
                      color: AppColors.textTertiary,
                      height: 1.3,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(width: 8),
          _buildSmallButton(
            label: '采纳',
            color: AppColors.accentGreen,
            bgColor: AppColors.accentGreen.withValues(alpha: 0.08),
            onTap: () => widget.onSubItemConfirm?.call(subItem),
          ),
          const SizedBox(width: 4),
          GestureDetector(
            onTap: () {
              setState(() {
                _dismissedSubItemIds.add(subItem.id);
              });
              widget.onSubItemDismiss?.call(subItem);
            },
            child: const Icon(
              Icons.close,
              size: 16,
              color: AppColors.textTertiary,
            ),
          ),
        ],
      ),
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
