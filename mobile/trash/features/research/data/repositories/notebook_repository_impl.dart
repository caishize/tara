import '../../domain/entities/notebook.dart';
import '../../domain/repositories/notebook_repository.dart';
import '../datasources/notebook_remote_datasource.dart';

/// Implementation of NotebookRepository
class NotebookRepositoryImpl implements NotebookRepository {
  final NotebookRemoteDataSource remoteDataSource;

  NotebookRepositoryImpl({required this.remoteDataSource});

  @override
  Future<Notebook> createNotebook({
    required String name,
    String? description,
    String icon = '📚',
    String color = '#6366F1',
  }) async {
    return remoteDataSource.createNotebook(
      name: name,
      description: description,
      icon: icon,
      color: color,
    );
  }

  @override
  Future<List<Notebook>> listNotebooks({
    int limit = 50,
    int offset = 0,
    String? status,
  }) async {
    return remoteDataSource.listNotebooks(
      limit: limit,
      offset: offset,
      status: status,
    );
  }

  @override
  Future<Notebook> getNotebook(String notebookId) async {
    return remoteDataSource.getNotebook(notebookId);
  }

  @override
  Future<Notebook> updateNotebook({
    required String notebookId,
    String? name,
    String? description,
    String? icon,
    String? color,
  }) async {
    return remoteDataSource.updateNotebook(
      notebookId: notebookId,
      name: name,
      description: description,
      icon: icon,
      color: color,
    );
  }

  @override
  Future<void> deleteNotebook(String notebookId) async {
    await remoteDataSource.deleteNotebook(notebookId);
  }

  @override
  Future<NotebookSource> addSource({
    required String notebookId,
    required String type,
    required String content,
    String? title,
  }) async {
    return remoteDataSource.addSource(
      notebookId: notebookId,
      type: type,
      content: content,
      title: title,
    );
  }

  @override
  Future<List<NotebookSource>> listSources({
    required String notebookId,
    String? sourceType,
  }) async {
    return remoteDataSource.listSources(
      notebookId: notebookId,
      sourceType: sourceType,
    );
  }

  @override
  Future<void> deleteSource({
    required String notebookId,
    required String sourceId,
  }) async {
    await remoteDataSource.deleteSource(
      notebookId: notebookId,
      sourceId: sourceId,
    );
  }

  @override
  Stream<ChatStreamEvent> chatStream({
    required String notebookId,
    required String question,
    bool includeHistory = true,
  }) {
    return remoteDataSource.chatStream(
      notebookId: notebookId,
      question: question,
      includeHistory: includeHistory,
    );
  }

  @override
  Stream<ChatStreamEvent> summarizeStream({
    required String notebookId,
    required String format,
  }) {
    return remoteDataSource.summarizeStream(
      notebookId: notebookId,
      format: format,
    );
  }

  @override
  Future<void> clearChatHistory(String notebookId) async {
    await remoteDataSource.clearChatHistory(notebookId);
  }
}
