import 'package:equatable/equatable.dart';

/// 回忆内容类型
enum MemoryContentType {
  photo,
  video,
  note,
}

/// 回忆内容类型扩展
extension MemoryContentTypeExtension on MemoryContentType {
  String get name {
    switch (this) {
      case MemoryContentType.photo:
        return '照片';
      case MemoryContentType.video:
        return '视频';
      case MemoryContentType.note:
        return '笔记';
    }
  }

  String get icon {
    switch (this) {
      case MemoryContentType.photo:
        return '📷';
      case MemoryContentType.video:
        return '🎥';
      case MemoryContentType.note:
        return '📝';
    }
  }

  String get value {
    return toString().split('.').last;
  }

  static MemoryContentType fromString(String value) {
    return MemoryContentType.values.firstWhere(
      (e) => e.value == value,
      orElse: () => MemoryContentType.photo,
    );
  }
}

/// 旅行回忆
class TripMemory extends Equatable {
  final String id;
  final String tripId;
  final MemoryContentType contentType;
  final List<String> contentUrls;
  final String? caption;
  final String? aiCaption;
  final String? location;
  final double? latitude;
  final double? longitude;
  final DateTime? memoryDate;
  final int rating;
  final String? itineraryItemId;
  final List<String> tags;
  final DateTime createdAt;
  final DateTime updatedAt;

  const TripMemory({
    required this.id,
    required this.tripId,
    this.contentType = MemoryContentType.photo,
    this.contentUrls = const [],
    this.caption,
    this.aiCaption,
    this.location,
    this.latitude,
    this.longitude,
    this.memoryDate,
    this.rating = 0,
    this.itineraryItemId,
    this.tags = const [],
    required this.createdAt,
    required this.updatedAt,
  });

  /// 获取主要内容URL
  String? get primaryUrl => contentUrls.isNotEmpty ? contentUrls.first : null;

  /// 是否有位置信息
  bool get hasLocation => location != null && location!.isNotEmpty;

  /// 是否有坐标
  bool get hasCoordinates => latitude != null && longitude != null;

  /// 显示的标题（优先用户标题，其次AI生成）
  String get displayCaption => caption ?? aiCaption ?? '';

  TripMemory copyWith({
    String? id,
    String? tripId,
    MemoryContentType? contentType,
    List<String>? contentUrls,
    String? caption,
    String? aiCaption,
    String? location,
    double? latitude,
    double? longitude,
    DateTime? memoryDate,
    int? rating,
    String? itineraryItemId,
    List<String>? tags,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return TripMemory(
      id: id ?? this.id,
      tripId: tripId ?? this.tripId,
      contentType: contentType ?? this.contentType,
      contentUrls: contentUrls ?? this.contentUrls,
      caption: caption ?? this.caption,
      aiCaption: aiCaption ?? this.aiCaption,
      location: location ?? this.location,
      latitude: latitude ?? this.latitude,
      longitude: longitude ?? this.longitude,
      memoryDate: memoryDate ?? this.memoryDate,
      rating: rating ?? this.rating,
      itineraryItemId: itineraryItemId ?? this.itineraryItemId,
      tags: tags ?? this.tags,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  List<Object?> get props => [
    id, tripId, contentType, contentUrls, caption, aiCaption,
    location, latitude, longitude, memoryDate, rating,
    itineraryItemId, tags, createdAt, updatedAt,
  ];
}

/// 行程反馈
class TripFeedback extends Equatable {
  final String tripId;
  final int rating;
  final String? feedback;
  final DateTime? submittedAt;

  const TripFeedback({
    required this.tripId,
    required this.rating,
    this.feedback,
    this.submittedAt,
  });

  @override
  List<Object?> get props => [tripId, rating, feedback, submittedAt];
}
