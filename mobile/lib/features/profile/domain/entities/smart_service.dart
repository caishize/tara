import 'package:equatable/equatable.dart';

/// Service category enum
enum ServiceCategory {
  reminder,
  recommendation,
  monitoring,
  sync,
  other,
}

/// Smart service entity
class SmartService extends Equatable {
  final String id;
  final String displayName;
  final String description;
  final String icon;
  final ServiceCategory category;
  final bool isEnabled;
  final bool isRunning;
  final String? lastRun;
  final String? lastStatus;
  final String? nextRun;
  final int totalExecutions;
  final double successRate;

  const SmartService({
    required this.id,
    required this.displayName,
    required this.description,
    required this.icon,
    required this.category,
    required this.isEnabled,
    required this.isRunning,
    this.lastRun,
    this.lastStatus,
    this.nextRun,
    this.totalExecutions = 0,
    this.successRate = 0.0,
  });

  /// Get category display name in Chinese
  String get categoryText {
    switch (category) {
      case ServiceCategory.reminder:
        return '提醒服务';
      case ServiceCategory.recommendation:
        return '推荐服务';
      case ServiceCategory.monitoring:
        return '监控服务';
      case ServiceCategory.sync:
        return '同步服务';
      case ServiceCategory.other:
        return '其他服务';
    }
  }

  /// Get status display text
  String get statusText {
    if (isRunning) return '运行中';
    if (isEnabled) return '已暂停';
    return '已停止';
  }

  /// Get last run relative time text
  String? get lastRunText {
    if (lastRun == null) return null;
    try {
      final lastRunTime = DateTime.parse(lastRun!);
      final now = DateTime.now();
      final diff = now.difference(lastRunTime);

      if (diff.inMinutes < 1) return '刚刚';
      if (diff.inMinutes < 60) return '${diff.inMinutes}分钟前';
      if (diff.inHours < 24) return '${diff.inHours}小时前';
      if (diff.inDays < 7) return '${diff.inDays}天前';
      return '${lastRunTime.month}月${lastRunTime.day}日';
    } catch (e) {
      return lastRun;
    }
  }

  @override
  List<Object?> get props => [
        id,
        displayName,
        description,
        icon,
        category,
        isEnabled,
        isRunning,
        lastRun,
        lastStatus,
        nextRun,
        totalExecutions,
        successRate,
      ];
}

/// Smart services summary
class SmartServicesSummary extends Equatable {
  final List<SmartService> services;
  final int totalCount;
  final int activeCount;

  const SmartServicesSummary({
    required this.services,
    required this.totalCount,
    required this.activeCount,
  });

  /// Create empty summary
  factory SmartServicesSummary.empty() => const SmartServicesSummary(
        services: [],
        totalCount: 0,
        activeCount: 0,
      );

  /// Get services by category
  List<SmartService> servicesByCategory(ServiceCategory category) {
    return services.where((s) => s.category == category).toList();
  }

  @override
  List<Object?> get props => [services, totalCount, activeCount];
}
