import 'package:dartz/dartz.dart';
import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../domain/repositories/insight_feed_repository.dart';
import '../datasources/insight_feed_datasource.dart';
import '../models/future_view_models.dart';
import '../models/insight_feed_models.dart';

/// Implementation of [InsightFeedRepository].
///
/// Delegates to [InsightFeedRemoteDataSource] and wraps results in
/// `Either<Failure, T>` following the same pattern as other repositories.
class InsightFeedRepositoryImpl implements InsightFeedRepository {
  final InsightFeedRemoteDataSource remoteDataSource;

  InsightFeedRepositoryImpl({required this.remoteDataSource});

  @override
  Future<Either<Failure, InsightFeedResponseModel>> getInsightFeed({
    int limit = 20,
    String? cursor,
  }) async {
    try {
      final response = await remoteDataSource.fetchInsightFeed(
        limit: limit,
        cursor: cursor,
      );
      return Right(response);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, PendingActionResponseModel>> executeInsightAction({
    required String insightId,
    required String actionType,
    Map<String, dynamic>? actionData,
  }) async {
    try {
      final response = await remoteDataSource.executeInsightAction(
        insightId: insightId,
        actionType: actionType,
        actionData: actionData,
      );
      return Right(response);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, void>> confirmAction({
    required String actionId,
  }) async {
    try {
      await remoteDataSource.confirmAction(actionId: actionId);
      return const Right(null);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, void>> submitInsightFeedback({
    required String insightId,
    required String feedbackType,
    String? reason,
  }) async {
    try {
      await remoteDataSource.submitInsightFeedback(
        insightId: insightId,
        feedbackType: feedbackType,
        reason: reason,
      );
      return const Right(null);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, void>> adoptInsight({
    required String insightId,
    required String tripId,
  }) async {
    try {
      await remoteDataSource.adoptInsight(
        insightId: insightId,
        tripId: tripId,
      );
      return const Right(null);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, FutureViewResponseModel>> getFutureView() async {
    try {
      final response = await remoteDataSource.fetchFutureView();
      return Right(response);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, FutureViewUpcomingPageModel>> getMoreUpcoming({
    required int offset,
    int limit = 10,
  }) async {
    try {
      final response = await remoteDataSource.fetchMoreUpcoming(
        offset: offset,
        limit: limit,
      );
      return Right(response);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, void>> acceptSuggestionToTrip({
    required String tripId,
    required String itemText,
    String? insightId,
  }) async {
    try {
      await remoteDataSource.acceptSuggestionToTrip(
        tripId: tripId,
        itemText: itemText,
        insightId: insightId,
      );
      return const Right(null);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, void>> togglePreparationItem({
    required String tripId,
    required String taskId,
    required bool done,
  }) async {
    try {
      await remoteDataSource.togglePreparationItem(
        tripId: tripId,
        taskId: taskId,
        done: done,
      );
      return const Right(null);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, List<InsightFeedItemModel>>> getTripInsights({
    required String tripId,
  }) async {
    try {
      final response = await remoteDataSource.fetchTripInsights(
        tripId: tripId,
      );
      return Right(response);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }
}
