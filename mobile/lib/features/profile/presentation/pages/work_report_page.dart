import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../app/di/injection.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../../shared/widgets/custom_app_bar.dart';
import '../../domain/entities/secretary_report.dart';
import '../bloc/work_report_bloc.dart';

class WorkReportPage extends StatelessWidget {
  const WorkReportPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (context) =>
          getIt<WorkReportBloc>()..add(const WorkReportLoadRequested()),
      child: const _WorkReportPageContent(),
    );
  }
}

class _WorkReportPageContent extends StatefulWidget {
  const _WorkReportPageContent();

  @override
  State<_WorkReportPageContent> createState() => _WorkReportPageContentState();
}

class _WorkReportPageContentState extends State<_WorkReportPageContent> {
  String _selectedRange = 'week';

  static const _ranges = [
    ('today', '今天'),
    ('week', '本周'),
    ('month', '本月'),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: const CustomAppBar(title: '秘书工作报告'),
      body: Column(
        children: [
          _buildTimeRangeBar(),
          const Divider(height: 1, color: AppColors.divider),
          Expanded(
            child: BlocBuilder<WorkReportBloc, WorkReportState>(
              builder: (context, state) {
                if (state is WorkReportLoading) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (state is WorkReportError) {
                  return _buildErrorView(context, state.message);
                }

                final report = state is WorkReportLoaded
                    ? state.report
                    : SecretaryReport.empty();

                return RefreshIndicator(
                  onRefresh: () async {
                    context
                        .read<WorkReportBloc>()
                        .add(const WorkReportRefreshRequested());
                  },
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      _HeroSummaryCard(
                        summary: report.summary,
                        rangeLabel: _rangeLabel,
                      ),
                      const SizedBox(height: 16),
                      _TimelineSection(items: report.timeline),
                    ],
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  String get _rangeLabel {
    switch (_selectedRange) {
      case 'today':
        return '今天';
      case 'month':
        return '本月';
      default:
        return '本周';
    }
  }

  Widget _buildTimeRangeBar() {
    return Container(
      color: Colors.white,
      height: 44,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: _ranges.map((entry) {
          final (range, label) = entry;
          final isSelected = _selectedRange == range;
          return GestureDetector(
            onTap: () {
              if (_selectedRange == range) return;
              setState(() => _selectedRange = range);
              context
                  .read<WorkReportBloc>()
                  .add(WorkReportLoadRequested(range: range));
            },
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  label,
                  style: AppTextStyles.bodyText2.copyWith(
                    color: isSelected
                        ? AppColors.accentGreen
                        : AppColors.textTertiary,
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 4),
                if (isSelected)
                  Container(
                    width: 24,
                    height: 3,
                    decoration: BoxDecoration(
                      color: AppColors.accentGreen,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  )
                else
                  const SizedBox(height: 3),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildErrorView(BuildContext context, String message) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.error_outline, size: 48, color: AppColors.textTertiary),
          const SizedBox(height: 16),
          Text(
            message,
            style: AppTextStyles.bodyText2
                .copyWith(color: AppColors.textSecondary),
          ),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: () {
              context
                  .read<WorkReportBloc>()
                  .add(const WorkReportLoadRequested());
            },
            child: const Text('重试'),
          ),
        ],
      ),
    );
  }
}

// ==================== Hero Summary Card ====================

class _HeroSummaryCard extends StatelessWidget {
  final ReportSummary summary;
  final String rangeLabel;

  const _HeroSummaryCard({
    required this.summary,
    required this.rangeLabel,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF667eea), Color(0xFF764ba2)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.auto_awesome, color: Colors.white, size: 20),
              const SizedBox(width: 8),
              Text(
                '$rangeLabel工作总览',
                style: AppTextStyles.headline6.copyWith(color: Colors.white),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: Column(
                  children: [
                    _MetricTile(
                      icon: Icons.calendar_today,
                      value: summary.eventsManaged,
                      label: '事件管理',
                    ),
                    const SizedBox(height: 10),
                    _MetricTile(
                      icon: Icons.psychology,
                      value: summary.memoriesExtracted,
                      label: '记忆提取',
                    ),
                    const SizedBox(height: 10),
                    _MetricTile(
                      icon: Icons.lightbulb_outline,
                      value: summary.insightsGenerated,
                      label: '洞察生成',
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  children: [
                    _MetricTile(
                      icon: Icons.notifications_active,
                      value: summary.remindersSent,
                      label: '提醒发送',
                    ),
                    const SizedBox(height: 10),
                    _MetricTile(
                      icon: Icons.article_outlined,
                      value: summary.briefingsRun,
                      label: '简报推送',
                    ),
                    const SizedBox(height: 10),
                    _MetricTile(
                      icon: Icons.auto_fix_high,
                      value: summary.giftsTracked,
                      label: '行程整理',
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MetricTile extends StatelessWidget {
  final IconData icon;
  final int value;
  final String label;

  const _MetricTile({
    required this.icon,
    required this.value,
    required this.label,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: Colors.white70, size: 18),
          const SizedBox(height: 6),
          Text(
            '$value',
            style: AppTextStyles.numberMedium.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: AppTextStyles.overline.copyWith(
              color: Colors.white70,
              letterSpacing: 0,
              fontSize: 11,
            ),
          ),
        ],
      ),
    );
  }
}

// ==================== Timeline Section ====================

class _TimelineSection extends StatelessWidget {
  final List<ReportTimelineItem> items;

  const _TimelineSection({required this.items});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('活动时间线', style: AppTextStyles.headline6),
            GestureDetector(
              onTap: () {
                // TODO: navigate to full timeline
              },
              child: Text(
                '查看全部',
                style: AppTextStyles.caption.copyWith(
                  color: AppColors.accentGreen,
                  fontSize: 13,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        if (items.isEmpty) _buildEmptyTimeline(),
        ...items.map((item) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: _TimelineItemCard(item: item),
            )),
      ],
    );
  }

  Widget _buildEmptyTimeline() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 32),
      child: Column(
        children: [
          Icon(Icons.timeline, size: 48, color: AppColors.textTertiary),
          const SizedBox(height: 12),
          Text(
            '暂无活动记录',
            style: AppTextStyles.bodyText2
                .copyWith(color: AppColors.textSecondary),
          ),
          const SizedBox(height: 4),
          Text(
            '秘书正在为您默默工作中...',
            style:
                AppTextStyles.caption.copyWith(color: AppColors.textTertiary),
          ),
        ],
      ),
    );
  }
}

class _TimelineItemCard extends StatelessWidget {
  final ReportTimelineItem item;

  const _TimelineItemCard({required this.item});

  @override
  Widget build(BuildContext context) {
    final config = _actionConfig(item.actionType);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: config.color,
              borderRadius: BorderRadius.circular(4),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.description,
                  style: AppTextStyles.subtitle2.copyWith(
                    color: AppColors.textPrimary,
                    fontWeight: FontWeight.w500,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Text(
                  _formatTimestamp(item),
                  style: AppTextStyles.overline.copyWith(
                    color: AppColors.textTertiary,
                    letterSpacing: 0,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Icon(config.icon, size: 18, color: config.color),
        ],
      ),
    );
  }

  String _formatTimestamp(ReportTimelineItem item) {
    final dt = item.dateTime;
    if (dt == null) return item.actionType;

    final now = DateTime.now();
    String dateStr;
    if (dt.year == now.year && dt.month == now.month && dt.day == now.day) {
      dateStr = '今天';
    } else if (dt.year == now.year &&
        dt.month == now.month &&
        dt.day == now.day - 1) {
      dateStr = '昨天';
    } else {
      dateStr = '${dt.month}/${dt.day}';
    }

    final timeStr =
        '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    final typeLabel = _actionTypeLabel(item.actionType);
    return '$dateStr $timeStr · $typeLabel';
  }

  static String _actionTypeLabel(String actionType) {
    switch (actionType) {
      case 'curation_job':
        return '行程整理';
      case 'memory_extraction':
        return '记忆提取';
      case 'insight_generation':
        return '洞察生成';
      case 'reminder_trigger':
        return '提醒发送';
      case 'briefing':
        return '简报推送';
      case 'gift_tracking':
        return '礼物追踪';
      default:
        return '工具执行';
    }
  }

  static _ActionConfig _actionConfig(String actionType) {
    switch (actionType) {
      case 'curation_job':
        return _ActionConfig(
          icon: Icons.calendar_today,
          color: AppColors.accentGreen,
        );
      case 'memory_extraction':
        return _ActionConfig(
          icon: Icons.psychology,
          color: const Color(0xFF5C6BC0),
        );
      case 'insight_generation':
        return _ActionConfig(
          icon: Icons.lightbulb_outline,
          color: const Color(0xFF26A69A),
        );
      case 'reminder_trigger':
        return _ActionConfig(
          icon: Icons.notifications_active,
          color: AppColors.accentWarm,
        );
      case 'briefing':
        return _ActionConfig(
          icon: Icons.article_outlined,
          color: const Color(0xFF5C6BC0),
        );
      default:
        return _ActionConfig(
          icon: Icons.build_outlined,
          color: AppColors.textTertiary,
        );
    }
  }
}

class _ActionConfig {
  final IconData icon;
  final Color color;

  const _ActionConfig({required this.icon, required this.color});
}
