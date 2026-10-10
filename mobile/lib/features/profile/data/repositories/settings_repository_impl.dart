import 'package:package_info_plus/package_info_plus.dart';

import '../../../../core/storage/settings_storage.dart';
import '../../domain/entities/app_settings.dart';
import '../../domain/entities/security_settings.dart';
import '../../domain/entities/backup_info.dart';
import '../../domain/entities/insight_settings.dart';
import '../../domain/repositories/settings_repository.dart';
import '../datasources/profile_remote_datasource.dart';

class SettingsRepositoryImpl implements SettingsRepository {
  final SettingsStorage _storage;
  final ProfileRemoteDataSource _remoteDataSource;

  SettingsRepositoryImpl({
    required SettingsStorage storage,
    required ProfileRemoteDataSource remoteDataSource,
  })  : _storage = storage,
        _remoteDataSource = remoteDataSource;

  @override
  Future<AppSettings> getAppSettings() async {
    return AppSettings(
      themeMode: ThemeModeSetting.fromString(_storage.themeMode),
      language: AppLanguage.fromLocale(_storage.language),
      notifications: NotificationSettings(
        enabled: _storage.notificationsEnabled,
        reminderNotifications: _storage.reminderNotifications,
        giftNotifications: _storage.giftNotifications,
        priceNotifications: _storage.priceNotifications,
        insightNotifications: _storage.insightNotifications,
      ),
    );
  }

  @override
  Future<void> setThemeMode(ThemeModeSetting mode) async {
    await _storage.setThemeMode(mode.name);
  }

  @override
  Future<void> setLanguage(AppLanguage language) async {
    await _storage.setLanguage(language.locale);
  }

  @override
  Future<void> setNotificationsEnabled(bool enabled) async {
    await _storage.setNotificationsEnabled(enabled);
  }

  @override
  Future<void> setReminderNotifications(bool enabled) async {
    await _storage.setReminderNotifications(enabled);
  }

  @override
  Future<void> setGiftNotifications(bool enabled) async {
    await _storage.setGiftNotifications(enabled);
  }

  @override
  Future<void> setPriceNotifications(bool enabled) async {
    await _storage.setPriceNotifications(enabled);
  }

  @override
  Future<void> setInsightNotifications(bool enabled) async {
    await _storage.setInsightNotifications(enabled);
  }

  @override
  Future<SecuritySettings> getSecuritySettings() async {
    return SecuritySettings(
      biometricEnabled: _storage.biometricEnabled,
      pinEnabled: _storage.pinEnabled,
      hasPinCode: _storage.pinCode != null,
    );
  }

  @override
  Future<void> setBiometricEnabled(bool enabled) async {
    await _storage.setBiometricEnabled(enabled);
  }

  @override
  Future<void> setPinEnabled(bool enabled) async {
    await _storage.setPinEnabled(enabled);
  }

  @override
  Future<bool> verifyPin(String pin) async {
    return _storage.pinCode == pin;
  }

  @override
  Future<void> setPin(String pin) async {
    await _storage.setPinCode(pin);
    await _storage.setPinEnabled(true);
  }

  @override
  Future<void> removePin() async {
    await _storage.setPinCode(null);
    await _storage.setPinEnabled(false);
  }

  @override
  Future<BackupInfo> getBackupInfo() async {
    return BackupInfo(
      lastBackupTime: _storage.lastBackupTime,
      autoBackupEnabled: _storage.autoBackupEnabled,
    );
  }

  @override
  Future<void> setAutoBackupEnabled(bool enabled) async {
    await _storage.setAutoBackupEnabled(enabled);
  }

  @override
  Future<void> createBackup() async {
    // TODO: Implement actual backup logic (export to file/cloud)
    // For now, just update the timestamp
    await _storage.setLastBackupTime(DateTime.now());
  }

  @override
  Future<void> restoreBackup() async {
    // TODO: Implement actual restore logic
    throw UnimplementedError('Backup restore not yet implemented');
  }

  @override
  Future<void> submitFeedback(String content, String? contactInfo) async {
    await _remoteDataSource.submitFeedback(content, contactInfo);
  }

  @override
  Future<String> getAppVersion() async {
    final packageInfo = await PackageInfo.fromPlatform();
    return '${packageInfo.version} (${packageInfo.buildNumber})';
  }

  @override
  Future<bool> checkForUpdate() async {
    // TODO: Implement actual update check via API
    // For now, always return false (no update)
    return false;
  }

  @override
  Future<InsightSettings> getInsightSettings() async {
    // Try to fetch from remote first, fall back to local storage
    try {
      final remoteSettings = await _remoteDataSource.fetchInsightSettings();
      // Update local storage with remote values
      await _storage.setEmotionPatternWindowDays(remoteSettings.emotionPatternWindowDays);
      await _storage.setRelationshipReminderThresholdDays(remoteSettings.relationshipReminderThresholdDays);
      await _storage.setInsightExpiryDays(remoteSettings.insightExpiryDays);
      await _storage.setOldPlanFollowupThresholdDays(remoteSettings.oldPlanFollowupThresholdDays);
      await _storage.setUpcomingTripCheckDays(remoteSettings.upcomingTripCheckDays);
      return remoteSettings;
    } catch (e) {
      // Fall back to local storage
      return InsightSettings(
        emotionPatternWindowDays: _storage.emotionPatternWindowDays,
        relationshipReminderThresholdDays: _storage.relationshipReminderThresholdDays,
        insightExpiryDays: _storage.insightExpiryDays,
        oldPlanFollowupThresholdDays: _storage.oldPlanFollowupThresholdDays,
        upcomingTripCheckDays: _storage.upcomingTripCheckDays,
      );
    }
  }

  @override
  Future<void> updateInsightSettings(InsightSettings settings) async {
    // Update remote first to ensure consistency
    await _remoteDataSource.updateInsightSettings(settings);
    // Then update local storage
    await _storage.setEmotionPatternWindowDays(settings.emotionPatternWindowDays);
    await _storage.setRelationshipReminderThresholdDays(settings.relationshipReminderThresholdDays);
    await _storage.setInsightExpiryDays(settings.insightExpiryDays);
    await _storage.setOldPlanFollowupThresholdDays(settings.oldPlanFollowupThresholdDays);
    await _storage.setUpcomingTripCheckDays(settings.upcomingTripCheckDays);
  }

  @override
  Future<void> resetInsightSettings() async {
    // Reset remote first
    await _remoteDataSource.resetInsightSettings();
    // Then reset local storage to defaults
    const defaults = InsightSettings.defaults;
    await _storage.setEmotionPatternWindowDays(defaults.emotionPatternWindowDays);
    await _storage.setRelationshipReminderThresholdDays(defaults.relationshipReminderThresholdDays);
    await _storage.setInsightExpiryDays(defaults.insightExpiryDays);
    await _storage.setOldPlanFollowupThresholdDays(defaults.oldPlanFollowupThresholdDays);
    await _storage.setUpcomingTripCheckDays(defaults.upcomingTripCheckDays);
  }

  @override
  Future<void> triggerManualCuration() async {
    await _remoteDataSource.triggerManualCuration();
  }
}
