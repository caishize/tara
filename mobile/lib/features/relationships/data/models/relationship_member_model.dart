import '../../domain/entities/relationship_member.dart';

/// Model class for parsing API response
class RelationshipMemberModel extends RelationshipMember {
  const RelationshipMemberModel({
    required super.id,
    required super.name,
    super.nickname,
    required super.displayName,
    super.avatarUrl,
    required super.relationType,
    required super.relationDisplay,
    required super.category,
    super.phone,
    super.email,
    super.age,
    super.gender,
    super.occupation,
    super.workplace,
    super.profileCompletion,
    required super.score,
    required super.status,
    super.lastInteraction,
    super.upcomingDates,
    super.suggestedActions,
    super.favorBalance,
  });

  factory RelationshipMemberModel.fromJson(Map<String, dynamic> json) {
    return RelationshipMemberModel(
      id: json['id'] as String,
      name: json['name'] as String,
      nickname: json['nickname'] as String?,
      displayName: json['display_name'] as String? ?? json['name'] as String,
      avatarUrl: json['avatar_url'] as String?,
      relationType: json['relation_type'] as String? ?? 'other',
      relationDisplay: json['relation_display'] as String? ?? '其他',
      category: _parseCategory(json['category'] as String?),
      phone: json['phone'] as String?,
      email: json['email'] as String?,
      age: json['age'] as int?,
      gender: json['gender'] as String?,
      occupation: json['occupation'] as String?,
      workplace: json['workplace'] as String?,
      profileCompletion: json['profile_completion'] as int? ?? 0,
      score: _parseScore(json['score'] as Map<String, dynamic>?),
      status: _parseStatus(json['status'] as Map<String, dynamic>?),
      lastInteraction: json['last_interaction'] != null
          ? DateTime.tryParse(json['last_interaction'] as String)
          : null,
      upcomingDates: _parseUpcomingDates(json['upcoming_dates'] as List?),
      suggestedActions: _parseActions(json['suggested_actions'] as List?),
      favorBalance: json['favor_balance'] as int?,
    );
  }

  static RelationshipCategory _parseCategory(String? category) {
    if (category == 'family') return RelationshipCategory.family;
    return RelationshipCategory.network;
  }

  static RelationshipScore _parseScore(Map<String, dynamic>? json) {
    if (json == null) {
      return const RelationshipScore(
        total: 0,
        contactScore: 0,
        thresholdDays: 90,
      );
    }
    return RelationshipScore(
      total: json['total'] as int? ?? 0,
      contactScore: (json['contact_score'] as num?)?.toDouble() ?? 0,
      careScore: (json['care_score'] as num?)?.toDouble() ?? 0,
      understandingScore: (json['understanding_score'] as num?)?.toDouble() ?? 0,
      favorScore: (json['favor_score'] as num?)?.toDouble(),
      mutualScore: (json['mutual_score'] as num?)?.toDouble(),
      daysSinceContact: json['days_since_contact'] as int?,
      thresholdDays: json['threshold_days'] as int? ?? 90,
      favorBalance: json['favor_balance'] as int?,
    );
  }

  static HealthStatus _parseStatus(Map<String, dynamic>? json) {
    if (json == null) {
      return const HealthStatus(
        level: HealthLevel.warning,
        color: '#EAB308',
        label: '需要维护',
        emoji: '💡',
      );
    }
    return HealthStatus(
      level: _parseHealthLevel(json['level'] as String?),
      color: json['color'] as String? ?? '#EAB308',
      label: json['label'] as String? ?? '需要维护',
      emoji: json['emoji'] as String? ?? '💡',
    );
  }

  static HealthLevel _parseHealthLevel(String? level) {
    switch (level) {
      case 'excellent':
        return HealthLevel.excellent;
      case 'good':
        return HealthLevel.good;
      case 'warning':
        return HealthLevel.warning;
      case 'attention':
        return HealthLevel.attention;
      case 'critical':
        return HealthLevel.critical;
      default:
        return HealthLevel.warning;
    }
  }

  static List<UpcomingDate> _parseUpcomingDates(List? json) {
    if (json == null) return [];
    return json.map((item) {
      final map = item as Map<String, dynamic>;
      return UpcomingDate(
        title: map['title'] as String? ?? '',
        daysUntil: map['days_until'] as int? ?? 0,
        dateType: map['date_type'] as String?,
      );
    }).toList();
  }

  static List<SuggestedAction> _parseActions(List? json) {
    if (json == null) return [];
    return json.map((item) {
      final map = item as Map<String, dynamic>;
      return SuggestedAction(
        type: map['type'] as String? ?? '',
        priority: map['priority'] as String? ?? 'medium',
        title: map['title'] as String? ?? '',
        description: map['description'] as String? ?? '',
        icon: map['icon'] as String? ?? 'info',
      );
    }).toList();
  }
}

/// Model for summary data
class RelationshipSummaryModel extends RelationshipSummary {
  const RelationshipSummaryModel({
    required super.totalCount,
    required super.familyCount,
    required super.networkCount,
    required super.averageScore,
    required super.needsAttention,
    required super.excellent,
  });

  factory RelationshipSummaryModel.fromJson(Map<String, dynamic> json) {
    return RelationshipSummaryModel(
      totalCount: json['total_count'] as int? ?? 0,
      familyCount: json['family_count'] as int? ?? 0,
      networkCount: json['network_count'] as int? ?? 0,
      averageScore: (json['average_score'] as num?)?.toDouble() ?? 0,
      needsAttention: json['needs_attention'] as int? ?? 0,
      excellent: json['excellent'] as int? ?? 0,
    );
  }
}

/// Model for complete relationship data response
class RelationshipDataModel extends RelationshipData {
  const RelationshipDataModel({
    required super.family,
    required super.network,
    required super.summary,
  });

  factory RelationshipDataModel.fromJson(Map<String, dynamic> json) {
    final familyList = (json['family'] as List?)
            ?.map((item) =>
                RelationshipMemberModel.fromJson(item as Map<String, dynamic>))
            .toList() ??
        [];

    final networkList = (json['network'] as List?)
            ?.map((item) =>
                RelationshipMemberModel.fromJson(item as Map<String, dynamic>))
            .toList() ??
        [];

    final summary = json['summary'] != null
        ? RelationshipSummaryModel.fromJson(
            json['summary'] as Map<String, dynamic>)
        : const RelationshipSummaryModel(
            totalCount: 0,
            familyCount: 0,
            networkCount: 0,
            averageScore: 0,
            needsAttention: 0,
            excellent: 0,
          );

    return RelationshipDataModel(
      family: familyList,
      network: networkList,
      summary: summary,
    );
  }
}
