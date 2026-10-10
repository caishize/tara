import 'package:equatable/equatable.dart';

/// User statistics entity
class UserStats extends Equatable {
  final int daysSinceJoined;
  final int totalRecords;
  final int completedGoals;
  final int familyMemberCount;
  final int upcomingEventsCount;
  final int activeServicesCount;

  const UserStats({
    required this.daysSinceJoined,
    required this.totalRecords,
    required this.completedGoals,
    required this.familyMemberCount,
    required this.upcomingEventsCount,
    required this.activeServicesCount,
  });

  /// Create empty stats
  factory UserStats.empty() => const UserStats(
        daysSinceJoined: 0,
        totalRecords: 0,
        completedGoals: 0,
        familyMemberCount: 0,
        upcomingEventsCount: 0,
        activeServicesCount: 0,
      );

  @override
  List<Object?> get props => [
        daysSinceJoined,
        totalRecords,
        completedGoals,
        familyMemberCount,
        upcomingEventsCount,
        activeServicesCount,
      ];
}
