import 'package:flutter/material.dart';

class AppColors {
  AppColors._();

  // Brand Colors - Sage Green Theme
  static const Color primary = Color(0xFF5D7A5D);      // Sage green
  static const Color primaryLight = Color(0xFF7A9A7A);
  static const Color primaryDark = Color(0xFF4A634A);

  static const Color secondary = Color(0xFF8B7355);    // Warm brown
  static const Color secondaryLight = Color(0xFFA08B70);
  static const Color secondaryDark = Color(0xFF6B5A45);

  // Accent Colors
  static const Color accent1 = Color(0xFFE8B86D);      // Gold/Amber
  static const Color accent2 = Color(0xFFD4A574);      // Peach
  static const Color accent3 = Color(0xFF9CAF88);      // Light sage

  // Feature Accent Colors
  static const Color connectionAccent = Color(0xFF26A69A); // Teal for data connections
  static const Color accentBlue = Color(0xFF4A90D9);       // Soft blue for explore/discover

  // Design Accent Colors (from design system)
  static const Color accentGreen = Color(0xFF3D8A5A);
  static const Color accentGreenLight = Color(0xFFC8F0D8);
  static const Color accentWarm = Color(0xFFD89575);
  static const Color accentWarmLight = Color(0xFFF5E6DD);

  // Avatar accent colors (for participant circles)
  static const Color avatarGold = Color(0xFFE8B84B);
  static const Color avatarIndigo = Color(0xFF7986CB);
  static const Color avatarPink = Color(0xFFEC407A);

  // UI token aliases
  static const Color borderSubtle = Color(0xFFE5E4E1);
  static const Color bgMuted = Color(0xFFF0F0EA);
  static const Color alertOrange = Color(0xFFE65100);
  static const Color alertOrangeLight = Color(0xFFFFF3E0);

  // Semantic Colors
  static const Color success = Color(0xFF4CAF50);
  static const Color warning = Color(0xFFF9A825);
  static const Color error = Color(0xFFE57373);
  static const Color info = Color(0xFF5D7A5D);

  // Neutral Colors - Light Theme (Warm Gray from design system)
  static const Color background = Color(0xFFF5F4F1);   // Warm off-white
  static const Color surface = Color(0xFFFFFFFF);
  static const Color cardBackground = Color(0xFFFFFFFF);
  static const Color inputBackground = Color(0xFFF0F0EA);
  static const Color divider = Color(0xFFE5E4E1);
  static const Color chipBackground = Color(0xFFF0F5EF);
  static const Color shimmerBase = Color(0xFFE5E5E0);

  // Badge/Tag Colors
  static const Color badgeGreen = Color(0xFFE8F5E9);
  static const Color badgeOrange = Color(0xFFFFF3E0);
  static const Color badgePink = Color(0xFFFCE4EC);
  static const Color badgePurple = Color(0xFFF3E5F5);
  static const Color badgeBlue = Color(0xFFE3F2FD);

  // Text Colors - Light Theme (warm neutral palette from design system)
  static const Color textPrimary = Color(0xFF1A1918);
  static const Color textSecondary = Color(0xFF6D6C6A);
  static const Color textTertiary = Color(0xFF9C9B99);
  static const Color textHint = Color(0xFFB5B4B2);

  // Neutral Colors - Dark Theme
  static const Color backgroundDark = Color(0xFF1A1F1A);
  static const Color surfaceDark = Color(0xFF252B25);
  static const Color inputBackgroundDark = Color(0xFF303730);
  static const Color dividerDark = Color(0xFF404840);

  // Text Colors - Dark Theme
  static const Color textPrimaryDark = Color(0xFFF5F5F0);
  static const Color textSecondaryDark = Color(0xFFCBD5CB);
  static const Color textTertiaryDark = Color(0xFF8A998A);

  // Category Colors (for charts and tags)
  static const List<Color> categoryColors = [
    Color(0xFF5D7A5D),  // Sage green
    Color(0xFF8B7355),  // Warm brown
    Color(0xFFE8B86D),  // Gold
    Color(0xFFD4A574),  // Peach
    Color(0xFF9CAF88),  // Light sage
    Color(0xFF4CAF50),  // Green
    Color(0xFF7986CB),  // Soft blue
    Color(0xFFE57373),  // Soft red
  ];

  // Gradient
  static const LinearGradient primaryGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [primary, primaryLight],
  );

  static const LinearGradient cardGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF5D7A5D), Color(0xFF7A9A7A)],
  );

  static const LinearGradient warmGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFFF5F5F0), Color(0xFFE8E8E0)],
  );

  // Shadows
  static BoxShadow get shadowLight => BoxShadow(
    color: Colors.black.withValues(alpha: 0.04),
    blurRadius: 10,
    offset: const Offset(0, 4),
  );

  static List<BoxShadow> get cardShadow => [
    BoxShadow(
      color: Colors.black.withValues(alpha: 0.04),
      blurRadius: 10,
      offset: const Offset(0, 4),
    ),
  ];

  static List<BoxShadow> get cardShadowMedium => [
    BoxShadow(
      color: Colors.black.withValues(alpha: 0.06),
      blurRadius: 16,
      offset: const Offset(0, 6),
    ),
  ];

  static List<BoxShadow> get buttonShadow => [
    BoxShadow(
      color: primary.withValues(alpha: 0.3),
      blurRadius: 12,
      offset: const Offset(0, 4),
    ),
  ];

  static List<BoxShadow> get bottomNavShadow => [
    BoxShadow(
      color: Colors.black.withValues(alpha: 0.05),
      blurRadius: 10,
      offset: const Offset(0, -2),
    ),
  ];

  static List<BoxShadow> get cardShadowElevated => [
    BoxShadow(
      color: Colors.black.withValues(alpha: 0.08),
      blurRadius: 20,
      offset: const Offset(0, 8),
    ),
    BoxShadow(
      color: Colors.black.withValues(alpha: 0.04),
      blurRadius: 6,
      offset: const Offset(0, 2),
    ),
  ];

  static List<BoxShadow> todayGlow(Color accent) => [
    BoxShadow(
      color: accent.withValues(alpha: 0.25),
      blurRadius: 12,
      offset: const Offset(0, 4),
    ),
    BoxShadow(
      color: accent.withValues(alpha: 0.08),
      blurRadius: 4,
      offset: const Offset(0, 1),
    ),
  ];
}

/// Theme extension that carries custom color tokens not covered by ColorScheme.
///
/// Access via `Theme.of(context).extension<AppColorsExtension>()!`
class AppColorsExtension extends ThemeExtension<AppColorsExtension> {
  final Color cardBackground;
  final Color inputBackground;
  final Color chipBackground;
  final Color shimmerBase;
  final Color textTertiary;
  final Color textHint;

  // Badge colors
  final Color badgeGreen;
  final Color badgeOrange;
  final Color badgePink;
  final Color badgePurple;
  final Color badgeBlue;

  // Bubble colors
  final Color assistantBubble;
  final Color userBubble;

  // Shadow opacity multiplier (0.0 for dark, 1.0 for light)
  final double shadowOpacity;

  // Insight accent colors (per type / urgency)
  final Color insightUrgent;
  final Color insightImportant;
  final Color insightReminder;
  final Color insightSuggestion;
  final Color insightObservation;
  final Color insightCorrelation;
  final Color insightPreparation;
  final Color insightFollowup;
  final Color insightDefault;

  // Insight card background gradient endpoints
  final Color insightCardBgStart;
  final Color insightCardBgEnd;

  const AppColorsExtension({
    required this.cardBackground,
    required this.inputBackground,
    required this.chipBackground,
    required this.shimmerBase,
    required this.textTertiary,
    required this.textHint,
    required this.badgeGreen,
    required this.badgeOrange,
    required this.badgePink,
    required this.badgePurple,
    required this.badgeBlue,
    required this.assistantBubble,
    required this.userBubble,
    required this.shadowOpacity,
    required this.insightUrgent,
    required this.insightImportant,
    required this.insightReminder,
    required this.insightSuggestion,
    required this.insightObservation,
    required this.insightCorrelation,
    required this.insightPreparation,
    required this.insightFollowup,
    required this.insightDefault,
    required this.insightCardBgStart,
    required this.insightCardBgEnd,
  });

  static const light = AppColorsExtension(
    cardBackground: AppColors.cardBackground,
    inputBackground: AppColors.inputBackground,
    chipBackground: AppColors.chipBackground,
    shimmerBase: AppColors.shimmerBase,
    textTertiary: AppColors.textTertiary,
    textHint: AppColors.textHint,
    badgeGreen: AppColors.badgeGreen,
    badgeOrange: AppColors.badgeOrange,
    badgePink: AppColors.badgePink,
    badgePurple: AppColors.badgePurple,
    badgeBlue: AppColors.badgeBlue,
    assistantBubble: Colors.white,
    userBubble: AppColors.primary,
    shadowOpacity: 1.0,
    // Insight colors — light theme
    insightUrgent: Color(0xFFD32F2F),
    insightImportant: Color(0xFFE6A000),
    insightReminder: Color(0xFFE65100),
    insightSuggestion: Color(0xFF2D7A46),
    insightObservation: Color(0xFF1976D2),
    insightCorrelation: Color(0xFF7B1FA2),
    insightPreparation: Color(0xFFE6A000),
    insightFollowup: Color(0xFF00796B),
    insightDefault: Color(0xFF2D7A46),
    insightCardBgStart: Color(0xFFE8F5ED),
    insightCardBgEnd: Color(0xFFF0FAF4),
  );

  static const dark = AppColorsExtension(
    cardBackground: AppColors.surfaceDark,
    inputBackground: AppColors.inputBackgroundDark,
    chipBackground: Color(0xFF303730),
    shimmerBase: Color(0xFF404840),
    textTertiary: AppColors.textTertiaryDark,
    textHint: Color(0xFF607060),
    badgeGreen: Color(0xFF1B3A1B),
    badgeOrange: Color(0xFF3A2A10),
    badgePink: Color(0xFF3A1A20),
    badgePurple: Color(0xFF2A1A30),
    badgeBlue: Color(0xFF1A2530),
    assistantBubble: AppColors.surfaceDark,
    userBubble: AppColors.primaryDark,
    shadowOpacity: 0.0,
    // Insight colors — dark theme
    insightUrgent: Color(0xFFEF5350),
    insightImportant: Color(0xFFFFB74D),
    insightReminder: Color(0xFFFF8A65),
    insightSuggestion: Color(0xFF66BB6A),
    insightObservation: Color(0xFF64B5F6),
    insightCorrelation: Color(0xFFCE93D8),
    insightPreparation: Color(0xFFFFB74D),
    insightFollowup: Color(0xFF4DB6AC),
    insightDefault: Color(0xFF66BB6A),
    insightCardBgStart: Color(0xFF1B2E1B),
    insightCardBgEnd: Color(0xFF202820),
  );

  @override
  AppColorsExtension copyWith({
    Color? cardBackground,
    Color? inputBackground,
    Color? chipBackground,
    Color? shimmerBase,
    Color? textTertiary,
    Color? textHint,
    Color? badgeGreen,
    Color? badgeOrange,
    Color? badgePink,
    Color? badgePurple,
    Color? badgeBlue,
    Color? assistantBubble,
    Color? userBubble,
    double? shadowOpacity,
    Color? insightUrgent,
    Color? insightImportant,
    Color? insightReminder,
    Color? insightSuggestion,
    Color? insightObservation,
    Color? insightCorrelation,
    Color? insightPreparation,
    Color? insightFollowup,
    Color? insightDefault,
    Color? insightCardBgStart,
    Color? insightCardBgEnd,
  }) {
    return AppColorsExtension(
      cardBackground: cardBackground ?? this.cardBackground,
      inputBackground: inputBackground ?? this.inputBackground,
      chipBackground: chipBackground ?? this.chipBackground,
      shimmerBase: shimmerBase ?? this.shimmerBase,
      textTertiary: textTertiary ?? this.textTertiary,
      textHint: textHint ?? this.textHint,
      badgeGreen: badgeGreen ?? this.badgeGreen,
      badgeOrange: badgeOrange ?? this.badgeOrange,
      badgePink: badgePink ?? this.badgePink,
      badgePurple: badgePurple ?? this.badgePurple,
      badgeBlue: badgeBlue ?? this.badgeBlue,
      assistantBubble: assistantBubble ?? this.assistantBubble,
      userBubble: userBubble ?? this.userBubble,
      shadowOpacity: shadowOpacity ?? this.shadowOpacity,
      insightUrgent: insightUrgent ?? this.insightUrgent,
      insightImportant: insightImportant ?? this.insightImportant,
      insightReminder: insightReminder ?? this.insightReminder,
      insightSuggestion: insightSuggestion ?? this.insightSuggestion,
      insightObservation: insightObservation ?? this.insightObservation,
      insightCorrelation: insightCorrelation ?? this.insightCorrelation,
      insightPreparation: insightPreparation ?? this.insightPreparation,
      insightFollowup: insightFollowup ?? this.insightFollowup,
      insightDefault: insightDefault ?? this.insightDefault,
      insightCardBgStart: insightCardBgStart ?? this.insightCardBgStart,
      insightCardBgEnd: insightCardBgEnd ?? this.insightCardBgEnd,
    );
  }

  @override
  AppColorsExtension lerp(AppColorsExtension? other, double t) {
    if (other is! AppColorsExtension) return this;
    return AppColorsExtension(
      cardBackground: Color.lerp(cardBackground, other.cardBackground, t)!,
      inputBackground: Color.lerp(inputBackground, other.inputBackground, t)!,
      chipBackground: Color.lerp(chipBackground, other.chipBackground, t)!,
      shimmerBase: Color.lerp(shimmerBase, other.shimmerBase, t)!,
      textTertiary: Color.lerp(textTertiary, other.textTertiary, t)!,
      textHint: Color.lerp(textHint, other.textHint, t)!,
      badgeGreen: Color.lerp(badgeGreen, other.badgeGreen, t)!,
      badgeOrange: Color.lerp(badgeOrange, other.badgeOrange, t)!,
      badgePink: Color.lerp(badgePink, other.badgePink, t)!,
      badgePurple: Color.lerp(badgePurple, other.badgePurple, t)!,
      badgeBlue: Color.lerp(badgeBlue, other.badgeBlue, t)!,
      assistantBubble: Color.lerp(assistantBubble, other.assistantBubble, t)!,
      userBubble: Color.lerp(userBubble, other.userBubble, t)!,
      shadowOpacity: t < 0.5 ? shadowOpacity : other.shadowOpacity,
      insightUrgent: Color.lerp(insightUrgent, other.insightUrgent, t)!,
      insightImportant: Color.lerp(insightImportant, other.insightImportant, t)!,
      insightReminder: Color.lerp(insightReminder, other.insightReminder, t)!,
      insightSuggestion: Color.lerp(insightSuggestion, other.insightSuggestion, t)!,
      insightObservation: Color.lerp(insightObservation, other.insightObservation, t)!,
      insightCorrelation: Color.lerp(insightCorrelation, other.insightCorrelation, t)!,
      insightPreparation: Color.lerp(insightPreparation, other.insightPreparation, t)!,
      insightFollowup: Color.lerp(insightFollowup, other.insightFollowup, t)!,
      insightDefault: Color.lerp(insightDefault, other.insightDefault, t)!,
      insightCardBgStart: Color.lerp(insightCardBgStart, other.insightCardBgStart, t)!,
      insightCardBgEnd: Color.lerp(insightCardBgEnd, other.insightCardBgEnd, t)!,
    );
  }
}
