import 'package:equatable/equatable.dart';

/// Relationship category
enum RelationshipCategory {
  family,
  network;

  String get displayName {
    switch (this) {
      case RelationshipCategory.family:
        return '家人圈';
      case RelationshipCategory.network:
        return '人脉圈';
    }
  }
}

/// Health status level
enum HealthLevel {
  excellent,
  good,
  warning,
  attention,
  critical;

  String get label {
    switch (this) {
      case HealthLevel.excellent:
        return '关系稳固';
      case HealthLevel.good:
        return '关系良好';
      case HealthLevel.warning:
        return '需要维护';
      case HealthLevel.attention:
        return '亟需联络';
      case HealthLevel.critical:
        return '关系危机';
    }
  }

  String get emoji {
    switch (this) {
      case HealthLevel.excellent:
        return '💚';
      case HealthLevel.good:
        return '💛';
      case HealthLevel.warning:
        return '💡';
      case HealthLevel.attention:
        return '⚠️';
      case HealthLevel.critical:
        return '🔴';
    }
  }
}

/// Score breakdown for relationship health
class RelationshipScore extends Equatable {
  final int total;
  final double contactScore;
  final double careScore;
  final double understandingScore;
  final double? favorScore;
  final double? mutualScore;
  final int? daysSinceContact;
  final int thresholdDays;
  final int? favorBalance;

  const RelationshipScore({
    required this.total,
    required this.contactScore,
    this.careScore = 0,
    this.understandingScore = 0,
    this.favorScore,
    this.mutualScore,
    this.daysSinceContact,
    required this.thresholdDays,
    this.favorBalance,
  });

  @override
  List<Object?> get props => [
        total,
        contactScore,
        careScore,
        understandingScore,
        favorScore,
        mutualScore,
        daysSinceContact,
        thresholdDays,
        favorBalance,
      ];
}

/// Health status with color
class HealthStatus extends Equatable {
  final HealthLevel level;
  final String color;
  final String label;
  final String emoji;

  const HealthStatus({
    required this.level,
    required this.color,
    required this.label,
    required this.emoji,
  });

  @override
  List<Object?> get props => [level, color, label, emoji];
}

/// Suggested action for relationship maintenance
class SuggestedAction extends Equatable {
  final String type;
  final String priority;
  final String title;
  final String description;
  final String icon;

  const SuggestedAction({
    required this.type,
    required this.priority,
    required this.title,
    required this.description,
    required this.icon,
  });

  @override
  List<Object?> get props => [type, priority, title, description, icon];
}

/// Upcoming important date
class UpcomingDate extends Equatable {
  final String title;
  final int daysUntil;
  final String? dateType;

  const UpcomingDate({
    required this.title,
    required this.daysUntil,
    this.dateType,
  });

  @override
  List<Object?> get props => [title, daysUntil, dateType];
}

/// Member with relationship health data
class RelationshipMember extends Equatable {
  final String id;
  final String name;
  final String? nickname;
  final String displayName;
  final String? avatarUrl;
  final String relationType;
  final String relationDisplay;
  final RelationshipCategory category;
  final String? phone;
  final String? email;
  final int? age;
  final String? gender;
  final String? occupation;
  final String? workplace;
  final int profileCompletion;
  final RelationshipScore score;
  final HealthStatus status;
  final DateTime? lastInteraction;
  final List<UpcomingDate> upcomingDates;
  final List<SuggestedAction> suggestedActions;
  final int? favorBalance;

  const RelationshipMember({
    required this.id,
    required this.name,
    this.nickname,
    required this.displayName,
    this.avatarUrl,
    required this.relationType,
    required this.relationDisplay,
    required this.category,
    this.phone,
    this.email,
    this.age,
    this.gender,
    this.occupation,
    this.workplace,
    this.profileCompletion = 0,
    required this.score,
    required this.status,
    this.lastInteraction,
    this.upcomingDates = const [],
    this.suggestedActions = const [],
    this.favorBalance,
  });

  /// Get the initials for avatar display
  String get initials {
    final name = displayName;
    if (name.isEmpty) return '?';
    // Get first character (works for both Chinese and ASCII)
    return name.substring(0, 1);
  }

  /// Check if this is a family member
  bool get isFamily => category == RelationshipCategory.family;

  /// Check if contact is overdue
  bool get isOverdue {
    final days = score.daysSinceContact;
    if (days == null) return false;
    return days > score.thresholdDays;
  }

  /// Get days since last contact as string
  String get lastContactText {
    final days = score.daysSinceContact;
    if (days == null) return '从未联络';
    if (days == 0) return '今天';
    if (days == 1) return '昨天';
    if (days < 7) return '$days天前';
    if (days < 30) return '${days ~/ 7}周前';
    if (days < 365) return '${days ~/ 30}个月前';
    return '${days ~/ 365}年前';
  }

  @override
  List<Object?> get props => [
        id,
        name,
        nickname,
        displayName,
        avatarUrl,
        relationType,
        relationDisplay,
        category,
        phone,
        email,
        age,
        gender,
        occupation,
        workplace,
        profileCompletion,
        score,
        status,
        lastInteraction,
        upcomingDates,
        suggestedActions,
        favorBalance,
      ];
}

/// Summary statistics for relationships
class RelationshipSummary extends Equatable {
  final int totalCount;
  final int familyCount;
  final int networkCount;
  final double averageScore;
  final int needsAttention;
  final int excellent;

  const RelationshipSummary({
    required this.totalCount,
    required this.familyCount,
    required this.networkCount,
    required this.averageScore,
    required this.needsAttention,
    required this.excellent,
  });

  @override
  List<Object?> get props => [
        totalCount,
        familyCount,
        networkCount,
        averageScore,
        needsAttention,
        excellent,
      ];
}

/// Complete relationship data response
class RelationshipData extends Equatable {
  final List<RelationshipMember> family;
  final List<RelationshipMember> network;
  final RelationshipSummary summary;

  const RelationshipData({
    required this.family,
    required this.network,
    required this.summary,
  });

  /// Get all members
  List<RelationshipMember> get all => [...family, ...network];

  @override
  List<Object?> get props => [family, network, summary];
}
