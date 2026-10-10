import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/di/injection.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../shared/widgets/custom_app_bar.dart';
import '../../domain/entities/app_settings.dart';
import '../../domain/entities/insight_settings.dart';
import '../bloc/settings_bloc.dart';

class AppSettingsPage extends StatelessWidget {
  const AppSettingsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (context) =>
          getIt<SettingsBloc>()..add(const SettingsLoadRequested()),
      child: const _AppSettingsPageContent(),
    );
  }
}

class _AppSettingsPageContent extends StatefulWidget {
  const _AppSettingsPageContent();

  @override
  State<_AppSettingsPageContent> createState() =>
      _AppSettingsPageContentState();
}

class _AppSettingsPageContentState extends State<_AppSettingsPageContent> {
  // Local UI state for chip selections
  int _briefingTimeSlot = 0; // 0=晨, 1=午, 2=晚
  int _insightFrequency = 1; // 0=高, 1=中, 2=低
  bool _isCurating = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: const CustomAppBar(title: '通知与简报'),
      body: BlocConsumer<SettingsBloc, SettingsState>(
        listener: (context, state) {
          if (state is SettingsError) {
            if (_isCurating) setState(() => _isCurating = false);
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                backgroundColor: AppColors.error,
              ),
            );
          } else if (state is SettingsOperationSuccess) {
            if (_isCurating) setState(() => _isCurating = false);
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                duration: const Duration(seconds: 2),
              ),
            );
          }
        },
        builder: (context, state) {
          if (state is SettingsLoading) {
            return const Center(child: CircularProgressIndicator());
          }

          AppSettings settings = AppSettings.defaults();
          InsightSettings insightSettings = InsightSettings.defaults;
          if (state is SettingsLoaded) {
            settings = state.appSettings;
            insightSettings = state.insightSettings;
          } else if (state is SettingsOperationSuccess) {
            settings = state.currentState.appSettings;
            insightSettings = state.currentState.insightSettings;
          } else if (state is PinVerificationResult) {
            settings = state.currentState.appSettings;
            insightSettings = state.currentState.insightSettings;
          } else if (state is UpdateCheckResult) {
            settings = state.currentState.appSettings;
            insightSettings = state.currentState.insightSettings;
          }

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // Description
              const Text(
                '管理你的推送通知偏好，自定义接收内容和频率',
                style: TextStyle(
                  fontSize: 13,
                  color: Color(0xFF6D6C6A),
                  height: 1.4,
                ),
              ),
              const SizedBox(height: 20),

              // Section: 简报推送
              const _SectionLabel(text: '简报推送'),
              const SizedBox(height: 8),
              _SettingsGroup(
                children: [
                  _ToggleRow(
                    title: '每日简报',
                    description: '每天推送简报摘要',
                    value: settings.notifications.enabled,
                    onChanged: (v) {
                      context
                          .read<SettingsBloc>()
                          .add(NotificationsToggled(v));
                    },
                  ),
                  const _RowDivider(),
                  _ChipRow(
                    title: '推送时段',
                    description: '选择接收简报的时间',
                    options: const ['晨', '午', '晚'],
                    selectedIndex: _briefingTimeSlot,
                    onSelected: (i) => setState(() => _briefingTimeSlot = i),
                  ),
                ],
              ),
              const SizedBox(height: 20),

              // Section: 洞察推送
              const _SectionLabel(text: '洞察推送'),
              const SizedBox(height: 8),
              _SettingsGroup(
                children: [
                  _ToggleRow(
                    title: '洞察推送',
                    description: 'AI分析和关系洞察提醒',
                    value: settings.notifications.insightNotifications,
                    onChanged: (v) {
                      context
                          .read<SettingsBloc>()
                          .add(InsightNotificationsToggled(v));
                    },
                  ),
                  const _RowDivider(),
                  _ChipRow(
                    title: '推送频率',
                    description: '控制洞察推送的频次',
                    options: const ['高', '中', '低'],
                    selectedIndex: _insightFrequency,
                    onSelected: (i) =>
                        setState(() => _insightFrequency = i),
                  ),
                ],
              ),
              const SizedBox(height: 20),

              // Section: 其他通知
              const _SectionLabel(text: '其他通知'),
              const SizedBox(height: 8),
              _SettingsGroup(
                children: [
                  _ToggleRow(
                    title: '提醒推送',
                    description: '日程和重要日期提醒',
                    value: settings.notifications.reminderNotifications,
                    onChanged: (v) {
                      context
                          .read<SettingsBloc>()
                          .add(ReminderNotificationsToggled(v));
                    },
                  ),
                  const _RowDivider(),
                  _ToggleRow(
                    title: '人情提醒',
                    description: '生日、纪念日等人情往来提醒',
                    value: settings.notifications.giftNotifications,
                    onChanged: (v) {
                      context
                          .read<SettingsBloc>()
                          .add(GiftNotificationsToggled(v));
                    },
                  ),
                ],
              ),
              const SizedBox(height: 20),

              // Section: 洞察与整理
              const _SectionLabel(text: '洞察与整理'),
              const SizedBox(height: 8),
              _SettingsGroup(
                children: [
                  _CompactSliderRow(
                    title: '情绪分析窗口',
                    description: '分析近期情绪的天数范围',
                    value: insightSettings.emotionPatternWindowDays,
                    min: 1,
                    max: 30,
                    unit: '天',
                    onChanged: (v) {
                      context.read<SettingsBloc>().add(
                            InsightSettingsChanged(
                              insightSettings.copyWith(
                                emotionPatternWindowDays: v,
                              ),
                            ),
                          );
                    },
                  ),
                  const _RowDivider(),
                  _CompactSliderRow(
                    title: '关系提醒阈值',
                    description: '超过多少天未联系时提醒',
                    value: insightSettings.relationshipReminderThresholdDays,
                    min: 7,
                    max: 365,
                    unit: '天',
                    onChanged: (v) {
                      context.read<SettingsBloc>().add(
                            InsightSettingsChanged(
                              insightSettings.copyWith(
                                relationshipReminderThresholdDays: v,
                              ),
                            ),
                          );
                    },
                  ),
                  const _RowDivider(),
                  _CompactSliderRow(
                    title: '洞察有效期',
                    description: '洞察自动过期的天数',
                    value: insightSettings.insightExpiryDays,
                    min: 1,
                    max: 30,
                    unit: '天',
                    onChanged: (v) {
                      context.read<SettingsBloc>().add(
                            InsightSettingsChanged(
                              insightSettings.copyWith(
                                insightExpiryDays: v,
                              ),
                            ),
                          );
                    },
                  ),
                  const _RowDivider(),
                  _ActionRow(
                    title: _isCurating ? '整理中...' : '立即整理',
                    description: _isCurating
                        ? '正在后台整理数据，请稍候'
                        : '手动触发一次数据整理',
                    icon: Icons.auto_fix_high,
                    isLoading: _isCurating,
                    onTap: _isCurating
                        ? null
                        : () {
                            setState(() => _isCurating = true);
                            context
                                .read<SettingsBloc>()
                                .add(const ManualCurationRequested());
                          },
                  ),
                  const _RowDivider(),
                  _NavigationRow(
                    title: '完整洞察设置',
                    description: '查看和调整所有洞察参数',
                    onTap: () => context.push(Routes.insightSettings),
                  ),
                ],
              ),
            ],
          );
        },
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  final String text;
  const _SectionLabel({required this.text});

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(
        fontSize: 13,
        fontWeight: FontWeight.w600,
        color: Color(0xFF6D6C6A),
      ),
    );
  }
}

class _SettingsGroup extends StatelessWidget {
  final List<Widget> children;
  const _SettingsGroup({required this.children});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(children: children),
    );
  }
}

class _RowDivider extends StatelessWidget {
  const _RowDivider();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(horizontal: 16),
      child: Divider(height: 1, thickness: 1, color: Color(0xFFE5E4E1)),
    );
  }
}

class _ToggleRow extends StatelessWidget {
  final String title;
  final String description;
  final bool value;
  final ValueChanged<bool> onChanged;

  const _ToggleRow({
    required this.title,
    required this.description,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
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
                    fontWeight: FontWeight.w500,
                    color: Color(0xFF1A1918),
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  description,
                  style: const TextStyle(
                    fontSize: 12,
                    color: Color(0xFF9C9B99),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          _CustomToggle(value: value, onChanged: onChanged),
        ],
      ),
    );
  }
}

class _CustomToggle extends StatelessWidget {
  final bool value;
  final ValueChanged<bool> onChanged;

  const _CustomToggle({required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => onChanged(!value),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        width: 44,
        height: 26,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(13),
          color: value
              ? AppColors.accentGreen
              : const Color(0xFFEDECEA),
        ),
        child: AnimatedAlign(
          duration: const Duration(milliseconds: 200),
          alignment: value ? Alignment.centerRight : Alignment.centerLeft,
          child: Container(
            width: 22,
            height: 22,
            margin: const EdgeInsets.all(2),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: Colors.white,
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.08),
                  blurRadius: 3,
                  offset: const Offset(0, 1),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ChipRow extends StatelessWidget {
  final String title;
  final String description;
  final List<String> options;
  final int selectedIndex;
  final ValueChanged<int> onSelected;

  const _ChipRow({
    required this.title,
    required this.description,
    required this.options,
    required this.selectedIndex,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
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
                    fontWeight: FontWeight.w500,
                    color: Color(0xFF1A1918),
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  description,
                  style: const TextStyle(
                    fontSize: 12,
                    color: Color(0xFF9C9B99),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Row(
            children: List.generate(options.length, (i) {
              final isSelected = i == selectedIndex;
              return Padding(
                padding: EdgeInsets.only(left: i > 0 ? 8 : 0),
                child: GestureDetector(
                  onTap: () => onSelected(i),
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: isSelected
                          ? AppColors.accentGreen
                          : const Color(0xFFEDECEA),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Text(
                      options[i],
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight:
                            isSelected ? FontWeight.w600 : FontWeight.w500,
                        color: isSelected
                            ? Colors.white
                            : const Color(0xFF6D6C6A),
                      ),
                    ),
                  ),
                ),
              );
            }),
          ),
        ],
      ),
    );
  }
}

class _CompactSliderRow extends StatelessWidget {
  final String title;
  final String description;
  final int value;
  final int min;
  final int max;
  final String unit;
  final ValueChanged<int> onChanged;

  const _CompactSliderRow({
    required this.title,
    required this.description,
    required this.value,
    required this.min,
    required this.max,
    required this.unit,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w500,
                        color: Color(0xFF1A1918),
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      description,
                      style: const TextStyle(
                        fontSize: 12,
                        color: Color(0xFF9C9B99),
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 4,
                ),
                decoration: BoxDecoration(
                  color: AppColors.accentGreen.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '$value$unit',
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: AppColors.accentGreen,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          SliderTheme(
            data: SliderTheme.of(context).copyWith(
              activeTrackColor: AppColors.accentGreen,
              inactiveTrackColor: const Color(0xFFEDECEA),
              thumbColor: AppColors.accentGreen,
              overlayColor: AppColors.accentGreen.withValues(alpha: 0.12),
              trackHeight: 4,
              thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 8),
            ),
            child: Slider(
              value: value.toDouble(),
              min: min.toDouble(),
              max: max.toDouble(),
              divisions: max - min,
              onChanged: (v) => onChanged(v.round()),
            ),
          ),
        ],
      ),
    );
  }
}

class _ActionRow extends StatelessWidget {
  final String title;
  final String description;
  final IconData icon;
  final VoidCallback? onTap;
  final bool isLoading;

  const _ActionRow({
    required this.title,
    required this.description,
    required this.icon,
    required this.onTap,
    this.isLoading = false,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w500,
                      color: isLoading
                          ? const Color(0xFF9C9B99)
                          : const Color(0xFF1A1918),
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    description,
                    style: const TextStyle(
                      fontSize: 12,
                      color: Color(0xFF9C9B99),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            if (isLoading)
              const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: AppColors.accentGreen,
                ),
              )
            else
              Icon(icon, size: 20, color: AppColors.accentGreen),
          ],
        ),
      ),
    );
  }
}

class _NavigationRow extends StatelessWidget {
  final String title;
  final String description;
  final VoidCallback onTap;

  const _NavigationRow({
    required this.title,
    required this.description,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
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
                      fontWeight: FontWeight.w500,
                      color: Color(0xFF1A1918),
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    description,
                    style: const TextStyle(
                      fontSize: 12,
                      color: Color(0xFF9C9B99),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            const Icon(
              Icons.chevron_right,
              size: 20,
              color: Color(0xFF9C9B99),
            ),
          ],
        ),
      ),
    );
  }
}
