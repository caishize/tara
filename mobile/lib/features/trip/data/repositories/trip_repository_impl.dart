import 'dart:io';

import 'package:dartz/dartz.dart';
import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../domain/entities/trip.dart';
import '../../domain/entities/itinerary.dart';
import '../../domain/entities/trip_expense.dart';
import '../../domain/entities/smart_itinerary.dart';
import '../../domain/entities/trip_memory.dart';
import '../../domain/entities/destination_recommendation.dart';
import '../../domain/repositories/trip_repository.dart';
import '../datasources/trip_remote_datasource.dart';
import '../models/trip_model.dart';
import '../models/trip_context_model.dart';
import '../models/trip_detail_response_model.dart';
import '../models/itinerary_model.dart';
import '../models/trip_expense_model.dart';
import '../models/smart_itinerary_model.dart';

class TripRepositoryImpl implements TripRepository {
  final TripRemoteDataSource remoteDataSource;

  TripRepositoryImpl({required this.remoteDataSource});

  @override
  Future<Either<Failure, List<Trip>>> getTrips({
    String? familyId,
    TripStatus? status,
    TripCategory? category,
    int limit = 20,
    int offset = 0,
  }) async {
    try {
      final plans = await remoteDataSource.getTrips(
        familyId: familyId,
        status: status?.name,
        category: category?.name,
        limit: limit,
        offset: offset,
      );
      return Right(plans);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, Trip>> getTrip(String tripId) async {
    try {
      final plan = await remoteDataSource.getTrip(tripId);
      return Right(plan);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('Failed to parse trip: $e'));
    }
  }

  @override
  Future<Either<Failure, Trip>> createTrip(Trip plan) async {
    try {
      final model = TripModel.fromEntity(plan);
      final result = await remoteDataSource.createTrip(model);
      return Right(result);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, Trip>> updateTrip(String tripId, Trip plan) async {
    try {
      final model = TripModel.fromEntity(plan);
      final result = await remoteDataSource.updateTrip(tripId, model);
      return Right(result);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, void>> deleteTrip(String tripId) async {
    try {
      await remoteDataSource.deleteTrip(tripId);
      return const Right(null);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, List<DayItinerary>>> getItinerary(
      String tripId) async {
    try {
      final itinerary = await remoteDataSource.getItinerary(tripId);
      return Right(itinerary);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('Failed to parse itinerary: $e'));
    }
  }

  @override
  Future<Either<Failure, List<DayItinerary>>> generateItinerary(
    String tripId, {
    String? style,
  }) async {
    try {
      final itinerary =
          await remoteDataSource.generateItinerary(tripId, style: style);
      return Right(itinerary);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, List<DayItinerary>>> adjustItinerary(
    String tripId,
    String adjustment,
  ) async {
    try {
      final itinerary =
          await remoteDataSource.adjustItinerary(tripId, adjustment);
      return Right(itinerary);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, DayItinerary>> updateDayActivity(
    String tripId,
    int dayNumber,
    int activityIndex,
    ItineraryActivity activity,
  ) async {
    try {
      final activityModel = ItineraryActivityModel(
        time: activity.time,
        activityType: activity.activityType,
        title: activity.title,
        location: activity.location,
        description: activity.description,
        estimatedCost: activity.estimatedCost,
        bookingInfo: activity.bookingInfo,
        notes: activity.notes,
        professionalAdvice: activity.professionalAdvice,
        alternatives: activity.alternatives,
      );
      final result = await remoteDataSource.updateDayActivity(
        tripId,
        dayNumber,
        activityIndex,
        activityModel,
      );
      return Right(result);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, List<TripExpense>>> getExpenses(
    String tripId, {
    int limit = 50,
    int offset = 0,
  }) async {
    try {
      final expenses = await remoteDataSource.getExpenses(
        tripId,
        limit: limit,
        offset: offset,
      );
      return Right(expenses);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('Failed to get expenses: $e'));
    }
  }

  @override
  Future<Either<Failure, TripExpense>> createExpense(
    String tripId,
    TripExpense expense,
  ) async {
    try {
      final model = TripExpenseModel.fromEntity(expense);
      final result = await remoteDataSource.createExpense(tripId, model);
      return Right(result);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, TripExpense>> updateExpense(
    String tripId,
    String expenseId,
    TripExpense expense,
  ) async {
    try {
      final model = TripExpenseModel.fromEntity(expense);
      final result =
          await remoteDataSource.updateExpense(tripId, expenseId, model);
      return Right(result);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, void>> deleteExpense(
      String tripId, String expenseId) async {
    try {
      await remoteDataSource.deleteExpense(tripId, expenseId);
      return const Right(null);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, BudgetStatus>> getBudgetStatus(String tripId) async {
    try {
      final status = await remoteDataSource.getBudgetStatus(tripId);
      return Right(status);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('Failed to get budget status: $e'));
    }
  }

  // Destination Recommendations
  @override
  Future<Either<Failure, RecommendationResponse>>
      getDestinationRecommendations({
    required String familyId,
    String? occasion,
    double? budgetMin,
    double? budgetMax,
    int? durationDays,
    String? season,
    String? userInput,
  }) async {
    try {
      final result = await remoteDataSource.getDestinationRecommendations(
        familyId: familyId,
        occasion: occasion,
        budgetMin: budgetMin,
        budgetMax: budgetMax,
        durationDays: durationDays,
        season: season,
        userInput: userInput,
      );
      return Right(result);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  // Smart Itinerary
  @override
  Future<Either<Failure, SmartItineraryResponse>> generateSmartItinerary(
    String tripId,
    SmartItineraryRequest request,
  ) async {
    try {
      final requestModel = SmartItineraryRequestModel(
        styles: request.styles,
        familyComposition: request.familyComposition,
        preferences: request.preferences,
      );
      final result =
          await remoteDataSource.generateSmartItinerary(tripId, requestModel);
      return Right(result);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  // Activity CRUD
  @override
  Future<Either<Failure, void>> addActivity(
    String tripId,
    int dayNumber,
    String time,
    String title, {
    String? activityType,
    String? location,
    String? description,
    double? estimatedCost,
  }) async {
    try {
      final request = ActivityCreateRequest(
        time: time,
        title: title,
        activityType: activityType,
        location: location,
        description: description,
        estimatedCost: estimatedCost,
      );
      await remoteDataSource.addActivity(tripId, dayNumber, request);
      return const Right(null);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, void>> deleteActivity(
    String tripId,
    int dayNumber,
    int activityIndex,
  ) async {
    try {
      await remoteDataSource.deleteActivity(tripId, dayNumber, activityIndex);
      return const Right(null);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, void>> swapDays(
    String tripId,
    int sourceDay,
    int targetDay,
  ) async {
    try {
      await remoteDataSource.swapDays(tripId, sourceDay, targetDay);
      return const Right(null);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  // Memories
  @override
  Future<Either<Failure, List<TripMemory>>> getMemories(
    String tripId, {
    int limit = 20,
    int offset = 0,
  }) async {
    try {
      final memories = await remoteDataSource.getMemories(
        tripId,
        limit: limit,
        offset: offset,
      );
      return Right(memories);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, TripMemory>> uploadMemory(
    String tripId,
    File file,
    String? caption,
    int? rating,
  ) async {
    try {
      final result = await remoteDataSource.uploadMemory(
        tripId,
        file,
        caption,
        rating,
      );
      return Right(result);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, void>> deleteMemory(
      String tripId, String memoryId) async {
    try {
      await remoteDataSource.deleteMemory(tripId, memoryId);
      return const Right(null);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, void>> submitFeedback(
    String tripId,
    int rating,
    String? feedback,
  ) async {
    try {
      await remoteDataSource.submitFeedback(tripId, rating, feedback);
      return const Right(null);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, String>> exportPdf(String tripId) async {
    try {
      final pdfUrl = await remoteDataSource.exportPdf(tripId);
      return Right(pdfUrl);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    }
  }

  @override
  Future<Either<Failure, TripContextModel>> getTripContext(
      String tripId) async {
    try {
      final context = await remoteDataSource.fetchTripContext(tripId);
      return Right(context);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('Failed to get trip context: $e'));
    }
  }

  @override
  Future<Either<Failure, List<TripPrepItemModel>>> togglePreparationItem({
    required String curatedEventId,
    required String itemKey,
    required bool done,
  }) async {
    try {
      final items = await remoteDataSource.togglePreparationItem(
        eventId: curatedEventId,
        itemKey: itemKey,
        done: done,
      );
      return Right(items);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('Failed to toggle preparation item: $e'));
    }
  }

  @override
  Future<Either<Failure, Map<String, dynamic>>> getEventContext(
      String eventId) async {
    try {
      final response = await remoteDataSource.fetchEventContext(eventId);
      return Right({
        'associations': response.associations,
        'related_memories': response.relatedMemories,
      });
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('Failed to get event context: $e'));
    }
  }

  @override
  Future<Either<Failure, TripDetailResponseModel>> getTripDetail(
      String tripId) async {
    try {
      final detail = await remoteDataSource.fetchTripDetail(tripId);
      return Right(detail);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('Failed to get trip detail: $e'));
    }
  }
}
