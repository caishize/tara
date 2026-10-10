import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/goal.dart';
import '../bloc/goals_bloc.dart';
import '../widgets/add_goal_sheet.dart';
import '../widgets/record_progress_sheet.dart';

class GoalsPage extends StatelessWidget {
  final String? memberId;

  const GoalsPage({super.key, this.memberId});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
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
              context.go('/family');
            }
          },
        ),
        title: Text('目标追踪', style: AppTextStyles.headline5),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: AppColors.textPrimary),
            onPressed: () {
              final bloc = context.read<GoalsBloc>();
              final currentState = bloc.state;
              if (currentState is GoalsLoaded) {
                bloc.add(GoalsLoadRequested(memberId: currentState.memberId));
              }
            },
          ),
        ],
      ),
      body: BlocConsumer<GoalsBloc, GoalsState>(
        listener: (context, state) {
          if (state is GoalsError) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                backgroundColor: AppColors.error,
              ),
            );
          } else if (state is GoalsOperationSuccess) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                backgroundColor: AppColors.success,
              ),
            );
          }
        },
        builder: (context, state) {
          if (state is GoalsLoading || state is GoalsInitial) {
            return const Center(child: CircularProgressIndicator());
          }

          if (state is GoalsError) {
            return _buildErrorState(context, state.message);
          }

          if (state is GoalsLoaded) {
            if (state.goals.isEmpty) {
              return _buildEmptyState(context, state.memberId);
            }
            return _buildContent(context, state);
          }

          return const SizedBox.shrink();
        },
      ),
      floatingActionButton: BlocBuilder<GoalsBloc, GoalsState>(
        builder: (context, state) {
          if (state is GoalsLoaded) {
            return FloatingActionButton(
              onPressed: () => _showAddGoalSheet(context, state.memberId),
              backgroundColor: AppColors.primary,
              child: const Icon(Icons.add, color: Colors.white),
            );
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }

  Widget _buildErrorState(BuildContext context, String message) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 64, color: AppColors.error.withValues(alpha: 0.5)),
            const SizedBox(height: 16),
            Text('加载失败', style: AppTextStyles.headline6),
            const SizedBox(height: 8),
            Text(
              message,
              style: AppTextStyles.bodyText2.copyWith(color: AppColors.textSecondary),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState(BuildContext context, String memberId) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.flag_outlined, size: 80, color: AppColors.primary.withValues(alpha: 0.3)),
            const SizedBox(height: 20),
            Text('还没有设定目标', style: AppTextStyles.headline6),
            const SizedBox(height: 8),
            Text(
              '设定一个目标,开始追踪你的进度吧',
              style: AppTextStyles.bodyText2.copyWith(color: AppColors.textSecondary),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: () => _showAddGoalSheet(context, memberId),
              icon: const Icon(Icons.add),
              label: const Text('创建目标'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent(BuildContext context, GoalsLoaded state) {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        // Overview stats card
        _buildOverviewCard(state),
        const SizedBox(height: 20),

        // Active goals section
        if (state.activeGoals.isNotEmpty) ...[
          Text('进行中的目标', style: AppTextStyles.subtitle1),
          const SizedBox(height: 12),
          ...state.activeGoals.map((goal) => _buildGoalCard(context, goal, state.memberId)),
          const SizedBox(height: 20),
        ],

        // Completed goals section
        if (state.completedGoals.isNotEmpty) ...[
          Text('已完成的目标', style: AppTextStyles.subtitle1),
          const SizedBox(height: 12),
          ...state.completedGoals.map((goal) => _buildGoalCard(context, goal, state.memberId)),
        ],
      ],
    );
  }

  Widget _buildOverviewCard(GoalsLoaded state) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: AppColors.primaryGradient,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: _buildOverviewStat(
                  '总目标',
                  state.totalGoals.toString(),
                  Icons.flag,
                ),
              ),
              Container(width: 1, height: 50, color: Colors.white.withValues(alpha: 0.3)),
              Expanded(
                child: _buildOverviewStat(
                  '进行中',
                  state.activeGoals.length.toString(),
                  Icons.trending_up,
                ),
              ),
              Container(width: 1, height: 50, color: Colors.white.withValues(alpha: 0.3)),
              Expanded(
                child: _buildOverviewStat(
                  '已完成',
                  state.completedCount.toString(),
                  Icons.check_circle,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: state.overallCompletionRate / 100,
              backgroundColor: Colors.white.withValues(alpha: 0.3),
              valueColor: const AlwaysStoppedAnimation(Colors.white),
              minHeight: 6,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '总体完成率: ${state.overallCompletionRate.toStringAsFixed(1)}%',
            style: AppTextStyles.caption.copyWith(color: Colors.white),
          ),
        ],
      ),
    );
  }

  Widget _buildOverviewStat(String label, String value, IconData icon) {
    return Column(
      children: [
        Icon(icon, color: Colors.white, size: 24),
        const SizedBox(height: 4),
        Text(
          value,
          style: AppTextStyles.headline5.copyWith(
            color: Colors.white,
            fontWeight: FontWeight.bold,
          ),
        ),
        Text(
          label,
          style: AppTextStyles.caption.copyWith(
            color: Colors.white.withValues(alpha: 0.8),
          ),
        ),
      ],
    );
  }

  Widget _buildGoalCard(BuildContext context, Goal goal, String memberId) {
    final isActive = goal.status == GoalStatus.active;

    Color progressColor;
    if (goal.completionPercentage >= 100) {
      progressColor = AppColors.success;
    } else if (goal.isOnTrack) {
      progressColor = AppColors.primary;
    } else {
      progressColor = AppColors.warning;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: InkWell(
        onTap: isActive ? () => _showRecordProgressSheet(context, goal, memberId) : null,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: progressColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(
                      _getGoalIcon(goal.goalType),
                      color: progressColor,
                      size: 24,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                goal.description,
                                style: AppTextStyles.subtitle2,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: progressColor.withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Text(
                                goal.goalTypeDisplay,
                                style: AppTextStyles.overline.copyWith(color: progressColor),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(
                          goal.progressDisplay,
                          style: AppTextStyles.bodyText2.copyWith(
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
                  value: (goal.completionPercentage / 100).clamp(0.0, 1.0),
                  backgroundColor: AppColors.background,
                  valueColor: AlwaysStoppedAnimation(progressColor),
                  minHeight: 8,
                ),
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    goal.completionDisplay,
                    style: AppTextStyles.caption.copyWith(
                      color: progressColor,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  if (isActive)
                    Text(
                      '剩余 ${goal.daysRemaining} 天',
                      style: AppTextStyles.caption.copyWith(
                        color: AppColors.textSecondary,
                      ),
                    )
                  else
                    Text(
                      goal.statusDisplay,
                      style: AppTextStyles.caption.copyWith(
                        color: AppColors.success,
                      ),
                    ),
                ],
              ),
              if (isActive) ...[
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: () => _showRecordProgressSheet(context, goal, memberId),
                        icon: const Icon(Icons.add, size: 18),
                        label: const Text('记录进度'),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: AppColors.primary,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    if (goal.completionPercentage >= 100)
                      Expanded(
                        child: ElevatedButton.icon(
                          onPressed: () {
                            context.read<GoalsBloc>().add(GoalStatusUpdated(
                              goalId: goal.id,
                              memberId: memberId,
                              newStatus: 'completed',
                            ));
                          },
                          icon: const Icon(Icons.check, size: 18),
                          label: const Text('完成'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: AppColors.success,
                            foregroundColor: Colors.white,
                          ),
                        ),
                      ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  IconData _getGoalIcon(String goalType) {
    return switch (goalType) {
      'reading' => Icons.menu_book,
      'exercise' => Icons.fitness_center,
      'savings' => Icons.savings,
      'learning' => Icons.school,
      'weight' => Icons.monitor_weight,
      'sleep' => Icons.bedtime,
      'meditation' => Icons.self_improvement,
      'work' => Icons.work,
      _ => Icons.flag,
    };
  }

  void _showAddGoalSheet(BuildContext context, String memberId) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) => BlocProvider.value(
        value: context.read<GoalsBloc>(),
        child: AddGoalSheet(memberId: memberId),
      ),
    );
  }

  void _showRecordProgressSheet(BuildContext context, Goal goal, String memberId) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) => BlocProvider.value(
        value: context.read<GoalsBloc>(),
        child: RecordProgressSheet(goal: goal, memberId: memberId),
      ),
    );
  }
}
