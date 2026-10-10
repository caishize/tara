import '../../domain/entities/research_session.dart';

class ResearchCandidateModel extends ResearchCandidate {
  const ResearchCandidateModel({
    required super.id,
    required super.title,
    required super.url,
    required super.snippet,
    super.source,
    super.category,
    super.score,
    super.imageUrl,
  });

  factory ResearchCandidateModel.fromJson(Map<String, dynamic> json) {
    return ResearchCandidateModel(
      id: json['id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      url: json['url'] as String? ?? '',
      snippet: json['snippet'] as String? ?? '',
      source: json['source'] as String?,
      category: json['category'] as String?,
      score: (json['score'] as num?)?.toDouble() ?? 0.0,
      imageUrl: json['image_url'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'url': url,
      'snippet': snippet,
      'source': source,
      'category': category,
      'score': score,
      'image_url': imageUrl,
    };
  }
}

class ManualItemModel extends ManualItem {
  const ManualItemModel({
    required super.id,
    required super.type,
    required super.content,
    super.title,
    super.extractedContent,
    required super.createdAt,
  });

  factory ManualItemModel.fromJson(Map<String, dynamic> json) {
    final createdAtStr = json['created_at'] as String?;
    return ManualItemModel(
      id: json['id'] as String? ?? '',
      type: json['type'] as String? ?? 'note',
      content: json['content'] as String? ?? '',
      title: json['title'] as String?,
      extractedContent: json['extracted_content'] as String?,
      createdAt: createdAtStr != null ? DateTime.parse(createdAtStr) : DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'type': type,
      'content': content,
      'title': title,
      'extracted_content': extractedContent,
      'created_at': createdAt.toIso8601String(),
    };
  }
}

class SynthesisSourceModel extends SynthesisSource {
  const SynthesisSourceModel({
    required super.title,
    required super.url,
  });

  factory SynthesisSourceModel.fromJson(Map<String, dynamic> json) {
    return SynthesisSourceModel(
      title: json['title'] as String? ?? '',
      url: json['url'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'title': title,
      'url': url,
    };
  }
}

class SynthesisResultModel extends SynthesisResult {
  const SynthesisResultModel({
    required super.format,
    required super.content,
    required super.sources,
    required super.generatedAt,
  });

  factory SynthesisResultModel.fromJson(Map<String, dynamic> json) {
    final generatedAtStr = json['generated_at'] as String?;
    return SynthesisResultModel(
      format: json['format'] as String? ?? 'markdown',
      content: json['content'] as String? ?? '',
      sources: (json['sources'] as List<dynamic>?)
              ?.map((e) => SynthesisSourceModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      generatedAt: generatedAtStr != null ? DateTime.parse(generatedAtStr) : DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'format': format,
      'content': content,
      'sources': sources.map((e) => (e as SynthesisSourceModel).toJson()).toList(),
      'generated_at': generatedAt.toIso8601String(),
    };
  }
}

class ResearchSessionModel extends ResearchSession {
  const ResearchSessionModel({
    required super.id,
    required super.topic,
    required super.scenario,
    required super.status,
    super.candidates,
    super.manualItems,
    super.selectedIds,
    super.synthesis,
    required super.createdAt,
    required super.updatedAt,
  });

  factory ResearchSessionModel.fromJson(Map<String, dynamic> json) {
    // Handle null safety for required fields
    final id = json['id'] as String? ?? '';
    final topic = json['topic'] as String? ?? '';
    final createdAtStr = json['created_at'] as String?;
    final updatedAtStr = json['updated_at'] as String?;

    if (id.isEmpty) {
      throw FormatException('Missing required field: id');
    }

    return ResearchSessionModel(
      id: id,
      topic: topic,
      scenario: _parseScenario(json['scenario'] as String?),
      status: _parseStatus(json['status'] as String?),
      candidates: (json['candidates'] as List<dynamic>?)
              ?.map((e) => ResearchCandidateModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      manualItems: (json['manual_items'] as List<dynamic>?)
              ?.map((e) => ManualItemModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      selectedIds:
          (json['selected_ids'] as List<dynamic>?)?.map((e) => e as String).toList() ?? [],
      synthesis: json['synthesis'] != null
          ? SynthesisResultModel.fromJson(json['synthesis'] as Map<String, dynamic>)
          : null,
      createdAt: createdAtStr != null ? DateTime.parse(createdAtStr) : DateTime.now(),
      updatedAt: updatedAtStr != null ? DateTime.parse(updatedAtStr) : DateTime.now(),
    );
  }

  static ResearchScenario _parseScenario(String? value) {
    switch (value) {
      case 'gift':
        return ResearchScenario.gift;
      case 'travel':
        return ResearchScenario.travel;
      case 'holiday':
        return ResearchScenario.holiday;
      case 'health':
        return ResearchScenario.health;
      default:
        return ResearchScenario.general;
    }
  }

  static SessionStatus _parseStatus(String? value) {
    switch (value) {
      case 'searching':
        return SessionStatus.searching;
      case 'synthesizing':
        return SessionStatus.synthesizing;
      case 'completed':
        return SessionStatus.completed;
      default:
        return SessionStatus.ready;
    }
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'topic': topic,
      'scenario': scenario.name,
      'status': status.name,
      'candidates': candidates
          .map((e) => (e as ResearchCandidateModel).toJson())
          .toList(),
      'manual_items': manualItems
          .map((e) => (e as ManualItemModel).toJson())
          .toList(),
      'selected_ids': selectedIds,
      'synthesis': synthesis != null
          ? (synthesis as SynthesisResultModel).toJson()
          : null,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }
}
