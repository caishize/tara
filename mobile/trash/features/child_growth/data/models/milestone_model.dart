import '../../domain/entities/milestone.dart';

/// 里程碑数据模型
class MilestoneModel extends Milestone {
  const MilestoneModel({
    required super.id,
    required super.childId,
    required super.type,
    required super.title,
    super.description,
    required super.achievedDate,
    super.ageMonths,
    super.isTypical,
    super.typicalAgeMin,
    super.typicalAgeMax,
    super.photoUrl,
    super.videoUrl,
    super.notes,
    required super.createdAt,
  });

  factory MilestoneModel.fromJson(Map<String, dynamic> json) {
    return MilestoneModel(
      id: json['id'] as String? ?? '',
      childId: json['child_id'] as String? ?? '',
      type: _parseType(json['milestone_type'] as String? ?? json['category'] as String? ?? 'physical'),
      title: json['title'] as String? ?? json['event_name'] as String? ?? '',
      description: json['description'] as String?,
      achievedDate: DateTime.parse(json['achieved_date'] as String? ?? DateTime.now().toIso8601String()),
      ageMonths: json['age_months'] as int? ?? json['age_in_months'] as int?,
      isTypical: json['is_typical'] as bool?,
      typicalAgeMin: json['typical_age_range_min'] as int?,
      typicalAgeMax: json['typical_age_range_max'] as int?,
      photoUrl: json['photo_url'] as String?,
      videoUrl: json['video_url'] as String?,
      notes: json['notes'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String? ?? DateTime.now().toIso8601String()),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'child_id': childId,
      'milestone_type': _typeToString(type),
      'title': title,
      if (description != null) 'description': description,
      'achieved_date': achievedDate.toIso8601String().split('T').first,
      if (ageMonths != null) 'age_months': ageMonths,
      if (photoUrl != null) 'photo_url': photoUrl,
      if (videoUrl != null) 'video_url': videoUrl,
      if (notes != null) 'notes': notes,
    };
  }

  factory MilestoneModel.fromEntity(Milestone entity) {
    return MilestoneModel(
      id: entity.id,
      childId: entity.childId,
      type: entity.type,
      title: entity.title,
      description: entity.description,
      achievedDate: entity.achievedDate,
      ageMonths: entity.ageMonths,
      isTypical: entity.isTypical,
      typicalAgeMin: entity.typicalAgeMin,
      typicalAgeMax: entity.typicalAgeMax,
      photoUrl: entity.photoUrl,
      videoUrl: entity.videoUrl,
      notes: entity.notes,
      createdAt: entity.createdAt,
    );
  }

  static MilestoneType _parseType(String type) {
    switch (type.toLowerCase()) {
      case 'physical':
      case 'motor':
        return MilestoneType.physical;
      case 'cognitive':
        return MilestoneType.cognitive;
      case 'language':
        return MilestoneType.language;
      case 'social':
        return MilestoneType.social;
      case 'emotional':
        return MilestoneType.emotional;
      default:
        return MilestoneType.physical;
    }
  }

  static String _typeToString(MilestoneType type) {
    switch (type) {
      case MilestoneType.physical:
        return 'physical';
      case MilestoneType.cognitive:
        return 'cognitive';
      case MilestoneType.language:
        return 'language';
      case MilestoneType.social:
        return 'social';
      case MilestoneType.emotional:
        return 'emotional';
    }
  }
}
