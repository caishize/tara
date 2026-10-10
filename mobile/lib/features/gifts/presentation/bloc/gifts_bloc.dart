import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';
import '../../domain/entities/gift.dart';
import '../../domain/repositories/gift_repository.dart';

// Events
abstract class GiftsEvent extends Equatable {
  const GiftsEvent();
  @override
  List<Object?> get props => [];
}

class GiftsLoadRequested extends GiftsEvent {
  final GiftCategory? category;

  const GiftsLoadRequested({this.category});

  @override
  List<Object?> get props => [category];
}

class GiftsSearchRequested extends GiftsEvent {
  final String query;
  final GiftCategory? category;
  final double? minPrice;
  final double? maxPrice;

  const GiftsSearchRequested({
    required this.query,
    this.category,
    this.minPrice,
    this.maxPrice,
  });

  @override
  List<Object?> get props => [query, category, minPrice, maxPrice];
}

class GiftRecommendationRequested extends GiftsEvent {
  final String memberId;
  final GiftOccasion occasion;
  final int? budgetMin;
  final int? budgetMax;
  final String? urgency;

  const GiftRecommendationRequested({
    required this.memberId,
    required this.occasion,
    this.budgetMin,
    this.budgetMax,
    this.urgency,
  });

  @override
  List<Object?> get props => [memberId, occasion, budgetMin, budgetMax, urgency];
}

class MemberGiftMemoryLoadRequested extends GiftsEvent {
  final String memberId;

  const MemberGiftMemoryLoadRequested({required this.memberId});

  @override
  List<Object?> get props => [memberId];
}

class MemberGiftHistoryLoadRequested extends GiftsEvent {
  final String memberId;

  const MemberGiftHistoryLoadRequested({required this.memberId});

  @override
  List<Object?> get props => [memberId];
}

class GiftSaveToggled extends GiftsEvent {
  final String giftId;
  final bool isSaved;

  const GiftSaveToggled({required this.giftId, required this.isSaved});

  @override
  List<Object?> get props => [giftId, isSaved];
}

class SavedGiftsLoadRequested extends GiftsEvent {
  const SavedGiftsLoadRequested();
}

class RecommendationHistoryLoadRequested extends GiftsEvent {
  final String? memberId;

  const RecommendationHistoryLoadRequested({this.memberId});

  @override
  List<Object?> get props => [memberId];
}

class SmartDatesLoadRequested extends GiftsEvent {
  final String memberId;
  final int daysAhead;

  const SmartDatesLoadRequested({
    required this.memberId,
    this.daysAhead = 90,
  });

  @override
  List<Object?> get props => [memberId, daysAhead];
}

class BudgetSuggestionLoadRequested extends GiftsEvent {
  final String memberId;
  final String? occasion;

  const BudgetSuggestionLoadRequested({
    required this.memberId,
    this.occasion,
  });

  @override
  List<Object?> get props => [memberId, occasion];
}

class SmartDateSelected extends GiftsEvent {
  final SmartDate? date;

  const SmartDateSelected({this.date});

  @override
  List<Object?> get props => [date];
}

// States
abstract class GiftsState extends Equatable {
  const GiftsState();
  @override
  List<Object?> get props => [];
}

class GiftsInitial extends GiftsState {
  const GiftsInitial();
}

class GiftsLoading extends GiftsState {
  const GiftsLoading();
}

class GiftsLoaded extends GiftsState {
  final List<Gift> gifts;
  final List<Gift> savedGifts;
  final List<GiftRecommendation> history;
  final GiftCategory? selectedCategory;
  final MemberGiftMemory? memberMemory;
  final List<GiftHistoryItem> memberGiftHistory;
  final GiftRecommendation? currentRecommendation;
  final List<SmartDate> smartDates;
  final SmartDate? selectedSmartDate;
  final BudgetSuggestion? budgetSuggestion;

  const GiftsLoaded({
    required this.gifts,
    this.savedGifts = const [],
    this.history = const [],
    this.selectedCategory,
    this.memberMemory,
    this.memberGiftHistory = const [],
    this.currentRecommendation,
    this.smartDates = const [],
    this.selectedSmartDate,
    this.budgetSuggestion,
  });

  GiftsLoaded copyWith({
    List<Gift>? gifts,
    List<Gift>? savedGifts,
    List<GiftRecommendation>? history,
    GiftCategory? selectedCategory,
    MemberGiftMemory? memberMemory,
    List<GiftHistoryItem>? memberGiftHistory,
    GiftRecommendation? currentRecommendation,
    bool clearRecommendation = false,
    List<SmartDate>? smartDates,
    SmartDate? selectedSmartDate,
    bool clearSelectedSmartDate = false,
    BudgetSuggestion? budgetSuggestion,
    bool clearBudgetSuggestion = false,
  }) {
    return GiftsLoaded(
      gifts: gifts ?? this.gifts,
      savedGifts: savedGifts ?? this.savedGifts,
      history: history ?? this.history,
      selectedCategory: selectedCategory ?? this.selectedCategory,
      memberMemory: memberMemory ?? this.memberMemory,
      memberGiftHistory: memberGiftHistory ?? this.memberGiftHistory,
      currentRecommendation: clearRecommendation ? null : (currentRecommendation ?? this.currentRecommendation),
      smartDates: smartDates ?? this.smartDates,
      selectedSmartDate: clearSelectedSmartDate ? null : (selectedSmartDate ?? this.selectedSmartDate),
      budgetSuggestion: clearBudgetSuggestion ? null : (budgetSuggestion ?? this.budgetSuggestion),
    );
  }

  @override
  List<Object?> get props => [
    gifts, savedGifts, history, selectedCategory, memberMemory, memberGiftHistory,
    currentRecommendation, smartDates, selectedSmartDate, budgetSuggestion,
  ];
}

class GiftRecommendationLoaded extends GiftsState {
  final GiftRecommendation recommendation;

  const GiftRecommendationLoaded(this.recommendation);

  @override
  List<Object?> get props => [recommendation];
}

class GiftsError extends GiftsState {
  final String message;

  const GiftsError(this.message);

  @override
  List<Object?> get props => [message];
}

// BLoC
class GiftsBloc extends Bloc<GiftsEvent, GiftsState> {
  final GiftRepository repository;

  GiftsBloc({required this.repository}) : super(const GiftsInitial()) {
    on<GiftsLoadRequested>(_onLoadRequested);
    on<GiftsSearchRequested>(_onSearchRequested);
    on<GiftRecommendationRequested>(_onRecommendationRequested);
    on<GiftSaveToggled>(_onSaveToggled);
    on<SavedGiftsLoadRequested>(_onSavedGiftsLoadRequested);
    on<RecommendationHistoryLoadRequested>(_onHistoryLoadRequested);
    on<MemberGiftMemoryLoadRequested>(_onMemberGiftMemoryLoadRequested);
    on<MemberGiftHistoryLoadRequested>(_onMemberGiftHistoryLoadRequested);
    on<SmartDatesLoadRequested>(_onSmartDatesLoadRequested);
    on<BudgetSuggestionLoadRequested>(_onBudgetSuggestionLoadRequested);
    on<SmartDateSelected>(_onSmartDateSelected);
  }

  Future<void> _onLoadRequested(
    GiftsLoadRequested event,
    Emitter<GiftsState> emit,
  ) async {
    emit(const GiftsLoading());

    // Load recommendation history and saved gifts (no trending/popular needed)
    final historyResult = await repository.getRecommendationHistory();
    final history = historyResult.fold(
      (failure) => <GiftRecommendation>[],
      (history) => history,
    );

    final savedResult = await repository.getSavedGifts();
    final savedGifts = savedResult.fold(
      (failure) => <Gift>[],
      (gifts) => gifts,
    );

    emit(GiftsLoaded(
      gifts: const [],
      savedGifts: savedGifts,
      history: history,
    ));
  }

  Future<void> _onSearchRequested(
    GiftsSearchRequested event,
    Emitter<GiftsState> emit,
  ) async {
    // Capture state before showing loading indicator
    final previousState = state;
    emit(const GiftsLoading());

    final result = await repository.searchGifts(
      query: event.query,
      category: event.category,
      minPrice: event.minPrice,
      maxPrice: event.maxPrice,
    );

    result.fold(
      (failure) => emit(GiftsError(failure.message)),
      (gifts) {
        // Use previousState since we emitted GiftsLoading and current state is not GiftsLoaded
        if (previousState is GiftsLoaded) {
          emit(previousState.copyWith(gifts: gifts));
        } else {
          emit(GiftsLoaded(gifts: gifts));
        }
      },
    );
  }

  Future<void> _onRecommendationRequested(
    GiftRecommendationRequested event,
    Emitter<GiftsState> emit,
  ) async {
    // Capture state before showing loading indicator
    final previousState = state;
    emit(const GiftsLoading());

    final result = await repository.generateRecommendation(
      memberId: event.memberId,
      occasion: event.occasion,
      budgetMin: event.budgetMin,
      budgetMax: event.budgetMax,
    );

    await result.fold(
      (failure) async => emit(GiftsError(failure.message)),
      (recommendation) async {
        // Use previousState since we emitted GiftsLoading
        GiftsLoaded newState;
        if (previousState is GiftsLoaded) {
          newState = previousState.copyWith(currentRecommendation: recommendation);
        } else {
          newState = GiftsLoaded(
            gifts: const [],
            currentRecommendation: recommendation,
          );
        }
        emit(newState);

        // Reload recommendation history to include the new recommendation
        final historyResult = await repository.getRecommendationHistory(
          memberId: event.memberId,
          limit: 10,
        );
        historyResult.fold(
          (failure) => null, // Ignore history load failure
          (history) {
            // Get latest state before emitting to avoid race conditions
            final latestState = state;
            if (latestState is GiftsLoaded) {
              emit(latestState.copyWith(history: history));
            }
          },
        );
      },
    );
  }

  Future<void> _onSaveToggled(
    GiftSaveToggled event,
    Emitter<GiftsState> emit,
  ) async {
    if (state is! GiftsLoaded) return;

    final result = event.isSaved
        ? await repository.saveGift(event.giftId)
        : await repository.unsaveGift(event.giftId);

    await result.fold(
      (failure) async => emit(GiftsError(failure.message)),
      (_) async {
        // Reload saved gifts
        final savedResult = await repository.getSavedGifts();
        savedResult.fold(
          (failure) => null,
          (savedGifts) {
            // Get latest state before emitting to avoid race conditions
            final latestState = state;
            if (latestState is GiftsLoaded) {
              emit(latestState.copyWith(savedGifts: savedGifts));
            }
          },
        );
      },
    );
  }

  Future<void> _onSavedGiftsLoadRequested(
    SavedGiftsLoadRequested event,
    Emitter<GiftsState> emit,
  ) async {
    final result = await repository.getSavedGifts();

    result.fold(
      (failure) => emit(GiftsError(failure.message)),
      (savedGifts) {
        // Get latest state before emitting to avoid race conditions
        final latestState = state;
        if (latestState is GiftsLoaded) {
          emit(latestState.copyWith(savedGifts: savedGifts));
        } else {
          emit(GiftsLoaded(gifts: const [], savedGifts: savedGifts));
        }
      },
    );
  }

  Future<void> _onHistoryLoadRequested(
    RecommendationHistoryLoadRequested event,
    Emitter<GiftsState> emit,
  ) async {
    final result = await repository.getRecommendationHistory(
      memberId: event.memberId,
      limit: 10,
    );

    result.fold(
      (failure) {
        // On failure, show empty history
        // Get latest state right before emitting to avoid race conditions
        final latestState = state;
        if (latestState is GiftsLoaded) {
          // Clear currentRecommendation when loading history for a specific member
          // to prevent showing stale recommendations from a different member
          emit(latestState.copyWith(
            history: const [],
            clearRecommendation: event.memberId != null,
          ));
        } else {
          emit(GiftsLoaded(gifts: const [], history: const []));
        }
      },
      (history) {
        // Get latest state right before emitting to avoid race conditions
        final latestState = state;
        if (latestState is GiftsLoaded) {
          // Clear currentRecommendation when loading history for a specific member
          emit(latestState.copyWith(
            history: history,
            clearRecommendation: event.memberId != null,
          ));
        } else {
          emit(GiftsLoaded(gifts: const [], history: history));
        }
      },
    );
  }

  Future<void> _onMemberGiftMemoryLoadRequested(
    MemberGiftMemoryLoadRequested event,
    Emitter<GiftsState> emit,
  ) async {
    final result = await repository.getMemberGiftMemory(event.memberId);

    result.fold(
      (failure) {
        // On failure, use empty memory
        // Get latest state right before emitting to avoid race conditions
        final latestState = state;
        if (latestState is GiftsLoaded) {
          emit(latestState.copyWith(memberMemory: MemberGiftMemory(memberId: event.memberId)));
        }
      },
      (memory) {
        // Get latest state right before emitting to avoid race conditions
        final latestState = state;
        if (latestState is GiftsLoaded) {
          emit(latestState.copyWith(memberMemory: memory));
        } else {
          emit(GiftsLoaded(gifts: const [], memberMemory: memory));
        }
      },
    );
  }

  Future<void> _onMemberGiftHistoryLoadRequested(
    MemberGiftHistoryLoadRequested event,
    Emitter<GiftsState> emit,
  ) async {
    final result = await repository.getMemberGiftHistory(event.memberId);

    result.fold(
      (failure) {
        // On failure, show empty history
        // Get latest state right before emitting to avoid race conditions
        final latestState = state;
        if (latestState is GiftsLoaded) {
          emit(latestState.copyWith(memberGiftHistory: const []));
        }
      },
      (history) {
        // Get latest state right before emitting to avoid race conditions
        final latestState = state;
        if (latestState is GiftsLoaded) {
          emit(latestState.copyWith(memberGiftHistory: history));
        } else {
          emit(GiftsLoaded(gifts: const [], memberGiftHistory: history));
        }
      },
    );
  }

  Future<void> _onSmartDatesLoadRequested(
    SmartDatesLoadRequested event,
    Emitter<GiftsState> emit,
  ) async {
    final result = await repository.getSmartDatesForMember(
      event.memberId,
      daysAhead: event.daysAhead,
    );

    result.fold(
      (failure) {
        // On failure, use empty smart dates list
        final latestState = state;
        if (latestState is GiftsLoaded) {
          emit(latestState.copyWith(smartDates: const []));
        }
      },
      (smartDatesResult) {
        final latestState = state;
        // Auto-select the nearest date if available
        SmartDate? autoSelected;
        if (smartDatesResult.nearestDateId != null) {
          autoSelected = smartDatesResult.dates.firstWhere(
            (d) => d.id == smartDatesResult.nearestDateId,
            orElse: () => smartDatesResult.dates.isNotEmpty
                ? smartDatesResult.dates.first
                : const SmartDate(
                    name: '通用推荐',
                    occasionType: GiftOccasion.other,
                    source: SmartDateSource.general,
                  ),
          );
        } else if (smartDatesResult.dates.isNotEmpty) {
          autoSelected = smartDatesResult.dates.first;
        }

        if (latestState is GiftsLoaded) {
          emit(latestState.copyWith(
            smartDates: smartDatesResult.dates,
            selectedSmartDate: autoSelected,
          ));
        } else {
          emit(GiftsLoaded(
            gifts: const [],
            smartDates: smartDatesResult.dates,
            selectedSmartDate: autoSelected,
          ));
        }
      },
    );
  }

  Future<void> _onBudgetSuggestionLoadRequested(
    BudgetSuggestionLoadRequested event,
    Emitter<GiftsState> emit,
  ) async {
    final result = await repository.getBudgetSuggestion(
      memberId: event.memberId,
      occasion: event.occasion,
    );

    result.fold(
      (failure) {
        // On failure, clear budget suggestion
        final latestState = state;
        if (latestState is GiftsLoaded) {
          emit(latestState.copyWith(clearBudgetSuggestion: true));
        }
      },
      (suggestion) {
        final latestState = state;
        if (latestState is GiftsLoaded) {
          emit(latestState.copyWith(budgetSuggestion: suggestion));
        } else {
          emit(GiftsLoaded(gifts: const [], budgetSuggestion: suggestion));
        }
      },
    );
  }

  Future<void> _onSmartDateSelected(
    SmartDateSelected event,
    Emitter<GiftsState> emit,
  ) async {
    final latestState = state;
    if (latestState is GiftsLoaded) {
      emit(latestState.copyWith(
        selectedSmartDate: event.date,
        clearSelectedSmartDate: event.date == null,
      ));
    }
  }
}
