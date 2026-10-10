import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../../app/di/injection.dart';
import '../../../../shared/widgets/avatar_with_initials.dart';
import '../../../members/presentation/bloc/members_bloc.dart';
import '../../../members/domain/entities/member.dart';
import '../../../schedule/presentation/bloc/schedule_bloc.dart';
import '../../../schedule/presentation/bloc/schedule_event.dart';
import '../../../schedule/presentation/bloc/schedule_state.dart';
import '../../../schedule/domain/entities/unified_event.dart';

/// 家庭健康管理页面
class HealthPage extends StatefulWidget {
  const HealthPage({super.key});

  @override
  State<HealthPage> createState() => _HealthPageState();
}

class _HealthPageState extends State<HealthPage> {
  late MembersBloc _membersBloc;
  late ScheduleBloc _scheduleBloc;

  @override
  void initState() {
    super.initState();
    _membersBloc = getIt<MembersBloc>();
    _scheduleBloc = getIt<ScheduleBloc>();

    _membersBloc.add(const MembersLoadRequested());
    _scheduleBloc.add(const ScheduleLoadRequested());
  }

  @override
  Widget build(BuildContext context) {
    return MultiBlocProvider(
      providers: [
        BlocProvider.value(value: _membersBloc),
        BlocProvider.value(value: _scheduleBloc),
      ],
      child: Scaffold(
        backgroundColor: AppColors.background,
        appBar: AppBar(
          backgroundColor: AppColors.background,
          elevation: 0,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_ios, color: AppColors.textPrimary),
            onPressed: () {
              if (context.canPop()) {
                context.pop();
              } else {
                context.go(Routes.family);
              }
            },
          ),
          title: Text('健康管理', style: AppTextStyles.headline5),
        ),
        body: RefreshIndicator(
          onRefresh: () async {
            _membersBloc.add(const MembersLoadRequested());
            _scheduleBloc.add(const ScheduleLoadRequested());
          },
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              _buildQuickActions(context),
              const SizedBox(height: 20),
              _buildFamilyHealthOverview(),
              const SizedBox(height: 20),
              _buildUpcomingReminders(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildQuickActions(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _buildActionCard(
            context,
            '体检记录',
            Icons.assignment_outlined,
            AppColors.primary,
            onTap: () => context.push(Routes.checkups),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _buildActionCard(
            context,
            '用药提醒',
            Icons.medication_outlined,
            AppColors.accent2,
            onTap: () => context.push(Routes.medications),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _buildActionCard(
            context,
            '健康数据',
            Icons.monitor_heart_outlined,
            AppColors.accent1,
            onTap: () => context.push(Routes.vitalSigns),
          ),
        ),
      ],
    );
  }

  Widget _buildActionCard(
    BuildContext context,
    String title,
    IconData icon,
    Color color, {
    VoidCallback? onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [AppColors.shadowLight],
        ),
        child: Column(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: color, size: 22),
            ),
            const SizedBox(height: 8),
            Text(
              title,
              style: AppTextStyles.caption.copyWith(fontWeight: FontWeight.w500),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFamilyHealthOverview() {
    return BlocBuilder<MembersBloc, MembersState>(
      builder: (context, state) {
        if (state is MembersLoading) {
          return _buildLoadingCard('家庭健康概览');
        }

        if (state is MembersError) {
          return _buildErrorCard('家庭健康概览', state.message);
        }

        if (state is MembersLoaded) {
          // Filter family members
          final familyMembers = state.members.where((m) =>
              m.relation == 'spouse' ||
              m.relation == 'child' ||
              m.relation == 'parent' ||
              m.relation == 'grandchild' ||
              m.relation == 'sibling' ||
              m.relation == 'self').toList();

          if (familyMembers.isEmpty) {
            return _buildEmptyHealthCard();
          }

          return Container(
            padding: const EdgeInsets.all(20),
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
                    Text('家庭健康概览', style: AppTextStyles.subtitle1),
                    const Spacer(),
                    Text(
                      '${familyMembers.length}位家人',
                      style: AppTextStyles.caption.copyWith(
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                ...familyMembers.take(5).map((member) => _buildMemberHealthRow(member)),
              ],
            ),
          );
        }

        return const SizedBox.shrink();
      },
    );
  }

  Widget _buildMemberHealthRow(Member member) {
    final healthInfo = member.healthInfo;
    final hasHealthConcerns = healthInfo?.chronicConditions?.isNotEmpty == true ||
        healthInfo?.allergies?.isNotEmpty == true;

    // Determine health status info
    String statusInfo;
    if (healthInfo?.lastCheckupDate != null && healthInfo!.lastCheckupDate!.isNotEmpty) {
      try {
        final checkupDate = DateTime.parse(healthInfo.lastCheckupDate!);
        final daysSince = DateTime.now().difference(checkupDate).inDays;
        if (daysSince < 365) {
          statusInfo = '体检: ${DateFormat('yyyy-MM-dd').format(checkupDate)}';
        } else {
          statusInfo = '超过1年未体检';
        }
      } catch (_) {
        statusInfo = _getDefaultHealthInfo(member);
      }
    } else {
      statusInfo = _getDefaultHealthInfo(member);
    }

    return GestureDetector(
      onTap: () async {
        await context.push(Routes.memberDetail(member.id));
        if (mounted) {
          _membersBloc.add(const MembersLoadRequested());
        }
      },
      child: Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Row(
          children: [
            AvatarWithInitials(
              name: member.displayName,
              size: 40,
              backgroundColor: _getAvatarColor(member.relation),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(member.displayName, style: AppTextStyles.bodyText1),
                      const SizedBox(width: 8),
                      Text(
                        member.relationText,
                        style: AppTextStyles.caption.copyWith(
                          color: AppColors.textTertiary,
                        ),
                      ),
                    ],
                  ),
                  Text(
                    statusInfo,
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
            _buildHealthStatusBadge(hasHealthConcerns, healthInfo),
          ],
        ),
      ),
    );
  }

  String _getDefaultHealthInfo(Member member) {
    if (member.healthInfo?.bloodType != null) {
      return '血型: ${member.healthInfo!.bloodType}';
    }
    if (member.age != null) {
      return '${member.age}岁';
    }
    return member.relationText;
  }

  Widget _buildHealthStatusBadge(bool hasHealthConcerns, MemberHealthInfo? healthInfo) {
    if (hasHealthConcerns) {
      final concerns = <String>[];
      if (healthInfo?.chronicConditions?.isNotEmpty == true) {
        concerns.addAll(healthInfo!.chronicConditions!.take(1));
      }
      if (healthInfo?.allergies?.isNotEmpty == true) {
        concerns.add('过敏');
      }

      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: AppColors.warning.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Text(
          concerns.isNotEmpty ? concerns.first : '关注',
          style: AppTextStyles.overline.copyWith(
            color: AppColors.warning,
          ),
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.success.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        '健康',
        style: AppTextStyles.overline.copyWith(
          color: AppColors.success,
        ),
      ),
    );
  }

  Color _getAvatarColor(String relation) {
    switch (relation) {
      case 'spouse':
        return AppColors.badgePink;
      case 'child':
        return AppColors.badgeBlue;
      case 'parent':
        return AppColors.badgeGreen;
      case 'grandchild':
        return AppColors.badgeOrange;
      case 'self':
        return AppColors.primary;
      default:
        return AppColors.chipBackground;
    }
  }

  Widget _buildUpcomingReminders() {
    return BlocBuilder<ScheduleBloc, ScheduleState>(
      builder: (context, state) {
        if (state is ScheduleLoading) {
          return _buildLoadingCard('健康提醒');
        }

        if (state is ScheduleLoaded) {
          // Filter health-related events (checkups, medications, etc.)
          final healthEvents = state.allEvents.where((event) {
            final title = event.title.toLowerCase();
            final desc = (event.description ?? '').toLowerCase();
            return title.contains('体检') ||
                title.contains('疫苗') ||
                title.contains('复诊') ||
                title.contains('看病') ||
                title.contains('医院') ||
                title.contains('药') ||
                desc.contains('健康') ||
                desc.contains('体检');
          }).take(5).toList();

          return Container(
            padding: const EdgeInsets.all(20),
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
                    Text('健康提醒', style: AppTextStyles.subtitle1),
                    const Spacer(),
                    GestureDetector(
                      onTap: () => context.push(Routes.timeline),
                      child: Text(
                        '查看全部',
                        style: AppTextStyles.caption.copyWith(
                          color: AppColors.primary,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                if (healthEvents.isEmpty)
                  _buildNoRemindersPlaceholder()
                else
                  ...healthEvents.map((event) => _buildReminderItem(event)),
              ],
            ),
          );
        }

        return _buildLoadingCard('健康提醒');
      },
    );
  }

  Widget _buildReminderItem(UnifiedEvent event) {
    final color = _getReminderColor(event);
    final timeText = _getTimeText(event);

    return GestureDetector(
      onTap: () => context.push(Routes.timeline),
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.05),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withValues(alpha: 0.2)),
        ),
        child: Row(
          children: [
            Icon(
              _getReminderIcon(event),
              color: color,
              size: 20,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(event.title, style: AppTextStyles.bodyText2),
                  if (event.description != null)
                    Text(
                      event.description!,
                      style: AppTextStyles.caption.copyWith(
                        color: AppColors.textSecondary,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                ],
              ),
            ),
            Text(
              timeText,
              style: AppTextStyles.caption.copyWith(
                color: color,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Color _getReminderColor(UnifiedEvent event) {
    if (event.isToday) return AppColors.error;
    final title = event.title.toLowerCase();
    if (title.contains('疫苗')) return AppColors.accent1;
    if (title.contains('体检')) return AppColors.secondary;
    if (title.contains('药')) return AppColors.accent2;
    return AppColors.primary;
  }

  IconData _getReminderIcon(UnifiedEvent event) {
    final title = event.title.toLowerCase();
    if (title.contains('疫苗')) return Icons.vaccines_outlined;
    if (title.contains('体检')) return Icons.assignment_outlined;
    if (title.contains('药')) return Icons.medication_outlined;
    if (title.contains('医院') || title.contains('看病')) return Icons.local_hospital_outlined;
    return Icons.notifications_outlined;
  }

  String _getTimeText(UnifiedEvent event) {
    if (event.dateTime == null) return '';

    final now = DateTime.now();
    final eventDate = event.dateTime!;
    final diff = eventDate.difference(now).inDays;

    if (diff < 0) return '已过期';
    if (diff == 0) return '今天';
    if (diff == 1) return '明天';
    if (diff <= 7) return '$diff天后';
    return DateFormat('M/d').format(eventDate);
  }

  Widget _buildNoRemindersPlaceholder() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 16),
      child: Center(
        child: Column(
          children: [
            Icon(
              Icons.check_circle_outline,
              size: 32,
              color: AppColors.success,
            ),
            const SizedBox(height: 8),
            Text(
              '暂无健康提醒',
              style: AppTextStyles.caption.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLoadingCard(String title) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: AppTextStyles.subtitle1),
          const SizedBox(height: 20),
          const Center(child: CircularProgressIndicator()),
          const SizedBox(height: 20),
        ],
      ),
    );
  }

  Widget _buildErrorCard(String title, String message) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: AppTextStyles.subtitle1),
          const SizedBox(height: 16),
          Center(
            child: Text(
              message,
              style: AppTextStyles.caption.copyWith(color: AppColors.error),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyHealthCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        children: [
          Text('家庭健康概览', style: AppTextStyles.subtitle1),
          const SizedBox(height: 24),
          Icon(
            Icons.family_restroom_outlined,
            size: 48,
            color: AppColors.textTertiary,
          ),
          const SizedBox(height: 12),
          Text(
            '添加家人后可查看健康信息',
            style: AppTextStyles.caption.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 16),
          ElevatedButton.icon(
            onPressed: () => context.push(Routes.memberForm),
            icon: const Icon(Icons.person_add_outlined, size: 18),
            label: const Text('添加家人'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(20),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
