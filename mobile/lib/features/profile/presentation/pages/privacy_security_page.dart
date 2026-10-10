import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/di/injection.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../../shared/widgets/custom_app_bar.dart';
import '../../domain/entities/security_settings.dart';
import '../bloc/settings_bloc.dart';

class PrivacySecurityPage extends StatelessWidget {
  const PrivacySecurityPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (context) =>
          getIt<SettingsBloc>()..add(const SettingsLoadRequested()),
      child: const _PrivacySecurityPageContent(),
    );
  }
}

class _PrivacySecurityPageContent extends StatelessWidget {
  const _PrivacySecurityPageContent();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: const CustomAppBar(title: '隐私安全'),
      body: BlocConsumer<SettingsBloc, SettingsState>(
        listener: (context, state) {
          if (state is SettingsError) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                backgroundColor: AppColors.error,
              ),
            );
          } else if (state is SettingsOperationSuccess) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                backgroundColor: AppColors.success,
              ),
            );
          } else if (state is PinVerificationResult) {
            if (!state.success) {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('PIN码错误'),
                  backgroundColor: AppColors.error,
                ),
              );
            }
          }
        },
        builder: (context, state) {
          if (state is SettingsLoading) {
            return const Center(child: CircularProgressIndicator());
          }

          SecuritySettings settings = const SecuritySettings();
          if (state is SettingsLoaded) {
            settings = state.securitySettings;
          } else if (state is SettingsOperationSuccess) {
            settings = state.currentState.securitySettings;
          } else if (state is PinVerificationResult) {
            settings = state.currentState.securitySettings;
          }

          return ListView(
            padding: const EdgeInsets.all(20),
            children: [
              // Security info card
              _buildSecurityInfoCard(settings),
              const SizedBox(height: 24),

              // Security settings
              _buildSectionTitle('安全设置'),
              _buildSettingsCard([
                _SecurityToggleTile(
                  icon: Icons.fingerprint,
                  title: '生物识别',
                  subtitle: '使用指纹或面容解锁应用',
                  value: settings.biometricEnabled,
                  onChanged: (value) {
                    context.read<SettingsBloc>().add(BiometricToggled(value));
                  },
                ),
                _PinSettingTile(
                  hasPinCode: settings.hasPinCode,
                  pinEnabled: settings.pinEnabled,
                ),
              ]),
              const SizedBox(height: 24),

              // Privacy settings
              _buildSectionTitle('隐私设置'),
              _buildSettingsCard([
                _PrivacyTile(
                  icon: Icons.visibility_outlined,
                  title: '隐藏敏感信息',
                  subtitle: '在任务切换时隐藏应用内容',
                ),
                _PrivacyTile(
                  icon: Icons.history,
                  title: '清除搜索历史',
                  subtitle: '清除应用内的搜索记录',
                  onTap: () => _showClearHistoryDialog(context),
                  isLast: true,
                ),
              ]),
              const SizedBox(height: 24),

              // Data Permission settings
              _buildSectionTitle('数据权限'),
              _buildSettingsCard([
                _PrivacyTile(
                  icon: Icons.sync_alt,
                  title: '数据连接管理',
                  subtitle: '管理已连接的外部数据源和使用权限',
                  onTap: () => context.push(Routes.appSettings),
                  isLast: true,
                ),
              ]),
            ],
          );
        },
      ),
    );
  }

  Widget _buildSecurityInfoCard(SecuritySettings settings) {
    final int securityScore = _calculateSecurityScore(settings);
    final String securityLevel = securityScore >= 80
        ? '安全等级高'
        : securityScore >= 50
            ? '安全等级中'
            : '安全等级低';
    final Color scoreColor = securityScore >= 80
        ? AppColors.success
        : securityScore >= 50
            ? AppColors.warning
            : AppColors.error;

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                width: 60,
                height: 60,
                decoration: BoxDecoration(
                  color: scoreColor.withValues(alpha: 0.1),
                  shape: BoxShape.circle,
                ),
                child: Center(
                  child: Text(
                    '$securityScore',
                    style: AppTextStyles.headline5.copyWith(
                      color: scoreColor,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(securityLevel, style: AppTextStyles.subtitle1),
                    const SizedBox(height: 4),
                    Text(
                      '开启更多安全选项提升账户安全',
                      style: AppTextStyles.caption.copyWith(
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: securityScore / 100,
              backgroundColor: AppColors.divider,
              valueColor: AlwaysStoppedAnimation<Color>(scoreColor),
              minHeight: 6,
            ),
          ),
        ],
      ),
    );
  }

  int _calculateSecurityScore(SecuritySettings settings) {
    int score = 20; // Base score
    if (settings.biometricEnabled) score += 40;
    if (settings.pinEnabled && settings.hasPinCode) score += 40;
    return score;
  }

  Widget _buildSectionTitle(String title) {
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 8),
      child: Text(
        title,
        style: AppTextStyles.subtitle2.copyWith(
          color: AppColors.textSecondary,
        ),
      ),
    );
  }

  Widget _buildSettingsCard(List<Widget> children) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(children: children),
    );
  }

  void _showClearHistoryDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('清除搜索历史'),
        content: const Text('确定要清除所有搜索历史记录吗？此操作不可撤销。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(dialogContext);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('搜索历史已清除'),
                  backgroundColor: AppColors.success,
                ),
              );
            },
            child: const Text('确定', style: TextStyle(color: AppColors.error)),
          ),
        ],
      ),
    );
  }
}

class _SecurityToggleTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final bool value;
  final ValueChanged<bool> onChanged;

  const _SecurityToggleTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        border: Border(
          bottom: BorderSide(color: AppColors.divider, width: 0.5),
        ),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        leading: Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: AppColors.primary.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(icon, color: AppColors.primary, size: 22),
        ),
        title: Text(title, style: AppTextStyles.bodyText1),
        subtitle: Text(
          subtitle,
          style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
        ),
        trailing: Switch(
          value: value,
          onChanged: onChanged,
          activeColor: AppColors.primary,
        ),
      ),
    );
  }
}

class _PinSettingTile extends StatelessWidget {
  final bool hasPinCode;
  final bool pinEnabled;

  const _PinSettingTile({
    required this.hasPinCode,
    required this.pinEnabled,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      leading: Container(
        width: 40,
        height: 40,
        decoration: BoxDecoration(
          color: AppColors.primary.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(10),
        ),
        child: const Icon(Icons.pin_outlined, color: AppColors.primary, size: 22),
      ),
      title: Text('PIN码', style: AppTextStyles.bodyText1),
      subtitle: Text(
        hasPinCode ? '已设置PIN码' : '未设置PIN码',
        style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
      ),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (hasPinCode)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: AppColors.success.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                '已开启',
                style: AppTextStyles.caption.copyWith(color: AppColors.success),
              ),
            ),
          const SizedBox(width: 8),
          const Icon(Icons.chevron_right, color: AppColors.textTertiary),
        ],
      ),
      onTap: () => _showPinDialog(context),
    );
  }

  void _showPinDialog(BuildContext context) {
    if (hasPinCode) {
      _showManagePinDialog(context);
    } else {
      _showSetPinDialog(context);
    }
  }

  void _showSetPinDialog(BuildContext context) {
    final pinController = TextEditingController();
    final confirmController = TextEditingController();

    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('设置PIN码'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: pinController,
              keyboardType: TextInputType.number,
              maxLength: 6,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'PIN码 (4-6位数字)',
                counterText: '',
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: confirmController,
              keyboardType: TextInputType.number,
              maxLength: 6,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: '确认PIN码',
                counterText: '',
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () {
              final pin = pinController.text;
              final confirm = confirmController.text;

              if (pin.length < 4) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('PIN码至少需要4位数字'),
                    backgroundColor: AppColors.error,
                  ),
                );
                return;
              }

              if (pin != confirm) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('两次输入的PIN码不一致'),
                    backgroundColor: AppColors.error,
                  ),
                );
                return;
              }

              context.read<SettingsBloc>().add(PinSetRequested(pin));
              Navigator.pop(dialogContext);
            },
            child: const Text('确定'),
          ),
        ],
      ),
    );
  }

  void _showManagePinDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('PIN码管理'),
        content: const Text('您可以修改或移除PIN码'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(dialogContext);
              _showSetPinDialog(context);
            },
            child: const Text('修改PIN码'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(dialogContext);
              _showRemovePinDialog(context);
            },
            child: const Text('移除PIN码', style: TextStyle(color: AppColors.error)),
          ),
        ],
      ),
    );
  }

  void _showRemovePinDialog(BuildContext context) {
    final pinController = TextEditingController();

    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('移除PIN码'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('请输入当前PIN码以确认移除'),
            const SizedBox(height: 16),
            TextField(
              controller: pinController,
              keyboardType: TextInputType.number,
              maxLength: 6,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: '当前PIN码',
                counterText: '',
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () {
              // In a real app, we would verify the PIN first
              context.read<SettingsBloc>().add(const PinRemoveRequested());
              Navigator.pop(dialogContext);
            },
            child: const Text('确认移除', style: TextStyle(color: AppColors.error)),
          ),
        ],
      ),
    );
  }
}

class _PrivacyTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback? onTap;
  final bool isLast;

  const _PrivacyTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    this.onTap,
    this.isLast = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        border: isLast
            ? null
            : const Border(
                bottom: BorderSide(color: AppColors.divider, width: 0.5),
              ),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        leading: Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: AppColors.primary.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(icon, color: AppColors.primary, size: 22),
        ),
        title: Text(title, style: AppTextStyles.bodyText1),
        subtitle: Text(
          subtitle,
          style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
        ),
        trailing: const Icon(Icons.chevron_right, color: AppColors.textTertiary),
        onTap: onTap,
      ),
    );
  }
}
