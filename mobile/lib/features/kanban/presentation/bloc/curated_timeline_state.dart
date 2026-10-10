import 'package:equatable/equatable.dart';
import '../../domain/entities/curated_event.dart';

/// 整理后时光轴状态 (timeline curation only)
abstract class CuratedTimelineState extends Equatable {
  const CuratedTimelineState();

  @override
  List<Object?> get props => [];
}

/// 初始状态
class CuratedTimelineInitial extends CuratedTimelineState {
  const CuratedTimelineInitial();
}

/// 加载中状态
class CuratedTimelineLoading extends CuratedTimelineState {
  const CuratedTimelineLoading();
}

/// 加载成功状态
class CuratedTimelineLoaded extends CuratedTimelineState {
  final CuratedTimeline timeline;
  final int selectedSegment; // 0: 未来, 1: 历史
  final DateTime selectedDate;
  final Set<String> expandedEventIds;
  final bool isRefreshing;
  final bool isCurating;
  final String? curationJobId;

  /// PRD 2.2.4: 懒加载支持
  final String? nextCursor;
  final bool hasMore;
  final bool isLoadingMore;

  const CuratedTimelineLoaded({
    required this.timeline,
    this.selectedSegment = 0,
    required this.selectedDate,
    this.expandedEventIds = const {},
    this.isRefreshing = false,
    this.isCurating = false,
    this.curationJobId,
    this.nextCursor,
    this.hasMore = true,
    this.isLoadingMore = false,
  });

  /// 按日期分组的事件
  Map<DateTime, List<CuratedEvent>> get eventsByDate => timeline.eventsByDate;

  /// 当前时间范围内的事件
  List<CuratedEvent> get filteredEvents {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);

    switch (selectedSegment) {
      case 0: // 未来 (今天及以后的所有事件)
        return timeline.events.where((e) {
          final localStart = e.startTime.toLocal();
          final localStartDate =
              DateTime(localStart.year, localStart.month, localStart.day);
          return localStartDate
                  .isAfter(today.subtract(const Duration(days: 1))) ||
              localStartDate.isAtSameMomentAs(today);
        }).toList();
      case 1: // 历史 (今天之前的事件)
        return timeline.events.where((e) {
          final localStart = e.startTime.toLocal();
          final localStartDate =
              DateTime(localStart.year, localStart.month, localStart.day);
          return localStartDate.isBefore(today);
        }).toList();
      default:
        return timeline.events;
    }
  }

  CuratedTimelineLoaded copyWith({
    CuratedTimeline? timeline,
    int? selectedSegment,
    DateTime? selectedDate,
    Set<String>? expandedEventIds,
    bool? isRefreshing,
    bool? isCurating,
    String? curationJobId,
    bool clearCurationJobId = false,
    String? nextCursor,
    bool? hasMore,
    bool? isLoadingMore,
    bool clearCursor = false,
  }) {
    return CuratedTimelineLoaded(
      timeline: timeline ?? this.timeline,
      selectedSegment: selectedSegment ?? this.selectedSegment,
      selectedDate: selectedDate ?? this.selectedDate,
      expandedEventIds: expandedEventIds ?? this.expandedEventIds,
      isRefreshing: isRefreshing ?? this.isRefreshing,
      isCurating: isCurating ?? this.isCurating,
      curationJobId:
          clearCurationJobId ? null : (curationJobId ?? this.curationJobId),
      nextCursor: clearCursor ? null : (nextCursor ?? this.nextCursor),
      hasMore: hasMore ?? this.hasMore,
      isLoadingMore: isLoadingMore ?? this.isLoadingMore,
    );
  }

  @override
  List<Object?> get props => [
        timeline,
        selectedSegment,
        selectedDate,
        expandedEventIds,
        isRefreshing,
        isCurating,
        curationJobId,
        nextCursor,
        hasMore,
        isLoadingMore,
      ];
}

/// 空状态
class CuratedTimelineEmpty extends CuratedTimelineState {
  final int selectedSegment;
  final DateTime selectedDate;

  const CuratedTimelineEmpty({
    this.selectedSegment = 0,
    required this.selectedDate,
  });

  @override
  List<Object?> get props => [selectedSegment, selectedDate];
}

/// 错误状态
class CuratedTimelineError extends CuratedTimelineState {
  final String message;
  final int selectedSegment;

  const CuratedTimelineError({
    required this.message,
    this.selectedSegment = 0,
  });

  @override
  List<Object?> get props => [message, selectedSegment];
}

/// 整理中状态
class CuratedTimelineCurating extends CuratedTimelineState {
  final String jobId;
  final String message;

  const CuratedTimelineCurating({
    required this.jobId,
    this.message = '正在整理您的日程...',
  });

  @override
  List<Object?> get props => [jobId, message];
}
