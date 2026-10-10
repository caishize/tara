import 'package:flutter/material.dart';

import '../../domain/entities/data_connection.dart';
import '../../../../app/theme/app_colors.dart';

/// Widget for toggling data usage permissions
class PermissionToggle extends StatelessWidget {
  final UsagePermissions permissions;
  final ValueChanged<UsagePermissions> onChanged;

  const PermissionToggle({
    super.key,
    required this.permissions,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '数据使用范围',
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          '选择允许秘书使用此数据源的功能',
          style: theme.textTheme.bodySmall?.copyWith(
            color: AppColors.textSecondary,
          ),
        ),
        const SizedBox(height: 16),
        _buildToggleItem(
          context,
          title: '日常简报',
          subtitle: '在每日简报中包含此数据源的相关事件',
          icon: Icons.wb_sunny,
          value: permissions.dailyBriefing,
          onChanged: (value) {
            onChanged(permissions.copyWith(dailyBriefing: value));
          },
        ),
        _buildToggleItem(
          context,
          title: '智能建议',
          subtitle: '基于此数据生成个性化建议和提醒',
          icon: Icons.lightbulb,
          value: permissions.smartSuggestions,
          onChanged: (value) {
            onChanged(permissions.copyWith(smartSuggestions: value));
          },
        ),
        _buildToggleItem(
          context,
          title: '日程聚合',
          subtitle: '将日程同步到统一日程视图',
          icon: Icons.calendar_view_day,
          value: permissions.scheduleAggregation,
          onChanged: (value) {
            onChanged(permissions.copyWith(scheduleAggregation: value));
          },
        ),
        _buildToggleItem(
          context,
          title: '记忆系统',
          subtitle: '允许秘书记住相关信息以提供更精准服务',
          icon: Icons.psychology,
          value: permissions.memorySystem,
          onChanged: (value) {
            onChanged(permissions.copyWith(memorySystem: value));
          },
        ),
      ],
    );
  }

  Widget _buildToggleItem(
    BuildContext context, {
    required String title,
    required String subtitle,
    required IconData icon,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: (value ? AppColors.primary : Colors.grey).withOpacity(0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(
              icon,
              color: value ? AppColors.primary : Colors.grey,
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w500,
                  ),
                ),
                Text(
                  subtitle,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
            activeColor: AppColors.primary,
          ),
        ],
      ),
    );
  }
}
