import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/di/injection.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../auth/presentation/bloc/auth_bloc.dart';
import '../bloc/profile_bloc.dart';
import '../widgets/profile_header_card.dart';
import '../widgets/stats_card.dart';
import '../widgets/secretary_report_card.dart';
import '../widgets/memory_card.dart';

class ProfilePage extends StatelessWidget {
  const ProfilePage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (context) => getIt<ProfileBloc>()..add(const ProfileLoadRequested()),
      child: const _ProfilePageContent(),
    );
  }
}

class _ProfilePageContent extends StatelessWidget {
  const _ProfilePageContent();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: BlocConsumer<ProfileBloc, ProfileState>(
          listener: (context, state) {
            if (state is ProfileError) {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text(state.message),
                  backgroundColor: AppColors.error,
                ),
              );
            } else if (state is ServiceOperationSuccess) {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text(state.message),
                  backgroundColor: AppColors.success,
                ),
              );
            }
          },
          builder: (context, state) {
            if (state is ProfileLoading) {
              return const Center(
                child: CircularProgressIndicator(),
              );
            }

            ProfileLoaded? loaded;
            if (state is ProfileLoaded) {
              loaded = state;
            } else if (state is ServiceOperationInProgress) {
              loaded = state.previousState;
            } else if (state is ServiceOperationSuccess) {
              loaded = state.currentState;
            }

            return RefreshIndicator(
              onRefresh: () async {
                context.read<ProfileBloc>().add(const ProfileRefreshRequested());
              },
              child: ListView(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 12,
                ),
                children: [
                  // Header title
                  const Padding(
                    padding: EdgeInsets.only(bottom: 12),
                    child: Text(
                      '个人中心',
                      style: TextStyle(
                        fontSize: 17,
                        fontWeight: FontWeight.w600,
                        color: Color(0xFF1A1918),
                      ),
                    ),
                  ),

                  // 1. Profile Header Card
                  Builder(
                    builder: (context) {
                      final authState = context.watch<AuthBloc>().state;
                      String displayName = '用户';
                      if (authState is AuthAuthenticated) {
                        displayName = authState.user.displayName;
                      }
                      return ProfileHeaderCard(
                        displayName: displayName,
                        daysSinceJoined: loaded?.stats.daysSinceJoined ?? 0,
                        familyMemberCount: loaded?.stats.familyMemberCount ?? 0,
                        onEditTap: () {
                          context.push(Routes.editProfile);
                        },
                      );
                    },
                  ),
                  const SizedBox(height: 16),

                  // 2. Stats Card
                  StatsCard(
                    daysSinceJoined: loaded?.stats.daysSinceJoined ?? 0,
                    totalRecords: loaded?.memoryCount ?? 0,
                    reminderCount:
                        loaded?.activitySummary?.remindersSent ?? 0,
                    insightCount:
                        loaded?.activitySummary?.priceAlerts ?? 0,
                  ),
                  const SizedBox(height: 16),

                  // 3. Secretary Work Report Card
                  SecretaryReportCard(
                    totalTasks:
                        loaded?.activitySummary?.totalTasksCompleted ?? 0,
                    eventCount: loaded?.reportEventCount ?? 0,
                    memoryCount: loaded?.reportMemoryCount ?? 0,
                    reminderCount: loaded?.reportReminderCount ?? 0,
                    periodText:
                        loaded?.activitySummary?.periodText ?? '本周',
                  ),
                  const SizedBox(height: 16),

                  // 4. Insight History Card (洞察历史)
                  MemoryCard(
                    memoryCount: loaded?.memoryCount ?? 0,
                    latestInsight: loaded?.latestInsight,
                    onTap: () {
                      context.push(Routes.insightHistory);
                    },
                  ),
                  const SizedBox(height: 16),

                  // 5. Settings Group 1: 成员管理, 通知与简报
                  _SettingsGroup(
                    items: [
                      _SettingsItem(
                        icon: Icons.people_outline,
                        title: '成员管理',
                        onTap: () => context.push(Routes.familyMembers),
                      ),
                      _SettingsItem(
                        icon: Icons.notifications_outlined,
                        title: '通知与简报',
                        onTap: () => context.push(Routes.appSettings),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  // 6. Settings Group 2: 隐私安全, 记忆管理, 数据导出, 关于
                  _SettingsGroup(
                    items: [
                      _SettingsItem(
                        icon: Icons.shield_outlined,
                        title: '隐私安全',
                        onTap: () => context.push(Routes.privacySecurity),
                      ),
                      _SettingsItem(
                        icon: Icons.psychology_outlined,
                        title: '记忆管理',
                        onTap: () => context.push(Routes.memories),
                      ),
                      _SettingsItem(
                        icon: Icons.storage_outlined,
                        title: '数据管理',
                        onTap: () => context.push(Routes.dataBackup),
                      ),
                      _SettingsItem(
                        icon: Icons.info_outline,
                        title: '关于',
                        onTap: () => context.push(Routes.helpFeedback),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  // 7. Logout Button
                  _LogoutButton(),
                  const SizedBox(height: 32),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}

class _SettingsItem {
  final IconData icon;
  final String title;
  final VoidCallback? onTap;

  const _SettingsItem({
    required this.icon,
    required this.title,
    this.onTap,
  });
}

class _SettingsGroup extends StatelessWidget {
  final List<_SettingsItem> items;

  const _SettingsGroup({required this.items});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: [
          for (int i = 0; i < items.length; i++) ...[
            _buildRow(items[i], isLast: i == items.length - 1),
            if (i < items.length - 1) _buildDivider(),
          ],
        ],
      ),
    );
  }

  Widget _buildRow(_SettingsItem item, {bool isLast = false}) {
    return InkWell(
      onTap: item.onTap,
      borderRadius: isLast
          ? const BorderRadius.vertical(bottom: Radius.circular(12))
          : null,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        child: Row(
          children: [
            Icon(
              item.icon,
              color: AppColors.accentGreen,
              size: 20,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                item.title,
                style: const TextStyle(
                  fontSize: 15,
                  color: Color(0xFF1A1918),
                ),
              ),
            ),
            const Icon(
              Icons.chevron_right,
              color: Color(0xFF9C9B99),
              size: 18,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDivider() {
    return const Padding(
      padding: EdgeInsets.only(left: 48, right: 16),
      child: Divider(
        height: 1,
        thickness: 1,
        color: Color(0xFFE5E4E1),
      ),
    );
  }
}

class _LogoutButton extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => _showLogoutConfirmation(context),
      child: Container(
        height: 48,
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
        ),
        alignment: Alignment.center,
        child: const Text(
          '退出登录',
          style: TextStyle(
            fontSize: 15,
            color: Color(0xFFE53935),
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
              context.read<AuthBloc>().add(const AuthLogoutRequested());
              context.go(Routes.login);
            },
            style: TextButton.styleFrom(
              foregroundColor: const Color(0xFFE53935),
            ),
            child: const Text('退出'),
          ),
        ],
      ),
    );
  }
}
