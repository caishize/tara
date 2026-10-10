import 'package:equatable/equatable.dart';

/// 整理后时光轴事件 (timeline curation only)
abstract class CuratedTimelineEvent extends Equatable {
  const CuratedTimelineEvent();

  @override
  List<Object?> get props => [];
}

/// 加载整理后的时光轴
class LoadCuratedTimeline extends CuratedTimelineEvent {
  final DateTime? startDate;
  final DateTime? endDate;

  const LoadCuratedTimeline({this.startDate, this.endDate});

  @override
  List<Object?> get props => [startDate, endDate];
}

/// 刷新整理后的时光轴
class RefreshCuratedTimeline extends CuratedTimelineEvent {
  const RefreshCuratedTimeline();
}

/// 请求AI整理
class RequestCuration extends CuratedTimelineEvent {
  final DateTime? startDate;
  final DateTime? endDate;

  const RequestCuration({this.startDate, this.endDate});

  @override
  List<Object?> get props => [startDate, endDate];
}

/// 切换时间范围
class ChangeTimeRange extends CuratedTimelineEvent {
  final int segmentIndex; // 0: 未来, 1: 本周, 2: 历史

  const ChangeTimeRange(this.segmentIndex);

  @override
  List<Object?> get props => [segmentIndex];
}

/// 选择特定日期
class SelectDate extends CuratedTimelineEvent {
  final DateTime date;

  const SelectDate(this.date);

  @override
  List<Object?> get props => [date];
}

/// 展开/收起事件详情
class ToggleEventExpanded extends CuratedTimelineEvent {
  final String eventId;

  const ToggleEventExpanded(this.eventId);

  @override
  List<Object?> get props => [eventId];
}

/// PRD 2.2.4: 懒加载更多时间线数据
class LoadMoreTimeline extends CuratedTimelineEvent {
  const LoadMoreTimeline();
}

/// 取消/删除事件
class CancelCuratedEvent extends CuratedTimelineEvent {
  final String eventId;
  final String eventTitle;

  const CancelCuratedEvent({required this.eventId, required this.eventTitle});

  @override
  List<Object?> get props => [eventId, eventTitle];
}

/// 创建用户事件
class CreateUserEvent extends CuratedTimelineEvent {
  final String title;
  final DateTime startTime;
  final DateTime? endTime;
  final String? eventType;
  final String? location;
  final String priority;
  final String? notes;
  final List<String> tags;

  const CreateUserEvent({
    required this.title,
    required this.startTime,
    this.endTime,
    this.eventType,
    this.location,
    this.priority = 'normal',
    this.notes,
    this.tags = const [],
  });

  @override
  List<Object?> get props =>
      [title, startTime, endTime, eventType, location, priority, notes, tags];
}
