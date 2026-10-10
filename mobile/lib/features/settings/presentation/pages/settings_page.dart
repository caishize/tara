import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/di/injection.dart';
import '../../../../shared/utils/relation_utils.dart';
import '../../../../shared/widgets/avatar_with_initials.dart';
import '../../../../shared/widgets/section_card.dart';
import '../../../auth/presentation/bloc/auth_bloc.dart';
import '../../../members/presentation/bloc/members_bloc.dart';
import '../../../profile/presentation/bloc/profile_bloc.dart';

/// Settings page (设置).
/// User profile, member management, preferences, and about.
class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key});

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  late MembersBloc _membersBloc;
  late ProfileBloc _profileBloc;
  late AuthBloc _authBloc;

  @override
  void initState() {
    super.initState();
    _membersBloc = getIt<MembersBloc>();
    _profileBloc = getIt<ProfileBloc>();
    _authBloc = getIt<AuthBloc>();

    // Load members and profile data
    _membersBloc.add(const MembersLoadRequested());
    _profileBloc.add(const ProfileLoadRequested());
  }

  @override
  Widget build(BuildContext context) {
    return MultiBlocProvider(
      providers: [
        BlocProvider.value(value: _membersBloc),
        BlocProvider.value(value: _profileBloc),
        BlocProvider.value(value: _authBloc),
      ],
      child: Scaffold(
        backgroundColor: AppColors.background,
        body: SafeArea(
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildHeader(),
                const SizedBox(height: 16),
                _buildProfileCard(context),
                const SizedBox(height: 16),
                _buildMemberManagement(context),
                const SizedBox(height: 16),
                _buildPreferences(context),
                const SizedBox(height: 16),
                _buildAccountSection(context),
                const SizedBox(height: 16),
                _buildAbout(context),
                const SizedBox(height: 24),
                _buildLogoutButton(context),
                const SizedBox(height: 32),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return const Padding(
      padding: EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '设置',
            style: TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.w700,
              color: AppColors.textPrimary,
            ),
          ),
          SizedBox(height: 4),
          Text(
            '管理你的守护者',
            style: TextStyle(
              fontSize: 14,
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildProfileCard(BuildContext context) {
    return BlocBuilder<AuthBloc, AuthState>(
      builder: (context, authState) {
        String userName = '';
        String? userEmail;

        if (authState is AuthAuthenticated) {
          userName = authState.user.username;
          userEmail = authState.user.email;
        }

        // Get display name (use username or email prefix)
        String displayName = userName;
        String avatarName = userName;

        if (userName.isEmpty && userEmail != null) {
          // Use email prefix as fallback
          displayName = userEmail.split('@').first;
          avatarName = displayName;
        } else if (userName.isEmpty) {
          displayName = '我的账户';
          avatarName = '我';
        }

        if (userName.isNotEmpty) {
          // If it looks like a Chinese name, use first character for avatar
          final firstChar = userName.characters.first;
          if (RegExp(r'[\u4e00-\u9fa5]').hasMatch(firstChar)) {
            avatarName = firstChar;
          }
        }

        return BlocBuilder<ProfileBloc, ProfileState>(
          builder: (context, profileState) {
            int memberCount = 0;
            int daysActive = 0;

            if (profileState is ProfileLoaded) {
              memberCount = profileState.stats.familyMemberCount;
              daysActive = profileState.stats.daysSinceJoined;
            }

            // Build the subtitle text
            String subtitleText;
            if (userEmail != null && userEmail.isNotEmpty) {
              subtitleText = userEmail;
            } else if (daysActive > 0 || memberCount > 0) {
              subtitleText = '已使用 $daysActive 天 · $memberCount 位家人';
            } else {
              subtitleText = '点击查看账户详情';
            }

            return GestureDetector(
              onTap: () => context.push(Routes.profile),
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 16),
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: AppColors.cardShadow,
                ),
                child: Row(
                  children: [
                    AvatarWithInitials(
                      name: avatarName,
                      size: 64,
                      backgroundColor: AppColors.badgeGreen,
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            displayName,
                            style: const TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.w600,
                              color: AppColors.textPrimary,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            subtitleText,
                            style: const TextStyle(
                              fontSize: 14,
                              color: AppColors.textSecondary,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const Icon(
                      Icons.chevron_right,
                      color: AppColors.textTertiary,
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  Widget _buildMemberManagement(BuildContext context) {
    return BlocBuilder<MembersBloc, MembersState>(
      builder: (context, state) {
        int familyCount = 0;
        int workCount = 0;
        int friendCount = 0;
        int otherCount = 0;

        if (state is MembersLoaded) {
          for (final member in state.members) {
            final category = RelationUtils.getRelationCategory(member.relation);
            switch (category) {
              case 'family':
                familyCount++;
                break;
              case 'work':
                workCount++;
                break;
              case 'friend':
                friendCount++;
                break;
              default:
                otherCount++;
            }
          }
        }

        return SectionCard(
          title: '成员管理',
          padding: const EdgeInsets.fromLTRB(0, 0, 0, 8),
          child: Column(
            children: [
              _buildMemberTypeRow(
                context,
                icon: Icons.family_restroom,
                iconColor: AppColors.badgePink,
                title: '家庭成员',
                count: familyCount,
                onTap: () => context.push(Routes.memberList(filter: 'family')),
              ),
              _buildMemberTypeRow(
                context,
                icon: Icons.work_outline,
                iconColor: AppColors.badgeBlue,
                title: '工作伙伴',
                count: workCount,
                onTap: () => context.push(Routes.memberList(filter: 'business')),
              ),
              _buildMemberTypeRow(
                context,
                icon: Icons.favorite_outline,
                iconColor: AppColors.badgeOrange,
                title: '重要亲友',
                count: friendCount,
                onTap: () => context.push(Routes.memberList(filter: 'friend')),
              ),
              _buildMemberTypeRow(
                context,
                icon: Icons.person_outline,
                iconColor: AppColors.chipBackground,
                title: '普通联系人',
                count: otherCount,
                onTap: () => context.push(Routes.memberList(filter: 'other')),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildMemberTypeRow(
    BuildContext context, {
    required IconData icon,
    required Color iconColor,
    required String title,
    required int count,
    VoidCallback? onTap,
  }) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: iconColor,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(
                icon,
                color: iconColor == AppColors.chipBackground
                    ? AppColors.textSecondary
                    : AppColors.textPrimary.withValues(alpha: 0.7),
                size: 20,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                title,
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w500,
                  color: AppColors.textPrimary,
                ),
              ),
            ),
            Text(
              '${count}人',
              style: const TextStyle(
                fontSize: 14,
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(width: 8),
            Icon(
              Icons.chevron_right,
              color: AppColors.textTertiary,
              size: 20,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPreferences(BuildContext context) {
    return SectionCard(
      title: '偏好设置',
      padding: const EdgeInsets.fromLTRB(0, 0, 0, 8),
      child: Column(
        children: [
          _buildSettingsRow(
            icon: Icons.settings_outlined,
            title: '应用设置',
            subtitle: '主题、语言、通知',
            onTap: () => context.push(Routes.appSettings),
          ),
          _buildSettingsRow(
            icon: Icons.psychology_outlined,
            title: '洞察设置',
            subtitle: 'AI分析与时光轴整理',
            onTap: () => context.push(Routes.insightSettings),
          ),
          _buildSettingsRow(
            icon: Icons.link_outlined,
            title: '数据连接',
            subtitle: '管理外部数据源',
            onTap: () => context.push(Routes.appSettings),
          ),
          _buildSettingsRow(
            icon: Icons.cloud_outlined,
            title: '数据备份',
            subtitle: '导出、备份、清除',
            onTap: () => context.push(Routes.dataBackup),
          ),
          _buildSettingsRow(
            icon: Icons.security_outlined,
            title: '隐私安全',
            subtitle: '密码、指纹、数据保护',
            onTap: () => context.push(Routes.privacySecurity),
          ),
        ],
      ),
    );
  }

  Widget _buildSettingsRow({
    required IconData icon,
    required String title,
    String? subtitle,
    VoidCallback? onTap,
  }) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            Icon(
              icon,
              color: AppColors.textSecondary,
              size: 22,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w500,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  if (subtitle != null)
                    Text(
                      subtitle,
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppColors.textSecondary,
                      ),
                    ),
                ],
              ),
            ),
            Icon(
              Icons.chevron_right,
              color: AppColors.textTertiary,
              size: 20,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAbout(BuildContext context) {
    return SectionCard(
      title: '关于',
      padding: const EdgeInsets.fromLTRB(0, 0, 0, 8),
      child: Column(
        children: [
          _buildAboutRow(
            title: '版本',
            value: '1.0.0',
            onTap: null,
          ),
          _buildSettingsRow(
            icon: Icons.help_outline,
            title: '帮助与反馈',
            onTap: () => context.push(Routes.helpFeedback),
          ),
        ],
      ),
    );
  }

  Widget _buildAccountSection(BuildContext context) {
    return SectionCard(
      title: '账户',
      padding: const EdgeInsets.fromLTRB(0, 0, 0, 8),
      child: Column(
        children: [
          _buildSettingsRow(
            icon: Icons.person_outline,
            title: '编辑资料',
            subtitle: '修改用户名、昵称',
            onTap: () => context.push(Routes.editProfile),
          ),
          _buildSettingsRow(
            icon: Icons.lock_outline,
            title: '修改密码',
            subtitle: '更新账户密码',
            onTap: () => context.push(Routes.changePassword),
          ),
          _buildSettingsRow(
            icon: Icons.delete_outline,
            title: '注销账户',
            subtitle: '永久删除账户及数据',
            onTap: () => context.push(Routes.deleteAccount),
          ),
        ],
      ),
    );
  }

  Widget _buildLogoutButton(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: SizedBox(
        width: double.infinity,
        child: OutlinedButton(
          onPressed: () => _showLogoutConfirmation(context),
          style: OutlinedButton.styleFrom(
            foregroundColor: AppColors.error,
            side: const BorderSide(color: AppColors.error),
            padding: const EdgeInsets.symmetric(vertical: 14),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          child: const Text(
            '退出登录',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w500,
            ),
          ),
        ),
      ),
    );
  }

  void _showLogoutConfirmation(BuildContext context) {
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('退出登录'),
        content: const Text('确定要退出登录吗？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () {
              Navigator.of(dialogContext).pop();
              _authBloc.add(const AuthLogoutRequested());
              context.go(Routes.login);
            },
            style: TextButton.styleFrom(
              foregroundColor: AppColors.error,
            ),
            child: const Text('退出'),
          ),
        ],
      ),
    );
  }

  Widget _buildAboutRow({
    required String title,
    required String value,
    VoidCallback? onTap,
  }) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            Text(
              title,
              style: const TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w500,
                color: AppColors.textPrimary,
              ),
            ),
            const Spacer(),
            Text(
              value,
              style: const TextStyle(
                fontSize: 14,
                color: AppColors.textSecondary,
              ),
            ),
            if (onTap != null) ...[
              const SizedBox(width: 8),
              Icon(
                Icons.chevron_right,
                color: AppColors.textTertiary,
                size: 20,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
