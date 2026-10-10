import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../app/di/injection.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../../shared/widgets/custom_app_bar.dart';
import '../bloc/settings_bloc.dart';

class HelpFeedbackPage extends StatelessWidget {
  const HelpFeedbackPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (context) =>
          getIt<SettingsBloc>()..add(const SettingsLoadRequested()),
      child: const _HelpFeedbackPageContent(),
    );
  }
}

class _HelpFeedbackPageContent extends StatelessWidget {
  const _HelpFeedbackPageContent();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: const CustomAppBar(title: '帮助与反馈'),
      body: BlocListener<SettingsBloc, SettingsState>(
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
          }
        },
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            // Quick help section
            _buildSectionTitle('快速帮助'),
            _buildSettingsCard([
              _HelpTile(
                icon: Icons.help_outline,
                title: '常见问题',
                subtitle: '查看使用中的常见问题解答',
                onTap: () => _showFAQPage(context),
              ),
              _HelpTile(
                icon: Icons.book_outlined,
                title: '使用指南',
                subtitle: '了解如何使用应用的各项功能',
                onTap: () => _showUserGuidePage(context),
              ),
              _HelpTile(
                icon: Icons.video_library_outlined,
                title: '视频教程',
                subtitle: '观看功能演示视频',
                onTap: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('视频教程即将上线')),
                  );
                },
                isLast: true,
              ),
            ]),
            const SizedBox(height: 24),

            // Feedback section
            _buildSectionTitle('意见反馈'),
            _buildSettingsCard([
              _HelpTile(
                icon: Icons.feedback_outlined,
                title: '提交反馈',
                subtitle: '告诉我们您的建议或遇到的问题',
                onTap: () => _showFeedbackDialog(context),
              ),
              _HelpTile(
                icon: Icons.bug_report_outlined,
                title: '报告问题',
                subtitle: '报告应用中的错误或异常',
                onTap: () => _showBugReportDialog(context),
              ),
              _HelpTile(
                icon: Icons.star_outline,
                title: '给我们评分',
                subtitle: '在应用商店为我们评分',
                onTap: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('感谢您的支持！')),
                  );
                },
                isLast: true,
              ),
            ]),
            const SizedBox(height: 24),

            // Contact section
            _buildSectionTitle('联系我们'),
            _buildSettingsCard([
              _HelpTile(
                icon: Icons.email_outlined,
                title: '邮件联系',
                subtitle: 'support@familysecretary.app',
                onTap: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('已复制邮件地址')),
                  );
                },
              ),
              _HelpTile(
                icon: Icons.chat_outlined,
                title: '在线客服',
                subtitle: '工作日 9:00-18:00',
                onTap: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('在线客服即将上线')),
                  );
                },
                isLast: true,
              ),
            ]),
          ],
        ),
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

  void _showFAQPage(BuildContext context) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (context) => const _FAQPage()),
    );
  }

  void _showUserGuidePage(BuildContext context) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (context) => const _UserGuidePage()),
    );
  }

  void _showFeedbackDialog(BuildContext context) {
    final contentController = TextEditingController();
    final contactController = TextEditingController();

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) => Container(
        padding: EdgeInsets.only(
          bottom: MediaQuery.of(sheetContext).viewInsets.bottom,
        ),
        decoration: const BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text('提交反馈', style: AppTextStyles.headline6),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.pop(sheetContext),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              TextField(
                controller: contentController,
                maxLines: 4,
                maxLength: 500,
                decoration: InputDecoration(
                  hintText: '请描述您的建议或问题...',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: contactController,
                decoration: InputDecoration(
                  hintText: '联系方式（选填）',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: () {
                    if (contentController.text.trim().isEmpty) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('请输入反馈内容'),
                          backgroundColor: AppColors.error,
                        ),
                      );
                      return;
                    }
                    context.read<SettingsBloc>().add(
                          FeedbackSubmitted(
                            contentController.text.trim(),
                            contactController.text.trim().isEmpty
                                ? null
                                : contactController.text.trim(),
                          ),
                        );
                    Navigator.pop(sheetContext);
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: const Text(
                    '提交',
                    style: TextStyle(color: Colors.white, fontSize: 16),
                  ),
                ),
              ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }

  void _showBugReportDialog(BuildContext context) {
    final contentController = TextEditingController();

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) => Container(
        padding: EdgeInsets.only(
          bottom: MediaQuery.of(sheetContext).viewInsets.bottom,
        ),
        decoration: const BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text('报告问题', style: AppTextStyles.headline6),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.pop(sheetContext),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.warning.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    const Icon(
                      Icons.info_outline,
                      color: AppColors.warning,
                      size: 20,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        '请详细描述问题发生的步骤，这将帮助我们更快定位问题',
                        style: AppTextStyles.caption.copyWith(
                          color: AppColors.warning,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: contentController,
                maxLines: 5,
                maxLength: 1000,
                decoration: InputDecoration(
                  hintText: '请描述您遇到的问题...\n\n例如：\n1. 打开xxx页面\n2. 点击xxx按钮\n3. 出现xxx错误',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: () {
                    if (contentController.text.trim().isEmpty) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('请输入问题描述'),
                          backgroundColor: AppColors.error,
                        ),
                      );
                      return;
                    }
                    context.read<SettingsBloc>().add(
                          FeedbackSubmitted(
                            '[Bug Report] ${contentController.text.trim()}',
                            null,
                          ),
                        );
                    Navigator.pop(sheetContext);
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: const Text(
                    '提交',
                    style: TextStyle(color: Colors.white, fontSize: 16),
                  ),
                ),
              ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }
}

class _HelpTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  final bool isLast;

  const _HelpTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
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

// FAQ Page
class _FAQPage extends StatelessWidget {
  const _FAQPage();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: const CustomAppBar(title: '常见问题'),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: const [
          _FAQItem(
            question: '如何添加家庭成员？',
            answer: '在首页点击"家人"标签，然后点击右上角的"+"按钮，填写成员信息即可添加新的家庭成员。',
          ),
          _FAQItem(
            question: '如何设置重要日期提醒？',
            answer: '进入"首页"，点击"重要日期"模块，可以添加生日、纪念日等重要日期。系统会在日期到来前自动发送提醒。',
          ),
          _FAQItem(
            question: '智能礼物推荐是如何工作的？',
            answer: '系统会根据家庭成员的年龄、性别、兴趣爱好等信息，结合即将到来的节日或纪念日，智能推荐合适的礼物。',
          ),
          _FAQItem(
            question: '如何使用价格监控功能？',
            answer: '在礼物推荐页面，点击商品卡片上的"关注"按钮，即可开启价格监控。当商品降价时，系统会发送通知提醒您。',
          ),
          _FAQItem(
            question: '数据是否安全？',
            answer: '您的数据会加密存储在服务器上，我们承诺不会将您的数据用于任何商业目的。您可以随时在设置中导出或删除您的数据。',
          ),
          _FAQItem(
            question: '如何联系客服？',
            answer: '您可以通过"帮助与反馈"页面的"联系我们"功能，通过邮件或在线客服与我们取得联系。',
          ),
        ],
      ),
    );
  }
}

class _FAQItem extends StatefulWidget {
  final String question;
  final String answer;

  const _FAQItem({
    required this.question,
    required this.answer,
  });

  @override
  State<_FAQItem> createState() => _FAQItemState();
}

class _FAQItemState extends State<_FAQItem> {
  bool _isExpanded = false;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          title: Text(
            widget.question,
            style: AppTextStyles.bodyText1.copyWith(
              fontWeight: FontWeight.w500,
            ),
          ),
          trailing: Icon(
            _isExpanded ? Icons.expand_less : Icons.expand_more,
            color: AppColors.primary,
          ),
          onExpansionChanged: (expanded) {
            setState(() => _isExpanded = expanded);
          },
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              child: Text(
                widget.answer,
                style: AppTextStyles.bodyText2.copyWith(
                  color: AppColors.textSecondary,
                  height: 1.5,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// User Guide Page
class _UserGuidePage extends StatelessWidget {
  const _UserGuidePage();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: const CustomAppBar(title: '使用指南'),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _GuideSection(
            title: '开始使用',
            icon: Icons.rocket_launch_outlined,
            steps: const [
              '注册并登录您的账户',
              '添加家庭成员信息',
              '设置重要日期和提醒',
              '开启智能秘书服务',
            ],
          ),
          const SizedBox(height: 16),
          _GuideSection(
            title: '家庭成员管理',
            icon: Icons.people_outline,
            steps: const [
              '点击"家人"标签进入成员列表',
              '点击"+"添加新成员',
              '填写姓名、生日、关系等信息',
              '点击成员卡片查看详情',
            ],
          ),
          const SizedBox(height: 16),
          _GuideSection(
            title: '重要日期',
            icon: Icons.calendar_today_outlined,
            steps: const [
              '在首页找到"重要日期"模块',
              '点击进入日期管理页面',
              '添加生日、纪念日等日期',
              '系统会自动发送提醒通知',
            ],
          ),
          const SizedBox(height: 16),
          _GuideSection(
            title: '礼物推荐',
            icon: Icons.card_giftcard_outlined,
            steps: const [
              '进入家庭成员详情页',
              '点击"推荐礼物"按钮',
              '查看系统智能推荐的礼物',
              '点击商品查看详情或购买',
            ],
          ),
        ],
      ),
    );
  }
}

class _GuideSection extends StatelessWidget {
  final String title;
  final IconData icon;
  final List<String> steps;

  const _GuideSection({
    required this.title,
    required this.icon,
    required this.steps,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: AppColors.primary, size: 22),
              ),
              const SizedBox(width: 12),
              Text(title, style: AppTextStyles.subtitle1),
            ],
          ),
          const SizedBox(height: 16),
          ...steps.asMap().entries.map((entry) {
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 24,
                    height: 24,
                    decoration: BoxDecoration(
                      color: AppColors.primary.withValues(alpha: 0.1),
                      shape: BoxShape.circle,
                    ),
                    child: Center(
                      child: Text(
                        '${entry.key + 1}',
                        style: AppTextStyles.caption.copyWith(
                          color: AppColors.primary,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      entry.value,
                      style: AppTextStyles.bodyText2.copyWith(
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }
}
