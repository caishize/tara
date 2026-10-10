class MemoryItem {
  final String id;
  final String type;
  final String content;
  final String summary;
  final List<MemoryEntity> entities;
  final List<String> tags;
  final int importance;
  final double confidence;
  final String status;
  final DateTime createdAt;
  final String? sourceSessionId;

  const MemoryItem({
    required this.id,
    required this.type,
    required this.content,
    this.summary = '',
    required this.entities,
    this.tags = const [],
    required this.importance,
    this.confidence = 0.8,
    required this.status,
    required this.createdAt,
    this.sourceSessionId,
  });

  /// Parse from backend MemoryResponse JSON.
  /// Backend returns `memory_type` and `entities` as a dict like
  /// {"person": "妈妈", "persons": ["妈妈", "爸爸"], "location": "北京"}.
  factory MemoryItem.fromJson(Map<String, dynamic> json) {
    return MemoryItem(
      id: json['id'] as String,
      type: (json['memory_type'] ?? json['type']) as String? ?? 'general',
      content: json['content'] as String? ?? '',
      summary: json['summary'] as String? ?? '',
      entities: _parseEntities(json['entities']),
      tags: (json['tags'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
      importance: json['importance'] as int? ?? 1,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.8,
      status: json['status'] as String? ?? 'active',
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'] as String)
          : DateTime.now(),
      sourceSessionId: json['source_session_id'] as String?,
    );
  }

  /// Check if a string looks like a UUID (internal ID, not useful to display).
  static final _uuidPattern = RegExp(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
  );
  static bool _isUuid(String value) => _uuidPattern.hasMatch(value.trim());

  /// Backend entities can be either:
  /// - A dict: {"people": ["妈妈"], "locations": ["北京"]}
  /// - A list: [{"name": "妈妈", "type": "person"}]
  /// Handle both formats gracefully.
  static List<MemoryEntity> _parseEntities(dynamic raw) {
    if (raw == null) return [];

    // Already a list of objects
    if (raw is List) {
      return raw
          .map((e) {
            if (e is Map<String, dynamic>) {
              final entity = MemoryEntity.fromJson(e);
              if (_isUuid(entity.name)) return null;
              return entity;
            }
            if (e is String) {
              if (_isUuid(e)) return null;
              return MemoryEntity(name: e);
            }
            return null;
          })
          .whereType<MemoryEntity>()
          .toList();
    }

    // Dict format: {"person": "妈妈", "persons": ["妈妈", "爸爸"], "location": "北京"}
    if (raw is Map<String, dynamic>) {
      final result = <MemoryEntity>[];
      // Track person names to deduplicate across "person", "persons", "name" keys
      final seenPersonNames = <String>{};

      for (final entry in raw.entries) {
        final category = entry.key;
        final values = entry.value;

        // Skip internal/meta keys, ID references, and status fields
        if (category.startsWith('_')) continue;
        if (category.endsWith('_id') || category.endsWith('_ids')) continue;
        if (category == 'id' || category == 'status') continue;

        // Determine if this is a person-type key
        final isPersonKey = category == 'person' || category == 'persons' || category == 'people';

        if (values is List) {
          for (final v in values) {
            final name = v.toString().trim();
            if (name.isEmpty || _isUuid(name)) continue;
            if (isPersonKey) {
              if (seenPersonNames.contains(name)) continue;
              seenPersonNames.add(name);
            }
            result.add(MemoryEntity(name: name, type: category));
          }
        } else if (values is String) {
          final name = values.trim();
          if (name.isEmpty || _isUuid(name)) continue;

          // "name" key typically holds the actual name of a person already
          // listed under "person" — merge into person type
          if (category == 'name') {
            if (!seenPersonNames.contains(name)) {
              seenPersonNames.add(name);
              result.add(MemoryEntity(name: name, type: 'person'));
            }
          } else {
            if (isPersonKey) {
              // "person" field may contain comma-separated names
              for (final part in name.split(RegExp(r'[,，、]'))) {
                final trimmed = part.trim();
                if (trimmed.isEmpty || seenPersonNames.contains(trimmed)) continue;
                seenPersonNames.add(trimmed);
                result.add(MemoryEntity(name: trimmed, type: category));
              }
            } else {
              result.add(MemoryEntity(name: name, type: category));
            }
          }
        }
      }
      return result;
    }

    return [];
  }

  /// Person-type entities only (for "关联人物" section).
  List<MemoryEntity> get personEntities => entities
      .where((e) =>
          e.type == 'person' ||
          e.type == 'persons' ||
          e.type == 'people' ||
          e.type == null)
      .toList();

  /// Non-person entities (location, time, emotion, etc.).
  List<MemoryEntity> get contextEntities => entities
      .where((e) =>
          e.type != null &&
          e.type != 'person' &&
          e.type != 'persons' &&
          e.type != 'people' &&
          e.type != 'name' &&
          !e.type!.startsWith('_'))
      .toList();

  String get typeLabel {
    switch (type) {
      case 'preference':
        return '\u{1f31f} \u504f\u597d';
      case 'emotion':
        return '\u{1f4ad} \u60c5\u7eea';
      case 'relationship':
        return '\u{1f91d} \u5173\u7cfb';
      case 'life_event':
        return '\u{1f4c5} \u751f\u6d3b\u4e8b\u4ef6';
      case 'plan':
        return '\u{1f3af} \u8ba1\u5212';
      case 'schedule':
        return '\u{1f5d3} \u65e5\u7a0b';
      case 'work':
        return '\u{1f4bc} \u5de5\u4f5c';
      case 'health':
        return '\u{2764} \u5065\u5eb7';
      case 'location':
        return '\u{1f4cd} \u5730\u70b9';
      case 'favor':
        return '\u{1f91e} \u4eba\u60c5';
      case 'general':
        return '\u{1f4cb} \u5176\u4ed6';
      default:
        return '\u{1f4cb} \u5176\u4ed6';
    }
  }
}

class MemoryEntity {
  final String name;
  final String? type;

  const MemoryEntity({required this.name, this.type});

  factory MemoryEntity.fromJson(Map<String, dynamic> json) {
    return MemoryEntity(
      name: json['name'] as String? ?? '',
      type: json['type'] as String?,
    );
  }
}

class InsightItem {
  final String id;
  final String type;
  final String title;
  final String content;
  final int priority;
  final String urgency;
  final String status;
  final List<String> relatedMemoryIds;
  final List<String> actionOptions;
  final DateTime createdAt;

  const InsightItem({
    required this.id,
    required this.type,
    this.title = '',
    required this.content,
    required this.priority,
    this.urgency = 'normal',
    required this.status,
    this.relatedMemoryIds = const [],
    this.actionOptions = const [],
    required this.createdAt,
  });

  /// Parse from backend InsightResponse JSON.
  /// Backend returns `insight_type`, `related_memory_ids`, `action_options`.
  factory InsightItem.fromJson(Map<String, dynamic> json) {
    return InsightItem(
      id: json['id'] as String,
      type: (json['insight_type'] ?? json['type']) as String? ?? 'observation',
      title: json['title'] as String? ?? '',
      content: json['content'] as String? ?? '',
      priority: json['priority'] as int? ?? 1,
      urgency: json['urgency'] as String? ?? 'normal',
      status: json['status'] as String? ?? 'pending',
      relatedMemoryIds: (json['related_memory_ids'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
      actionOptions: (json['action_options'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'] as String)
          : DateTime.now(),
    );
  }

  String get typeIcon {
    switch (type) {
      case 'suggestion':
        return '\u{1f4a1}';
      case 'goal':
        return '\u{1f3af}';
      case 'observation':
        return '\u{1f440}';
      case 'connection':
        return '\u{1f517}';
      default:
        return '\u{1f4a1}';
    }
  }
}

/// Response wrapper for paginated memory list.
/// Backend returns: {"memories": [...], "total": N}
class MemoryListResponse {
  final List<MemoryItem> items;
  final int total;
  final int offset;
  final int limit;

  const MemoryListResponse({
    required this.items,
    required this.total,
    this.offset = 0,
    this.limit = 20,
  });

  factory MemoryListResponse.fromJson(
    Map<String, dynamic> json, {
    int requestOffset = 0,
    int requestLimit = 20,
  }) {
    // Backend returns "memories" key
    final rawList =
        (json['memories'] ?? json['items']) as List<dynamic>? ?? [];
    return MemoryListResponse(
      items: rawList
          .map((e) => MemoryItem.fromJson(e as Map<String, dynamic>))
          .toList(),
      total: json['total'] as int? ?? 0,
      offset: requestOffset,
      limit: requestLimit,
    );
  }

  bool get hasMore => offset + items.length < total;
}
