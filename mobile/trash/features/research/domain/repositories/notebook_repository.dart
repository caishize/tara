import '../entities/notebook.dart';
import '../../data/datasources/notebook_remote_datasource.dart';

/// Repository interface for notebook operations
abstract class NotebookRepository {
  /// Create a new notebook
  Future<Notebook> createNotebook({
    required String name,
    String? description,
    String icon,
    String color,
  });

  /// List user's notebooks
  Future<List<Notebook>> listNotebooks({
    int limit,
    int offset,
    String? status,
  });

  /// Get notebook by ID with sources
  Future<Notebook> getNotebook(String notebookId);

  /// Update notebook
  Future<Notebook> updateNotebook({
    required String notebookId,
    String? name,
    String? description,
    String? icon,
    String? color,
  });

  /// Delete notebook
  Future<void> deleteNotebook(String notebookId);

  /// Add source to notebook
  Future<NotebookSource> addSource({
    required String notebookId,
    required String type,
    required String content,
    String? title,
  });

  /// List sources in notebook
  Future<List<NotebookSource>> listSources({
    required String notebookId,
    String? sourceType,
  });

  /// Delete source
  Future<void> deleteSource({
    required String notebookId,
    required String sourceId,
  });

  /// Chat with notebook (stream)
  Stream<ChatStreamEvent> chatStream({
    required String notebookId,
    required String question,
    bool includeHistory,
  });

  /// Summarize notebook (stream)
  Stream<ChatStreamEvent> summarizeStream({
    required String notebookId,
    required String format,
  });

  /// Clear chat history
  Future<void> clearChatHistory(String notebookId);
}
