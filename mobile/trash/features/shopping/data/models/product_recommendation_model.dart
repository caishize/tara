import '../../domain/entities/product_recommendation.dart';
import '../../domain/entities/bundle_opportunity.dart';

class ProductRecommendationModel extends ProductRecommendation {
  const ProductRecommendationModel({
    required super.id,
    required super.productName,
    super.category,
    required super.reason,
    super.priority,
    super.estimatedPrice,
    super.currentPrice,
    super.baselinePrice,
    super.description,
    super.metadata,
    required super.createdAt,
  });

  factory ProductRecommendationModel.fromJson(Map<String, dynamic> json) {
    return ProductRecommendationModel(
      id: json['id']?.toString() ?? '',
      productName: json['product_name'] ?? json['name'] ?? '',
      category: json['category'],
      reason: _parseReason(json['reason'] ?? json['type']),
      priority: json['priority'] ?? 3,
      estimatedPrice: json['estimated_price']?.toDouble(),
      currentPrice: json['current_price']?.toDouble(),
      baselinePrice: json['baseline_price']?.toDouble(),
      description: json['description'] ?? json['reason_detail'],
      metadata: _parseMetadata(json),
      createdAt: DateTime.tryParse(json['created_at'] ?? '') ?? DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'product_name': productName,
      'category': category,
      'reason': _reasonToString(reason),
      'priority': priority,
      'estimated_price': estimatedPrice,
      'current_price': currentPrice,
      'baseline_price': baselinePrice,
      'description': description,
      ...metadata,
      'created_at': createdAt.toIso8601String(),
    };
  }

  static RecommendationReason _parseReason(String? reason) {
    switch (reason?.toLowerCase()) {
      case 'frequent_purchase':
      case 'frequent':
        return RecommendationReason.frequentPurchase;
      case 'low_stock':
        return RecommendationReason.lowStock;
      case 'price_drop':
        return RecommendationReason.priceDrop;
      case 'seasonal':
        return RecommendationReason.seasonal;
      case 'bundle_suggestion':
      case 'bundle':
        return RecommendationReason.bundleSuggestion;
      default:
        return RecommendationReason.frequentPurchase;
    }
  }

  static String _reasonToString(RecommendationReason reason) {
    switch (reason) {
      case RecommendationReason.frequentPurchase:
        return 'frequent_purchase';
      case RecommendationReason.lowStock:
        return 'low_stock';
      case RecommendationReason.priceDrop:
        return 'price_drop';
      case RecommendationReason.seasonal:
        return 'seasonal';
      case RecommendationReason.bundleSuggestion:
        return 'bundle_suggestion';
    }
  }

  static Map<String, dynamic> _parseMetadata(Map<String, dynamic> json) {
    return {
      if (json['purchase_count'] != null) 'purchase_count': json['purchase_count'],
      if (json['last_purchase_date'] != null) 'last_purchase_date': json['last_purchase_date'],
      if (json['current_stock'] != null) 'current_stock': json['current_stock'],
      if (json['price_drop_percentage'] != null) 'price_drop_percentage': json['price_drop_percentage'],
    };
  }
}

class BundleOpportunityModel extends BundleOpportunity {
  const BundleOpportunityModel({
    required super.couponName,
    required super.threshold,
    required super.discount,
    required super.currentTotal,
    required super.gap,
    required super.potentialSavings,
    super.suggestedItems,
    super.message,
    super.roi,
  });

  factory BundleOpportunityModel.fromJson(Map<String, dynamic> json) {
    final suggestedItemsJson = json['suggested_items'] as List<dynamic>? ?? [];
    final suggestedItems = suggestedItemsJson
        .map((item) => ProductRecommendationModel.fromJson(item as Map<String, dynamic>))
        .toList();

    return BundleOpportunityModel(
      couponName: json['coupon_name'] ?? json['coupon'] ?? '满减优惠',
      threshold: (json['threshold'] ?? 0).toDouble(),
      discount: (json['discount'] ?? 0).toDouble(),
      currentTotal: (json['current_total'] ?? 0).toDouble(),
      gap: (json['gap'] ?? 0).toDouble(),
      potentialSavings: (json['potential_savings'] ?? json['discount'] ?? 0).toDouble(),
      suggestedItems: suggestedItems,
      message: json['message'],
      roi: (json['roi'] ?? 0).toDouble(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'coupon_name': couponName,
      'threshold': threshold,
      'discount': discount,
      'current_total': currentTotal,
      'gap': gap,
      'potential_savings': potentialSavings,
      'suggested_items': suggestedItems
          .map((item) => (item as ProductRecommendationModel).toJson())
          .toList(),
      'message': message,
      'roi': roi,
    };
  }
}
