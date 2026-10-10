import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_dimensions.dart';

/// 3-tier card display system controlling element VISIBILITY, not just styling.
///
/// Spotlight: highest priority — full chrome, gradient, shadow, context hint.
/// Standard: normal priority — accent bar, subtle gradient, 1 CTA chip.
/// Whisper: low priority — minimal chrome, flat surface, dot-only accent.
enum InsightCardTier { spotlight, standard, whisper }

// =============================================================================
// Memoization cache key
// =============================================================================

class _StyleCacheKey {
  final String insightType;
  final InsightCardTier tier;
  final Brightness brightness;

  const _StyleCacheKey({
    required this.insightType,
    required this.tier,
    required this.brightness,
  });

  @override
  bool operator ==(Object other) =>
      other is _StyleCacheKey &&
      insightType == other.insightType &&
      tier == other.tier &&
      brightness == other.brightness;

  @override
  int get hashCode => Object.hash(insightType, tier, brightness);
}

/// Shared style descriptor for AI insight cards and detail sheets.
///
/// Use [InsightStyle.resolve] to obtain the correct style for a given
/// insight type, urgency, and priority. The 3-tier system controls which
/// elements are shown per card, not just gradient alpha.
class InsightStyle {
  final Color accentColor;
  final List<Color> bgGradient;
  final Color borderColor;
  final String emoji;
  final String label;

  /// 3-tier card system controlling element visibility.
  final InsightCardTier cardTier;

  /// Theme-aware surface color for insight-related containers.
  final Color surfaceColor;

  /// Theme-aware chip background color for context hints and tags.
  final Color chipBgColor;

  /// Theme-aware chip text/icon color.
  final Color chipTextColor;

  /// Theme-aware color for timeline connecting lines between events.
  final Color timelineConnectorColor;

  /// Theme-aware color for timeline dots.
  final Color timelineDotColor;

  /// Shadow elevation driven by tier.
  final double elevation;

  const InsightStyle({
    required this.accentColor,
    required this.bgGradient,
    required this.borderColor,
    required this.emoji,
    required this.label,
    required this.surfaceColor,
    required this.chipBgColor,
    required this.chipTextColor,
    required this.timelineConnectorColor,
    required this.timelineDotColor,
    this.cardTier = InsightCardTier.standard,
    this.elevation = 0.0,
  });

  // ── Tier-driven element visibility ──

  /// Whether the full header row (dot+emoji+label+timestamp) is shown.
  bool get showFullHeader => cardTier != InsightCardTier.whisper;

  /// Whether context hint is visible in collapsed state.
  bool get showContextHint => cardTier == InsightCardTier.spotlight;

  /// Whether action chips are visible in collapsed state.
  bool get showActionChips => cardTier != InsightCardTier.whisper;

  /// Title font size per tier.
  double get titleFontSize => switch (cardTier) {
    InsightCardTier.spotlight => 17.0,
    InsightCardTier.standard => 16.0,
    InsightCardTier.whisper => 15.0,
  };

  /// Title font weight per tier.
  FontWeight get titleFontWeight => cardTier == InsightCardTier.whisper
      ? FontWeight.w600
      : FontWeight.w700;

  /// Title max lines per tier (collapsed state).
  int get titleMaxLines => cardTier == InsightCardTier.whisper ? 1 : 2;

  /// Content preview max lines per tier (collapsed state).
  int get contentMaxLines => switch (cardTier) {
    InsightCardTier.spotlight => 3,
    InsightCardTier.standard => 2,
    InsightCardTier.whisper => 1,
  };

  /// Border width per tier.
  double get borderWidth => cardTier == InsightCardTier.spotlight
      ? AppDimensions.cardBorderWidthElevated
      : AppDimensions.cardBorderWidth;

  /// Vertical margin per tier.
  double get verticalMargin => cardTier == InsightCardTier.spotlight ? 10.0 : 6.0;

  // ── Memoization cache ──

  static final Map<_StyleCacheKey, InsightStyle> _cache = {};

  /// Clears the style cache. Call when the app theme changes.
  static void invalidateCache() => _cache.clear();

  /// Determines the card tier from urgency, priority, and visual weight.
  static InsightCardTier assignTier(String urgency, int priority, double? visualWeight) {
    if (urgency == 'urgent') return InsightCardTier.spotlight;
    if (urgency == 'important' && priority <= 2) return InsightCardTier.spotlight;
    if (urgency == 'important') return InsightCardTier.standard;
    // Normal urgency: use visualWeight threshold
    final vw = visualWeight ?? 0.35;
    if (vw >= 0.4) return InsightCardTier.standard;
    return InsightCardTier.whisper;
  }

  /// Resolves the visual style for an insight using theme-aware colors.
  static InsightStyle resolve({
    required BuildContext context,
    required String insightType,
    required String urgency,
    double? visualWeight,
    int priority = 5,
  }) {
    final brightness = Theme.of(context).brightness;
    final tier = assignTier(urgency, priority, visualWeight);

    final key = _StyleCacheKey(
      insightType: insightType,
      tier: tier,
      brightness: brightness,
    );
    final cached = _cache[key];
    if (cached != null) return cached;

    final resolved = _resolveUncached(context, insightType, urgency, tier);
    _cache[key] = resolved;
    return resolved;
  }

  static InsightStyle _resolveUncached(
    BuildContext context,
    String insightType,
    String urgency,
    InsightCardTier tier,
  ) {
    final ext = Theme.of(context).extension<AppColorsExtension>();
    final colorScheme = Theme.of(context).colorScheme;

    final surfaceColor = colorScheme.surface;
    final chipBgColor = ext?.chipBackground ?? AppColors.chipBackground;
    final chipTextColor = ext?.textTertiary ?? AppColors.textTertiary;
    final timelineConnectorColor = ext?.insightDefault.withValues(alpha: 0.2)
        ?? const Color(0xFFD4E8DC);
    final timelineDotColor = ext?.textTertiary ?? const Color(0xFFB0B0AE);

    if (urgency == 'urgent') {
      final accent = ext?.insightUrgent ?? const Color(0xFFD32F2F);
      return InsightStyle(
        accentColor: accent,
        bgGradient: _gradientForTier(accent, tier, surfaceColor),
        borderColor: accent.withValues(alpha: tier == InsightCardTier.spotlight ? 0.4 : 0.25),
        emoji: '\u26A0\uFE0F',
        label: '\u7D27\u6025\u63D0\u9192',
        surfaceColor: surfaceColor,
        chipBgColor: chipBgColor,
        chipTextColor: chipTextColor,
        timelineConnectorColor: timelineConnectorColor,
        timelineDotColor: timelineDotColor,
        cardTier: tier,
        elevation: _elevationForTier(tier),
      );
    }
    if (urgency == 'important') {
      final accent = ext?.insightImportant ?? const Color(0xFFE6A000);
      return InsightStyle(
        accentColor: accent,
        bgGradient: _gradientForTier(accent, tier, surfaceColor),
        borderColor: accent.withValues(alpha: tier == InsightCardTier.spotlight ? 0.4 : 0.25),
        emoji: '\u26A0\uFE0F',
        label: '\u91CD\u8981\u63D0\u9192',
        surfaceColor: surfaceColor,
        chipBgColor: chipBgColor,
        chipTextColor: chipTextColor,
        timelineConnectorColor: timelineConnectorColor,
        timelineDotColor: timelineDotColor,
        cardTier: tier,
        elevation: _elevationForTier(tier),
      );
    }
    return _resolveByType(
      insightType,
      ext,
      tier: tier,
      surfaceColor: surfaceColor,
      chipBgColor: chipBgColor,
      chipTextColor: chipTextColor,
      timelineConnectorColor: timelineConnectorColor,
      timelineDotColor: timelineDotColor,
    );
  }

  /// Tier-based elevation: Spotlight gets accent shadow, Standard gets subtle, Whisper gets none.
  static double _elevationForTier(InsightCardTier tier) => switch (tier) {
    InsightCardTier.spotlight => 4.0,
    InsightCardTier.standard => 2.0,
    InsightCardTier.whisper => 0.0,
  };

  /// 3 fixed gradient presets per tier (no continuous scaling).
  static List<Color> _gradientForTier(Color accent, InsightCardTier tier, Color surface) => switch (tier) {
    InsightCardTier.spotlight => [
      accent.withValues(alpha: 0.18),
      accent.withValues(alpha: 0.09),
    ],
    InsightCardTier.standard => [
      accent.withValues(alpha: 0.08),
      accent.withValues(alpha: 0.04),
    ],
    InsightCardTier.whisper => [surface, surface],
  };

  /// Normal-urgency insights: type determines accent color, tier determines styling.
  static InsightStyle _resolveByType(
    String insightType,
    AppColorsExtension? ext, {
    required InsightCardTier tier,
    required Color surfaceColor,
    required Color chipBgColor,
    required Color chipTextColor,
    required Color timelineConnectorColor,
    required Color timelineDotColor,
  }) {
    final (accent, emoji, label) = _typeAttributes(insightType, ext);
    final borderAlpha = tier == InsightCardTier.spotlight ? 0.4 : 0.25;

    return InsightStyle(
      accentColor: accent,
      bgGradient: _gradientForTier(accent, tier, surfaceColor),
      borderColor: accent.withValues(alpha: borderAlpha),
      emoji: emoji,
      label: label,
      surfaceColor: surfaceColor,
      chipBgColor: chipBgColor,
      chipTextColor: chipTextColor,
      timelineConnectorColor: timelineConnectorColor,
      timelineDotColor: timelineDotColor,
      cardTier: tier,
      elevation: _elevationForTier(tier),
    );
  }

  /// Maps insight type to (accent color, emoji, label).
  static (Color, String, String) _typeAttributes(
    String insightType,
    AppColorsExtension? ext,
  ) => switch (insightType) {
    'reminder' || 'favor_reminder' => (
      ext?.insightReminder ?? const Color(0xFFE65100),
      '\uD83D\uDD14',
      '\u63D0\u9192',
    ),
    'suggestion' => (
      ext?.insightSuggestion ?? const Color(0xFF2D7A46),
      '\uD83D\uDCA1',
      '\u5EFA\u8BAE',
    ),
    'observation' || 'pattern_observation' => (
      ext?.insightObservation ?? const Color(0xFF1976D2),
      '\uD83D\uDC41\uFE0F',
      '\u89C2\u5BDF',
    ),
    'correlation' || 'relationship_maintenance' => (
      ext?.insightCorrelation ?? const Color(0xFF7B1FA2),
      '\uD83D\uDD17',
      '\u5173\u8054',
    ),
    'event_preparation' => (
      ext?.insightPreparation ?? const Color(0xFFE6A000),
      '\u2705',
      '\u51C6\u5907',
    ),
    'followup' => (
      ext?.insightFollowup ?? const Color(0xFF00796B),
      '\uD83D\uDD04',
      '\u8DDF\u8FDB',
    ),
    _ => (
      ext?.insightDefault ?? const Color(0xFF2D7A46),
      '\u2728',
      'AI \u6D1E\u5BDF',
    ),
  };
}
