import 'package:bloc_test/bloc_test.dart';
import 'package:dartz/dartz.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:family_secretary/core/error/failures.dart';
import 'package:family_secretary/features/chat/domain/entities/chat_message.dart';
import 'package:family_secretary/features/chat/domain/repositories/assistant_repository.dart';
import 'package:family_secretary/features/chat/presentation/bloc/assistant_bloc.dart';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

class MockAssistantRepository extends Mock implements AssistantRepository {}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

ChatMessage _makeMsg(String id) => ChatMessage(
      id: id,
      sessionId: 'session-1',
      role: MessageRole.user,
      content: 'msg $id',
      createdAt: DateTime.now(),
    );

// A minimal AssistantLoaded seeded with necessary fields for load-more tests.
AssistantLoaded _loadedState({
  List<ChatMessage> messages = const [],
  bool historyHasMore = true,
  bool isLoadingHistory = false,
  String? oldestMessageId,
  String sessionId = 'session-1',
}) =>
    AssistantLoaded(
      messages: messages,
      sessionId: sessionId,
      historyHasMore: historyHasMore,
      isLoadingHistory: isLoadingHistory,
      oldestMessageId: oldestMessageId,
    );

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  late MockAssistantRepository mockRepository;

  setUp(() {
    mockRepository = MockAssistantRepository();
  });

  group('AssistantBloc — LoadMoreHistoryRequested', () {
    test('ignored when state is not AssistantLoaded', () async {
      // Bloc starts in AssistantInitial — event should be silently ignored.
      final bloc = AssistantBloc(repository: mockRepository);
      bloc.add(const LoadMoreHistoryRequested());
      // No state change expected; stream completes without emission.
      await expectLater(
        bloc.stream.timeout(const Duration(milliseconds: 100),
            onTimeout: (sink) => sink.close()),
        emitsDone,
      );
      bloc.close();
    });

    blocTest<AssistantBloc, AssistantState>(
      'ignored when isLoadingHistory is already true',
      build: () => AssistantBloc(repository: mockRepository),
      seed: () => _loadedState(isLoadingHistory: true, historyHasMore: true),
      act: (bloc) => bloc.add(const LoadMoreHistoryRequested()),
      // No new state emitted — bloc returns early.
      expect: () => <AssistantState>[],
      verify: (_) {
        verifyNever(() => mockRepository.loadMoreHistory(
              sessionId: any(named: 'sessionId'),
              beforeId: any(named: 'beforeId'),
              limit: any(named: 'limit'),
            ));
      },
    );

    blocTest<AssistantBloc, AssistantState>(
      'ignored when historyHasMore is false',
      build: () => AssistantBloc(repository: mockRepository),
      seed: () => _loadedState(historyHasMore: false),
      act: (bloc) => bloc.add(const LoadMoreHistoryRequested()),
      expect: () => <AssistantState>[],
      verify: (_) {
        verifyNever(() => mockRepository.loadMoreHistory(
              sessionId: any(named: 'sessionId'),
              beforeId: any(named: 'beforeId'),
              limit: any(named: 'limit'),
            ));
      },
    );

    blocTest<AssistantBloc, AssistantState>(
      'happy path — merges older messages at the front and updates hasMore',
      build: () {
        // Repository returns two older messages plus hasMore=true.
        final olderMessages = [_makeMsg('old-1'), _makeMsg('old-2')];
        when(() => mockRepository.loadMoreHistory(
              sessionId: any(named: 'sessionId'),
              beforeId: any(named: 'beforeId'),
              limit: any(named: 'limit'),
            )).thenAnswer((_) async => Right((
              messages: olderMessages,
              hasMore: true,
              oldestId: 'old-1',
            )));
        return AssistantBloc(repository: mockRepository);
      },
      seed: () => _loadedState(
        messages: [_makeMsg('current-1')],
        historyHasMore: true,
        oldestMessageId: 'current-1',
      ),
      act: (bloc) => bloc.add(const LoadMoreHistoryRequested()),
      expect: () => [
        // First emission: loading flag set
        isA<AssistantLoaded>().having(
          (s) => s.isLoadingHistory,
          'isLoadingHistory',
          true,
        ),
        // Second emission: messages merged, loading cleared
        isA<AssistantLoaded>()
            .having((s) => s.isLoadingHistory, 'isLoadingHistory', false)
            .having((s) => s.historyHasMore, 'historyHasMore', true)
            .having((s) => s.oldestMessageId, 'oldestMessageId', 'old-1')
            .having(
              (s) => s.messages.map((m) => m.id).toList(),
              'message ids',
              ['old-1', 'old-2', 'current-1'],
            ),
      ],
    );

    blocTest<AssistantBloc, AssistantState>(
      'api failure — resets isLoadingHistory to false and sets error',
      build: () {
        when(() => mockRepository.loadMoreHistory(
              sessionId: any(named: 'sessionId'),
              beforeId: any(named: 'beforeId'),
              limit: any(named: 'limit'),
            )).thenAnswer(
          (_) async => const Left(ServerFailure('Network error')),
        );
        return AssistantBloc(repository: mockRepository);
      },
      seed: () => _loadedState(historyHasMore: true),
      act: (bloc) => bloc.add(const LoadMoreHistoryRequested()),
      expect: () => [
        // Loading starts
        isA<AssistantLoaded>().having(
          (s) => s.isLoadingHistory,
          'isLoadingHistory',
          true,
        ),
        // Loading reset on failure
        isA<AssistantLoaded>()
            .having((s) => s.isLoadingHistory, 'isLoadingHistory', false)
            .having((s) => s.error, 'error', isNotNull),
      ],
    );
  });
}
