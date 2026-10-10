import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../domain/entities/app_settings.dart';
import '../../domain/entities/security_settings.dart';
import '../../domain/entities/backup_info.dart';
import '../../domain/entities/insight_settings.dart';
import '../../domain/repositories/settings_repository.dart';

// Events
abstract class SettingsEvent extends Equatable {
  const SettingsEvent();

  @override
  List<Object?> get props => [];
}

class SettingsLoadRequested extends SettingsEvent {
  const SettingsLoadRequested();
}

class ThemeModeChanged extends SettingsEvent {
  final ThemeModeSetting themeMode;
  const ThemeModeChanged(this.themeMode);

  @override
  List<Object?> get props => [themeMode];
}

class LanguageChanged extends SettingsEvent {
  final AppLanguage language;
  const LanguageChanged(this.language);

  @override
  List<Object?> get props => [language];
}

class NotificationsToggled extends SettingsEvent {
  final bool enabled;
  const NotificationsToggled(this.enabled);

  @override
  List<Object?> get props => [enabled];
}

class ReminderNotificationsToggled extends SettingsEvent {
  final bool enabled;
  const ReminderNotificationsToggled(this.enabled);

  @override
  List<Object?> get props => [enabled];
}

class GiftNotificationsToggled extends SettingsEvent {
  final bool enabled;
  const GiftNotificationsToggled(this.enabled);

  @override
  List<Object?> get props => [enabled];
}

class PriceNotificationsToggled extends SettingsEvent {
  final bool enabled;
  const PriceNotificationsToggled(this.enabled);

  @override
  List<Object?> get props => [enabled];
}

class InsightNotificationsToggled extends SettingsEvent {
  final bool enabled;
  const InsightNotificationsToggled(this.enabled);

  @override
  List<Object?> get props => [enabled];
}

class BiometricToggled extends SettingsEvent {
  final bool enabled;
  const BiometricToggled(this.enabled);

  @override
  List<Object?> get props => [enabled];
}

class PinSetRequested extends SettingsEvent {
  final String pin;
  const PinSetRequested(this.pin);

  @override
  List<Object?> get props => [pin];
}

class PinRemoveRequested extends SettingsEvent {
  const PinRemoveRequested();
}

class PinVerifyRequested extends SettingsEvent {
  final String pin;
  const PinVerifyRequested(this.pin);

  @override
  List<Object?> get props => [pin];
}

class AutoBackupToggled extends SettingsEvent {
  final bool enabled;
  const AutoBackupToggled(this.enabled);

  @override
  List<Object?> get props => [enabled];
}

class BackupRequested extends SettingsEvent {
  const BackupRequested();
}

class RestoreRequested extends SettingsEvent {
  const RestoreRequested();
}

class FeedbackSubmitted extends SettingsEvent {
  final String content;
  final String? contactInfo;
  const FeedbackSubmitted(this.content, this.contactInfo);

  @override
  List<Object?> get props => [content, contactInfo];
}

class UpdateCheckRequested extends SettingsEvent {
  const UpdateCheckRequested();
}

class InsightSettingsChanged extends SettingsEvent {
  final InsightSettings settings;
  const InsightSettingsChanged(this.settings);

  @override
  List<Object?> get props => [settings];
}

class InsightSettingsResetRequested extends SettingsEvent {
  const InsightSettingsResetRequested();
}

class ManualCurationRequested extends SettingsEvent {
  const ManualCurationRequested();
}

// States
abstract class SettingsState extends Equatable {
  const SettingsState();

  @override
  List<Object?> get props => [];
}

class SettingsInitial extends SettingsState {
  const SettingsInitial();
}

class SettingsLoading extends SettingsState {
  const SettingsLoading();
}

class SettingsLoaded extends SettingsState {
  final AppSettings appSettings;
  final SecuritySettings securitySettings;
  final BackupInfo backupInfo;
  final InsightSettings insightSettings;
  final String appVersion;

  const SettingsLoaded({
    required this.appSettings,
    required this.securitySettings,
    required this.backupInfo,
    required this.insightSettings,
    required this.appVersion,
  });

  @override
  List<Object?> get props => [appSettings, securitySettings, backupInfo, insightSettings, appVersion];

  SettingsLoaded copyWith({
    AppSettings? appSettings,
    SecuritySettings? securitySettings,
    BackupInfo? backupInfo,
    InsightSettings? insightSettings,
    String? appVersion,
  }) =>
      SettingsLoaded(
        appSettings: appSettings ?? this.appSettings,
        securitySettings: securitySettings ?? this.securitySettings,
        backupInfo: backupInfo ?? this.backupInfo,
        insightSettings: insightSettings ?? this.insightSettings,
        appVersion: appVersion ?? this.appVersion,
      );
}

class SettingsError extends SettingsState {
  final String message;
  const SettingsError(this.message);

  @override
  List<Object?> get props => [message];
}

class SettingsOperationSuccess extends SettingsState {
  final String message;
  final SettingsLoaded currentState;
  const SettingsOperationSuccess(this.message, this.currentState);

  @override
  List<Object?> get props => [message, currentState];
}

class PinVerificationResult extends SettingsState {
  final bool success;
  final SettingsLoaded currentState;
  const PinVerificationResult(this.success, this.currentState);

  @override
  List<Object?> get props => [success, currentState];
}

class UpdateCheckResult extends SettingsState {
  final bool updateAvailable;
  final SettingsLoaded currentState;
  const UpdateCheckResult(this.updateAvailable, this.currentState);

  @override
  List<Object?> get props => [updateAvailable, currentState];
}

// BLoC
class SettingsBloc extends Bloc<SettingsEvent, SettingsState> {
  final SettingsRepository _repository;

  SettingsBloc({required SettingsRepository repository})
      : _repository = repository,
        super(const SettingsInitial()) {
    on<SettingsLoadRequested>(_onLoadRequested);
    on<ThemeModeChanged>(_onThemeModeChanged);
    on<LanguageChanged>(_onLanguageChanged);
    on<NotificationsToggled>(_onNotificationsToggled);
    on<ReminderNotificationsToggled>(_onReminderNotificationsToggled);
    on<GiftNotificationsToggled>(_onGiftNotificationsToggled);
    on<PriceNotificationsToggled>(_onPriceNotificationsToggled);
    on<InsightNotificationsToggled>(_onInsightNotificationsToggled);
    on<BiometricToggled>(_onBiometricToggled);
    on<PinSetRequested>(_onPinSetRequested);
    on<PinRemoveRequested>(_onPinRemoveRequested);
    on<PinVerifyRequested>(_onPinVerifyRequested);
    on<AutoBackupToggled>(_onAutoBackupToggled);
    on<BackupRequested>(_onBackupRequested);
    on<RestoreRequested>(_onRestoreRequested);
    on<FeedbackSubmitted>(_onFeedbackSubmitted);
    on<UpdateCheckRequested>(_onUpdateCheckRequested);
    on<InsightSettingsChanged>(_onInsightSettingsChanged);
    on<InsightSettingsResetRequested>(_onInsightSettingsResetRequested);
    on<ManualCurationRequested>(_onManualCurationRequested);
  }

  Future<void> _onLoadRequested(
    SettingsLoadRequested event,
    Emitter<SettingsState> emit,
  ) async {
    emit(const SettingsLoading());
    try {
      final results = await Future.wait([
        _repository.getAppSettings(),
        _repository.getSecuritySettings(),
        _repository.getBackupInfo(),
        _repository.getInsightSettings(),
        _repository.getAppVersion(),
      ]);

      emit(SettingsLoaded(
        appSettings: results[0] as AppSettings,
        securitySettings: results[1] as SecuritySettings,
        backupInfo: results[2] as BackupInfo,
        insightSettings: results[3] as InsightSettings,
        appVersion: results[4] as String,
      ));
    } catch (e) {
      emit(SettingsError('加载设置失败: $e'));
    }
  }

  Future<void> _onThemeModeChanged(
    ThemeModeChanged event,
    Emitter<SettingsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! SettingsLoaded) return;

    try {
      await _repository.setThemeMode(event.themeMode);
      emit(currentState.copyWith(
        appSettings: currentState.appSettings.copyWith(themeMode: event.themeMode),
      ));
    } catch (e) {
      emit(SettingsError('更改主题失败: $e'));
    }
  }

  Future<void> _onLanguageChanged(
    LanguageChanged event,
    Emitter<SettingsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! SettingsLoaded) return;

    try {
      await _repository.setLanguage(event.language);
      emit(currentState.copyWith(
        appSettings: currentState.appSettings.copyWith(language: event.language),
      ));
    } catch (e) {
      emit(SettingsError('更改语言失败: $e'));
    }
  }

  Future<void> _onNotificationsToggled(
    NotificationsToggled event,
    Emitter<SettingsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! SettingsLoaded) return;

    try {
      await _repository.setNotificationsEnabled(event.enabled);
      emit(currentState.copyWith(
        appSettings: currentState.appSettings.copyWith(
          notifications: currentState.appSettings.notifications.copyWith(
            enabled: event.enabled,
          ),
        ),
      ));
    } catch (e) {
      emit(SettingsError('更改通知设置失败: $e'));
    }
  }

  Future<void> _onReminderNotificationsToggled(
    ReminderNotificationsToggled event,
    Emitter<SettingsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! SettingsLoaded) return;

    try {
      await _repository.setReminderNotifications(event.enabled);
      emit(currentState.copyWith(
        appSettings: currentState.appSettings.copyWith(
          notifications: currentState.appSettings.notifications.copyWith(
            reminderNotifications: event.enabled,
          ),
        ),
      ));
    } catch (e) {
      emit(SettingsError('更改提醒通知设置失败: $e'));
    }
  }

  Future<void> _onGiftNotificationsToggled(
    GiftNotificationsToggled event,
    Emitter<SettingsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! SettingsLoaded) return;

    try {
      await _repository.setGiftNotifications(event.enabled);
      emit(currentState.copyWith(
        appSettings: currentState.appSettings.copyWith(
          notifications: currentState.appSettings.notifications.copyWith(
            giftNotifications: event.enabled,
          ),
        ),
      ));
    } catch (e) {
      emit(SettingsError('更改礼物通知设置失败: $e'));
    }
  }

  Future<void> _onPriceNotificationsToggled(
    PriceNotificationsToggled event,
    Emitter<SettingsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! SettingsLoaded) return;

    try {
      await _repository.setPriceNotifications(event.enabled);
      emit(currentState.copyWith(
        appSettings: currentState.appSettings.copyWith(
          notifications: currentState.appSettings.notifications.copyWith(
            priceNotifications: event.enabled,
          ),
        ),
      ));
    } catch (e) {
      emit(SettingsError('更改价格通知设置失败: $e'));
    }
  }

  Future<void> _onInsightNotificationsToggled(
    InsightNotificationsToggled event,
    Emitter<SettingsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! SettingsLoaded) return;

    try {
      await _repository.setInsightNotifications(event.enabled);
      emit(currentState.copyWith(
        appSettings: currentState.appSettings.copyWith(
          notifications: currentState.appSettings.notifications.copyWith(
            insightNotifications: event.enabled,
          ),
        ),
      ));
    } catch (e) {
      emit(SettingsError('更改智能洞察设置失败: $e'));
    }
  }

  Future<void> _onBiometricToggled(
    BiometricToggled event,
    Emitter<SettingsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! SettingsLoaded) return;

    try {
      await _repository.setBiometricEnabled(event.enabled);
      emit(currentState.copyWith(
        securitySettings: currentState.securitySettings.copyWith(
          biometricEnabled: event.enabled,
        ),
      ));
    } catch (e) {
      emit(SettingsError('更改生物识别设置失败: $e'));
    }
  }

  Future<void> _onPinSetRequested(
    PinSetRequested event,
    Emitter<SettingsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! SettingsLoaded) return;

    try {
      await _repository.setPin(event.pin);
      final newState = currentState.copyWith(
        securitySettings: currentState.securitySettings.copyWith(
          pinEnabled: true,
          hasPinCode: true,
        ),
      );
      emit(SettingsOperationSuccess('PIN码设置成功', newState));
    } catch (e) {
      emit(SettingsError('设置PIN码失败: $e'));
    }
  }

  Future<void> _onPinRemoveRequested(
    PinRemoveRequested event,
    Emitter<SettingsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! SettingsLoaded) return;

    try {
      await _repository.removePin();
      final newState = currentState.copyWith(
        securitySettings: currentState.securitySettings.copyWith(
          pinEnabled: false,
          hasPinCode: false,
        ),
      );
      emit(SettingsOperationSuccess('PIN码已移除', newState));
    } catch (e) {
      emit(SettingsError('移除PIN码失败: $e'));
    }
  }

  Future<void> _onPinVerifyRequested(
    PinVerifyRequested event,
    Emitter<SettingsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! SettingsLoaded) return;

    try {
      final success = await _repository.verifyPin(event.pin);
      emit(PinVerificationResult(success, currentState));
    } catch (e) {
      emit(SettingsError('验证PIN码失败: $e'));
    }
  }

  Future<void> _onAutoBackupToggled(
    AutoBackupToggled event,
    Emitter<SettingsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! SettingsLoaded) return;

    try {
      await _repository.setAutoBackupEnabled(event.enabled);
      emit(currentState.copyWith(
        backupInfo: currentState.backupInfo.copyWith(
          autoBackupEnabled: event.enabled,
        ),
      ));
    } catch (e) {
      emit(SettingsError('更改自动备份设置失败: $e'));
    }
  }

  Future<void> _onBackupRequested(
    BackupRequested event,
    Emitter<SettingsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! SettingsLoaded) return;

    try {
      await _repository.createBackup();
      final newBackupInfo = await _repository.getBackupInfo();
      final newState = currentState.copyWith(backupInfo: newBackupInfo);
      emit(SettingsOperationSuccess('备份成功', newState));
    } catch (e) {
      emit(SettingsError('备份失败: $e'));
    }
  }

  Future<void> _onRestoreRequested(
    RestoreRequested event,
    Emitter<SettingsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! SettingsLoaded) return;

    try {
      await _repository.restoreBackup();
      emit(SettingsOperationSuccess('恢复成功', currentState));
    } catch (e) {
      emit(SettingsError('恢复失败: $e'));
    }
  }

  Future<void> _onFeedbackSubmitted(
    FeedbackSubmitted event,
    Emitter<SettingsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! SettingsLoaded) return;

    try {
      await _repository.submitFeedback(event.content, event.contactInfo);
      emit(SettingsOperationSuccess('反馈提交成功，感谢您的意见！', currentState));
    } catch (e) {
      emit(SettingsError('提交反馈失败: $e'));
    }
  }

  Future<void> _onUpdateCheckRequested(
    UpdateCheckRequested event,
    Emitter<SettingsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! SettingsLoaded) return;

    try {
      final updateAvailable = await _repository.checkForUpdate();
      emit(UpdateCheckResult(updateAvailable, currentState));
    } catch (e) {
      emit(SettingsError('检查更新失败: $e'));
    }
  }

  Future<void> _onInsightSettingsChanged(
    InsightSettingsChanged event,
    Emitter<SettingsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! SettingsLoaded) return;

    try {
      await _repository.updateInsightSettings(event.settings);
      emit(currentState.copyWith(insightSettings: event.settings));
    } catch (e) {
      emit(SettingsError('更改智能洞察设置失败: $e'));
    }
  }

  Future<void> _onInsightSettingsResetRequested(
    InsightSettingsResetRequested event,
    Emitter<SettingsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! SettingsLoaded) return;

    try {
      await _repository.resetInsightSettings();
      final newState = currentState.copyWith(
        insightSettings: InsightSettings.defaults,
      );
      emit(SettingsOperationSuccess('智能洞察设置已重置为默认值', newState));
    } catch (e) {
      emit(SettingsError('重置智能洞察设置失败: $e'));
    }
  }

  Future<void> _onManualCurationRequested(
    ManualCurationRequested event,
    Emitter<SettingsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! SettingsLoaded) return;

    try {
      await _repository.triggerManualCuration();
      emit(SettingsOperationSuccess('时光轴整理已启动，请稍后刷新查看结果', currentState));
    } catch (e) {
      emit(SettingsError('触发整理失败: $e'));
    }
  }
}
