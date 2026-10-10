import '../../domain/entities/research_session.dart';
import '../../domain/repositories/research_repository.dart';
import '../datasources/research_remote_datasource.dart';

class ResearchRepositoryImpl implements ResearchRepository {
  final ResearchRemoteDataSource remoteDataSource;

  ResearchRepositoryImpl({required this.remoteDataSource});

  @override
  Future<ResearchSession> createSession({
    required String topic,
    required ResearchScenario scenario,
  }) async {
    return await remoteDataSource.createSession(
      topic: topic,
      scenario: scenario,
    );
  }

  @override
  Future<ResearchSession> getSession(String sessionId) async {
    return await remoteDataSource.getSession(sessionId);
  }

  @override
  Future<List<ResearchSession>> listSessions({int limit = 20}) async {
    return await remoteDataSource.listSessions(limit: limit);
  }

  @override
  Future<void> deleteSession(String sessionId) async {
    await remoteDataSource.deleteSession(sessionId);
  }

  @override
  Stream<ResearchStreamEvent> searchStream(String sessionId) {
    return remoteDataSource.searchStream(sessionId);
  }

  @override
  Future<ResearchSession> updateSelection({
    required String sessionId,
    required List<String> selectedIds,
  }) async {
    return await remoteDataSource.updateSelection(
      sessionId: sessionId,
      selectedIds: selectedIds,
    );
  }

  @override
  Future<ManualItem> addManualItem({
    required String sessionId,
    required String type,
    required String content,
  }) async {
    return await remoteDataSource.addManualItem(
      sessionId: sessionId,
      type: type,
      content: content,
    );
  }

  @override
  Future<void> deleteManualItem({
    required String sessionId,
    required String itemId,
  }) async {
    await remoteDataSource.deleteManualItem(
      sessionId: sessionId,
      itemId: itemId,
    );
  }

  @override
  Stream<SynthesisStreamEvent> synthesizeStream({
    required String sessionId,
    required SynthesisFormat format,
  }) {
    return remoteDataSource.synthesizeStream(
      sessionId: sessionId,
      format: format,
    );
  }
}
