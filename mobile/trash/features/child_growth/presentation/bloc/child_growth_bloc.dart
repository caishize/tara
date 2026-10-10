import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';
import '../../domain/entities/growth_record.dart';
import '../../domain/entities/milestone.dart';
import '../../domain/entities/vaccine.dart';
import '../../domain/repositories/child_growth_repository.dart';

// ==================== Events ====================

abstract class ChildGrowthEvent extends Equatable {
  const ChildGrowthEvent();

  @override
  List<Object?> get props => [];
}

/// 加载成长数据
class ChildGrowthLoadRequested extends ChildGrowthEvent {
  final String childId;

  const ChildGrowthLoadRequested({required this.childId});

  @override
  List<Object?> get props => [childId];
}

/// 添加成长记录
class GrowthRecordAddRequested extends ChildGrowthEvent {
  final String childId;
  final DateTime recordDate;
  final double? height;
  final double? weight;
  final double? headCircumference;
  final String? notes;

  const GrowthRecordAddRequested({
    required this.childId,
    required this.recordDate,
    this.height,
    this.weight,
    this.headCircumference,
    this.notes,
  });

  @override
  List<Object?> get props => [childId, recordDate, height, weight, headCircumference, notes];
}

/// 添加里程碑
class MilestoneAddRequested extends ChildGrowthEvent {
  final String childId;
  final MilestoneType type;
  final String title;
  final DateTime achievedDate;
  final String? description;
  final String? photoUrl;
  final String? videoUrl;
  final String? notes;
  final int? ageMonths;

  const MilestoneAddRequested({
    required this.childId,
    required this.type,
    required this.title,
    required this.achievedDate,
    this.description,
    this.photoUrl,
    this.videoUrl,
    this.notes,
    this.ageMonths,
  });

  @override
  List<Object?> get props => [childId, type, title, achievedDate, description, photoUrl, videoUrl, notes, ageMonths];
}

/// 更新疫苗状态
class VaccineStatusUpdateRequested extends ChildGrowthEvent {
  final String vaccineId;
  final VaccineStatus status;
  final DateTime? actualDate;
  final String? location;
  final String? batchNumber;
  final String? notes;

  const VaccineStatusUpdateRequested({
    required this.vaccineId,
    required this.status,
    this.actualDate,
    this.location,
    this.batchNumber,
    this.notes,
  });

  @override
  List<Object?> get props => [vaccineId, status, actualDate, location, batchNumber, notes];
}

/// 切换当前Tab
class ChildGrowthTabChanged extends ChildGrowthEvent {
  final int tabIndex;

  const ChildGrowthTabChanged({required this.tabIndex});

  @override
  List<Object?> get props => [tabIndex];
}

// ==================== States ====================

abstract class ChildGrowthState extends Equatable {
  const ChildGrowthState();

  @override
  List<Object?> get props => [];
}

/// 初始状态
class ChildGrowthInitial extends ChildGrowthState {}

/// 加载中
class ChildGrowthLoading extends ChildGrowthState {}

/// 加载完成
class ChildGrowthLoaded extends ChildGrowthState {
  final String childId;
  final GrowthCurveData? growthCurveData;
  final List<Milestone> milestones;
  final List<VaccineRecord> vaccines;
  final int currentTabIndex;
  final bool isAddingRecord;
  final String? errorMessage;

  const ChildGrowthLoaded({
    required this.childId,
    this.growthCurveData,
    this.milestones = const [],
    this.vaccines = const [],
    this.currentTabIndex = 0,
    this.isAddingRecord = false,
    this.errorMessage,
  });

  /// 获取待接种疫苗数量
  int get pendingVaccinesCount => vaccines.where((v) => v.isScheduled || v.isOverdue).length;

  /// 获取已过期疫苗
  List<VaccineRecord> get overdueVaccines => vaccines.where((v) => v.isOverdue).toList();

  /// 获取即将到期疫苗（7天内）
  List<VaccineRecord> get upcomingVaccines =>
      vaccines.where((v) => v.isScheduled && v.daysUntil >= 0 && v.daysUntil <= 7).toList();

  /// 按类型分组的里程碑
  Map<MilestoneType, List<Milestone>> get milestonesByType {
    final map = <MilestoneType, List<Milestone>>{};
    for (final milestone in milestones) {
      map.putIfAbsent(milestone.type, () => []).add(milestone);
    }
    return map;
  }

  ChildGrowthLoaded copyWith({
    String? childId,
    GrowthCurveData? growthCurveData,
    List<Milestone>? milestones,
    List<VaccineRecord>? vaccines,
    int? currentTabIndex,
    bool? isAddingRecord,
    String? errorMessage,
  }) {
    return ChildGrowthLoaded(
      childId: childId ?? this.childId,
      growthCurveData: growthCurveData ?? this.growthCurveData,
      milestones: milestones ?? this.milestones,
      vaccines: vaccines ?? this.vaccines,
      currentTabIndex: currentTabIndex ?? this.currentTabIndex,
      isAddingRecord: isAddingRecord ?? this.isAddingRecord,
      errorMessage: errorMessage,
    );
  }

  @override
  List<Object?> get props => [
    childId, growthCurveData, milestones, vaccines,
    currentTabIndex, isAddingRecord, errorMessage,
  ];
}

/// 错误状态
class ChildGrowthError extends ChildGrowthState {
  final String message;

  const ChildGrowthError({required this.message});

  @override
  List<Object?> get props => [message];
}

// ==================== BLoC ====================

class ChildGrowthBloc extends Bloc<ChildGrowthEvent, ChildGrowthState> {
  final ChildGrowthRepository repository;

  ChildGrowthBloc({required this.repository}) : super(ChildGrowthInitial()) {
    on<ChildGrowthLoadRequested>(_onLoadRequested);
    on<GrowthRecordAddRequested>(_onAddGrowthRecord);
    on<MilestoneAddRequested>(_onAddMilestone);
    on<VaccineStatusUpdateRequested>(_onUpdateVaccineStatus);
    on<ChildGrowthTabChanged>(_onTabChanged);
  }

  Future<void> _onLoadRequested(
    ChildGrowthLoadRequested event,
    Emitter<ChildGrowthState> emit,
  ) async {
    emit(ChildGrowthLoading());

    // 并行加载所有数据
    final results = await Future.wait([
      repository.getGrowthCurveData(event.childId),
      repository.getMilestones(event.childId),
      repository.getVaccines(event.childId),
    ]);

    final growthResult = results[0];
    final milestonesResult = results[1];
    final vaccinesResult = results[2];

    GrowthCurveData? growthData;
    List<Milestone> milestones = [];
    List<VaccineRecord> vaccines = [];

    // 处理成长数据
    growthResult.fold(
      (failure) => null,
      (data) => growthData = data as GrowthCurveData,
    );

    // 处理里程碑数据
    milestonesResult.fold(
      (failure) => null,
      (data) => milestones = data as List<Milestone>,
    );

    // 处理疫苗数据
    vaccinesResult.fold(
      (failure) => null,
      (data) => vaccines = data as List<VaccineRecord>,
    );

    emit(ChildGrowthLoaded(
      childId: event.childId,
      growthCurveData: growthData,
      milestones: milestones,
      vaccines: vaccines,
    ));
  }

  Future<void> _onAddGrowthRecord(
    GrowthRecordAddRequested event,
    Emitter<ChildGrowthState> emit,
  ) async {
    if (state is! ChildGrowthLoaded) return;
    final currentState = state as ChildGrowthLoaded;

    emit(currentState.copyWith(isAddingRecord: true));

    final result = await repository.addGrowthRecord(
      childId: event.childId,
      recordDate: event.recordDate,
      height: event.height,
      weight: event.weight,
      headCircumference: event.headCircumference,
      notes: event.notes,
    );

    await result.fold(
      (failure) async {
        emit(currentState.copyWith(
          isAddingRecord: false,
          errorMessage: failure.message,
        ));
      },
      (record) async {
        // 重新加载成长数据
        final growthResult = await repository.getGrowthCurveData(event.childId);
        growthResult.fold(
          (failure) {
            emit(currentState.copyWith(isAddingRecord: false));
          },
          (data) {
            emit(currentState.copyWith(
              growthCurveData: data,
              isAddingRecord: false,
            ));
          },
        );
      },
    );
  }

  Future<void> _onAddMilestone(
    MilestoneAddRequested event,
    Emitter<ChildGrowthState> emit,
  ) async {
    if (state is! ChildGrowthLoaded) return;
    final currentState = state as ChildGrowthLoaded;

    emit(currentState.copyWith(isAddingRecord: true));

    final result = await repository.addMilestone(
      childId: event.childId,
      type: event.type,
      title: event.title,
      achievedDate: event.achievedDate,
      description: event.description,
      photoUrl: event.photoUrl,
      videoUrl: event.videoUrl,
      notes: event.notes,
      ageMonths: event.ageMonths,
    );

    await result.fold(
      (failure) async {
        emit(currentState.copyWith(
          isAddingRecord: false,
          errorMessage: failure.message,
        ));
      },
      (milestone) async {
        // 添加到列表并排序
        final newMilestones = [...currentState.milestones, milestone];
        newMilestones.sort((a, b) => b.achievedDate.compareTo(a.achievedDate));
        emit(currentState.copyWith(
          milestones: newMilestones,
          isAddingRecord: false,
        ));
      },
    );
  }

  Future<void> _onUpdateVaccineStatus(
    VaccineStatusUpdateRequested event,
    Emitter<ChildGrowthState> emit,
  ) async {
    if (state is! ChildGrowthLoaded) return;
    final currentState = state as ChildGrowthLoaded;

    final result = await repository.updateVaccineStatus(
      vaccineId: event.vaccineId,
      status: event.status,
      actualDate: event.actualDate,
      location: event.location,
      batchNumber: event.batchNumber,
      notes: event.notes,
    );

    result.fold(
      (failure) {
        emit(currentState.copyWith(errorMessage: failure.message));
      },
      (updatedVaccine) {
        // 更新疫苗列表
        final newVaccines = currentState.vaccines.map((v) {
          if (v.id == event.vaccineId) {
            return updatedVaccine;
          }
          return v;
        }).toList();
        emit(currentState.copyWith(vaccines: newVaccines));
      },
    );
  }

  void _onTabChanged(
    ChildGrowthTabChanged event,
    Emitter<ChildGrowthState> emit,
  ) {
    if (state is! ChildGrowthLoaded) return;
    final currentState = state as ChildGrowthLoaded;
    emit(currentState.copyWith(currentTabIndex: event.tabIndex));
  }
}
