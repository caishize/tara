import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../bloc/guardian_bloc.dart';
import '../bloc/guardian_event.dart';
import '../bloc/guardian_state.dart';
import '../widgets/day_navigation_bar.dart';
import '../widgets/timeline_activity_item.dart';

/// Trip planning page showing itinerary with timeline view
class TripPlanningPage extends StatelessWidget {
  final String tripId;

  const TripPlanningPage({
    super.key,
    required this.tripId,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: BlocBuilder<GuardianBloc, GuardianState>(
          builder: (context, state) {
            if (state is GuardianLoading) {
              return const _LoadingView();
            }

            if (state is GuardianError) {
              return _ErrorView(
                message: state.message,
                onRetry: () {
                  context
                      .read<GuardianBloc>()
                      .add(TripPlanningLoadRequested(tripId));
                },
              );
            }

            if (state is TripPlanningLoaded) {
              return _TripPlanningContent(state: state);
            }

            return const SizedBox.shrink();
          },
        ),
      ),
    );
  }
}

class _TripPlanningContent extends StatelessWidget {
  final TripPlanningLoaded state;

  const _TripPlanningContent({required this.state});

  @override
  Widget build(BuildContext context) {
    final dateFormat = DateFormat('M月d日');
    final dayItinerary = state.currentDayItinerary;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header
        _buildHeader(context),

        // Date overview card
        _buildDateOverviewCard(dateFormat),

        // Day navigation
        DayNavigationBar(
          totalDays: state.totalDays,
          selectedDay: state.selectedDay,
          onDaySelected: (day) {
            // Update selected day in bloc
            // For now, just show snackbar
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('切换到第$day天')),
            );
          },
        ),

        // Current day header
        if (dayItinerary != null)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
            child: Text(
              '${dateFormat.format(dayItinerary.date)} ${_getWeekday(dayItinerary.date)}',
              style: AppTextStyles.subtitle1.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
          ),

        // Timeline
        Expanded(
          child: dayItinerary == null || dayItinerary.activities.isEmpty
              ? _buildEmptyDayView(context)
              : ListView.builder(
                  padding: const EdgeInsets.only(bottom: 100),
                  itemCount: dayItinerary.activities.length +
                      (dayItinerary.secretaryAdvice != null ? 1 : 0),
                  itemBuilder: (context, index) {
                    // Secretary advice at the end
                    if (index == dayItinerary.activities.length &&
                        dayItinerary.secretaryAdvice != null) {
                      return SecretaryAdviceCard(
                        advice: dayItinerary.secretaryAdvice!,
                      );
                    }

                    final activity = dayItinerary.activities[index];
                    return TimelineActivityItem(
                      activity: activity,
                      isFirst: index == 0,
                      isLast: index == dayItinerary.activities.length - 1 &&
                          dayItinerary.secretaryAdvice == null,
                    );
                  },
                ),
        ),
      ],
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
      child: Row(
        children: [
          IconButton(
            onPressed: () => context.pop(),
            icon: const Icon(Icons.arrow_back_ios),
            color: AppColors.textPrimary,
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              state.tripName,
              style: AppTextStyles.headline6.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          IconButton(
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('编辑功能开发中')),
              );
            },
            icon: const Icon(Icons.edit_outlined),
            color: AppColors.textSecondary,
          ),
        ],
      ),
    );
  }

  Widget _buildDateOverviewCard(DateFormat dateFormat) {
    final startStr = dateFormat.format(state.startDate);
    final endStr = dateFormat.format(state.endDate);
    final activityCount = state.itinerary.fold<int>(
      0,
      (sum, day) => sum + day.activities.length,
    );

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF2196F3), Color(0xFF00BCD4)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '$startStr - $endStr',
                  style: AppTextStyles.subtitle1.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '共${state.totalDays}天 · 已安排${activityCount}个行程',
                  style: AppTextStyles.caption.copyWith(
                    color: Colors.white.withValues(alpha: 0.8),
                  ),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(
              Icons.download_outlined,
              color: Colors.white,
              size: 20,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyDayView(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.event_available_outlined,
            size: 64,
            color: AppColors.textTertiary.withValues(alpha: 0.5),
          ),
          const SizedBox(height: 16),
          Text(
            '今天还没有安排',
            style: AppTextStyles.subtitle1.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '点击下方按钮添加行程',
            style: AppTextStyles.caption.copyWith(
              color: AppColors.textTertiary,
            ),
          ),
        ],
      ),
    );
  }

  String _getWeekday(DateTime date) {
    const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
    return weekdays[date.weekday - 1];
  }
}

class _LoadingView extends StatelessWidget {
  const _LoadingView();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: CircularProgressIndicator(color: AppColors.primary),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _ErrorView({
    required this.message,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, size: 48, color: AppColors.error),
          const SizedBox(height: 16),
          Text(message),
          const SizedBox(height: 16),
          ElevatedButton(onPressed: onRetry, child: const Text('重试')),
        ],
      ),
    );
  }
}
