import 'package:flutter_bloc/flutter_bloc.dart';
import '../../data/datasources/curated_timeline_datasource.dart' hide CuratedEventDto, TimelineItem;
import '../../domain/entities/curated_event.dart';
import '../../domain/repositories/curated_timeline_repository.dart';
import 'curated_timeline_event.dart';
import 'curated_timeline_state.dart';

/// 整理后时光轴 BLoC (timeline curation only)
class CuratedTimelineBloc
    extends Bloc<CuratedTimelineEvent, CuratedTimelineState> {
  final CuratedTimelineRepository _repository;

  CuratedTimelineBloc({required CuratedTimelineRepository repository})
      : _repository = repository,
        super(const CuratedTimelineInitial()) {
    on<LoadCuratedTimeline>(_onLoadCuratedTimeline);
    on<RefreshCuratedTimeline>(_onRefreshCuratedTimeline);
    on<RequestCuration>(_onRequestCuration);
    on<ChangeTimeRange>(_onChangeTimeRange);
    on<SelectDate>(_onSelectDate);
    on<ToggleEventExpanded>(_onToggleEventExpanded);
    on<LoadMoreTimeline>(_onLoadMoreTimeline);
    on<CancelCuratedEvent>(_onCancelCuratedEvent);
    on<CreateUserEvent>(_onCreateUserEvent);
  }

  Future<void> _onLoadCuratedTimeline(
    LoadCuratedTimeline event,
    Emitter<CuratedTimelineState> emit,
  ) async {
    emit(const CuratedTimelineLoading());

    final now = DateTime.now();
    final startDate =
        event.startDate ?? now.subtract(const Duration(days: 30));
    final endDate = event.endDate ?? now.add(const Duration(days: 60));

    final result = await _repository.getCuratedTimeline(
      startDate: startDate,
      endDate: endDate,
    );

    result.fold(
      (failure) => emit(CuratedTimelineError(message: failure.message)),
      (timeline) {
        if (timeline.events.isEmpty) {
          emit(CuratedTimelineEmpty(selectedDate: now));
        } else {
          emit(CuratedTimelineLoaded(
            timeline: timeline,
            selectedDate: now,
          ));
        }
      },
    );
  }

  Future<void> _onRefreshCuratedTimeline(
    RefreshCuratedTimeline event,
    Emitter<CuratedTimelineState> emit,
  ) async {
    final currentState = state;
    if (currentState is CuratedTimelineLoaded) {
      emit(currentState.copyWith(isRefreshing: true));

      final now = DateTime.now();
      final startDate = now.subtract(const Duration(days: 30));
      final endDate = now.add(const Duration(days: 60));

      final result = await _repository.getCuratedTimeline(
        startDate: startDate,
        endDate: endDate,
      );

      result.fold(
        (failure) => emit(currentState.copyWith(isRefreshing: false)),
        (timeline) {
          if (timeline.events.isEmpty) {
            emit(CuratedTimelineEmpty(
              selectedSegment: currentState.selectedSegment,
              selectedDate: currentState.selectedDate,
            ));
          } else {
            emit(currentState.copyWith(
              timeline: timeline,
              isRefreshing: false,
            ));
          }
        },
      );
    }
  }

  Future<void> _onRequestCuration(
    RequestCuration event,
    Emitter<CuratedTimelineState> emit,
  ) async {
    final currentState = state;

    if (currentState is CuratedTimelineLoaded) {
      emit(currentState.copyWith(isCurating: true));
    } else {
      emit(CuratedTimelineCurating(
        jobId: '',
        message: '正在整理您的日程...',
      ));
    }

    final now = DateTime.now();
    final startDate = event.startDate ?? now;
    final endDate = event.endDate ?? now.add(const Duration(days: 14));

    final result = await _repository.requestCuration(
      startDate: startDate,
      endDate: endDate,
    );

    result.fold(
      (failure) {
        if (currentState is CuratedTimelineLoaded) {
          emit(currentState.copyWith(isCurating: false));
        } else {
          emit(CuratedTimelineError(message: failure.message));
        }
      },
      (jobStatus) async {
        if (jobStatus.isCompleted) {
          add(const RefreshCuratedTimeline());
        } else if (currentState is CuratedTimelineLoaded) {
          emit(currentState.copyWith(
            isCurating: false,
            curationJobId: jobStatus.jobId,
          ));
          add(const RefreshCuratedTimeline());
        }
      },
    );
  }

  void _onChangeTimeRange(
    ChangeTimeRange event,
    Emitter<CuratedTimelineState> emit,
  ) {
    final currentState = state;
    if (currentState is CuratedTimelineLoaded) {
      emit(currentState.copyWith(selectedSegment: event.segmentIndex));
    } else if (currentState is CuratedTimelineEmpty) {
      emit(CuratedTimelineEmpty(
        selectedSegment: event.segmentIndex,
        selectedDate: currentState.selectedDate,
      ));
    } else if (currentState is CuratedTimelineError) {
      emit(CuratedTimelineError(
        message: currentState.message,
        selectedSegment: event.segmentIndex,
      ));
    }
  }

  void _onSelectDate(
    SelectDate event,
    Emitter<CuratedTimelineState> emit,
  ) {
    final currentState = state;
    if (currentState is CuratedTimelineLoaded) {
      emit(currentState.copyWith(selectedDate: event.date));
    }
  }

  void _onToggleEventExpanded(
    ToggleEventExpanded event,
    Emitter<CuratedTimelineState> emit,
  ) {
    final currentState = state;
    if (currentState is CuratedTimelineLoaded) {
      final newExpandedIds = Set<String>.from(currentState.expandedEventIds);
      if (newExpandedIds.contains(event.eventId)) {
        newExpandedIds.remove(event.eventId);
      } else {
        newExpandedIds.add(event.eventId);
      }
      emit(currentState.copyWith(expandedEventIds: newExpandedIds));
    }
  }

  /// PRD 2.2.4: 懒加载更多时间线数据
  Future<void> _onLoadMoreTimeline(
    LoadMoreTimeline event,
    Emitter<CuratedTimelineState> emit,
  ) async {
    final currentState = state;
    if (currentState is! CuratedTimelineLoaded) return;

    if (!currentState.hasMore || currentState.isLoadingMore) return;

    emit(currentState.copyWith(isLoadingMore: true));

    try {
      final direction = currentState.selectedSegment == 1
          ? TimelineDirection.past
          : TimelineDirection.future;

      final response = await _repository.getDirectionalTimeline(
        direction: direction,
        days: 7,
        cursor: currentState.nextCursor,
      );

      response.fold(
        (failure) {
          emit(currentState.copyWith(isLoadingMore: false));
        },
        (newData) {
          final newEvents = <CuratedEvent>[];
          for (final dayGroup in newData.dayGroups) {
            for (final item in dayGroup.events) {
              newEvents.add(CuratedEvent(
                id: item.id,
                title: item.title,
                startTime: item.startTime,
                endTime: item.endTime,
                eventType: CuratedEventType.fromString(item.eventType),
                location: item.location,
                tripId: item.tripId,
              ));
            }
          }

          final allEvents = [...currentState.timeline.events, ...newEvents];
          final updatedTimeline = CuratedTimeline(
            events: allEvents,
            lastCuratedAt: currentState.timeline.lastCuratedAt,
            hasUnconfirmed: currentState.timeline.hasUnconfirmed,
            unconfirmedCount: currentState.timeline.unconfirmedCount,
            unconfirmedItems: currentState.timeline.unconfirmedItems,
          );

          emit(currentState.copyWith(
            timeline: updatedTimeline,
            nextCursor: newData.nextCursor,
            hasMore: newData.hasMore,
            isLoadingMore: false,
          ));
        },
      );
    } catch (e) {
      emit(currentState.copyWith(isLoadingMore: false));
    }
  }

  /// 取消/删除事件
  Future<void> _onCancelCuratedEvent(
    CancelCuratedEvent event,
    Emitter<CuratedTimelineState> emit,
  ) async {
    final currentState = state;
    if (currentState is! CuratedTimelineLoaded) return;

    final result = await _repository.cancelEvent(
      eventId: event.eventId,
      eventTitle: event.eventTitle,
    );

    result.fold(
      (failure) {
        // Could emit an error state or show a snackbar
      },
      (success) {
        if (success) {
          final updatedEvents = currentState.timeline.events
              .where((e) => e.id != event.eventId)
              .toList();
          final updatedTimeline = CuratedTimeline(
            events: updatedEvents,
            lastCuratedAt: currentState.timeline.lastCuratedAt,
            hasUnconfirmed: currentState.timeline.hasUnconfirmed,
            unconfirmedCount: currentState.timeline.unconfirmedCount,
            unconfirmedItems: currentState.timeline.unconfirmedItems,
          );
          emit(currentState.copyWith(timeline: updatedTimeline));
          add(const RequestCuration());
        }
      },
    );
  }

  /// 创建用户事件，成功后刷新时光轴
  Future<void> _onCreateUserEvent(
    CreateUserEvent event,
    Emitter<CuratedTimelineState> emit,
  ) async {
    final result = await _repository.createEvent(
      title: event.title,
      startTime: event.startTime,
      endTime: event.endTime,
      eventType: event.eventType,
      location: event.location,
      priority: event.priority,
      notes: event.notes,
      tags: event.tags,
    );

    result.fold(
      (failure) {
        // Emit error or let UI handle via state
      },
      (_) {
        add(const RefreshCuratedTimeline());
      },
    );
  }
}
