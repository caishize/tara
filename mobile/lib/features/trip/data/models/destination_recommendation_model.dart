import '../../domain/entities/destination_recommendation.dart';

class DestinationRecommendationModel extends DestinationRecommendation {
  const DestinationRecommendationModel({
    required super.destinationName,
    super.country,
    super.region,
    super.description,
    super.bestSeason,
    super.estimatedBudget,
    super.recommendedDays,
    super.highlights,
    super.suitableFor,
    super.matchScore,
    super.matchReason,
    super.imageUrl,
  });

  factory DestinationRecommendationModel.fromJson(Map<String, dynamic> json) {
    return DestinationRecommendationModel(
      destinationName: json['destination_name'] ?? json['destination'] ?? '',
      country: json['country'],
      region: json['region'],
      description: json['description'] ?? '',
      bestSeason: json['best_season'],
      estimatedBudget: (json['estimated_budget'] ?? 0).toDouble(),
      recommendedDays: json['recommended_days'] ?? 3,
      highlights: (json['highlights'] as List?)?.cast<String>() ?? [],
      suitableFor: (json['suitable_for'] as List?)?.cast<String>() ?? [],
      matchScore: (json['match_score'] ?? json['fit_score'] ?? 0).toDouble(),
      matchReason: json['match_reason'] ?? json['suitable_reason'],
      imageUrl: json['image_url'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'destination_name': destinationName,
      'country': country,
      'region': region,
      'description': description,
      'best_season': bestSeason,
      'estimated_budget': estimatedBudget,
      'recommended_days': recommendedDays,
      'highlights': highlights,
      'suitable_for': suitableFor,
      'match_score': matchScore,
      'match_reason': matchReason,
      'image_url': imageUrl,
    };
  }

  static DestinationRecommendationModel fromEntity(DestinationRecommendation entity) {
    return DestinationRecommendationModel(
      destinationName: entity.destinationName,
      country: entity.country,
      region: entity.region,
      description: entity.description,
      bestSeason: entity.bestSeason,
      estimatedBudget: entity.estimatedBudget,
      recommendedDays: entity.recommendedDays,
      highlights: entity.highlights,
      suitableFor: entity.suitableFor,
      matchScore: entity.matchScore,
      matchReason: entity.matchReason,
      imageUrl: entity.imageUrl,
    );
  }
}

class RecommendationRequestModel extends RecommendationRequest {
  const RecommendationRequestModel({
    required super.familyId,
    super.occasion,
    super.budgetMin,
    super.budgetMax,
    super.durationDays,
    super.season,
    super.userInput,
  });

  Map<String, dynamic> toJson() {
    return {
      'family_id': familyId,
      if (occasion != null) 'occasion': occasion,
      if (budgetMin != null) 'budget_min': budgetMin,
      if (budgetMax != null) 'budget_max': budgetMax,
      if (durationDays != null) 'duration_days': durationDays,
      if (season != null) 'season': season,
      if (userInput != null) 'user_input': userInput,
    };
  }

  static RecommendationRequestModel fromEntity(RecommendationRequest entity) {
    return RecommendationRequestModel(
      familyId: entity.familyId,
      occasion: entity.occasion,
      budgetMin: entity.budgetMin,
      budgetMax: entity.budgetMax,
      durationDays: entity.durationDays,
      season: entity.season,
      userInput: entity.userInput,
    );
  }
}

class RecommendationResponseModel extends RecommendationResponse {
  const RecommendationResponseModel({
    super.recommendations,
    super.familyContext,
    super.generationTimeMs,
  });

  factory RecommendationResponseModel.fromJson(Map<String, dynamic> json) {
    return RecommendationResponseModel(
      recommendations: (json['recommendations'] as List?)
          ?.map((r) => DestinationRecommendationModel.fromJson(r as Map<String, dynamic>))
          .toList() ?? [],
      familyContext: json['family_context'],
      generationTimeMs: json['generation_time_ms'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'recommendations': recommendations
          .map((r) => (r as DestinationRecommendationModel).toJson())
          .toList(),
      if (familyContext != null) 'family_context': familyContext,
      if (generationTimeMs != null) 'generation_time_ms': generationTimeMs,
    };
  }
}
