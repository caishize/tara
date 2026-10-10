import 'package:equatable/equatable.dart';
import 'smart_itinerary.dart';

/// 行程版本实体
class ItineraryVersion extends Equatable {
  final String id;
  final String tripId;
  final int versionNumber;
  final String? versionName;
  final List<String> styleTags;
  final bool isActive;
  final double? totalEstimatedCost;
  final List<VersionDaySchedule> schedules;
  final VersionGenerationConfig? generationConfig;
  final DateTime createdAt;
  final DateTime? updatedAt;

  const ItineraryVersion({
    required this.id,
    required this.tripId,
    required this.versionNumber,
    this.versionName,
    this.styleTags = const [],
    this.isActive = false,
    this.totalEstimatedCost,
    this.schedules = const [],
    this.generationConfig,
    required this.createdAt,
    this.updatedAt,
  });

  /// 版本显示名称
  String get displayName {
    if (versionName != null && versionName!.isNotEmpty) {
      return versionName!;
    }
    return '方案 $versionNumber';
  }

  /// 风格标签显示名称
  List<String> get styleDisplayNames {
    const styleMap = {
      'intensive': '紧凑型',
      'relaxed': '轻松型',
      'budget': '经济型',
      'luxury': '豪华型',
      'adventure': '探险型',
      'cultural': '文化型',
    };
    return styleTags.map((tag) => styleMap[tag] ?? tag).toList();
  }

  /// 总天数
  int get totalDays => schedules.length;

  /// 总活动数
  int get totalActivities {
    return schedules.fold(0, (sum, day) => sum + day.activities.length);
  }

  /// 计算总费用
  double get calculatedTotalCost {
    if (totalEstimatedCost != null) return totalEstimatedCost!;
    return schedules.fold(0.0, (sum, day) {
      return sum + day.activities.fold(0.0, (daySum, activity) {
        return daySum + (activity.estimatedCost ?? 0);
      });
    });
  }

  ItineraryVersion copyWith({
    String? id,
    String? tripId,
    int? versionNumber,
    String? versionName,
    List<String>? styleTags,
    bool? isActive,
    double? totalEstimatedCost,
    List<VersionDaySchedule>? schedules,
    VersionGenerationConfig? generationConfig,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return ItineraryVersion(
      id: id ?? this.id,
      tripId: tripId ?? this.tripId,
      versionNumber: versionNumber ?? this.versionNumber,
      versionName: versionName ?? this.versionName,
      styleTags: styleTags ?? this.styleTags,
      isActive: isActive ?? this.isActive,
      totalEstimatedCost: totalEstimatedCost ?? this.totalEstimatedCost,
      schedules: schedules ?? this.schedules,
      generationConfig: generationConfig ?? this.generationConfig,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  List<Object?> get props => [
    id,
    tripId,
    versionNumber,
    versionName,
    styleTags,
    isActive,
    totalEstimatedCost,
    schedules,
    generationConfig,
    createdAt,
    updatedAt,
  ];
}

/// 版本中的每日行程
class VersionDaySchedule extends Equatable {
  final int dayNumber;
  final List<VersionActivity> activities;
  final String? packingNotes;
  final String? theme;
  final String? summary;

  const VersionDaySchedule({
    required this.dayNumber,
    this.activities = const [],
    this.packingNotes,
    this.theme,
    this.summary,
  });

  double get totalCost {
    return activities.fold(0.0, (sum, a) => sum + (a.estimatedCost ?? 0));
  }

  @override
  List<Object?> get props => [dayNumber, activities, packingNotes, theme, summary];
}

/// 版本中的活动
class VersionActivity extends Equatable {
  final String? id;
  final String time;
  final String activityType;
  final String title;
  final String? location;
  final String? description;
  final double? estimatedCost;
  final String? professionalAdvice;
  final List<SelectableAlternative> alternatives;
  final bool hasMultipleChoices;

  const VersionActivity({
    this.id,
    required this.time,
    required this.activityType,
    required this.title,
    this.location,
    this.description,
    this.estimatedCost,
    this.professionalAdvice,
    this.alternatives = const [],
    this.hasMultipleChoices = false,
  });

  String get activityTypeIcon {
    switch (activityType) {
      case 'transportation':
        return '🚗';
      case 'accommodation':
        return '🏨';
      case 'attraction':
        return '🎡';
      case 'meal':
      case 'restaurant':
      case 'dining':
        return '🍽️';
      case 'shopping':
        return '🛍️';
      case 'rest':
        return '😴';
      default:
        return '📍';
    }
  }

  @override
  List<Object?> get props => [
    id,
    time,
    activityType,
    title,
    location,
    description,
    estimatedCost,
    professionalAdvice,
    alternatives,
    hasMultipleChoices,
  ];
}

/// 可选替代方案
class SelectableAlternative extends Equatable {
  final String id;
  final String title;
  final String? location;
  final String? description;
  final String reason;
  final double? estimatedCost;
  final String? activityType;
  final bool isSimilar;
  final double? similarityScore;

  const SelectableAlternative({
    required this.id,
    required this.title,
    this.location,
    this.description,
    required this.reason,
    this.estimatedCost,
    this.activityType,
    this.isSimilar = true,
    this.similarityScore,
  });

  @override
  List<Object?> get props => [
    id, title, location, description, reason,
    estimatedCost, activityType, isSimilar, similarityScore,
  ];
}

/// 版本生成配置
class VersionGenerationConfig extends Equatable {
  final List<String> styles;
  final FamilyComposition? familyComposition;
  final ItineraryPreferences? preferences;

  const VersionGenerationConfig({
    this.styles = const [],
    this.familyComposition,
    this.preferences,
  });

  @override
  List<Object?> get props => [styles, familyComposition, preferences];
}

/// 版本摘要信息（用于列表展示）
class ItineraryVersionSummary extends Equatable {
  final String id;
  final int versionNumber;
  final String? versionName;
  final List<String> styleTags;
  final bool isActive;
  final double? totalEstimatedCost;
  final int totalDays;
  final int totalActivities;
  final DateTime createdAt;

  const ItineraryVersionSummary({
    required this.id,
    required this.versionNumber,
    this.versionName,
    this.styleTags = const [],
    this.isActive = false,
    this.totalEstimatedCost,
    this.totalDays = 0,
    this.totalActivities = 0,
    required this.createdAt,
  });

  String get displayName {
    if (versionName != null && versionName!.isNotEmpty) {
      return versionName!;
    }
    return '方案 $versionNumber';
  }

  List<String> get styleDisplayNames {
    const styleMap = {
      'intensive': '紧凑型',
      'relaxed': '轻松型',
      'budget': '经济型',
      'luxury': '豪华型',
      'adventure': '探险型',
      'cultural': '文化型',
    };
    return styleTags.map((tag) => styleMap[tag] ?? tag).toList();
  }

  @override
  List<Object?> get props => [
    id,
    versionNumber,
    versionName,
    styleTags,
    isActive,
    totalEstimatedCost,
    totalDays,
    totalActivities,
    createdAt,
  ];
}
