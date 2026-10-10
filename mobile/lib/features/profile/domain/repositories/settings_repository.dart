import '../entities/app_settings.dart';
import '../entities/security_settings.dart';
import '../entities/backup_info.dart';
import '../entities/insight_settings.dart';

abstract class SettingsRepository {
  // App Settings
  Future<AppSettings> getAppSettings();
  Future<void> setThemeMode(ThemeModeSetting mode);
  Future<void> setLanguage(AppLanguage language);
  Future<void> setNotificationsEnabled(bool enabled);
  Future<void> setReminderNotifications(bool enabled);
  Future<void> setGiftNotifications(bool enabled);
  Future<void> setPriceNotifications(bool enabled);
  Future<void> setInsightNotifications(bool enabled);

  // Security Settings
  Future<SecuritySettings> getSecuritySettings();
  Future<void> setBiometricEnabled(bool enabled);
  Future<void> setPinEnabled(bool enabled);
  Future<bool> verifyPin(String pin);
  Future<void> setPin(String pin);
  Future<void> removePin();

  // Backup
  Future<BackupInfo> getBackupInfo();
  Future<void> setAutoBackupEnabled(bool enabled);
  Future<void> createBackup();
  Future<void> restoreBackup();

  // Feedback
  Future<void> submitFeedback(String content, String? contactInfo);

  // App Info
  Future<String> getAppVersion();
  Future<bool> checkForUpdate();

  // Insight Settings
  Future<InsightSettings> getInsightSettings();
  Future<void> updateInsightSettings(InsightSettings settings);
  Future<void> resetInsightSettings();

  // Timeline Curation
  Future<void> triggerManualCuration();
}
