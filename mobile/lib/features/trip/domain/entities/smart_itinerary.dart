import 'package:equatable/equatable.dart';

/// 行程风格
enum ItineraryStyle {
  intensive,  // 紧凑型
  relaxed,    // 轻松型
  budget,     // 经济型
  luxury,     // 豪华型
  adventure,  // 探险型
  cultural,   // 文化型
}

/// 行程风格扩展
extension ItineraryStyleExtension on ItineraryStyle {
  String get name {
    switch (this) {
      case ItineraryStyle.intensive:
        return '紧凑型';
      case ItineraryStyle.relaxed:
        return '轻松型';
      case ItineraryStyle.budget:
        return '经济型';
      case ItineraryStyle.luxury:
        return '豪华型';
      case ItineraryStyle.adventure:
        return '探险型';
      case ItineraryStyle.cultural:
        return '文化型';
    }
  }

  String get icon {
    switch (this) {
      case ItineraryStyle.intensive:
        return '🏃';
      case ItineraryStyle.relaxed:
        return '🧘';
      case ItineraryStyle.budget:
        return '💰';
      case ItineraryStyle.luxury:
        return '👑';
      case ItineraryStyle.adventure:
        return '🏔️';
      case ItineraryStyle.cultural:
        return '🏛️';
    }
  }

  String get description {
    switch (this) {
      case ItineraryStyle.intensive:
        return '景点密集，充分利用时间';
      case ItineraryStyle.relaxed:
        return '慢节奏，充足休息';
      case ItineraryStyle.budget:
        return '控制花费，高性价比';
      case ItineraryStyle.luxury:
        return '高端体验，五星服务';
      case ItineraryStyle.adventure:
        return '户外活动，自然风光';
      case ItineraryStyle.cultural:
        return '博物馆、历史遗迹';
    }
  }

  String get value {
    return toString().split('.').last;
  }

  static ItineraryStyle fromString(String value) {
    return ItineraryStyle.values.firstWhere(
      (e) => e.value == value,
      orElse: () => ItineraryStyle.relaxed,
    );
  }
}

/// 家庭成员
class FamilyMember extends Equatable {
  final String? name;
  final int age;
  final String? relation;

  const FamilyMember({
    this.name,
    required this.age,
    this.relation,
  });

  FamilyMember copyWith({
    String? name,
    int? age,
    String? relation,
  }) {
    return FamilyMember(
      name: name ?? this.name,
      age: age ?? this.age,
      relation: relation ?? this.relation,
    );
  }

  @override
  List<Object?> get props => [name, age, relation];
}

/// 家庭组成
class FamilyComposition extends Equatable {
  final List<FamilyMember> children;
  final List<FamilyMember> elderly;
  final List<String> specialNeeds;

  const FamilyComposition({
    this.children = const [],
    this.elderly = const [],
    this.specialNeeds = const [],
  });

  bool get hasChildren => children.isNotEmpty;
  bool get hasElderly => elderly.isNotEmpty;
  bool get hasSpecialNeeds => specialNeeds.isNotEmpty;
  bool get isEmpty => children.isEmpty && elderly.isEmpty && specialNeeds.isEmpty;

  FamilyComposition copyWith({
    List<FamilyMember>? children,
    List<FamilyMember>? elderly,
    List<String>? specialNeeds,
  }) {
    return FamilyComposition(
      children: children ?? this.children,
      elderly: elderly ?? this.elderly,
      specialNeeds: specialNeeds ?? this.specialNeeds,
    );
  }

  @override
  List<Object?> get props => [children, elderly, specialNeeds];
}

/// 行程偏好设置
class ItineraryPreferences extends Equatable {
  final bool enableNapTime;
  final String napTimeStart;
  final String napTimeEnd;
  final bool weatherAware;
  final bool includeLocalTips;
  final bool includeAlternatives;

  const ItineraryPreferences({
    this.enableNapTime = true,
    this.napTimeStart = '14:00',
    this.napTimeEnd = '16:00',
    this.weatherAware = true,
    this.includeLocalTips = true,
    this.includeAlternatives = true,
  });

  ItineraryPreferences copyWith({
    bool? enableNapTime,
    String? napTimeStart,
    String? napTimeEnd,
    bool? weatherAware,
    bool? includeLocalTips,
    bool? includeAlternatives,
  }) {
    return ItineraryPreferences(
      enableNapTime: enableNapTime ?? this.enableNapTime,
      napTimeStart: napTimeStart ?? this.napTimeStart,
      napTimeEnd: napTimeEnd ?? this.napTimeEnd,
      weatherAware: weatherAware ?? this.weatherAware,
      includeLocalTips: includeLocalTips ?? this.includeLocalTips,
      includeAlternatives: includeAlternatives ?? this.includeAlternatives,
    );
  }

  @override
  List<Object?> get props => [
    enableNapTime, napTimeStart, napTimeEnd,
    weatherAware, includeLocalTips, includeAlternatives,
  ];
}

/// 智能行程生成请求
class SmartItineraryRequest extends Equatable {
  final List<ItineraryStyle> styles;
  final FamilyComposition? familyComposition;
  final ItineraryPreferences? preferences;

  const SmartItineraryRequest({
    required this.styles,
    this.familyComposition,
    this.preferences,
  });

  @override
  List<Object?> get props => [styles, familyComposition, preferences];
}

/// 行程设计理念
class TripDesignRationale extends Equatable {
  final String planningPhilosophy;
  final String routeLogic;
  final List<String> highlights;
  final List<BackupPlan> backupPlans;
  final List<String> localTips;

  const TripDesignRationale({
    required this.planningPhilosophy,
    required this.routeLogic,
    this.highlights = const [],
    this.backupPlans = const [],
    this.localTips = const [],
  });

  @override
  List<Object?> get props => [
    planningPhilosophy, routeLogic, highlights, backupPlans, localTips,
  ];
}

/// 备选方案
class BackupPlan extends Equatable {
  final String scenario;
  final String alternative;

  const BackupPlan({
    required this.scenario,
    required this.alternative,
  });

  @override
  List<Object?> get props => [scenario, alternative];
}

/// 预算分配
class BudgetAllocation extends Equatable {
  final Map<String, BudgetCategory> categories;
  final double totalBudget;

  const BudgetAllocation({
    this.categories = const {},
    this.totalBudget = 0,
  });

  @override
  List<Object?> get props => [categories, totalBudget];
}

/// 预算分类
class BudgetCategory extends Equatable {
  final double amount;
  final double percentage;

  const BudgetCategory({
    required this.amount,
    required this.percentage,
  });

  @override
  List<Object?> get props => [amount, percentage];
}

/// 每日摘要
class DaySummary extends Equatable {
  final double totalCost;
  final double walkingDistanceKm;
  final int activityCount;
  final String energyLevel;
  final Map<String, double> costBreakdown;

  const DaySummary({
    this.totalCost = 0,
    this.walkingDistanceKm = 0,
    this.activityCount = 0,
    this.energyLevel = 'moderate',
    this.costBreakdown = const {},
  });

  @override
  List<Object?> get props => [
    totalCost, walkingDistanceKm, activityCount, energyLevel, costBreakdown,
  ];
}

/// 智能行程响应
class SmartItineraryResponse extends Equatable {
  final String tripId;
  final String destination;
  final int durationDays;
  final List<String> styles;
  final String generatedAt;
  final TripDesignRationale? tripDesignRationale;
  final BudgetAllocation? budgetAllocation;
  final List<SmartDailySchedule> dailySchedules;

  const SmartItineraryResponse({
    required this.tripId,
    required this.destination,
    required this.durationDays,
    this.styles = const [],
    required this.generatedAt,
    this.tripDesignRationale,
    this.budgetAllocation,
    this.dailySchedules = const [],
  });

  @override
  List<Object?> get props => [
    tripId, destination, durationDays, styles, generatedAt,
    tripDesignRationale, budgetAllocation, dailySchedules,
  ];
}

/// 智能每日行程
class SmartDailySchedule extends Equatable {
  final int day;
  final String dateLabel;
  final String theme;
  final String summary;
  final List<EnhancedActivity> activities;
  final DaySummary? daySummary;

  const SmartDailySchedule({
    required this.day,
    required this.dateLabel,
    this.theme = '',
    this.summary = '',
    this.activities = const [],
    this.daySummary,
  });

  @override
  List<Object?> get props => [
    day, dateLabel, theme, summary, activities, daySummary,
  ];
}

/// 增强活动（包含专业建议）
class EnhancedActivity extends Equatable {
  final String time;
  final int durationMinutes;
  final String activityType;
  final String title;
  final String location;
  final String description;
  final double estimatedCost;
  final ProfessionalAdvice? professionalAdvice;
  final List<Alternative> alternatives;
  final CostBreakdown? costBreakdown;

  const EnhancedActivity({
    required this.time,
    this.durationMinutes = 60,
    required this.activityType,
    required this.title,
    this.location = '',
    this.description = '',
    this.estimatedCost = 0,
    this.professionalAdvice,
    this.alternatives = const [],
    this.costBreakdown,
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

  String get activityTypeName {
    switch (activityType) {
      case 'transportation':
        return '交通';
      case 'accommodation':
        return '住宿';
      case 'attraction':
        return '景点';
      case 'meal':
      case 'restaurant':
      case 'dining':
        return '餐饮';
      case 'shopping':
        return '购物';
      case 'rest':
        return '休息';
      default:
        return '其他';
    }
  }

  @override
  List<Object?> get props => [
    time, durationMinutes, activityType, title, location, description,
    estimatedCost, professionalAdvice, alternatives, costBreakdown,
  ];
}

/// 专业建议
class ProfessionalAdvice extends Equatable {
  final String whyChosen;
  final String bestExperience;
  final String timeTips;
  final String costTips;
  final List<String> warnings;

  const ProfessionalAdvice({
    this.whyChosen = '',
    this.bestExperience = '',
    this.timeTips = '',
    this.costTips = '',
    this.warnings = const [],
  });

  bool get hasContent =>
      whyChosen.isNotEmpty ||
      bestExperience.isNotEmpty ||
      timeTips.isNotEmpty ||
      costTips.isNotEmpty ||
      warnings.isNotEmpty;

  @override
  List<Object?> get props => [
    whyChosen, bestExperience, timeTips, costTips, warnings,
  ];
}

/// 替代方案
class Alternative extends Equatable {
  final String name;
  final String reason;

  const Alternative({
    required this.name,
    required this.reason,
  });

  @override
  List<Object?> get props => [name, reason];
}

/// 费用明细
class CostBreakdown extends Equatable {
  final List<CostItem> items;

  const CostBreakdown({
    this.items = const [],
  });

  double get total => items.fold(0, (sum, item) => sum + item.amount);

  @override
  List<Object?> get props => [items];
}

/// 费用项目
class CostItem extends Equatable {
  final String category;
  final String description;
  final double amount;

  const CostItem({
    required this.category,
    required this.description,
    required this.amount,
  });

  @override
  List<Object?> get props => [category, description, amount];
}
