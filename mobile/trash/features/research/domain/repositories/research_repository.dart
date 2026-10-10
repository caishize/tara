import '../entities/research_session.dart';
import '../../data/datasources/research_remote_datasource.dart';

abstract class ResearchRepository {
  /// Create a new research session
  Future<ResearchSession> createSession({
    required String topic,
    required ResearchScenario scenario,
  });

  /// Get session details
  Future<ResearchSession> getSession(String sessionId);

  /// List user's research sessions
  Future<List<ResearchSession>> listSessions({int limit = 20});

  /// Delete a research session
  Future<void> deleteSession(String sessionId);

  /// Start search and stream results
  Stream<ResearchStreamEvent> searchStream(String sessionId);

  /// Update selected candidates
  Future<ResearchSession> updateSelection({
    required String sessionId,
    required List<String> selectedIds,
  });

  /// Add a manual item (note or URL)
  Future<ManualItem> addManualItem({
    required String sessionId,
    required String type,
    required String content,
  });

  /// Delete a manual item
  Future<void> deleteManualItem({
    required String sessionId,
    required String itemId,
  });

  /// Start synthesis and stream results
  Stream<SynthesisStreamEvent> synthesizeStream({
    required String sessionId,
    required SynthesisFormat format,
  });
}
