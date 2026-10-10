import '../../domain/entities/core_event.dart';

/// CoreEvent 数据模型 - 用于 API 通信
class CoreEventModel extends CoreEvent {
  const CoreEventModel({
    required super.id,
    required super.title,
    super.subtitle,
    super.location,
    required super.startDate,
    super.endDate,
    required super.eventType,
    super.metadata,
  });

  /// 从 JSON 创建模型
  factory CoreEventModel.fromJson(Map<String, dynamic> json) {
    return CoreEventModel(
      id: json['id'] as String,
      title: json['title'] as String,
      subtitle: json['subtitle'] as String?,
      location: json['location'] as String?,
      startDate: DateTime.parse(json['start_date'] as String),
      endDate: json['end_date'] != null
          ? DateTime.parse(json['end_date'] as String)
          : null,
      eventType: _parseEventType(json['event_type'] as String?),
      metadata: json['metadata'] as Map<String, dynamic>?,
    );
  }

  /// 转换为 JSON
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'subtitle': subtitle,
      'location': location,
      'start_date': startDate.toIso8601String(),
      'end_date': endDate?.toIso8601String(),
      'event_type': _eventTypeToString(eventType),
      'metadata': metadata,
    };
  }

  /// 从实体创建模型
  factory CoreEventModel.fromEntity(CoreEvent entity) {
    return CoreEventModel(
      id: entity.id,
      title: entity.title,
      subtitle: entity.subtitle,
      location: entity.location,
      startDate: entity.startDate,
      endDate: entity.endDate,
      eventType: entity.eventType,
      metadata: entity.metadata,
    );
  }

  static EventType _parseEventType(String? type) {
    switch (type) {
      case 'business_trip':
        return EventType.businessTrip;
      case 'travel':
        return EventType.travel;
      case 'meeting':
        return EventType.meeting;
      case 'appointment':
        return EventType.appointment;
      case 'holiday':
        return EventType.holiday;
      case 'birthday':
        return EventType.birthday;
      case 'anniversary':
        return EventType.anniversary;
      default:
        return EventType.other;
    }
  }

  static String _eventTypeToString(EventType type) {
    switch (type) {
      case EventType.businessTrip:
        return 'business_trip';
      case EventType.travel:
        return 'travel';
      case EventType.meeting:
        return 'meeting';
      case EventType.appointment:
        return 'appointment';
      case EventType.holiday:
        return 'holiday';
      case EventType.birthday:
        return 'birthday';
      case EventType.anniversary:
        return 'anniversary';
      case EventType.other:
        return 'other';
    }
  }
}
