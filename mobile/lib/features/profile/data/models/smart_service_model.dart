import '../../domain/entities/smart_service.dart';

class SmartServiceModel extends SmartService {
  const SmartServiceModel({
    required super.id,
    required super.displayName,
    required super.description,
    required super.icon,
    required super.category,
    required super.isEnabled,
    required super.isRunning,
    super.lastRun,
    super.lastStatus,
    super.nextRun,
    super.totalExecutions = 0,
    super.successRate = 0.0,
  });

  factory SmartServiceModel.fromJson(Map<String, dynamic> json) {
    return SmartServiceModel(
      id: json['id'] as String,
      displayName: json['display_name'] as String,
      description: json['description'] as String? ?? '',
      icon: json['icon'] as String? ?? 'settings',
      category: _parseCategory(json['category'] as String?),
      isEnabled: json['is_enabled'] as bool? ?? false,
      isRunning: json['is_running'] as bool? ?? false,
      lastRun: json['last_run'] as String?,
      lastStatus: json['last_status'] as String?,
      nextRun: json['next_run'] as String?,
      totalExecutions: json['total_executions'] as int? ?? 0,
      successRate: (json['success_rate'] as num?)?.toDouble() ?? 0.0,
    );
  }

  static ServiceCategory _parseCategory(String? category) {
    switch (category?.toLowerCase()) {
      case 'reminder':
        return ServiceCategory.reminder;
      case 'recommendation':
        return ServiceCategory.recommendation;
      case 'monitoring':
        return ServiceCategory.monitoring;
      case 'sync':
        return ServiceCategory.sync;
      default:
        return ServiceCategory.other;
    }
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'display_name': displayName,
      'description': description,
      'icon': icon,
      'category': category.name,
      'is_enabled': isEnabled,
      'is_running': isRunning,
      'last_run': lastRun,
      'last_status': lastStatus,
      'next_run': nextRun,
      'total_executions': totalExecutions,
      'success_rate': successRate,
    };
  }

  factory SmartServiceModel.fromEntity(SmartService service) {
    return SmartServiceModel(
      id: service.id,
      displayName: service.displayName,
      description: service.description,
      icon: service.icon,
      category: service.category,
      isEnabled: service.isEnabled,
      isRunning: service.isRunning,
      lastRun: service.lastRun,
      lastStatus: service.lastStatus,
      nextRun: service.nextRun,
      totalExecutions: service.totalExecutions,
      successRate: service.successRate,
    );
  }
}

class SmartServicesSummaryModel extends SmartServicesSummary {
  const SmartServicesSummaryModel({
    required List<SmartService> services,
    required super.totalCount,
    required super.activeCount,
  }) : super(services: services);

  factory SmartServicesSummaryModel.fromJson(Map<String, dynamic> json) {
    final servicesList = (json['services'] as List<dynamic>?)
            ?.map((s) => SmartServiceModel.fromJson(s as Map<String, dynamic>))
            .toList() ??
        [];

    return SmartServicesSummaryModel(
      services: servicesList,
      totalCount: json['total_count'] as int? ?? servicesList.length,
      activeCount: json['active_count'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'services': services
          .map((s) => SmartServiceModel.fromEntity(s).toJson())
          .toList(),
      'total_count': totalCount,
      'active_count': activeCount,
    };
  }
}
