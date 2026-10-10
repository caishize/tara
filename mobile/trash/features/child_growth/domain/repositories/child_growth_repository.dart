import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/growth_record.dart';
import '../entities/milestone.dart';
import '../entities/vaccine.dart';

/// 小孩成长仓库接口
abstract class ChildGrowthRepository {
  // ==================== 成长记录 ====================

  /// 添加成长记录
  Future<Either<Failure, GrowthRecord>> addGrowthRecord({
    required String childId,
    required DateTime recordDate,
    double? height,
    double? weight,
    double? headCircumference,
    String? notes,
  });

  /// 获取成长曲线数据
  Future<Either<Failure, GrowthCurveData>> getGrowthCurveData(String childId);

  // ==================== 里程碑 ====================

  /// 添加里程碑
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
  });

  /// 获取里程碑列表
  Future<Either<Failure, List<Milestone>>> getMilestones(String childId);

  // ==================== 疫苗 ====================

  /// 获取疫苗记录列表
  Future<Either<Failure, List<VaccineRecord>>> getVaccines(String childId);

  /// 更新疫苗状态
  Future<Either<Failure, VaccineRecord>> updateVaccineStatus({
    required String vaccineId,
    required VaccineStatus status,
    DateTime? actualDate,
    String? location,
    String? batchNumber,
    String? notes,
  });
}
