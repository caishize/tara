import 'package:equatable/equatable.dart';

/// 事件类型枚举
enum EventType {
  businessTrip,    // 出差
  travel,          // 旅行
  meeting,         // 会议
  appointment,     // 预约
  holiday,         // 节假日
  birthday,        // 生日
  anniversary,     // 纪念日
  other,           // 其他
}

/// 核心事件实体 - 动态图谱的触发中心
class CoreEvent extends Equatable {
  final String id;
  final String title;
  final String? subtitle;
  final String? location;
  final DateTime startDate;
  final DateTime? endDate;
  final EventType eventType;
  final Map<String, dynamic>? metadata;

  const CoreEvent({
    required this.id,
    required this.title,
    this.subtitle,
    this.location,
    required this.startDate,
    this.endDate,
    required this.eventType,
    this.metadata,
  });

  /// 获取事件类型的中文显示名称
  String get eventTypeDisplayName {
    switch (eventType) {
      case EventType.businessTrip:
        return '出差';
      case EventType.travel:
        return '旅行';
      case EventType.meeting:
        return '会议';
      case EventType.appointment:
        return '预约';
      case EventType.holiday:
        return '节假日';
      case EventType.birthday:
        return '生日';
      case EventType.anniversary:
        return '纪念日';
      case EventType.other:
        return '其他';
    }
  }

  /// 是否是多日事件
  bool get isMultiDay {
    if (endDate == null) return false;
    return !_isSameDay(startDate, endDate!);
  }

  bool _isSameDay(DateTime a, DateTime b) {
    return a.year == b.year && a.month == b.month && a.day == b.day;
  }

  /// 创建副本
  CoreEvent copyWith({
    String? id,
    String? title,
    String? subtitle,
    String? location,
    DateTime? startDate,
    DateTime? endDate,
    EventType? eventType,
    Map<String, dynamic>? metadata,
  }) {
    return CoreEvent(
      id: id ?? this.id,
      title: title ?? this.title,
      subtitle: subtitle ?? this.subtitle,
      location: location ?? this.location,
      startDate: startDate ?? this.startDate,
      endDate: endDate ?? this.endDate,
      eventType: eventType ?? this.eventType,
      metadata: metadata ?? this.metadata,
    );
  }

  @override
  List<Object?> get props => [
        id,
        title,
        subtitle,
        location,
        startDate,
        endDate,
        eventType,
        metadata,
      ];
}
