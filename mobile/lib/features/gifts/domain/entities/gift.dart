import 'package:equatable/equatable.dart';

enum GiftCategory {
  electronics,    // 电子产品
  fashion,        // 时尚服饰
  beauty,         // 美妆护肤
  food,           // 食品饮料
  home,           // 家居生活
  sports,         // 运动户外
  books,          // 图书音像
  toys,           // 玩具礼品
  jewelry,        // 珠宝首饰
  other,          // 其他
}

enum GiftOccasion {
  birthday,       // 生日
  anniversary,    // 纪念日
  holiday,        // 节日
  graduation,     // 毕业
  wedding,        // 婚礼
  babyShower,     // 满月/百日
  housewarming,   // 乔迁
  thankyou,       // 感谢
  other,          // 其他
}

class Gift extends Equatable {
  final String id;
  final String name;
  final String? description;
  final String? imageUrl;
  final double price;
  final double? originalPrice;
  final GiftCategory category;
  final List<GiftOccasion> suitableOccasions;
  final String? brand;
  final double rating;
  final int reviewCount;
  final String? purchaseUrl;
  final bool isSaved;
  final DateTime createdAt;

  const Gift({
    required this.id,
    required this.name,
    this.description,
    this.imageUrl,
    required this.price,
    this.originalPrice,
    required this.category,
    this.suitableOccasions = const [],
    this.brand,
    this.rating = 0,
    this.reviewCount = 0,
    this.purchaseUrl,
    this.isSaved = false,
    required this.createdAt,
  });

  /// 是否有折扣
  bool get hasDiscount => originalPrice != null && originalPrice! > price;

  /// 折扣百分比
  int get discountPercent {
    if (!hasDiscount) return 0;
    return ((1 - price / originalPrice!) * 100).round();
  }

  /// 获取分类显示名称
  String get categoryName {
    switch (category) {
      case GiftCategory.electronics:
        return '电子产品';
      case GiftCategory.fashion:
        return '时尚服饰';
      case GiftCategory.beauty:
        return '美妆护肤';
      case GiftCategory.food:
        return '食品饮料';
      case GiftCategory.home:
        return '家居生活';
      case GiftCategory.sports:
        return '运动户外';
      case GiftCategory.books:
        return '图书音像';
      case GiftCategory.toys:
        return '玩具礼品';
      case GiftCategory.jewelry:
        return '珠宝首饰';
      case GiftCategory.other:
        return '其他';
    }
  }

  /// 获取分类图标
  String get categoryIcon {
    switch (category) {
      case GiftCategory.electronics:
        return '📱';
      case GiftCategory.fashion:
        return '👗';
      case GiftCategory.beauty:
        return '💄';
      case GiftCategory.food:
        return '🍰';
      case GiftCategory.home:
        return '🏠';
      case GiftCategory.sports:
        return '⚽';
      case GiftCategory.books:
        return '📚';
      case GiftCategory.toys:
        return '🎁';
      case GiftCategory.jewelry:
        return '💎';
      case GiftCategory.other:
        return '🎀';
    }
  }

  Gift copyWith({
    String? id,
    String? name,
    String? description,
    String? imageUrl,
    double? price,
    double? originalPrice,
    GiftCategory? category,
    List<GiftOccasion>? suitableOccasions,
    String? brand,
    double? rating,
    int? reviewCount,
    String? purchaseUrl,
    bool? isSaved,
    DateTime? createdAt,
  }) {
    return Gift(
      id: id ?? this.id,
      name: name ?? this.name,
      description: description ?? this.description,
      imageUrl: imageUrl ?? this.imageUrl,
      price: price ?? this.price,
      originalPrice: originalPrice ?? this.originalPrice,
      category: category ?? this.category,
      suitableOccasions: suitableOccasions ?? this.suitableOccasions,
      brand: brand ?? this.brand,
      rating: rating ?? this.rating,
      reviewCount: reviewCount ?? this.reviewCount,
      purchaseUrl: purchaseUrl ?? this.purchaseUrl,
      isSaved: isSaved ?? this.isSaved,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  @override
  List<Object?> get props => [
    id, name, description, imageUrl, price, originalPrice, category,
    suitableOccasions, brand, rating, reviewCount, purchaseUrl, isSaved, createdAt,
  ];
}

class GiftRecommendation extends Equatable {
  final String id;
  final String memberId;
  final String memberName;
  final GiftOccasion occasion;
  final DateTime eventDate;
  final List<Gift> gifts;
  final int budget;
  final DateTime createdAt;

  const GiftRecommendation({
    required this.id,
    required this.memberId,
    required this.memberName,
    required this.occasion,
    required this.eventDate,
    required this.gifts,
    required this.budget,
    required this.createdAt,
  });

  @override
  List<Object?> get props => [
    id, memberId, memberName, occasion, eventDate, gifts, budget, createdAt,
  ];
}

/// 成员礼物记忆 - 用于存储成员的偏好和历史信息
class MemberGiftMemory extends Equatable {
  final String memberId;
  final double memoryRichnessScore;
  final int totalGiftsReceived;
  final int giftsLastYear;
  final Map<String, int> categoryDistribution;
  final List<String> recentGifts;
  final List<String> giftsToAvoid;
  final List<String> likedCategories;
  final List<String> dislikedCategories;
  final Map<String, double> preferenceScores;
  final List<String> interestKeywords;
  final String? specialNotes;
  final DateTime? lastGiftDate;

  const MemberGiftMemory({
    required this.memberId,
    this.memoryRichnessScore = 0,
    this.totalGiftsReceived = 0,
    this.giftsLastYear = 0,
    this.categoryDistribution = const {},
    this.recentGifts = const [],
    this.giftsToAvoid = const [],
    this.likedCategories = const [],
    this.dislikedCategories = const [],
    this.preferenceScores = const {},
    this.interestKeywords = const [],
    this.specialNotes,
    this.lastGiftDate,
  });

  @override
  List<Object?> get props => [
    memberId, memoryRichnessScore, totalGiftsReceived, giftsLastYear,
    categoryDistribution, recentGifts, giftsToAvoid, likedCategories,
    dislikedCategories, preferenceScores, interestKeywords, specialNotes, lastGiftDate,
  ];
}

/// 礼物历史记录
class GiftHistoryItem extends Equatable {
  final String id;
  final String memberId;
  final String memberName;
  final String giftName;
  final String? giftDescription;
  final String category;
  final double price;
  final String occasion;
  final DateTime giftDate;
  final String? feedback;
  final int? rating;
  final DateTime createdAt;

  const GiftHistoryItem({
    required this.id,
    required this.memberId,
    required this.memberName,
    required this.giftName,
    this.giftDescription,
    required this.category,
    required this.price,
    required this.occasion,
    required this.giftDate,
    this.feedback,
    this.rating,
    required this.createdAt,
  });

  @override
  List<Object?> get props => [
    id, memberId, memberName, giftName, giftDescription, category,
    price, occasion, giftDate, feedback, rating, createdAt,
  ];
}

/// 智能日期来源
enum SmartDateSource {
  memberDate,      // 成员的重要日期 (生日、纪念日等)
  naturalHoliday,  // 自然节日 (春节、情人节等)
  general,         // 通用推荐
}

/// 智能日期 - 用于礼物推荐的日期选择
class SmartDate extends Equatable {
  final String? id;
  final String name;
  final DateTime? dateValue;
  final int? daysUntil;
  final GiftOccasion occasionType;
  final SmartDateSource source;
  final String? dateType;
  final int importanceLevel;

  const SmartDate({
    this.id,
    required this.name,
    this.dateValue,
    this.daysUntil,
    required this.occasionType,
    required this.source,
    this.dateType,
    this.importanceLevel = 5,
  });

  /// 是否为通用推荐
  bool get isGeneral => source == SmartDateSource.general;

  /// 获取倒计时显示文本
  String get countdownText {
    if (daysUntil == null) return '';
    if (daysUntil == 0) return '今天';
    if (daysUntil == 1) return '明天';
    if (daysUntil! < 0) return '已过';
    return '$daysUntil天后';
  }

  /// 获取日期类型图标
  String get icon {
    if (isGeneral) return '🎁';
    switch (dateType) {
      case 'birthday': return '🎂';
      case 'anniversary': return '💑';
      case 'wedding': return '💒';
      case 'graduation': return '🎓';
      case 'holiday': return '🎉';
      default: return '📅';
    }
  }

  @override
  List<Object?> get props => [
    id, name, dateValue, daysUntil, occasionType, source, dateType, importanceLevel,
  ];
}

/// 预算建议 - AI智能推荐的预算
class BudgetSuggestion extends Equatable {
  final int suggestedBudget;
  final int budgetMin;
  final int budgetMax;
  final Map<String, dynamic> factors;
  final double confidence;

  const BudgetSuggestion({
    required this.suggestedBudget,
    required this.budgetMin,
    required this.budgetMax,
    this.factors = const {},
    this.confidence = 0.5,
  });

  /// 置信度等级描述
  String get confidenceLevel {
    if (confidence >= 0.8) return '高';
    if (confidence >= 0.5) return '中';
    return '低';
  }

  /// 获取关系类型描述
  String? get relationshipType => factors['relationship_type'] as String?;

  /// 获取历史平均值
  double? get historicalAvg => (factors['historical_avg'] as num?)?.toDouble();

  @override
  List<Object?> get props => [suggestedBudget, budgetMin, budgetMax, factors, confidence];
}

/// 智能日期结果 - 包含日期列表和最近日期ID
class SmartDatesResult extends Equatable {
  final List<SmartDate> dates;
  final String? nearestDateId;

  const SmartDatesResult({
    required this.dates,
    this.nearestDateId,
  });

  @override
  List<Object?> get props => [dates, nearestDateId];
}
