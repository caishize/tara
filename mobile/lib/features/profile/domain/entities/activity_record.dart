import 'package:equatable/equatable.dart';

/// Type of activity performed by the secretary
enum ActivityType {
  reminder,
  giftRecommendation,
  priceAlert,
  holidaySync,
  holidayPreparation,
  other,
}

/// A single activity record from the secretary
class ActivityRecord extends Equatable {
  final String id;
  final ActivityType type;
  final String title;
  final String? description;
  final String? targetName; // e.g., family member name, product name
  final DateTime createdAt;
  final Map<String, dynamic>? metadata;

  const ActivityRecord({
    required this.id,
    required this.type,
    required this.title,
    this.description,
    this.targetName,
    required this.createdAt,
    this.metadata,
  });

  /// Get icon for this activity type
  String get iconName {
    switch (type) {
      case ActivityType.reminder:
        return 'notifications_active';
      case ActivityType.giftRecommendation:
        return 'redeem';
      case ActivityType.priceAlert:
        return 'trending_down';
      case ActivityType.holidaySync:
        return 'celebration';
      case ActivityType.holidayPreparation:
        return 'card_giftcard';
      case ActivityType.other:
        return 'auto_awesome';
    }
  }

  /// Get type display text
  String get typeText {
    switch (type) {
      case ActivityType.reminder:
        return '日期提醒';
      case ActivityType.giftRecommendation:
        return '礼物推荐';
      case ActivityType.priceAlert:
        return '价格监控';
      case ActivityType.holidaySync:
        return '节日同步';
      case ActivityType.holidayPreparation:
        return '节日准备';
      case ActivityType.other:
        return '其他';
    }
  }

  /// Get relative time text
  String get relativeTimeText {
    final now = DateTime.now();
    final diff = now.difference(createdAt);

    if (diff.inMinutes < 1) return '刚刚';
    if (diff.inMinutes < 60) return '${diff.inMinutes}分钟前';
    if (diff.inHours < 24) return '${diff.inHours}小时前';
    if (diff.inDays < 7) return '${diff.inDays}天前';
    return '${createdAt.month}月${createdAt.day}日';
  }

  /// Get formatted date for grouping
  String get dateGroup {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final yesterday = today.subtract(const Duration(days: 1));
    final activityDate =
        DateTime(createdAt.year, createdAt.month, createdAt.day);

    if (activityDate == today) return '今天';
    if (activityDate == yesterday) return '昨天';
    if (now.difference(createdAt).inDays < 7) return '本周';
    if (now.month == createdAt.month && now.year == createdAt.year) {
      return '本月';
    }
    return '${createdAt.month}月';
  }

  @override
  List<Object?> get props =>
      [id, type, title, description, targetName, createdAt, metadata];
}

/// Summary of activities
class ActivitySummary extends Equatable {
  final int totalTasksCompleted;
  final int remindersSent;
  final int giftsRecommended;
  final int priceAlerts;
  final int holidaysSynced;
  final String period; // 'week' or 'month'

  const ActivitySummary({
    required this.totalTasksCompleted,
    required this.remindersSent,
    required this.giftsRecommended,
    required this.priceAlerts,
    required this.holidaysSynced,
    required this.period,
  });

  factory ActivitySummary.empty() => const ActivitySummary(
        totalTasksCompleted: 0,
        remindersSent: 0,
        giftsRecommended: 0,
        priceAlerts: 0,
        holidaysSynced: 0,
        period: 'week',
      );

  String get periodText => period == 'week' ? '本周' : '本月';

  @override
  List<Object?> get props => [
        totalTasksCompleted,
        remindersSent,
        giftsRecommended,
        priceAlerts,
        holidaysSynced,
        period,
      ];
}

/// Activity timeline with records and summary
class ActivityTimeline extends Equatable {
  final List<ActivityRecord> activities;
  final ActivitySummary summary;

  const ActivityTimeline({
    required this.activities,
    required this.summary,
  });

  factory ActivityTimeline.empty() => ActivityTimeline(
        activities: const [],
        summary: ActivitySummary.empty(),
      );

  /// Group activities by date
  Map<String, List<ActivityRecord>> get groupedActivities {
    final Map<String, List<ActivityRecord>> groups = {};
    for (var activity in activities) {
      final group = activity.dateGroup;
      groups.putIfAbsent(group, () => []).add(activity);
    }
    return groups;
  }

  @override
  List<Object?> get props => [activities, summary];
}
