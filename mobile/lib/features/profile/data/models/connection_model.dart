class UserConnection {
  final String id;
  final String providerType;
  final String providerName;
  final String displayName;
  final String? iconUrl;
  final String connectionStatus;
  final List<String> scopes;
  final DateTime? lastSyncAt;
  final String? lastError;
  final String? syncFrequency;

  const UserConnection({
    required this.id,
    required this.providerType,
    required this.providerName,
    required this.displayName,
    this.iconUrl,
    required this.connectionStatus,
    required this.scopes,
    this.lastSyncAt,
    this.lastError,
    this.syncFrequency,
  });

  factory UserConnection.fromJson(Map<String, dynamic> json) {
    return UserConnection(
      id: json['id'] as String,
      providerType: json['provider_type'] as String? ?? '',
      providerName: json['provider_name'] as String? ?? '',
      displayName: json['display_name'] as String? ?? '',
      iconUrl: json['icon_url'] as String?,
      connectionStatus: json['connection_status'] as String? ?? 'disconnected',
      scopes: (json['scopes'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
      lastSyncAt: json['last_sync_at'] != null
          ? DateTime.parse(json['last_sync_at'] as String)
          : null,
      lastError: json['last_error'] as String?,
      syncFrequency: json['sync_frequency'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'provider_type': providerType,
      'provider_name': providerName,
      'display_name': displayName,
      if (iconUrl != null) 'icon_url': iconUrl,
      'connection_status': connectionStatus,
      'scopes': scopes,
      if (lastSyncAt != null) 'last_sync_at': lastSyncAt!.toIso8601String(),
      if (lastError != null) 'last_error': lastError,
      if (syncFrequency != null) 'sync_frequency': syncFrequency,
    };
  }

  bool get isConnected => connectionStatus == 'connected';
  bool get hasError => connectionStatus == 'error';
}

class AvailableProvider {
  final String providerName;
  final String providerType;
  final String displayName;
  final String description;
  final String authType;
  final List<String> defaultScopes;
  final String? iconUrl;
  final String category;

  const AvailableProvider({
    required this.providerName,
    required this.providerType,
    required this.displayName,
    required this.description,
    required this.authType,
    required this.defaultScopes,
    this.iconUrl,
    required this.category,
  });

  factory AvailableProvider.fromJson(Map<String, dynamic> json) {
    return AvailableProvider(
      providerName: json['provider_name'] as String? ?? '',
      providerType: json['provider_type'] as String? ?? '',
      displayName: json['display_name'] as String? ?? '',
      description: json['description'] as String? ?? '',
      authType: json['auth_type'] as String? ?? 'oauth2',
      defaultScopes: (json['default_scopes'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
      iconUrl: json['icon_url'] as String?,
      category: json['category'] as String? ?? json['provider_type'] as String? ?? 'other',
    );
  }
}
