import '../../domain/entities/activity_record.dart';

class ActivityRecordModel extends ActivityRecord {
  const ActivityRecordModel({
    required super.id,
    required super.type,
    required super.title,
    super.description,
    super.targetName,
    required super.createdAt,
    super.metadata,
  });

  /// Create activity record from execution history item
  factory ActivityRecordModel.fromExecution(Map<String, dynamic> json) {
    final schedulerName = json['scheduler_name'] as String? ?? '';
    final jobName = json['job_name'] as String? ?? '';
    final status = json['status'] as String? ?? '';
    final resultSummary = json['result_summary'] as Map<String, dynamic>?;

    // Only create activities for successful executions
    if (status != 'completed') {
      return ActivityRecordModel(
        id: json['id'] as String? ?? '',
        type: ActivityType.other,
        title: '任务执行失败',
        description: json['error_message'] as String?,
        createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ??
            DateTime.now(),
      );
    }

    // Determine activity type and details based on scheduler/job name
    final type = _determineActivityType(schedulerName, jobName);
    final title = _generateTitle(type, schedulerName, jobName, resultSummary);
    final description = _generateDescription(type, resultSummary);
    final targetName = _extractTargetName(type, resultSummary);

    return ActivityRecordModel(
      id: json['id'] as String? ?? '',
      type: type,
      title: title,
      description: description,
      targetName: targetName,
      createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ??
          DateTime.now(),
      metadata: resultSummary,
    );
  }

  static ActivityType _determineActivityType(
      String schedulerName, String jobName) {
    final lower = schedulerName.toLowerCase();
    if (lower.contains('reminder')) return ActivityType.reminder;
    if (lower.contains('gift') || lower.contains('recommendation')) {
      return ActivityType.giftRecommendation;
    }
    if (lower.contains('price')) return ActivityType.priceAlert;
    if (lower.contains('holiday_sync')) return ActivityType.holidaySync;
    if (lower.contains('holiday_prep')) return ActivityType.holidayPreparation;
    return ActivityType.other;
  }

  static String _generateTitle(
    ActivityType type,
    String schedulerName,
    String jobName,
    Map<String, dynamic>? result,
  ) {
    switch (type) {
      case ActivityType.reminder:
        final count = result?['reminders_sent'] ?? result?['count'] ?? 0;
        if (count > 0) return '发送了 $count 条日期提醒';
        return '检查了重要日期';
      case ActivityType.giftRecommendation:
        final count = result?['recommendations_count'] ?? result?['count'] ?? 0;
        if (count > 0) return '推荐了 $count 款礼物';
        return '更新了礼物推荐';
      case ActivityType.priceAlert:
        final count = result?['alerts_count'] ?? result?['count'] ?? 0;
        if (count > 0) return '监测到 $count 次价格变动';
        return '检查了商品价格';
      case ActivityType.holidaySync:
        final count = result?['holidays_synced'] ?? result?['count'] ?? 0;
        if (count > 0) return '同步了 $count 个节日';
        return '同步了节日日历';
      case ActivityType.holidayPreparation:
        return '检查了节日准备事项';
      case ActivityType.other:
        return result?['message'] as String? ?? '执行了任务';
    }
  }

  static String? _generateDescription(
    ActivityType type,
    Map<String, dynamic>? result,
  ) {
    if (result == null) return null;
    if (result.containsKey('message')) return result['message'] as String?;
    if (result.containsKey('details')) return result['details'] as String?;
    return null;
  }

  static String? _extractTargetName(
    ActivityType type,
    Map<String, dynamic>? result,
  ) {
    if (result == null) return null;
    if (result.containsKey('member_name')) {
      return result['member_name'] as String?;
    }
    if (result.containsKey('product_name')) {
      return result['product_name'] as String?;
    }
    return null;
  }
}

class ActivitySummaryModel extends ActivitySummary {
  const ActivitySummaryModel({
    required super.totalTasksCompleted,
    required super.remindersSent,
    required super.giftsRecommended,
    required super.priceAlerts,
    required super.holidaysSynced,
    required super.period,
  });

  factory ActivitySummaryModel.fromJson(Map<String, dynamic> json) {
    return ActivitySummaryModel(
      totalTasksCompleted: json['total_tasks_completed'] as int? ?? 0,
      remindersSent: json['reminders_sent'] as int? ?? 0,
      giftsRecommended: json['gifts_recommended'] as int? ?? 0,
      priceAlerts: json['price_alerts'] as int? ?? 0,
      holidaysSynced: json['holidays_synced'] as int? ?? 0,
      period: json['period'] as String? ?? 'week',
    );
  }

  /// Create summary from execution history
  factory ActivitySummaryModel.fromExecutions(
      List<Map<String, dynamic>> executions) {
    int reminders = 0;
    int gifts = 0;
    int prices = 0;
    int holidays = 0;
    int total = 0;

    for (var exec in executions) {
      if (exec['status'] != 'completed') continue;
      total++;

      final schedulerName =
          (exec['scheduler_name'] as String? ?? '').toLowerCase();
      if (schedulerName.contains('reminder')) {
        reminders++;
      } else if (schedulerName.contains('gift') ||
          schedulerName.contains('recommendation')) {
        gifts++;
      } else if (schedulerName.contains('price')) {
        prices++;
      } else if (schedulerName.contains('holiday')) {
        holidays++;
      }
    }

    return ActivitySummaryModel(
      totalTasksCompleted: total,
      remindersSent: reminders,
      giftsRecommended: gifts,
      priceAlerts: prices,
      holidaysSynced: holidays,
      period: 'week',
    );
  }
}
