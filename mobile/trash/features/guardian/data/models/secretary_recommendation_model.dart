import '../../domain/entities/secretary_recommendation.dart';
import 'poi_model.dart';

/// Secretary recommendation model for JSON serialization
class SecretaryRecommendationModel extends SecretaryRecommendation {
  const SecretaryRecommendationModel({
    required super.id,
    super.tripId,
    required super.title,
    required super.reason,
    super.recommendedPOIs = const [],
    required super.createdAt,
  });

  factory SecretaryRecommendationModel.fromJson(Map<String, dynamic> json) {
    final pois = (json['recommended_pois'] as List<dynamic>?)
            ?.map((e) => POIModel.fromJson(e as Map<String, dynamic>))
            .toList() ??
        const [];

    return SecretaryRecommendationModel(
      id: json['id']?.toString() ?? '',
      tripId: json['trip_id'] as String?,
      title: json['title'] as String? ?? '',
      reason: json['reason'] as String? ?? '',
      recommendedPOIs: pois,
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'] as String)
          : DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'trip_id': tripId,
      'title': title,
      'reason': reason,
      'recommended_pois': recommendedPOIs
          .map((poi) => POIModel.fromEntity(poi).toJson())
          .toList(),
      'created_at': createdAt.toIso8601String(),
    };
  }

  /// Convert entity to model
  factory SecretaryRecommendationModel.fromEntity(
      SecretaryRecommendation recommendation) {
    return SecretaryRecommendationModel(
      id: recommendation.id,
      tripId: recommendation.tripId,
      title: recommendation.title,
      reason: recommendation.reason,
      recommendedPOIs: recommendation.recommendedPOIs,
      createdAt: recommendation.createdAt,
    );
  }
}
