import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../domain/entities/research_session.dart';
import '../../domain/repositories/research_repository.dart';
import '../../data/datasources/research_remote_datasource.dart';

// Events
abstract class ResearchEvent extends Equatable {
  const ResearchEvent();

  @override
  List<Object?> get props => [];
}

class CreateSessionEvent extends ResearchEvent {
  final String topic;
  final ResearchScenario scenario;

  const CreateSessionEvent({required this.topic, required this.scenario});

  @override
  List<Object?> get props => [topic, scenario];
}

class LoadSessionEvent extends ResearchEvent {
  final String sessionId;

  const LoadSessionEvent({required this.sessionId});

  @override
  List<Object?> get props => [sessionId];
}

class StartSearchEvent extends ResearchEvent {
  const StartSearchEvent();
}

class ToggleCandidateEvent extends ResearchEvent {
  final String candidateId;

  const ToggleCandidateEvent({required this.candidateId});

  @override
  List<Object?> get props => [candidateId];
}

class SelectAllCandidatesEvent extends ResearchEvent {
  const SelectAllCandidatesEvent();
}

class ClearSelectionEvent extends ResearchEvent {
  const ClearSelectionEvent();
}

class AddManualItemEvent extends ResearchEvent {
  final String type;
  final String content;

  const AddManualItemEvent({required this.type, required this.content});

  @override
  List<Object?> get props => [type, content];
}

class RemoveManualItemEvent extends ResearchEvent {
  final String itemId;

  const RemoveManualItemEvent({required this.itemId});

  @override
  List<Object?> get props => [itemId];
}

class GenerateSynthesisEvent extends ResearchEvent {
  final SynthesisFormat format;

  const GenerateSynthesisEvent({required this.format});

  @override
  List<Object?> get props => [format];
}

class ResetSessionEvent extends ResearchEvent {
  const ResetSessionEvent();
}

// State
class ResearchState extends Equatable {
  final ResearchSession? session;
  final List<ResearchCandidate> candidates;
  final Set<String> selectedIds;
  final List<ManualItem> manualItems;
  final String synthesisContent;
  final List<SynthesisSource> synthesisSources;
  final bool isLoading;
  final bool isSearching;
  final bool isSynthesizing;
  final String? progressMessage;
  final String? error;

  const ResearchState({
    this.session,
    this.candidates = const [],
    this.selectedIds = const {},
    this.manualItems = const [],
    this.synthesisContent = '',
    this.synthesisSources = const [],
    this.isLoading = false,
    this.isSearching = false,
    this.isSynthesizing = false,
    this.progressMessage,
    this.error,
  });

  ResearchState copyWith({
    ResearchSession? session,
    List<ResearchCandidate>? candidates,
    Set<String>? selectedIds,
    List<ManualItem>? manualItems,
    String? synthesisContent,
    List<SynthesisSource>? synthesisSources,
    bool? isLoading,
    bool? isSearching,
    bool? isSynthesizing,
    String? progressMessage,
    String? error,
    bool clearError = false,
    bool clearProgress = false,
  }) {
    return ResearchState(
      session: session ?? this.session,
      candidates: candidates ?? this.candidates,
      selectedIds: selectedIds ?? this.selectedIds,
      manualItems: manualItems ?? this.manualItems,
      synthesisContent: synthesisContent ?? this.synthesisContent,
      synthesisSources: synthesisSources ?? this.synthesisSources,
      isLoading: isLoading ?? this.isLoading,
      isSearching: isSearching ?? this.isSearching,
      isSynthesizing: isSynthesizing ?? this.isSynthesizing,
      progressMessage: clearProgress ? null : (progressMessage ?? this.progressMessage),
      error: clearError ? null : (error ?? this.error),
    );
  }

  int get totalSelectedCount => selectedIds.length + manualItems.length;

  @override
  List<Object?> get props => [
        session,
        candidates,
        selectedIds,
        manualItems,
        synthesisContent,
        synthesisSources,
        isLoading,
        isSearching,
        isSynthesizing,
        progressMessage,
        error,
      ];
}

// Bloc
class ResearchBloc extends Bloc<ResearchEvent, ResearchState> {
  final ResearchRepository repository;

  ResearchBloc({required this.repository}) : super(const ResearchState()) {
    on<CreateSessionEvent>(_onCreateSession);
    on<LoadSessionEvent>(_onLoadSession);
    on<StartSearchEvent>(_onStartSearch);
    on<ToggleCandidateEvent>(_onToggleCandidate);
    on<SelectAllCandidatesEvent>(_onSelectAll);
    on<ClearSelectionEvent>(_onClearSelection);
    on<AddManualItemEvent>(_onAddManualItem);
    on<RemoveManualItemEvent>(_onRemoveManualItem);
    on<GenerateSynthesisEvent>(_onGenerateSynthesis);
    on<ResetSessionEvent>(_onReset);
  }

  Future<void> _onCreateSession(
    CreateSessionEvent event,
    Emitter<ResearchState> emit,
  ) async {
    emit(state.copyWith(isLoading: true, clearError: true));

    try {
      final session = await repository.createSession(
        topic: event.topic,
        scenario: event.scenario,
      );

      emit(state.copyWith(
        session: session,
        candidates: [],
        selectedIds: {},
        manualItems: [],
        synthesisContent: '',
        synthesisSources: [],
        isLoading: false,
      ));

      // Auto-start search
      add(const StartSearchEvent());
    } catch (e) {
      emit(state.copyWith(
        isLoading: false,
        error: '创建研究会话失败: ${e.toString()}',
      ));
    }
  }

  Future<void> _onLoadSession(
    LoadSessionEvent event,
    Emitter<ResearchState> emit,
  ) async {
    emit(state.copyWith(isLoading: true, clearError: true));

    try {
      final session = await repository.getSession(event.sessionId);

      emit(state.copyWith(
        session: session,
        candidates: session.candidates,
        selectedIds: session.selectedIds.toSet(),
        manualItems: session.manualItems,
        synthesisContent: session.synthesis?.content ?? '',
        synthesisSources: session.synthesis?.sources ?? [],
        isLoading: false,
      ));
    } catch (e) {
      emit(state.copyWith(
        isLoading: false,
        error: '加载研究会话失败: ${e.toString()}',
      ));
    }
  }

  Future<void> _onStartSearch(
    StartSearchEvent event,
    Emitter<ResearchState> emit,
  ) async {
    if (state.session == null) return;

    emit(state.copyWith(
      isSearching: true,
      candidates: [],
      clearError: true,
      progressMessage: '正在搜索...',
    ));

    try {
      await emit.forEach<ResearchStreamEvent>(
        repository.searchStream(state.session!.id),
        onData: (streamEvent) {
          if (streamEvent.type == ResearchEventType.candidate && streamEvent.candidate != null) {
            final newCandidates = [...state.candidates, streamEvent.candidate!];
            return state.copyWith(candidates: newCandidates);
          } else if (streamEvent.type == ResearchEventType.progress) {
            return state.copyWith(progressMessage: streamEvent.message);
          } else if (streamEvent.type == ResearchEventType.done) {
            return state.copyWith(isSearching: false, clearProgress: true);
          } else if (streamEvent.type == ResearchEventType.error) {
            return state.copyWith(
              isSearching: false,
              error: streamEvent.error,
              clearProgress: true,
            );
          }
          return state;
        },
      );
      // Stream completed naturally
      if (state.isSearching) {
        emit(state.copyWith(isSearching: false, clearProgress: true));
      }
    } catch (error) {
      emit(state.copyWith(
        isSearching: false,
        error: '搜索失败: $error',
        clearProgress: true,
      ));
    }
  }

  Future<void> _onToggleCandidate(
    ToggleCandidateEvent event,
    Emitter<ResearchState> emit,
  ) async {
    final newSelectedIds = Set<String>.from(state.selectedIds);
    if (newSelectedIds.contains(event.candidateId)) {
      newSelectedIds.remove(event.candidateId);
    } else {
      newSelectedIds.add(event.candidateId);
    }
    emit(state.copyWith(selectedIds: newSelectedIds));

    // Sync with server if session exists
    if (state.session != null) {
      try {
        await repository.updateSelection(
          sessionId: state.session!.id,
          selectedIds: newSelectedIds.toList(),
        );
      } catch (_) {
        // Ignore sync errors
      }
    }
  }

  void _onSelectAll(
    SelectAllCandidatesEvent event,
    Emitter<ResearchState> emit,
  ) {
    final allIds = state.candidates.map((c) => c.id).toSet();
    emit(state.copyWith(selectedIds: allIds));

    // Sync with server (fire-and-forget)
    if (state.session != null) {
      repository.updateSelection(
        sessionId: state.session!.id,
        selectedIds: allIds.toList(),
      ).then((_) {}, onError: (_) {});
    }
  }

  void _onClearSelection(
    ClearSelectionEvent event,
    Emitter<ResearchState> emit,
  ) {
    emit(state.copyWith(selectedIds: {}));

    // Sync with server (fire-and-forget)
    if (state.session != null) {
      repository.updateSelection(
        sessionId: state.session!.id,
        selectedIds: [],
      ).then((_) {}, onError: (_) {});
    }
  }

  Future<void> _onAddManualItem(
    AddManualItemEvent event,
    Emitter<ResearchState> emit,
  ) async {
    if (state.session == null) return;

    emit(state.copyWith(isLoading: true, clearError: true));

    try {
      final item = await repository.addManualItem(
        sessionId: state.session!.id,
        type: event.type,
        content: event.content,
      );

      emit(state.copyWith(
        manualItems: [...state.manualItems, item],
        isLoading: false,
      ));
    } catch (e) {
      emit(state.copyWith(
        isLoading: false,
        error: '添加失败: ${e.toString()}',
      ));
    }
  }

  Future<void> _onRemoveManualItem(
    RemoveManualItemEvent event,
    Emitter<ResearchState> emit,
  ) async {
    if (state.session == null) return;

    try {
      await repository.deleteManualItem(
        sessionId: state.session!.id,
        itemId: event.itemId,
      );

      emit(state.copyWith(
        manualItems: state.manualItems.where((i) => i.id != event.itemId).toList(),
      ));
    } catch (e) {
      emit(state.copyWith(error: '删除失败: ${e.toString()}'));
    }
  }

  Future<void> _onGenerateSynthesis(
    GenerateSynthesisEvent event,
    Emitter<ResearchState> emit,
  ) async {
    if (state.session == null) return;
    if (state.totalSelectedCount == 0) {
      emit(state.copyWith(error: '请先选择要综合的内容'));
      return;
    }

    emit(state.copyWith(
      isSynthesizing: true,
      synthesisContent: '',
      synthesisSources: [],
      clearError: true,
      progressMessage: '正在生成报告...',
    ));

    try {
      await emit.forEach<SynthesisStreamEvent>(
        repository.synthesizeStream(
          sessionId: state.session!.id,
          format: event.format,
        ),
        onData: (streamEvent) {
          if (streamEvent.type == SynthesisEventType.content && streamEvent.content != null) {
            return state.copyWith(
              synthesisContent: state.synthesisContent + streamEvent.content!,
            );
          } else if (streamEvent.type == SynthesisEventType.sources && streamEvent.sources != null) {
            return state.copyWith(synthesisSources: streamEvent.sources!);
          } else if (streamEvent.type == SynthesisEventType.done) {
            return state.copyWith(isSynthesizing: false, clearProgress: true);
          } else if (streamEvent.type == SynthesisEventType.error) {
            return state.copyWith(
              isSynthesizing: false,
              error: streamEvent.error,
              clearProgress: true,
            );
          }
          return state;
        },
      );
      // Stream completed naturally
      if (state.isSynthesizing) {
        emit(state.copyWith(isSynthesizing: false, clearProgress: true));
      }
    } catch (error) {
      emit(state.copyWith(
        isSynthesizing: false,
        error: '生成报告失败: $error',
        clearProgress: true,
      ));
    }
  }

  void _onReset(
    ResetSessionEvent event,
    Emitter<ResearchState> emit,
  ) {
    emit(const ResearchState());
  }
}
