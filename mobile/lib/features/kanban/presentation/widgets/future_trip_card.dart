import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../data/models/future_view_models.dart';
import '../../data/models/insight_feed_models.dart';
import 'insight_section.dart';

/// Trip card for V4 future timeline view.
///
/// Shows trip header with gradient, participant pills, countdown badge,
/// progress bar. Tasks are collapsed by default; tap header to expand.
class FutureTripCard extends StatefulWidget {
  final FutureViewTripModel trip;
  final void Function(String taskId)? onTaskAction;
  final void Function(String taskId, bool done)? onTaskToggle;
  final VoidCallback? onTap;
  final void Function(InsightFeedItemModel)? onInsightTap;
  final Future<bool> Function(InsightFeedItemModel)? onInsightDismiss;
  final void Function(
    InsightFeedItemModel insight,
    String actionType,
    Map<String, dynamic>? payload,
  )? onInsightActionTap;

  const FutureTripCard({
    super.key,
    required this.trip,
    this.onTaskAction,
    this.onTaskToggle,
    this.onTap,
    this.onInsightTap,
    this.onInsightDismiss,
    this.onInsightActionTap,
  });

  @override
  State<FutureTripCard> createState() => _FutureTripCardState();
}

class _FutureTripCardState extends State<FutureTripCard>
    with SingleTickerProviderStateMixin {
  bool _expanded = false;
  late final AnimationController _animController;
  late final Animation<double> _expandAnimation;

  FutureViewTripModel get trip => widget.trip;

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      duration: const Duration(milliseconds: 250),
      vsync: this,
    );
    _expandAnimation = CurvedAnimation(
      parent: _animController,
      curve: Curves.easeInOut,
    );
  }

  @override
  void dispose() {
    _animController.dispose();
    super.dispose();
  }

  void _toggleExpand() {
    setState(() {
      _expanded = !_expanded;
      if (_expanded) {
        _animController.forward();
      } else {
        _animController.reverse();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.divider, width: 1),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF1A1918).withValues(alpha: 0.03),
            blurRadius: 12,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _buildHeader(),
          if (trip.tasks.isNotEmpty)
            SizeTransition(
              sizeFactor: _expandAnimation,
              axisAlignment: -1.0,
              child: Column(
                children: trip.tasks.map(_buildTaskRow).toList(),
              ),
            ),
          if (trip.insights.isNotEmpty) _buildInsightSection(),
          if (trip.tasks.isNotEmpty) _buildExpandHint(),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    final isBusiness = trip.isBusiness;
    final gradientStart = isBusiness
        ? const Color(0xFF3D8A5A).withValues(alpha: 0.09)
        : const Color(0xFFD89575).withValues(alpha: 0.09);
    final gradientEnd = isBusiness
        ? const Color(0xFF3D8A5A).withValues(alpha: 0.03)
        : const Color(0xFFD89575).withValues(alpha: 0.03);

    return GestureDetector(
      onTap: trip.tasks.isNotEmpty ? _toggleExpand : widget.onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: const EdgeInsets.fromLTRB(16, 14, 16, 12),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [gradientStart, gradientEnd],
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildTopRow(),
            const SizedBox(height: 10),
            _buildMetaRow(),
            if (trip.participants.isNotEmpty) ...[
              const SizedBox(height: 8),
              _buildPeopleRow(),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildTopRow() {
    return Row(
      children: [
        Expanded(
          child: Text(
            '${trip.emoji} ${trip.name}',
            style: const TextStyle(
              fontSize: 17,
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
              height: 1.3,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ),
        const SizedBox(width: 8),
        _buildCountdownBadge(),
      ],
    );
  }

  Widget _buildCountdownBadge() {
    final Color bgColor;
    final String label;

    if (trip.daysUntil <= 0) {
      bgColor = const Color(0xFFD32F2F);
      label = '今天';
    } else if (trip.daysUntil <= 3) {
      bgColor = const Color(0xFFD4A64A);
      label = '${trip.daysUntil}天后';
    } else {
      bgColor = AppColors.textTertiary;
      label = '${trip.daysUntil}天后';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(100),
      ),
      child: Text(
        label,
        style: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: Colors.white,
          height: 1.2,
        ),
      ),
    );
  }

  Widget _buildMetaRow() {
    final progress = trip.totalCount > 0
        ? (trip.doneCount / trip.totalCount).clamp(0.0, 1.0)
        : 0.0;

    return Row(
      children: [
        const Icon(Icons.calendar_today_outlined,
            size: 12, color: AppColors.textTertiary),
        const SizedBox(width: 4),
        Text(
          _formatDateRange(trip.startDate, trip.endDate),
          style: const TextStyle(
            fontSize: 12,
            color: AppColors.textTertiary,
            height: 1.3,
          ),
        ),
        const Spacer(),
        SizedBox(
          width: 48,
          height: 4,
          child: Stack(
            children: [
              Container(
                decoration: BoxDecoration(
                  color: AppColors.divider,
                  borderRadius: BorderRadius.circular(100),
                ),
              ),
              FractionallySizedBox(
                widthFactor: progress,
                child: Container(
                  decoration: BoxDecoration(
                    color: AppColors.accentGreen,
                    borderRadius: BorderRadius.circular(100),
                  ),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: 6),
        Text(
          '${trip.doneCount}/${trip.totalCount}',
          style: const TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: AppColors.accentGreen,
            height: 1.2,
          ),
        ),
      ],
    );
  }

  Widget _buildPeopleRow() {
    return Row(
      children: [
        const Icon(Icons.people_outline,
            size: 12, color: AppColors.textTertiary),
        const SizedBox(width: 6),
        Expanded(
          child: Wrap(
            spacing: 4,
            runSpacing: 4,
            children: trip.participants.map(_buildParticipantPill).toList(),
          ),
        ),
      ],
    );
  }

  Widget _buildParticipantPill(FutureViewTripParticipant participant) {
    final color = participant.colorValue;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(100),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(
              color: color,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 4),
          Text(
            participant.name,
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w500,
              color: color,
              height: 1.2,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInsightSection() {
    return Container(
      decoration: const BoxDecoration(
        border: Border(
          top: BorderSide(color: AppColors.divider, width: 1),
        ),
      ),
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 4),
      child: InsightSection(
        insights: trip.insights,
        maxVisible: 2,
        showActions: false,
        onInsightTap: widget.onInsightTap,
        onInsightDismiss: widget.onInsightDismiss,
        onInsightActionTap: widget.onInsightActionTap,
      ),
    );
  }

  Widget _buildExpandHint() {
    return Container(
      decoration: const BoxDecoration(
        border: Border(
          top: BorderSide(color: AppColors.divider, width: 1),
        ),
      ),
      child: Row(
        children: [
          Expanded(
            child: GestureDetector(
              onTap: _toggleExpand,
              behavior: HitTestBehavior.opaque,
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      _expanded ? '收起' : '展开 ${trip.tasks.length} 项待办',
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppColors.textTertiary,
                        height: 1.2,
                      ),
                    ),
                    const SizedBox(width: 2),
                    AnimatedRotation(
                      turns: _expanded ? 0.5 : 0.0,
                      duration: const Duration(milliseconds: 250),
                      child: const Icon(
                        Icons.keyboard_arrow_down,
                        size: 14,
                        color: AppColors.textTertiary,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          if (_expanded)
            GestureDetector(
              onTap: widget.onTap,
              behavior: HitTestBehavior.opaque,
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      '查看行程',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w500,
                        color: AppColors.accentGreen.withValues(alpha: 0.8),
                        height: 1.2,
                      ),
                    ),
                    const SizedBox(width: 2),
                    Icon(
                      Icons.arrow_forward_ios,
                      size: 10,
                      color: AppColors.accentGreen.withValues(alpha: 0.8),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildTaskRow(FutureViewTripTaskModel task) {
    final isDone = task.done;
    final bgColor = isDone ? AppColors.background : Colors.white;

    return Container(
      decoration: BoxDecoration(
        color: bgColor,
        border: const Border(
          top: BorderSide(color: AppColors.divider, width: 1),
        ),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        children: [
          _buildCheckCircle(task),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  task.title,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                    color: isDone
                        ? AppColors.textTertiary
                        : AppColors.textPrimary,
                    height: 1.3,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                if (task.subtitle.isNotEmpty) ...[
                  const SizedBox(height: 2),
                  Text(
                    task.subtitle,
                    style: const TextStyle(
                      fontSize: 11,
                      color: AppColors.textTertiary,
                      height: 1.3,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(width: 8),
          isDone ? _buildDoneLabel() : _buildActionButton(task),
        ],
      ),
    );
  }

  Widget _buildCheckCircle(FutureViewTripTaskModel task) {
    if (task.done) {
      return GestureDetector(
        onTap: () => widget.onTaskToggle?.call(task.id, false),
        child: Container(
          width: 20,
          height: 20,
          decoration: const BoxDecoration(
            color: AppColors.accentGreen,
            shape: BoxShape.circle,
          ),
          child: const Icon(Icons.check, size: 12, color: Colors.white),
        ),
      );
    }

    final ringColor = task.memberColorValue ?? AppColors.textTertiary;
    return GestureDetector(
      onTap: () => widget.onTaskToggle?.call(task.id, true),
      child: Container(
        width: 20,
        height: 20,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          border: Border.all(color: ringColor, width: 2),
        ),
      ),
    );
  }

  Widget _buildDoneLabel() {
    return const Text(
      '已完成',
      style: TextStyle(
        fontSize: 11,
        fontWeight: FontWeight.w500,
        color: AppColors.textTertiary,
        height: 1.2,
      ),
    );
  }

  Widget _buildActionButton(FutureViewTripTaskModel task) {
    if (task.actionLabel.isEmpty) return const SizedBox.shrink();

    final isPrimary = task.isPrimaryAction;
    final bgColor = isPrimary
        ? AppColors.accentGreen
        : const Color(0xFFEDECEA);
    final textColor = isPrimary
        ? Colors.white
        : AppColors.textSecondary;

    return GestureDetector(
      onTap: () => widget.onTaskAction?.call(task.id),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: bgColor,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(
          task.actionLabel,
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: textColor,
            height: 1.2,
          ),
        ),
      ),
    );
  }

  String _formatDateRange(DateTime start, DateTime end) {
    final startStr = '${start.month}/${start.day}';
    final endStr = '${end.month}/${end.day}';
    return '$startStr - $endStr';
  }
}
