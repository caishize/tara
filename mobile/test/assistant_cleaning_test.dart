import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:dartz/dartz.dart';
import 'package:family_secretary/features/chat/presentation/bloc/assistant_bloc.dart';
import 'package:family_secretary/features/chat/domain/repositories/assistant_repository.dart';

// Mock dependencies
class MockAssistantRepository extends Mock implements AssistantRepository {}

void main() {
  group('AssistantBloc XML Cleaning', () {
    late AssistantBloc assistantBloc;
    late MockAssistantRepository mockRepository;

    setUp(() {
      mockRepository = MockAssistantRepository();
      assistantBloc = AssistantBloc(repository: mockRepository);
    });

    tearDown(() {
      assistantBloc.close();
    });

    test('should clean raw XML <function> tags from streaming content', () async {
      // Seed the bloc with initial streaming state
      // We can't easily seed with `bloc_test` missing, so we have to emit state or rely on start
      // But AssistantBloc starts at AssistantInitial.
      // We'll trust the event handler logic handles state checks.
      // However, _onStreamChunkReceived requires state to be AssistantLoaded.
      
      // So we must first verify we can get it into AssistantLoaded.
      // Or we can just test the logic method if it was public... it is not.
      
      // WORKAROUND: We will emit a fake AssistantLoaded state if possible, 
      // but we can't emit from outside.
      // We have to trigger an event that transitions to AssistantLoaded.
      // AssistantLoadHistory or AssistantStartChat would work.
      
      // Correct approach without bloc_test's seed:
      // We added `AssistantLoadHistory` handler.
      // We will mock `getSessionHistory` to return empty list.
      
      // Stub repository
      when(() => mockRepository.loadMoreHistory(
            sessionId: any(named: 'sessionId'),
            beforeId: any(named: 'beforeId'),
            limit: any(named: 'limit'),
          )).thenAnswer((_) async => const Right((
            messages: [],
            hasMore: false,
            oldestId: null,
          )));

      // Transition to Loaded
      assistantBloc.add(const AssistantLoadHistory('test-session'));
      
      await expectLater(
        assistantBloc.stream,
        emitsThrough(isA<AssistantLoaded>()),
      );

      // Now we are in AssistantLoaded.
      // Verify cleaning logic.
      final futureExpectation = expectLater(
        assistantBloc.stream,
        emitsThrough(
          isA<AssistantLoaded>().having(
            (state) => state.streamingContent,
            'streamingContent',
            'Here is the plan. ', // Should remain same, XML stripped
          ),
        ),
      );
      
      // Inject "dirty" content manually into state? No, we use the event.
      // We need to set streamingContent first.
      
      // Send a chunk that sets content (and clean it?)
      // Wait, the logic is: newContent = current.streamingContent + chunk
      // So if we send "Here is the plan. <function...>...</function>"
      assistantBloc.add(const AssistantStreamChunkReceived(
        'Here is the plan. <function=web_search><parameter=query>Shenzhen travel</parameter></function>'
      ));
      
      await futureExpectation;
    });

    test('should clean raw XML tags when they are split across chunks', () async {
       // Setup as Loaded
      when(() => mockRepository.loadMoreHistory(
            sessionId: any(named: 'sessionId'),
            beforeId: any(named: 'beforeId'),
            limit: any(named: 'limit'),
          )).thenAnswer((_) async => const Right((
            messages: [],
            hasMore: false,
            oldestId: null,
          )));
      assistantBloc.add(const AssistantLoadHistory('test-session'));
      await expectLater(assistantBloc.stream, emitsThrough(isA<AssistantLoaded>()));

      // 1. Send first chunk with partial tag (first chunk always triggers full emit)
      assistantBloc.add(const AssistantStreamChunkReceived('Data: <function=test>'));

      // Wait for the state update — partial tag is NOT stripped (no closing tag yet)
      await expectLater(
        assistantBloc.stream,
        emitsThrough(isA<AssistantLoaded>().having((s) => s.streamingContent, 'content', 'Data: <function=test>')),
      );

      // Wait > 100ms to bypass the chunk throttle so the next chunk triggers a full emit with cleaning
      await Future.delayed(const Duration(milliseconds: 150));

      // 2. Send closing chunk — now outside throttle window, full emit with regex cleaning runs
      assistantBloc.add(const AssistantStreamChunkReceived('args</function>'));

      // Now the whole thing should match and be removed:
      // 'Data: <function=test>args</function>' -> 'Data: '
      await expectLater(
        assistantBloc.stream,
        emitsThrough(isA<AssistantLoaded>().having(
            (state) => state.streamingContent,
            'streamingContent',
            'Data: ',
          )),
      );
    });
  });
}

// Minimal Right implementation for Either if dartz is not exported or needed
// Checking imports: pubspec has dartz.
