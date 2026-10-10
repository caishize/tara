import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_dimensions.dart';
import '../../data/models/insight_feed_models.dart';
import '../../data/models/kanban_models.dart';
import 'event_mini_card.dart';

/// Fallback group icon mapping for each semantic group.
/// Used when the server does not provide an [InsightGroupModel.icon].
const _fallbackGroupIcons = <String, IconData>{
  'today_focus': Icons.flash_on,
  'relationship_care': Icons.favorite_outline,
  'coming_up': Icons.calendar_today_outlined,
  'patterns': Icons.insights,
};

/// Maps a server-provided icon string to an [IconData].
/// Returns null if the identifier is not recognized — callers should
/// fall back to the hardcoded map.
IconData? _parseServerIcon(String? iconId) {
  if (iconId == null) return null;
  return switch (iconId) {
    'flash_on' => Icons.flash_on,
    'favorite_outline' => Icons.favorite_outline,
    'calendar_today_outlined' => Icons.calendar_today_outlined,
    'insights' => Icons.insights,
    'auto_awesome' => Icons.auto_awesome,
    'lightbulb_outline' => Icons.lightbulb_outline,
    'trending_up' => Icons.trending_up,
    'schedule' => Icons.schedule,
    _ => null,
  };
}

/// Resolves group accent color, preferring server-provided value.
/// Falls back to theme extension and then hardcoded defaults.
Color _resolveGroupColor(
  BuildContext context,
  String groupId,
  String? serverAccentColor,
) {
  // PLAN-004: Prefer server-provided color when available
  if (serverAccentColor != null && serverAccentColor.isNotEmpty) {
    final parsed = _parseHexColor(serverAccentColor);
    if (parsed != null) return parsed;
  }

  // Fallback: theme extension / hardcoded
  final ext = Theme.of(context).extension<AppColorsExtension>();
  return switch (groupId) {
    'today_focus' => ext?.insightSuggestion ?? AppColors.accentGreen,
    'relationship_care' => ext?.insightCorrelation ?? AppColors.accentWarm,
    'coming_up' => ext?.insightObservation ?? AppColors.accentBlue,
    'patterns' => ext?.insightFollowup ?? AppColors.textSecondary,
    _ => ext?.insightDefault ?? AppColors.accentGreen,
  };
}

/// Parses a hex color string like '#2D7A46' or '2D7A46'.
Color? _parseHexColor(String hex) {
  final cleaned = hex.replaceFirst('#', '');
  if (cleaned.length != 6) return null;
  final value = int.tryParse(cleaned, radix: 16);
  if (value == null) return null;
  return Color(0xFF000000 | value);
}

/// Renders a collapsible section for one insight group.
///
/// Shows a header with icon, title, subtitle, and insight count,
/// followed by the group's insight cards, standalone events, and
/// preparation events built by their respective builders.
class InsightGroupSection extends StatelessWidget {
  final InsightGroupModel group;
  final bool isExpanded;
  final VoidCallback onToggle;
  final Widget Function(InsightFeedItemModel insight) itemBuilder;
  final void Function(KanbanEventModel event)? onEventTap;

  const InsightGroupSection({
    super.key,
    required this.group,
    required this.isExpanded,
    required this.onToggle,
    required this.itemBuilder,
    this.onEventTap,
  });

  @override
  Widget build(BuildContext context) {
    // PLAN-004: Prefer server-provided icon, fall back to hardcoded map
    final icon = _parseServerIcon(group.icon) ??
        _fallbackGroupIcons[group.groupId] ??
        Icons.auto_awesome;
    final color = _resolveGroupColor(context, group.groupId, group.accentColor);
    final totalCount = group.insights.length +
        group.preparationEvents.length +
        group.standaloneEvents.length;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildHeader(icon, color, totalCount),
        // PLAN-007: Show 1-line preview of highest-urgency insight when collapsed
        if (!isExpanded) ...[
          _buildCollapsedPreview(color),
        ],
        if (isExpanded) ...[
          if (group.subtitle != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(
                AppDimensions.cardMarginH,
                0,
                AppDimensions.cardMarginH,
                AppDimensions.spacing8,
              ),
              child: Text(
                group.subtitle!,
                style: TextStyle(
                  fontSize: 13,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          ...group.insights.map(itemBuilder),
          for (final event in group.standaloneEvents)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: EventMiniCard(
                event: event,
                onTap: () => onEventTap?.call(event),
              ),
            ),
          for (final event in group.preparationEvents)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: EventMiniCard(
                event: event,
                onTap: () => onEventTap?.call(event),
              ),
            ),
        ],
      ],
    );
  }

  /// PLAN-005: Resolve highest urgency among group insights.
  String _highestUrgency() {
    for (final insight in group.insights) {
      if (insight.urgency == 'urgent') return 'urgent';
    }
    for (final insight in group.insights) {
      if (insight.urgency == 'important') return 'important';
    }
    return 'normal';
  }

  /// PLAN-007: Returns the highest-urgency insight title for collapsed preview.
  ///
  /// Uses the same per-insight urgency+priority ordering as card sort within
  /// expanded groups, so the preview matches the top card when expanded.
  InsightFeedItemModel? _highestPriorityInsight() {
    if (group.insights.isEmpty) return null;
    // Sort by urgency weight descending, then priority ascending
    final sorted = [...group.insights]..sort((a, b) {
        final urgencyOrder = {'urgent': 0, 'important': 1, 'normal': 2};
        final ua = urgencyOrder[a.urgency] ?? 2;
        final ub = urgencyOrder[b.urgency] ?? 2;
        if (ua != ub) return ua.compareTo(ub);
        return a.priority.compareTo(b.priority);
      });
    return sorted.first;
  }

  /// PLAN-007: 1-line preview of the highest-urgency insight below a collapsed header.
  Widget _buildCollapsedPreview(Color groupColor) {
    final topInsight = _highestPriorityInsight();
    if (topInsight == null) return const SizedBox.shrink();

    return Builder(builder: (context) {
      final colorScheme = Theme.of(context).colorScheme;
      return Padding(
        padding: const EdgeInsets.fromLTRB(
          AppDimensions.cardMarginH + AppDimensions.iconSizeLarge + AppDimensions.spacing8,
          0,
          AppDimensions.cardMarginH,
          AppDimensions.spacing8,
        ),
        child: Text(
          topInsight.title,
          style: TextStyle(
            fontSize: 13,
            color: colorScheme.onSurfaceVariant,
            fontWeight: FontWeight.w400,
            height: 1.3,
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      );
    });
  }

  Widget _buildHeader(IconData icon, Color color, int totalCount) {
    return Semantics(
      label: '${group.title} group, $totalCount items',
      button: true,
      expanded: isExpanded,
      child: GestureDetector(
        onTap: onToggle,
        behavior: HitTestBehavior.opaque,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(
            AppDimensions.cardMarginH,
            AppDimensions.spacing16,
            AppDimensions.cardMarginH,
            AppDimensions.spacing8,
          ),
          child: Row(
            children: [
              Icon(icon, size: AppDimensions.iconSizeLarge, color: color),
              const SizedBox(width: AppDimensions.spacing8),
              Expanded(
                child: Text(
                  group.title,
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    color: color,
                  ),
                ),
              ),
              // PLAN-005: Urgency indicator when collapsed
              if (!isExpanded && group.insights.isNotEmpty) ...[
                _UrgencyIndicatorDot(urgency: _highestUrgency()),
                const SizedBox(width: AppDimensions.spacing4),
              ],
              if (totalCount > 0)
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppDimensions.spacing8,
                    vertical: AppDimensions.spacing2,
                  ),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    '$totalCount',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: color,
                    ),
                  ),
                ),
              const SizedBox(width: AppDimensions.spacing8),
              AnimatedRotation(
                turns: isExpanded ? 0.25 : 0.0,
                duration: const Duration(milliseconds: 200),
                child: const Icon(
                  Icons.chevron_right,
                  size: AppDimensions.iconSizeMedium,
                  color: AppColors.textTertiary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// PLAN-005: Small colored dot indicating highest urgency in a collapsed group.
class _UrgencyIndicatorDot extends StatelessWidget {
  final String urgency;

  const _UrgencyIndicatorDot({required this.urgency});

  @override
  Widget build(BuildContext context) {
    if (urgency == 'normal') return const SizedBox.shrink();

    final ext = Theme.of(context).extension<AppColorsExtension>();
    final color = switch (urgency) {
      'urgent' => ext?.insightUrgent ?? const Color(0xFFD32F2F),
      'important' => ext?.insightImportant ?? const Color(0xFFE6A000),
      _ => Colors.transparent,
    };

    return Container(
      width: 8,
      height: 8,
      decoration: BoxDecoration(
        color: color,
        shape: BoxShape.circle,
      ),
    );
  }
}
