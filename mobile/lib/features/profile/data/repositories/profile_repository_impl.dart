import 'package:dartz/dartz.dart';

import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../domain/entities/user_stats.dart';
import '../../domain/entities/smart_service.dart';
import '../../domain/repositories/profile_repository.dart';
import '../datasources/profile_remote_datasource.dart';

class ProfileRepositoryImpl implements ProfileRepository {
  final ProfileRemoteDataSource remoteDataSource;

  ProfileRepositoryImpl({
    required this.remoteDataSource,
  });

  @override
  Future<Either<Failure, UserStats>> getUserStats() async {
    try {
      final stats = await remoteDataSource.getUserStats();
      return Right(stats);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return const Left(ServerFailure('获取用户统计数据失败'));
    }
  }

  @override
  Future<Either<Failure, SmartServicesSummary>> getSmartServices() async {
    try {
      final services = await remoteDataSource.getSmartServices();
      return Right(services);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return const Left(ServerFailure('获取智能服务状态失败'));
    }
  }

  @override
  Future<Either<Failure, void>> pauseService(String serviceId) async {
    try {
      await remoteDataSource.pauseService(serviceId);
      return const Right(null);
    } on NotFoundException {
      return const Left(NotFoundFailure('服务不存在'));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return const Left(ServerFailure('暂停服务失败'));
    }
  }

  @override
  Future<Either<Failure, void>> resumeService(String serviceId) async {
    try {
      await remoteDataSource.resumeService(serviceId);
      return const Right(null);
    } on NotFoundException {
      return const Left(NotFoundFailure('服务不存在'));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return const Left(ServerFailure('恢复服务失败'));
    }
  }

  @override
  Future<Either<Failure, void>> triggerServiceJob(
      String serviceId, String jobName) async {
    try {
      await remoteDataSource.triggerServiceJob(serviceId, jobName);
      return const Right(null);
    } on NotFoundException {
      return const Left(NotFoundFailure('服务或任务不存在'));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return const Left(ServerFailure('触发任务失败'));
    }
  }
}
