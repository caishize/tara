import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';

import '../../../../core/events/app_event_bus.dart';
import '../../domain/entities/relationship_member.dart';
import '../../domain/repositories/relationship_repository.dart';

// Events
abstract class RelationshipsEvent extends Equatable {
  const RelationshipsEvent();

  @override
  List<Object?> get props => [];
}

class RelationshipsLoadRequested extends RelationshipsEvent {
  final String? category;
  final String sortBy;
  final String sortOrder;

  const RelationshipsLoadRequested({
    this.category,
    this.sortBy = 'score',
    this.sortOrder = 'desc',
  });

  @override
  List<Object?> get props => [category, sortBy, sortOrder];
}

class RelationshipsRefreshRequested extends RelationshipsEvent {
  const RelationshipsRefreshRequested();
}

class RelationshipsCategoryChanged extends RelationshipsEvent {
  final String? category;

  const RelationshipsCategoryChanged(this.category);

  @override
  List<Object?> get props => [category];
}

class RelationshipsSortChanged extends RelationshipsEvent {
  final String sortBy;
  final String sortOrder;

  const RelationshipsSortChanged({
    required this.sortBy,
    required this.sortOrder,
  });

  @override
  List<Object?> get props => [sortBy, sortOrder];
}

class RelationshipsInteractionRecorded extends RelationshipsEvent {
  final String memberId;
  final String interactionType;
  final String? description;

  const RelationshipsInteractionRecorded({
    required this.memberId,
    required this.interactionType,
    this.description,
  });

  @override
  List<Object?> get props => [memberId, interactionType, description];
}

class RelationshipsGraphRequested extends RelationshipsEvent {
  final String? centerMemberId;

  const RelationshipsGraphRequested({this.centerMemberId});

  @override
  List<Object?> get props => [centerMemberId];
}

// States
abstract class RelationshipsState extends Equatable {
  const RelationshipsState();

  @override
  List<Object?> get props => [];
}

class RelationshipsInitial extends RelationshipsState {
  const RelationshipsInitial();
}

class RelationshipsLoading extends RelationshipsState {
  const RelationshipsLoading();
}

class RelationshipsLoaded extends RelationshipsState {
  final RelationshipData data;
  final String? category;
  final String sortBy;
  final String sortOrder;

  const RelationshipsLoaded({
    required this.data,
    this.category,
    this.sortBy = 'score',
    this.sortOrder = 'desc',
  });

  @override
  List<Object?> get props => [data, category, sortBy, sortOrder];

  RelationshipsLoaded copyWith({
    RelationshipData? data,
    String? category,
    String? sortBy,
    String? sortOrder,
  }) {
    return RelationshipsLoaded(
      data: data ?? this.data,
      category: category ?? this.category,
      sortBy: sortBy ?? this.sortBy,
      sortOrder: sortOrder ?? this.sortOrder,
    );
  }
}

class RelationshipsError extends RelationshipsState {
  final String message;

  const RelationshipsError(this.message);

  @override
  List<Object?> get props => [message];
}

class RelationshipsGraphLoaded extends RelationshipsState {
  final Map<String, dynamic> graphData;

  const RelationshipsGraphLoaded(this.graphData);

  @override
  List<Object?> get props => [graphData];
}

class RelationshipsInteractionSuccess extends RelationshipsState {
  final String message;

  const RelationshipsInteractionSuccess(this.message);

  @override
  List<Object?> get props => [message];
}

// BLoC
class RelationshipsBloc extends Bloc<RelationshipsEvent, RelationshipsState> {
  final RelationshipRepository _repository;

  String? _currentCategory;
  String _currentSortBy = 'score';
  String _currentSortOrder = 'desc';
  StreamSubscription<MemberUpdatedEvent>? _memberUpdatedSub;

  RelationshipsBloc({required RelationshipRepository repository})
      : _repository = repository,
        super(const RelationshipsInitial()) {
    on<RelationshipsLoadRequested>(_onLoadRequested);
    on<RelationshipsRefreshRequested>(_onRefreshRequested);
    on<RelationshipsCategoryChanged>(_onCategoryChanged);
    on<RelationshipsSortChanged>(_onSortChanged);
    on<RelationshipsInteractionRecorded>(_onInteractionRecorded);
    on<RelationshipsGraphRequested>(_onGraphRequested);

    // Refresh when profile is updated from another feature (e.g. AuthBloc)
    _memberUpdatedSub = AppEventBus.instance.on<MemberUpdatedEvent>().listen((_) {
      add(const RelationshipsRefreshRequested());
    });
  }

  @override
  Future<void> close() {
    _memberUpdatedSub?.cancel();
    return super.close();
  }

  Future<void> _onLoadRequested(
    RelationshipsLoadRequested event,
    Emitter<RelationshipsState> emit,
  ) async {
    emit(const RelationshipsLoading());

    _currentCategory = event.category;
    _currentSortBy = event.sortBy;
    _currentSortOrder = event.sortOrder;

    try {
      final data = await _repository.getAllMembersWithHealth(
        category: event.category,
        sortBy: event.sortBy,
        sortOrder: event.sortOrder,
      );

      emit(RelationshipsLoaded(
        data: data,
        category: event.category,
        sortBy: event.sortBy,
        sortOrder: event.sortOrder,
      ));
    } catch (e) {
      emit(RelationshipsError(e.toString()));
    }
  }

  Future<void> _onRefreshRequested(
    RelationshipsRefreshRequested event,
    Emitter<RelationshipsState> emit,
  ) async {
    try {
      final data = await _repository.getAllMembersWithHealth(
        category: _currentCategory,
        sortBy: _currentSortBy,
        sortOrder: _currentSortOrder,
      );

      emit(RelationshipsLoaded(
        data: data,
        category: _currentCategory,
        sortBy: _currentSortBy,
        sortOrder: _currentSortOrder,
      ));
    } catch (e) {
      emit(RelationshipsError(e.toString()));
    }
  }

  Future<void> _onCategoryChanged(
    RelationshipsCategoryChanged event,
    Emitter<RelationshipsState> emit,
  ) async {
    _currentCategory = event.category;

    emit(const RelationshipsLoading());

    try {
      final data = await _repository.getAllMembersWithHealth(
        category: event.category,
        sortBy: _currentSortBy,
        sortOrder: _currentSortOrder,
      );

      emit(RelationshipsLoaded(
        data: data,
        category: event.category,
        sortBy: _currentSortBy,
        sortOrder: _currentSortOrder,
      ));
    } catch (e) {
      emit(RelationshipsError(e.toString()));
    }
  }

  Future<void> _onSortChanged(
    RelationshipsSortChanged event,
    Emitter<RelationshipsState> emit,
  ) async {
    _currentSortBy = event.sortBy;
    _currentSortOrder = event.sortOrder;

    emit(const RelationshipsLoading());

    try {
      final data = await _repository.getAllMembersWithHealth(
        category: _currentCategory,
        sortBy: event.sortBy,
        sortOrder: event.sortOrder,
      );

      emit(RelationshipsLoaded(
        data: data,
        category: _currentCategory,
        sortBy: event.sortBy,
        sortOrder: event.sortOrder,
      ));
    } catch (e) {
      emit(RelationshipsError(e.toString()));
    }
  }

  Future<void> _onInteractionRecorded(
    RelationshipsInteractionRecorded event,
    Emitter<RelationshipsState> emit,
  ) async {
    try {
      await _repository.recordInteraction(
        memberId: event.memberId,
        interactionType: event.interactionType,
        description: event.description,
      );

      emit(const RelationshipsInteractionSuccess('互动已记录'));

      // Refresh the data
      add(const RelationshipsRefreshRequested());
    } catch (e) {
      emit(RelationshipsError(e.toString()));
    }
  }

  Future<void> _onGraphRequested(
    RelationshipsGraphRequested event,
    Emitter<RelationshipsState> emit,
  ) async {
    try {
      final graphData = await _repository.getRelationshipGraph(
        centerMemberId: event.centerMemberId,
      );

      emit(RelationshipsGraphLoaded(graphData));
    } catch (e) {
      emit(RelationshipsError(e.toString()));
    }
  }
}
