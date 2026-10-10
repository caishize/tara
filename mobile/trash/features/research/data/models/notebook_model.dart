import '../../domain/entities/notebook.dart';

/// Model for NotebookSource JSON serialization
class NotebookSourceModel extends NotebookSource {
  const NotebookSourceModel({
    required super.id,
    required super.notebookId,
    required super.type,
    super.title,
    super.originalUrl,
    super.originalContent,
    super.hasExtractedText,
    super.summary,
    super.metadata,
    super.extractionStatus,
    super.extractionError,
    required super.createdAt,
    required super.updatedAt,
  });

  factory NotebookSourceModel.fromJson(Map<String, dynamic> json) {
    return NotebookSourceModel(
      id: json['id'] as String,
      notebookId: json['notebook_id'] as String,
      type: _parseSourceType(json['type'] as String?),
      title: json['title'] as String?,
      originalUrl: json['original_url'] as String?,
      originalContent: json['original_content'] as String?,
      hasExtractedText: json['has_extracted_text'] as bool? ?? false,
      summary: json['summary'] as String?,
      metadata: (json['metadata'] as Map<String, dynamic>?) ?? {},
      extractionStatus: _parseExtractionStatus(json['extraction_status'] as String?),
      extractionError: json['extraction_error'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'notebook_id': notebookId,
      'type': type.name,
      'title': title,
      'original_url': originalUrl,
      'original_content': originalContent,
      'has_extracted_text': hasExtractedText,
      'summary': summary,
      'metadata': metadata,
      'extraction_status': extractionStatus.name,
      'extraction_error': extractionError,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }

  static SourceType _parseSourceType(String? type) {
    switch (type) {
      case 'url':
        return SourceType.url;
      case 'text':
        return SourceType.text;
      case 'file':
        return SourceType.file;
      default:
        return SourceType.text;
    }
  }

  static ExtractionStatus _parseExtractionStatus(String? status) {
    switch (status) {
      case 'pending':
        return ExtractionStatus.pending;
      case 'processing':
        return ExtractionStatus.processing;
      case 'completed':
        return ExtractionStatus.completed;
      case 'failed':
        return ExtractionStatus.failed;
      default:
        return ExtractionStatus.pending;
    }
  }
}

/// Model for ChatSource JSON serialization
class ChatSourceModel extends ChatSource {
  const ChatSourceModel({
    required super.id,
    required super.title,
    super.type,
    super.url,
  });

  factory ChatSourceModel.fromJson(Map<String, dynamic> json) {
    return ChatSourceModel(
      id: json['id'] as String,
      title: json['title'] as String,
      type: json['type'] as String?,
      url: json['url'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'type': type,
      'url': url,
    };
  }
}

/// Model for ChatMessage JSON serialization
class ChatMessageModel extends ChatMessage {
  const ChatMessageModel({
    required super.id,
    required super.role,
    required super.content,
    super.sources,
    required super.timestamp,
  });

  factory ChatMessageModel.fromJson(Map<String, dynamic> json) {
    return ChatMessageModel(
      id: json['id'] as String,
      role: json['role'] as String,
      content: json['content'] as String,
      sources: (json['sources'] as List<dynamic>?)
              ?.map((s) => ChatSourceModel.fromJson(s as Map<String, dynamic>))
              .toList() ??
          [],
      timestamp: DateTime.parse(json['timestamp'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'role': role,
      'content': content,
      'sources': sources
          .map((s) => s is ChatSourceModel
              ? s.toJson()
              : {'id': s.id, 'title': s.title, 'type': s.type, 'url': s.url})
          .toList(),
      'timestamp': timestamp.toIso8601String(),
    };
  }
}

/// Model for Notebook JSON serialization
class NotebookModel extends Notebook {
  const NotebookModel({
    required super.id,
    required super.userId,
    super.familyId,
    required super.name,
    super.description,
    super.icon,
    super.color,
    super.status,
    super.sourceCount,
    super.totalSources,
    super.sources,
    super.chatHistory,
    required super.createdAt,
    required super.updatedAt,
  });

  factory NotebookModel.fromJson(Map<String, dynamic> json) {
    return NotebookModel(
      id: json['id'] as String,
      userId: json['user_id'] as String,
      familyId: json['family_id'] as String?,
      name: json['name'] as String,
      description: json['description'] as String?,
      icon: json['icon'] as String? ?? '📚',
      color: json['color'] as String? ?? '#6366F1',
      status: json['status'] as String? ?? 'active',
      sourceCount: _parseSourceCount(json['source_count']),
      totalSources: json['total_sources'] as int? ?? 0,
      sources: (json['sources'] as List<dynamic>?)
              ?.map((s) => NotebookSourceModel.fromJson(s as Map<String, dynamic>))
              .toList() ??
          [],
      chatHistory: (json['chat_history'] as List<dynamic>?)
              ?.map((m) => ChatMessageModel.fromJson(m as Map<String, dynamic>))
              .toList() ??
          [],
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'user_id': userId,
      'family_id': familyId,
      'name': name,
      'description': description,
      'icon': icon,
      'color': color,
      'status': status,
      'source_count': sourceCount,
      'total_sources': totalSources,
      'sources': sources
          .map((s) => s is NotebookSourceModel
              ? s.toJson()
              : NotebookSourceModel(
                  id: s.id,
                  notebookId: s.notebookId,
                  type: s.type,
                  title: s.title,
                  originalUrl: s.originalUrl,
                  originalContent: s.originalContent,
                  hasExtractedText: s.hasExtractedText,
                  summary: s.summary,
                  metadata: s.metadata,
                  extractionStatus: s.extractionStatus,
                  extractionError: s.extractionError,
                  createdAt: s.createdAt,
                  updatedAt: s.updatedAt,
                ).toJson())
          .toList(),
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }

  static Map<String, int> _parseSourceCount(dynamic value) {
    if (value == null) return {'url': 0, 'text': 0, 'file': 0};
    if (value is Map<String, dynamic>) {
      return {
        'url': value['url'] as int? ?? 0,
        'text': value['text'] as int? ?? 0,
        'file': value['file'] as int? ?? 0,
      };
    }
    return {'url': 0, 'text': 0, 'file': 0};
  }
}
