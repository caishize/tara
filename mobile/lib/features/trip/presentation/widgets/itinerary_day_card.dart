import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../../../app/theme/app_colors.dart';
import '../../domain/entities/itinerary.dart';
import 'add_activity_sheet.dart';
import 'day_swap_dialog.dart';
import 'activity_action_menu.dart';

class ItineraryDayCard extends StatefulWidget {
  final DayItinerary dayItinerary;
  final DateTime date;
  final String? tripId;
  final List<DayItinerary>? allDays;
  final Function(int activityIndex)? onActivityDeleted;
  final Function(int sourceDay, int targetDay)? onDaySwap;
  final Function(String time, String title, String? activityType,
      String? location, double? estimatedCost)? onActivityAdded;

  const ItineraryDayCard({
    super.key,
    required this.dayItinerary,
    required this.date,
    this.tripId,
    this.allDays,
    this.onActivityDeleted,
    this.onDaySwap,
    this.onActivityAdded,
  });

  @override
  State<ItineraryDayCard> createState() => _ItineraryDayCardState();
}

class _ItineraryDayCardState extends State<ItineraryDayCard> {
  late bool _isExpanded;

  bool get _isPast {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final cardDate = DateTime(
      widget.date.year,
      widget.date.month,
      widget.date.day,
    );
    return cardDate.isBefore(today);
  }

  bool get _isToday {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final cardDate = DateTime(
      widget.date.year,
      widget.date.month,
      widget.date.day,
    );
    return cardDate.isAtSameMomentAs(today);
  }

  @override
  void initState() {
    super.initState();
    // Past days collapsed by default, today and future expanded
    _isExpanded = !_isPast;
  }

  @override
  Widget build(BuildContext context) {
    final dateFormat = DateFormat('MM月dd日 EEEE', 'zh_CN');

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: _isToday
            ? Border.all(color: AppColors.accent1, width: 0.5)
            : null,
        boxShadow: _isToday
            ? AppColors.todayGlow(AppColors.accent1)
            : AppColors.cardShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Day header - always visible, tappable for past days
          _buildDayHeader(dateFormat),
          // Activities - collapsible via AnimatedCrossFade
          AnimatedCrossFade(
            firstChild: const SizedBox(width: double.infinity, height: 0),
            secondChild: _buildActivitiesContent(),
            crossFadeState: _isExpanded
                ? CrossFadeState.showSecond
                : CrossFadeState.showFirst,
            duration: const Duration(milliseconds: 250),
          ),
        ],
      ),
    );
  }

  Widget _buildDayHeader(DateFormat dateFormat) {
    final dayCircleColor = _isPast
        ? AppColors.textTertiary
        : _isToday
            ? AppColors.accent1
            : AppColors.primary;

    return GestureDetector(
      onTap: _isPast ? () => setState(() => _isExpanded = !_isExpanded) : null,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: _isToday
              ? AppColors.accent1.withValues(alpha: 0.08)
              : _isPast
                  ? AppColors.chipBackground
                  : AppColors.chipBackground,
          borderRadius: _isExpanded
              ? const BorderRadius.only(
                  topLeft: Radius.circular(12),
                  topRight: Radius.circular(12),
                )
              : BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            // Left accent for today
            if (_isToday)
              Container(
                width: 4,
                height: 36,
                margin: const EdgeInsets.only(right: 10),
                decoration: BoxDecoration(
                  color: AppColors.accent1,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            // Day circle
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: dayCircleColor,
                shape: BoxShape.circle,
              ),
              child: Center(
                child: Text(
                  'D${widget.dayItinerary.dayNumber}',
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                    fontSize: 13,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),
            // Date + TODAY badge
            Expanded(
              child: Row(
                children: [
                  Text(
                    dateFormat.format(widget.date),
                    style: TextStyle(
                      color: _isPast
                          ? AppColors.textTertiary
                          : AppColors.textPrimary,
                      fontWeight: FontWeight.w500,
                      fontSize: 15,
                    ),
                  ),
                  if (_isToday) ...[
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        color: AppColors.accent1,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Text(
                        'TODAY',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: Colors.white,
                          letterSpacing: 0.5,
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
            // Cost
            Text(
              '¥${widget.dayItinerary.totalEstimatedCost.toStringAsFixed(0)}',
              style: TextStyle(
                color: _isPast
                    ? AppColors.textTertiary
                    : AppColors.textSecondary,
                fontWeight: FontWeight.w500,
                fontSize: 13,
              ),
            ),
            // Swap button
            if (widget.onDaySwap != null &&
                widget.allDays != null &&
                widget.allDays!.length > 1)
              IconButton(
                icon: const Icon(Icons.swap_horiz, size: 20),
                onPressed: () => _showDaySwapDialog(context),
                tooltip: '交换日程',
                color: AppColors.textTertiary,
                padding: const EdgeInsets.only(left: 8),
                constraints: const BoxConstraints(),
              ),
            // Expand/collapse indicator for past days
            if (_isPast)
              Icon(
                _isExpanded ? Icons.expand_less : Icons.expand_more,
                size: 20,
                color: AppColors.textTertiary,
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildActivitiesContent() {
    return Column(
      children: [
        // Activities
        if (widget.dayItinerary.activities.isEmpty)
          Padding(
            padding: const EdgeInsets.all(24),
            child: Center(
              child: Text(
                '暂无行程安排',
                style: TextStyle(color: AppColors.textTertiary),
              ),
            ),
          )
        else
          ListView.separated(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: widget.dayItinerary.activities.length,
            separatorBuilder: (context, index) => Divider(
              height: 1,
              indent: 56,
              color: AppColors.divider,
            ),
            itemBuilder: (context, index) {
              final activity = widget.dayItinerary.activities[index];
              return _ActivityItem(
                activity: activity,
                activityIndex: index,
                isMuted: _isPast,
                onDelete: widget.onActivityDeleted != null
                    ? () => widget.onActivityDeleted!(index)
                    : null,
              );
            },
          ),

        // Add activity button
        if (widget.onActivityAdded != null || widget.tripId != null)
          Padding(
            padding: const EdgeInsets.all(12),
            child: AddActivityButton(
              dayNumber: widget.dayItinerary.dayNumber,
              onTap: () => _showAddActivitySheet(context),
            ),
          ),

        // Packing notes
        if (widget.dayItinerary.packingNotes != null) ...[
          Divider(height: 1, color: AppColors.divider),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  Icons.backpack,
                  size: 20,
                  color: AppColors.textTertiary,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    widget.dayItinerary.packingNotes!,
                    style: TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 14,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }

  void _showDaySwapDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => DaySwapDialog(
        days: widget.allDays!,
        currentDayNumber: widget.dayItinerary.dayNumber,
        onSwap: widget.onDaySwap!,
      ),
    );
  }

  void _showAddActivitySheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => AddActivitySheet(
        dayNumber: widget.dayItinerary.dayNumber,
        onSubmit: (time, title, activityType, location, estimatedCost) {
          widget.onActivityAdded
              ?.call(time, title, activityType, location, estimatedCost);
        },
      ),
    );
  }
}

class _ActivityItem extends StatefulWidget {
  final ItineraryActivity activity;
  final int activityIndex;
  final bool isMuted;
  final VoidCallback? onDelete;

  const _ActivityItem({
    required this.activity,
    required this.activityIndex,
    this.isMuted = false,
    this.onDelete,
  });

  @override
  State<_ActivityItem> createState() => _ActivityItemState();
}

class _ActivityItemState extends State<_ActivityItem> {
  bool _isExpanded = false;

  @override
  Widget build(BuildContext context) {
    final mutedOpacity = widget.isMuted ? 0.6 : 1.0;

    return Opacity(
      opacity: mutedOpacity,
      child: Column(
        children: [
          InkWell(
            onTap: () {
              if (widget.activity.professionalAdvice != null ||
                  widget.activity.description != null) {
                setState(() => _isExpanded = !_isExpanded);
              } else {
                _showActivityDetail(context);
              }
            },
            child: Padding(
              padding:
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Time column
                  SizedBox(
                    width: 44,
                    child: Text(
                      widget.activity.time ?? '--:--',
                      style: TextStyle(
                        color: AppColors.textTertiary,
                        fontSize: 13,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                  // Icon
                  Container(
                    width: 32,
                    height: 32,
                    decoration: BoxDecoration(
                      color: _getActivityColor(widget.activity.activityType)
                          .withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Center(
                      child: Text(
                        widget.activity.activityTypeIcon,
                        style: const TextStyle(fontSize: 16),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  // Content
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          widget.activity.title,
                          style: const TextStyle(
                            fontWeight: FontWeight.w500,
                            fontSize: 15,
                          ),
                        ),
                        if (widget.activity.location != null) ...[
                          const SizedBox(height: 4),
                          Row(
                            children: [
                              Icon(
                                Icons.location_on,
                                size: 14,
                                color: AppColors.textTertiary,
                              ),
                              const SizedBox(width: 4),
                              Expanded(
                                child: Text(
                                  widget.activity.location!,
                                  style: TextStyle(
                                    color: AppColors.textTertiary,
                                    fontSize: 13,
                                  ),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ],
                          ),
                        ],
                        // Expand indicator if has advice
                        if (widget.activity.professionalAdvice != null)
                          Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: Row(
                              children: [
                                Icon(
                                  _isExpanded
                                      ? Icons.expand_less
                                      : Icons.expand_more,
                                  size: 16,
                                  color: AppColors.primary,
                                ),
                                const SizedBox(width: 4),
                                Text(
                                  _isExpanded ? '收起建议' : '查看专业建议',
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: AppColors.primary,
                                  ),
                                ),
                              ],
                            ),
                          ),
                      ],
                    ),
                  ),
                  // Cost and actions
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      if (widget.activity.estimatedCost != null)
                        Text(
                          '¥${widget.activity.estimatedCost!.toStringAsFixed(0)}',
                          style: TextStyle(
                            color: AppColors.textTertiary,
                            fontSize: 13,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      if (widget.onDelete != null)
                        ActivityActionMenu(
                          activity: widget.activity,
                          activityIndex: widget.activityIndex,
                          onDelete: widget.onDelete,
                          onViewDetails: () => _showActivityDetail(context),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          // Expanded content (professional advice)
          AnimatedCrossFade(
            firstChild: const SizedBox(width: double.infinity, height: 0),
            secondChild: widget.activity.professionalAdvice != null
                ? Padding(
                    padding: const EdgeInsets.fromLTRB(56, 0, 16, 12),
                    child: _buildExpandedContent(),
                  )
                : const SizedBox.shrink(),
            crossFadeState: _isExpanded
                ? CrossFadeState.showSecond
                : CrossFadeState.showFirst,
            duration: const Duration(milliseconds: 200),
          ),
        ],
      ),
    );
  }

  Widget _buildExpandedContent() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (widget.activity.description != null) ...[
          Text(
            widget.activity.description!,
            style: TextStyle(
              color: AppColors.textSecondary,
              fontSize: 13,
            ),
          ),
          const SizedBox(height: 8),
        ],
        if (widget.activity.professionalAdvice != null)
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.badgeBlue,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: AppColors.primary.withValues(alpha: 0.15),
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Text('🎯', style: TextStyle(fontSize: 14)),
                    const SizedBox(width: 4),
                    Text(
                      '旅行家建议',
                      style: TextStyle(
                        fontWeight: FontWeight.w600,
                        color: AppColors.primary,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  widget.activity.professionalAdvice!,
                  style: TextStyle(
                    fontSize: 13,
                    color: AppColors.textPrimary,
                    height: 1.4,
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }

  void _showActivityDetail(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => DraggableScrollableSheet(
        initialChildSize: 0.6,
        minChildSize: 0.3,
        maxChildSize: 0.9,
        expand: false,
        builder: (context, scrollController) {
          return SingleChildScrollView(
            controller: scrollController,
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(
                    width: 40,
                    height: 4,
                    decoration: BoxDecoration(
                      color: AppColors.divider,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                ),
                const SizedBox(height: 24),
                Row(
                  children: [
                    Text(
                      widget.activity.activityTypeIcon,
                      style: const TextStyle(fontSize: 32),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            widget.activity.title,
                            style: const TextStyle(
                              fontSize: 20,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          Text(
                            widget.activity.activityTypeName,
                            style: TextStyle(color: AppColors.textTertiary),
                          ),
                        ],
                      ),
                    ),
                    if (widget.onDelete != null)
                      IconButton(
                        icon: Icon(Icons.delete_outline,
                            color: AppColors.error),
                        onPressed: () {
                          Navigator.pop(context);
                          _showDeleteConfirmation(context);
                        },
                      ),
                  ],
                ),
                const SizedBox(height: 24),
                if (widget.activity.time != null)
                  _buildInfoRow('时间', widget.activity.time!),
                if (widget.activity.location != null)
                  _buildInfoRow('地点', widget.activity.location!),
                if (widget.activity.description != null)
                  _buildInfoRow('描述', widget.activity.description!),
                if (widget.activity.estimatedCost != null)
                  _buildInfoRow(
                    '预估费用',
                    '¥${widget.activity.estimatedCost!.toStringAsFixed(0)}',
                  ),
                if (widget.activity.bookingInfo != null)
                  _buildInfoRow('预订信息', widget.activity.bookingInfo!),
                if (widget.activity.professionalAdvice != null) ...[
                  const SizedBox(height: 16),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppColors.badgeBlue,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Row(
                          children: [
                            Icon(Icons.lightbulb,
                                color: AppColors.accent1, size: 20),
                            SizedBox(width: 8),
                            Text(
                              '旅行家建议',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 16,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(widget.activity.professionalAdvice!),
                      ],
                    ),
                  ),
                ],
                if (widget.activity.alternatives != null &&
                    widget.activity.alternatives!.isNotEmpty) ...[
                  const SizedBox(height: 16),
                  const Text(
                    '备选方案',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                    ),
                  ),
                  const SizedBox(height: 8),
                  ...widget.activity.alternatives!.map(
                    (alt) => Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: Row(
                        children: [
                          const Icon(Icons.swap_horiz, size: 16),
                          const SizedBox(width: 8),
                          Text(alt),
                        ],
                      ),
                    ),
                  ),
                ],
              ],
            ),
          );
        },
      ),
    );
  }

  void _showDeleteConfirmation(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('删除活动'),
        content: Text('确定要删除"${widget.activity.title}"吗？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              widget.onDelete?.call();
            },
            style: TextButton.styleFrom(foregroundColor: AppColors.error),
            child: const Text('删除'),
          ),
        ],
      ),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 80,
            child: Text(
              label,
              style: TextStyle(color: AppColors.textTertiary),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(fontWeight: FontWeight.w500),
            ),
          ),
        ],
      ),
    );
  }

  Color _getActivityColor(ActivityType type) {
    switch (type) {
      case ActivityType.transportation:
        return const Color(0xFF42A5F5);
      case ActivityType.accommodation:
        return const Color(0xFFAB47BC);
      case ActivityType.attraction:
        return const Color(0xFFFFA726);
      case ActivityType.dining:
        return AppColors.success;
      case ActivityType.shopping:
        return const Color(0xFFEC407A);
      case ActivityType.rest:
        return const Color(0xFF26A69A);
      case ActivityType.other:
        return AppColors.textTertiary;
    }
  }
}
