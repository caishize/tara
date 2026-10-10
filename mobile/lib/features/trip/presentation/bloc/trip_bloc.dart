import 'dart:io';

import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';
import '../../domain/entities/trip.dart';
import '../../domain/entities/itinerary.dart';
import '../../domain/entities/trip_expense.dart';
import '../../domain/entities/smart_itinerary.dart';
import '../../domain/entities/trip_memory.dart';
import '../../domain/entities/destination_recommendation.dart';
import '../../domain/repositories/trip_repository.dart';
import '../../data/models/trip_context_model.dart';
import '../../data/models/association_summary_model.dart';
import '../../data/models/related_memory_model.dart';

// Events
abstract class TripBlocEvent extends Equatable {
  const TripBlocEvent();
  @override
  List<Object?> get props => [];
}

class TripsLoadRequested extends TripBlocEvent {
  final TripStatus? status;
  final TripCategory? category;

  const TripsLoadRequested({this.status, this.category});

  @override
  List<Object?> get props => [status, category];
}

class TripLoadRequested extends TripBlocEvent {
  final String tripId;

  const TripLoadRequested(this.tripId);

  @override
  List<Object?> get props => [tripId];
}

class TripCreateRequested extends TripBlocEvent {
  final Trip plan;

  const TripCreateRequested(this.plan);

  @override
  List<Object?> get props => [plan];
}

class TripUpdateRequested extends TripBlocEvent {
  final String tripId;
  final Trip plan;

  const TripUpdateRequested(this.tripId, this.plan);

  @override
  List<Object?> get props => [tripId, plan];
}

class TripDeleteRequested extends TripBlocEvent {
  final String tripId;

  const TripDeleteRequested(this.tripId);

  @override
  List<Object?> get props => [tripId];
}

class ItineraryLoadRequested extends TripBlocEvent {
  final String tripId;

  const ItineraryLoadRequested(this.tripId);

  @override
  List<Object?> get props => [tripId];
}

class ItineraryGenerateRequested extends TripBlocEvent {
  final String tripId;
  final String? style;

  const ItineraryGenerateRequested(this.tripId, {this.style});

  @override
  List<Object?> get props => [tripId, style];
}

class ItineraryAdjustRequested extends TripBlocEvent {
  final String tripId;
  final String adjustment;

  const ItineraryAdjustRequested(this.tripId, this.adjustment);

  @override
  List<Object?> get props => [tripId, adjustment];
}

class ExpensesLoadRequested extends TripBlocEvent {
  final String tripId;

  const ExpensesLoadRequested(this.tripId);

  @override
  List<Object?> get props => [tripId];
}

class ExpenseCreateRequested extends TripBlocEvent {
  final String tripId;
  final TripExpense expense;

  const ExpenseCreateRequested(this.tripId, this.expense);

  @override
  List<Object?> get props => [tripId, expense];
}

class ExpenseDeleteRequested extends TripBlocEvent {
  final String tripId;
  final String expenseId;

  const ExpenseDeleteRequested(this.tripId, this.expenseId);

  @override
  List<Object?> get props => [tripId, expenseId];
}

class BudgetStatusLoadRequested extends TripBlocEvent {
  final String tripId;

  const BudgetStatusLoadRequested(this.tripId);

  @override
  List<Object?> get props => [tripId];
}

// Destination Recommendations
class DestinationRecommendationRequested extends TripBlocEvent {
  final String familyId;
  final String? occasion;
  final double? budgetMin;
  final double? budgetMax;
  final int? durationDays;

  const DestinationRecommendationRequested({
    required this.familyId,
    this.occasion,
    this.budgetMin,
    this.budgetMax,
    this.durationDays,
  });

  @override
  List<Object?> get props =>
      [familyId, occasion, budgetMin, budgetMax, durationDays];
}

// Smart Itinerary
class SmartItineraryGenerateRequested extends TripBlocEvent {
  final String tripId;
  final List<ItineraryStyle> styles;
  final FamilyComposition? familyComposition;
  final ItineraryPreferences? preferences;

  const SmartItineraryGenerateRequested({
    required this.tripId,
    required this.styles,
    this.familyComposition,
    this.preferences,
  });

  @override
  List<Object?> get props => [tripId, styles, familyComposition, preferences];
}

// Activity CRUD
class ActivityAddRequested extends TripBlocEvent {
  final String tripId;
  final int dayNumber;
  final String time;
  final String title;
  final String? activityType;
  final String? location;
  final double? estimatedCost;

  const ActivityAddRequested({
    required this.tripId,
    required this.dayNumber,
    required this.time,
    required this.title,
    this.activityType,
    this.location,
    this.estimatedCost,
  });

  @override
  List<Object?> get props =>
      [tripId, dayNumber, time, title, activityType, location, estimatedCost];
}

class ActivityDeleteRequested extends TripBlocEvent {
  final String tripId;
  final int dayNumber;
  final int activityIndex;

  const ActivityDeleteRequested({
    required this.tripId,
    required this.dayNumber,
    required this.activityIndex,
  });

  @override
  List<Object?> get props => [tripId, dayNumber, activityIndex];
}

class DaysSwapRequested extends TripBlocEvent {
  final String tripId;
  final int sourceDay;
  final int targetDay;

  const DaysSwapRequested({
    required this.tripId,
    required this.sourceDay,
    required this.targetDay,
  });

  @override
  List<Object?> get props => [tripId, sourceDay, targetDay];
}

// Memories
class MemoriesLoadRequested extends TripBlocEvent {
  final String tripId;

  const MemoriesLoadRequested(this.tripId);

  @override
  List<Object?> get props => [tripId];
}

class MemoryUploadRequested extends TripBlocEvent {
  final String tripId;
  final File file;
  final String? caption;
  final int? rating;

  const MemoryUploadRequested({
    required this.tripId,
    required this.file,
    this.caption,
    this.rating,
  });

  @override
  List<Object?> get props => [tripId, file, caption, rating];
}

class MemoryDeleteRequested extends TripBlocEvent {
  final String tripId;
  final String memoryId;

  const MemoryDeleteRequested({
    required this.tripId,
    required this.memoryId,
  });

  @override
  List<Object?> get props => [tripId, memoryId];
}

class TripFeedbackSubmitted extends TripBlocEvent {
  final String tripId;
  final int rating;
  final String? feedback;

  const TripFeedbackSubmitted({
    required this.tripId,
    required this.rating,
    this.feedback,
  });

  @override
  List<Object?> get props => [tripId, rating, feedback];
}

class TripContextLoadRequested extends TripBlocEvent {
  final String tripId;

  const TripContextLoadRequested(this.tripId);

  @override
  List<Object?> get props => [tripId];
}

class TripPrepItemToggleRequested extends TripBlocEvent {
  final String tripId;
  final String curatedEventId;
  final String itemKey;
  final bool done;

  const TripPrepItemToggleRequested({
    required this.tripId,
    required this.curatedEventId,
    required this.itemKey,
    required this.done,
  });

  @override
  List<Object?> get props => [tripId, curatedEventId, itemKey, done];
}

class PdfExportRequested extends TripBlocEvent {
  final String tripId;

  const PdfExportRequested(this.tripId);

  @override
  List<Object?> get props => [tripId];
}

// States
abstract class TripState extends Equatable {
  const TripState();
  @override
  List<Object?> get props => [];
}

class TripInitial extends TripState {
  const TripInitial();
}

class TripLoading extends TripState {
  const TripLoading();
}

class TripsLoaded extends TripState {
  final List<Trip> plans;
  final TripStatus? filterStatus;
  final TripCategory? filterCategory;

  const TripsLoaded({
    required this.plans,
    this.filterStatus,
    this.filterCategory,
  });

  @override
  List<Object?> get props => [plans, filterStatus, filterCategory];
}

class TripDetailLoaded extends TripState {
  final Trip plan;
  final List<DayItinerary> itinerary;
  final List<TripExpense> expenses;
  final BudgetStatus? budgetStatus;
  final List<TripMemory> memories;
  final SmartItineraryResponse? smartItinerary;
  final TripContextModel? tripContext;
  final List<AssociationSummaryModel> associations;
  final List<RelatedMemoryModel> relatedMemories;

  const TripDetailLoaded({
    required this.plan,
    this.itinerary = const [],
    this.expenses = const [],
    this.budgetStatus,
    this.memories = const [],
    this.smartItinerary,
    this.tripContext,
    this.associations = const [],
    this.relatedMemories = const [],
  });

  TripDetailLoaded copyWith({
    Trip? plan,
    List<DayItinerary>? itinerary,
    List<TripExpense>? expenses,
    BudgetStatus? budgetStatus,
    List<TripMemory>? memories,
    SmartItineraryResponse? smartItinerary,
    TripContextModel? tripContext,
    List<AssociationSummaryModel>? associations,
    List<RelatedMemoryModel>? relatedMemories,
  }) {
    return TripDetailLoaded(
      plan: plan ?? this.plan,
      itinerary: itinerary ?? this.itinerary,
      expenses: expenses ?? this.expenses,
      budgetStatus: budgetStatus ?? this.budgetStatus,
      memories: memories ?? this.memories,
      smartItinerary: smartItinerary ?? this.smartItinerary,
      tripContext: tripContext ?? this.tripContext,
      associations: associations ?? this.associations,
      relatedMemories: relatedMemories ?? this.relatedMemories,
    );
  }

  @override
  List<Object?> get props => [
        plan,
        itinerary,
        expenses,
        budgetStatus,
        memories,
        smartItinerary,
        tripContext,
        associations,
        relatedMemories
      ];
}

class TripOperationSuccess extends TripState {
  final String message;

  const TripOperationSuccess(this.message);

  @override
  List<Object?> get props => [message];
}

class TripError extends TripState {
  final String message;

  const TripError(this.message);

  @override
  List<Object?> get props => [message];
}

class DestinationRecommendationsLoaded extends TripState {
  final RecommendationResponse recommendations;

  const DestinationRecommendationsLoaded(this.recommendations);

  @override
  List<Object?> get props => [recommendations];
}

class MemoryUploadInProgress extends TripState {
  final double progress;

  const MemoryUploadInProgress(this.progress);

  @override
  List<Object?> get props => [progress];
}

class PdfExportComplete extends TripState {
  final String pdfUrl;

  const PdfExportComplete(this.pdfUrl);

  @override
  List<Object?> get props => [pdfUrl];
}

// BLoC
class TripBloc extends Bloc<TripBlocEvent, TripState> {
  final TripRepository repository;

  TripBloc({required this.repository}) : super(const TripInitial()) {
    on<TripsLoadRequested>(_onPlansLoadRequested);
    on<TripLoadRequested>(_onPlanLoadRequested);
    on<TripCreateRequested>(_onPlanCreateRequested);
    on<TripUpdateRequested>(_onPlanUpdateRequested);
    on<TripDeleteRequested>(_onPlanDeleteRequested);
    on<ItineraryLoadRequested>(_onItineraryLoadRequested);
    on<ItineraryGenerateRequested>(_onItineraryGenerateRequested);
    on<ItineraryAdjustRequested>(_onItineraryAdjustRequested);
    on<ExpensesLoadRequested>(_onExpensesLoadRequested);
    on<ExpenseCreateRequested>(_onExpenseCreateRequested);
    on<ExpenseDeleteRequested>(_onExpenseDeleteRequested);
    on<BudgetStatusLoadRequested>(_onBudgetStatusLoadRequested);
    // New handlers
    on<DestinationRecommendationRequested>(
        _onDestinationRecommendationRequested);
    on<SmartItineraryGenerateRequested>(_onSmartItineraryGenerateRequested);
    on<ActivityAddRequested>(_onActivityAddRequested);
    on<ActivityDeleteRequested>(_onActivityDeleteRequested);
    on<DaysSwapRequested>(_onDaysSwapRequested);
    on<MemoriesLoadRequested>(_onMemoriesLoadRequested);
    on<MemoryUploadRequested>(_onMemoryUploadRequested);
    on<MemoryDeleteRequested>(_onMemoryDeleteRequested);
    on<TripContextLoadRequested>(_onTripContextLoadRequested);
    on<TripPrepItemToggleRequested>(_onTripPrepItemToggleRequested);
    on<TripFeedbackSubmitted>(_onTripFeedbackSubmitted);
    on<PdfExportRequested>(_onPdfExportRequested);
  }

  Future<void> _onPlansLoadRequested(
    TripsLoadRequested event,
    Emitter<TripState> emit,
  ) async {
    emit(const TripLoading());

    final result = await repository.getTrips(
      status: event.status,
      category: event.category,
    );

    result.fold(
      (failure) => emit(TripError(failure.message)),
      (plans) => emit(TripsLoaded(
        plans: plans,
        filterStatus: event.status,
        filterCategory: event.category,
      )),
    );
  }

  Future<void> _onPlanLoadRequested(
    TripLoadRequested event,
    Emitter<TripState> emit,
  ) async {
    emit(const TripLoading());

    // Single aggregated API call replaces 6 serial requests
    final result = await repository.getTripDetail(event.tripId);

    result.fold(
      (failure) {
        emit(TripError(failure.message));
      },
      (detail) {
        emit(TripDetailLoaded(
          plan: detail.plan,
          itinerary: detail.itinerary,
          expenses: detail.expenses,
          budgetStatus: detail.budgetStatus,
          tripContext: detail.context,
          associations: detail.associations,
          relatedMemories: detail.relatedMemories,
        ));
      },
    );
  }

  Future<void> _onPlanCreateRequested(
    TripCreateRequested event,
    Emitter<TripState> emit,
  ) async {
    emit(const TripLoading());

    final result = await repository.createTrip(event.plan);

    result.fold(
      (failure) => emit(TripError(failure.message)),
      (plan) => emit(const TripOperationSuccess('行程计划创建成功')),
    );
  }

  Future<void> _onPlanUpdateRequested(
    TripUpdateRequested event,
    Emitter<TripState> emit,
  ) async {
    emit(const TripLoading());

    final result = await repository.updateTrip(event.tripId, event.plan);

    result.fold(
      (failure) => emit(TripError(failure.message)),
      (plan) => emit(const TripOperationSuccess('行程计划更新成功')),
    );
  }

  Future<void> _onPlanDeleteRequested(
    TripDeleteRequested event,
    Emitter<TripState> emit,
  ) async {
    final result = await repository.deleteTrip(event.tripId);

    result.fold(
      (failure) => emit(TripError(failure.message)),
      (_) => emit(const TripOperationSuccess('行程计划已删除')),
    );
  }

  Future<void> _onItineraryLoadRequested(
    ItineraryLoadRequested event,
    Emitter<TripState> emit,
  ) async {
    final currentState = state;
    if (currentState is! TripDetailLoaded) return;

    final result = await repository.getItinerary(event.tripId);

    result.fold(
      (failure) => emit(TripError(failure.message)),
      (itinerary) => emit(currentState.copyWith(itinerary: itinerary)),
    );
  }

  Future<void> _onItineraryGenerateRequested(
    ItineraryGenerateRequested event,
    Emitter<TripState> emit,
  ) async {
    final currentState = state;
    emit(const TripLoading());

    final result = await repository.generateItinerary(
      event.tripId,
      style: event.style,
    );

    result.fold(
      (failure) => emit(TripError(failure.message)),
      (itinerary) {
        if (currentState is TripDetailLoaded) {
          emit(currentState.copyWith(itinerary: itinerary));
        } else {
          emit(const TripOperationSuccess('行程生成成功'));
        }
      },
    );
  }

  Future<void> _onItineraryAdjustRequested(
    ItineraryAdjustRequested event,
    Emitter<TripState> emit,
  ) async {
    final currentState = state;
    if (currentState is! TripDetailLoaded) return;

    emit(const TripLoading());

    final result = await repository.adjustItinerary(
      event.tripId,
      event.adjustment,
    );

    result.fold(
      (failure) => emit(TripError(failure.message)),
      (itinerary) => emit(currentState.copyWith(itinerary: itinerary)),
    );
  }

  Future<void> _onExpensesLoadRequested(
    ExpensesLoadRequested event,
    Emitter<TripState> emit,
  ) async {
    final currentState = state;
    if (currentState is! TripDetailLoaded) return;

    final result = await repository.getExpenses(event.tripId);

    result.fold(
      (failure) => emit(TripError(failure.message)),
      (expenses) => emit(currentState.copyWith(expenses: expenses)),
    );
  }

  Future<void> _onExpenseCreateRequested(
    ExpenseCreateRequested event,
    Emitter<TripState> emit,
  ) async {
    final result = await repository.createExpense(event.tripId, event.expense);

    await result.fold(
      (failure) async => emit(TripError(failure.message)),
      (expense) async {
        // Reload expenses and budget status
        add(ExpensesLoadRequested(event.tripId));
        add(BudgetStatusLoadRequested(event.tripId));
      },
    );
  }

  Future<void> _onExpenseDeleteRequested(
    ExpenseDeleteRequested event,
    Emitter<TripState> emit,
  ) async {
    final result =
        await repository.deleteExpense(event.tripId, event.expenseId);

    await result.fold(
      (failure) async => emit(TripError(failure.message)),
      (_) async {
        add(ExpensesLoadRequested(event.tripId));
        add(BudgetStatusLoadRequested(event.tripId));
      },
    );
  }

  Future<void> _onBudgetStatusLoadRequested(
    BudgetStatusLoadRequested event,
    Emitter<TripState> emit,
  ) async {
    final currentState = state;
    if (currentState is! TripDetailLoaded) return;

    final result = await repository.getBudgetStatus(event.tripId);

    result.fold(
      (failure) => null, // Silently fail
      (status) => emit(currentState.copyWith(budgetStatus: status)),
    );
  }

  // New handlers for enhanced features

  Future<void> _onDestinationRecommendationRequested(
    DestinationRecommendationRequested event,
    Emitter<TripState> emit,
  ) async {
    emit(const TripLoading());

    final result = await repository.getDestinationRecommendations(
      familyId: event.familyId,
      occasion: event.occasion,
      budgetMin: event.budgetMin,
      budgetMax: event.budgetMax,
      durationDays: event.durationDays,
    );

    result.fold(
      (failure) => emit(TripError(failure.message)),
      (recommendations) =>
          emit(DestinationRecommendationsLoaded(recommendations)),
    );
  }

  Future<void> _onSmartItineraryGenerateRequested(
    SmartItineraryGenerateRequested event,
    Emitter<TripState> emit,
  ) async {
    // Try to get the current plan state, or reload if needed
    TripDetailLoaded? planState;
    final currentState = state;

    if (currentState is TripDetailLoaded) {
      planState = currentState;
    } else {
      // State is not TripDetailLoaded (might be TripLoading due to race condition)
      // Try to reload the plan data first
      emit(const TripLoading());

      final planResult = await repository.getTrip(event.tripId);
      if (planResult.isLeft()) {
        emit(const TripError('无法生成行程：无法加载旅行计划'));
        return;
      }

      final plan =
          planResult.getOrElse(() => throw Exception('Plan not found'));
      final itineraryResult = await repository.getItinerary(event.tripId);
      final itinerary = itineraryResult.getOrElse(() => []);
      final expensesResult = await repository.getExpenses(event.tripId);
      final expenses = expensesResult.getOrElse(() => []);
      final budgetResult = await repository.getBudgetStatus(event.tripId);
      final budgetStatus = budgetResult.toOption().toNullable();

      planState = TripDetailLoaded(
        plan: plan,
        itinerary: itinerary,
        expenses: expenses,
        budgetStatus: budgetStatus,
      );
    }

    // At this point planState is guaranteed to be non-null by flow analysis
    final confirmedPlanState = planState;

    emit(const TripLoading());

    final request = SmartItineraryRequest(
      styles: event.styles,
      familyComposition: event.familyComposition,
      preferences: event.preferences,
    );

    final result =
        await repository.generateSmartItinerary(event.tripId, request);

    if (result.isLeft()) {
      // API failed - show error message, don't use demo data
      final failure = result.fold((f) => f, (_) => null);
      final errorMessage = failure?.message ?? '智能行程生成失败，请稍后重试';
      emit(TripError(errorMessage));

      // Restore previous state so user can retry
      emit(confirmedPlanState);
    } else {
      // API succeeded - convert smart schedules to regular itinerary
      final smartResponse = result.getOrElse(
        () => SmartItineraryResponse(
          tripId: event.tripId,
          destination: confirmedPlanState.plan.destination,
          durationDays: confirmedPlanState.plan.durationDays,
          generatedAt: DateTime.now().toIso8601String(),
        ),
      );

      // Convert smart daily schedules to regular day itinerary
      final newItinerary = _convertSmartSchedulesToItinerary(
        smartResponse.dailySchedules,
        event.tripId,
      );

      // First emit success message
      emit(const TripOperationSuccess('智能行程生成成功'));

      // Then emit updated state with both itinerary and smart response
      emit(confirmedPlanState.copyWith(
        itinerary: newItinerary,
        smartItinerary: smartResponse,
      ));
    }
  }

  /// Convert SmartDailySchedule list to DayItinerary list
  List<DayItinerary> _convertSmartSchedulesToItinerary(
    List<SmartDailySchedule> schedules,
    String tripId,
  ) {
    final now = DateTime.now();
    return schedules.map((schedule) {
      return DayItinerary(
        id: '${tripId}_day${schedule.day}',
        tripId: tripId,
        dayNumber: schedule.day,
        activities: schedule.activities.map((activity) {
          return ItineraryActivity(
            time: activity.time,
            activityType: _parseActivityType(activity.activityType),
            title: activity.title,
            location: activity.location.isNotEmpty ? activity.location : null,
            description:
                activity.description.isNotEmpty ? activity.description : null,
            estimatedCost:
                activity.estimatedCost > 0 ? activity.estimatedCost : null,
            professionalAdvice: activity.professionalAdvice?.whyChosen,
            alternatives: activity.alternatives.map((a) => a.name).toList(),
          );
        }).toList(),
        createdAt: now,
        updatedAt: now,
      );
    }).toList();
  }

  /// Parse activity type string to enum
  ActivityType _parseActivityType(String typeString) {
    switch (typeString.toLowerCase()) {
      case 'transportation':
        return ActivityType.transportation;
      case 'accommodation':
        return ActivityType.accommodation;
      case 'attraction':
        return ActivityType.attraction;
      case 'dining':
      case 'meal':
      case 'restaurant':
        return ActivityType.dining;
      case 'shopping':
        return ActivityType.shopping;
      case 'rest':
        return ActivityType.rest;
      default:
        return ActivityType.other;
    }
  }

  Future<void> _onActivityAddRequested(
    ActivityAddRequested event,
    Emitter<TripState> emit,
  ) async {
    final result = await repository.addActivity(
      event.tripId,
      event.dayNumber,
      event.time,
      event.title,
      activityType: event.activityType,
      location: event.location,
      estimatedCost: event.estimatedCost,
    );

    await result.fold(
      (failure) async => emit(TripError(failure.message)),
      (_) async {
        add(ItineraryLoadRequested(event.tripId));
        emit(const TripOperationSuccess('活动添加成功'));
      },
    );
  }

  Future<void> _onActivityDeleteRequested(
    ActivityDeleteRequested event,
    Emitter<TripState> emit,
  ) async {
    final result = await repository.deleteActivity(
      event.tripId,
      event.dayNumber,
      event.activityIndex,
    );

    await result.fold(
      (failure) async => emit(TripError(failure.message)),
      (_) async {
        add(ItineraryLoadRequested(event.tripId));
        emit(const TripOperationSuccess('活动已删除'));
      },
    );
  }

  Future<void> _onDaysSwapRequested(
    DaysSwapRequested event,
    Emitter<TripState> emit,
  ) async {
    final result = await repository.swapDays(
      event.tripId,
      event.sourceDay,
      event.targetDay,
    );

    await result.fold(
      (failure) async => emit(TripError(failure.message)),
      (_) async {
        add(ItineraryLoadRequested(event.tripId));
        emit(const TripOperationSuccess('日程交换成功'));
      },
    );
  }

  Future<void> _onMemoriesLoadRequested(
    MemoriesLoadRequested event,
    Emitter<TripState> emit,
  ) async {
    final currentState = state;
    if (currentState is! TripDetailLoaded) return;

    final result = await repository.getMemories(event.tripId);

    result.fold(
      (failure) => emit(TripError(failure.message)),
      (memories) => emit(currentState.copyWith(memories: memories)),
    );
  }

  Future<void> _onMemoryUploadRequested(
    MemoryUploadRequested event,
    Emitter<TripState> emit,
  ) async {
    final result = await repository.uploadMemory(
      event.tripId,
      event.file,
      event.caption,
      event.rating,
    );

    await result.fold(
      (failure) async => emit(TripError(failure.message)),
      (memory) async {
        add(MemoriesLoadRequested(event.tripId));
        emit(const TripOperationSuccess('照片上传成功'));
      },
    );
  }

  Future<void> _onMemoryDeleteRequested(
    MemoryDeleteRequested event,
    Emitter<TripState> emit,
  ) async {
    final result = await repository.deleteMemory(event.tripId, event.memoryId);

    await result.fold(
      (failure) async => emit(TripError(failure.message)),
      (_) async {
        add(MemoriesLoadRequested(event.tripId));
        emit(const TripOperationSuccess('照片已删除'));
      },
    );
  }

  Future<void> _onTripContextLoadRequested(
    TripContextLoadRequested event,
    Emitter<TripState> emit,
  ) async {
    final currentState = state;
    if (currentState is! TripDetailLoaded) return;

    try {
      final result = await repository.getTripContext(event.tripId);
      result.fold(
        (_) {},
        (context) => emit(currentState.copyWith(tripContext: context)),
      );
    } catch (_) {
      // Silently fail - context is supplementary
    }
  }

  Future<void> _onTripPrepItemToggleRequested(
    TripPrepItemToggleRequested event,
    Emitter<TripState> emit,
  ) async {
    final currentState = state;
    if (currentState is! TripDetailLoaded) return;
    final currentContext = currentState.tripContext;
    if (currentContext == null) return;

    // Optimistic update for immediate UI feedback.
    final optimisticItems = currentContext.preparationItems.map((item) {
      if (item.key != event.itemKey) return item;
      return TripPrepItemModel(
        key: item.key,
        text: item.text,
        done: event.done,
        source: item.source,
        actionLabel: item.actionLabel,
      );
    }).toList();
    emit(currentState.copyWith(
      tripContext: TripContextModel(
        tripId: currentContext.tripId,
        participants: currentContext.participants,
        weather: currentContext.weather,
        preparationItems: optimisticItems,
        curatedEventId: currentContext.curatedEventId,
        insightText: currentContext.insightText,
        sideActivities: currentContext.sideActivities,
        recommendationHighlights: currentContext.recommendationHighlights,
      ),
    ));

    final result = await repository.togglePreparationItem(
      curatedEventId: event.curatedEventId,
      itemKey: event.itemKey,
      done: event.done,
    );

    result.fold(
      (_) {
        // Roll back on failure to keep UI consistent.
        emit(currentState);
      },
      (serverItems) {
        emit(currentState.copyWith(
          tripContext: TripContextModel(
            tripId: currentContext.tripId,
            participants: currentContext.participants,
            weather: currentContext.weather,
            preparationItems: serverItems,
            curatedEventId: currentContext.curatedEventId,
            insightText: currentContext.insightText,
            sideActivities: currentContext.sideActivities,
            recommendationHighlights: currentContext.recommendationHighlights,
          ),
        ));
      },
    );
  }

  Future<void> _onTripFeedbackSubmitted(
    TripFeedbackSubmitted event,
    Emitter<TripState> emit,
  ) async {
    final result = await repository.submitFeedback(
      event.tripId,
      event.rating,
      event.feedback,
    );

    result.fold(
      (failure) => emit(TripError(failure.message)),
      (_) => emit(const TripOperationSuccess('感谢您的反馈')),
    );
  }

  Future<void> _onPdfExportRequested(
    PdfExportRequested event,
    Emitter<TripState> emit,
  ) async {
    emit(const TripLoading());

    final result = await repository.exportPdf(event.tripId);

    result.fold(
      (failure) => emit(TripError(failure.message)),
      (pdfUrl) => emit(PdfExportComplete(pdfUrl)),
    );
  }
}
