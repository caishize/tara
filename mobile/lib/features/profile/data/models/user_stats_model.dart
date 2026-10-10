import '../../domain/entities/user_stats.dart';

class UserStatsModel extends UserStats {
  const UserStatsModel({
    required super.daysSinceJoined,
    required super.totalRecords,
    required super.completedGoals,
    required super.familyMemberCount,
    required super.upcomingEventsCount,
    required super.activeServicesCount,
  });

  factory UserStatsModel.fromJson(Map<String, dynamic> json) {
    return UserStatsModel(
      daysSinceJoined: json['days_since_joined'] as int? ?? 0,
      totalRecords: json['total_records'] as int? ?? 0,
      completedGoals: json['completed_goals'] as int? ?? 0,
      familyMemberCount: json['family_member_count'] as int? ?? 0,
      upcomingEventsCount: json['upcoming_events_count'] as int? ?? 0,
      activeServicesCount: json['active_services_count'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'days_since_joined': daysSinceJoined,
      'total_records': totalRecords,
      'completed_goals': completedGoals,
      'family_member_count': familyMemberCount,
      'upcoming_events_count': upcomingEventsCount,
      'active_services_count': activeServicesCount,
    };
  }

  factory UserStatsModel.fromEntity(UserStats stats) {
    return UserStatsModel(
      daysSinceJoined: stats.daysSinceJoined,
      totalRecords: stats.totalRecords,
      completedGoals: stats.completedGoals,
      familyMemberCount: stats.familyMemberCount,
      upcomingEventsCount: stats.upcomingEventsCount,
      activeServicesCount: stats.activeServicesCount,
    );
  }
}
