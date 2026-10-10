import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:shimmer/shimmer.dart';

import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../profile/domain/entities/activity_record.dart';

class RecentActivitiesCard extends StatefulWidget {
  final List<ActivityRecord> activities;
  final bool isLoading;
  final VoidCallback? onRefresh;

  const RecentActivitiesCard({
    super.key,
    required this.activities,
    this.isLoading = false,
    this.onRefresh,
  });

  @override
  State<RecentActivitiesCard> createState() => _RecentActivitiesCardState();
}

class _RecentActivitiesCardState extends State<RecentActivitiesCard>
    with TickerProviderStateMixin {
  late AnimationController _pulseController;
  late AnimationController _staggerController;
  bool _isExpanded = false;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);
    _staggerController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    );

    if (!widget.isLoading && widget.activities.isNotEmpty) {
      _staggerController.forward();
    }
  }

  @override
  void didUpdateWidget(RecentActivitiesCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.isLoading && !widget.isLoading) {
      _staggerController.forward(from: 0);
    }
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _staggerController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.isLoading) return _buildLoading();
    if (widget.activities.isEmpty) return _buildEmpty();
    return _buildContent(context);
  }

  Widget _buildLoading() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Shimmer.fromColors(
        baseColor: Colors.grey[200]!,
        highlightColor: Colors.grey[50]!,
        child: Container(
          height: 280,
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(24),
          ),
        ),
      ),
    );
  }

  Widget _buildEmpty() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20),
      padding: const EdgeInsets.symmetric(vertical: 48, horizontal: 32),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Colors.white,
            AppColors.primary.withValues(alpha: 0.02),
          ],
        ),
        borderRadius: BorderRadius.circular(28),
        border: Border.all(color: AppColors.divider.withValues(alpha: 0.5)),
      ),
      child: Column(
        children: [
          AnimatedBuilder(
            animation: _pulseController,
            builder: (context, _) {
              return Transform.scale(
                scale: 1.0 + _pulseController.value * 0.1,
                child: Container(
                  width: 72,
                  height: 72,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        AppColors.primary.withValues(alpha: 0.1),
                        AppColors.secondary.withValues(alpha: 0.1),
                      ],
                    ),
                    borderRadius: BorderRadius.circular(24),
                  ),
                  child: Icon(
                    Icons.inbox_rounded,
                    size: 32,
                    color: AppColors.primary.withValues(alpha: 0.5),
                  ),
                ),
              );
            },
          ),
          const SizedBox(height: 20),
          Text(
            '暂无动态',
            style: AppTextStyles.subtitle1.copyWith(fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 8),
          Text(
            '您的智能提醒和通知会显示在这里',
            style: AppTextStyles.bodyText2.copyWith(color: AppColors.textTertiary),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildContent(BuildContext context) {
    final newCount = widget.activities
        .where((a) => DateTime.now().difference(a.createdAt).inHours < 2)
        .length;
    final displayCount = _isExpanded ? widget.activities.length : math.min(5, widget.activities.length);
    final displayActivities = widget.activities.take(displayCount).toList();

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 20,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          // Header
          _buildHeader(context, newCount),

          // Timeline list
          AnimatedContainer(
            duration: const Duration(milliseconds: 300),
            curve: Curves.easeInOut,
            child: ListView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              padding: EdgeInsets.zero,
              itemCount: displayActivities.length,
              itemBuilder: (context, index) {
                final activity = displayActivities[index];
                final isLast = index == displayActivities.length - 1;
                final delay = index * 0.1;

                return _TimelineItem(
                  activity: activity,
                  isLast: isLast,
                  animation: CurvedAnimation(
                    parent: _staggerController,
                    curve: Interval(
                      delay.clamp(0.0, 0.6),
                      (delay + 0.4).clamp(0.0, 1.0),
                      curve: Curves.easeOutCubic,
                    ),
                  ),
                );
              },
            ),
          ),

          // Footer
          if (widget.activities.length > 5) _buildFooter(),
        ],
      ),
    );
  }

  Widget _buildHeader(BuildContext context, int newCount) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppColors.primary.withValues(alpha: 0.05),
            AppColors.secondary.withValues(alpha: 0.02),
          ],
        ),
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Row(
        children: [
          // Animated icon
          AnimatedBuilder(
            animation: _pulseController,
            builder: (context, _) {
              return Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  gradient: AppColors.primaryGradient,
                  borderRadius: BorderRadius.circular(14),
                  boxShadow: [
                    BoxShadow(
                      color: AppColors.primary.withValues(
                        alpha: 0.2 + _pulseController.value * 0.1,
                      ),
                      blurRadius: 8 + _pulseController.value * 4,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
                child: const Icon(
                  Icons.bolt_rounded,
                  color: Colors.white,
                  size: 22,
                ),
              );
            },
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      '最新动态',
                      style: AppTextStyles.subtitle1.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    if (newCount > 0) ...[
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 3,
                        ),
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(
                            colors: [Color(0xFFFF6B6B), Color(0xFFFF8E53)],
                          ),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Text(
                          '$newCount 新',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  '共 ${widget.activities.length} 条记录',
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.textTertiary,
                  ),
                ),
              ],
            ),
          ),
          TextButton.icon(
            onPressed: () {
              HapticFeedback.lightImpact();
              context.push(Routes.activityTimeline);
            },
            icon: Text(
              '全部',
              style: AppTextStyles.caption.copyWith(
                color: AppColors.primary,
                fontWeight: FontWeight.w600,
              ),
            ),
            label: const Icon(
              Icons.arrow_forward_ios_rounded,
              size: 12,
              color: AppColors.primary,
            ),
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              backgroundColor: AppColors.primary.withValues(alpha: 0.08),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFooter() {
    return GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick();
        setState(() => _isExpanded = !_isExpanded);
      },
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          color: AppColors.background,
          borderRadius: const BorderRadius.vertical(bottom: Radius.circular(24)),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              _isExpanded ? '收起' : '展开更多 (${widget.activities.length - 5})',
              style: AppTextStyles.caption.copyWith(
                color: AppColors.textSecondary,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(width: 4),
            AnimatedRotation(
              turns: _isExpanded ? 0.5 : 0,
              duration: const Duration(milliseconds: 200),
              child: Icon(
                Icons.keyboard_arrow_down_rounded,
                size: 18,
                color: AppColors.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _TimelineItem extends StatefulWidget {
  final ActivityRecord activity;
  final bool isLast;
  final Animation<double> animation;

  const _TimelineItem({
    required this.activity,
    required this.isLast,
    required this.animation,
  });

  @override
  State<_TimelineItem> createState() => _TimelineItemState();
}

class _TimelineItemState extends State<_TimelineItem> {
  bool _isPressed = false;

  Color get _color {
    switch (widget.activity.type) {
      case ActivityType.reminder:
        return const Color(0xFF6366F1);
      case ActivityType.giftRecommendation:
        return const Color(0xFFEC4899);
      case ActivityType.priceAlert:
        return const Color(0xFF06B6D4);
      case ActivityType.holidaySync:
        return const Color(0xFFF59E0B);
      case ActivityType.holidayPreparation:
        return const Color(0xFF8B5CF6);
      case ActivityType.other:
        return AppColors.primary;
    }
  }

  IconData get _icon {
    switch (widget.activity.type) {
      case ActivityType.reminder:
        return Icons.notifications_active_rounded;
      case ActivityType.giftRecommendation:
        return Icons.redeem_rounded;
      case ActivityType.priceAlert:
        return Icons.trending_down_rounded;
      case ActivityType.holidaySync:
        return Icons.celebration_rounded;
      case ActivityType.holidayPreparation:
        return Icons.card_giftcard_rounded;
      case ActivityType.other:
        return Icons.auto_awesome_rounded;
    }
  }

  @override
  Widget build(BuildContext context) {
    final isNew = DateTime.now().difference(widget.activity.createdAt).inHours < 2;

    return FadeTransition(
      opacity: widget.animation,
      child: SlideTransition(
        position: Tween<Offset>(
          begin: const Offset(0.1, 0),
          end: Offset.zero,
        ).animate(widget.animation),
        child: GestureDetector(
          onTapDown: (_) => setState(() => _isPressed = true),
          onTapUp: (_) => setState(() => _isPressed = false),
          onTapCancel: () => setState(() => _isPressed = false),
          onTap: () {
            HapticFeedback.lightImpact();
            context.push(Routes.activityTimeline);
          },
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 100),
            color: _isPressed
                ? AppColors.primary.withValues(alpha: 0.03)
                : Colors.transparent,
            child: IntrinsicHeight(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Timeline indicator
                  SizedBox(
                    width: 60,
                    child: Column(
                      children: [
                        // Line above
                        Expanded(
                          child: Container(
                            width: 2,
                            color: AppColors.divider.withValues(alpha: 0.5),
                          ),
                        ),
                        // Dot
                        Container(
                          width: 36,
                          height: 36,
                          decoration: BoxDecoration(
                            color: _color.withValues(alpha: 0.1),
                            shape: BoxShape.circle,
                            border: Border.all(
                              color: _color.withValues(alpha: 0.3),
                              width: 2,
                            ),
                          ),
                          child: Icon(_icon, color: _color, size: 16),
                        ),
                        // Line below
                        Expanded(
                          child: Container(
                            width: 2,
                            color: widget.isLast
                                ? Colors.transparent
                                : AppColors.divider.withValues(alpha: 0.5),
                          ),
                        ),
                      ],
                    ),
                  ),

                  // Content
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(4, 12, 20, 12),
                      child: Row(
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Row(
                                  children: [
                                    Container(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 8,
                                        vertical: 3,
                                      ),
                                      decoration: BoxDecoration(
                                        color: _color.withValues(alpha: 0.1),
                                        borderRadius: BorderRadius.circular(6),
                                      ),
                                      child: Text(
                                        widget.activity.typeText,
                                        style: TextStyle(
                                          color: _color,
                                          fontSize: 10,
                                          fontWeight: FontWeight.w600,
                                        ),
                                      ),
                                    ),
                                    if (isNew) ...[
                                      const SizedBox(width: 6),
                                      Container(
                                        width: 6,
                                        height: 6,
                                        decoration: const BoxDecoration(
                                          color: Color(0xFFFF6B6B),
                                          shape: BoxShape.circle,
                                        ),
                                      ),
                                    ],
                                    const Spacer(),
                                    Text(
                                      widget.activity.relativeTimeText,
                                      style: AppTextStyles.caption.copyWith(
                                        color: AppColors.textTertiary,
                                        fontSize: 11,
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 6),
                                Text(
                                  widget.activity.title,
                                  style: AppTextStyles.bodyText2.copyWith(
                                    fontWeight: FontWeight.w600,
                                    height: 1.3,
                                  ),
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                ),
                                if (widget.activity.description != null) ...[
                                  const SizedBox(height: 4),
                                  Text(
                                    widget.activity.description!,
                                    style: AppTextStyles.caption.copyWith(
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
                          Icon(
                            Icons.chevron_right_rounded,
                            color: AppColors.textTertiary.withValues(alpha: 0.5),
                            size: 20,
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
