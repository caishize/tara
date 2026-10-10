import 'package:equatable/equatable.dart';

/// Source type in a notebook
enum SourceType {
  url,
  text,
  file;

  String get displayName {
    switch (this) {
      case SourceType.url:
        return '网页链接';
      case SourceType.text:
        return '文本笔记';
      case SourceType.file:
        return '文件';
    }
  }

  String get icon {
    switch (this) {
      case SourceType.url:
        return '🔗';
      case SourceType.text:
        return '📝';
      case SourceType.file:
        return '📄';
    }
  }
}

/// Extraction status for sources
enum ExtractionStatus {
  pending,
  processing,
  completed,
  failed;

  String get displayName {
    switch (this) {
      case ExtractionStatus.pending:
        return '等待处理';
      case ExtractionStatus.processing:
        return '正在提取';
      case ExtractionStatus.completed:
        return '提取完成';
      case ExtractionStatus.failed:
        return '提取失败';
    }
  }
}

/// Summary format options
enum SummaryFormat {
  summary,
  detailed,
  outline,
  faq,
  comparison;

  String get displayName {
    switch (this) {
      case SummaryFormat.summary:
        return '简要摘要';
      case SummaryFormat.detailed:
        return '详细摘要';
      case SummaryFormat.outline:
        return '大纲形式';
      case SummaryFormat.faq:
        return '问答形式';
      case SummaryFormat.comparison:
        return '对比分析';
    }
  }

  String get description {
    switch (this) {
      case SummaryFormat.summary:
        return '1-2段简洁的核心要点总结';
      case SummaryFormat.detailed:
        return '多段落详细分析';
      case SummaryFormat.outline:
        return '结构化的要点列表';
      case SummaryFormat.faq:
        return '常见问题及答案';
      case SummaryFormat.comparison:
        return '多个主题的对比表格';
    }
  }
}

/// A source within a notebook
class NotebookSource extends Equatable {
  final String id;
  final String notebookId;
  final SourceType type;
  final String? title;
  final String? originalUrl;
  final String? originalContent;
  final bool hasExtractedText;
  final String? summary;
  final Map<String, dynamic> metadata;
  final ExtractionStatus extractionStatus;
  final String? extractionError;
  final DateTime createdAt;
  final DateTime updatedAt;

  const NotebookSource({
    required this.id,
    required this.notebookId,
    required this.type,
    this.title,
    this.originalUrl,
    this.originalContent,
    this.hasExtractedText = false,
    this.summary,
    this.metadata = const {},
    this.extractionStatus = ExtractionStatus.pending,
    this.extractionError,
    required this.createdAt,
    required this.updatedAt,
  });

  String get displayTitle {
    if (title != null && title!.isNotEmpty) return title!;
    if (originalUrl != null) return originalUrl!;
    if (originalContent != null && originalContent!.length > 50) {
      return '${originalContent!.substring(0, 50)}...';
    }
    return originalContent ?? 'Untitled';
  }

  @override
  List<Object?> get props => [
        id,
        notebookId,
        type,
        title,
        originalUrl,
        originalContent,
        hasExtractedText,
        summary,
        extractionStatus,
        extractionError,
        createdAt,
        updatedAt,
      ];
}

/// Chat message in notebook
class ChatMessage extends Equatable {
  final String id;
  final String role; // 'user' or 'assistant'
  final String content;
  final List<ChatSource> sources;
  final DateTime timestamp;

  const ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    this.sources = const [],
    required this.timestamp,
  });

  bool get isUser => role == 'user';
  bool get isAssistant => role == 'assistant';

  @override
  List<Object?> get props => [id, role, content, sources, timestamp];
}

/// Source reference in chat response
class ChatSource extends Equatable {
  final String id;
  final String title;
  final String? type;
  final String? url;

  const ChatSource({
    required this.id,
    required this.title,
    this.type,
    this.url,
  });

  @override
  List<Object?> get props => [id, title, type, url];
}

/// Notebook entity (knowledge base)
class Notebook extends Equatable {
  final String id;
  final String userId;
  final String? familyId;
  final String name;
  final String? description;
  final String icon;
  final String color;
  final String status;
  final Map<String, int> sourceCount;
  final int totalSources;
  final List<NotebookSource> sources;
  final List<ChatMessage> chatHistory;
  final DateTime createdAt;
  final DateTime updatedAt;

  const Notebook({
    required this.id,
    required this.userId,
    this.familyId,
    required this.name,
    this.description,
    this.icon = '📚',
    this.color = '#6366F1',
    this.status = 'active',
    this.sourceCount = const {'url': 0, 'text': 0, 'file': 0},
    this.totalSources = 0,
    this.sources = const [],
    this.chatHistory = const [],
    required this.createdAt,
    required this.updatedAt,
  });

  bool get isEmpty => totalSources == 0;
  bool get hasContent => totalSources > 0;

  int get urlCount => sourceCount['url'] ?? 0;
  int get textCount => sourceCount['text'] ?? 0;
  int get fileCount => sourceCount['file'] ?? 0;

  Notebook copyWith({
    String? id,
    String? userId,
    String? familyId,
    String? name,
    String? description,
    String? icon,
    String? color,
    String? status,
    Map<String, int>? sourceCount,
    int? totalSources,
    List<NotebookSource>? sources,
    List<ChatMessage>? chatHistory,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return Notebook(
      id: id ?? this.id,
      userId: userId ?? this.userId,
      familyId: familyId ?? this.familyId,
      name: name ?? this.name,
      description: description ?? this.description,
      icon: icon ?? this.icon,
      color: color ?? this.color,
      status: status ?? this.status,
      sourceCount: sourceCount ?? this.sourceCount,
      totalSources: totalSources ?? this.totalSources,
      sources: sources ?? this.sources,
      chatHistory: chatHistory ?? this.chatHistory,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  List<Object?> get props => [
        id,
        userId,
        familyId,
        name,
        description,
        icon,
        color,
        status,
        sourceCount,
        totalSources,
        sources,
        chatHistory,
        createdAt,
        updatedAt,
      ];
}
