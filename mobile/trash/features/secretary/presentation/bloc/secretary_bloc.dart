import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';

import '../../domain/entities/smart_suggestion.dart';
import '../../domain/repositories/secretary_repository.dart';
import '../../data/models/smart_suggestion_model.dart';

// Events
abstract class SecretaryEvent extends Equatable {
  const SecretaryEvent();

  @override
  List<Object?> get props => [];
}

class LoadSuggestions extends SecretaryEvent {
  final String? familyId;
  final int limit;

  const LoadSuggestions({this.familyId, this.limit = 10});

  @override
  List<Object?> get props => [familyId, limit];
}

class RefreshSuggestions extends SecretaryEvent {
  const RefreshSuggestions();
}

class ExecuteSuggestionAction extends SecretaryEvent {
  final String suggestionId;
  final String action;
  final Map<String, dynamic>? params;

  const ExecuteSuggestionAction({
    required this.suggestionId,
    required this.action,
    this.params,
  });

  @override
  List<Object?> get props => [suggestionId, action, params];
}

class DismissSuggestion extends SecretaryEvent {
  final String suggestionId;

  const DismissSuggestion(this.suggestionId);

  @override
  List<Object?> get props => [suggestionId];
}

// States
abstract class SecretaryState extends Equatable {
  const SecretaryState();

  @override
  List<Object?> get props => [];
}

class SecretaryInitial extends SecretaryState {
  const SecretaryInitial();
}

class SecretaryLoading extends SecretaryState {
  const SecretaryLoading();
}

class SecretaryLoaded extends SecretaryState {
  final List<SmartSuggestion> suggestions;
  final DateTime loadedAt;

  const SecretaryLoaded({
    required this.suggestions,
    required this.loadedAt,
  });

  @override
  List<Object?> get props => [suggestions, loadedAt];
}

class SecretaryError extends SecretaryState {
  final String message;

  const SecretaryError(this.message);

  @override
  List<Object?> get props => [message];
}

class SuggestionActionExecuting extends SecretaryState {
  final String suggestionId;
  final List<SmartSuggestion> suggestions;

  const SuggestionActionExecuting({
    required this.suggestionId,
    required this.suggestions,
  });

  @override
  List<Object?> get props => [suggestionId, suggestions];
}

class SuggestionActionSuccess extends SecretaryState {
  final SuggestionActionResponse response;
  final List<SmartSuggestion> suggestions;

  const SuggestionActionSuccess({
    required this.response,
    required this.suggestions,
  });

  @override
  List<Object?> get props => [response, suggestions];
}

// BLoC
class SecretaryBloc extends Bloc<SecretaryEvent, SecretaryState> {
  final SecretaryRepository _repository;
  String? _familyId;
  int _limit = 10;
  List<SmartSuggestion> _currentSuggestions = [];

  SecretaryBloc(this._repository) : super(const SecretaryInitial()) {
    on<LoadSuggestions>(_onLoadSuggestions);
    on<RefreshSuggestions>(_onRefreshSuggestions);
    on<ExecuteSuggestionAction>(_onExecuteAction);
    on<DismissSuggestion>(_onDismissSuggestion);
  }

  Future<void> _onLoadSuggestions(
    LoadSuggestions event,
    Emitter<SecretaryState> emit,
  ) async {
    emit(const SecretaryLoading());

    try {
      _familyId = event.familyId;
      _limit = event.limit;

      final suggestions = await _repository.getSuggestions(
        familyId: event.familyId,
        limit: event.limit,
      );

      _currentSuggestions = suggestions;

      emit(SecretaryLoaded(
        suggestions: suggestions,
        loadedAt: DateTime.now(),
      ));
    } catch (e) {
      emit(SecretaryError('Failed to load suggestions: ${e.toString()}'));
    }
  }

  Future<void> _onRefreshSuggestions(
    RefreshSuggestions event,
    Emitter<SecretaryState> emit,
  ) async {
    try {
      final suggestions = await _repository.getSuggestions(
        familyId: _familyId,
        limit: _limit,
      );

      _currentSuggestions = suggestions;

      emit(SecretaryLoaded(
        suggestions: suggestions,
        loadedAt: DateTime.now(),
      ));
    } catch (e) {
      emit(SecretaryError('Failed to refresh suggestions: ${e.toString()}'));
    }
  }

  Future<void> _onExecuteAction(
    ExecuteSuggestionAction event,
    Emitter<SecretaryState> emit,
  ) async {
    emit(SuggestionActionExecuting(
      suggestionId: event.suggestionId,
      suggestions: _currentSuggestions,
    ));

    try {
      final response = await _repository.executeAction(
        suggestionId: event.suggestionId,
        action: event.action,
        params: event.params,
      );

      // If action was 'ignore', remove from list
      if (event.action == 'ignore' && response.success) {
        _currentSuggestions = _currentSuggestions
            .where((s) => s.id != event.suggestionId)
            .toList();
      }

      emit(SuggestionActionSuccess(
        response: response,
        suggestions: _currentSuggestions,
      ));
    } catch (e) {
      emit(SecretaryError('Failed to execute action: ${e.toString()}'));
    }
  }

  Future<void> _onDismissSuggestion(
    DismissSuggestion event,
    Emitter<SecretaryState> emit,
  ) async {
    try {
      await _repository.dismissSuggestion(event.suggestionId);

      _currentSuggestions = _currentSuggestions
          .where((s) => s.id != event.suggestionId)
          .toList();

      emit(SecretaryLoaded(
        suggestions: _currentSuggestions,
        loadedAt: DateTime.now(),
      ));
    } catch (e) {
      emit(SecretaryError('Failed to dismiss suggestion: ${e.toString()}'));
    }
  }
}
