import 'package:equatable/equatable.dart';

/// Research scenario types
enum ResearchScenario {
  gift,
  travel,
  holiday,
  health,
  general;

  String get displayName {
    switch (this) {
      case ResearchScenario.gift:
        return '礼物推荐';
      case ResearchScenario.travel:
        return '旅行攻略';
      case ResearchScenario.holiday:
        return '节日准备';
      case ResearchScenario.health:
        return '健康知识';
      case ResearchScenario.general:
        return '通用搜索';
    }
  }

  String get icon {
    switch (this) {
      case ResearchScenario.gift:
        return '🎁';
      case ResearchScenario.travel:
        return '✈️';
      case ResearchScenario.holiday:
        return '🎉';
      case ResearchScenario.health:
        return '💊';
      case ResearchScenario.general:
        return '🔍';
    }
  }
}

/// Research session status
enum SessionStatus {
  ready,
  searching,
  synthesizing,
  completed;
}

/// Synthesis format
enum SynthesisFormat {
  summary,
  outline,
  detailed;

  String get displayName {
    switch (this) {
      case SynthesisFormat.summary:
        return '摘要';
      case SynthesisFormat.outline:
        return '大纲';
      case SynthesisFormat.detailed:
        return '详细';
    }
  }
}

/// Search candidate from search results
class ResearchCandidate extends Equatable {
  final String id;
  final String title;
  final String url;
  final String snippet;
  final String? source;
  final String? category;
  final double score;
  final String? imageUrl;

  const ResearchCandidate({
    required this.id,
    required this.title,
    required this.url,
    required this.snippet,
    this.source,
    this.category,
    this.score = 0.0,
    this.imageUrl,
  });

  @override
  List<Object?> get props => [id, title, url, snippet, source, category, score, imageUrl];
}

/// Manual item added by user
class ManualItem extends Equatable {
  final String id;
  final String type; // 'note' or 'url'
  final String content;
  final String? title;
  final String? extractedContent;
  final DateTime createdAt;

  const ManualItem({
    required this.id,
    required this.type,
    required this.content,
    this.title,
    this.extractedContent,
    required this.createdAt,
  });

  @override
  List<Object?> get props => [id, type, content, title, extractedContent, createdAt];
}

/// Synthesis result
class SynthesisResult extends Equatable {
  final String format;
  final String content;
  final List<SynthesisSource> sources;
  final DateTime generatedAt;

  const SynthesisResult({
    required this.format,
    required this.content,
    required this.sources,
    required this.generatedAt,
  });

  @override
  List<Object?> get props => [format, content, sources, generatedAt];
}

/// Source reference in synthesis
class SynthesisSource extends Equatable {
  final String title;
  final String url;

  const SynthesisSource({
    required this.title,
    required this.url,
  });

  @override
  List<Object?> get props => [title, url];
}

/// Research session entity
class ResearchSession extends Equatable {
  final String id;
  final String topic;
  final ResearchScenario scenario;
  final SessionStatus status;
  final List<ResearchCandidate> candidates;
  final List<ManualItem> manualItems;
  final List<String> selectedIds;
  final SynthesisResult? synthesis;
  final DateTime createdAt;
  final DateTime updatedAt;

  const ResearchSession({
    required this.id,
    required this.topic,
    required this.scenario,
    required this.status,
    this.candidates = const [],
    this.manualItems = const [],
    this.selectedIds = const [],
    this.synthesis,
    required this.createdAt,
    required this.updatedAt,
  });

  ResearchSession copyWith({
    String? id,
    String? topic,
    ResearchScenario? scenario,
    SessionStatus? status,
    List<ResearchCandidate>? candidates,
    List<ManualItem>? manualItems,
    List<String>? selectedIds,
    SynthesisResult? synthesis,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return ResearchSession(
      id: id ?? this.id,
      topic: topic ?? this.topic,
      scenario: scenario ?? this.scenario,
      status: status ?? this.status,
      candidates: candidates ?? this.candidates,
      manualItems: manualItems ?? this.manualItems,
      selectedIds: selectedIds ?? this.selectedIds,
      synthesis: synthesis ?? this.synthesis,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  List<Object?> get props => [
        id,
        topic,
        scenario,
        status,
        candidates,
        manualItems,
        selectedIds,
        synthesis,
        createdAt,
        updatedAt,
      ];
}
