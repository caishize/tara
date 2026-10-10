import 'package:equatable/equatable.dart';

/// Trending gift category enum matching backend
enum TrendingGiftCategory {
  electronics,
  fashion,
  jewelry,
  cosmetics,
  health,
  books,
  toys,
  sports,
  home,
  food,
  experience,
  custom,
}

/// Extension for category display info
extension TrendingGiftCategoryExtension on TrendingGiftCategory {
  String get displayName {
    switch (this) {
      case TrendingGiftCategory.electronics:
        return '数码电子';
      case TrendingGiftCategory.fashion:
        return '时尚服饰';
      case TrendingGiftCategory.jewelry:
        return '珠宝首饰';
      case TrendingGiftCategory.cosmetics:
        return '美妆护肤';
      case TrendingGiftCategory.health:
        return '健康保健';
      case TrendingGiftCategory.books:
        return '图书文具';
      case TrendingGiftCategory.toys:
        return '玩具游戏';
      case TrendingGiftCategory.sports:
        return '运动户外';
      case TrendingGiftCategory.home:
        return '家居生活';
      case TrendingGiftCategory.food:
        return '美食特产';
      case TrendingGiftCategory.experience:
        return '体验服务';
      case TrendingGiftCategory.custom:
        return '定制礼品';
    }
  }

  String get icon {
    switch (this) {
      case TrendingGiftCategory.electronics:
        return '📱';
      case TrendingGiftCategory.fashion:
        return '👗';
      case TrendingGiftCategory.jewelry:
        return '💎';
      case TrendingGiftCategory.cosmetics:
        return '💄';
      case TrendingGiftCategory.health:
        return '🏥';
      case TrendingGiftCategory.books:
        return '📚';
      case TrendingGiftCategory.toys:
        return '🎮';
      case TrendingGiftCategory.sports:
        return '⚽';
      case TrendingGiftCategory.home:
        return '🏠';
      case TrendingGiftCategory.food:
        return '🍜';
      case TrendingGiftCategory.experience:
        return '🎭';
      case TrendingGiftCategory.custom:
        return '🎁';
    }
  }

  static TrendingGiftCategory fromString(String value) {
    return TrendingGiftCategory.values.firstWhere(
      (e) => e.name == value,
      orElse: () => TrendingGiftCategory.custom,
    );
  }
}

/// Trending gift entity from external data sources
class TrendingGift extends Equatable {
  final String id;
  final String externalId;
  final String name;
  final String? brand;
  final double price;
  final double? originalPrice;
  final int? discountPercent;
  final double? rating;
  final int? reviewCount;
  final String? imageUrl;
  final String? productUrl;
  final TrendingGiftCategory category;
  final String dataSource;
  final int? popularityScore;
  final int? rank;
  final bool isSaved;
  final DateTime? updatedAt;

  const TrendingGift({
    required this.id,
    required this.externalId,
    required this.name,
    this.brand,
    required this.price,
    this.originalPrice,
    this.discountPercent,
    this.rating,
    this.reviewCount,
    this.imageUrl,
    this.productUrl,
    required this.category,
    required this.dataSource,
    this.popularityScore,
    this.rank,
    this.isSaved = false,
    this.updatedAt,
  });

  /// Check if gift has discount
  bool get hasDiscount => originalPrice != null && originalPrice! > price;

  /// Calculate discount if not provided
  int get effectiveDiscountPercent {
    if (discountPercent != null) return discountPercent!;
    if (!hasDiscount) return 0;
    return ((1 - price / originalPrice!) * 100).round();
  }

  TrendingGift copyWith({
    String? id,
    String? externalId,
    String? name,
    String? brand,
    double? price,
    double? originalPrice,
    int? discountPercent,
    double? rating,
    int? reviewCount,
    String? imageUrl,
    String? productUrl,
    TrendingGiftCategory? category,
    String? dataSource,
    int? popularityScore,
    int? rank,
    bool? isSaved,
    DateTime? updatedAt,
  }) {
    return TrendingGift(
      id: id ?? this.id,
      externalId: externalId ?? this.externalId,
      name: name ?? this.name,
      brand: brand ?? this.brand,
      price: price ?? this.price,
      originalPrice: originalPrice ?? this.originalPrice,
      discountPercent: discountPercent ?? this.discountPercent,
      rating: rating ?? this.rating,
      reviewCount: reviewCount ?? this.reviewCount,
      imageUrl: imageUrl ?? this.imageUrl,
      productUrl: productUrl ?? this.productUrl,
      category: category ?? this.category,
      dataSource: dataSource ?? this.dataSource,
      popularityScore: popularityScore ?? this.popularityScore,
      rank: rank ?? this.rank,
      isSaved: isSaved ?? this.isSaved,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  factory TrendingGift.fromJson(Map<String, dynamic> json) {
    return TrendingGift(
      id: json['id'] as String,
      externalId: json['external_id'] as String,
      name: json['name'] as String,
      brand: json['brand'] as String?,
      price: (json['price'] as num).toDouble(),
      originalPrice: json['original_price'] != null
          ? (json['original_price'] as num).toDouble()
          : null,
      discountPercent: json['discount_percent'] as int?,
      rating: json['rating'] != null
          ? (json['rating'] as num).toDouble()
          : null,
      reviewCount: json['review_count'] as int?,
      imageUrl: json['image_url'] as String?,
      productUrl: json['product_url'] as String?,
      category: TrendingGiftCategoryExtension.fromString(
          json['category'] as String),
      dataSource: json['data_source'] as String,
      popularityScore: json['popularity_score'] as int?,
      rank: json['rank'] as int?,
      isSaved: json['is_saved'] as bool? ?? false,
      updatedAt: json['updated_at'] != null
          ? DateTime.parse(json['updated_at'] as String)
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'external_id': externalId,
      'name': name,
      'brand': brand,
      'price': price,
      'original_price': originalPrice,
      'discount_percent': discountPercent,
      'rating': rating,
      'review_count': reviewCount,
      'image_url': imageUrl,
      'product_url': productUrl,
      'category': category.name,
      'data_source': dataSource,
      'popularity_score': popularityScore,
      'rank': rank,
      'is_saved': isSaved,
      'updated_at': updatedAt?.toIso8601String(),
    };
  }

  @override
  List<Object?> get props => [
        id,
        externalId,
        name,
        brand,
        price,
        originalPrice,
        discountPercent,
        rating,
        reviewCount,
        imageUrl,
        productUrl,
        category,
        dataSource,
        popularityScore,
        rank,
        isSaved,
        updatedAt,
      ];
}
