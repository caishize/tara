import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../app/di/injection.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../../shared/widgets/custom_app_bar.dart';
import '../../domain/entities/smart_service.dart';
import '../../domain/entities/service_execution.dart';
import '../bloc/service_detail_bloc.dart';

class ServiceDetailPage extends StatelessWidget {
  final SmartService service;

  const ServiceDetailPage({super.key, required this.service});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (context) => getIt<ServiceDetailBloc>()
        ..add(ServiceDetailLoadRequested(service.id)),
      child: _ServiceDetailPageContent(service: service),
    );
  }
}

class _ServiceDetailPageContent extends StatelessWidget {
  final SmartService service;

  const _ServiceDetailPageContent({required this.service});

  IconData _getServiceIcon() {
    switch (service.icon) {
      case 'notifications_active':
        return Icons.notifications_active_outlined;
      case 'celebration':
        return Icons.celebration_outlined;
      case 'card_giftcard':
        return Icons.card_giftcard_outlined;
      case 'redeem':
        return Icons.redeem_outlined;
      case 'trending_down':
        return Icons.trending_down_outlined;
      default:
        return Icons.settings_outlined;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: CustomAppBar(title: service.displayName),
      body: BlocConsumer<ServiceDetailBloc, ServiceDetailState>(
        listener: (context, state) {
          if (state is ServiceDetailError) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                backgroundColor: AppColors.error,
              ),
            );
          } else if (state is ServiceTriggerSuccess) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('任务已触发，正在执行中...'),
                backgroundColor: AppColors.success,
              ),
            );
          }
        },
        builder: (context, state) {
          if (state is ServiceDetailLoading) {
            return const Center(child: CircularProgressIndicator());
          }

          ExecutionHistory history = ExecutionHistory.empty();
          bool isTriggering = false;
          SmartService currentService = service;

          if (state is ServiceDetailLoaded) {
            history = state.executionHistory;
            currentService = state.service ?? service;
          } else if (state is ServiceTriggerInProgress) {
            history = state.previousHistory;
            isTriggering = true;
            currentService = state.service ?? service;
          } else if (state is ServiceTriggerSuccess) {
            history = state.executionHistory;
            currentService = state.service ?? service;
          }

          return RefreshIndicator(
            onRefresh: () async {
              context
                  .read<ServiceDetailBloc>()
                  .add(ServiceDetailLoadRequested(service.id));
            },
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                // Service header card
                _buildServiceHeaderCard(context, currentService, isTriggering),
                const SizedBox(height: 20),

                // Statistics card
                _buildStatisticsCard(currentService),
                const SizedBox(height: 20),

                // Execution history section
                _buildExecutionHistorySection(history),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildServiceHeaderCard(
    BuildContext context,
    SmartService currentService,
    bool isTriggering,
  ) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: currentService.isRunning
            ? AppColors.primaryGradient
            : const LinearGradient(
                colors: [Color(0xFF9E9E9E), Color(0xFF757575)],
              ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(
                  _getServiceIcon(),
                  color: Colors.white,
                  size: 28,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      currentService.displayName,
                      style: AppTextStyles.headline6.copyWith(
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      currentService.description,
                      style: AppTextStyles.caption.copyWith(
                        color: Colors.white.withValues(alpha: 0.8),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(
                child: _buildStatusBadge(currentService),
              ),
              const SizedBox(width: 12),
              // Manual trigger button
              ElevatedButton.icon(
                onPressed: isTriggering
                    ? null
                    : () {
                        context.read<ServiceDetailBloc>().add(
                              ServiceManualTriggerRequested(service.id),
                            );
                      },
                icon: isTriggering
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Icon(Icons.play_arrow, size: 18),
                label: Text(isTriggering ? '执行中...' : '立即执行'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: AppColors.primary,
                  padding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatusBadge(SmartService currentService) {
    final isRunning = currentService.isRunning;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: isRunning ? Colors.greenAccent : Colors.white54,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            currentService.statusText,
            style: AppTextStyles.bodyText2.copyWith(color: Colors.white),
          ),
          if (currentService.lastRunText != null) ...[
            const SizedBox(width: 12),
            Text(
              '上次: ${currentService.lastRunText}',
              style:
                  AppTextStyles.caption.copyWith(color: Colors.white70),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildStatisticsCard(SmartService currentService) {
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
              const Icon(Icons.analytics_outlined,
                  color: AppColors.primary, size: 20),
              const SizedBox(width: 8),
              Text('执行统计', style: AppTextStyles.subtitle1),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _buildStatItem(
                  '总执行次数',
                  '${currentService.totalExecutions}',
                  Icons.repeat,
                ),
              ),
              Container(width: 1, height: 40, color: AppColors.divider),
              Expanded(
                child: _buildStatItem(
                  '成功率',
                  '${currentService.successRate.toStringAsFixed(1)}%',
                  Icons.check_circle_outline,
                  valueColor: currentService.successRate >= 90
                      ? AppColors.success
                      : currentService.successRate >= 70
                          ? AppColors.warning
                          : AppColors.error,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          // Success rate progress bar
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '成功率趋势',
                style: AppTextStyles.caption
                    .copyWith(color: AppColors.textSecondary),
              ),
              const SizedBox(height: 8),
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: currentService.successRate / 100,
                  backgroundColor: AppColors.divider,
                  valueColor: AlwaysStoppedAnimation<Color>(
                    currentService.successRate >= 90
                        ? AppColors.success
                        : currentService.successRate >= 70
                            ? AppColors.warning
                            : AppColors.error,
                  ),
                  minHeight: 8,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatItem(String label, String value, IconData icon,
      {Color? valueColor}) {
    return Column(
      children: [
        Icon(icon, color: valueColor ?? AppColors.primary, size: 24),
        const SizedBox(height: 8),
        Text(
          value,
          style: AppTextStyles.headline6.copyWith(
            color: valueColor ?? AppColors.textPrimary,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style:
              AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
        ),
      ],
    );
  }

  Widget _buildExecutionHistorySection(ExecutionHistory history) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              children: [
                const Icon(Icons.history, color: AppColors.primary, size: 20),
                const SizedBox(width: 8),
                Text('执行记录', style: AppTextStyles.subtitle1),
              ],
            ),
            Text(
              '共 ${history.total} 条',
              style:
                  AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
            ),
          ],
        ),
        const SizedBox(height: 12),
        if (history.executions.isEmpty)
          Container(
            padding: const EdgeInsets.all(40),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [AppColors.shadowLight],
            ),
            child: Center(
              child: Column(
                children: [
                  Icon(Icons.inbox_outlined,
                      size: 48, color: AppColors.textTertiary),
                  const SizedBox(height: 12),
                  Text(
                    '暂无执行记录',
                    style: AppTextStyles.bodyText2
                        .copyWith(color: AppColors.textSecondary),
                  ),
                ],
              ),
            ),
          )
        else
          Container(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [AppColors.shadowLight],
            ),
            child: Column(
              children: history.executions
                  .take(20)
                  .map((e) => _ExecutionHistoryTile(execution: e))
                  .toList(),
            ),
          ),
      ],
    );
  }
}

class _ExecutionHistoryTile extends StatelessWidget {
  final ServiceExecution execution;

  const _ExecutionHistoryTile({required this.execution});

  IconData _getStatusIcon() {
    switch (execution.status) {
      case ExecutionStatus.completed:
        return Icons.check_circle;
      case ExecutionStatus.failed:
        return Icons.error;
      case ExecutionStatus.running:
        return Icons.sync;
      case ExecutionStatus.timeout:
        return Icons.timer_off;
      case ExecutionStatus.cancelled:
        return Icons.cancel;
      case ExecutionStatus.pending:
        return Icons.schedule;
    }
  }

  Color _getStatusColor() {
    switch (execution.status) {
      case ExecutionStatus.completed:
        return AppColors.success;
      case ExecutionStatus.failed:
      case ExecutionStatus.timeout:
      case ExecutionStatus.cancelled:
        return AppColors.error;
      case ExecutionStatus.running:
        return AppColors.primary;
      case ExecutionStatus.pending:
        return AppColors.warning;
    }
  }

  @override
  Widget build(BuildContext context) {
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
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              color: _getStatusColor().withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(
              _getStatusIcon(),
              color: _getStatusColor(),
              size: 18,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      execution.statusText,
                      style: AppTextStyles.bodyText2.copyWith(
                        color: _getStatusColor(),
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    Text(
                      execution.relativeTimeText,
                      style: AppTextStyles.caption
                          .copyWith(color: AppColors.textTertiary),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                if (execution.resultText != null)
                  Text(
                    execution.resultText!,
                    style: AppTextStyles.caption
                        .copyWith(color: AppColors.textSecondary),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  )
                else if (execution.errorMessage != null)
                  Text(
                    execution.errorMessage!,
                    style:
                        AppTextStyles.caption.copyWith(color: AppColors.error),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                if (execution.durationText != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    '耗时: ${execution.durationText}',
                    style: AppTextStyles.caption
                        .copyWith(color: AppColors.textTertiary),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
