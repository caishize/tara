import '../../domain/entities/smart_itinerary.dart';

class FamilyMemberModel extends FamilyMember {
  const FamilyMemberModel({
    super.name,
    required super.age,
    super.relation,
  });

  factory FamilyMemberModel.fromJson(Map<String, dynamic> json) {
    return FamilyMemberModel(
      name: json['name'],
      age: json['age'] ?? 0,
      relation: json['relation'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      if (name != null) 'name': name,
      'age': age,
      if (relation != null) 'relation': relation,
    };
  }

  static FamilyMemberModel fromEntity(FamilyMember entity) {
    return FamilyMemberModel(
      name: entity.name,
      age: entity.age,
      relation: entity.relation,
    );
  }
}

class FamilyCompositionModel extends FamilyComposition {
  const FamilyCompositionModel({
    super.children,
    super.elderly,
    super.specialNeeds,
  });

  factory FamilyCompositionModel.fromJson(Map<String, dynamic> json) {
    return FamilyCompositionModel(
      children: (json['children'] as List?)
          ?.map((c) => FamilyMemberModel.fromJson(c as Map<String, dynamic>))
          .toList() ?? [],
      elderly: (json['elderly'] as List?)
          ?.map((e) => FamilyMemberModel.fromJson(e as Map<String, dynamic>))
          .toList() ?? [],
      specialNeeds: (json['special_needs'] as List?)?.cast<String>() ?? [],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'children': children
          .map((c) => FamilyMemberModel.fromEntity(c).toJson())
          .toList(),
      'elderly': elderly
          .map((e) => FamilyMemberModel.fromEntity(e).toJson())
          .toList(),
      'special_needs': specialNeeds,
    };
  }

  static FamilyCompositionModel fromEntity(FamilyComposition entity) {
    return FamilyCompositionModel(
      children: entity.children,
      elderly: entity.elderly,
      specialNeeds: entity.specialNeeds,
    );
  }
}

class ItineraryPreferencesModel extends ItineraryPreferences {
  const ItineraryPreferencesModel({
    super.enableNapTime,
    super.napTimeStart,
    super.napTimeEnd,
    super.weatherAware,
    super.includeLocalTips,
    super.includeAlternatives,
  });

  factory ItineraryPreferencesModel.fromJson(Map<String, dynamic> json) {
    return ItineraryPreferencesModel(
      enableNapTime: json['enable_nap_time'] ?? true,
      napTimeStart: json['nap_time_start'] ?? '14:00',
      napTimeEnd: json['nap_time_end'] ?? '16:00',
      weatherAware: json['weather_aware'] ?? true,
      includeLocalTips: json['include_local_tips'] ?? true,
      includeAlternatives: json['include_alternatives'] ?? true,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'enable_nap_time': enableNapTime,
      'nap_time_start': napTimeStart,
      'nap_time_end': napTimeEnd,
      'weather_aware': weatherAware,
      'include_local_tips': includeLocalTips,
      'include_alternatives': includeAlternatives,
    };
  }

  static ItineraryPreferencesModel fromEntity(ItineraryPreferences entity) {
    return ItineraryPreferencesModel(
      enableNapTime: entity.enableNapTime,
      napTimeStart: entity.napTimeStart,
      napTimeEnd: entity.napTimeEnd,
      weatherAware: entity.weatherAware,
      includeLocalTips: entity.includeLocalTips,
      includeAlternatives: entity.includeAlternatives,
    );
  }
}

class SmartItineraryRequestModel extends SmartItineraryRequest {
  const SmartItineraryRequestModel({
    required super.styles,
    super.familyComposition,
    super.preferences,
  });

  Map<String, dynamic> toJson() {
    return {
      'styles': styles.map((s) => s.value).toList(),
      if (familyComposition != null)
        'family_composition': FamilyCompositionModel.fromEntity(familyComposition!).toJson(),
      if (preferences != null)
        'preferences': ItineraryPreferencesModel.fromEntity(preferences!).toJson(),
    };
  }

  static SmartItineraryRequestModel fromEntity(SmartItineraryRequest entity) {
    return SmartItineraryRequestModel(
      styles: entity.styles,
      familyComposition: entity.familyComposition,
      preferences: entity.preferences,
    );
  }
}

class ProfessionalAdviceModel extends ProfessionalAdvice {
  const ProfessionalAdviceModel({
    super.whyChosen,
    super.bestExperience,
    super.timeTips,
    super.costTips,
    super.warnings,
  });

  factory ProfessionalAdviceModel.fromJson(Map<String, dynamic> json) {
    return ProfessionalAdviceModel(
      whyChosen: json['why_chosen'] ?? '',
      bestExperience: json['best_experience'] ?? '',
      timeTips: json['time_tips'] ?? '',
      costTips: json['cost_tips'] ?? '',
      warnings: (json['warnings'] as List?)?.cast<String>() ?? [],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'why_chosen': whyChosen,
      'best_experience': bestExperience,
      'time_tips': timeTips,
      'cost_tips': costTips,
      'warnings': warnings,
    };
  }
}

class AlternativeModel extends Alternative {
  const AlternativeModel({
    required super.name,
    required super.reason,
  });

  factory AlternativeModel.fromJson(Map<String, dynamic> json) {
    return AlternativeModel(
      name: json['name'] ?? '',
      reason: json['reason'] ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'name': name,
      'reason': reason,
    };
  }
}

class CostItemModel extends CostItem {
  const CostItemModel({
    required super.category,
    required super.description,
    required super.amount,
  });

  factory CostItemModel.fromJson(Map<String, dynamic> json) {
    return CostItemModel(
      category: json['category'] ?? '',
      description: json['description'] ?? '',
      amount: (json['amount'] ?? 0).toDouble(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'category': category,
      'description': description,
      'amount': amount,
    };
  }
}

class CostBreakdownModel extends CostBreakdown {
  const CostBreakdownModel({
    super.items,
  });

  factory CostBreakdownModel.fromJson(Map<String, dynamic> json) {
    return CostBreakdownModel(
      items: (json['items'] as List?)
          ?.map((i) => CostItemModel.fromJson(i as Map<String, dynamic>))
          .toList() ?? [],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'items': items.map((i) => (i as CostItemModel).toJson()).toList(),
    };
  }
}

class EnhancedActivityModel extends EnhancedActivity {
  const EnhancedActivityModel({
    required super.time,
    super.durationMinutes,
    required super.activityType,
    required super.title,
    super.location,
    super.description,
    super.estimatedCost,
    super.professionalAdvice,
    super.alternatives,
    super.costBreakdown,
  });

  factory EnhancedActivityModel.fromJson(Map<String, dynamic> json) {
    // Handle location which can be either a String or a Map object
    String locationStr = '';
    final locationData = json['location'];
    if (locationData != null) {
      if (locationData is String) {
        locationStr = locationData;
      } else if (locationData is Map<String, dynamic>) {
        // Extract name and address from the location object
        final name = locationData['name'] ?? '';
        final address = locationData['address'] ?? '';
        if (name.isNotEmpty && address.isNotEmpty) {
          locationStr = '$name ($address)';
        } else if (name.isNotEmpty) {
          locationStr = name;
        } else if (address.isNotEmpty) {
          locationStr = address;
        }
      }
    }

    return EnhancedActivityModel(
      time: json['time'] ?? '09:00',
      durationMinutes: json['duration_minutes'] ?? 60,
      activityType: json['activity_type'] ?? 'other',
      title: json['title'] ?? '',
      location: locationStr,
      description: json['description'] ?? '',
      estimatedCost: (json['estimated_cost'] ?? 0).toDouble(),
      professionalAdvice: json['professional_advice'] != null
          ? ProfessionalAdviceModel.fromJson(json['professional_advice'])
          : null,
      alternatives: (json['alternatives'] as List?)
          ?.map((a) => AlternativeModel.fromJson(a as Map<String, dynamic>))
          .toList() ?? [],
      costBreakdown: json['cost_breakdown'] != null
          ? CostBreakdownModel.fromJson(json['cost_breakdown'])
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'time': time,
      'duration_minutes': durationMinutes,
      'activity_type': activityType,
      'title': title,
      'location': location,
      'description': description,
      'estimated_cost': estimatedCost,
      if (professionalAdvice != null)
        'professional_advice': (professionalAdvice as ProfessionalAdviceModel).toJson(),
      'alternatives': alternatives
          .map((a) => (a as AlternativeModel).toJson())
          .toList(),
      if (costBreakdown != null)
        'cost_breakdown': (costBreakdown as CostBreakdownModel).toJson(),
    };
  }
}

class DaySummaryModel extends DaySummary {
  const DaySummaryModel({
    super.totalCost,
    super.walkingDistanceKm,
    super.activityCount,
    super.energyLevel,
    super.costBreakdown,
  });

  factory DaySummaryModel.fromJson(Map<String, dynamic> json) {
    return DaySummaryModel(
      totalCost: (json['total_cost'] ?? 0).toDouble(),
      walkingDistanceKm: (json['walking_distance_km'] ?? 0).toDouble(),
      activityCount: json['activity_count'] ?? 0,
      energyLevel: json['energy_level'] ?? 'moderate',
      costBreakdown: (json['cost_breakdown'] as Map<String, dynamic>?)
          ?.map((k, v) => MapEntry(k, (v ?? 0).toDouble())) ?? {},
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'total_cost': totalCost,
      'walking_distance_km': walkingDistanceKm,
      'activity_count': activityCount,
      'energy_level': energyLevel,
      'cost_breakdown': costBreakdown,
    };
  }
}

class SmartDailyScheduleModel extends SmartDailySchedule {
  const SmartDailyScheduleModel({
    required super.day,
    required super.dateLabel,
    super.theme,
    super.summary,
    super.activities,
    super.daySummary,
  });

  factory SmartDailyScheduleModel.fromJson(Map<String, dynamic> json) {
    return SmartDailyScheduleModel(
      day: json['day'] ?? 1,
      dateLabel: json['date_label'] ?? '',
      theme: json['theme'] ?? '',
      summary: json['summary'] ?? '',
      activities: (json['activities'] as List?)
          ?.map((a) => EnhancedActivityModel.fromJson(a as Map<String, dynamic>))
          .toList() ?? [],
      daySummary: json['day_summary'] != null
          ? DaySummaryModel.fromJson(json['day_summary'])
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'day': day,
      'date_label': dateLabel,
      'theme': theme,
      'summary': summary,
      'activities': activities
          .map((a) => (a as EnhancedActivityModel).toJson())
          .toList(),
      if (daySummary != null)
        'day_summary': (daySummary as DaySummaryModel).toJson(),
    };
  }
}

class BackupPlanModel extends BackupPlan {
  const BackupPlanModel({
    required super.scenario,
    required super.alternative,
  });

  factory BackupPlanModel.fromJson(Map<String, dynamic> json) {
    return BackupPlanModel(
      scenario: json['scenario'] ?? '',
      alternative: json['alternative'] ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'scenario': scenario,
      'alternative': alternative,
    };
  }
}

class TripDesignRationaleModel extends TripDesignRationale {
  const TripDesignRationaleModel({
    required super.planningPhilosophy,
    required super.routeLogic,
    super.highlights,
    super.backupPlans,
    super.localTips,
  });

  factory TripDesignRationaleModel.fromJson(Map<String, dynamic> json) {
    return TripDesignRationaleModel(
      planningPhilosophy: json['planning_philosophy'] ?? '',
      routeLogic: json['route_logic'] ?? '',
      highlights: (json['highlights'] as List?)?.cast<String>() ?? [],
      backupPlans: (json['backup_plans'] as List?)
          ?.map((b) => BackupPlanModel.fromJson(b as Map<String, dynamic>))
          .toList() ?? [],
      localTips: (json['local_tips'] as List?)?.cast<String>() ?? [],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'planning_philosophy': planningPhilosophy,
      'route_logic': routeLogic,
      'highlights': highlights,
      'backup_plans': backupPlans
          .map((b) => (b as BackupPlanModel).toJson())
          .toList(),
      'local_tips': localTips,
    };
  }
}

class BudgetCategoryModel extends BudgetCategory {
  const BudgetCategoryModel({
    required super.amount,
    required super.percentage,
  });

  factory BudgetCategoryModel.fromJson(Map<String, dynamic> json) {
    return BudgetCategoryModel(
      amount: (json['amount'] ?? 0).toDouble(),
      percentage: (json['percentage'] ?? 0).toDouble(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'amount': amount,
      'percentage': percentage,
    };
  }
}

class BudgetAllocationModel extends BudgetAllocation {
  const BudgetAllocationModel({
    super.categories,
    super.totalBudget,
  });

  factory BudgetAllocationModel.fromJson(Map<String, dynamic> json) {
    final categoriesMap = <String, BudgetCategory>{};
    if (json['categories'] != null) {
      (json['categories'] as Map<String, dynamic>).forEach((key, value) {
        categoriesMap[key] = BudgetCategoryModel.fromJson(value);
      });
    }
    return BudgetAllocationModel(
      categories: categoriesMap,
      totalBudget: (json['total_budget'] ?? 0).toDouble(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'categories': categories.map((k, v) => MapEntry(k, (v as BudgetCategoryModel).toJson())),
      'total_budget': totalBudget,
    };
  }
}

class SmartItineraryResponseModel extends SmartItineraryResponse {
  const SmartItineraryResponseModel({
    required super.tripId,
    required super.destination,
    required super.durationDays,
    super.styles,
    required super.generatedAt,
    super.tripDesignRationale,
    super.budgetAllocation,
    super.dailySchedules,
  });

  factory SmartItineraryResponseModel.fromJson(Map<String, dynamic> json) {
    return SmartItineraryResponseModel(
      tripId: json['trip_id']?.toString() ?? '',
      destination: json['destination'] ?? '',
      durationDays: json['duration_days'] ?? 1,
      styles: (json['styles'] as List?)?.cast<String>() ?? [],
      generatedAt: json['generated_at'] ?? DateTime.now().toIso8601String(),
      tripDesignRationale: json['trip_design_rationale'] != null
          ? TripDesignRationaleModel.fromJson(json['trip_design_rationale'])
          : null,
      budgetAllocation: json['budget_allocation'] != null
          ? BudgetAllocationModel.fromJson(json['budget_allocation'])
          : null,
      dailySchedules: (json['daily_schedules'] as List?)
          ?.map((d) => SmartDailyScheduleModel.fromJson(d as Map<String, dynamic>))
          .toList() ?? [],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'trip_id': tripId,
      'destination': destination,
      'duration_days': durationDays,
      'styles': styles,
      'generated_at': generatedAt,
      if (tripDesignRationale != null)
        'trip_design_rationale': (tripDesignRationale as TripDesignRationaleModel).toJson(),
      if (budgetAllocation != null)
        'budget_allocation': (budgetAllocation as BudgetAllocationModel).toJson(),
      'daily_schedules': dailySchedules
          .map((d) => (d as SmartDailyScheduleModel).toJson())
          .toList(),
    };
  }
}

/// 增量更新响应
class IncrementalUpdateResponse {
  final bool success;
  final String? message;
  final Map<String, dynamic>? updatedSchedule;
  final DaySummaryModel? daySummary;

  const IncrementalUpdateResponse({
    this.success = true,
    this.message,
    this.updatedSchedule,
    this.daySummary,
  });

  factory IncrementalUpdateResponse.fromJson(Map<String, dynamic> json) {
    return IncrementalUpdateResponse(
      success: json['success'] ?? true,
      message: json['message'],
      updatedSchedule: json['updated_schedule'],
      daySummary: json['day_summary'] != null
          ? DaySummaryModel.fromJson(json['day_summary'])
          : null,
    );
  }
}

/// 活动创建请求
class ActivityCreateRequest {
  final String time;
  final String title;
  final String? activityType;
  final String? location;
  final String? description;
  final double? estimatedCost;

  const ActivityCreateRequest({
    required this.time,
    required this.title,
    this.activityType,
    this.location,
    this.description,
    this.estimatedCost,
  });

  Map<String, dynamic> toJson() {
    return {
      'time': time,
      'title': title,
      if (activityType != null) 'activity_type': activityType,
      if (location != null) 'location': location,
      if (description != null) 'description': description,
      if (estimatedCost != null) 'estimated_cost': estimatedCost,
    };
  }
}

/// 活动更新请求
class ActivityUpdateRequest {
  final int activityIndex;
  final String? time;
  final int? durationMinutes;
  final String? title;
  final String? location;
  final String? description;
  final double? estimatedCost;

  const ActivityUpdateRequest({
    required this.activityIndex,
    this.time,
    this.durationMinutes,
    this.title,
    this.location,
    this.description,
    this.estimatedCost,
  });

  Map<String, dynamic> toJson() {
    return {
      'activity_index': activityIndex,
      if (time != null) 'time': time,
      if (durationMinutes != null) 'duration_minutes': durationMinutes,
      if (title != null) 'title': title,
      if (location != null) 'location': location,
      if (description != null) 'description': description,
      if (estimatedCost != null) 'estimated_cost': estimatedCost,
    };
  }
}
