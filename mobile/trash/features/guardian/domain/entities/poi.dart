import 'package:equatable/equatable.dart';
import 'poi_category.dart';

/// Point of Interest entity
class POI extends Equatable {
  final String id;
  final String name;
  final POICategory category;
  final String address;
  final double rating;
  final int reviewCount;
  final String? priceRange; // ¥, ¥¥, ¥¥¥
  final double? distance; // km
  final List<String> tags; // 热门推荐, 老字号, 可订座
  final List<String> imageUrls;
  final String? openingHours;
  final String? phone;
  final String? secretaryReview; // AI 点评

  const POI({
    required this.id,
    required this.name,
    required this.category,
    required this.address,
    required this.rating,
    required this.reviewCount,
    this.priceRange,
    this.distance,
    this.tags = const [],
    this.imageUrls = const [],
    this.openingHours,
    this.phone,
    this.secretaryReview,
  });

  /// Whether the POI has a secretary review
  bool get hasSecretaryReview =>
      secretaryReview != null && secretaryReview!.isNotEmpty;

  /// Whether the POI has images
  bool get hasImages => imageUrls.isNotEmpty;

  /// Formatted distance string
  String get formattedDistance {
    if (distance == null) return '';
    if (distance! < 1) {
      return '${(distance! * 1000).toInt()}m';
    }
    return '${distance!.toStringAsFixed(1)}km';
  }

  /// Create a copy with updated fields
  POI copyWith({
    String? id,
    String? name,
    POICategory? category,
    String? address,
    double? rating,
    int? reviewCount,
    String? priceRange,
    double? distance,
    List<String>? tags,
    List<String>? imageUrls,
    String? openingHours,
    String? phone,
    String? secretaryReview,
  }) {
    return POI(
      id: id ?? this.id,
      name: name ?? this.name,
      category: category ?? this.category,
      address: address ?? this.address,
      rating: rating ?? this.rating,
      reviewCount: reviewCount ?? this.reviewCount,
      priceRange: priceRange ?? this.priceRange,
      distance: distance ?? this.distance,
      tags: tags ?? this.tags,
      imageUrls: imageUrls ?? this.imageUrls,
      openingHours: openingHours ?? this.openingHours,
      phone: phone ?? this.phone,
      secretaryReview: secretaryReview ?? this.secretaryReview,
    );
  }

  @override
  List<Object?> get props => [
        id,
        name,
        category,
        address,
        rating,
        reviewCount,
        priceRange,
        distance,
        tags,
        imageUrls,
        openingHours,
        phone,
        secretaryReview,
      ];
}
