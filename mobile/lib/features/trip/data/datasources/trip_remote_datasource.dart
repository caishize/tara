import 'dart:io';

import 'package:dio/dio.dart';

import '../../../../core/network/api_client.dart';
import '../models/trip_model.dart';
import '../models/itinerary_model.dart';
import '../models/trip_expense_model.dart';
import '../models/smart_itinerary_model.dart';
import '../models/trip_memory_model.dart';
import '../models/destination_recommendation_model.dart';
import '../models/trip_context_model.dart';
import '../models/association_summary_model.dart';
import '../models/related_memory_model.dart';
import '../models/trip_detail_response_model.dart';

abstract class TripRemoteDataSource {
  // Trips
  Future<List<TripModel>> getTrips({
    String? familyId,
    String? status,
    String? category,
    int limit = 20,
    int offset = 0,
  });

  Future<TripModel> getTrip(String tripId);

  Future<TripModel> createTrip(TripModel plan);

  Future<TripModel> updateTrip(String tripId, TripModel plan);

  Future<void> deleteTrip(String tripId);

  // Itinerary
  Future<List<DayItineraryModel>> getItinerary(String tripId);

  Future<List<DayItineraryModel>> generateItinerary(String tripId,
      {String? style});

  Future<List<DayItineraryModel>> adjustItinerary(
      String tripId, String adjustment);

  Future<DayItineraryModel> updateDayActivity(
    String tripId,
    int dayNumber,
    int activityIndex,
    ItineraryActivityModel activity,
  );

  // Expenses
  Future<List<TripExpenseModel>> getExpenses(
    String tripId, {
    int limit = 50,
    int offset = 0,
  });

  Future<TripExpenseModel> createExpense(
      String tripId, TripExpenseModel expense);

  Future<TripExpenseModel> updateExpense(
    String tripId,
    String expenseId,
    TripExpenseModel expense,
  );

  Future<void> deleteExpense(String tripId, String expenseId);

  Future<BudgetStatusModel> getBudgetStatus(String tripId);

  // Destination Recommendations
  Future<RecommendationResponseModel> getDestinationRecommendations({
    required String familyId,
    String? occasion,
    double? budgetMin,
    double? budgetMax,
    int? durationDays,
    String? season,
    String? userInput,
  });

  // Smart Itinerary
  Future<SmartItineraryResponseModel> generateSmartItinerary(
    String tripId,
    SmartItineraryRequestModel request,
  );

  // Activity CRUD
  Future<IncrementalUpdateResponse> addActivity(
    String tripId,
    int dayNumber,
    ActivityCreateRequest request,
  );

  Future<IncrementalUpdateResponse> deleteActivity(
    String tripId,
    int dayNumber,
    int activityIndex,
  );

  Future<IncrementalUpdateResponse> swapDays(
    String tripId,
    int sourceDay,
    int targetDay,
  );

  // Memories
  Future<List<TripMemoryModel>> getMemories(
    String tripId, {
    int limit = 20,
    int offset = 0,
  });

  Future<TripMemoryModel> uploadMemory(
    String tripId,
    File file,
    String? caption,
    int? rating,
  );

  Future<void> deleteMemory(String tripId, String memoryId);

  Future<void> submitFeedback(String tripId, int rating, String? feedback);

  Future<String> exportPdf(String tripId);

  /// Fetch enriched trip context (participants, weather, prep items).
  Future<TripContextModel> fetchTripContext(String tripId);

  /// Toggle preparation item state on the linked curated event.
  Future<List<TripPrepItemModel>> togglePreparationItem({
    required String eventId,
    required String itemKey,
    required bool done,
  });

  /// Fetch associated events and related memories for a kanban event.
  Future<EventContextResponse> fetchEventContext(String eventId);

  /// Fetch aggregated trip detail (plan + itineraries + expenses + context).
  Future<TripDetailResponseModel> fetchTripDetail(String tripId);
}

/// Response containing associations and related memories for an event.
class EventContextResponse {
  final List<AssociationSummaryModel> associations;
  final List<RelatedMemoryModel> relatedMemories;

  const EventContextResponse({
    this.associations = const [],
    this.relatedMemories = const [],
  });

  factory EventContextResponse.fromJson(Map<String, dynamic> json) {
    return EventContextResponse(
      associations: (json['associations'] as List<dynamic>?)
              ?.map((e) =>
                  AssociationSummaryModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      relatedMemories: (json['related_memories'] as List<dynamic>?)
              ?.map(
                  (e) => RelatedMemoryModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }
}

class TripRemoteDataSourceImpl implements TripRemoteDataSource {
  final ApiClient _apiClient;

  TripRemoteDataSourceImpl(this._apiClient);

  static const String _basePath = '/trips/plans';

  @override
  Future<List<TripModel>> getTrips({
    String? familyId,
    String? status,
    String? category,
    int limit = 20,
    int offset = 0,
  }) async {
    final queryParams = <String, dynamic>{
      'limit': limit,
      'offset': offset,
    };
    if (familyId != null) queryParams['family_id'] = familyId;
    if (status != null) queryParams['status'] = status;
    if (category != null) queryParams['category'] = category;

    return await _apiClient.get<List<TripModel>>(
      _basePath,
      queryParameters: queryParams,
      parser: (data) {
        final items = data['items'] as List? ?? data as List? ?? [];
        return items
            .map((e) => TripModel.fromJson(e as Map<String, dynamic>))
            .toList();
      },
    );
  }

  @override
  Future<TripModel> getTrip(String tripId) async {
    return await _apiClient.get<TripModel>(
      '$_basePath/$tripId',
      parser: (data) => TripModel.fromJson(data as Map<String, dynamic>),
    );
  }

  @override
  Future<TripModel> createTrip(TripModel plan) async {
    return await _apiClient.post<TripModel>(
      _basePath,
      data: plan.toCreateJson(),
      parser: (data) => TripModel.fromJson(data as Map<String, dynamic>),
    );
  }

  @override
  Future<TripModel> updateTrip(String tripId, TripModel plan) async {
    return await _apiClient.put<TripModel>(
      '$_basePath/$tripId',
      data: plan.toJson(),
      parser: (data) => TripModel.fromJson(data as Map<String, dynamic>),
    );
  }

  @override
  Future<void> deleteTrip(String tripId) async {
    await _apiClient.delete('$_basePath/$tripId');
  }

  @override
  Future<List<DayItineraryModel>> getItinerary(String tripId) async {
    return await _apiClient.get<List<DayItineraryModel>>(
      '$_basePath/$tripId/itinerary',
      parser: (data) {
        final items = data['items'] as List? ?? data as List? ?? [];
        return items
            .map((e) => DayItineraryModel.fromJson(e as Map<String, dynamic>))
            .toList();
      },
    );
  }

  @override
  Future<List<DayItineraryModel>> generateItinerary(String tripId,
      {String? style}) async {
    final endpoint = style != null
        ? '$_basePath/$tripId/itinerary/generate-smart'
        : '$_basePath/$tripId/itinerary/generate';

    return await _apiClient.post<List<DayItineraryModel>>(
      endpoint,
      data: style != null ? {'style': style} : null,
      parser: (data) {
        // Basic generate returns {itineraries: [...]}, smart returns different format
        final items = data['itineraries'] as List? ?? data as List? ?? [];
        return items
            .map((e) => DayItineraryModel.fromJson(e as Map<String, dynamic>))
            .toList();
      },
    );
  }

  @override
  Future<List<DayItineraryModel>> adjustItinerary(
      String tripId, String adjustment) async {
    return await _apiClient.post<List<DayItineraryModel>>(
      '$_basePath/$tripId/itinerary/adjust',
      data: {'adjustment_request': adjustment},
      parser: (data) {
        // Backend returns suggestions, not itineraries directly
        // Return empty list for now - this feature needs redesign
        if (data is List) {
          return data
              .map((e) => DayItineraryModel.fromJson(e as Map<String, dynamic>))
              .toList();
        }
        return [];
      },
    );
  }

  @override
  Future<DayItineraryModel> updateDayActivity(
    String tripId,
    int dayNumber,
    int activityIndex,
    ItineraryActivityModel activity,
  ) async {
    return await _apiClient.put<DayItineraryModel>(
      '$_basePath/$tripId/itinerary/day/$dayNumber/activity',
      data: {
        'activity_index': activityIndex,
        'activity': activity.toJson(),
      },
      parser: (data) =>
          DayItineraryModel.fromJson(data as Map<String, dynamic>),
    );
  }

  @override
  Future<List<TripExpenseModel>> getExpenses(
    String tripId, {
    int limit = 50,
    int offset = 0,
  }) async {
    return await _apiClient.get<List<TripExpenseModel>>(
      '$_basePath/$tripId/expenses',
      queryParameters: {'limit': limit, 'offset': offset},
      parser: (data) {
        final items = data['items'] as List? ?? data as List? ?? [];
        return items
            .map((e) => TripExpenseModel.fromJson(e as Map<String, dynamic>))
            .toList();
      },
    );
  }

  @override
  Future<TripExpenseModel> createExpense(
      String tripId, TripExpenseModel expense) async {
    return await _apiClient.post<TripExpenseModel>(
      '$_basePath/$tripId/expenses',
      data: expense.toCreateJson(),
      parser: (data) => TripExpenseModel.fromJson(data as Map<String, dynamic>),
    );
  }

  @override
  Future<TripExpenseModel> updateExpense(
    String tripId,
    String expenseId,
    TripExpenseModel expense,
  ) async {
    return await _apiClient.put<TripExpenseModel>(
      '$_basePath/$tripId/expenses/$expenseId',
      data: expense.toJson(),
      parser: (data) => TripExpenseModel.fromJson(data as Map<String, dynamic>),
    );
  }

  @override
  Future<void> deleteExpense(String tripId, String expenseId) async {
    await _apiClient.delete('$_basePath/$tripId/expenses/$expenseId');
  }

  @override
  Future<BudgetStatusModel> getBudgetStatus(String tripId) async {
    return await _apiClient.get<BudgetStatusModel>(
      '$_basePath/$tripId/expenses/budget-status',
      parser: (data) =>
          BudgetStatusModel.fromJson(data as Map<String, dynamic>),
    );
  }

  // Destination Recommendations
  @override
  Future<RecommendationResponseModel> getDestinationRecommendations({
    required String familyId,
    String? occasion,
    double? budgetMin,
    double? budgetMax,
    int? durationDays,
    String? season,
    String? userInput,
  }) async {
    final data = <String, dynamic>{
      'family_id': familyId,
    };
    if (occasion != null) data['occasion'] = occasion;
    if (budgetMin != null) data['budget_min'] = budgetMin;
    if (budgetMax != null) data['budget_max'] = budgetMax;
    if (durationDays != null) data['duration_days'] = durationDays;
    if (season != null) data['season'] = season;
    if (userInput != null) data['user_input'] = userInput;

    // Destination recommendation uses AI and can take time
    return await _apiClient.post<RecommendationResponseModel>(
      '/trips/recommend',
      data: data,
      parser: (data) =>
          RecommendationResponseModel.fromJson(data as Map<String, dynamic>),
      timeout: const Duration(minutes: 3),
    );
  }

  // Smart Itinerary
  @override
  Future<SmartItineraryResponseModel> generateSmartItinerary(
    String tripId,
    SmartItineraryRequestModel request,
  ) async {
    // Smart itinerary generation can take 5-10 minutes due to AI processing
    // Use a 10-minute timeout to match the backend timeout (600 seconds)
    return await _apiClient.post<SmartItineraryResponseModel>(
      '$_basePath/$tripId/itinerary/generate-smart',
      data: request.toJson(),
      parser: (data) =>
          SmartItineraryResponseModel.fromJson(data as Map<String, dynamic>),
      timeout: const Duration(minutes: 10),
    );
  }

  // Activity CRUD
  @override
  Future<IncrementalUpdateResponse> addActivity(
    String tripId,
    int dayNumber,
    ActivityCreateRequest request,
  ) async {
    return await _apiClient.post<IncrementalUpdateResponse>(
      '$_basePath/$tripId/itinerary/day/$dayNumber/activity',
      data: request.toJson(),
      parser: (data) =>
          IncrementalUpdateResponse.fromJson(data as Map<String, dynamic>),
    );
  }

  @override
  Future<IncrementalUpdateResponse> deleteActivity(
    String tripId,
    int dayNumber,
    int activityIndex,
  ) async {
    return await _apiClient.delete<IncrementalUpdateResponse>(
      '$_basePath/$tripId/itinerary/day/$dayNumber/activity/$activityIndex',
      parser: (data) =>
          IncrementalUpdateResponse.fromJson(data as Map<String, dynamic>),
    );
  }

  @override
  Future<IncrementalUpdateResponse> swapDays(
    String tripId,
    int sourceDay,
    int targetDay,
  ) async {
    return await _apiClient.post<IncrementalUpdateResponse>(
      '$_basePath/$tripId/itinerary/swap-days',
      data: {
        'source_day': sourceDay,
        'target_day': targetDay,
      },
      parser: (data) =>
          IncrementalUpdateResponse.fromJson(data as Map<String, dynamic>),
    );
  }

  // Memories
  @override
  Future<List<TripMemoryModel>> getMemories(
    String tripId, {
    int limit = 20,
    int offset = 0,
  }) async {
    return await _apiClient.get<List<TripMemoryModel>>(
      '$_basePath/$tripId/memories',
      queryParameters: {'limit': limit, 'offset': offset},
      parser: (data) {
        final items = data['items'] as List? ?? data as List? ?? [];
        return items
            .map((e) => TripMemoryModel.fromJson(e as Map<String, dynamic>))
            .toList();
      },
    );
  }

  @override
  Future<TripMemoryModel> uploadMemory(
    String tripId,
    File file,
    String? caption,
    int? rating,
  ) async {
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(
        file.path,
        filename: file.path.split('/').last,
      ),
      if (caption != null) 'caption': caption,
      if (rating != null) 'rating': rating,
    });

    return await _apiClient.postMultipart<TripMemoryModel>(
      '$_basePath/$tripId/memories/upload',
      formData: formData,
      parser: (data) => TripMemoryModel.fromJson(data as Map<String, dynamic>),
    );
  }

  @override
  Future<void> deleteMemory(String tripId, String memoryId) async {
    await _apiClient.delete('$_basePath/$tripId/memories/$memoryId');
  }

  @override
  Future<void> submitFeedback(
      String tripId, int rating, String? feedback) async {
    await _apiClient.post(
      '$_basePath/$tripId/feedback',
      data: {
        'rating': rating,
        if (feedback != null) 'feedback': feedback,
      },
    );
  }

  @override
  Future<String> exportPdf(String tripId) async {
    final result = await _apiClient.post<Map<String, dynamic>>(
      '$_basePath/$tripId/memories/export-pdf',
      parser: (data) => data as Map<String, dynamic>,
    );
    return result['pdf_url'] ?? '';
  }

  @override
  Future<TripContextModel> fetchTripContext(String tripId) async {
    return await _apiClient.get<TripContextModel>(
      '$_basePath/$tripId/context',
      parser: (data) => TripContextModel.fromJson(data as Map<String, dynamic>),
    );
  }

  @override
  Future<List<TripPrepItemModel>> togglePreparationItem({
    required String eventId,
    required String itemKey,
    required bool done,
  }) async {
    final response = await _apiClient.patch<Map<String, dynamic>>(
      '/kanban/events/$eventId/preparation',
      data: {
        'item_key': itemKey,
        'done': done,
      },
    );
    final items = (response['preparation_items'] as List<dynamic>?) ??
        (response['items'] as List<dynamic>?) ??
        const [];
    return items
        .map((item) => TripPrepItemModel.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<EventContextResponse> fetchEventContext(String eventId) async {
    return await _apiClient.get<EventContextResponse>(
      '/kanban/events/$eventId/context',
      parser: (data) =>
          EventContextResponse.fromJson(data as Map<String, dynamic>),
    );
  }

  @override
  Future<TripDetailResponseModel> fetchTripDetail(String tripId) async {
    return await _apiClient.get<TripDetailResponseModel>(
      '$_basePath/$tripId/detail',
      parser: (data) =>
          TripDetailResponseModel.fromJson(data as Map<String, dynamic>),
    );
  }
}
