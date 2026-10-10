import 'dart:async';
import 'dart:convert';
import 'package:dio/dio.dart';
import '../../../../core/network/api_client.dart';
import '../../domain/entities/research_session.dart';
import '../models/research_session_model.dart';

/// SSE event types for research
enum ResearchEventType { candidate, progress, done, error }

/// Parsed SSE event for research
class ResearchStreamEvent {
  final ResearchEventType type;
  final ResearchCandidateModel? candidate;
  final String? message;
  final String? error;

  ResearchStreamEvent({
    required this.type,
    this.candidate,
    this.message,
    this.error,
  });
}

/// SSE event types for synthesis
enum SynthesisEventType { content, sources, done, error }

/// Parsed SSE event for synthesis
class SynthesisStreamEvent {
  final SynthesisEventType type;
  final String? content;
  final List<SynthesisSourceModel>? sources;
  final String? error;

  SynthesisStreamEvent({
    required this.type,
    this.content,
    this.sources,
    this.error,
  });
}

abstract class ResearchRemoteDataSource {
  /// Create a new research session
  Future<ResearchSessionModel> createSession({
    required String topic,
    required ResearchScenario scenario,
  });

  /// Get session details
  Future<ResearchSessionModel> getSession(String sessionId);

  /// List user's research sessions
  Future<List<ResearchSessionModel>> listSessions({int limit = 20});

  /// Delete a research session
  Future<void> deleteSession(String sessionId);

  /// Start search and stream results
  Stream<ResearchStreamEvent> searchStream(String sessionId);

  /// Update selected candidates
  Future<ResearchSessionModel> updateSelection({
    required String sessionId,
    required List<String> selectedIds,
  });

  /// Add a manual item (note or URL)
  Future<ManualItemModel> addManualItem({
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

class ResearchRemoteDataSourceImpl implements ResearchRemoteDataSource {
  final ApiClient apiClient;
  final Dio dio;

  ResearchRemoteDataSourceImpl({
    required this.apiClient,
    required this.dio,
  });

  @override
  Future<ResearchSessionModel> createSession({
    required String topic,
    required ResearchScenario scenario,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/research/sessions',
      data: {
        'topic': topic,
        'scenario': scenario.name,
      },
    );
    return ResearchSessionModel.fromJson(response);
  }

  @override
  Future<ResearchSessionModel> getSession(String sessionId) async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/research/sessions/$sessionId',
    );
    return ResearchSessionModel.fromJson(response);
  }

  @override
  Future<List<ResearchSessionModel>> listSessions({int limit = 20}) async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/research/sessions',
      queryParameters: {'limit': limit},
    );
    final sessions = response['sessions'] as List<dynamic>? ?? [];
    return sessions
        .map((s) => ResearchSessionModel.fromJson(s as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<void> deleteSession(String sessionId) async {
    await apiClient.delete<Map<String, dynamic>>(
      '/research/sessions/$sessionId',
    );
  }

  @override
  Stream<ResearchStreamEvent> searchStream(String sessionId) async* {
    try {
      final response = await dio.post(
        '/research/sessions/$sessionId/search',
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
                yield ResearchStreamEvent(type: ResearchEventType.done);
                return;
              }
              try {
                final json = jsonDecode(data) as Map<String, dynamic>;
                final type = json['type'] as String?;

                if (type == 'candidate') {
                  // Backend sends 'candidate', not 'data'
                  final candidateData = json['candidate'] as Map<String, dynamic>?;
                  if (candidateData != null) {
                    yield ResearchStreamEvent(
                      type: ResearchEventType.candidate,
                      candidate: ResearchCandidateModel.fromJson(candidateData),
                    );
                  }
                } else if (type == 'progress') {
                  yield ResearchStreamEvent(
                    type: ResearchEventType.progress,
                    message: json['message'] as String?,
                  );
                } else if (type == 'error') {
                  yield ResearchStreamEvent(
                    type: ResearchEventType.error,
                    error: json['message'] as String?,
                  );
                } else if (type == 'complete' || type == 'done') {
                  // Backend sends 'complete', handle both for compatibility
                  yield ResearchStreamEvent(type: ResearchEventType.done);
                }
              } catch (_) {
                // Ignore parse errors
              }
            }
          }
        }
      }
    } on DioException catch (e) {
      yield ResearchStreamEvent(
        type: ResearchEventType.error,
        error: _getFriendlyErrorMessage(e),
      );
    } catch (e) {
      yield ResearchStreamEvent(
        type: ResearchEventType.error,
        error: '搜索过程中发生错误,请稍后重试',
      );
    }
  }

  @override
  Future<ResearchSessionModel> updateSelection({
    required String sessionId,
    required List<String> selectedIds,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/research/sessions/$sessionId/select',
      data: {'selected_ids': selectedIds},
    );
    return ResearchSessionModel.fromJson(response);
  }

  @override
  Future<ManualItemModel> addManualItem({
    required String sessionId,
    required String type,
    required String content,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/research/sessions/$sessionId/manual',
      data: {
        'type': type,
        'content': content,
      },
    );
    return ManualItemModel.fromJson(response);
  }

  @override
  Future<void> deleteManualItem({
    required String sessionId,
    required String itemId,
  }) async {
    await apiClient.delete<Map<String, dynamic>>(
      '/research/sessions/$sessionId/manual/$itemId',
    );
  }

  @override
  Stream<SynthesisStreamEvent> synthesizeStream({
    required String sessionId,
    required SynthesisFormat format,
  }) async* {
    try {
      final response = await dio.post(
        '/research/sessions/$sessionId/synthesize',
        data: {'format': format.name},
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
                yield SynthesisStreamEvent(type: SynthesisEventType.done);
                return;
              }
              try {
                final json = jsonDecode(data) as Map<String, dynamic>;
                final type = json['type'] as String?;

                if (type == 'content') {
                  yield SynthesisStreamEvent(
                    type: SynthesisEventType.content,
                    content: json['content'] as String?,
                  );
                } else if (type == 'sources') {
                  final sourcesList = json['sources'] as List<dynamic>?;
                  yield SynthesisStreamEvent(
                    type: SynthesisEventType.sources,
                    sources: sourcesList
                        ?.map((s) => SynthesisSourceModel.fromJson(
                              s as Map<String, dynamic>,
                            ))
                        .toList(),
                  );
                } else if (type == 'error') {
                  yield SynthesisStreamEvent(
                    type: SynthesisEventType.error,
                    error: json['message'] as String?,
                  );
                } else if (type == 'done') {
                  yield SynthesisStreamEvent(type: SynthesisEventType.done);
                }
              } catch (_) {
                // Ignore parse errors
              }
            }
          }
        }
      }
    } on DioException catch (e) {
      yield SynthesisStreamEvent(
        type: SynthesisEventType.error,
        error: _getFriendlyErrorMessage(e),
      );
    } catch (e) {
      yield SynthesisStreamEvent(
        type: SynthesisEventType.error,
        error: '生成报告时发生错误,请稍后重试',
      );
    }
  }

  String _getFriendlyErrorMessage(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return '网络连接超时,请检查网络后重试';
      case DioExceptionType.connectionError:
        return '无法连接到服务器,请检查网络连接';
      case DioExceptionType.badResponse:
        final statusCode = e.response?.statusCode;
        if (statusCode == 401) {
          return '登录已过期,请重新登录';
        } else if (statusCode == 404) {
          return '研究会话不存在';
        } else if (statusCode != null && statusCode >= 500) {
          return '服务器繁忙,请稍后重试';
        }
        return '请求失败,请稍后重试';
      default:
        return '网络请求失败,请稍后重试';
    }
  }
}
