import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../../../../core/error/exceptions.dart';
import '../../domain/entities/growth_record.dart';
import '../../domain/entities/milestone.dart';
import '../../domain/entities/vaccine.dart';
import '../../domain/repositories/child_growth_repository.dart';
import '../datasources/child_growth_remote_datasource.dart';

/// 小孩成长仓库实现
class ChildGrowthRepositoryImpl implements ChildGrowthRepository {
  final ChildGrowthRemoteDataSource remoteDataSource;

  ChildGrowthRepositoryImpl({required this.remoteDataSource});

  // ==================== 成长记录 ====================

  @override
  Future<Either<Failure, GrowthRecord>> addGrowthRecord({
    required String childId,
    required DateTime recordDate,
    double? height,
    double? weight,
    double? headCircumference,
    String? notes,
  }) async {
    try {
      final response = await remoteDataSource.addGrowthRecord(
        childId: childId,
        recordDate: recordDate,
        height: height,
        weight: weight,
        headCircumference: headCircumference,
        notes: notes,
      );

      // 后端返回的是 { records: [...], count: N }
      final records = response['records'] as List<dynamic>? ?? [];
      if (records.isEmpty) {
        return const Left(ServerFailure('未能创建成长记录'));
      }

      // 构建一个合并的记录用于返回
      final record = GrowthRecord(
        id: records.first['id']?.toString() ?? '',
        childId: childId,
        recordDate: recordDate,
        height: height,
        weight: weight,
        headCircumference: headCircumference,
        notes: notes,
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
      );

      return Right(record);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, GrowthCurveData>> getGrowthCurveData(String childId) async {
    try {
      final data = await remoteDataSource.getGrowthCurveData(childId);
      return Right(data);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  // ==================== 里程碑 ====================

  @override
  Future<Either<Failure, Milestone>> addMilestone({
    required String childId,
    required MilestoneType type,
    required String title,
    required DateTime achievedDate,
    String? description,
    String? photoUrl,
    String? videoUrl,
    String? notes,
    int? ageMonths,
  }) async {
    try {
      final milestone = await remoteDataSource.addMilestone(
        childId: childId,
        milestoneType: _milestoneTypeToString(type),
        title: title,
        achievedDate: achievedDate,
        description: description,
        photoUrl: photoUrl,
        videoUrl: videoUrl,
        notes: notes,
      );
      return Right(milestone);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, List<Milestone>>> getMilestones(String childId) async {
    try {
      final milestones = await remoteDataSource.getMilestones(childId);
      return Right(milestones);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  // ==================== 疫苗 ====================

  @override
  Future<Either<Failure, List<VaccineRecord>>> getVaccines(String childId) async {
    try {
      final vaccines = await remoteDataSource.getVaccines(childId);
      return Right(vaccines);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, VaccineRecord>> updateVaccineStatus({
    required String vaccineId,
    required VaccineStatus status,
    DateTime? actualDate,
    String? location,
    String? batchNumber,
    String? notes,
  }) async {
    try {
      final vaccine = await remoteDataSource.updateVaccineStatus(
        vaccineId: vaccineId,
        status: _vaccineStatusToString(status),
        actualDate: actualDate,
        location: location,
        batchNumber: batchNumber,
        notes: notes,
      );
      return Right(vaccine);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  String _milestoneTypeToString(MilestoneType type) {
    switch (type) {
      case MilestoneType.physical:
        return 'physical';
      case MilestoneType.cognitive:
        return 'cognitive';
      case MilestoneType.language:
        return 'language';
      case MilestoneType.social:
        return 'social';
      case MilestoneType.emotional:
        return 'emotional';
    }
  }

  String _vaccineStatusToString(VaccineStatus status) {
    switch (status) {
      case VaccineStatus.scheduled:
        return 'scheduled';
      case VaccineStatus.completed:
        return 'completed';
      case VaccineStatus.overdue:
        return 'overdue';
      case VaccineStatus.skipped:
        return 'skipped';
    }
  }
}
