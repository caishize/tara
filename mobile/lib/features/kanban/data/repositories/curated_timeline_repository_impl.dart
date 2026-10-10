import 'package:dartz/dartz.dart';
import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../domain/entities/curated_event.dart';
import '../../domain/entities/memory_lane.dart';
import '../../domain/repositories/curated_timeline_repository.dart';
import '../datasources/curated_timeline_datasource.dart';
import '../models/kanban_models.dart';

/// 整理后时光轴仓库实现
class CuratedTimelineRepositoryImpl implements CuratedTimelineRepository {
  final CuratedTimelineRemoteDataSource remoteDataSource;

  CuratedTimelineRepositoryImpl({required this.remoteDataSource});

  @override
  Future<Either<Failure, CuratedTimeline>> getCuratedTimeline({
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    try {
      final timeline = await remoteDataSource.fetchCuratedTimeline(
        startDate: startDate,
        endDate: endDate,
      );
      return Right(timeline);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, CurationJobStatus>> requestCuration({
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    try {
      final status = await remoteDataSource.requestCuration(
        startDate: startDate,
        endDate: endDate,
      );
      return Right(status);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, CurationJobStatus>> getCurationJobStatus(
    String jobId,
  ) async {
    try {
      final status = await remoteDataSource.getCurationJobStatus(jobId);
      return Right(status);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, DirectionalTimelineResponse>> getDirectionalTimeline({
    required TimelineDirection direction,
    int days = 14,
    String? cursor,
  }) async {
    try {
      final response = await remoteDataSource.fetchDirectionalTimeline(
        direction: direction,
        days: days,
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
  Future<Either<Failure, bool>> updateEventStatus({
    required String eventId,
    required String status,
  }) async {
    try {
      final success = await remoteDataSource.updateEventStatus(
        eventId: eventId,
        status: status,
      );
      return Right(success);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, bool>> cancelEvent({
    required String eventId,
    required String eventTitle,
  }) async {
    try {
      final success = await remoteDataSource.cancelEvent(
        eventId: eventId,
        eventTitle: eventTitle,
      );
      return Right(success);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, void>> createEvent({
    required String title,
    required DateTime startTime,
    DateTime? endTime,
    String? eventType,
    String? location,
    String priority = 'normal',
    String? notes,
    List<String> tags = const [],
  }) async {
    try {
      await remoteDataSource.createEvent(
        title: title,
        startTime: startTime,
        endTime: endTime,
        eventType: eventType,
        location: location,
        priority: priority,
        notes: notes,
        tags: tags,
      );
      return const Right(null);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, KanbanResponseModel>> getKanban() async {
    try {
      final kanban = await remoteDataSource.fetchKanban();
      return Right(kanban);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, List<PreparationItemModel>>> togglePreparationItem({
    required String eventId,
    required int itemIndex,
    String? itemKey,
    required bool done,
  }) async {
    try {
      final items = await remoteDataSource.togglePreparationItem(
        eventId: eventId,
        itemIndex: itemIndex,
        itemKey: itemKey,
        done: done,
      );
      return Right(items);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, MemoryLaneResponse>> getMemoryLane({int? year}) async {
    try {
      final response = await remoteDataSource.fetchMemoryLane(year: year);
      return Right(response);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, OnThisDayResponse>> getOnThisDay() async {
    try {
      final response = await remoteDataSource.fetchOnThisDay();
      return Right(response);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, EventSearchResponse>> searchEvents({
    required String query,
    List<String>? eventTypes,
    int limit = 20,
  }) async {
    try {
      final response = await remoteDataSource.searchEvents(
        query: query,
        eventTypes: eventTypes,
        limit: limit,
      );
      return Right(response);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

}
