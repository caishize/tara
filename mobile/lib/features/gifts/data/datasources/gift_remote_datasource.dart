import '../../../../core/network/api_client.dart';
import '../../domain/entities/gift.dart';
import '../models/gift_model.dart';

class GiftRemoteDataSource {
  final ApiClient _client;

  GiftRemoteDataSource(this._client);

  Future<List<GiftModel>> getPopularGifts({
    GiftCategory? category,
    int? limit,
  }) async {
    final queryParams = <String, dynamic>{};
    if (category != null) queryParams['category'] = category.name;
    if (limit != null) queryParams['limit'] = limit;

    final response = await _client.get<List<dynamic>>(
      '/gifts/trending',
      queryParameters: queryParams.isNotEmpty ? queryParams : null,
    );

    return response
        .map((json) => GiftModel.fromJson(json as Map<String, dynamic>))
        .toList();
  }

  Future<List<GiftModel>> searchGifts({
    required String query,
    GiftCategory? category,
    double? minPrice,
    double? maxPrice,
  }) async {
    final queryParams = <String, dynamic>{'q': query};
    if (category != null) queryParams['category'] = category.name;
    if (minPrice != null) queryParams['min_price'] = minPrice;
    if (maxPrice != null) queryParams['max_price'] = maxPrice;

    final response = await _client.get<List<dynamic>>(
      '/gifts/search',
      queryParameters: queryParams,
    );

    return response
        .map((json) => GiftModel.fromJson(json as Map<String, dynamic>))
        .toList();
  }

  /// Generate AI gift recommendations
  /// POST /gifts/recommend (baseUrl already has /api/v1)
  Future<GiftRecommendationModel> generateRecommendation({
    required String memberId,
    required GiftOccasion occasion,
    int? budgetMin,
    int? budgetMax,
    String? urgency,
  }) async {
    final response = await _client.post<Map<String, dynamic>>(
      '/gifts/recommend',
      data: {
        'member_id': memberId,
        'occasion': occasion.name,
        if (budgetMin != null) 'budget_min': budgetMin,
        if (budgetMax != null) 'budget_max': budgetMax,
        if (urgency != null) 'urgency': urgency,
      },
    );

    return GiftRecommendationModel.fromBackendResponse(response);
  }

  /// Get member gift memory (preferences, history, things to avoid)
  /// GET /gifts/memory/{member_id}
  Future<MemberGiftMemoryModel> getMemberGiftMemory(String memberId) async {
    final response = await _client.get<Map<String, dynamic>>(
      '/gifts/memory/$memberId',
    );

    return MemberGiftMemoryModel.fromJson(response);
  }

  /// Get gift history for a member
  /// GET /gifts/history/{member_id}
  Future<List<GiftHistoryItemModel>> getMemberGiftHistory(String memberId) async {
    final response = await _client.get<List<dynamic>>(
      '/gifts/history/$memberId',
    );

    return response
        .map((json) => GiftHistoryItemModel.fromJson(json as Map<String, dynamic>))
        .toList();
  }

  /// Get smart date suggestions for a member (important dates + holidays)
  /// GET /gifts/smart-dates/{member_id}
  Future<SmartDatesResultModel> getSmartDatesForMember(
    String memberId, {
    int daysAhead = 90,
  }) async {
    final response = await _client.get<Map<String, dynamic>>(
      '/gifts/smart-dates/$memberId',
      queryParameters: {'days_ahead': daysAhead},
    );

    return SmartDatesResultModel.fromJson(response);
  }

  /// Get intelligent budget suggestion for a member
  /// GET /gifts/budget-suggestion/{member_id}
  Future<BudgetSuggestionModel> getBudgetSuggestion({
    required String memberId,
    String? occasion,
  }) async {
    final queryParams = <String, dynamic>{};
    if (occasion != null) queryParams['occasion'] = occasion;

    final response = await _client.get<Map<String, dynamic>>(
      '/gifts/budget-suggestion/$memberId',
      queryParameters: queryParams.isNotEmpty ? queryParams : null,
    );

    return BudgetSuggestionModel.fromJson(response);
  }

  /// Get recommendation history (all recommendations)
  /// GET /gifts/recommend (baseUrl already has /api/v1)
  Future<List<GiftRecommendationModel>> getRecommendationHistory({
    String? memberId,
    int limit = 10,
    int offset = 0,
  }) async {
    final queryParams = <String, dynamic>{
      'limit': limit,
      'offset': offset,
    };
    // Pass member_id to backend for server-side filtering
    if (memberId != null) {
      queryParams['member_id'] = memberId;
    }

    final response = await _client.get<Map<String, dynamic>>(
      '/gifts/recommend',
      queryParameters: queryParams,
    );

    final recommendations = response['recommendations'] as List<dynamic>? ?? [];
    return recommendations
        .map((json) => GiftRecommendationModel.fromBackendResponse(json as Map<String, dynamic>))
        .toList();
  }

  Future<List<GiftModel>> getSavedGifts() async {
    final response = await _client.get<List<dynamic>>('/gifts/saved');

    return response
        .map((json) => GiftModel.fromJson(json as Map<String, dynamic>))
        .toList();
  }

  Future<void> saveGift(String giftId) async {
    await _client.post('/gifts/$giftId/save');
  }

  Future<void> unsaveGift(String giftId) async {
    await _client.delete('/gifts/$giftId/save');
  }
}
