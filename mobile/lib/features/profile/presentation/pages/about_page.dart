import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../app/di/injection.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../../shared/widgets/custom_app_bar.dart';
import '../bloc/settings_bloc.dart';

class AboutPage extends StatelessWidget {
  const AboutPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (context) =>
          getIt<SettingsBloc>()..add(const SettingsLoadRequested()),
      child: const _AboutPageContent(),
    );
  }
}

class _AboutPageContent extends StatelessWidget {
  const _AboutPageContent();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: const CustomAppBar(title: '关于我们'),
      body: BlocConsumer<SettingsBloc, SettingsState>(
        listener: (context, state) {
          if (state is UpdateCheckResult) {
            if (state.updateAvailable) {
              _showUpdateDialog(context);
            } else {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('已是最新版本'),
                  backgroundColor: AppColors.success,
                ),
              );
            }
          } else if (state is SettingsError) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                backgroundColor: AppColors.error,
              ),
            );
          }
        },
        builder: (context, state) {
          String version = '1.0.0';
          if (state is SettingsLoaded) {
            version = state.appVersion;
          } else if (state is UpdateCheckResult) {
            version = state.currentState.appVersion;
          }

          return ListView(
            padding: const EdgeInsets.all(20),
            children: [
              // App logo and info
              _buildAppInfoCard(version),
              const SizedBox(height: 24),

              // Version and update
              _buildSectionTitle('版本信息'),
              _buildSettingsCard([
                _AboutTile(
                  icon: Icons.info_outline,
                  title: '当前版本',
                  trailing: Text(
                    version,
                    style: AppTextStyles.bodyText2.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                ),
                _AboutTile(
                  icon: Icons.system_update_outlined,
                  title: '检查更新',
                  trailing: const Icon(
                    Icons.chevron_right,
                    color: AppColors.textTertiary,
                  ),
                  onTap: () {
                    context
                        .read<SettingsBloc>()
                        .add(const UpdateCheckRequested());
                  },
                  isLast: true,
                ),
              ]),
              const SizedBox(height: 24),

              // Legal info
              _buildSectionTitle('法律信息'),
              _buildSettingsCard([
                _AboutTile(
                  icon: Icons.description_outlined,
                  title: '用户协议',
                  trailing: const Icon(
                    Icons.chevron_right,
                    color: AppColors.textTertiary,
                  ),
                  onTap: () => _showLegalPage(context, '用户协议', _userAgreement),
                ),
                _AboutTile(
                  icon: Icons.privacy_tip_outlined,
                  title: '隐私政策',
                  trailing: const Icon(
                    Icons.chevron_right,
                    color: AppColors.textTertiary,
                  ),
                  onTap: () => _showLegalPage(context, '隐私政策', _privacyPolicy),
                ),
                _AboutTile(
                  icon: Icons.gavel_outlined,
                  title: '开源许可',
                  trailing: const Icon(
                    Icons.chevron_right,
                    color: AppColors.textTertiary,
                  ),
                  onTap: () => _showLicensesPage(context),
                  isLast: true,
                ),
              ]),
              const SizedBox(height: 24),

              // Social links
              _buildSectionTitle('关注我们'),
              _buildSocialLinks(context),
              const SizedBox(height: 32),

              // Copyright
              Center(
                child: Text(
                  '© 2024 家庭秘书. All rights reserved.',
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.textTertiary,
                  ),
                ),
              ),
              const SizedBox(height: 16),
            ],
          );
        },
      ),
    );
  }

  Widget _buildAppInfoCard(String version) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        children: [
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              gradient: AppColors.primaryGradient,
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Icon(
              Icons.family_restroom,
              size: 40,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 16),
          Text(
            '家庭秘书',
            style: AppTextStyles.headline5,
          ),
          const SizedBox(height: 4),
          Text(
            '版本 $version',
            style: AppTextStyles.caption.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            '智能家庭生活助手',
            style: AppTextStyles.bodyText2.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '让家庭生活更有温度',
            style: AppTextStyles.caption.copyWith(
              color: AppColors.textTertiary,
              fontStyle: FontStyle.italic,
            ),
          ),
        ],
      ),
    );
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

  Widget _buildSocialLinks(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          _SocialButton(
            icon: Icons.language,
            label: '官网',
            onTap: () => _launchUrl('https://familysecretary.app'),
          ),
          _SocialButton(
            icon: Icons.alternate_email,
            label: '微博',
            onTap: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('微博账号即将开通')),
              );
            },
          ),
          _SocialButton(
            icon: Icons.chat_bubble_outline,
            label: '微信',
            onTap: () => _showWeChatDialog(context),
          ),
          _SocialButton(
            icon: Icons.code,
            label: 'GitHub',
            onTap: () => _launchUrl('https://github.com/familysecretary'),
          ),
        ],
      ),
    );
  }

  void _showUpdateDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('发现新版本'),
        content: const Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('新版本已发布，建议您更新以获得最佳体验。'),
            SizedBox(height: 12),
            Text('更新内容:', style: TextStyle(fontWeight: FontWeight.bold)),
            SizedBox(height: 8),
            Text('• 优化了智能推荐算法'),
            Text('• 修复了已知问题'),
            Text('• 提升了应用性能'),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('稍后'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(dialogContext);
              // TODO: Navigate to app store
            },
            child: const Text('立即更新'),
          ),
        ],
      ),
    );
  }

  void _showLegalPage(BuildContext context, String title, String content) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => _LegalPage(title: title, content: content),
      ),
    );
  }

  void _showLicensesPage(BuildContext context) {
    showLicensePage(
      context: context,
      applicationName: '家庭秘书',
      applicationIcon: Container(
        width: 64,
        height: 64,
        decoration: BoxDecoration(
          gradient: AppColors.primaryGradient,
          borderRadius: BorderRadius.circular(16),
        ),
        child: const Icon(
          Icons.family_restroom,
          size: 32,
          color: Colors.white,
        ),
      ),
    );
  }

  void _showWeChatDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('关注微信公众号'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 150,
              height: 150,
              decoration: BoxDecoration(
                color: AppColors.background,
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Center(
                child: Icon(
                  Icons.qr_code,
                  size: 100,
                  color: AppColors.textTertiary,
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              '扫描二维码关注公众号',
              style: AppTextStyles.caption.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('关闭'),
          ),
        ],
      ),
    );
  }

  Future<void> _launchUrl(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }
}

class _AboutTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final Widget? trailing;
  final VoidCallback? onTap;
  final bool isLast;

  const _AboutTile({
    required this.icon,
    required this.title,
    this.trailing,
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
        trailing: trailing,
        onTap: onTap,
      ),
    );
  }
}

class _SocialButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _SocialButton({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.all(8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: AppColors.primary.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: AppColors.primary, size: 22),
            ),
            const SizedBox(height: 8),
            Text(
              label,
              style: AppTextStyles.caption.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LegalPage extends StatelessWidget {
  final String title;
  final String content;

  const _LegalPage({
    required this.title,
    required this.content,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: CustomAppBar(title: title),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            boxShadow: [AppColors.shadowLight],
          ),
          child: Text(
            content,
            style: AppTextStyles.bodyText2.copyWith(
              height: 1.8,
              color: AppColors.textSecondary,
            ),
          ),
        ),
      ),
    );
  }
}

const String _userAgreement = '''
家庭秘书用户协议

欢迎使用家庭秘书应用！

在使用本应用之前，请您仔细阅读本协议的所有条款。

1. 服务内容
家庭秘书是一款智能家庭生活助手应用，为用户提供家庭成员管理、重要日期提醒、智能礼物推荐、价格监控等服务。

2. 用户账号
2.1 用户需注册账号方可使用本应用的全部功能。
2.2 用户应妥善保管账号信息，对账号下的所有行为负责。
2.3 如发现账号被盗用，请立即联系客服处理。

3. 用户行为规范
3.1 用户应遵守国家法律法规，不得利用本应用从事违法活动。
3.2 用户不得利用本应用侵犯他人合法权益。
3.3 用户不得对本应用进行反向工程、反编译等操作。

4. 知识产权
本应用的所有内容（包括但不限于文字、图片、软件代码等）均受知识产权法保护。

5. 免责声明
5.1 本应用提供的礼物推荐、价格信息等仅供参考，不构成购买建议。
5.2 因不可抗力导致的服务中断，本应用不承担责任。

6. 协议修改
我们保留随时修改本协议的权利，修改后的协议将在应用内公布。

7. 联系我们
如有任何问题，请通过应用内的帮助与反馈功能联系我们。

最后更新日期：2024年1月1日
''';

const String _privacyPolicy = '''
家庭秘书隐私政策

我们深知个人信息对您的重要性，我们将按照法律法规要求，保护您的个人信息安全。

1. 信息收集
我们可能收集以下信息：
• 账号信息：手机号码、邮箱地址
• 家庭成员信息：姓名、生日、关系等
• 日期记录：重要日期、纪念日等
• 设备信息：设备型号、操作系统版本

2. 信息使用
我们使用收集的信息用于：
• 提供、维护和改进我们的服务
• 发送服务通知和提醒
• 提供个性化的礼物推荐
• 进行数据分析以改进产品

3. 信息共享
我们不会将您的个人信息出售给任何第三方。
仅在以下情况下可能共享信息：
• 获得您的明确同意
• 法律法规要求
• 保护我们的合法权益

4. 信息安全
我们采用多种安全技术和程序来保护您的信息：
• 数据加密传输和存储
• 访问控制和身份验证
• 定期安全审计

5. 您的权利
您有权：
• 访问和更正您的个人信息
• 删除您的账号和数据
• 撤回同意
• 导出您的数据

6. 未成年人保护
我们非常重视对未成年人个人信息的保护。如您是未成年人，请在监护人指导下使用本应用。

7. 隐私政策更新
我们可能会更新本隐私政策，更新后会在应用内通知您。

8. 联系我们
如有隐私相关问题，请通过以下方式联系：
邮箱：privacy@familysecretary.app

最后更新日期：2024年1月1日
''';
