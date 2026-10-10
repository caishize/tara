/// Summary of a related memory linked to a trip or event.
class RelatedMemoryModel {
  final String id;
  final String summary;
  final String? memoryType;
  final DateTime? createdAt;

  const RelatedMemoryModel({
    required this.id,
    required this.summary,
    this.memoryType,
    this.createdAt,
  });

  factory RelatedMemoryModel.fromJson(Map<String, dynamic> json) {
    return RelatedMemoryModel(
      id: json['id'] as String? ?? '',
      summary: json['summary'] as String? ?? '',
      memoryType: json['memory_type'] as String?,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'] as String)
          : null,
    );
  }

  /// Display label for the memory type.
  String get categoryLabel {
    switch (memoryType) {
      case 'preference':
        return '偏好';
      case 'experience':
        return '经历';
      case 'relationship':
        return '关系';
      case 'fact':
        return '事实';
      case 'habit':
        return '习惯';
      default:
        return '记忆';
    }
  }

  String get categoryIcon {
    switch (memoryType) {
      case 'preference':
        return '\u{1F4A1}';
      case 'experience':
        return '\u{1F4DD}';
      case 'relationship':
        return '\u{2764}\u{FE0F}';
      case 'fact':
        return '\u{1F4CB}';
      case 'habit':
        return '\u{1F504}';
      default:
        return '\u{1F9E0}';
    }
  }
}
