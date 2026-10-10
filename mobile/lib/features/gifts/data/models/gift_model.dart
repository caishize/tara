import '../../domain/entities/gift.dart';

class GiftModel extends Gift {
  const GiftModel({
    required super.id,
    required super.name,
    super.description,
    super.imageUrl,
    required super.price,
    super.originalPrice,
    required super.category,
    super.suitableOccasions,
    super.brand,
    super.rating,
    super.reviewCount,
    super.purchaseUrl,
    super.isSaved,
    required super.createdAt,
  });

  factory GiftModel.fromJson(Map<String, dynamic> json) {
    return GiftModel(
      id: json['id']?.toString() ?? '',
      name: json['name'] ?? '',
      description: json['description'],
      imageUrl: json['image_url'] ?? json['imageUrl'],
      price: _parseDouble(json['price']) ?? 0,
      originalPrice: _parseDouble(json['original_price']),
      category: _parseCategory(json['category']),
      suitableOccasions: _parseOccasions(json['suitable_occasions']),
      brand: json['brand'],
      rating: _parseDouble(json['rating']) ?? 0,
      reviewCount: _parseInt(json['review_count']) ?? 0,
      purchaseUrl: json['purchase_url'] ?? json['purchaseUrl'],
      isSaved: json['is_saved'] ?? false,
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'])
          : DateTime.now(),
    );
  }

  /// Parse a value that could be String or num to double
  static double? _parseDouble(dynamic value) {
    if (value == null) return null;
    if (value is num) return value.toDouble();
    if (value is String) return double.tryParse(value);
    return null;
  }

  /// Parse a value that could be String or num to int
  static int? _parseInt(dynamic value) {
    if (value == null) return null;
    if (value is int) return value;
    if (value is num) return value.toInt();
    if (value is String) return int.tryParse(value);
    return null;
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'description': description,
      'image_url': imageUrl,
      'price': price,
      'original_price': originalPrice,
      'category': category.name,
      'suitable_occasions': suitableOccasions.map((o) => o.name).toList(),
      'brand': brand,
      'rating': rating,
      'review_count': reviewCount,
      'purchase_url': purchaseUrl,
      'is_saved': isSaved,
    };
  }

  static GiftCategory _parseCategory(String? category) {
    if (category == null) return GiftCategory.other;
    return GiftCategory.values.firstWhere(
      (c) => c.name.toLowerCase() == category.toLowerCase(),
      orElse: () => GiftCategory.other,
    );
  }

  static List<GiftOccasion> _parseOccasions(dynamic occasions) {
    if (occasions == null) return [];
    if (occasions is! List) return [];
    return occasions
        .map((o) => GiftOccasion.values.firstWhere(
              (oc) => oc.name.toLowerCase() == o.toString().toLowerCase(),
              orElse: () => GiftOccasion.other,
            ))
        .toList();
  }

  static GiftModel fromEntity(Gift gift) {
    return GiftModel(
      id: gift.id,
      name: gift.name,
      description: gift.description,
      imageUrl: gift.imageUrl,
      price: gift.price,
      originalPrice: gift.originalPrice,
      category: gift.category,
      suitableOccasions: gift.suitableOccasions,
      brand: gift.brand,
      rating: gift.rating,
      reviewCount: gift.reviewCount,
      purchaseUrl: gift.purchaseUrl,
      isSaved: gift.isSaved,
      createdAt: gift.createdAt,
    );
  }
}

class GiftRecommendationModel extends GiftRecommendation {
  const GiftRecommendationModel({
    required super.id,
    required super.memberId,
    required super.memberName,
    required super.occasion,
    required super.eventDate,
    required super.gifts,
    required super.budget,
    required super.createdAt,
  });

  factory GiftRecommendationModel.fromJson(Map<String, dynamic> json) {
    return GiftRecommendationModel(
      id: json['id']?.toString() ?? '',
      memberId: json['member_id']?.toString() ?? '',
      memberName: json['member_name'] ?? '',
      occasion: GiftOccasion.values.firstWhere(
        (o) => o.name.toLowerCase() == (json['occasion'] ?? '').toLowerCase(),
        orElse: () => GiftOccasion.other,
      ),
      eventDate: DateTime.parse(json['event_date']),
      gifts: (json['gifts'] as List? ?? [])
          .map((g) => GiftModel.fromJson(g as Map<String, dynamic>))
          .toList(),
      budget: json['budget'] ?? 0,
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'])
          : DateTime.now(),
    );
  }

  /// Parse from backend API response format
  /// Response format: { id, member_id, member_name, occasion, recommendations: [...], generated_at }
  factory GiftRecommendationModel.fromBackendResponse(Map<String, dynamic> json) {
    final recommendations = json['recommendations'] as List<dynamic>? ?? [];
    final now = DateTime.now();

    return GiftRecommendationModel(
      id: json['id']?.toString() ?? DateTime.now().millisecondsSinceEpoch.toString(),
      memberId: json['member_id']?.toString() ?? '',
      memberName: json['member_name'] ?? '',
      occasion: GiftOccasion.values.firstWhere(
        (o) => o.name.toLowerCase() == (json['occasion'] ?? '').toLowerCase(),
        orElse: () => GiftOccasion.other,
      ),
      eventDate: json['_occasion_date'] != null
          ? DateTime.parse(json['_occasion_date'])
          : now,
      gifts: recommendations
          .map((r) => _parseRecommendationItem(r as Map<String, dynamic>))
          .toList(),
      budget: _parseIntSafely(json['_budget_max'] ?? json['_budget_min'] ?? 0),
      createdAt: json['generated_at'] != null
          ? DateTime.parse(json['generated_at'])
          : now,
    );
  }

  /// Parse a single recommendation item from the API response
  static Gift _parseRecommendationItem(Map<String, dynamic> json) {
    final now = DateTime.now();
    // Backend returns: gift_name, category, description, reason, estimated_price, etc.
    final price = json['estimated_price'] ?? json['price_range_max'] ?? json['price_range_min'] ?? 0;

    return Gift(
      id: json['id']?.toString() ?? DateTime.now().millisecondsSinceEpoch.toString(),
      name: json['gift_name'] ?? json['name'] ?? '',
      description: json['reason'] ?? json['description'] ?? '',
      imageUrl: json['image_url'],
      price: (price is num) ? price.toDouble() : 0.0,
      originalPrice: null,
      category: _parseCategoryFromString(json['category']),
      suitableOccasions: [],
      brand: null,
      rating: ((json['confidence_score'] ?? 0.8) * 5).toDouble(), // Convert 0-1 to 0-5 rating
      reviewCount: 0,
      purchaseUrl: json['purchase_url'],
      isSaved: false,
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'])
          : now,
    );
  }

  static int _parseIntSafely(dynamic value) {
    if (value == null) return 0;
    if (value is int) return value;
    if (value is double) return value.toInt();
    if (value is String) return int.tryParse(value) ?? 0;
    return 0;
  }

  static GiftCategory _parseCategoryFromString(String? category) {
    if (category == null) return GiftCategory.other;
    final lowerCategory = category.toLowerCase();

    // Map common category names
    if (lowerCategory.contains('电子') || lowerCategory.contains('electronic') || lowerCategory.contains('tech')) {
      return GiftCategory.electronics;
    }
    if (lowerCategory.contains('时尚') || lowerCategory.contains('服饰') || lowerCategory.contains('fashion') || lowerCategory.contains('cloth')) {
      return GiftCategory.fashion;
    }
    if (lowerCategory.contains('美妆') || lowerCategory.contains('护肤') || lowerCategory.contains('beauty') || lowerCategory.contains('cosmetic')) {
      return GiftCategory.beauty;
    }
    if (lowerCategory.contains('食品') || lowerCategory.contains('饮料') || lowerCategory.contains('food') || lowerCategory.contains('饮食')) {
      return GiftCategory.food;
    }
    if (lowerCategory.contains('家居') || lowerCategory.contains('home') || lowerCategory.contains('家用')) {
      return GiftCategory.home;
    }
    if (lowerCategory.contains('运动') || lowerCategory.contains('户外') || lowerCategory.contains('sport')) {
      return GiftCategory.sports;
    }
    if (lowerCategory.contains('图书') || lowerCategory.contains('音像') || lowerCategory.contains('book')) {
      return GiftCategory.books;
    }
    if (lowerCategory.contains('玩具') || lowerCategory.contains('toy') || lowerCategory.contains('游戏')) {
      return GiftCategory.toys;
    }
    if (lowerCategory.contains('珠宝') || lowerCategory.contains('首饰') || lowerCategory.contains('jewelry')) {
      return GiftCategory.jewelry;
    }

    return GiftCategory.other;
  }
}

/// Model for member gift memory from API
class MemberGiftMemoryModel extends MemberGiftMemory {
  const MemberGiftMemoryModel({
    required super.memberId,
    super.memoryRichnessScore,
    super.totalGiftsReceived,
    super.giftsLastYear,
    super.categoryDistribution,
    super.recentGifts,
    super.giftsToAvoid,
    super.likedCategories,
    super.dislikedCategories,
    super.preferenceScores,
    super.interestKeywords,
    super.specialNotes,
    super.lastGiftDate,
  });

  factory MemberGiftMemoryModel.fromJson(Map<String, dynamic> json) {
    // Parse category distribution
    final catDistRaw = json['gift_stats']?['category_distribution'] as Map<String, dynamic>? ?? {};
    final categoryDistribution = catDistRaw.map((k, v) => MapEntry(k, _parseInt(v) ?? 0));

    // Parse preference scores
    final prefScoresRaw = json['preferences']?['scores'] as Map<String, dynamic>? ?? {};
    final preferenceScores = prefScoresRaw.map((k, v) => MapEntry(k, _parseDouble(v) ?? 0.0));

    // Parse recent gifts list
    final recentGiftsRaw = json['recent_gifts'] as List<dynamic>? ?? [];
    final recentGifts = recentGiftsRaw.map((g) {
      if (g is Map) return g['gift_name']?.toString() ?? '';
      return g.toString();
    }).where((s) => s.isNotEmpty).toList();

    // Parse gifts to avoid
    final giftsToAvoidRaw = json['gifts_to_avoid'] as List<dynamic>? ?? [];
    final giftsToAvoid = giftsToAvoidRaw.map((g) {
      if (g is Map) return g['gift_name']?.toString() ?? '';
      return g.toString();
    }).where((s) => s.isNotEmpty).toList();

    return MemberGiftMemoryModel(
      memberId: json['member_id']?.toString() ?? '',
      memoryRichnessScore: _parseDouble(json['memory_richness']) ?? 0,
      totalGiftsReceived: _parseInt(json['gift_stats']?['total_received']) ?? 0,
      giftsLastYear: _parseInt(json['gift_stats']?['last_year']) ?? 0,
      categoryDistribution: categoryDistribution,
      recentGifts: recentGifts,
      giftsToAvoid: giftsToAvoid,
      likedCategories: List<String>.from(json['preferences']?['liked'] ?? []),
      dislikedCategories: List<String>.from(json['preferences']?['disliked'] ?? []),
      preferenceScores: preferenceScores,
      interestKeywords: List<String>.from(json['interest_keywords'] ?? []),
      specialNotes: json['special_notes'],
      lastGiftDate: json['last_gift_date'] != null
          ? DateTime.tryParse(json['last_gift_date'])
          : null,
    );
  }

  /// Parse a value that could be String or num to double
  static double? _parseDouble(dynamic value) {
    if (value == null) return null;
    if (value is num) return value.toDouble();
    if (value is String) return double.tryParse(value);
    return null;
  }

  /// Parse a value that could be String or num to int
  static int? _parseInt(dynamic value) {
    if (value == null) return null;
    if (value is int) return value;
    if (value is num) return value.toInt();
    if (value is String) return int.tryParse(value);
    return null;
  }
}

/// Model for gift history item from API
class GiftHistoryItemModel extends GiftHistoryItem {
  const GiftHistoryItemModel({
    required super.id,
    required super.memberId,
    required super.memberName,
    required super.giftName,
    super.giftDescription,
    required super.category,
    required super.price,
    required super.occasion,
    required super.giftDate,
    super.feedback,
    super.rating,
    required super.createdAt,
  });

  factory GiftHistoryItemModel.fromJson(Map<String, dynamic> json) {
    return GiftHistoryItemModel(
      id: json['id']?.toString() ?? '',
      memberId: json['member_id']?.toString() ?? '',
      memberName: json['member_name'] ?? '',
      giftName: json['gift_name'] ?? json['name'] ?? '',
      giftDescription: json['gift_description'] ?? json['description'],
      category: json['category'] ?? 'other',
      price: _parseDouble(json['price']) ?? 0,
      occasion: json['occasion'] ?? '',
      giftDate: json['gift_date'] != null
          ? DateTime.parse(json['gift_date'])
          : (json['date_given'] != null
              ? DateTime.parse(json['date_given'])
              : DateTime.now()),
      feedback: json['feedback'],
      rating: _parseInt(json['rating']),
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'])
          : DateTime.now(),
    );
  }

  /// Parse a value that could be String or num to double
  static double? _parseDouble(dynamic value) {
    if (value == null) return null;
    if (value is num) return value.toDouble();
    if (value is String) return double.tryParse(value);
    return null;
  }

  /// Parse a value that could be String or num to int
  static int? _parseInt(dynamic value) {
    if (value == null) return null;
    if (value is int) return value;
    if (value is num) return value.toInt();
    if (value is String) return int.tryParse(value);
    return null;
  }
}

/// Model for smart date from API
class SmartDateModel extends SmartDate {
  const SmartDateModel({
    super.id,
    required super.name,
    super.dateValue,
    super.daysUntil,
    required super.occasionType,
    required super.source,
    super.dateType,
    super.importanceLevel,
  });

  factory SmartDateModel.fromJson(Map<String, dynamic> json) {
    return SmartDateModel(
      id: json['id']?.toString(),
      name: json['name'] ?? '',
      dateValue: json['date_value'] != null
          ? DateTime.tryParse(json['date_value'])
          : null,
      daysUntil: json['days_until'] as int?,
      occasionType: _parseOccasion(json['occasion_type'] as String?),
      source: _parseSource(json['source'] as String?),
      dateType: json['date_type'] as String?,
      importanceLevel: json['importance_level'] as int? ?? 5,
    );
  }

  static GiftOccasion _parseOccasion(String? value) {
    if (value == null) return GiftOccasion.other;
    return GiftOccasion.values.firstWhere(
      (e) => e.name.toLowerCase() == value.toLowerCase(),
      orElse: () => GiftOccasion.other,
    );
  }

  static SmartDateSource _parseSource(String? value) {
    switch (value) {
      case 'member_date':
        return SmartDateSource.memberDate;
      case 'natural_holiday':
        return SmartDateSource.naturalHoliday;
      case 'general':
      default:
        return SmartDateSource.general;
    }
  }
}

/// Model for budget suggestion from API
class BudgetSuggestionModel extends BudgetSuggestion {
  const BudgetSuggestionModel({
    required super.suggestedBudget,
    required super.budgetMin,
    required super.budgetMax,
    super.factors,
    super.confidence,
  });

  factory BudgetSuggestionModel.fromJson(Map<String, dynamic> json) {
    return BudgetSuggestionModel(
      suggestedBudget: _parseInt(json['suggested_budget']) ?? 300,
      budgetMin: _parseInt(json['budget_min']) ?? 100,
      budgetMax: _parseInt(json['budget_max']) ?? 500,
      factors: json['factors'] as Map<String, dynamic>? ?? {},
      confidence: _parseDouble(json['confidence']) ?? 0.5,
    );
  }

  /// Parse a value that could be String or num to double
  static double? _parseDouble(dynamic value) {
    if (value == null) return null;
    if (value is num) return value.toDouble();
    if (value is String) return double.tryParse(value);
    return null;
  }

  /// Parse a value that could be String or num to int
  static int? _parseInt(dynamic value) {
    if (value == null) return null;
    if (value is int) return value;
    if (value is num) return value.toInt();
    if (value is String) return int.tryParse(value);
    return null;
  }
}

/// Model for smart dates result from API
class SmartDatesResultModel extends SmartDatesResult {
  const SmartDatesResultModel({
    required super.dates,
    super.nearestDateId,
  });

  factory SmartDatesResultModel.fromJson(Map<String, dynamic> json) {
    final datesRaw = json['dates'] as List<dynamic>? ?? [];
    final dates = datesRaw
        .map((d) => SmartDateModel.fromJson(d as Map<String, dynamic>))
        .toList();

    return SmartDatesResultModel(
      dates: dates,
      nearestDateId: json['nearest_date_id'] as String?,
    );
  }
}
