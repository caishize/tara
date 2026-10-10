import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../app/di/injection.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../../shared/widgets/custom_app_bar.dart';
import '../../domain/entities/work_report.dart';
import '../bloc/work_report_bloc.dart';

class CurationDetailPage extends StatelessWidget {
  final String jobId;

  const CurationDetailPage({super.key, required this.jobId});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (context) => getIt<WorkReportBloc>()
        ..add(CurationDetailRequested(jobId)),
      child: _CurationDetailContent(jobId: jobId),
    );
  }
}

class _CurationDetailContent extends StatelessWidget {
  final String jobId;

  const _CurationDetailContent({required this.jobId});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: const CustomAppBar(title: '整理详情'),
      body: BlocBuilder<WorkReportBloc, WorkReportState>(
        builder: (context, state) {
          if (state is CurationDetailLoading || state is WorkReportInitial) {
            return const Center(child: CircularProgressIndicator());
          }

          if (state is CurationDetailError) {
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
                          .read<WorkReportBloc>()
                          .add(CurationDetailRequested(jobId));
                    },
                    child: const Text('重试'),
                  ),
                ],
              ),
            );
          }

          if (state is CurationDetailLoaded) {
            return _buildContent(state.detail);
          }

          return const Center(child: CircularProgressIndicator());
        },
      ),
    );
  }

  Widget _buildContent(CurationJobDetail detail) {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        // Job header
        _buildJobHeader(detail.job),
        const SizedBox(height: 20),

        // Curated events section
        if (detail.curatedEvents.isNotEmpty) ...[
          _buildSectionHeader(
            Icons.event_available,
            '整理后的行程',
            '${detail.curatedEvents.length} 条',
          ),
          const SizedBox(height: 12),
          ...detail.curatedEvents.map(_buildCuratedEventCard),
          const SizedBox(height: 20),
        ],

        // Associations section
        if (detail.associations.isNotEmpty) ...[
          _buildSectionHeader(
            Icons.link,
            '发现的关联',
            '${detail.associations.length} 条',
          ),
          const SizedBox(height: 12),
          ...detail.associations.map(_buildAssociationCard),
          const SizedBox(height: 20),
        ],

        // Error section
        if (detail.job.isFailed && detail.job.errorMessage != null) ...[
          _buildSectionHeader(
            Icons.error_outline,
            '错误信息',
            null,
          ),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.red.withValues(alpha: 0.05),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                  color: Colors.red.withValues(alpha: 0.2)),
            ),
            child: Text(
              detail.job.errorMessage!,
              style:
                  AppTextStyles.bodyText2.copyWith(color: Colors.red.shade700),
            ),
          ),
        ],

        // Empty state
        if (detail.curatedEvents.isEmpty && detail.associations.isEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 40),
            child: Center(
              child: Column(
                children: [
                  Icon(Icons.inbox_outlined,
                      size: 48, color: AppColors.textTertiary),
                  const SizedBox(height: 12),
                  Text(
                    '此次整理未产生具体数据',
                    style: AppTextStyles.bodyText2
                        .copyWith(color: AppColors.textSecondary),
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildJobHeader(CurationJobSummary job) {
    Color statusColor;
    if (job.isSuccess) {
      statusColor = const Color(0xFF26A69A);
    } else if (job.isFailed) {
      statusColor = Colors.red;
    } else {
      statusColor = Colors.orange;
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: statusColor.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  job.statusText,
                  style: AppTextStyles.subtitle2.copyWith(color: statusColor),
                ),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  job.triggerTypeText,
                  style: AppTextStyles.caption
                      .copyWith(color: AppColors.primary),
                ),
              ),
              if (job.durationText.isNotEmpty) ...[
                const Spacer(),
                Text(
                  job.durationText,
                  style: AppTextStyles.caption
                      .copyWith(color: AppColors.textTertiary),
                ),
              ],
            ],
          ),
          if (job.dateRangeStart != null) ...[
            const SizedBox(height: 12),
            Text(
              '日期范围: ${job.dateRangeStart} ~ ${job.dateRangeEnd ?? ""}',
              style: AppTextStyles.bodyText2
                  .copyWith(color: AppColors.textSecondary),
            ),
          ],
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildHeaderStat('处理', job.eventsProcessed),
              _buildHeaderStat('整理', job.eventsCurated),
              _buildHeaderStat('关联', job.associationsCreated),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildHeaderStat(String label, int value) {
    return Column(
      children: [
        Text(
          '$value',
          style: AppTextStyles.headline5.copyWith(
            color: AppColors.primary,
            fontWeight: FontWeight.bold,
          ),
        ),
        Text(
          label,
          style: AppTextStyles.caption
              .copyWith(color: AppColors.textSecondary),
        ),
      ],
    );
  }

  Widget _buildSectionHeader(IconData icon, String title, String? trailing) {
    return Row(
      children: [
        Icon(icon, color: AppColors.primary, size: 20),
        const SizedBox(width: 8),
        Text(title, style: AppTextStyles.subtitle1),
        if (trailing != null) ...[
          const Spacer(),
          Text(
            trailing,
            style: AppTextStyles.caption
                .copyWith(color: AppColors.textTertiary),
          ),
        ],
      ],
    );
  }

  Widget _buildCuratedEventCard(CuratedEventDetail event) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  event.title,
                  style: AppTextStyles.bodyText1,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  event.eventTypeText,
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.primary,
                    fontSize: 10,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Wrap(
            spacing: 6,
            runSpacing: 4,
            children: [
              if (event.mergedCount > 1)
                _buildMiniChip('合并 ${event.mergedCount} 个来源'),
              ...event.sourceTypes.map((s) => _buildMiniChip(s)),
            ],
          ),
          if (event.dedupReason != null) ...[
            const SizedBox(height: 6),
            Text(
              event.dedupReason!,
              style: AppTextStyles.caption
                  .copyWith(color: AppColors.textSecondary),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildAssociationCard(AssociationDetail assoc) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  assoc.title,
                  style: AppTextStyles.bodyText1,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              _buildMiniChip(assoc.associationTypeText),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            assoc.reason,
            style: AppTextStyles.caption
                .copyWith(color: AppColors.textSecondary),
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }

  Widget _buildMiniChip(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: AppColors.textTertiary.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        text,
        style: AppTextStyles.caption.copyWith(
          color: AppColors.textSecondary,
          fontSize: 10,
        ),
      ),
    );
  }
}
