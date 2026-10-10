import 'package:equatable/equatable.dart';

/// 目的地推荐
class DestinationRecommendation extends Equatable {
  final String destinationName;
  final String? country;
  final String? region;
  final String description;
  final String? bestSeason;
  final double estimatedBudget;
  final int recommendedDays;
  final List<String> highlights;
  final List<String> suitableFor;
  final double matchScore;
  final String? matchReason;
  final String? imageUrl;

  const DestinationRecommendation({
    required this.destinationName,
    this.country,
    this.region,
    this.description = '',
    this.bestSeason,
    this.estimatedBudget = 0,
    this.recommendedDays = 3,
    this.highlights = const [],
    this.suitableFor = const [],
    this.matchScore = 0,
    this.matchReason,
    this.imageUrl,
  });

  /// 匹配度显示文本
  String get matchScoreText => '${(matchScore * 100).toInt()}%';

  /// 预算显示文本
  String get budgetText => '¥${estimatedBudget.toStringAsFixed(0)}';

  /// 天数显示文本
  String get daysText => '$recommendedDays天';

  DestinationRecommendation copyWith({
    String? destinationName,
    String? country,
    String? region,
    String? description,
    String? bestSeason,
    double? estimatedBudget,
    int? recommendedDays,
    List<String>? highlights,
    List<String>? suitableFor,
    double? matchScore,
    String? matchReason,
    String? imageUrl,
  }) {
    return DestinationRecommendation(
      destinationName: destinationName ?? this.destinationName,
      country: country ?? this.country,
      region: region ?? this.region,
      description: description ?? this.description,
      bestSeason: bestSeason ?? this.bestSeason,
      estimatedBudget: estimatedBudget ?? this.estimatedBudget,
      recommendedDays: recommendedDays ?? this.recommendedDays,
      highlights: highlights ?? this.highlights,
      suitableFor: suitableFor ?? this.suitableFor,
      matchScore: matchScore ?? this.matchScore,
      matchReason: matchReason ?? this.matchReason,
      imageUrl: imageUrl ?? this.imageUrl,
    );
  }

  @override
  List<Object?> get props => [
    destinationName, country, region, description, bestSeason,
    estimatedBudget, recommendedDays, highlights, suitableFor,
    matchScore, matchReason, imageUrl,
  ];
}

/// 推荐请求参数
class RecommendationRequest extends Equatable {
  final String familyId;
  final String? occasion;
  final double? budgetMin;
  final double? budgetMax;
  final int? durationDays;
  final String? season;
  final String? userInput;

  const RecommendationRequest({
    required this.familyId,
    this.occasion,
    this.budgetMin,
    this.budgetMax,
    this.durationDays,
    this.season,
    this.userInput,
  });

  @override
  List<Object?> get props => [
    familyId, occasion, budgetMin, budgetMax, durationDays, season, userInput,
  ];
}

/// 推荐响应
class RecommendationResponse extends Equatable {
  final List<DestinationRecommendation> recommendations;
  final Map<String, dynamic>? familyContext;
  final int? generationTimeMs;

  const RecommendationResponse({
    this.recommendations = const [],
    this.familyContext,
    this.generationTimeMs,
  });

  @override
  List<Object?> get props => [recommendations, familyContext, generationTimeMs];
}

/// 场合类型
enum OccasionType {
  vacation,       // 假期
  weekend,        // 周末
  honeymoon,      // 蜜月
  anniversary,    // 纪念日
  birthday,       // 生日
  teamBuilding,   // 团建
  other,          // 其他
}

/// 场合类型扩展
extension OccasionTypeExtension on OccasionType {
  String get name {
    switch (this) {
      case OccasionType.vacation:
        return '假期';
      case OccasionType.weekend:
        return '周末';
      case OccasionType.honeymoon:
        return '蜜月';
      case OccasionType.anniversary:
        return '纪念日';
      case OccasionType.birthday:
        return '生日';
      case OccasionType.teamBuilding:
        return '团建';
      case OccasionType.other:
        return '其他';
    }
  }

  String get icon {
    switch (this) {
      case OccasionType.vacation:
        return '🏖️';
      case OccasionType.weekend:
        return '🌅';
      case OccasionType.honeymoon:
        return '💑';
      case OccasionType.anniversary:
        return '💝';
      case OccasionType.birthday:
        return '🎂';
      case OccasionType.teamBuilding:
        return '👥';
      case OccasionType.other:
        return '✈️';
    }
  }

  String get value {
    return toString().split('.').last;
  }
}
