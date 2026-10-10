import 'dart:async';
import 'dart:convert';
import 'package:dio/dio.dart';
import '../../../../core/network/api_client.dart';
import '../models/notebook_model.dart';

/// SSE event types for notebook chat
enum ChatEventType { thinking, content, sources, done, error }

/// Parsed SSE event for notebook chat
class ChatStreamEvent {
  final ChatEventType type;
  final String? message;
  final String? content;
  final List<ChatSourceModel>? sources;
  final String? error;

  ChatStreamEvent({
    required this.type,
    this.message,
    this.content,
    this.sources,
    this.error,
  });
}

/// Remote data source for notebook operations
class NotebookRemoteDataSource {
  final ApiClient apiClient;
  final Dio dio;

  NotebookRemoteDataSource({
    required this.apiClient,
    required this.dio,
  });

  /// Create a new notebook
  Future<NotebookModel> createNotebook({
    required String name,
    String? description,
    String icon = '📚',
    String color = '#6366F1',
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/research/notebooks',
      data: {
        'name': name,
        'description': description,
        'icon': icon,
        'color': color,
      },
    );
    return NotebookModel.fromJson(response);
  }

  /// List user's notebooks
  Future<List<NotebookModel>> listNotebooks({
    int limit = 50,
    int offset = 0,
    String? status,
  }) async {
    final response = await apiClient.get<List<dynamic>>(
      '/research/notebooks',
      queryParameters: {
        'limit': limit,
        'offset': offset,
        if (status != null) 'status': status,
      },
    );
    return response
        .map((n) => NotebookModel.fromJson(n as Map<String, dynamic>))
        .toList();
  }

  /// Get notebook by ID with sources
  Future<NotebookModel> getNotebook(String notebookId) async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/research/notebooks/$notebookId',
    );
    return NotebookModel.fromJson(response);
  }

  /// Update notebook
  Future<NotebookModel> updateNotebook({
    required String notebookId,
    String? name,
    String? description,
    String? icon,
    String? color,
  }) async {
    final response = await apiClient.patch<Map<String, dynamic>>(
      '/research/notebooks/$notebookId',
      data: {
        if (name != null) 'name': name,
        if (description != null) 'description': description,
        if (icon != null) 'icon': icon,
        if (color != null) 'color': color,
      },
    );
    return NotebookModel.fromJson(response);
  }

  /// Delete notebook
  Future<void> deleteNotebook(String notebookId) async {
    await apiClient.delete<Map<String, dynamic>>(
      '/research/notebooks/$notebookId',
    );
  }

  /// Add a source to notebook
  Future<NotebookSourceModel> addSource({
    required String notebookId,
    required String type,
    required String content,
    String? title,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/research/notebooks/$notebookId/sources',
      data: {
        'type': type,
        'content': content,
        if (title != null) 'title': title,
      },
    );
    return NotebookSourceModel.fromJson(response);
  }

  /// List sources in notebook
  Future<List<NotebookSourceModel>> listSources({
    required String notebookId,
    String? sourceType,
  }) async {
    final response = await apiClient.get<List<dynamic>>(
      '/research/notebooks/$notebookId/sources',
      queryParameters: {
        if (sourceType != null) 'source_type': sourceType,
      },
    );
    return response
        .map((s) => NotebookSourceModel.fromJson(s as Map<String, dynamic>))
        .toList();
  }

  /// Delete a source
  Future<void> deleteSource({
    required String notebookId,
    required String sourceId,
  }) async {
    await apiClient.delete<Map<String, dynamic>>(
      '/research/notebooks/$notebookId/sources/$sourceId',
    );
  }

  /// Chat with notebook (SSE stream)
  Stream<ChatStreamEvent> chatStream({
    required String notebookId,
    required String question,
    bool includeHistory = true,
  }) async* {
    try {
      final response = await dio.post(
        '/research/notebooks/$notebookId/chat',
        data: {
          'question': question,
          'include_history': includeHistory,
        },
        options: Options(
          responseType: ResponseType.stream,
          headers: {
            'Accept': 'text/event-stream',
            'Cache-Control': 'no-cache',
          },
        ),
      );

      final stream = response.data.stream as Stream<List<int>>;
      String buffer = '';

      await for (final chunk in stream) {
        buffer += utf8.decode(chunk);

        while (buffer.contains('\n\n')) {
          final endIndex = buffer.indexOf('\n\n');
          final eventData = buffer.substring(0, endIndex);
          buffer = buffer.substring(endIndex + 2);

          for (final line in eventData.split('\n')) {
            if (line.startsWith('data: ')) {
              final data = line.substring(6);
              if (data == '[DONE]') {
                yield ChatStreamEvent(type: ChatEventType.done);
                return;
              }
              try {
                final json = jsonDecode(data) as Map<String, dynamic>;
                final type = json['type'] as String?;

                if (type == 'thinking') {
                  yield ChatStreamEvent(
                    type: ChatEventType.thinking,
                    message: json['message'] as String?,
                  );
                } else if (type == 'content') {
                  yield ChatStreamEvent(
                    type: ChatEventType.content,
                    content: json['content'] as String?,
                  );
                } else if (type == 'sources') {
                  final sourcesList = json['sources'] as List<dynamic>?;
                  yield ChatStreamEvent(
                    type: ChatEventType.sources,
                    sources: sourcesList
                        ?.map((s) => ChatSourceModel.fromJson(
                              s as Map<String, dynamic>,
                            ))
                        .toList(),
                  );
                } else if (type == 'error') {
                  yield ChatStreamEvent(
                    type: ChatEventType.error,
                    error: json['error'] as String?,
                  );
                } else if (type == 'done') {
                  yield ChatStreamEvent(type: ChatEventType.done);
                }
              } catch (_) {
                // Ignore parse errors
              }
            }
          }
        }
      }
    } on DioException catch (e) {
      yield ChatStreamEvent(
        type: ChatEventType.error,
        error: _getFriendlyErrorMessage(e),
      );
    } catch (e) {
      yield ChatStreamEvent(
        type: ChatEventType.error,
        error: '处理问题时发生错误，请稍后重试',
      );
    }
  }

  /// Summarize notebook content (SSE stream)
  Stream<ChatStreamEvent> summarizeStream({
    required String notebookId,
    required String format,
  }) async* {
    try {
      final response = await dio.post(
        '/research/notebooks/$notebookId/summarize',
        data: {'format': format},
        options: Options(
          responseType: ResponseType.stream,
          headers: {
            'Accept': 'text/event-stream',
            'Cache-Control': 'no-cache',
          },
        ),
      );

      final stream = response.data.stream as Stream<List<int>>;
      String buffer = '';

      await for (final chunk in stream) {
        buffer += utf8.decode(chunk);

        while (buffer.contains('\n\n')) {
          final endIndex = buffer.indexOf('\n\n');
          final eventData = buffer.substring(0, endIndex);
          buffer = buffer.substring(endIndex + 2);

          for (final line in eventData.split('\n')) {
            if (line.startsWith('data: ')) {
              final data = line.substring(6);
              if (data == '[DONE]') {
                yield ChatStreamEvent(type: ChatEventType.done);
                return;
              }
              try {
                final json = jsonDecode(data) as Map<String, dynamic>;
                final type = json['type'] as String?;

                if (type == 'thinking') {
                  yield ChatStreamEvent(
                    type: ChatEventType.thinking,
                    message: json['message'] as String?,
                  );
                } else if (type == 'content') {
                  yield ChatStreamEvent(
                    type: ChatEventType.content,
                    content: json['content'] as String?,
                  );
                } else if (type == 'sources') {
                  final sourcesList = json['sources'] as List<dynamic>?;
                  yield ChatStreamEvent(
                    type: ChatEventType.sources,
                    sources: sourcesList
                        ?.map((s) => ChatSourceModel.fromJson(
                              s as Map<String, dynamic>,
                            ))
                        .toList(),
                  );
                } else if (type == 'error') {
                  yield ChatStreamEvent(
                    type: ChatEventType.error,
                    error: json['error'] as String?,
                  );
                } else if (type == 'done') {
                  yield ChatStreamEvent(type: ChatEventType.done);
                }
              } catch (_) {
                // Ignore parse errors
              }
            }
          }
        }
      }
    } on DioException catch (e) {
      yield ChatStreamEvent(
        type: ChatEventType.error,
        error: _getFriendlyErrorMessage(e),
      );
    } catch (e) {
      yield ChatStreamEvent(
        type: ChatEventType.error,
        error: '生成摘要时发生错误，请稍后重试',
      );
    }
  }

  /// Clear chat history
  Future<void> clearChatHistory(String notebookId) async {
    await apiClient.delete<Map<String, dynamic>>(
      '/research/notebooks/$notebookId/chat',
    );
  }

  String _getFriendlyErrorMessage(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return '网络连接超时，请检查网络后重试';
      case DioExceptionType.connectionError:
        return '无法连接到服务器，请检查网络连接';
      case DioExceptionType.badResponse:
        final statusCode = e.response?.statusCode;
        if (statusCode == 401) {
          return '登录已过期，请重新登录';
        } else if (statusCode == 404) {
          return '知识库不存在';
        } else if (statusCode != null && statusCode >= 500) {
          return '服务器繁忙，请稍后重试';
        }
        return '请求失败，请稍后重试';
      default:
        return '网络请求失败，请稍后重试';
    }
  }
}
