import 'package:equatable/equatable.dart';

/// 活动类型
enum ActivityType {
  transportation,  // 交通
  accommodation,   // 住宿
  attraction,      // 景点
  dining,          // 餐饮
  shopping,        // 购物
  rest,            // 休息
  other,           // 其他
}

/// 单个活动
class ItineraryActivity extends Equatable {
  final String? time;

  /// Day-period label provided by the backend: "上午", "下午", or "晚上".
  final String? period;
  final ActivityType activityType;
  final String title;
  final String? location;
  final String? description;
  final double? estimatedCost;
  final String? bookingInfo;
  final String? notes;
  final String? professionalAdvice;
  final List<String>? alternatives;

  const ItineraryActivity({
    this.time,
    this.period,
    required this.activityType,
    required this.title,
    this.location,
    this.description,
    this.estimatedCost,
    this.bookingInfo,
    this.notes,
    this.professionalAdvice,
    this.alternatives,
  });

  /// 活动类型显示名称
  String get activityTypeName {
    switch (activityType) {
      case ActivityType.transportation:
        return '交通';
      case ActivityType.accommodation:
        return '住宿';
      case ActivityType.attraction:
        return '景点';
      case ActivityType.dining:
        return '餐饮';
      case ActivityType.shopping:
        return '购物';
      case ActivityType.rest:
        return '休息';
      case ActivityType.other:
        return '其他';
    }
  }

  /// 活动类型图标
  String get activityTypeIcon {
    switch (activityType) {
      case ActivityType.transportation:
        return '🚗';
      case ActivityType.accommodation:
        return '🏨';
      case ActivityType.attraction:
        return '🎡';
      case ActivityType.dining:
        return '🍽️';
      case ActivityType.shopping:
        return '🛍️';
      case ActivityType.rest:
        return '😴';
      case ActivityType.other:
        return '📍';
    }
  }

  ItineraryActivity copyWith({
    String? time,
    String? period,
    ActivityType? activityType,
    String? title,
    String? location,
    String? description,
    double? estimatedCost,
    String? bookingInfo,
    String? notes,
    String? professionalAdvice,
    List<String>? alternatives,
  }) {
    return ItineraryActivity(
      time: time ?? this.time,
      period: period ?? this.period,
      activityType: activityType ?? this.activityType,
      title: title ?? this.title,
      location: location ?? this.location,
      description: description ?? this.description,
      estimatedCost: estimatedCost ?? this.estimatedCost,
      bookingInfo: bookingInfo ?? this.bookingInfo,
      notes: notes ?? this.notes,
      professionalAdvice: professionalAdvice ?? this.professionalAdvice,
      alternatives: alternatives ?? this.alternatives,
    );
  }

  @override
  List<Object?> get props => [
    time, period, activityType, title, location, description,
    estimatedCost, bookingInfo, notes, professionalAdvice, alternatives,
  ];
}

/// 每日行程
class DayItinerary extends Equatable {
  final String id;
  final String tripId;
  final int dayNumber;
  final List<ItineraryActivity> activities;
  final String? packingNotes;
  final DateTime createdAt;
  final DateTime updatedAt;

  const DayItinerary({
    required this.id,
    required this.tripId,
    required this.dayNumber,
    this.activities = const [],
    this.packingNotes,
    required this.createdAt,
    required this.updatedAt,
  });

  /// 当日总预估费用
  double get totalEstimatedCost {
    return activities.fold(0, (sum, activity) => sum + (activity.estimatedCost ?? 0));
  }

  /// 活动数量
  int get activityCount => activities.length;

  DayItinerary copyWith({
    String? id,
    String? tripId,
    int? dayNumber,
    List<ItineraryActivity>? activities,
    String? packingNotes,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return DayItinerary(
      id: id ?? this.id,
      tripId: tripId ?? this.tripId,
      dayNumber: dayNumber ?? this.dayNumber,
      activities: activities ?? this.activities,
      packingNotes: packingNotes ?? this.packingNotes,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  List<Object?> get props => [
    id, tripId, dayNumber, activities, packingNotes, createdAt, updatedAt,
  ];
}
