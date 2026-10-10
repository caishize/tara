import '../../../../core/utils/timezone_utils.dart';

import '../../domain/entities/itinerary_version.dart';
import '../../domain/entities/smart_itinerary.dart';

/// Helper function to safely extract a string from a dynamic value
String? _safeString(dynamic value) {
  if (value == null) return null;
  if (value is String) return value;
  if (value is Map<String, dynamic>) {
    return value['text']?.toString() ??
        value['content']?.toString() ??
        value['name']?.toString() ??
        value.toString();
  }
  if (value is List) {
    return value.map((e) => e.toString()).join(', ');
  }
  return value.toString();
}

/// Helper function to parse double from various types
double? _parseDouble(dynamic value) {
  if (value == null) return null;
  if (value is double) return value;
  if (value is int) return value.toDouble();
  if (value is String) return double.tryParse(value);
  return null;
}

class ItineraryVersionModel extends ItineraryVersion {
  const ItineraryVersionModel({
    required super.id,
    required super.tripId,
    required super.versionNumber,
    super.versionName,
    super.styleTags,
    super.isActive,
    super.totalEstimatedCost,
    super.schedules,
    super.generationConfig,
    required super.createdAt,
    super.updatedAt,
  });

  factory ItineraryVersionModel.fromJson(Map<String, dynamic> json) {
    // Parse schedules
    final schedulesData = json['schedules'] as List? ?? [];
    final schedules = schedulesData
        .map((s) => VersionDayScheduleModel.fromJson(s as Map<String, dynamic>))
        .toList();

    // Parse style tags
    final styleTags = (json['style_tags'] as List?)
            ?.map((e) => e.toString())
            .toList() ??
        [];

    // Parse generation config
    VersionGenerationConfigModel? generationConfig;
    if (json['generation_config'] != null) {
      generationConfig = VersionGenerationConfigModel.fromJson(
          json['generation_config'] as Map<String, dynamic>);
    }

    return ItineraryVersionModel(
      id: json['version_id']?.toString() ?? json['id']?.toString() ?? '',
      tripId: json['trip_id']?.toString() ?? '',
      versionNumber: json['version_number'] ?? 1,
      versionName: json['version_name']?.toString(),
      styleTags: styleTags,
      isActive: json['is_active'] ?? false,
      totalEstimatedCost: _parseDouble(json['total_estimated_cost']),
      schedules: schedules,
      generationConfig: generationConfig,
      createdAt: json['created_at'] != null
          ? TimezoneUtils.parseApiTime(json['created_at'])
          : DateTime.now().toUtc(),
      updatedAt: json['updated_at'] != null
          ? TimezoneUtils.parseApiTime(json['updated_at'])
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'version_id': id,
      'trip_id': tripId,
      'version_number': versionNumber,
      'version_name': versionName,
      'style_tags': styleTags,
      'is_active': isActive,
      'total_estimated_cost': totalEstimatedCost,
      'schedules': schedules
          .map((s) => (s as VersionDayScheduleModel).toJson())
          .toList(),
      'generation_config': generationConfig != null
          ? (generationConfig as VersionGenerationConfigModel).toJson()
          : null,
      'created_at': TimezoneUtils.toApiTime(createdAt),
      'updated_at': updatedAt != null ? TimezoneUtils.toApiTime(updatedAt!) : null,
    };
  }
}

class VersionDayScheduleModel extends VersionDaySchedule {
  const VersionDayScheduleModel({
    required super.dayNumber,
    super.activities,
    super.packingNotes,
    super.theme,
    super.summary,
  });

  factory VersionDayScheduleModel.fromJson(Map<String, dynamic> json) {
    final activitiesData =
        json['schedule'] as List? ?? json['activities'] as List? ?? [];

    return VersionDayScheduleModel(
      dayNumber: json['day_number'] ?? 1,
      activities: activitiesData
          .map((a) => VersionActivityModel.fromJson(a as Map<String, dynamic>))
          .toList(),
      packingNotes: _safeString(json['packing_notes']),
      theme: json['theme']?.toString(),
      summary: json['summary']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'day_number': dayNumber,
      'schedule':
          activities.map((a) => (a as VersionActivityModel).toJson()).toList(),
      'packing_notes': packingNotes,
      'theme': theme,
      'summary': summary,
    };
  }
}

class VersionActivityModel extends VersionActivity {
  const VersionActivityModel({
    super.id,
    required super.time,
    required super.activityType,
    required super.title,
    super.location,
    super.description,
    super.estimatedCost,
    super.professionalAdvice,
    super.alternatives,
    super.hasMultipleChoices,
  });

  factory VersionActivityModel.fromJson(Map<String, dynamic> json) {
    // Handle location
    String? locationStr;
    final locationData = json['location'];
    if (locationData != null) {
      if (locationData is String) {
        locationStr = locationData;
      } else if (locationData is Map<String, dynamic>) {
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

    // Parse alternatives
    final altData = json['alternatives'] as List? ?? [];
    final alternatives = altData.map((a) {
      if (a is String) {
        return SelectableAlternativeModel(
          id: '',
          title: a,
          reason: '',
        );
      }
      return SelectableAlternativeModel.fromJson(a as Map<String, dynamic>);
    }).toList();

    // Check if has multiple choices
    final hasMultipleChoices =
        json['has_multiple_choices'] ?? alternatives.isNotEmpty;

    return VersionActivityModel(
      id: json['id']?.toString(),
      time: json['time']?.toString() ?? '',
      activityType: json['activity_type']?.toString() ?? 'other',
      title: _safeString(json['title']) ?? '',
      location: locationStr,
      description: _safeString(json['description']),
      estimatedCost: _parseDouble(json['estimated_cost']),
      professionalAdvice: _safeString(json['professional_advice']),
      alternatives: alternatives,
      hasMultipleChoices: hasMultipleChoices,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'time': time,
      'activity_type': activityType,
      'title': title,
      'location': location,
      'description': description,
      'estimated_cost': estimatedCost,
      'professional_advice': professionalAdvice,
      'alternatives': alternatives
          .map((a) => (a as SelectableAlternativeModel).toJson())
          .toList(),
      'has_multiple_choices': hasMultipleChoices,
    };
  }
}

class SelectableAlternativeModel extends SelectableAlternative {
  const SelectableAlternativeModel({
    required super.id,
    required super.title,
    super.location,
    super.description,
    required super.reason,
    super.estimatedCost,
    super.activityType,
    super.isSimilar,
    super.similarityScore,
  });

  factory SelectableAlternativeModel.fromJson(Map<String, dynamic> json) {
    return SelectableAlternativeModel(
      id: json['id']?.toString() ?? '',
      title: json['title']?.toString() ?? json['name']?.toString() ?? '',
      location: json['location']?.toString(),
      description: json['description']?.toString(),
      reason: json['reason']?.toString() ?? '',
      estimatedCost: _parseDouble(json['estimated_cost']),
      activityType: json['activity_type']?.toString(),
      isSimilar: json['is_similar'] ?? true,
      similarityScore: _parseDouble(json['similarity_score']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'location': location,
      'description': description,
      'reason': reason,
      'estimated_cost': estimatedCost,
      'activity_type': activityType,
      'is_similar': isSimilar,
      'similarity_score': similarityScore,
    };
  }
}

class VersionGenerationConfigModel extends VersionGenerationConfig {
  const VersionGenerationConfigModel({
    super.styles,
    super.familyComposition,
    super.preferences,
  });

  factory VersionGenerationConfigModel.fromJson(Map<String, dynamic> json) {
    final styles =
        (json['styles'] as List?)?.map((e) => e.toString()).toList() ?? [];

    FamilyComposition? familyComp;
    if (json['family_composition'] != null) {
      final fc = json['family_composition'] as Map<String, dynamic>;
      familyComp = FamilyComposition(
        children: (fc['children'] as List?)
                ?.map((c) => FamilyMember(
                      name: c['name']?.toString(),
                      age: c['age'] ?? 0,
                      relation: c['relation']?.toString(),
                    ))
                .toList() ??
            [],
        elderly: (fc['elderly'] as List?)
                ?.map((e) => FamilyMember(
                      name: e['name']?.toString(),
                      age: e['age'] ?? 60,
                      relation: e['relation']?.toString(),
                    ))
                .toList() ??
            [],
        specialNeeds: (fc['special_needs'] as List?)
                ?.map((s) => s.toString())
                .toList() ??
            [],
      );
    }

    ItineraryPreferences? prefs;
    if (json['preferences'] != null) {
      final p = json['preferences'] as Map<String, dynamic>;
      prefs = ItineraryPreferences(
        enableNapTime: p['enable_nap_time'] ?? true,
        napTimeStart: p['nap_time_start']?.toString() ?? '14:00',
        napTimeEnd: p['nap_time_end']?.toString() ?? '16:00',
        weatherAware: p['weather_aware'] ?? true,
        includeLocalTips: p['include_local_tips'] ?? true,
        includeAlternatives: p['include_alternatives'] ?? true,
      );
    }

    return VersionGenerationConfigModel(
      styles: styles,
      familyComposition: familyComp,
      preferences: prefs,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'styles': styles,
      'family_composition': familyComposition != null
          ? {
              'children': familyComposition!.children
                  .map((c) => {
                        'name': c.name,
                        'age': c.age,
                        'relation': c.relation,
                      })
                  .toList(),
              'elderly': familyComposition!.elderly
                  .map((e) => {
                        'name': e.name,
                        'age': e.age,
                        'relation': e.relation,
                      })
                  .toList(),
              'special_needs': familyComposition!.specialNeeds,
            }
          : null,
      'preferences': preferences != null
          ? {
              'enable_nap_time': preferences!.enableNapTime,
              'nap_time_start': preferences!.napTimeStart,
              'nap_time_end': preferences!.napTimeEnd,
              'weather_aware': preferences!.weatherAware,
              'include_local_tips': preferences!.includeLocalTips,
              'include_alternatives': preferences!.includeAlternatives,
            }
          : null,
    };
  }
}

/// Summary model for list display
class ItineraryVersionSummaryModel extends ItineraryVersionSummary {
  const ItineraryVersionSummaryModel({
    required super.id,
    required super.versionNumber,
    super.versionName,
    super.styleTags,
    super.isActive,
    super.totalEstimatedCost,
    super.totalDays,
    super.totalActivities,
    required super.createdAt,
  });

  factory ItineraryVersionSummaryModel.fromJson(Map<String, dynamic> json) {
    return ItineraryVersionSummaryModel(
      id: json['version_id']?.toString() ?? json['id']?.toString() ?? '',
      versionNumber: json['version_number'] ?? 1,
      versionName: json['version_name']?.toString(),
      styleTags: (json['style_tags'] as List?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      isActive: json['is_active'] ?? false,
      totalEstimatedCost: _parseDouble(json['total_estimated_cost']),
      totalDays: json['total_days'] ?? 0,
      totalActivities: json['total_activities'] ?? 0,
      createdAt: json['created_at'] != null
          ? TimezoneUtils.parseApiTime(json['created_at'])
          : DateTime.now().toUtc(),
    );
  }
}
