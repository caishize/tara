/// Shared dimension constants for consistent spacing, radius, and sizing.
///
/// Replaces inline magic numbers across insight widgets and other components.
/// All values are in logical pixels.
abstract final class AppDimensions {
  // ── Card dimensions ──
  static const double cardRadius = 16.0;
  static const double cardMarginH = 16.0;
  static const double cardMarginV = 6.0;
  static const double cardPadding = 12.0;
  static const double cardPaddingH = 16.0;
  static const double cardPaddingV = 14.0;

  // ── Chip dimensions ──
  static const double chipRadius = 8.0;
  static const double chipHeight = 36.0;
  static const double chipPaddingH = 14.0;

  // ── Card border ──
  static const double cardBorderWidth = 1.0;
  static const double cardBorderWidthElevated = 1.5;
  static const double cardRadiusSmall = 12.0;
  static const double cardMinHeight = 72.0;

  // ── Accent / decorative ──
  static const double accentBarWidth = 4.0;
  static const double urgencyDotSize = 8.0;

  // ── Section layout ──
  static const double sectionSpacing = 20.0;
  static const double sectionTitleFontSize = 15.0;
  static const double sectionHeaderPaddingH = 16.0;

  // ── Avatar ──
  static const double avatarSizeSmall = 24.0;
  static const double avatarSizeMedium = 36.0;
  static const double avatarSizeLarge = 48.0;

  // ── Icon sizing ──
  static const double iconSizeSmall = 14.0;
  static const double iconSizeMedium = 18.0;
  static const double iconSizeLarge = 24.0;

  // ── Spacing scale ──
  static const double spacing2 = 2.0;
  static const double spacing4 = 4.0;
  static const double spacing6 = 6.0;
  static const double spacing8 = 8.0;
  static const double spacing12 = 12.0;
  static const double spacing16 = 16.0;
  static const double spacing20 = 20.0;
  static const double spacing24 = 24.0;

  // ── Animation timing ──
  static const Duration animEntranceDuration = Duration(milliseconds: 300);
  static const Duration animEntranceStagger = Duration(milliseconds: 50);
  static const Duration animExpandDuration = Duration(milliseconds: 280);
  static const Duration animPressFeedback = Duration(milliseconds: 100);
}
