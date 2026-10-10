import 'package:equatable/equatable.dart';
import 'poi.dart';

/// Secretary recommendation entity - AI-generated recommendations for a trip
class SecretaryRecommendation extends Equatable {
  final String id;
  final String? tripId;
  final String title;
  final String reason;
  final List<POI> recommendedPOIs;
  final DateTime createdAt;

  const SecretaryRecommendation({
    required this.id,
    this.tripId,
    required this.title,
    required this.reason,
    this.recommendedPOIs = const [],
    required this.createdAt,
  });

  /// Whether this recommendation is linked to a specific trip
  bool get isTripSpecific => tripId != null;

  /// Number of POIs in this recommendation
  int get poiCount => recommendedPOIs.length;

  /// Create a copy with updated fields
  SecretaryRecommendation copyWith({
    String? id,
    String? tripId,
    String? title,
    String? reason,
    List<POI>? recommendedPOIs,
    DateTime? createdAt,
  }) {
    return SecretaryRecommendation(
      id: id ?? this.id,
      tripId: tripId ?? this.tripId,
      title: title ?? this.title,
      reason: reason ?? this.reason,
      recommendedPOIs: recommendedPOIs ?? this.recommendedPOIs,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  @override
  List<Object?> get props => [
        id,
        tripId,
        title,
        reason,
        recommendedPOIs,
        createdAt,
      ];
}
