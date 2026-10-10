import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../data/datasources/insight_graph_remote_datasource.dart';
import '../../domain/entities/associated_item.dart';
import '../../domain/entities/conflict_alert.dart';
import '../../domain/entities/core_event.dart';
import '../bloc/insight_graph_bloc.dart';
import '../bloc/insight_graph_event.dart';
import '../bloc/insight_graph_state.dart';
import '../widgets/associated_item_card.dart';
import '../widgets/associated_item_detail_sheet.dart';
import '../widgets/conflict_alert_card.dart';
import '../widgets/core_event_card.dart';
import '../widgets/event_graph_view.dart';
import '../widgets/priority_badge.dart';

/// 动态图谱页面 (standalone — creates its own BLoC)
///
/// Use [InsightGraphView] directly when the BLoC is provided externally
/// (e.g. from MainShell for tab-switch refresh support).
class InsightGraphPage extends StatelessWidget {
  const InsightGraphPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (context) => GetIt.I<InsightGraphBloc>()
        ..add(const LoadInsightGraph())
        ..add(const LoadUpcomingTrips()), // PRD 2.3.2: 同时加载行程列表
      child: const InsightGraphView(),
    );
  }
}

/// The core view widget — expects an [InsightGraphBloc] in the widget tree.
class InsightGraphView extends StatelessWidget {
  const InsightGraphView({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: BlocBuilder<InsightGraphBloc, InsightGraphState>(
          builder: (context, state) {
            if (state is InsightGraphLoading) {
              return const _LoadingView();
            }

            if (state is InsightGraphError) {
              return _ErrorView(
                message: state.message,
                onRetry: () {
                  context.read<InsightGraphBloc>().add(const LoadInsightGraph());
                },
              );
            }

            if (state is InsightGraphEmpty) {
              return _EmptyView(message: state.message);
            }

            if (state is InsightGraphLoaded) {
              return _LoadedView(state: state);
            }

            return const SizedBox.shrink();
          },
        ),
      ),
    );
  }
}

class _LoadedView extends StatelessWidget {
  final InsightGraphLoaded state;

  const _LoadedView({required this.state});

  @override
  Widget build(BuildContext context) {
    final data = state.data;

    return RefreshIndicator(
      onRefresh: () async {
        context.read<InsightGraphBloc>().add(const RefreshInsightGraph());
        context.read<InsightGraphBloc>().add(const LoadUpcomingTrips());
        // 等待刷新完成
        await Future.delayed(const Duration(milliseconds: 800));
      },
      color: AppColors.primary,
      child: CustomScrollView(
        slivers: [
          // 页面标题
          SliverToBoxAdapter(
            child: _buildHeader(context),
          ),

          // PRD 2.3.2: 行程切换器
          if (state.upcomingTrips.isNotEmpty)
            SliverToBoxAdapter(
              child: _buildTripSwitcher(context),
            ),

          // 核心事件卡片
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.only(top: 16, bottom: 20),
              child: CoreEventCard(
                event: data.coreEvent,
                onTap: () => _onCoreEventTap(context, data.coreEvent),
              ),
            ),
          ),

          // 关联事项区域
          if (data.associatedItems.isNotEmpty) ...[
            // 区域标题
            SliverToBoxAdapter(
              child: _buildSectionHeader(
                context,
                title: '关联事项',
                badge: CountBadge(
                  count: data.convenientCount,
                  suffix: '项可顺便',
                ),
              ),
            ),

            // 关联事项列表
            SliverPadding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              sliver: SliverList(
                delegate: SliverChildBuilderDelegate(
                  (context, index) {
                    final item = state.filteredItems[index];
                    return AssociatedItemCard(
                      item: item,
                      onTap: () => _onItemTap(context, item),
                      onDismiss: () => _onDismissItem(context, item),
                      onConfirm: () => _onConfirmItem(context, item),
                    );
                  },
                  childCount: state.filteredItems.length,
                ),
              ),
            ),
          ] else ...[
            // 无关联事项时的提示
            SliverToBoxAdapter(
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: AppColors.cardBackground,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: AppColors.divider,
                    width: 1,
                  ),
                ),
                child: const Column(
                  children: [
                    Icon(
                      Icons.link_off_outlined,
                      size: 32,
                      color: AppColors.textTertiary,
                    ),
                    SizedBox(height: 12),
                    Text(
                      '暂无关联事项',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w500,
                        color: AppColors.textSecondary,
                      ),
                    ),
                    SizedBox(height: 4),
                    Text(
                      'AI正在分析可能的关联，稍后再来看看',
                      style: TextStyle(
                        fontSize: 13,
                        color: AppColors.textTertiary,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],

          // 注意事项区域
          if (data.conflictAlerts.isNotEmpty) ...[
            SliverToBoxAdapter(
              child: _buildSectionHeader(
                context,
                title: '注意事项',
                badge: data.conflictCount > 0
                    ? CountBadge(
                        count: data.conflictCount,
                        suffix: '项冲突',
                        backgroundColor: AppColors.badgeOrange,
                        textColor: AppColors.warning,
                      )
                    : null,
              ),
            ),
            SliverPadding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              sliver: SliverList(
                delegate: SliverChildBuilderDelegate(
                  (context, index) {
                    final alert = data.conflictAlerts[index];
                    return ConflictAlertCard(
                      alert: alert,
                      onTap: () => _onAlertTap(context, alert),
                      onDismiss: () {
                        context.read<InsightGraphBloc>().add(DismissAlert(alert.id));
                      },
                      onAction: () => _onConflictAction(context, alert),
                    );
                  },
                  childCount: data.conflictAlerts.length,
                ),
              ),
            ),
          ],

          // 事件关联图谱 (人-事件-时间)
          if (state.tripGraph != null && state.tripGraph!.nodes.isNotEmpty)
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.only(top: 8),
                child: EventGraphView(
                  graph: state.tripGraph!,
                  onNodeTap: (node) => _onGraphNodeTap(context, node),
                ),
              ),
            ),

          // 底部间距
          const SliverToBoxAdapter(
            child: SizedBox(height: 32),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          const Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '事件图谱',
                style: TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
              SizedBox(height: 4),
              Text(
                '智能关联',
                style: TextStyle(
                  fontSize: 14,
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
          // 筛选按钮
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: AppColors.cardBackground,
              borderRadius: BorderRadius.circular(12),
              boxShadow: AppColors.cardShadow,
            ),
            child: IconButton(
              onPressed: () => _showFilterDialog(context),
              icon: const Icon(
                Icons.tune,
                color: AppColors.textPrimary,
                size: 22,
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// PRD 2.3.2: 行程切换器 - 显示即将到来的行程，支持切换
  Widget _buildTripSwitcher(BuildContext context) {
    final trips = state.upcomingTrips;
    if (trips.isEmpty) return const SizedBox.shrink();

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 16, 16, 0),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(12),
        boxShadow: AppColors.cardShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.swap_horiz,
                size: 18,
                color: AppColors.textSecondary,
              ),
              const SizedBox(width: 8),
              const Text(
                '切换行程',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                  color: AppColors.textSecondary,
                ),
              ),
              const Spacer(),
              Text(
                '${trips.length} 个即将到来的行程',
                style: const TextStyle(
                  fontSize: 12,
                  color: AppColors.textTertiary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          SizedBox(
            height: 80,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: trips.length,
              separatorBuilder: (_, __) => const SizedBox(width: 12),
              itemBuilder: (context, index) {
                final trip = trips[index];
                final isSelected = trip.id == state.selectedTripId;
                return _buildTripCard(context, trip, isSelected);
              },
            ),
          ),
        ],
      ),
    );
  }

  /// PRD 2.3.2: 单个行程卡片
  Widget _buildTripCard(BuildContext context, TripSummary trip, bool isSelected) {
    final dateFormat = DateFormat('M.d');
    final dateRange = '${dateFormat.format(trip.startDate)}-${dateFormat.format(trip.endDate)}';

    // 优先级颜色
    Color priorityColor;
    switch (trip.priority) {
      case 'critical':
      case 'high':
        priorityColor = AppColors.error;
        break;
      case 'normal':
        priorityColor = AppColors.warning;
        break;
      default:
        priorityColor = AppColors.textTertiary;
    }

    return GestureDetector(
      onTap: () {
        context.read<InsightGraphBloc>().add(SwitchTrip(trip.id));
      },
      child: Container(
        width: 140,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: isSelected
              ? AppColors.primary.withAlpha((0.1 * 255).round())
              : AppColors.chipBackground,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: isSelected ? AppColors.primary : Colors.transparent,
            width: 2,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    color: priorityColor,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    trip.title,
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: isSelected ? AppColors.primary : AppColors.textPrimary,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  dateRange,
                  style: TextStyle(
                    fontSize: 12,
                    color: isSelected ? AppColors.primary : AppColors.textSecondary,
                  ),
                ),
                if (trip.isCurrent)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: AppColors.success.withAlpha((0.2 * 255).round()),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: const Text(
                      '进行中',
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w500,
                        color: AppColors.success,
                      ),
                    ),
                  )
                else if (isSelected)
                  const Icon(
                    Icons.check_circle,
                    size: 16,
                    color: AppColors.primary,
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSectionHeader(
    BuildContext context, {
    required String title,
    Widget? badge,
  }) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            title,
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
            ),
          ),
          if (badge != null) badge,
        ],
      ),
    );
  }

  void _onItemTap(BuildContext context, AssociatedItem item) {
    // Navigate based on item type or metadata
    final metadata = item.metadata ?? {};
    final referenceType = metadata['reference_type'] as String?;
    final referenceId = metadata['reference_id'] as String?;

    // Check for travel/trip related items
    if (referenceType == 'travel' || referenceType == 'trip') {
      if (referenceId != null) {
        context.push(Routes.tripDetail(referenceId)).then((result) {
          if (result == true && context.mounted) {
            _refreshAfterChange(context);
          }
        });
        return;
      }
    }

    // Check for event/task related items - show detail sheet
    if (referenceType == 'event' || item.itemType == ItemType.task) {
      AssociatedItemDetailSheet.show(context, item);
      return;
    }

    // Check for person/member related items
    if (item.itemType == ItemType.person || referenceType == 'member') {
      final memberId = item.relatedMemberId ?? referenceId;
      if (memberId != null) {
        context.push(Routes.memberDetail(memberId));
        return;
      }
    }

    // Check for place - navigate to exploration
    if (item.itemType == ItemType.place) {
      context.push(Routes.tripExploration);
      return;
    }

    // Default: show detail sheet
    AssociatedItemDetailSheet.show(context, item);
  }

  /// 忽略关联事项 — 弹出对话框让用户可选填纠正信息
  void _onDismissItem(BuildContext context, AssociatedItem item) {
    final correctionController = TextEditingController();
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (sheetContext) => Padding(
        padding: EdgeInsets.fromLTRB(
          20, 20, 20,
          MediaQuery.of(sheetContext).viewInsets.bottom + 20,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '忽略「${item.title}」',
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              '忽略后不会再出现。如果信息有误，可以填写纠正内容帮助 AI 记住。',
              style: TextStyle(
                fontSize: 14,
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: correctionController,
              decoration: InputDecoration(
                hintText: '可选：纠正信息，如"外婆不在澳门，她住在深圳"',
                hintStyle: const TextStyle(
                  fontSize: 14,
                  color: AppColors.textHint,
                ),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppColors.divider),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppColors.primary),
                ),
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 16, vertical: 12,
                ),
              ),
              maxLines: 2,
              textInputAction: TextInputAction.done,
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => Navigator.of(sheetContext).pop(),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                    child: const Text('取消'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ElevatedButton(
                    onPressed: () {
                      Navigator.of(sheetContext).pop();
                      final correction = correctionController.text.trim();
                      context.read<InsightGraphBloc>().add(
                        DismissItem(
                          item.id,
                          correction: correction.isNotEmpty ? correction : null,
                        ),
                      );
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.error,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                    child: const Text('确认忽略'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  /// 确认关联事项 — 弹出日期时间选择器
  Future<void> _onConfirmItem(BuildContext context, AssociatedItem item) async {
    // 先选日期
    final now = DateTime.now();
    final pickedDate = await showDatePicker(
      context: context,
      initialDate: now.add(const Duration(days: 1)),
      firstDate: now,
      lastDate: now.add(const Duration(days: 365)),
      helpText: '选择「${item.title}」的日期',
    );
    if (pickedDate == null || !context.mounted) return;

    // 再选时间
    final pickedTime = await showTimePicker(
      context: context,
      initialTime: const TimeOfDay(hour: 10, minute: 0),
      helpText: '选择时间',
    );
    if (!context.mounted) return;

    final scheduledStart = DateTime(
      pickedDate.year,
      pickedDate.month,
      pickedDate.day,
      pickedTime?.hour ?? 10,
      pickedTime?.minute ?? 0,
    );

    context.read<InsightGraphBloc>().add(
      ConfirmItem(item.id, scheduledStart: scheduledStart),
    );

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.check_circle, color: Colors.white, size: 18),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                '「${item.title}」已加入日程 ${DateFormat('M月d日 HH:mm').format(scheduledStart)}',
              ),
            ),
          ],
        ),
        backgroundColor: AppColors.success,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        duration: const Duration(seconds: 3),
        margin: const EdgeInsets.all(16),
      ),
    );
  }

  void _onAlertTap(BuildContext context, ConflictAlert alert) {
    final eventId = alert.conflictingEventIds.isNotEmpty
        ? alert.conflictingEventIds.first
        : null;
    if (eventId != null) {
      context.push('${Routes.kanban}?event_id=$eventId');
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(alert.description ?? '查看提醒详情'),
          duration: const Duration(seconds: 2),
        ),
      );
    }
  }

  void _onConflictAction(BuildContext context, ConflictAlert alert) {
    if (alert.autoResolved) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(alert.resolutionNote ?? '秘书已自动调整'),
          duration: const Duration(seconds: 3),
        ),
      );
      return;
    }

    if (alert.pendingActionId == null) return;

    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (sheetContext) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                alert.title,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 8),
              if (alert.description != null)
                Text(
                  alert.description!,
                  style: const TextStyle(
                    fontSize: 14,
                    color: AppColors.textSecondary,
                  ),
                ),
              if (alert.suggestedAction != null) ...[
                const SizedBox(height: 8),
                Text(
                  alert.suggestedAction!,
                  style: const TextStyle(
                    fontSize: 14,
                    color: AppColors.primary,
                  ),
                ),
              ],
              const SizedBox(height: 20),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () {
                        Navigator.of(sheetContext).pop();
                        context.read<InsightGraphBloc>().add(
                          ResolveConflict(
                            alertId: alert.id,
                            pendingActionId: alert.pendingActionId!,
                            action: ConflictResolutionAction.reject,
                          ),
                        );
                      },
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                      child: const Text('忽略'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () {
                        Navigator.of(sheetContext).pop();
                        context.read<InsightGraphBloc>().add(
                          ResolveConflict(
                            alertId: alert.id,
                            pendingActionId: alert.pendingActionId!,
                            action: ConflictResolutionAction.confirm,
                          ),
                        );
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.primary,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                      child: const Text('确认调整'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              SizedBox(
                width: double.infinity,
                child: TextButton.icon(
                  onPressed: () {
                    Navigator.of(sheetContext).pop();
                    _showCustomDatePicker(context, alert);
                  },
                  icon: const Icon(Icons.edit_calendar, size: 18),
                  label: const Text('自定义时间'),
                  style: TextButton.styleFrom(
                    foregroundColor: AppColors.textSecondary,
                    padding: const EdgeInsets.symmetric(vertical: 12),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _showCustomDatePicker(
    BuildContext context,
    ConflictAlert alert,
  ) async {
    final now = DateTime.now();
    final pickedDate = await showDatePicker(
      context: context,
      initialDate: now.add(const Duration(days: 1)),
      firstDate: now,
      lastDate: now.add(const Duration(days: 365)),
      helpText: '选择新的开始日期',
    );
    if (pickedDate == null || !context.mounted) return;

    final pickedTime = await showTimePicker(
      context: context,
      initialTime: const TimeOfDay(hour: 9, minute: 0),
      helpText: '选择开始时间',
    );
    if (!context.mounted) return;

    final newStart = DateTime(
      pickedDate.year,
      pickedDate.month,
      pickedDate.day,
      pickedTime?.hour ?? 9,
      pickedTime?.minute ?? 0,
    );

    context.read<InsightGraphBloc>().add(
      ResolveConflict(
        alertId: alert.id,
        pendingActionId: alert.pendingActionId!,
        action: ConflictResolutionAction.confirm,
        newStart: newStart,
      ),
    );
  }

  /// Refresh insight graph and trip list after a change (e.g. trip deleted).
  void _refreshAfterChange(BuildContext context) {
    context.read<InsightGraphBloc>().add(const RefreshInsightGraph());
    context.read<InsightGraphBloc>().add(const LoadUpcomingTrips());
  }

  void _onCoreEventTap(BuildContext context, CoreEvent event) {
    switch (event.eventType) {
      case EventType.travel:
      case EventType.businessTrip:
        final tripId = event.metadata?['trip_id'] as String?;
        if (tripId != null && tripId.isNotEmpty) {
          context.push(Routes.tripDetail(tripId)).then((result) {
            if (result == true && context.mounted) {
              _refreshAfterChange(context);
            }
          });
        } else {
          // Fallback to timeline when this travel event isn't backed by a TravelPlan
          context.push('${Routes.kanban}?event_id=${event.id}');
        }
        break;
      case EventType.birthday:
      case EventType.anniversary:
      case EventType.holiday:
        context.push(Routes.dateDetail(event.id));
        break;
      case EventType.meeting:
      case EventType.appointment:
      case EventType.other:
        // Navigate to timeline with event context
        context.push('${Routes.kanban}?event_id=${event.id}');
        break;
    }
  }

  void _onGraphNodeTap(BuildContext context, GraphNode node) {
    final data = node.data;
    switch (node.type) {
      case 'person':
        final memberId = data?['member_id'] as String?;
        if (memberId != null) {
          context.push(Routes.memberDetail(memberId));
          return;
        }
      case 'event':
        final eventId = data?['event_id'] as String? ?? node.id;
        context.push('${Routes.kanban}?event_id=$eventId');
        return;
      case 'place':
        context.push(Routes.tripExploration);
        return;
      case 'task':
        final taskId = data?['task_id'] as String?;
        if (taskId != null) {
          context.push('${Routes.kanban}?event_id=$taskId');
          return;
        }
      default:
        break;
    }
    // Fallback: show a snackbar with node info
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(node.label),
        duration: const Duration(seconds: 2),
      ),
    );
  }

  void _showFilterDialog(BuildContext context) {
    final bloc = context.read<InsightGraphBloc>();
    final categories = [
      ('person', '人物', Icons.person),
      ('task', '待办', Icons.check_circle_outline),
      ('memory', '人情', Icons.card_giftcard),
      ('place', '地点', Icons.location_on),
      ('date', '历史', Icons.history),
      ('gift', '人情往来', Icons.redeem),
    ];

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('筛选关联类型'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: categories.map((cat) {
            return ListTile(
              leading: Icon(cat.$3, color: AppColors.primary),
              title: Text(cat.$2),
              onTap: () {
                Navigator.of(ctx).pop();
                bloc.add(FilterByCategory(category: cat.$1));
              },
            );
          }).toList(),
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.of(ctx).pop();
              bloc.add(const ClearFilter());
            },
            child: const Text('清除筛选'),
          ),
        ],
      ),
    );
  }
}

class _LoadingView extends StatelessWidget {
  const _LoadingView();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CircularProgressIndicator(
            color: AppColors.primary,
          ),
          SizedBox(height: 16),
          Text(
            '正在加载...',
            style: TextStyle(
              fontSize: 14,
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
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
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.error_outline,
              size: 64,
              color: AppColors.error,
            ),
            const SizedBox(height: 16),
            Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 16,
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('重试'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(
                  horizontal: 24,
                  vertical: 12,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _EmptyView extends StatelessWidget {
  final String message;

  const _EmptyView({required this.message});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.hub_outlined,
              size: 80,
              color: AppColors.textHint.withValues(alpha: 0.5),
            ),
            const SizedBox(height: 16),
            Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 16,
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              '当有即将到来的事件时，会显示相关的智能关联',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 14,
                color: AppColors.textTertiary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
