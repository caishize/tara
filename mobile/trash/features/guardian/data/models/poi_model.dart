import '../../domain/entities/poi.dart';
import '../../domain/entities/poi_category.dart';

/// POI model for JSON serialization
class POIModel extends POI {
  const POIModel({
    required super.id,
    required super.name,
    required super.category,
    required super.address,
    required super.rating,
    required super.reviewCount,
    super.priceRange,
    super.distance,
    super.tags = const [],
    super.imageUrls = const [],
    super.openingHours,
    super.phone,
    super.secretaryReview,
  });

  factory POIModel.fromJson(Map<String, dynamic> json) {
    return POIModel(
      id: json['id']?.toString() ?? '',
      name: json['name'] as String? ?? '',
      category: _parseCategory(json['category'] as String?),
      address: json['address'] as String? ?? '',
      rating: (json['rating'] as num?)?.toDouble() ?? 0.0,
      reviewCount: json['review_count'] as int? ?? 0,
      priceRange: json['price_range'] as String?,
      distance: (json['distance'] as num?)?.toDouble(),
      tags: (json['tags'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
      imageUrls: (json['image_urls'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
      openingHours: json['opening_hours'] as String?,
      phone: json['phone'] as String?,
      secretaryReview: json['secretary_review'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'category': category.name,
      'address': address,
      'rating': rating,
      'review_count': reviewCount,
      'price_range': priceRange,
      'distance': distance,
      'tags': tags,
      'image_urls': imageUrls,
      'opening_hours': openingHours,
      'phone': phone,
      'secretary_review': secretaryReview,
    };
  }

  static POICategory _parseCategory(String? category) {
    switch (category?.toLowerCase()) {
      case 'food':
        return POICategory.food;
      case 'attraction':
        return POICategory.attraction;
      case 'hotel':
        return POICategory.hotel;
      case 'activity':
        return POICategory.activity;
      default:
        return POICategory.food;
    }
  }

  /// Convert POI entity to model
  factory POIModel.fromEntity(POI poi) {
    return POIModel(
      id: poi.id,
      name: poi.name,
      category: poi.category,
      address: poi.address,
      rating: poi.rating,
      reviewCount: poi.reviewCount,
      priceRange: poi.priceRange,
      distance: poi.distance,
      tags: poi.tags,
      imageUrls: poi.imageUrls,
      openingHours: poi.openingHours,
      phone: poi.phone,
      secretaryReview: poi.secretaryReview,
    );
  }
}
