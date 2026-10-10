import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/storage/auth_storage.dart';
import '../../data/models/kanban_models.dart';
import '../../domain/entities/curated_event.dart';
import '../../domain/repositories/insight_feed_repository.dart';
import '../bloc/curated_timeline_bloc.dart';
import '../bloc/curated_timeline_event.dart';
import '../bloc/future_view_bloc.dart';
import '../bloc/future_view_event.dart';
import '../bloc/future_view_state.dart';
import '../bloc/kanban_bloc.dart';
import '../bloc/memory_lane_bloc.dart';
import '../bloc/memory_lane_event.dart' as memory_events;
import '../widgets/event_search_sheet.dart';
import '../widgets/add_event_sheet.dart';
import 'future_view_page.dart';
import 'memory_lane_page.dart';

/// Curated Timeline page (AI-curated timeline).
/// Two tabs: "未来" (future view) and "回忆" (memory lane).
///
/// This is a thin shell that provides BLoCs and delegates each tab's
/// content to [FutureViewPage] and [MemoryLanePage].
class CuratedTimelinePage extends StatefulWidget {
  const CuratedTimelinePage({super.key});

  @override
  State<CuratedTimelinePage> createState() => _CuratedTimelinePageState();
}

class _CuratedTimelinePageState extends State<CuratedTimelinePage> {
  late CuratedTimelineBloc _timelineBloc;
  late KanbanBloc _kanbanBloc;
  late FutureViewBloc _futureViewBloc;
  late MemoryLaneBloc _memoryLaneBloc;
  int _selectedSegment = 0; // 0: 未来, 1: 回忆

  @override
  void initState() {
    super.initState();
    _timelineBloc = getIt<CuratedTimelineBloc>();
    _kanbanBloc = getIt<KanbanBloc>();
    _memoryLaneBloc = getIt<MemoryLaneBloc>();
    final feedRepo = getIt<InsightFeedRepository>();
    _futureViewBloc = FutureViewBloc(repository: feedRepo);
    _futureViewBloc.add(const LoadFutureView());
  }

  @override
  void dispose() {
    _timelineBloc.close();
    _kanbanBloc.close();
    _futureViewBloc.close();
    _memoryLaneBloc.close();
    super.dispose();
  }

  /// PLAN-008: Smart tab switch — only reload if data is stale or missing.
  static const _staleDuration = Duration(minutes: 5);

  void _onSegmentChanged(int index) {
    if (_selectedSegment == index) return;
    setState(() {
      _selectedSegment = index;
    });
    if (index == 0) {
      // PLAN-008: Skip reload when data is fresh
      final futureState = _futureViewBloc.state;
      final isFresh = futureState is FutureViewLoaded &&
          futureState.lastLoadedAt != null &&
          DateTime.now().difference(futureState.lastLoadedAt!) < _staleDuration;
      if (!isFresh) {
        _futureViewBloc.add(const LoadFutureView());
      }
    } else {
      _memoryLaneBloc.add(const memory_events.LoadMemoryLane());
      _memoryLaneBloc.add(const memory_events.LoadOnThisDay());
      _memoryLaneBloc.add(const memory_events.LoadMemoryHighlights());
    }
  }

  @override
  Widget build(BuildContext context) {
    return MultiBlocProvider(
      providers: [
        BlocProvider.value(value: _timelineBloc),
        BlocProvider.value(value: _kanbanBloc),
        BlocProvider.value(value: _futureViewBloc),
        BlocProvider.value(value: _memoryLaneBloc),
      ],
      child: Scaffold(
        backgroundColor: AppColors.background,
        floatingActionButton: _selectedSegment == 0
            ? FloatingActionButton(
                onPressed: _showAddEventSheet,
                backgroundColor: AppColors.accentGreen,
                child: const Icon(Icons.add, color: Colors.white),
              )
            : null,
        body: SafeArea(
          child: Column(
            children: [
              _buildHeader(),
              _buildSegmentedControl(),
              Expanded(
                child: _selectedSegment == 0
                    ? const FutureViewPage()
                    : const MemoryLanePage(),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Header -- green avatar + "时光轴" + search icon
  // ---------------------------------------------------------------------------

  String _getUsername() {
    try {
      final authStorage = getIt<AuthStorage>();
      final info = authStorage.getUserInfo();
      final name = info?['username'] as String?;
      if (name != null && name.isNotEmpty) return name;
    } catch (_) {}
    return '\u8001\u677F';
  }

  String _getAvatarInitial() {
    final name = _getUsername();
    if (name.isEmpty) return '';
    return name.substring(0, 1);
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
      child: SizedBox(
        height: 48,
        child: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: AppColors.accentGreen,
                borderRadius: BorderRadius.circular(18),
              ),
              alignment: Alignment.center,
              child: Text(
                _getAvatarInitial(),
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  color: Colors.white,
                ),
              ),
            ),
            const SizedBox(width: 12),
            const Text(
              '\u65F6\u5149\u8F74',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
              ),
            ),
            const Spacer(),
            GestureDetector(
              onTap: _showSearchSheet,
              child: const Icon(
                Icons.search,
                size: 22,
                color: AppColors.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Tabs -- "未来" / "回忆"
  // ---------------------------------------------------------------------------

  Widget _buildSegmentedControl() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: SizedBox(
        height: 40,
        child: Row(
          children: [
            _buildTabItem(0, '\u672A\u6765'),
            const SizedBox(width: 20),
            _buildTabItem(1, '\u56DE\u5FC6'),
            const Spacer(),
          ],
        ),
      ),
    );
  }

  Widget _buildTabItem(int index, String label) {
    final isSelected = _selectedSegment == index;
    final activeColor =
        index == 1 ? AppColors.accentWarm : AppColors.accentGreen;

    return GestureDetector(
      onTap: () => _onSegmentChanged(index),
      behavior: HitTestBehavior.opaque,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Text(
              label,
              style: TextStyle(
                fontSize: 15,
                fontWeight: isSelected ? FontWeight.w700 : FontWeight.w400,
                color: isSelected ? activeColor : AppColors.textTertiary,
              ),
            ),
          ),
          AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            height: 3,
            width: isSelected ? 32 : 0,
            decoration: BoxDecoration(
              color: isSelected ? activeColor : Colors.transparent,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Actions -- search & add event
  // ---------------------------------------------------------------------------

  void _showSearchSheet() {
    EventSearchSheet.show(
      context,
      kanbanBloc: _kanbanBloc,
      onEventTap: (event) => _navigateToEvent(event),
    );
  }

  void _navigateToEvent(KanbanEventModel event) {
    final eventType = event.eventType;
    if (eventType == CuratedEventType.businessTrip ||
        eventType == CuratedEventType.travel) {
      if (event.tripId != null) {
        context.push(Routes.tripDetail(event.tripId!));
        return;
      }
    }
    context.push(Routes.eventDetail(event.id), extra: event);
  }

  void _showAddEventSheet() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => DraggableScrollableSheet(
        initialChildSize: 0.85,
        maxChildSize: 0.95,
        minChildSize: 0.5,
        builder: (_, scrollController) => AddEventSheet(
          onSubmit: (title, startTime, endTime, eventType, location,
              priority, notes) async {
            _timelineBloc.add(CreateUserEvent(
              title: title,
              startTime: startTime,
              endTime: endTime,
              eventType: eventType,
              location: location,
              priority: priority,
              notes: notes,
            ));
          },
        ),
      ),
    );
  }
}
