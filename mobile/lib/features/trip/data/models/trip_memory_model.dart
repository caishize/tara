import '../../../../core/utils/timezone_utils.dart';

import '../../domain/entities/trip_memory.dart';

class TripMemoryModel extends TripMemory {
  const TripMemoryModel({
    required super.id,
    required super.tripId,
    super.contentType,
    super.contentUrls,
    super.caption,
    super.aiCaption,
    super.location,
    super.latitude,
    super.longitude,
    super.memoryDate,
    super.rating,
    super.itineraryItemId,
    super.tags,
    required super.createdAt,
    required super.updatedAt,
  });

  factory TripMemoryModel.fromJson(Map<String, dynamic> json) {
    return TripMemoryModel(
      id: json['memory_id']?.toString() ?? json['id']?.toString() ?? '',
      tripId: json['trip_id']?.toString() ?? '',
      contentType: _parseContentType(json['content_type']),
      contentUrls: (json['content_urls'] as List?)?.cast<String>() ??
          (json['content_url'] != null ? [json['content_url'] as String] : []),
      caption: json['caption'],
      aiCaption: json['ai_caption'],
      location: json['location'],
      latitude: json['latitude']?.toDouble(),
      longitude: json['longitude']?.toDouble(),
      memoryDate: json['memory_date'] != null
          ? TimezoneUtils.parseApiTime(json['memory_date'])
          : null,
      rating: json['rating'] ?? 0,
      itineraryItemId: json['itinerary_item_id']?.toString(),
      tags: (json['tags'] as List?)?.cast<String>() ?? [],
      createdAt: json['created_at'] != null
          ? TimezoneUtils.parseApiTime(json['created_at'])
          : DateTime.now().toUtc(),
      updatedAt: json['updated_at'] != null
          ? TimezoneUtils.parseApiTime(json['updated_at'])
          : DateTime.now().toUtc(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'memory_id': id,
      'trip_id': tripId,
      'content_type': contentType.value,
      'content_urls': contentUrls,
      'caption': caption,
      'ai_caption': aiCaption,
      'location': location,
      'latitude': latitude,
      'longitude': longitude,
      'memory_date': memoryDate != null ? TimezoneUtils.toApiTime(memoryDate!) : null,
      'rating': rating,
      'itinerary_item_id': itineraryItemId,
      'tags': tags,
      'created_at': TimezoneUtils.toApiTime(createdAt),
      'updated_at': TimezoneUtils.toApiTime(updatedAt),
    };
  }

  static MemoryContentType _parseContentType(String? type) {
    if (type == null) return MemoryContentType.photo;
    return MemoryContentType.values.firstWhere(
      (t) => t.value == type,
      orElse: () => MemoryContentType.photo,
    );
  }

  static TripMemoryModel fromEntity(TripMemory entity) {
    return TripMemoryModel(
      id: entity.id,
      tripId: entity.tripId,
      contentType: entity.contentType,
      contentUrls: entity.contentUrls,
      caption: entity.caption,
      aiCaption: entity.aiCaption,
      location: entity.location,
      latitude: entity.latitude,
      longitude: entity.longitude,
      memoryDate: entity.memoryDate,
      rating: entity.rating,
      itineraryItemId: entity.itineraryItemId,
      tags: entity.tags,
      createdAt: entity.createdAt,
      updatedAt: entity.updatedAt,
    );
  }
}

class TripFeedbackModel extends TripFeedback {
  const TripFeedbackModel({
    required super.tripId,
    required super.rating,
    super.feedback,
    super.submittedAt,
  });

  factory TripFeedbackModel.fromJson(Map<String, dynamic> json) {
    return TripFeedbackModel(
      tripId: json['trip_id']?.toString() ?? '',
      rating: json['rating'] ?? 0,
      feedback: json['feedback'],
      submittedAt: json['submitted_at'] != null
          ? TimezoneUtils.parseApiTime(json['submitted_at'])
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'trip_id': tripId,
      'rating': rating,
      if (feedback != null) 'feedback': feedback,
      if (submittedAt != null) 'submitted_at': TimezoneUtils.toApiTime(submittedAt!),
    };
  }

  static TripFeedbackModel fromEntity(TripFeedback entity) {
    return TripFeedbackModel(
      tripId: entity.tripId,
      rating: entity.rating,
      feedback: entity.feedback,
      submittedAt: entity.submittedAt,
    );
  }
}
