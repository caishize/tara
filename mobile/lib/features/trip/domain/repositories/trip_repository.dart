import 'dart:io';

import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/trip.dart';
import '../entities/itinerary.dart';
import '../entities/trip_expense.dart';
import '../entities/smart_itinerary.dart';
import '../entities/trip_memory.dart';
import '../entities/destination_recommendation.dart';
import '../../data/models/trip_context_model.dart';
import '../../data/models/trip_detail_response_model.dart';

abstract class TripRepository {
  // Travel Plans
  Future<Either<Failure, List<Trip>>> getTrips({
    String? familyId,
    TripStatus? status,
    TripCategory? category,
    int limit = 20,
    int offset = 0,
  });

  Future<Either<Failure, Trip>> getTrip(String tripId);

  Future<Either<Failure, Trip>> createTrip(Trip plan);

  Future<Either<Failure, Trip>> updateTrip(String tripId, Trip plan);

  Future<Either<Failure, void>> deleteTrip(String tripId);

  // Itinerary
  Future<Either<Failure, List<DayItinerary>>> getItinerary(String tripId);

  Future<Either<Failure, List<DayItinerary>>> generateItinerary(
    String tripId, {
    String? style,
  });

  Future<Either<Failure, List<DayItinerary>>> adjustItinerary(
    String tripId,
    String adjustment,
  );

  Future<Either<Failure, DayItinerary>> updateDayActivity(
    String tripId,
    int dayNumber,
    int activityIndex,
    ItineraryActivity activity,
  );

  // Expenses
  Future<Either<Failure, List<TripExpense>>> getExpenses(
    String tripId, {
    int limit = 50,
    int offset = 0,
  });

  Future<Either<Failure, TripExpense>> createExpense(
    String tripId,
    TripExpense expense,
  );

  Future<Either<Failure, TripExpense>> updateExpense(
    String tripId,
    String expenseId,
    TripExpense expense,
  );

  Future<Either<Failure, void>> deleteExpense(String tripId, String expenseId);

  Future<Either<Failure, BudgetStatus>> getBudgetStatus(String tripId);

  // Destination Recommendations
  Future<Either<Failure, RecommendationResponse>>
      getDestinationRecommendations({
    required String familyId,
    String? occasion,
    double? budgetMin,
    double? budgetMax,
    int? durationDays,
    String? season,
    String? userInput,
  });

  // Smart Itinerary
  Future<Either<Failure, SmartItineraryResponse>> generateSmartItinerary(
    String tripId,
    SmartItineraryRequest request,
  );

  // Activity CRUD
  Future<Either<Failure, void>> addActivity(
    String tripId,
    int dayNumber,
    String time,
    String title, {
    String? activityType,
    String? location,
    String? description,
    double? estimatedCost,
  });

  Future<Either<Failure, void>> deleteActivity(
    String tripId,
    int dayNumber,
    int activityIndex,
  );

  Future<Either<Failure, void>> swapDays(
    String tripId,
    int sourceDay,
    int targetDay,
  );

  // Memories
  Future<Either<Failure, List<TripMemory>>> getMemories(
    String tripId, {
    int limit = 20,
    int offset = 0,
  });

  Future<Either<Failure, TripMemory>> uploadMemory(
    String tripId,
    File file,
    String? caption,
    int? rating,
  );

  Future<Either<Failure, void>> deleteMemory(String tripId, String memoryId);

  Future<Either<Failure, void>> submitFeedback(
    String tripId,
    int rating,
    String? feedback,
  );

  Future<Either<Failure, String>> exportPdf(String tripId);

  /// Fetch enriched trip context (participants, weather, prep items).
  Future<Either<Failure, TripContextModel>> getTripContext(String tripId);

  /// Toggle a preparation checklist item's done status.
  Future<Either<Failure, List<TripPrepItemModel>>> togglePreparationItem({
    required String curatedEventId,
    required String itemKey,
    required bool done,
  });

  /// Fetch associated events and related memories for a kanban event.
  Future<Either<Failure, Map<String, dynamic>>> getEventContext(String eventId);

  /// Fetch aggregated trip detail (plan + itineraries + expenses + context).
  Future<Either<Failure, TripDetailResponseModel>> getTripDetail(String tripId);
}
