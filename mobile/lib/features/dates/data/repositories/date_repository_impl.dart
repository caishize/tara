import 'package:dartz/dartz.dart';
import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../domain/entities/important_date.dart';
import '../../domain/repositories/date_repository.dart';
import '../datasources/date_remote_datasource.dart';
import '../models/important_date_model.dart';

class DateRepositoryImpl implements DateRepository {
  final DateRemoteDataSource remoteDataSource;

  DateRepositoryImpl({required this.remoteDataSource});

  @override
  Future<Either<Failure, List<ImportantDate>>> getDates({
    String? memberId,
    DateType? dateType,
  }) async {
    try {
      final dates = await remoteDataSource.getDates(
        memberId: memberId,
        dateType: dateType,
      );
      return Right(dates);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, List<ImportantDate>>> getUpcomingDates({
    int daysAhead = 30,
  }) async {
    try {
      final dates = await remoteDataSource.getUpcomingDates(daysAhead: daysAhead);
      return Right(dates);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, ImportantDate>> getDateById(String id) async {
    try {
      final date = await remoteDataSource.getDateById(id);
      return Right(date);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, ImportantDate>> createDate(ImportantDate date) async {
    try {
      final model = ImportantDateModel.fromEntity(date);
      final result = await remoteDataSource.createDate(model);
      return Right(result);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, ImportantDate>> updateDate(ImportantDate date) async {
    try {
      final model = ImportantDateModel.fromEntity(date);
      final result = await remoteDataSource.updateDate(model);
      return Right(result);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, void>> deleteDate(String id) async {
    try {
      await remoteDataSource.deleteDate(id);
      return const Right(null);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }
}
