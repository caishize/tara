import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:dartz/dartz.dart';
import 'package:family_secretary/features/chat/presentation/bloc/assistant_bloc.dart';
import 'package:family_secretary/features/chat/domain/repositories/assistant_repository.dart';
import 'package:family_secretary/features/chat/data/datasources/pending_action_datasource.dart';

// Mocks
class MockAssistantRepository extends Mock implements AssistantRepository {}

class MockPendingActionDatasource extends Mock
    implements PendingActionDatasource {}

void main() {
  group('AssistantBloc SyncPendingActions', () {
    late AssistantBloc bloc;
    late MockAssistantRepository mockRepository;
    late MockPendingActionDatasource mockDatasource;

    setUp(() {
      mockRepository = MockAssistantRepository();
      mockDatasource = MockPendingActionDatasource();
      bloc = AssistantBloc(
        repository: mockRepository,
        pendingActionDatasource: mockDatasource,
      );
    });

    tearDown(() {
      bloc.close();
    });

    test('does nothing when state is not AssistantLoaded', () async {
      // Initial state is AssistantInitial, not AssistantLoaded
      when(() => mockDatasource.fetchPending())
          .thenAnswer((_) async => []);

      bloc.add(const AssistantSyncPendingActions());

      // Give bloc time to process
      await Future.delayed(const Duration(milliseconds: 100));

      // fetchPending should not have been called
      verifyNever(() => mockDatasource.fetchPending());
    });

    test('does nothing when pendingActionDatasource is null', () async {
      // Create bloc without datasource
      final blocNoDatasource = AssistantBloc(repository: mockRepository);

      // Transition to loaded state
      when(() => mockRepository.loadMoreHistory(
              sessionId: any(named: 'sessionId'),
              beforeId: any(named: 'beforeId'),
              limit: any(named: 'limit')))
          .thenAnswer((_) async => const Right((
                messages: [],
                hasMore: false,
                oldestId: null,
              )));
      blocNoDatasource.add(const AssistantLoadHistory('test-session'));

      await expectLater(
        blocNoDatasource.stream,
        emitsThrough(isA<AssistantLoaded>()),
      );

      blocNoDatasource.add(const AssistantSyncPendingActions());
      await Future.delayed(const Duration(milliseconds: 100));

      // No crash, no fetch
      verifyNever(() => mockDatasource.fetchPending());

      await blocNoDatasource.close();
    });

    test('injects pending actions as confirmation_required messages', () async {
      // Transition to loaded state
      when(() => mockRepository.loadMoreHistory(
              sessionId: any(named: 'sessionId'),
              beforeId: any(named: 'beforeId'),
              limit: any(named: 'limit')))
          .thenAnswer((_) async => const Right((
                messages: [],
                hasMore: false,
                oldestId: null,
              )));
      bloc.add(const AssistantLoadHistory('test-session'));

      await expectLater(
        bloc.stream,
        emitsThrough(isA<AssistantLoaded>()),
      );

      // Mock pending actions
      when(() => mockDatasource.fetchPending()).thenAnswer((_) async => [
            {
              'id': 'action-001',
              'action_type': 'purchase',
              'display_title': '确认购买',
              'display_details': [
                {'label': '商品', 'value': 'AirPods'},
              ],
            },
          ]);

      final expectation = expectLater(
        bloc.stream,
        emitsThrough(
          isA<AssistantLoaded>().having(
            (state) => state.messages.any(
              (m) =>
                  m.intent == 'confirmation_required' &&
                  m.data?['action_id'] == 'action-001',
            ),
            'has injected action',
            isTrue,
          ),
        ),
      );

      bloc.add(const AssistantSyncPendingActions());
      await expectation;
    });

    test('skips duplicate actions already in messages', () async {
      // Transition to loaded
      when(() => mockRepository.loadMoreHistory(
              sessionId: any(named: 'sessionId'),
              beforeId: any(named: 'beforeId'),
              limit: any(named: 'limit')))
          .thenAnswer((_) async => const Right((
                messages: [],
                hasMore: false,
                oldestId: null,
              )));
      bloc.add(const AssistantLoadHistory('test-session'));
      await expectLater(
        bloc.stream,
        emitsThrough(isA<AssistantLoaded>()),
      );

      // First sync — inject action-dup
      when(() => mockDatasource.fetchPending()).thenAnswer((_) async => [
            {
              'id': 'action-dup',
              'action_type': 'purchase',
              'display_title': '确认',
              'display_details': [],
            },
          ]);
      bloc.add(const AssistantSyncPendingActions());
      await expectLater(
        bloc.stream,
        emitsThrough(
          isA<AssistantLoaded>().having(
            (s) => s.messages.where((m) => m.data?['action_id'] == 'action-dup').length,
            'action count',
            equals(1),
          ),
        ),
      );

      // Second sync with same action — should not duplicate
      bloc.add(const AssistantSyncPendingActions());
      await Future.delayed(const Duration(milliseconds: 200));

      final state = bloc.state as AssistantLoaded;
      final count = state.messages
          .where((m) => m.data?['action_id'] == 'action-dup')
          .length;
      expect(count, equals(1));
    });

    test('does nothing when fetchPending returns empty', () async {
      // Transition to loaded
      when(() => mockRepository.loadMoreHistory(
              sessionId: any(named: 'sessionId'),
              beforeId: any(named: 'beforeId'),
              limit: any(named: 'limit')))
          .thenAnswer((_) async => const Right((
                messages: [],
                hasMore: false,
                oldestId: null,
              )));
      bloc.add(const AssistantLoadHistory('test-session'));
      await expectLater(
        bloc.stream,
        emitsThrough(isA<AssistantLoaded>()),
      );

      when(() => mockDatasource.fetchPending()).thenAnswer((_) async => []);

      final stateBefore = bloc.state as AssistantLoaded;
      final msgCountBefore = stateBefore.messages.length;

      bloc.add(const AssistantSyncPendingActions());
      await Future.delayed(const Duration(milliseconds: 100));

      final stateAfter = bloc.state as AssistantLoaded;
      expect(stateAfter.messages.length, equals(msgCountBefore));
    });

    test('handles fetchPending exception gracefully', () async {
      // Transition to loaded
      when(() => mockRepository.loadMoreHistory(
              sessionId: any(named: 'sessionId'),
              beforeId: any(named: 'beforeId'),
              limit: any(named: 'limit')))
          .thenAnswer((_) async => const Right((
                messages: [],
                hasMore: false,
                oldestId: null,
              )));
      bloc.add(const AssistantLoadHistory('test-session'));
      await expectLater(
        bloc.stream,
        emitsThrough(isA<AssistantLoaded>()),
      );

      when(() => mockDatasource.fetchPending())
          .thenThrow(Exception('Network error'));

      // Should not crash the bloc
      bloc.add(const AssistantSyncPendingActions());
      await Future.delayed(const Duration(milliseconds: 100));

      // State should still be AssistantLoaded (not error)
      expect(bloc.state, isA<AssistantLoaded>());
    });
  });
}
