import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';
import '../../domain/entities/goal.dart';
import '../../domain/repositories/goals_repository.dart';

// Events
abstract class GoalsEvent extends Equatable {
  const GoalsEvent();
  @override
  List<Object?> get props => [];
}

class GoalsLoadRequested extends GoalsEvent {
  final String memberId;
  final String? statusFilter;
  final String? typeFilter;

  const GoalsLoadRequested({
    required this.memberId,
    this.statusFilter,
    this.typeFilter,
  });

  @override
  List<Object?> get props => [memberId, statusFilter, typeFilter];
}

class GoalCreateRequested extends GoalsEvent {
  final String memberId;
  final String goalType;
  final String description;
  final double targetValue;
  final String unit;
  final DateTime startDate;
  final DateTime endDate;

  const GoalCreateRequested({
    required this.memberId,
    required this.goalType,
    required this.description,
    required this.targetValue,
    required this.unit,
    required this.startDate,
    required this.endDate,
  });

  @override
  List<Object?> get props => [memberId, goalType, description, targetValue, unit, startDate, endDate];
}

class GoalProgressRecorded extends GoalsEvent {
  final String goalId;
  final String memberId;
  final double progressIncrement;
  final String? notes;

  const GoalProgressRecorded({
    required this.goalId,
    required this.memberId,
    required this.progressIncrement,
    this.notes,
  });

  @override
  List<Object?> get props => [goalId, memberId, progressIncrement, notes];
}

class GoalSelected extends GoalsEvent {
  final String goalId;
  const GoalSelected(this.goalId);
  @override
  List<Object?> get props => [goalId];
}

class GoalStatusUpdated extends GoalsEvent {
  final String goalId;
  final String memberId;
  final String newStatus;

  const GoalStatusUpdated({
    required this.goalId,
    required this.memberId,
    required this.newStatus,
  });

  @override
  List<Object?> get props => [goalId, memberId, newStatus];
}

// States
abstract class GoalsState extends Equatable {
  const GoalsState();
  @override
  List<Object?> get props => [];
}

class GoalsInitial extends GoalsState {
  const GoalsInitial();
}

class GoalsLoading extends GoalsState {
  const GoalsLoading();
}

class GoalsLoaded extends GoalsState {
  final List<Goal> goals;
  final Goal? selectedGoal;
  final String memberId;

  const GoalsLoaded({
    required this.goals,
    required this.memberId,
    this.selectedGoal,
  });

  GoalsLoaded copyWith({
    List<Goal>? goals,
    Goal? selectedGoal,
    String? memberId,
  }) {
    return GoalsLoaded(
      goals: goals ?? this.goals,
      selectedGoal: selectedGoal ?? this.selectedGoal,
      memberId: memberId ?? this.memberId,
    );
  }

  List<Goal> get activeGoals => goals.where((g) => g.status == GoalStatus.active).toList();
  List<Goal> get completedGoals => goals.where((g) => g.status == GoalStatus.completed).toList();
  int get totalGoals => goals.length;
  int get completedCount => completedGoals.length;
  double get overallCompletionRate => totalGoals > 0 ? completedCount / totalGoals * 100 : 0;

  @override
  List<Object?> get props => [goals, selectedGoal, memberId];
}

class GoalsError extends GoalsState {
  final String message;
  const GoalsError(this.message);
  @override
  List<Object?> get props => [message];
}

class GoalsOperationSuccess extends GoalsState {
  final String message;
  const GoalsOperationSuccess(this.message);
  @override
  List<Object?> get props => [message];
}

// BLoC
class GoalsBloc extends Bloc<GoalsEvent, GoalsState> {
  final GoalsRepository repository;

  GoalsBloc({required this.repository}) : super(const GoalsInitial()) {
    on<GoalsLoadRequested>(_onLoadRequested);
    on<GoalCreateRequested>(_onGoalCreate);
    on<GoalProgressRecorded>(_onProgressRecord);
    on<GoalSelected>(_onGoalSelected);
    on<GoalStatusUpdated>(_onStatusUpdate);
  }

  Future<void> _onLoadRequested(
    GoalsLoadRequested event,
    Emitter<GoalsState> emit,
  ) async {
    emit(const GoalsLoading());

    final result = await repository.getMemberGoals(
      memberId: event.memberId,
      status: event.statusFilter,
      goalType: event.typeFilter,
    );

    result.fold(
      (failure) => emit(GoalsError(failure.message)),
      (goals) {
        emit(GoalsLoaded(
          goals: goals,
          memberId: event.memberId,
          selectedGoal: goals.isNotEmpty ? goals.first : null,
        ));
      },
    );
  }

  Future<void> _onGoalCreate(
    GoalCreateRequested event,
    Emitter<GoalsState> emit,
  ) async {
    final result = await repository.createGoal(
      memberId: event.memberId,
      goalType: event.goalType,
      description: event.description,
      targetValue: event.targetValue,
      unit: event.unit,
      startDate: event.startDate,
      endDate: event.endDate,
    );

    result.fold(
      (failure) => emit(GoalsError(failure.message)),
      (goal) {
        emit(const GoalsOperationSuccess('目标创建成功'));
        add(GoalsLoadRequested(memberId: event.memberId));
      },
    );
  }

  Future<void> _onProgressRecord(
    GoalProgressRecorded event,
    Emitter<GoalsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! GoalsLoaded) return;

    final result = await repository.recordProgress(
      goalId: event.goalId,
      memberId: event.memberId,
      progressIncrement: event.progressIncrement,
      notes: event.notes,
    );

    result.fold(
      (failure) => emit(GoalsError(failure.message)),
      (_) {
        emit(const GoalsOperationSuccess('进度记录成功'));
        add(GoalsLoadRequested(memberId: currentState.memberId));
      },
    );
  }

  Future<void> _onGoalSelected(
    GoalSelected event,
    Emitter<GoalsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! GoalsLoaded) return;

    final selected = currentState.goals.where((g) => g.id == event.goalId).firstOrNull;
    if (selected != null) {
      emit(currentState.copyWith(selectedGoal: selected));
    }
  }

  Future<void> _onStatusUpdate(
    GoalStatusUpdated event,
    Emitter<GoalsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! GoalsLoaded) return;

    final result = await repository.updateGoal(
      goalId: event.goalId,
      memberId: event.memberId,
      status: event.newStatus,
    );

    result.fold(
      (failure) => emit(GoalsError(failure.message)),
      (_) {
        final message = event.newStatus == 'completed' ? '目标完成!' : '状态更新成功';
        emit(GoalsOperationSuccess(message));
        add(GoalsLoadRequested(memberId: currentState.memberId));
      },
    );
  }
}
