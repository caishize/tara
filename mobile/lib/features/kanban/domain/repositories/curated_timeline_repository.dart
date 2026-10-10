import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/curated_event.dart';
import '../entities/memory_lane.dart';
import '../../data/datasources/curated_timeline_datasource.dart';
import '../../data/models/kanban_models.dart';

/// 整理后时光轴仓库接口
abstract class CuratedTimelineRepository {
  /// 获取AI整理后的时光轴数据 (legacy)
  Future<Either<Failure, CuratedTimeline>> getCuratedTimeline({
    DateTime? startDate,
    DateTime? endDate,
  });

  /// 获取方向时间线 (新API)
  Future<Either<Failure, DirectionalTimelineResponse>> getDirectionalTimeline({
    required TimelineDirection direction,
    int days = 14,
    String? cursor,
  });

  /// 更新事件状态
  Future<Either<Failure, bool>> updateEventStatus({
    required String eventId,
    required String status,
  });

  /// 请求AI整理
  Future<Either<Failure, CurationJobStatus>> requestCuration({
    DateTime? startDate,
    DateTime? endDate,
  });

  /// 获取整理任务状态
  Future<Either<Failure, CurationJobStatus>> getCurationJobStatus(String jobId);

  /// 取消/删除事件
  Future<Either<Failure, bool>> cancelEvent({
    required String eventId,
    required String eventTitle,
  });

  /// 创建用户事件
  Future<Either<Failure, void>> createEvent({
    required String title,
    required DateTime startTime,
    DateTime? endTime,
    String? eventType,
    String? location,
    String priority,
    String? notes,
    List<String> tags,
  });

  /// Fetch semantic kanban view
  Future<Either<Failure, KanbanResponseModel>> getKanban();

  /// Toggle a preparation item's done status
  Future<Either<Failure, List<PreparationItemModel>>> togglePreparationItem({
    required String eventId,
    required int itemIndex,
    String? itemKey,
    required bool done,
  });

  /// Fetch memory lane (past stories grouped by year)
  Future<Either<Failure, MemoryLaneResponse>> getMemoryLane({int? year});

  /// Fetch on-this-day items
  Future<Either<Failure, OnThisDayResponse>> getOnThisDay();

  /// Search events by query string
  Future<Either<Failure, EventSearchResponse>> searchEvents({
    required String query,
    List<String>? eventTypes,
    int limit,
  });

}
