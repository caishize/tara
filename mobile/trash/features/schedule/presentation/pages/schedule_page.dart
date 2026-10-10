import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/unified_event.dart';
import '../bloc/schedule_bloc.dart';
import '../bloc/schedule_event.dart';
import '../bloc/schedule_state.dart';
import '../widgets/schedule_section.dart';

class SchedulePage extends StatefulWidget {
  final String? initialTimePeriodFilter;

  const SchedulePage({super.key, this.initialTimePeriodFilter});

  @override
  State<SchedulePage> createState() => _SchedulePageState();
}

class _SchedulePageState extends State<SchedulePage> {
  @override
  void initState() {
    super.initState();
    // Parse initial time period filter if provided (e.g., from daily briefing)
    final initialFilter = widget.initialTimePeriodFilter != null
        ? _parseTimePeriod(widget.initialTimePeriodFilter!)
        : null;

    // Load schedule with initial filter applied
    context.read<ScheduleBloc>().add(
          ScheduleLoadRequested(initialTimePeriodFilter: initialFilter),
        );
  }

  /// Parse string to TimePeriod enum
  TimePeriod? _parseTimePeriod(String value) {
    switch (value.toLowerCase()) {
      case 'thisweek':
      case 'this_week':
        return TimePeriod.thisWeek;
      case 'today':
        return TimePeriod.today;
      case 'tomorrow':
        return TimePeriod.tomorrow;
      case 'nextweek':
      case 'next_week':
        return TimePeriod.nextWeek;
      default:
        return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            Expanded(child: _buildContent()),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Title row
          Row(
            children: [
              const Text(
                '📆',
                style: TextStyle(fontSize: 28),
              ),
              const SizedBox(width: 12),
              Text(
                '日程',
                style: AppTextStyles.headline3,
              ),
              const Spacer(),
              // Refresh button
              BlocBuilder<ScheduleBloc, ScheduleState>(
                builder: (context, state) {
                  return IconButton(
                    onPressed: state is ScheduleLoading
                        ? null
                        : () {
                            context.read<ScheduleBloc>().add(
                                  const ScheduleRefreshRequested(),
                                );
                          },
                    icon: state is ScheduleLoading
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.refresh),
                    color: AppColors.textSecondary,
                  );
                },
              ),
            ],
          ),
          const SizedBox(height: 12),
          // Stats bar
          BlocBuilder<ScheduleBloc, ScheduleState>(
            builder: (context, state) {
              if (state is ScheduleLoaded) {
                return ScheduleStatsBar(
                  todayCount: state.todayCount,
                  tomorrowCount: state.tomorrowCount,
                  weekCount: state.thisWeekCount,
                );
              }
              return const SizedBox.shrink();
            },
          ),
          const SizedBox(height: 12),
          // Time period filter banner (when filtered from briefing)
          _buildTimePeriodFilterBanner(),
          // Filter chips
          _buildFilterChips(),
          const SizedBox(height: 8),
        ],
      ),
    );
  }

  Widget _buildTimePeriodFilterBanner() {
    return BlocBuilder<ScheduleBloc, ScheduleState>(
      builder: (context, state) {
        if (state is! ScheduleLoaded || !state.hasTimePeriodFilter) {
          return const SizedBox.shrink();
        }

        return Container(
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: AppColors.info.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: AppColors.info.withValues(alpha: 0.3),
            ),
          ),
          child: Row(
            children: [
              const Icon(
                Icons.filter_alt_rounded,
                color: AppColors.info,
                size: 18,
              ),
              const SizedBox(width: 8),
              Text(
                '仅显示${state.timePeriodFilterName}事项',
                style: AppTextStyles.bodyText2.copyWith(
                  color: AppColors.info,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const Spacer(),
              GestureDetector(
                onTap: () {
                  context.read<ScheduleBloc>().add(
                        const ScheduleTimePeriodFilterChanged(null),
                      );
                },
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppColors.info.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(
                        Icons.close,
                        color: AppColors.info,
                        size: 14,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        '查看全部',
                        style: AppTextStyles.caption.copyWith(
                          color: AppColors.info,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildFilterChips() {
    return BlocBuilder<ScheduleBloc, ScheduleState>(
      builder: (context, state) {
        if (state is! ScheduleLoaded) {
          return const SizedBox.shrink();
        }

        final countBySource = state.countBySource;

        return SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              // All filter
              SourceFilterChip(
                source: null,
                isSelected: state.currentFilter == null,
                count: state.allEvents.length,
                onTap: () {
                  context.read<ScheduleBloc>().add(
                        const ScheduleFilterChanged(null),
                      );
                },
              ),
              const SizedBox(width: 8),
              // Important dates filter
              SourceFilterChip(
                source: EventSource.importantDate,
                isSelected: state.currentFilter == EventSource.importantDate,
                count: countBySource[EventSource.importantDate],
                onTap: () {
                  context.read<ScheduleBloc>().add(
                        ScheduleFilterChanged(
                          state.currentFilter == EventSource.importantDate
                              ? null
                              : EventSource.importantDate,
                        ),
                      );
                },
              ),
              const SizedBox(width: 8),
              // Travel filter
              SourceFilterChip(
                source: EventSource.travelPlan,
                isSelected: state.currentFilter == EventSource.travelPlan,
                count: countBySource[EventSource.travelPlan],
                onTap: () {
                  context.read<ScheduleBloc>().add(
                        ScheduleFilterChanged(
                          state.currentFilter == EventSource.travelPlan
                              ? null
                              : EventSource.travelPlan,
                        ),
                      );
                },
              ),
              const SizedBox(width: 8),
              // Extracted schedule filter (will show when Secretary is integrated)
              if (countBySource[EventSource.extractedSchedule] != null)
                SourceFilterChip(
                  source: EventSource.extractedSchedule,
                  isSelected: state.currentFilter == EventSource.extractedSchedule,
                  count: countBySource[EventSource.extractedSchedule],
                  onTap: () {
                    context.read<ScheduleBloc>().add(
                          ScheduleFilterChanged(
                            state.currentFilter == EventSource.extractedSchedule
                                ? null
                                : EventSource.extractedSchedule,
                          ),
                        );
                  },
                ),
              if (countBySource[EventSource.extractedPlan] != null)
                Padding(
                  padding: const EdgeInsets.only(left: 8),
                  child: SourceFilterChip(
                    source: EventSource.extractedPlan,
                    isSelected: state.currentFilter == EventSource.extractedPlan,
                    count: countBySource[EventSource.extractedPlan],
                    onTap: () {
                      context.read<ScheduleBloc>().add(
                            ScheduleFilterChanged(
                              state.currentFilter == EventSource.extractedPlan
                                  ? null
                                  : EventSource.extractedPlan,
                            ),
                          );
                    },
                  ),
                ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildContent() {
    return BlocBuilder<ScheduleBloc, ScheduleState>(
      builder: (context, state) {
        if (state is ScheduleInitial || state is ScheduleLoading) {
          return const Center(
            child: CircularProgressIndicator(),
          );
        }

        if (state is ScheduleError) {
          return _buildErrorState(state.message);
        }

        if (state is ScheduleLoaded) {
          if (!state.hasEvents) {
            return _buildEmptyState();
          }

          return RefreshIndicator(
            onRefresh: () async {
              final completer = Completer<void>();
              final bloc = context.read<ScheduleBloc>();
              late StreamSubscription<ScheduleState> subscription;

              subscription = bloc.stream.listen((newState) {
                if (newState is ScheduleLoaded || newState is ScheduleError) {
                  if (!completer.isCompleted) {
                    completer.complete();
                  }
                  subscription.cancel();
                }
              });

              bloc.add(const ScheduleRefreshRequested());

              // Timeout after 10 seconds
              return completer.future.timeout(
                const Duration(seconds: 10),
                onTimeout: () {
                  subscription.cancel();
                },
              );
            },
            child: _buildEventsList(state),
          );
        }

        return const SizedBox.shrink();
      },
    );
  }

  Widget _buildEventsList(ScheduleLoaded state) {
    final eventsByPeriod = state.filteredEventsByPeriod;

    if (eventsByPeriod.isEmpty) {
      return _buildNoFilteredEvents();
    }

    // Define the order of periods
    const periodOrder = [
      TimePeriod.overdue,
      TimePeriod.today,
      TimePeriod.tomorrow,
      TimePeriod.thisWeek,
      TimePeriod.nextWeek,
      TimePeriod.later,
    ];

    // Count non-empty sections
    int nonEmptyCount = 0;
    for (final period in periodOrder) {
      final events = eventsByPeriod[period];
      if (events != null && events.isNotEmpty) {
        nonEmptyCount++;
      }
    }

    // Add 1 for load more button if we have future events capability
    final itemCount = nonEmptyCount + 1;

    return ListView.builder(
      padding: const EdgeInsets.all(20),
      itemCount: itemCount,
      itemBuilder: (context, index) {
        // Last item is the load more button
        if (index == itemCount - 1) {
          return _buildLoadMoreButton(state);
        }

        // Find the nth non-empty period
        int currentNonEmpty = 0;
        for (final period in periodOrder) {
          final events = eventsByPeriod[period];
          if (events != null && events.isNotEmpty) {
            if (currentNonEmpty == index) {
              return ScheduleSection(
                period: period,
                events: events,
              );
            }
            currentNonEmpty++;
          }
        }

        return const SizedBox.shrink();
      },
    );
  }

  Widget _buildLoadMoreButton(ScheduleLoaded state) {
    // Only show load more if we have more events to load
    if (!state.hasMoreFutureEvents) {
      // Show "all loaded" indicator
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 16),
        child: Center(
          child: Text(
            '已加载全部日程',
            style: AppTextStyles.caption.copyWith(
              color: AppColors.textTertiary,
            ),
          ),
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 16),
      child: Center(
        child: state.isLoadingMoreFuture
            ? const SizedBox(
                width: 24,
                height: 24,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : OutlinedButton.icon(
                onPressed: () {
                  context.read<ScheduleBloc>().add(
                        const ScheduleLoadMoreFutureRequested(),
                      );
                },
                icon: const Icon(Icons.expand_more),
                label: const Text('加载更多'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppColors.primary,
                  side: BorderSide(color: AppColors.primary.withValues(alpha: 0.5)),
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                ),
              ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(40),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                color: AppColors.primary.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(20),
              ),
              child: const Center(
                child: Text(
                  '📅',
                  style: TextStyle(fontSize: 40),
                ),
              ),
            ),
            const SizedBox(height: 24),
            Text(
              '暂无日程',
              style: AppTextStyles.headline5,
            ),
            const SizedBox(height: 8),
            Text(
              '添加重要日期或旅行计划，\n它们会自动显示在这里',
              style: AppTextStyles.bodyText2.copyWith(
                color: AppColors.textSecondary,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildNoFilteredEvents() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(40),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.filter_list_off,
              size: 48,
              color: AppColors.textTertiary,
            ),
            const SizedBox(height: 16),
            Text(
              '没有符合筛选条件的日程',
              style: AppTextStyles.bodyText1.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: 16),
            TextButton(
              onPressed: () {
                context.read<ScheduleBloc>().add(
                      const ScheduleFilterChanged(null),
                    );
              },
              child: const Text('清除筛选'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorState(String message) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(40),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.error_outline,
              size: 48,
              color: AppColors.error,
            ),
            const SizedBox(height: 16),
            Text(
              '加载失败',
              style: AppTextStyles.headline5,
            ),
            const SizedBox(height: 8),
            Text(
              message,
              style: AppTextStyles.bodyText2.copyWith(
                color: AppColors.textSecondary,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: () {
                context.read<ScheduleBloc>().add(
                      const ScheduleRefreshRequested(),
                    );
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
              ),
              child: const Text('重试'),
            ),
          ],
        ),
      ),
    );
  }
}
