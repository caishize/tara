import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../domain/entities/memory_lane.dart';
import '../bloc/memory_lane_bloc.dart';
import '../bloc/memory_lane_event.dart' as memory_events;
import '../bloc/memory_lane_state.dart';
import '../widgets/ai_memory_highlights.dart';
import '../widgets/memory_lane_skeleton.dart';
import '../widgets/on_this_day_card.dart';
import '../widgets/story_card.dart';
import '../widgets/yearly_summary_row.dart';

/// Memory lane tab content (segment 1 of the curated timeline).
///
/// Expects a [MemoryLaneBloc] to be available via [BlocProvider] from the
/// parent widget tree.
class MemoryLanePage extends StatelessWidget {
  const MemoryLanePage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<MemoryLaneBloc, MemoryLaneState>(
      builder: (context, state) {
        if (state is MemoryLaneLoading) {
          // PLAN-006: Shimmer skeleton instead of plain spinner
          return const MemoryLaneSkeleton();
        }
        if (state is MemoryLaneError) {
          return _buildErrorState(context, state.message);
        }
        if (state is MemoryLaneLoaded) {
          return _buildMemoryLane(context, state);
        }
        return const MemoryLaneSkeleton();
      },
    );
  }

  Widget _buildMemoryLane(BuildContext context, MemoryLaneLoaded state) {
    final memoryLaneBloc = context.read<MemoryLaneBloc>();

    return RefreshIndicator(
      onRefresh: () async {
        memoryLaneBloc.add(const memory_events.LoadMemoryLane());
        memoryLaneBloc.add(const memory_events.LoadOnThisDay());
        memoryLaneBloc.add(const memory_events.LoadMemoryHighlights());
      },
      child: CustomScrollView(
        slivers: [
          // ✨ AI 回忆精华 (PLAN-011)
          if (state.memoryHighlights.isNotEmpty)
            SliverToBoxAdapter(
              child: AiMemoryHighlights(highlights: state.memoryHighlights),
            ),

          // 🌅 那年今日
          if (state.visibleOnThisDayItems.isNotEmpty)
            SliverToBoxAdapter(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Padding(
                    padding: EdgeInsets.fromLTRB(16, 16, 16, 10),
                    child: Text(
                      '\uD83C\uDF05 \u90A3\u5E74\u4ECA\u65E5',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: AppColors.textPrimary,
                      ),
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: OnThisDayCard(
                      items: state.visibleOnThisDayItems,
                      onDismiss: (id) => memoryLaneBloc.add(
                        memory_events.DismissOnThisDay(id),
                      ),
                      onViewDetail: (item) => _navigateOnThisDay(context, item),
                    ),
                  ),
                ],
              ),
            ),

          // 📖 最近的故事
          if (state.recentStories.isNotEmpty)
            SliverToBoxAdapter(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Padding(
                    padding: EdgeInsets.fromLTRB(16, 16, 16, 10),
                    child: Text(
                      '\uD83D\uDCD6 \u6700\u8FD1\u7684\u6545\u4E8B',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: AppColors.textPrimary,
                      ),
                    ),
                  ),
                  ...state.recentStories
                      .map((story) => StoryCard(
                            story: story,
                            onTap: () => _navigateToStory(context, story),
                          )),
                ],
              ),
            ),

          // 📆 更早
          if (state.yearlySummaries.isNotEmpty)
            SliverToBoxAdapter(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Padding(
                    padding: EdgeInsets.fromLTRB(16, 16, 16, 10),
                    child: Text(
                      '\uD83D\uDCC6 \u66F4\u65E9',
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: AppColors.textPrimary,
                      ),
                    ),
                  ),
                  ...state.yearlySummaries.map((year) => YearlySummaryRow(
                        summary: year,
                        isExpanded:
                            state.expandedYears.contains(year.year),
                        onToggle: () => memoryLaneBloc
                            .add(memory_events.LoadYearDetail(year.year)),
                        onStoryTap: (story) =>
                            _navigateToStory(context, story),
                      )),
                ],
              ),
            ),

          // Empty state
          if (state.recentStories.isEmpty &&
              state.yearlySummaries.isEmpty &&
              state.visibleOnThisDayItems.isEmpty &&
              state.memoryHighlights.isEmpty)
            SliverFillRemaining(
              child: _buildEmptyState(context),
            ),

          const SliverPadding(padding: EdgeInsets.only(bottom: 80)),
        ],
      ),
    );
  }

  void _navigateToStory(BuildContext context, StoryGroup story) {
    if (story.isTrip) {
      context.push(Routes.tripMemory, extra: story);
      return;
    }
    final firstEvent = story.events.isNotEmpty ? story.events.first : null;
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(story.title),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (firstEvent?.startTime != null)
              Text(
                DateFormat('yyyy\u5E74M\u6708d\u65E5').format(firstEvent!.startTime!.toLocal()),
                style: const TextStyle(color: AppColors.textSecondary),
              ),
            if (firstEvent?.location != null) ...[
              const SizedBox(height: 4),
              Text(firstEvent!.location!, style: const TextStyle(color: AppColors.textSecondary)),
            ],
            if (firstEvent?.notes != null) ...[
              const SizedBox(height: 8),
              Text(firstEvent!.notes!),
            ],
            if (story.memorySummaries.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                story.memorySummaries.first,
                style: const TextStyle(fontSize: 13, fontStyle: FontStyle.italic, color: AppColors.textSecondary),
              ),
            ],
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('\u5173\u95ED')),
        ],
      ),
    );
  }

  void _navigateOnThisDay(BuildContext context, OnThisDayItem item) {
    if (item.eventType == 'travel' || item.eventType == 'business_trip') {
      final event = StoryEvent(
        id: item.id, title: item.title, eventType: item.eventType,
        startTime: item.startTime, location: item.location,
        notes: item.notes, tripId: item.tripId, tripName: item.tripName,
      );
      final story = StoryGroup(
        tripId: item.tripId, title: item.tripName ?? item.title,
        events: [event], memorySummaries: item.memorySummaries,
        startDate: item.startTime, participantCount: item.participantCount,
      );
      context.push(Routes.tripMemory, extra: story);
      return;
    }
    context.push(Routes.eventDetail(item.id));
  }

  Widget _buildEmptyState(BuildContext context) {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.event_note_outlined, size: 64, color: AppColors.textTertiary),
          SizedBox(height: 16),
          Text(
            '\u6682\u65E0\u56DE\u5FC6',
            style: TextStyle(fontSize: 16, color: AppColors.textSecondary),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorState(BuildContext context, String message) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, size: 64, color: AppColors.textTertiary),
          const SizedBox(height: 16),
          Text(
            message,
            style: const TextStyle(fontSize: 16, color: AppColors.textSecondary),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: () => context.read<MemoryLaneBloc>().add(
                  const memory_events.LoadMemoryLane(),
                ),
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.accentGreen),
            child: const Text('\u91CD\u8BD5'),
          ),
        ],
      ),
    );
  }
}
