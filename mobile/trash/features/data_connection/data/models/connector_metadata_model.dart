import '../../domain/entities/connector_metadata.dart';

class ConnectorMetadataModel extends ConnectorMetadata {
  const ConnectorMetadataModel({
    required super.id,
    required super.name,
    required super.displayName,
    required super.displayNameZh,
    required super.description,
    required super.descriptionZh,
    required super.icon,
    required super.category,
    required super.authType,
    required super.capabilities,
    required super.requiredScopes,
    required super.optionalScopes,
    required super.dataRetentionDays,
    required super.isAvailable,
    required super.regions,
    required super.dataUsageDescription,
    required super.dataUsageDescriptionZh,
  });

  factory ConnectorMetadataModel.fromJson(Map<String, dynamic> json) {
    return ConnectorMetadataModel(
      id: json['id'] as String,
      name: json['name'] as String,
      displayName: json['display_name'] as String,
      displayNameZh: json['display_name_zh'] as String? ?? json['display_name'] as String,
      description: json['description'] as String,
      descriptionZh: json['description_zh'] as String? ?? json['description'] as String,
      icon: json['icon'] as String? ?? 'extension',
      category: _parseCategory(json['category'] as String?),
      authType: _parseAuthType(json['auth_type'] as String?),
      capabilities: _parseCapabilities(json['capabilities']),
      requiredScopes: (json['required_scopes'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
      optionalScopes: (json['optional_scopes'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
      dataRetentionDays: json['data_retention_days'] as int? ?? 90,
      isAvailable: json['is_available'] as bool? ?? true,
      regions:
          (json['regions'] as List<dynamic>?)?.map((e) => e as String).toList() ??
              ['CN'],
      dataUsageDescription: json['data_usage_description'] as String? ?? '',
      dataUsageDescriptionZh:
          json['data_usage_description_zh'] as String? ?? json['data_usage_description'] as String? ?? '',
    );
  }

  static ConnectorCapabilities _parseCapabilities(dynamic value) {
    if (value == null) {
      return const ConnectorCapabilities();
    }
    if (value is Map<String, dynamic>) {
      return ConnectorCapabilities(
        canRead: value['can_read'] as bool? ?? true,
        canWrite: value['can_write'] as bool? ?? false,
        supportsWebhook: value['supports_webhook'] as bool? ?? false,
        supportsIncrementalSync: value['supports_incremental_sync'] as bool? ?? false,
        rateLimitPerHour: value['rate_limit_per_hour'] as int?,
        maxHistoricalDays: value['max_historical_days'] as int?,
      );
    }
    // Fallback for old list format (if any)
    return const ConnectorCapabilities();
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'display_name': displayName,
      'display_name_zh': displayNameZh,
      'description': description,
      'description_zh': descriptionZh,
      'icon': icon,
      'category': category.name,
      'auth_type': authType.name,
      'capabilities': {
        'can_read': capabilities.canRead,
        'can_write': capabilities.canWrite,
        'supports_webhook': capabilities.supportsWebhook,
        'supports_incremental_sync': capabilities.supportsIncrementalSync,
        'rate_limit_per_hour': capabilities.rateLimitPerHour,
        'max_historical_days': capabilities.maxHistoricalDays,
      },
      'required_scopes': requiredScopes,
      'optional_scopes': optionalScopes,
      'data_retention_days': dataRetentionDays,
      'is_available': isAvailable,
      'regions': regions,
      'data_usage_description': dataUsageDescription,
      'data_usage_description_zh': dataUsageDescriptionZh,
    };
  }

  static DataCategory _parseCategory(String? value) {
    if (value == null) return DataCategory.other;
    final normalized = value.toLowerCase();
    // Handle snake_case from backend (e.g., "food_delivery" -> "fooddelivery")
    final withoutUnderscore = normalized.replaceAll('_', '');
    return DataCategory.values.firstWhere(
      (e) => e.name.toLowerCase() == withoutUnderscore,
      orElse: () => DataCategory.other,
    );
  }

  static AuthType _parseAuthType(String? value) {
    if (value == null) return AuthType.oauth2;
    final normalized = value.toLowerCase().replaceAll('_', '');
    // Handle api_key -> apikey
    return AuthType.values.firstWhere(
      (e) => e.name.toLowerCase() == normalized,
      orElse: () => AuthType.oauth2,
    );
  }
}
