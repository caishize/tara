import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_dimensions.dart';
import '../../data/models/insight_feed_models.dart';
import '../bloc/insight_feed_state.dart';
import '../utils/insight_style.dart';
import '../utils/insight_title_enricher.dart';
import 'context_hint_chip.dart';
import 'insight_card_context.dart';
import 'insight_card_parts.dart';

/// Full-width AI insight card with 3-tier display system.
///
/// Displays AI insights with tier-driven element visibility:
/// - Spotlight: full chrome, gradient, shadow, context hint, 1 CTA
/// - Standard: accent bar, subtle gradient, 1 CTA
/// - Whisper: minimal chrome, flat surface, no CTA in collapsed state
///
/// Gestures: tap=expand, swipe-left=dismiss, long-press=defer.
class InsightCard extends StatefulWidget {
  final InsightFeedItemModel insight;
  final bool isExpanded;
  final InsightActionState actionState;
  final VoidCallback? onTap;
  final VoidCallback? onDismiss;
  final VoidCallback? onDefer;
  final void Function(String actionType, Map<String, dynamic>? actionData)?
      onActionTap;
  final void Function(String eventId)? onEventTap;
  final void Function(String memberId)? onMemberTap;
  final VoidCallback? onShowDetail;

  const InsightCard({
    super.key,
    required this.insight,
    this.isExpanded = false,
    this.actionState = InsightActionState.idle,
    this.onTap,
    this.onDismiss,
    this.onDefer,
    this.onActionTap,
    this.onEventTap,
    this.onMemberTap,
    this.onShowDetail,
  });

  @override
  State<InsightCard> createState() => _InsightCardState();
}

class _InsightCardState extends State<InsightCard> {
  bool _pressed = false;
  bool _tapActive = false;

  InsightFeedItemModel get insight => widget.insight;
  bool get isExpanded => widget.isExpanded;
  InsightActionState get actionState => widget.actionState;

  @override
  Widget build(BuildContext context) {
    final style = InsightStyle.resolve(
      context: context,
      insightType: insight.insightType,
      urgency: insight.urgency,
      visualWeight: insight.visualWeight,
      priority: insight.priority,
    );

    final isWhisper = style.cardTier == InsightCardTier.whisper;
    final isSpotlight = style.cardTier == InsightCardTier.spotlight;

    // Tier-driven shadow
    final accentShadow = style.elevation > 0
        ? BoxShadow(
            color: style.accentColor.withValues(alpha: 0.15),
            blurRadius: style.elevation * 3,
            offset: Offset(0, style.elevation),
          )
        : null;
    final shadow = isWhisper
        ? <BoxShadow>[]
        : [
            ...isSpotlight ? AppColors.cardShadowMedium : AppColors.cardShadow,
            if (accentShadow != null) accentShadow,
          ];

    // Tier-driven border color
    final borderColor = isWhisper
        ? Theme.of(context).colorScheme.outlineVariant
        : style.borderColor;

    // Tier-driven accent bar
    final accentBar = isWhisper
        ? _WhisperAccentDot(color: style.accentColor)
        : InsightAccentBar(accentColor: style.accentColor);

    return Semantics(
      label: '${style.label}: ${insight.title}',
      button: true,
      child: Dismissible(
        key: Key('insight-${insight.id}'),
        direction: DismissDirection.endToStart,
        confirmDismiss: (direction) async {
          widget.onDismiss?.call();
          return true;
        },
        background: const InsightCardDismissBackground(),
        child: GestureDetector(
          onTapDown: (_) {
            _tapActive = true;
            // Delay press feedback to disambiguate from scroll intent
            Future.delayed(const Duration(milliseconds: 150), () {
              if (mounted && _tapActive) {
                HapticFeedback.selectionClick();
                setState(() => _pressed = true);
              }
            });
          },
          onTapUp: (_) {
            _tapActive = false;
            setState(() => _pressed = false);
          },
          onTapCancel: () {
            _tapActive = false;
            setState(() => _pressed = false);
          },
          onTap: widget.onTap,
          onLongPress: () {
            HapticFeedback.heavyImpact();
            widget.onDefer?.call();
          },
          child: AnimatedScale(
            scale: _pressed ? 0.97 : 1.0,
            duration: AppDimensions.animPressFeedback,
            curve: Curves.easeOut,
            child: Container(
              margin: EdgeInsets.symmetric(
                horizontal: AppDimensions.cardMarginH,
                vertical: style.verticalMargin,
              ),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: style.bgGradient,
                ),
                borderRadius: BorderRadius.circular(AppDimensions.cardRadius),
                border: Border.all(color: borderColor, width: style.borderWidth),
                boxShadow: shadow,
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  accentBar,
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.all(AppDimensions.cardPadding),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _buildHeader(context, style),
                          const SizedBox(height: 6),
                          _buildTitle(context, style),
                          const SizedBox(height: 4),
                          _buildContentPreview(context, style),
                          // Collapsed state: context hint for Spotlight only
                          if (style.showContextHint && !isExpanded && insight.contextHint != null) ...[
                            const SizedBox(height: 6),
                            ContextHintChip(hint: insight.contextHint!),
                          ],
                          // Expand/collapse with AnimatedSize (replaces AnimatedCrossFade)
                          ClipRect(
                            child: AnimatedSize(
                              duration: AppDimensions.animExpandDuration,
                              curve: Curves.easeOutCubic,
                              clipBehavior: Clip.hardEdge,
                              child: isExpanded
                                  ? _buildExpandedDetail(context, style)
                                  : const SizedBox.shrink(),
                            ),
                          ),
                          // Action chips: visible for Spotlight/Standard only
                          if (style.showActionChips &&
                              (insight.actionOptions.isNotEmpty ||
                                  insight.actionType != null)) ...[
                            const SizedBox(height: 10),
                            _buildActionChips(style),
                          ],
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context, InsightStyle style) {
    final ext = Theme.of(context).extension<AppColorsExtension>();

    // Whisper tier: timestamp only, no full header
    if (!style.showFullHeader) {
      return Row(
        mainAxisAlignment: MainAxisAlignment.end,
        children: [
          if (insight.createdAt != null)
            Text(
              InsightCardParts.formatTimestamp(insight.createdAt!),
              style: TextStyle(
                fontSize: 11,
                color: ext?.textTertiary ?? AppColors.textTertiary,
              ),
            ),
        ],
      );
    }

    // Entity-first header: when members are linked, show avatar + name
    final hasMember = insight.relatedMembers.isNotEmpty;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        if (hasMember) ...[
          CompactMemberAvatar(member: insight.relatedMembers.first),
          const SizedBox(width: 6),
          Flexible(
            child: Text(
              '${insight.relatedMembers.first.name} \u00B7 ${style.label}',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: style.accentColor,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ] else ...[
          InsightUrgencyDot(urgency: insight.urgency),
          const SizedBox(width: 6),
          Text(style.emoji, style: const TextStyle(fontSize: 13)),
          const SizedBox(width: 4),
          Text(
            style.label,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: style.accentColor,
            ),
          ),
        ],
        const Spacer(),
        if (insight.createdAt != null)
          Text(
            InsightCardParts.formatTimestamp(insight.createdAt!),
            style: TextStyle(
              fontSize: 11,
              color: ext?.textTertiary ?? AppColors.textTertiary,
            ),
          ),
        if (insight.priority <= 2) ...[
          const SizedBox(width: 6),
          InsightPriorityBadge(priority: insight.priority),
        ],
      ],
    );
  }

  Widget _buildTitle(BuildContext context, InsightStyle style) {
    final colorScheme = Theme.of(context).colorScheme;
    final enrichedTitle = InsightTitleEnricher.enrich(insight);

    return Text(
      enrichedTitle,
      style: TextStyle(
        fontSize: style.titleFontSize,
        fontWeight: style.titleFontWeight,
        color: colorScheme.onSurface,
        height: 1.3,
      ),
      maxLines: style.titleMaxLines,
      overflow: TextOverflow.ellipsis,
    );
  }

  Widget _buildContentPreview(BuildContext context, InsightStyle style) {
    final colorScheme = Theme.of(context).colorScheme;
    final maxLines = isExpanded ? null : style.contentMaxLines;

    return Text(
      insight.content,
      style: TextStyle(
        fontSize: 14,
        fontWeight: FontWeight.w400,
        color: colorScheme.onSurfaceVariant,
        height: 1.45,
      ),
      maxLines: maxLines,
      overflow: maxLines == null ? TextOverflow.visible : TextOverflow.ellipsis,
    );
  }

  Widget _buildExpandedDetail(BuildContext context, InsightStyle style) {
    final associations = _extractAssociations();
    final prepSuggestions = _extractPreparationSuggestions();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 10),
        // Show related events/members in expanded state only
        if (insight.relatedEvents.isNotEmpty) ...[
          _buildRelatedEvents(),
          const SizedBox(height: 8),
        ],
        if (insight.relatedMembers.isNotEmpty) ...[
          _buildRelatedMembers(),
          const SizedBox(height: 8),
        ],
        if (associations.isNotEmpty) ...[
          _buildAssociationList(context, associations, style),
          const SizedBox(height: 8),
        ],
        if (prepSuggestions.isNotEmpty) ...[
          _buildPreparationList(context, prepSuggestions, style),
          const SizedBox(height: 8),
        ],
        if (insight.relatedTrip != null) ...[
          InsightTripCard(trip: insight.relatedTrip!),
          const SizedBox(height: 8),
        ],
        if (insight.sourceContext != null) ...[
          InsightSourceContextChip(sourceContext: insight.sourceContext!),
          const SizedBox(height: 8),
        ],
        if (insight.contextHint != null) ...[
          ContextHintChip(hint: insight.contextHint!),
          const SizedBox(height: 8),
        ],
        if (widget.onShowDetail != null) ...[
          _buildMoreOptionsButton(context),
          const SizedBox(height: 8),
        ],
      ],
    );
  }

  Widget _buildMoreOptionsButton(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Align(
      alignment: Alignment.centerRight,
      child: GestureDetector(
        onTap: widget.onShowDetail,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 2),
          child: Icon(
            Icons.more_horiz,
            size: 20,
            color: colorScheme.onSurfaceVariant,
          ),
        ),
      ),
    );
  }

  List<Map<String, dynamic>> _extractAssociations() {
    final data = insight.actionData;
    if (data == null) return [];
    final raw = data['associations'];
    if (raw is! List) return [];
    return raw.whereType<Map<String, dynamic>>().toList();
  }

  List<String> _extractPreparationSuggestions() {
    final data = insight.actionData;
    if (data == null) return [];
    final raw = data['preparation_suggestions'];
    if (raw is! List) return [];
    return raw.whereType<String>().where((s) => s.trim().isNotEmpty).toList();
  }

  Widget _buildRelatedEvents() {
    return Wrap(
      spacing: 6,
      runSpacing: 4,
      children: insight.relatedEvents.map((event) {
        return GestureDetector(
          onTap: () => widget.onEventTap?.call(event.id),
          child: InsightEventChip(event: event),
        );
      }).toList(),
    );
  }

  Widget _buildRelatedMembers() {
    return Row(
      children: insight.relatedMembers.take(5).map((member) {
        return Padding(
          padding: const EdgeInsets.only(right: 10),
          child: GestureDetector(
            onTap: () => widget.onMemberTap?.call(member.id),
            child: InsightMemberAvatar(member: member),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildAssociationList(
    BuildContext context,
    List<Map<String, dynamic>> associations,
    InsightStyle style,
  ) {
    final colorScheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '\u5173\u8054\u4E8B\u9879',
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 4),
        ...associations.map((assoc) {
          final title = assoc['title'] as String? ?? '';
          final reason = assoc['reason'] as String? ?? '';
          return Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.link, size: 14, color: style.accentColor),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    reason.isNotEmpty ? '$title ($reason)' : title,
                    style: TextStyle(
                      fontSize: 13,
                      color: colorScheme.onSurface,
                      height: 1.4,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          );
        }),
      ],
    );
  }

  Widget _buildPreparationList(
    BuildContext context,
    List<String> suggestions,
    InsightStyle style,
  ) {
    final colorScheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '\u51C6\u5907\u4E8B\u9879',
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 4),
        ...suggestions.map((item) {
          return Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  Icons.check_circle_outline,
                  size: 14,
                  color: style.accentColor,
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    item,
                    style: TextStyle(
                      fontSize: 13,
                      color: colorScheme.onSurface,
                      height: 1.4,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          );
        }),
      ],
    );
  }

  Widget _buildActionChips(InsightStyle style) {
    final chips = insight.actionOptions.isNotEmpty
        ? insight.actionOptions
        : (insight.actionType != null
            ? [ActionOptionModel(actionType: insight.actionType!, label: insight.actionType!)]
            : <ActionOptionModel>[]);

    if (chips.isEmpty) return const SizedBox.shrink();

    // Show only first CTA in collapsed state
    final visibleChips = isExpanded ? chips : chips.take(1).toList();

    final contextSummary = !isExpanded
        ? InsightActionContext.buildSummary(insight)
        : null;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: 8,
          runSpacing: 6,
          children: visibleChips.map((option) {
            final spec = ActionChipSpec.fromOptionWithContext(option, insight);
            return InsightActionChipButton(
              spec: spec,
              actionState: actionState,
              accentColor: style.accentColor,
              onTap: () => widget.onActionTap?.call(
                option.actionType, insight.actionData,
              ),
            );
          }).toList(),
        ),
        if (contextSummary != null) ...[
          const SizedBox(height: 4),
          Text(
            contextSummary,
            style: TextStyle(
              fontSize: 12,
              color: style.chipTextColor,
              fontWeight: FontWeight.w400,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ],
    );
  }
}

/// Whisper tier accent: small dot instead of full-height bar.
class _WhisperAccentDot extends StatelessWidget {
  final Color color;
  const _WhisperAccentDot({required this.color});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 6, top: 16),
      child: Container(
        width: 6,
        height: 6,
        decoration: BoxDecoration(
          color: color,
          shape: BoxShape.circle,
        ),
      ),
    );
  }
}
