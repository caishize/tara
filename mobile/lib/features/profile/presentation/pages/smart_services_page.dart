import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../app/di/injection.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../../shared/widgets/custom_app_bar.dart';
import '../../domain/entities/smart_service.dart';
import '../bloc/profile_bloc.dart';

class SmartServicesPage extends StatelessWidget {
  const SmartServicesPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (context) =>
          getIt<ProfileBloc>()..add(const ProfileLoadRequested()),
      child: const _SmartServicesPageContent(),
    );
  }
}

class _SmartServicesPageContent extends StatelessWidget {
  const _SmartServicesPageContent();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: const CustomAppBar(title: '智能秘书服务'),
      body: BlocConsumer<ProfileBloc, ProfileState>(
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
            return const Center(child: CircularProgressIndicator());
          }

          SmartServicesSummary services = SmartServicesSummary.empty();
          String? loadingServiceId;

          if (state is ProfileLoaded) {
            services = state.services;
          } else if (state is ServiceOperationInProgress) {
            services = state.previousState.services;
            loadingServiceId = state.serviceId;
          } else if (state is ServiceOperationSuccess) {
            services = state.currentState.services;
          }

          return RefreshIndicator(
            onRefresh: () async {
              context.read<ProfileBloc>().add(const ProfileRefreshRequested());
            },
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                // Summary card
                _buildSummaryCard(services),
                const SizedBox(height: 24),

                // Group services by category
                ..._buildServiceGroups(
                  context,
                  services.services,
                  loadingServiceId,
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildSummaryCard(SmartServicesSummary services) {
    final successRate = services.services.isNotEmpty
        ? services.services
                .map((s) => s.successRate)
                .reduce((a, b) => a + b) /
            services.services.length
        : 0.0;

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
                '服务状态概览',
                style: AppTextStyles.subtitle1.copyWith(color: Colors.white),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildSummaryItem(
                '${services.activeCount}/${services.totalCount}',
                '运行中',
              ),
              Container(
                width: 1,
                height: 40,
                color: Colors.white.withValues(alpha: 0.3),
              ),
              _buildSummaryItem(
                '${successRate.toStringAsFixed(1)}%',
                '平均成功率',
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSummaryItem(String value, String label) {
    return Column(
      children: [
        Text(
          value,
          style: AppTextStyles.headline5.copyWith(
            color: Colors.white,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: AppTextStyles.caption.copyWith(
            color: Colors.white.withValues(alpha: 0.8),
          ),
        ),
      ],
    );
  }

  List<Widget> _buildServiceGroups(
    BuildContext context,
    List<SmartService> services,
    String? loadingServiceId,
  ) {
    // Group by category
    final Map<ServiceCategory, List<SmartService>> groups = {};
    for (var service in services) {
      groups.putIfAbsent(service.category, () => []).add(service);
    }

    final widgets = <Widget>[];

    for (var entry in groups.entries) {
      widgets.add(
        _buildCategoryGroup(
          context,
          entry.key,
          entry.value,
          loadingServiceId,
        ),
      );
      widgets.add(const SizedBox(height: 16));
    }

    return widgets;
  }

  Widget _buildCategoryGroup(
    BuildContext context,
    ServiceCategory category,
    List<SmartService> services,
    String? loadingServiceId,
  ) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 4, bottom: 8),
          child: Text(
            services.first.categoryText,
            style: AppTextStyles.subtitle2.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
        ),
        Container(
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            boxShadow: [AppColors.shadowLight],
          ),
          child: Column(
            children: services
                .map((service) => _ServiceDetailTile(
                      service: service,
                      isLoading: loadingServiceId == service.id,
                      onToggle: (enabled) {
                        context.read<ProfileBloc>().add(
                              SmartServiceToggled(
                                serviceId: service.id,
                                enable: enabled,
                              ),
                            );
                      },
                    ))
                .toList(),
          ),
        ),
      ],
    );
  }
}

class _ServiceDetailTile extends StatelessWidget {
  final SmartService service;
  final bool isLoading;
  final void Function(bool enabled)? onToggle;

  const _ServiceDetailTile({
    required this.service,
    this.isLoading = false,
    this.onToggle,
  });

  IconData _getIconData() {
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
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: const BoxDecoration(
        border: Border(
          bottom: BorderSide(color: AppColors.divider, width: 0.5),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  _getIconData(),
                  color: AppColors.primary,
                  size: 22,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(service.displayName, style: AppTextStyles.bodyText1),
                    const SizedBox(height: 2),
                    Text(
                      service.description,
                      style: AppTextStyles.caption.copyWith(
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
              if (isLoading)
                const SizedBox(
                  width: 24,
                  height: 24,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              else
                Switch(
                  value: service.isRunning,
                  onChanged: onToggle,
                  activeColor: AppColors.primary,
                ),
            ],
          ),
          const SizedBox(height: 12),
          // Stats row
          Row(
            children: [
              _buildStatChip(
                Icons.access_time,
                '上次运行: ${service.lastRunText ?? "从未"}',
              ),
              const SizedBox(width: 8),
              _buildStatChip(
                Icons.check_circle_outline,
                '成功率: ${service.successRate.toStringAsFixed(1)}%',
              ),
            ],
          ),
          if (service.lastStatus != null) ...[
            const SizedBox(height: 8),
            Row(
              children: [
                Icon(
                  service.lastStatus == 'completed'
                      ? Icons.check_circle
                      : Icons.error,
                  size: 14,
                  color: service.lastStatus == 'completed'
                      ? AppColors.success
                      : AppColors.error,
                ),
                const SizedBox(width: 4),
                Text(
                  service.lastStatus == 'completed' ? '上次执行成功' : '上次执行失败',
                  style: AppTextStyles.caption.copyWith(
                    color: service.lastStatus == 'completed'
                        ? AppColors.success
                        : AppColors.error,
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildStatChip(IconData icon, String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: AppColors.textSecondary),
          const SizedBox(width: 4),
          Text(
            text,
            style: AppTextStyles.caption.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }
}
