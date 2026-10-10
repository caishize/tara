import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../app/di/injection.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../data/datasources/relationship_remote_datasource.dart';
import '../bloc/smart_groups_bloc.dart';

/// Smart Groups page for AI-powered member categorization
class SmartGroupsPage extends StatelessWidget {
  const SmartGroupsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (context) => SmartGroupsBloc(
        dataSource: getIt<RelationshipRemoteDataSource>(),
      )..add(const SmartGroupsLoadRequested()),
      child: const _SmartGroupsView(),
    );
  }
}

class _SmartGroupsView extends StatelessWidget {
  const _SmartGroupsView();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1E293B),
        title: const Text('智能分组'),
        actions: [
          IconButton(
            onPressed: () => _showReminders(context),
            icon: const Icon(Icons.notifications_outlined),
          ),
        ],
      ),
      body: BlocBuilder<SmartGroupsBloc, SmartGroupsState>(
        builder: (context, state) {
          if (state is SmartGroupsLoading) {
            return const Center(
              child: CircularProgressIndicator(color: AppColors.primary),
            );
          }

          if (state is SmartGroupsError) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.error_outline, size: 48, color: Colors.white38),
                  const SizedBox(height: 16),
                  Text(
                    state.message,
                    style: AppTextStyles.subtitle1.copyWith(color: Colors.white54),
                  ),
                  const SizedBox(height: 16),
                  TextButton(
                    onPressed: () => context
                        .read<SmartGroupsBloc>()
                        .add(const SmartGroupsRefreshRequested()),
                    child: const Text('重试'),
                  ),
                ],
              ),
            );
          }

          if (state is SmartGroupsLoaded) {
            if (state.groups.isEmpty) {
              return _buildEmptyState();
            }
            return _buildContent(context, state);
          }

          return const SizedBox.shrink();
        },
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              color: AppColors.primary.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Icon(
              Icons.auto_awesome,
              color: AppColors.primary,
              size: 40,
            ),
          ),
          const SizedBox(height: 24),
          Text(
            '暂无智能分组',
            style: AppTextStyles.headline6.copyWith(color: Colors.white),
          ),
          const SizedBox(height: 8),
          Text(
            '添加家庭成员后，AI 将自动生成智能分组',
            style: AppTextStyles.caption.copyWith(color: Colors.white54),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildContent(BuildContext context, SmartGroupsLoaded state) {
    return CustomScrollView(
      slivers: [
        // Header
        SliverToBoxAdapter(
          child: _buildHeader(state),
        ),
        // Groups grid
        SliverPadding(
          padding: const EdgeInsets.all(16),
          sliver: SliverGrid(
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              childAspectRatio: 0.85,
            ),
            delegate: SliverChildBuilderDelegate(
              (context, index) {
                if (index >= state.groups.length) return null;
                return _buildGroupCard(context, state.groups[index]);
              },
              childCount: state.groups.length,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildHeader(SmartGroupsLoaded state) {
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF1E3A5F), Color(0xFF0F172A)],
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFF334155)),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: const Icon(
                  Icons.auto_awesome,
                  color: AppColors.primary,
                  size: 28,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'AI 智能分组',
                      style: AppTextStyles.headline6.copyWith(
                        color: Colors.white,
                      ),
                    ),
                    Text(
                      '根据关系特征自动分类',
                      style: AppTextStyles.caption.copyWith(
                        color: Colors.white54,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          const Divider(color: Color(0xFF334155)),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _buildStatItem(
                  '分组数',
                  '${state.groups.length}',
                  Icons.folder_outlined,
                ),
              ),
              Container(
                width: 1,
                height: 40,
                color: const Color(0xFF334155),
              ),
              Expanded(
                child: _buildStatItem(
                  '总成员',
                  '${state.totalMembers}',
                  Icons.people_outline,
                ),
              ),
              Container(
                width: 1,
                height: 40,
                color: const Color(0xFF334155),
              ),
              Expanded(
                child: _buildStatItem(
                  '需关注',
                  '${state.needsAttentionGroup?.memberCount ?? 0}',
                  Icons.warning_amber,
                  valueColor: AppColors.warning,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatItem(
    String label,
    String value,
    IconData icon, {
    Color? valueColor,
  }) {
    return Column(
      children: [
        Icon(icon, size: 20, color: valueColor ?? Colors.white54),
        const SizedBox(height: 4),
        Text(
          value,
          style: AppTextStyles.headline6.copyWith(
            color: valueColor ?? Colors.white,
          ),
        ),
        Text(
          label,
          style: AppTextStyles.overline.copyWith(
            color: Colors.white54,
          ),
        ),
      ],
    );
  }

  Widget _buildGroupCard(BuildContext context, SmartGroup group) {
    return GestureDetector(
      onTap: () => _showGroupDetail(context, group),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: const Color(0xFF1E293B),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: group.color.withValues(alpha: 0.3),
            width: 1,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Icon and count
            Row(
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: group.color.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(group.icon, color: group.color, size: 24),
                ),
                const Spacer(),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: group.color.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    '${group.memberCount}',
                    style: AppTextStyles.subtitle2.copyWith(
                      color: group.color,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),

            const SizedBox(height: 12),

            // Name
            Text(
              group.name,
              style: AppTextStyles.subtitle1.copyWith(
                color: Colors.white,
                fontWeight: FontWeight.w600,
              ),
            ),

            const SizedBox(height: 4),

            // Description
            Text(
              group.description,
              style: AppTextStyles.caption.copyWith(
                color: Colors.white54,
              ),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),

            const Spacer(),

            // Preview avatars
            Row(
              children: [
                ...group.previewMembers.take(3).map((member) {
                  return Container(
                    width: 28,
                    height: 28,
                    margin: const EdgeInsets.only(right: 4),
                    decoration: BoxDecoration(
                      color: group.color.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: const Color(0xFF1E293B),
                        width: 2,
                      ),
                    ),
                    child: Center(
                      child: Text(
                        member.name.isNotEmpty ? member.name.characters.first : '?',
                        style: TextStyle(
                          color: group.color,
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  );
                }),
                if (group.memberCount > 3)
                  Container(
                    width: 28,
                    height: 28,
                    decoration: BoxDecoration(
                      color: const Color(0xFF334155),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Center(
                      child: Text(
                        '+${group.memberCount - 3}',
                        style: AppTextStyles.overline.copyWith(
                          color: Colors.white54,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  void _showGroupDetail(BuildContext context, SmartGroup group) {
    // Request detailed data
    context.read<SmartGroupsBloc>().add(SmartGroupDetailRequested(groupKey: group.key));

    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF1E293B),
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.7,
        maxChildSize: 0.9,
        minChildSize: 0.5,
        expand: false,
        builder: (context, scrollController) => Column(
          children: [
            // Handle
            Container(
              margin: const EdgeInsets.only(top: 12),
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: Colors.white24,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            // Header
            Padding(
              padding: const EdgeInsets.all(20),
              child: Row(
                children: [
                  Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      color: group.color.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(group.icon, color: group.color),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          group.name,
                          style: AppTextStyles.headline6.copyWith(
                            color: Colors.white,
                          ),
                        ),
                        Text(
                          '${group.memberCount} 位成员',
                          style: AppTextStyles.caption.copyWith(
                            color: Colors.white54,
                          ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    onPressed: () => Navigator.pop(context),
                    icon: const Icon(Icons.close, color: Colors.white54),
                  ),
                ],
              ),
            ),
            const Divider(color: Color(0xFF334155), height: 1),
            // Member list
            Expanded(
              child: group.previewMembers.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.people_outline,
                              size: 48, color: Colors.white24),
                          const SizedBox(height: 16),
                          Text(
                            '暂无成员',
                            style: AppTextStyles.subtitle1
                                .copyWith(color: Colors.white54),
                          ),
                        ],
                      ),
                    )
                  : ListView.builder(
                      controller: scrollController,
                      padding: const EdgeInsets.all(16),
                      itemCount: group.previewMembers.length,
                      itemBuilder: (context, index) {
                        final member = group.previewMembers[index];
                        return _buildMemberListItem(member, group.color);
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMemberListItem(GroupMemberPreview member, Color color) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Center(
              child: Text(
                member.name.isNotEmpty ? member.name.characters.first : '?',
                style: TextStyle(
                  color: color,
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  member.name,
                  style: AppTextStyles.subtitle1.copyWith(
                    color: Colors.white,
                  ),
                ),
                Text(
                  '点击查看详情',
                  style: AppTextStyles.caption.copyWith(
                    color: Colors.white54,
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            onPressed: () {},
            icon: const Icon(
              Icons.phone_outlined,
              color: Colors.white54,
              size: 20,
            ),
          ),
          IconButton(
            onPressed: () {},
            icon: const Icon(
              Icons.message_outlined,
              color: Colors.white54,
              size: 20,
            ),
          ),
        ],
      ),
    );
  }

  void _showReminders(BuildContext context) async {
    final bloc = context.read<SmartGroupsBloc>();
    final reminders = await bloc.getDailyReminders();

    if (!context.mounted) return;

    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF1E293B),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => Container(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.notifications, color: AppColors.primary),
                const SizedBox(width: 8),
                Text(
                  '今日提醒',
                  style: AppTextStyles.headline6.copyWith(color: Colors.white),
                ),
              ],
            ),
            const SizedBox(height: 16),
            if (reminders.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 20),
                child: Center(
                  child: Column(
                    children: [
                      const Icon(Icons.check_circle_outline,
                          size: 48, color: AppColors.success),
                      const SizedBox(height: 12),
                      Text(
                        '今天没有提醒',
                        style: AppTextStyles.subtitle1
                            .copyWith(color: Colors.white54),
                      ),
                    ],
                  ),
                ),
              )
            else
              ...reminders.map((reminder) => _buildReminderItem(
                    icon: reminder.icon,
                    color: reminder.color,
                    title: reminder.title,
                    subtitle: reminder.body,
                  )),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  Widget _buildReminderItem({
    required IconData icon,
    required Color color,
    required String title,
    required String subtitle,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: color, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: AppTextStyles.subtitle2.copyWith(color: Colors.white),
                ),
                Text(
                  subtitle,
                  style: AppTextStyles.caption.copyWith(color: Colors.white54),
                ),
              ],
            ),
          ),
          const Icon(Icons.chevron_right, color: Colors.white38),
        ],
      ),
    );
  }
}
