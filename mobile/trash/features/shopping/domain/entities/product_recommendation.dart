import 'package:equatable/equatable.dart';

/// 推荐原因类型
enum RecommendationReason {
  frequentPurchase, // 经常购买
  lowStock,         // 库存不足
  priceDrop,        // 价格下降
  seasonal,         // 季节推荐
  bundleSuggestion, // 凑单建议
}

/// 商品推荐实体
class ProductRecommendation extends Equatable {
  final String id;
  final String productName;
  final String? category;
  final RecommendationReason reason;
  final int priority; // 1-5, 1最高
  final double? estimatedPrice;
  final double? currentPrice;
  final double? baselinePrice;
  final String? description;
  final String? imageUrl;
  final String? merchant;
  final Map<String, dynamic> metadata;
  final DateTime createdAt;

  const ProductRecommendation({
    required this.id,
    required this.productName,
    this.category,
    required this.reason,
    this.priority = 3,
    this.estimatedPrice,
    this.currentPrice,
    this.baselinePrice,
    this.description,
    this.imageUrl,
    this.merchant,
    this.metadata = const {},
    required this.createdAt,
  });

  /// 是否有价格下降
  bool get hasPriceDrop {
    if (currentPrice == null || baselinePrice == null) return false;
    return currentPrice! < baselinePrice!;
  }

  /// 价格下降百分比
  double? get priceDropPercentage {
    if (!hasPriceDrop) return null;
    return ((baselinePrice! - currentPrice!) / baselinePrice! * 100);
  }

  /// 获取推荐原因显示名称
  String get reasonName {
    switch (reason) {
      case RecommendationReason.frequentPurchase:
        return '经常购买';
      case RecommendationReason.lowStock:
        return '库存不足';
      case RecommendationReason.priceDrop:
        return '降价促销';
      case RecommendationReason.seasonal:
        return '应季推荐';
      case RecommendationReason.bundleSuggestion:
        return '凑单推荐';
    }
  }

  /// 获取推荐原因图标
  String get reasonIcon {
    switch (reason) {
      case RecommendationReason.frequentPurchase:
        return '🔄';
      case RecommendationReason.lowStock:
        return '⚠️';
      case RecommendationReason.priceDrop:
        return '💰';
      case RecommendationReason.seasonal:
        return '🌸';
      case RecommendationReason.bundleSuggestion:
        return '📦';
    }
  }

  /// 获取购买次数（从metadata）
  int? get purchaseCount => metadata['purchase_count'] as int?;

  /// 获取上次购买日期（从metadata）
  DateTime? get lastPurchaseDate {
    final dateStr = metadata['last_purchase_date'] as String?;
    if (dateStr == null) return null;
    return DateTime.tryParse(dateStr);
  }

  /// 获取当前库存量（从metadata）
  double? get currentStock => (metadata['current_stock'] as num?)?.toDouble();

  ProductRecommendation copyWith({
    String? id,
    String? productName,
    String? category,
    RecommendationReason? reason,
    int? priority,
    double? estimatedPrice,
    double? currentPrice,
    double? baselinePrice,
    String? description,
    String? imageUrl,
    String? merchant,
    Map<String, dynamic>? metadata,
    DateTime? createdAt,
  }) {
    return ProductRecommendation(
      id: id ?? this.id,
      productName: productName ?? this.productName,
      category: category ?? this.category,
      reason: reason ?? this.reason,
      priority: priority ?? this.priority,
      estimatedPrice: estimatedPrice ?? this.estimatedPrice,
      currentPrice: currentPrice ?? this.currentPrice,
      baselinePrice: baselinePrice ?? this.baselinePrice,
      description: description ?? this.description,
      imageUrl: imageUrl ?? this.imageUrl,
      merchant: merchant ?? this.merchant,
      metadata: metadata ?? this.metadata,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  @override
  List<Object?> get props => [
    id, productName, category, reason, priority,
    estimatedPrice, currentPrice, baselinePrice,
    description, imageUrl, merchant, metadata, createdAt,
  ];
}
