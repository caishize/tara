import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../app/di/injection.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../../shared/widgets/custom_app_bar.dart';
import '../../domain/entities/activity_record.dart';
import '../bloc/activity_bloc.dart';

class ActivityTimelinePage extends StatelessWidget {
  const ActivityTimelinePage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (context) =>
          getIt<ActivityBloc>()..add(const ActivityLoadRequested()),
      child: const _ActivityTimelinePageContent(),
    );
  }
}

class _ActivityTimelinePageContent extends StatelessWidget {
  const _ActivityTimelinePageContent();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: const CustomAppBar(title: '秘书工作记录'),
      body: BlocBuilder<ActivityBloc, ActivityState>(
        builder: (context, state) {
          if (state is ActivityLoading) {
            return const Center(child: CircularProgressIndicator());
          }

          if (state is ActivityError) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.error_outline,
                      size: 48, color: AppColors.textTertiary),
                  const SizedBox(height: 16),
                  Text(state.message,
                      style: AppTextStyles.bodyText2
                          .copyWith(color: AppColors.textSecondary)),
                  const SizedBox(height: 16),
                  ElevatedButton(
                    onPressed: () {
                      context
                          .read<ActivityBloc>()
                          .add(const ActivityLoadRequested());
                    },
                    child: const Text('重试'),
                  ),
                ],
              ),
            );
          }

          ActivityTimeline timeline = ActivityTimeline.empty();
          if (state is ActivityLoaded) {
            timeline = state.timeline;
          }

          return RefreshIndicator(
            onRefresh: () async {
              context.read<ActivityBloc>().add(const ActivityLoadRequested());
            },
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                // Summary card
                _buildSummaryCard(timeline.summary),
                const SizedBox(height: 24),

                // Activity timeline
                _buildTimelineSection(timeline),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildSummaryCard(ActivitySummary summary) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: AppColors.primaryGradient,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.auto_awesome, color: Colors.white, size: 24),
              const SizedBox(width: 8),
              Text(
                '${summary.periodText}秘书工作报告',
                style: AppTextStyles.subtitle1.copyWith(color: Colors.white),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            '共完成 ${summary.totalTasksCompleted} 项任务',
            style: AppTextStyles.headline5.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 20),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              if (summary.remindersSent > 0)
                _buildSummaryChip(
                    Icons.notifications_active, '${summary.remindersSent} 条提醒'),
              if (summary.giftsRecommended > 0)
                _buildSummaryChip(
                    Icons.redeem, '${summary.giftsRecommended} 款礼物'),
              if (summary.priceAlerts > 0)
                _buildSummaryChip(
                    Icons.trending_down, '${summary.priceAlerts} 次价格监控'),
              if (summary.holidaysSynced > 0)
                _buildSummaryChip(
                    Icons.celebration, '${summary.holidaysSynced} 个节日同步'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSummaryChip(IconData icon, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: Colors.white),
          const SizedBox(width: 6),
          Text(
            label,
            style: AppTextStyles.caption.copyWith(color: Colors.white),
          ),
        ],
      ),
    );
  }

  Widget _buildTimelineSection(ActivityTimeline timeline) {
    if (timeline.activities.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(40),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          boxShadow: [AppColors.shadowLight],
        ),
        child: Center(
          child: Column(
            children: [
              Icon(Icons.inbox_outlined, size: 48, color: AppColors.textTertiary),
              const SizedBox(height: 12),
              Text(
                '暂无工作记录',
                style: AppTextStyles.bodyText2
                    .copyWith(color: AppColors.textSecondary),
              ),
              const SizedBox(height: 4),
              Text(
                '秘书正在为您默默工作中...',
                style: AppTextStyles.caption
                    .copyWith(color: AppColors.textTertiary),
              ),
            ],
          ),
        ),
      );
    }

    final groupedActivities = timeline.groupedActivities;
    final widgets = <Widget>[];

    for (var entry in groupedActivities.entries) {
      // Date header
      widgets.add(
        Padding(
          padding: const EdgeInsets.only(left: 4, bottom: 12, top: 8),
          child: Text(
            entry.key,
            style: AppTextStyles.subtitle2
                .copyWith(color: AppColors.textSecondary),
          ),
        ),
      );

      // Activities for this date
      widgets.add(
        Container(
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            boxShadow: [AppColors.shadowLight],
          ),
          child: Column(
            children: entry.value
                .map((activity) => _ActivityTile(activity: activity))
                .toList(),
          ),
        ),
      );

      widgets.add(const SizedBox(height: 16));
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.timeline, color: AppColors.primary, size: 20),
            const SizedBox(width: 8),
            Text('活动时间线', style: AppTextStyles.subtitle1),
          ],
        ),
        const SizedBox(height: 16),
        ...widgets,
      ],
    );
  }
}

class _ActivityTile extends StatelessWidget {
  final ActivityRecord activity;

  const _ActivityTile({required this.activity});

  IconData _getIcon() {
    switch (activity.type) {
      case ActivityType.reminder:
        return Icons.notifications_active_outlined;
      case ActivityType.giftRecommendation:
        return Icons.redeem_outlined;
      case ActivityType.priceAlert:
        return Icons.trending_down_outlined;
      case ActivityType.holidaySync:
        return Icons.celebration_outlined;
      case ActivityType.holidayPreparation:
        return Icons.card_giftcard_outlined;
      case ActivityType.other:
        return Icons.auto_awesome_outlined;
    }
  }

  Color _getColor() {
    switch (activity.type) {
      case ActivityType.reminder:
        return const Color(0xFF5C6BC0);
      case ActivityType.giftRecommendation:
        return const Color(0xFFEC407A);
      case ActivityType.priceAlert:
        return const Color(0xFF26A69A);
      case ActivityType.holidaySync:
        return const Color(0xFFFF7043);
      case ActivityType.holidayPreparation:
        return const Color(0xFFAB47BC);
      case ActivityType.other:
        return AppColors.primary;
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = _getColor();

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: const BoxDecoration(
        border: Border(
          bottom: BorderSide(color: AppColors.divider, width: 0.5),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Timeline indicator
          Column(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(_getIcon(), color: color, size: 18),
              ),
            ],
          ),
          const SizedBox(width: 12),
          // Content
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Text(
                        activity.title,
                        style: AppTextStyles.bodyText1,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    Text(
                      activity.relativeTimeText,
                      style: AppTextStyles.caption
                          .copyWith(color: AppColors.textTertiary),
                    ),
                  ],
                ),
                if (activity.description != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    activity.description!,
                    style: AppTextStyles.caption
                        .copyWith(color: AppColors.textSecondary),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
                const SizedBox(height: 4),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    activity.typeText,
                    style: AppTextStyles.caption.copyWith(
                      color: color,
                      fontSize: 10,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
