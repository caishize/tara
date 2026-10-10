import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/important_date.dart';
import '../bloc/dates_bloc.dart';

class DateDetailPage extends StatelessWidget {
  final String dateId;

  const DateDetailPage({super.key, required this.dateId});

  @override
  Widget build(BuildContext context) {
    return BlocListener<DatesBloc, DatesState>(
      listener: (context, state) {
        // When date is deleted, show success message and pop
        if (state is DateOperationSuccess && state.message.contains('删除')) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(state.message)),
          );
          context.pop();
        }
      },
      child: BlocBuilder<DatesBloc, DatesState>(
        builder: (context, state) {
          if (state is! DatesLoaded) {
            return Scaffold(
              appBar: AppBar(title: const Text('日期详情')),
              body: const Center(child: CircularProgressIndicator()),
            );
          }

          final date = state.dates.firstWhere(
            (d) => d.id == dateId,
            orElse: () => throw Exception('Date not found'),
          );

          return Scaffold(
          backgroundColor: AppColors.background,
          body: CustomScrollView(
            slivers: [
              _buildAppBar(context, date),
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _buildCountdownCard(date),
                      const SizedBox(height: 20),
                      _buildInfoCard(date),
                      const SizedBox(height: 20),
                      _buildReminderCard(date),
                      const SizedBox(height: 20),
                      _buildActionsCard(context, date),
                    ],
                  ),
                ),
              ),
            ],
          ),
        );
      },
    ),
    );
  }

  Widget _buildAppBar(BuildContext context, ImportantDate date) {
    return SliverAppBar(
      expandedHeight: 200,
      pinned: true,
      backgroundColor: AppColors.primary,
      flexibleSpace: FlexibleSpaceBar(
        title: Text(date.title),
        background: Container(
          decoration: BoxDecoration(
            gradient: _getGradientForType(date.dateType),
          ),
          child: Center(
            child: Text(
              date.dateTypeIcon,
              style: const TextStyle(fontSize: 64),
            ),
          ),
        ),
      ),
      actions: [
        IconButton(
          icon: const Icon(Icons.edit),
          onPressed: () => context.push('/dates/${date.id}/edit'),
        ),
        PopupMenuButton(
          itemBuilder: (context) => [
            const PopupMenuItem(
              value: 'delete',
              child: Row(
                children: [
                  Icon(Icons.delete_outline, color: Colors.red),
                  SizedBox(width: 8),
                  Text('删除', style: TextStyle(color: Colors.red)),
                ],
              ),
            ),
          ],
          onSelected: (value) {
            if (value == 'delete') {
              _showDeleteDialog(context, date);
            }
          },
        ),
      ],
    );
  }

  Widget _buildCountdownCard(ImportantDate date) {
    final days = date.daysUntilNext;
    final isToday = days == 0;

    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: isToday
            ? const LinearGradient(
                colors: [Color(0xFFFF6B6B), Color(0xFFFF8E53)],
              )
            : AppColors.primaryGradient,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        children: [
          Text(
            isToday ? '就是今天!' : '还有',
            style: AppTextStyles.bodyText1.copyWith(
              color: Colors.white.withValues(alpha: 0.9),
            ),
          ),
          if (!isToday) ...[
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  '$days',
                  style: const TextStyle(
                    fontSize: 64,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
                const Padding(
                  padding: EdgeInsets.only(bottom: 12),
                  child: Text(
                    ' 天',
                    style: TextStyle(
                      fontSize: 24,
                      color: Colors.white,
                    ),
                  ),
                ),
              ],
            ),
          ],
          const SizedBox(height: 8),
          Text(
            DateFormat('yyyy年M月d日 EEEE', 'zh_CN').format(date.nextOccurrence),
            style: AppTextStyles.bodyText2.copyWith(
              color: Colors.white.withValues(alpha: 0.9),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInfoCard(ImportantDate date) {
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
          Text('基本信息', style: AppTextStyles.subtitle1),
          const SizedBox(height: 16),
          _buildInfoRow('类型', '${date.dateTypeIcon} ${date.dateTypeName}'),
          _buildInfoRow(
            '日期',
            DateFormat('yyyy年M月d日').format(date.date),
          ),
          _buildInfoRow(
            '日历',
            date.calendarType == CalendarType.solar ? '公历' : '农历',
          ),
          _buildInfoRow('重复', date.isRecurring ? '每年重复' : '不重复'),
          if (date.memberName != null)
            _buildInfoRow('关联成员', date.memberName!),
          if (date.description != null && date.description!.isNotEmpty)
            _buildInfoRow('备注', date.description!),
        ],
      ),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 80,
            child: Text(
              label,
              style: AppTextStyles.bodyText2.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
          ),
          Expanded(
            child: Text(value, style: AppTextStyles.bodyText1),
          ),
        ],
      ),
    );
  }

  Widget _buildReminderCard(ImportantDate date) {
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
          Text('提醒设置', style: AppTextStyles.subtitle1),
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: date.reminderDays.map((days) {
              String label;
              if (days == 0) {
                label = '当天';
              } else if (days == 1) {
                label = '提前1天';
              } else {
                label = '提前$days天';
              }

              return Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.notifications_outlined,
                      size: 16,
                      color: AppColors.primary,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      label,
                      style: AppTextStyles.caption.copyWith(
                        color: AppColors.primary,
                      ),
                    ),
                  ],
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildActionsCard(BuildContext context, ImportantDate date) {
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
          Text('快捷操作', style: AppTextStyles.subtitle1),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _buildActionButton(
                  icon: Icons.card_giftcard,
                  label: '挑选礼物',
                  onTap: () {
                    if (date.memberId != null) {
                      // Navigate to gift recommendation for this member with occasion
                      final occasion = _mapDateTypeToOccasion(date.dateType);
                      context.push(Routes.giftRecommend(
                        date.memberId!,
                        occasion: occasion,
                      ));
                    } else {
                      // Navigate to gift entry to select a member
                      context.push(Routes.giftEntry);
                    }
                  },
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildActionButton(
                  icon: Icons.share_outlined,
                  label: '分享提醒',
                  onTap: () {},
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  /// 将日期类型映射为礼物场景
  String _mapDateTypeToOccasion(DateType dateType) {
    switch (dateType) {
      case DateType.birthday:
        return 'birthday';
      case DateType.anniversary:
        return 'anniversary';
      case DateType.holiday:
        return 'holiday';
      case DateType.memorial:
        return 'other'; // 祭日不太适合送礼，使用 other
      case DateType.custom:
        return 'other';
    }
  }

  Widget _buildActionButton({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.background,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          children: [
            Icon(icon, color: AppColors.primary),
            const SizedBox(height: 8),
            Text(label, style: AppTextStyles.caption),
          ],
        ),
      ),
    );
  }

  LinearGradient _getGradientForType(DateType type) {
    switch (type) {
      case DateType.birthday:
        return const LinearGradient(
          colors: [Color(0xFFFF6B6B), Color(0xFFFFE66D)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      case DateType.anniversary:
        return const LinearGradient(
          colors: [Color(0xFFFF6B9D), Color(0xFFC44569)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      case DateType.holiday:
        return const LinearGradient(
          colors: [Color(0xFF4ECDC4), Color(0xFF44BD32)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      case DateType.memorial:
        return const LinearGradient(
          colors: [Color(0xFF636E72), Color(0xFF2D3436)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      case DateType.custom:
        return AppColors.primaryGradient;
    }
  }

  void _showDeleteDialog(BuildContext context, ImportantDate date) {
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('删除日期'),
        content: Text('确定要删除"${date.title}"吗？此操作不可恢复。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(dialogContext); // Close dialog
              // Trigger delete - BlocListener will handle navigation after success
              context.read<DatesBloc>().add(DateDeleted(date.id));
            },
            child: const Text('删除', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
  }
}
