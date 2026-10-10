import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/di/injection.dart';
import '../../domain/entities/insight_settings.dart';
import '../bloc/settings_bloc.dart';

/// Settings page for configuring AI insight generation cycles.
class InsightSettingsPage extends StatefulWidget {
  const InsightSettingsPage({super.key});

  @override
  State<InsightSettingsPage> createState() => _InsightSettingsPageState();
}

class _InsightSettingsPageState extends State<InsightSettingsPage> {
  late SettingsBloc _settingsBloc;

  @override
  void initState() {
    super.initState();
    _settingsBloc = getIt<SettingsBloc>()..add(const SettingsLoadRequested());
  }

  @override
  void dispose() {
    _settingsBloc.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocProvider.value(
      value: _settingsBloc,
      child: Scaffold(
        backgroundColor: AppColors.background,
        appBar: AppBar(
          backgroundColor: Colors.white,
          elevation: 0,
          centerTitle: true,
          title: const Text(
            '洞察设置',
            style: TextStyle(
              color: AppColors.textPrimary,
              fontWeight: FontWeight.w600,
            ),
          ),
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_ios, color: AppColors.textPrimary),
            onPressed: () => Navigator.of(context).pop(),
          ),
          actions: [
            BlocBuilder<SettingsBloc, SettingsState>(
              builder: (context, state) {
                if (state is SettingsLoaded) {
                  return TextButton(
                    onPressed: () {
                      _settingsBloc.add(const InsightSettingsResetRequested());
                    },
                    child: const Text('重置'),
                  );
                }
                return const SizedBox.shrink();
              },
            ),
          ],
        ),
        body: BlocConsumer<SettingsBloc, SettingsState>(
          listener: (context, state) {
            if (state is SettingsOperationSuccess) {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text(state.message),
                  behavior: SnackBarBehavior.floating,
                ),
              );
            } else if (state is SettingsError) {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text(state.message),
                  backgroundColor: AppColors.error,
                  behavior: SnackBarBehavior.floating,
                ),
              );
            }
          },
          builder: (context, state) {
            if (state is SettingsLoading) {
              return const Center(
                child: CircularProgressIndicator(),
              );
            }

            if (state is SettingsError) {
              return Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.error_outline, size: 48, color: AppColors.error),
                    const SizedBox(height: 16),
                    Text(state.message),
                    const SizedBox(height: 16),
                    ElevatedButton(
                      onPressed: () {
                        _settingsBloc.add(const SettingsLoadRequested());
                      },
                      child: const Text('重试'),
                    ),
                  ],
                ),
              );
            }

            InsightSettings settings = InsightSettings.defaults;
            if (state is SettingsLoaded) {
              settings = state.insightSettings;
            } else if (state is SettingsOperationSuccess) {
              settings = state.currentState.insightSettings;
            }

            return _buildSettingsList(settings);
          },
        ),
      ),
    );
  }

  Widget _buildSettingsList(InsightSettings settings) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildInfoCard(),
        const SizedBox(height: 16),
        _buildSettingCard(
          title: '情绪模式分析窗口',
          description: '分析多少天内的情绪模式来生成洞察',
          value: settings.emotionPatternWindowDays,
          suffix: '天',
          min: 1,
          max: 30,
          onChanged: (value) {
            _updateSetting(settings.copyWith(emotionPatternWindowDays: value));
          },
        ),
        const SizedBox(height: 12),
        _buildSettingCard(
          title: '关系提醒阈值',
          description: '超过多少天未联系会触发提醒',
          value: settings.relationshipReminderThresholdDays,
          suffix: '天',
          min: 7,
          max: 365,
          onChanged: (value) {
            _updateSetting(settings.copyWith(relationshipReminderThresholdDays: value));
          },
        ),
        const SizedBox(height: 12),
        _buildSettingCard(
          title: '洞察过期时间',
          description: '洞察生成后多少天内有效',
          value: settings.insightExpiryDays,
          suffix: '天',
          min: 1,
          max: 30,
          onChanged: (value) {
            _updateSetting(settings.copyWith(insightExpiryDays: value));
          },
        ),
        const SizedBox(height: 12),
        _buildSettingCard(
          title: '计划跟进提醒',
          description: '计划超过多少天未更新会提醒跟进',
          value: settings.oldPlanFollowupThresholdDays,
          suffix: '天',
          min: 1,
          max: 60,
          onChanged: (value) {
            _updateSetting(settings.copyWith(oldPlanFollowupThresholdDays: value));
          },
        ),
        const SizedBox(height: 12),
        _buildSettingCard(
          title: '行程提前提醒',
          description: '提前多少天提醒即将到来的行程',
          value: settings.upcomingTripCheckDays,
          suffix: '天',
          min: 1,
          max: 30,
          onChanged: (value) {
            _updateSetting(settings.copyWith(upcomingTripCheckDays: value));
          },
        ),
        const SizedBox(height: 24),
        _buildSectionHeader('时光轴整理'),
        const SizedBox(height: 12),
        _buildCurationInfoCard(),
        const SizedBox(height: 12),
        _buildIntervalSelector(settings),
        const SizedBox(height: 12),
        _buildSettingCard(
          title: '整理天数范围',
          description: '整理未来多少天内的日程',
          value: settings.curationDaysAhead,
          suffix: '天',
          min: 1,
          max: 30,
          onChanged: (value) {
            _updateSetting(settings.copyWith(curationDaysAhead: value));
          },
        ),
        const SizedBox(height: 12),
        _buildToggleCard(
          title: '创建行程时自动整理',
          description: '当创建新行程计划时，自动触发时光轴整理',
          value: settings.autoCurateOnTravelCreate,
          onChanged: (value) {
            _updateSetting(settings.copyWith(autoCurateOnTravelCreate: value));
          },
        ),
        const SizedBox(height: 12),
        _buildToggleCard(
          title: '事件变更时自动整理',
          description: '当创建、更新或删除事件时，自动触发时光轴整理',
          value: settings.autoCurateOnEventChange,
          onChanged: (value) {
            _updateSetting(settings.copyWith(autoCurateOnEventChange: value));
          },
        ),
        const SizedBox(height: 16),
        _buildManualCurationButton(),
        const SizedBox(height: 24),
      ],
    );
  }

  // Preset interval values in minutes
  static const List<int> _intervalPresets = [15, 30, 60, 120, 360, 720, 1440];

  static String _intervalLabel(int minutes) {
    if (minutes < 60) return '$minutes分钟';
    if (minutes == 60) return '1小时';
    if (minutes < 1440) return '${minutes ~/ 60}小时';
    return '24小时';
  }

  int _resolvePresetIndex(int minutes) {
    final exact = _intervalPresets.indexOf(minutes);
    if (exact >= 0) return exact;
    final closest = _intervalPresets.indexWhere((v) => v >= minutes);
    return closest.clamp(0, _intervalPresets.length - 1);
  }

  Widget _buildIntervalSelector(InsightSettings settings) {
    final sliderIndex = _resolvePresetIndex(settings.curationIntervalMinutes);

    return _buildSliderCard(
      title: '整理频率',
      description: '自动整理时光轴的最小间隔',
      displayValue: _intervalLabel(_intervalPresets[sliderIndex]),
      sliderValue: sliderIndex.toDouble(),
      min: 0,
      max: (_intervalPresets.length - 1).toDouble(),
      divisions: _intervalPresets.length - 1,
      minLabel: _intervalLabel(_intervalPresets.first),
      maxLabel: _intervalLabel(_intervalPresets.last),
      onChanged: (newValue) {
        _updateSetting(settings.copyWith(
          curationIntervalMinutes: _intervalPresets[newValue.round()],
        ));
      },
    );
  }

  Widget _buildInfoCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.primary.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(
            Icons.lightbulb_outline,
            color: AppColors.primary,
            size: 24,
          ),
          const SizedBox(width: 12),
          const Expanded(
            child: Text(
              '这些设置控制AI生成智能洞察的频率和范围。调整它们以获得更个性化的提醒体验。',
              style: TextStyle(
                fontSize: 13,
                color: AppColors.textSecondary,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSettingCard({
    required String title,
    required String description,
    required int value,
    required String suffix,
    required int min,
    required int max,
    required ValueChanged<int> onChanged,
  }) {
    return _buildSliderCard(
      title: title,
      description: description,
      displayValue: '$value$suffix',
      sliderValue: value.toDouble(),
      min: min.toDouble(),
      max: max.toDouble(),
      divisions: max - min,
      minLabel: '$min$suffix',
      maxLabel: '$max$suffix',
      onChanged: (newValue) => onChanged(newValue.round()),
    );
  }

  /// Shared slider card layout used by both _buildSettingCard and _buildIntervalSelector.
  Widget _buildSliderCard({
    required String title,
    required String description,
    required String displayValue,
    required double sliderValue,
    required double min,
    required double max,
    required int divisions,
    required String minLabel,
    required String maxLabel,
    required ValueChanged<double> onChanged,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: AppColors.cardShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      description,
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  displayValue,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppColors.primary,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Text(
                minLabel,
                style: const TextStyle(
                  fontSize: 12,
                  color: AppColors.textTertiary,
                ),
              ),
              Expanded(
                child: SliderTheme(
                  data: SliderTheme.of(context).copyWith(
                    activeTrackColor: AppColors.primary,
                    inactiveTrackColor: AppColors.divider,
                    thumbColor: AppColors.primary,
                    overlayColor: AppColors.primary.withValues(alpha: 0.2),
                  ),
                  child: Slider(
                    value: sliderValue,
                    min: min,
                    max: max,
                    divisions: divisions,
                    onChanged: onChanged,
                  ),
                ),
              ),
              Text(
                maxLabel,
                style: const TextStyle(
                  fontSize: 12,
                  color: AppColors.textTertiary,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title) {
    return Text(
      title,
      style: const TextStyle(
        fontSize: 16,
        fontWeight: FontWeight.w600,
        color: AppColors.textPrimary,
      ),
    );
  }

  Widget _buildCurationInfoCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.secondary.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(
            Icons.auto_fix_high,
            color: AppColors.secondary,
            size: 24,
          ),
          const SizedBox(width: 12),
          const Expanded(
            child: Text(
              'AI秘书会自动整理您的时光轴，合并重复事件，提取准确时间，关联相关任务和人物。',
              style: TextStyle(
                fontSize: 13,
                color: AppColors.textSecondary,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildToggleCard({
    required String title,
    required String description,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: AppColors.cardShadow,
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  description,
                  style: const TextStyle(
                    fontSize: 13,
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Switch(
            value: value,
            onChanged: onChanged,
            activeColor: AppColors.primary,
          ),
        ],
      ),
    );
  }

  Widget _buildManualCurationButton() {
    return BlocBuilder<SettingsBloc, SettingsState>(
      builder: (context, state) {
        final isLoading = state is SettingsLoading;
        return SizedBox(
          width: double.infinity,
          child: ElevatedButton.icon(
            onPressed: isLoading
                ? null
                : () {
                    _settingsBloc.add(const ManualCurationRequested());
                  },
            icon: isLoading
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Icon(Icons.refresh),
            label: Text(isLoading ? '整理中...' : '立即整理'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.secondary,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
        );
      },
    );
  }

  void _updateSetting(InsightSettings newSettings) {
    _settingsBloc.add(InsightSettingsChanged(newSettings));
  }
}
