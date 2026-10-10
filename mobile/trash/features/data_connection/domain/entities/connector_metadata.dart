import 'package:equatable/equatable.dart';

/// Category of data connector
enum DataCategory {
  calendar,
  email,
  ecommerce,
  foodDelivery,
  social,
  health,
  finance,
  location,
  travel,
  productivity,
  other;

  String get displayName {
    switch (this) {
      case DataCategory.calendar:
        return '日历';
      case DataCategory.email:
        return '邮箱';
      case DataCategory.ecommerce:
        return '电商';
      case DataCategory.foodDelivery:
        return '外卖';
      case DataCategory.social:
        return '社交';
      case DataCategory.health:
        return '健康';
      case DataCategory.finance:
        return '财务';
      case DataCategory.location:
        return '位置';
      case DataCategory.travel:
        return '旅行';
      case DataCategory.productivity:
        return '效率工具';
      case DataCategory.other:
        return '其他';
    }
  }

  String get icon {
    switch (this) {
      case DataCategory.calendar:
        return 'calendar_today';
      case DataCategory.email:
        return 'email';
      case DataCategory.ecommerce:
        return 'shopping_cart';
      case DataCategory.foodDelivery:
        return 'restaurant';
      case DataCategory.social:
        return 'people';
      case DataCategory.health:
        return 'favorite';
      case DataCategory.finance:
        return 'account_balance';
      case DataCategory.location:
        return 'location_on';
      case DataCategory.travel:
        return 'flight';
      case DataCategory.productivity:
        return 'construction';
      case DataCategory.other:
        return 'extension';
    }
  }
}

/// Authentication type for connector
enum AuthType {
  oauth2,
  oauth1,
  apiKey,
  mcp,
  basic,
  imap,
  custom;

  String get displayName {
    switch (this) {
      case AuthType.oauth2:
        return 'OAuth 2.0';
      case AuthType.oauth1:
        return 'OAuth 1.0a';
      case AuthType.apiKey:
        return 'API Key';
      case AuthType.mcp:
        return 'MCP';
      case AuthType.basic:
        return 'Basic Auth';
      case AuthType.imap:
        return 'IMAP';
      case AuthType.custom:
        return '自定义';
    }
  }
}

/// Capabilities of a data connector
class ConnectorCapabilities extends Equatable {
  final bool canRead;
  final bool canWrite;
  final bool supportsWebhook;
  final bool supportsIncrementalSync;
  final int? rateLimitPerHour;
  final int? maxHistoricalDays;

  const ConnectorCapabilities({
    this.canRead = true,
    this.canWrite = false,
    this.supportsWebhook = false,
    this.supportsIncrementalSync = false,
    this.rateLimitPerHour,
    this.maxHistoricalDays,
  });

  /// Convert to list of capability strings for display
  List<String> toDisplayList() {
    final list = <String>[];
    if (canRead) list.add('读取数据');
    if (canWrite) list.add('写入数据');
    if (supportsWebhook) list.add('实时推送');
    if (supportsIncrementalSync) list.add('增量同步');
    return list;
  }

  @override
  List<Object?> get props => [
        canRead,
        canWrite,
        supportsWebhook,
        supportsIncrementalSync,
        rateLimitPerHour,
        maxHistoricalDays,
      ];
}

/// Metadata describing a data connector
class ConnectorMetadata extends Equatable {
  final String id;
  final String name;
  final String displayName;
  final String displayNameZh;
  final String description;
  final String descriptionZh;
  final String icon;
  final DataCategory category;
  final AuthType authType;
  final ConnectorCapabilities capabilities;
  final List<String> requiredScopes;
  final List<String> optionalScopes;
  final int dataRetentionDays;
  final bool isAvailable;
  final List<String> regions;
  final String dataUsageDescription;
  final String dataUsageDescriptionZh;

  const ConnectorMetadata({
    required this.id,
    required this.name,
    required this.displayName,
    required this.displayNameZh,
    required this.description,
    required this.descriptionZh,
    required this.icon,
    required this.category,
    required this.authType,
    required this.capabilities,
    required this.requiredScopes,
    required this.optionalScopes,
    required this.dataRetentionDays,
    required this.isAvailable,
    required this.regions,
    required this.dataUsageDescription,
    required this.dataUsageDescriptionZh,
  });

  /// Whether this connector uses MCP (Model Context Protocol)
  bool get isMCP => authType == AuthType.mcp;

  /// Whether this connector uses OAuth
  bool get isOAuth => authType == AuthType.oauth2 || authType == AuthType.oauth1;

  /// Get the auth type description for display
  String get authTypeDescription {
    if (isMCP) {
      return 'MCP 协议连接，支持工具调用和资源访问';
    } else if (isOAuth) {
      return '通过 ${authType.displayName} 安全授权';
    } else {
      return '使用 ${authType.displayName} 认证';
    }
  }

  @override
  List<Object?> get props => [
        id,
        name,
        displayName,
        displayNameZh,
        description,
        descriptionZh,
        icon,
        category,
        authType,
        capabilities,
        requiredScopes,
        optionalScopes,
        dataRetentionDays,
        isAvailable,
        regions,
        dataUsageDescription,
        dataUsageDescriptionZh,
      ];
}
