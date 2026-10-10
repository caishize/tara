import '../../../../core/network/api_client.dart';
import '../../domain/entities/trending_gift.dart';
import '../../domain/entities/occasion.dart';

/// Remote data source for trending gifts API
class TrendingGiftsRemoteDataSource {
  final ApiClient _apiClient;

  TrendingGiftsRemoteDataSource(this._apiClient);

  /// Get trending gifts by category
  Future<TrendingGiftsResponse> getTrendingGifts({
    TrendingGiftCategory? category,
    String sortBy = 'popularity',
    int limit = 20,
    int offset = 0,
  }) async {
    final queryParams = <String, dynamic>{
      'sort_by': sortBy,
      'limit': limit,
      'offset': offset,
    };
    if (category != null) {
      queryParams['category'] = category.name;
    }

    final response = await _apiClient.get<Map<String, dynamic>>(
      '/gifts/trending',
      queryParameters: queryParams,
    );
    return TrendingGiftsResponse.fromJson(response);
  }

  /// Search trending gifts
  Future<TrendingGiftsResponse> searchGifts({
    required String query,
    TrendingGiftCategory? category,
    int limit = 20,
    int offset = 0,
  }) async {
    final queryParams = <String, dynamic>{
      'q': query,
      'limit': limit,
      'offset': offset,
    };
    if (category != null) {
      queryParams['category'] = category.name;
    }

    final response = await _apiClient.get<Map<String, dynamic>>(
      '/gifts/trending/search',
      queryParameters: queryParams,
    );
    return TrendingGiftsResponse.fromJson(response);
  }

  /// Get gift detail
  Future<TrendingGift> getGiftDetail(String giftId) async {
    final response = await _apiClient.get<Map<String, dynamic>>(
      '/gifts/trending/$giftId',
    );
    return TrendingGift.fromJson(response);
  }

  /// Get upcoming occasions with gift previews
  Future<List<OccasionWithGifts>> getUpcomingOccasions({
    int days = 30,
    int previewCount = 5,
  }) async {
    final response = await _apiClient.get<Map<String, dynamic>>(
      '/gifts/occasions/upcoming',
      queryParameters: {
        'days': days,
        'preview_count': previewCount,
      },
    );
    final items = response['items'] as List<dynamic>;
    return items
        .map((e) => OccasionWithGifts.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Get all occasions
  Future<List<Occasion>> getOccasions({int upcomingDays = 30}) async {
    final response = await _apiClient.get<Map<String, dynamic>>(
      '/gifts/occasions',
      queryParameters: {'upcoming_days': upcomingDays},
    );
    final items = response['items'] as List<dynamic>;
    return items
        .map((e) => Occasion.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Get gifts for an occasion
  Future<TrendingGiftsResponse> getOccasionGifts({
    required String occasionId,
    int limit = 10,
    int offset = 0,
  }) async {
    final response = await _apiClient.get<Map<String, dynamic>>(
      '/gifts/occasions/$occasionId/gifts',
      queryParameters: {'limit': limit, 'offset': offset},
    );
    return TrendingGiftsResponse.fromJson(response);
  }

  /// Save a gift
  Future<void> saveGift(String giftId, {String? note}) async {
    await _apiClient.post(
      '/gifts/saved',
      data: {
        'gift_id': giftId,
        if (note != null) 'note': note,
      },
    );
  }

  /// Unsave a gift
  Future<void> unsaveGift(String giftId) async {
    await _apiClient.delete('/gifts/saved/$giftId');
  }

  /// Get user's saved gifts
  Future<SavedGiftsResponse> getSavedGifts({
    int limit = 20,
    int offset = 0,
  }) async {
    final response = await _apiClient.get<Map<String, dynamic>>(
      '/gifts/saved',
      queryParameters: {'limit': limit, 'offset': offset},
    );
    return SavedGiftsResponse.fromJson(response);
  }
}

/// Response model for trending gifts list
class TrendingGiftsResponse {
  final List<TrendingGift> items;
  final int total;
  final int page;
  final int pageSize;
  final DateTime? lastUpdated;

  TrendingGiftsResponse({
    required this.items,
    required this.total,
    required this.page,
    required this.pageSize,
    this.lastUpdated,
  });

  factory TrendingGiftsResponse.fromJson(Map<String, dynamic> json) {
    return TrendingGiftsResponse(
      items: (json['items'] as List<dynamic>)
          .map((e) => TrendingGift.fromJson(e as Map<String, dynamic>))
          .toList(),
      total: json['total'] as int,
      page: json['page'] as int? ?? 0,
      pageSize: json['page_size'] as int? ?? 0,
      lastUpdated: json['last_updated'] != null
          ? DateTime.parse(json['last_updated'] as String)
          : null,
    );
  }
}

/// Response model for saved gifts
class SavedGiftsResponse {
  final List<SavedGift> items;
  final int total;
  final int page;
  final int pageSize;

  SavedGiftsResponse({
    required this.items,
    required this.total,
    required this.page,
    required this.pageSize,
  });

  factory SavedGiftsResponse.fromJson(Map<String, dynamic> json) {
    return SavedGiftsResponse(
      items: (json['items'] as List<dynamic>)
          .map((e) => SavedGift.fromJson(e as Map<String, dynamic>))
          .toList(),
      total: json['total'] as int,
      page: json['page'] as int? ?? 0,
      pageSize: json['page_size'] as int? ?? 0,
    );
  }
}

/// Saved gift model
class SavedGift {
  final String id;
  final TrendingGift gift;
  final DateTime savedAt;
  final String? note;

  SavedGift({
    required this.id,
    required this.gift,
    required this.savedAt,
    this.note,
  });

  factory SavedGift.fromJson(Map<String, dynamic> json) {
    return SavedGift(
      id: json['id'] as String,
      gift: TrendingGift.fromJson(json['gift'] as Map<String, dynamic>),
      savedAt: DateTime.parse(json['saved_at'] as String),
      note: json['note'] as String?,
    );
  }
}
