import 'package:equatable/equatable.dart';

enum ThemeModeSetting {
  system,
  light,
  dark;

  String get displayName {
    switch (this) {
      case ThemeModeSetting.system:
        return '跟随系统';
      case ThemeModeSetting.light:
        return '浅色模式';
      case ThemeModeSetting.dark:
        return '深色模式';
    }
  }

  static ThemeModeSetting fromString(String value) {
    switch (value) {
      case 'light':
        return ThemeModeSetting.light;
      case 'dark':
        return ThemeModeSetting.dark;
      default:
        return ThemeModeSetting.system;
    }
  }
}

enum AppLanguage {
  zhCN,
  enUS;

  String get displayName {
    switch (this) {
      case AppLanguage.zhCN:
        return '简体中文';
      case AppLanguage.enUS:
        return 'English';
    }
  }

  String get locale {
    switch (this) {
      case AppLanguage.zhCN:
        return 'zh_CN';
      case AppLanguage.enUS:
        return 'en_US';
    }
  }

  static AppLanguage fromLocale(String locale) {
    switch (locale) {
      case 'en_US':
        return AppLanguage.enUS;
      default:
        return AppLanguage.zhCN;
    }
  }
}

class AppSettings extends Equatable {
  final ThemeModeSetting themeMode;
  final AppLanguage language;
  final NotificationSettings notifications;

  const AppSettings({
    required this.themeMode,
    required this.language,
    required this.notifications,
  });

  factory AppSettings.defaults() => const AppSettings(
        themeMode: ThemeModeSetting.system,
        language: AppLanguage.zhCN,
        notifications: NotificationSettings(),
      );

  AppSettings copyWith({
    ThemeModeSetting? themeMode,
    AppLanguage? language,
    NotificationSettings? notifications,
  }) =>
      AppSettings(
        themeMode: themeMode ?? this.themeMode,
        language: language ?? this.language,
        notifications: notifications ?? this.notifications,
      );

  @override
  List<Object?> get props => [themeMode, language, notifications];
}

class NotificationSettings extends Equatable {
  final bool enabled;
  final bool reminderNotifications;
  final bool giftNotifications;
  final bool priceNotifications;
  final bool insightNotifications;

  const NotificationSettings({
    this.enabled = true,
    this.reminderNotifications = true,
    this.giftNotifications = true,
    this.priceNotifications = true,
    this.insightNotifications = true,
  });

  NotificationSettings copyWith({
    bool? enabled,
    bool? reminderNotifications,
    bool? giftNotifications,
    bool? priceNotifications,
    bool? insightNotifications,
  }) =>
      NotificationSettings(
        enabled: enabled ?? this.enabled,
        reminderNotifications:
            reminderNotifications ?? this.reminderNotifications,
        giftNotifications: giftNotifications ?? this.giftNotifications,
        priceNotifications: priceNotifications ?? this.priceNotifications,
        insightNotifications:
            insightNotifications ?? this.insightNotifications,
      );

  @override
  List<Object?> get props => [
        enabled,
        reminderNotifications,
        giftNotifications,
        priceNotifications,
        insightNotifications,
      ];
}
