import 'package:hive/hive.dart';

/// Storage for app settings using Hive
class SettingsStorage {
  final Box _box;

  static const String _themeKey = 'theme_mode';
  static const String _languageKey = 'language';
  static const String _notificationsEnabledKey = 'notifications_enabled';
  static const String _reminderNotificationsKey = 'reminder_notifications';
  static const String _giftNotificationsKey = 'gift_notifications';
  static const String _priceNotificationsKey = 'price_notifications';
  static const String _insightNotificationsKey = 'insight_notifications';
  static const String _biometricEnabledKey = 'biometric_enabled';
  static const String _pinEnabledKey = 'pin_enabled';
  static const String _pinCodeKey = 'pin_code';
  static const String _lastBackupKey = 'last_backup_time';
  static const String _autoBackupKey = 'auto_backup_enabled';

  // Insight settings keys
  static const String _emotionPatternWindowDaysKey = 'emotion_pattern_window_days';
  static const String _relationshipReminderThresholdDaysKey = 'relationship_reminder_threshold_days';
  static const String _insightExpiryDaysKey = 'insight_expiry_days';
  static const String _oldPlanFollowupThresholdDaysKey = 'old_plan_followup_threshold_days';
  static const String _upcomingTripCheckDaysKey = 'upcoming_trip_check_days';

  SettingsStorage(this._box);

  // Theme settings
  String get themeMode => _box.get(_themeKey, defaultValue: 'system');
  Future<void> setThemeMode(String mode) => _box.put(_themeKey, mode);

  // Language settings
  String get language => _box.get(_languageKey, defaultValue: 'zh_CN');
  Future<void> setLanguage(String locale) => _box.put(_languageKey, locale);

  // Notification settings
  bool get notificationsEnabled =>
      _box.get(_notificationsEnabledKey, defaultValue: true);
  Future<void> setNotificationsEnabled(bool enabled) =>
      _box.put(_notificationsEnabledKey, enabled);

  bool get reminderNotifications =>
      _box.get(_reminderNotificationsKey, defaultValue: true);
  Future<void> setReminderNotifications(bool enabled) =>
      _box.put(_reminderNotificationsKey, enabled);

  bool get giftNotifications =>
      _box.get(_giftNotificationsKey, defaultValue: true);
  Future<void> setGiftNotifications(bool enabled) =>
      _box.put(_giftNotificationsKey, enabled);

  bool get priceNotifications =>
      _box.get(_priceNotificationsKey, defaultValue: true);
  Future<void> setPriceNotifications(bool enabled) =>
      _box.put(_priceNotificationsKey, enabled);

  bool get insightNotifications =>
      _box.get(_insightNotificationsKey, defaultValue: true);
  Future<void> setInsightNotifications(bool enabled) =>
      _box.put(_insightNotificationsKey, enabled);

  // Security settings
  bool get biometricEnabled =>
      _box.get(_biometricEnabledKey, defaultValue: false);
  Future<void> setBiometricEnabled(bool enabled) =>
      _box.put(_biometricEnabledKey, enabled);

  bool get pinEnabled => _box.get(_pinEnabledKey, defaultValue: false);
  Future<void> setPinEnabled(bool enabled) => _box.put(_pinEnabledKey, enabled);

  String? get pinCode => _box.get(_pinCodeKey);
  Future<void> setPinCode(String? code) async {
    if (code == null) {
      await _box.delete(_pinCodeKey);
    } else {
      await _box.put(_pinCodeKey, code);
    }
  }

  // Backup settings
  DateTime? get lastBackupTime {
    final timestamp = _box.get(_lastBackupKey);
    return timestamp != null
        ? DateTime.fromMillisecondsSinceEpoch(timestamp)
        : null;
  }

  Future<void> setLastBackupTime(DateTime time) =>
      _box.put(_lastBackupKey, time.millisecondsSinceEpoch);

  bool get autoBackupEnabled =>
      _box.get(_autoBackupKey, defaultValue: false);
  Future<void> setAutoBackupEnabled(bool enabled) =>
      _box.put(_autoBackupKey, enabled);

  // Insight settings
  int get emotionPatternWindowDays =>
      _box.get(_emotionPatternWindowDaysKey, defaultValue: 7);
  Future<void> setEmotionPatternWindowDays(int days) =>
      _box.put(_emotionPatternWindowDaysKey, days.clamp(1, 30));

  int get relationshipReminderThresholdDays =>
      _box.get(_relationshipReminderThresholdDaysKey, defaultValue: 90);
  Future<void> setRelationshipReminderThresholdDays(int days) =>
      _box.put(_relationshipReminderThresholdDaysKey, days.clamp(7, 365));

  int get insightExpiryDays =>
      _box.get(_insightExpiryDaysKey, defaultValue: 7);
  Future<void> setInsightExpiryDays(int days) =>
      _box.put(_insightExpiryDaysKey, days.clamp(1, 30));

  int get oldPlanFollowupThresholdDays =>
      _box.get(_oldPlanFollowupThresholdDaysKey, defaultValue: 14);
  Future<void> setOldPlanFollowupThresholdDays(int days) =>
      _box.put(_oldPlanFollowupThresholdDaysKey, days.clamp(1, 60));

  int get upcomingTripCheckDays =>
      _box.get(_upcomingTripCheckDaysKey, defaultValue: 7);
  Future<void> setUpcomingTripCheckDays(int days) =>
      _box.put(_upcomingTripCheckDaysKey, days.clamp(1, 30));

  // Clear all settings
  Future<void> clear() => _box.clear();
}
