import 'package:dartz/dartz.dart';
import 'package:dio/dio.dart';
import '../../../../core/error/failures.dart';
import '../../../../core/error/exceptions.dart';
import '../../domain/entities/chat_message.dart';
import '../../domain/repositories/assistant_repository.dart';
import '../datasources/assistant_remote_datasource.dart';
import '../models/chat_message_model.dart';

class AssistantRepositoryImpl implements AssistantRepository {
  final AssistantRemoteDataSource remoteDataSource;

  AssistantRepositoryImpl({required this.remoteDataSource});

  @override
  Future<Either<Failure, ChatMessage>> sendMessage({
    required String message,
    String? sessionId,
  }) async {
    try {
      final response = await remoteDataSource.sendMessage(
        message: message,
        sessionId: sessionId,
      );

      final chatMessage = ChatMessage(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        sessionId: response.sessionId,
        role: MessageRole.assistant,
        content: response.response,
        intent: response.intent,
        data: response.data,
        quickActions: response.quickActions,
        createdAt: DateTime.now(),
      );

      return Right(chatMessage);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } on DioException catch (e) {
      return Left(_handleDioError(e));
    } catch (_) {
      return const Left(ServerFailure('发生未知错误,请稍后重试'));
    }
  }

  @override
  Future<Either<Failure, List<ChatMessage>>> getSessionHistory({
    required String sessionId,
    int limit = 50,
  }) async {
    try {
      final messages = await remoteDataSource.getSessionHistory(
        sessionId: sessionId,
        limit: limit,
      );
      return Right(messages);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } on DioException catch (e) {
      return Left(_handleDioError(e));
    } catch (_) {
      return const Left(ServerFailure('发生未知错误,请稍后重试'));
    }
  }

  @override
  Future<
      Either<
          Failure,
          ({
            List<ChatMessage> messages,
            bool hasMore,
            String? oldestId,
          })>> loadMoreHistory({
    String? sessionId,
    String? beforeId,
    int limit = 30,
  }) async {
    try {
      final result = await remoteDataSource.getSessionHistoryWithMeta(
        sessionId: sessionId,
        beforeId: beforeId,
        limit: limit,
      );
      return Right((
        messages: result.messages,
        hasMore: result.hasMore,
        oldestId: result.oldestId,
      ));
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } on DioException catch (e) {
      return Left(_handleDioError(e));
    } catch (_) {
      return const Left(ServerFailure('加载历史消息失败'));
    }
  }

  @override
  Future<Map<String, String>> getDailySummaries({
    required String sessionId,
  }) =>
      remoteDataSource.getDailySummaries(sessionId: sessionId);

  @override
  Future<Either<Failure, List<ChatSession>>> getSessions(
      {int limit = 20}) async {
    try {
      final sessions = await remoteDataSource.getSessions(limit: limit);
      return Right(sessions);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } on DioException catch (e) {
      return Left(_handleDioError(e));
    } catch (_) {
      return const Left(ServerFailure('获取会话列表失败'));
    }
  }

  @override
  Future<Either<Failure, ChatSession>> createSession() async {
    try {
      final session = await remoteDataSource.createSession();
      return Right(session);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } on DioException catch (e) {
      return Left(_handleDioError(e));
    } catch (_) {
      return const Left(ServerFailure('创建会话失败'));
    }
  }

  @override
  Future<Either<Failure, List<QuickAction>>> getQuickActions() async {
    try {
      final actions = await remoteDataSource.getQuickActions();
      return Right(actions);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } on DioException catch (e) {
      return Left(_handleDioError(e));
    } catch (_) {
      return const Left(ServerFailure('发生未知错误,请稍后重试'));
    }
  }

  /// 将 Dio 错误转换为友好的 Failure
  Failure _handleDioError(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return const NetworkFailure('网络连接超时,请检查网络后重试');
      case DioExceptionType.connectionError:
        return const NetworkFailure('无法连接到服务器,请检查网络连接');
      case DioExceptionType.badResponse:
        final statusCode = e.response?.statusCode;
        if (statusCode == 401) {
          return const AuthFailure('登录已过期,请重新登录');
        } else if (statusCode == 403) {
          return const PermissionFailure('没有权限执行此操作');
        } else if (statusCode == 404) {
          return const NotFoundFailure('请求的服务不存在');
        } else if (statusCode != null && statusCode >= 500) {
          return const ServerFailure('服务器繁忙,请稍后重试');
        }
        return const ServerFailure('请求失败,请稍后重试');
      case DioExceptionType.cancel:
        return const ServerFailure('请求已取消');
      case DioExceptionType.badCertificate:
        return const NetworkFailure('网络安全证书错误');
      case DioExceptionType.unknown:
        if (e.message?.contains('SocketException') == true ||
            e.message?.contains('Connection refused') == true) {
          return const NetworkFailure('无法连接到服务器,请检查网络连接');
        }
        return const ServerFailure('网络请求失败,请稍后重试');
    }
  }

  // Message Operations (与Web端一致) - 使用流式响应
  @override
  Stream<StreamEvent> streamEditMessage({
    required String sessionId,
    required String messageId,
    required String newContent,
  }) {
    return remoteDataSource.streamEditMessage(
      sessionId: sessionId,
      messageId: messageId,
      newContent: newContent,
    );
  }

  // Suggestions API (与Web端一致)
  @override
  Future<Either<Failure, void>> dismissSuggestion(String suggestionId) async {
    try {
      await remoteDataSource.dismissSuggestion(suggestionId);
      return const Right(null);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } on DioException catch (e) {
      return Left(_handleDioError(e));
    } catch (_) {
      return const Left(ServerFailure('关闭建议失败'));
    }
  }

  @override
  Future<Either<Failure, Map<String, dynamic>>> actOnSuggestion(
      String suggestionId) async {
    try {
      final result = await remoteDataSource.actOnSuggestion(suggestionId);
      return Right(result);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } on DioException catch (e) {
      return Left(_handleDioError(e));
    } catch (_) {
      return const Left(ServerFailure('执行建议操作失败'));
    }
  }

  // Task Assignment API (与Web端一致)
  @override
  Future<Either<Failure, TaskModel>> assignTask(
      String taskId, String assigneeId) async {
    try {
      final task = await remoteDataSource.assignTask(taskId, assigneeId);
      return Right(task);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } on DioException catch (e) {
      return Left(_handleDioError(e));
    } catch (_) {
      return const Left(ServerFailure('分配任务失败'));
    }
  }

  // Holiday Details API (与Web端一致)
  @override
  Future<Either<Failure, Map<String, dynamic>>> getRedEnvelopes(
      String planId) async {
    try {
      final result = await remoteDataSource.getRedEnvelopes(planId);
      return Right(result);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } on DioException catch (e) {
      return Left(_handleDioError(e));
    } catch (_) {
      return const Left(ServerFailure('获取红包预算失败'));
    }
  }

  @override
  Future<Either<Failure, Map<String, dynamic>>> getShoppingList(
      String planId) async {
    try {
      final result = await remoteDataSource.getShoppingList(planId);
      return Right(result);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } on DioException catch (e) {
      return Left(_handleDioError(e));
    } catch (_) {
      return const Left(ServerFailure('获取购物清单失败'));
    }
  }

  @override
  Stream<StreamEvent> streamVoiceMessage({
    required String audioPath,
    String? sessionId,
    double? latitude,
    double? longitude,
    String? locationName,
  }) {
    return remoteDataSource.streamVoiceMessage(
      audioPath: audioPath,
      sessionId: sessionId,
      latitude: latitude,
      longitude: longitude,
      locationName: locationName,
    );
  }

  @override
  Stream<StreamEvent> listenWebSocketEvents() {
    return remoteDataSource.listenWebSocketEvents();
  }

  @override
  Future<Either<Failure, void>> submitFeedback({
    required String messageId,
    required String feedback,
    String? reason,
  }) async {
    try {
      await remoteDataSource.submitFeedback(
        messageId: messageId,
        feedback: feedback,
        reason: reason,
      );
      return const Right(null);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } on DioException catch (e) {
      return Left(_handleDioError(e));
    } catch (_) {
      return const Left(ServerFailure('提交反馈失败'));
    }
  }

  @override
  Future<Either<Failure, String>> confirmTravelPlan(
    String messageId,
    Map<String, dynamic> planData,
  ) async {
    try {
      final planId = await remoteDataSource.confirmTravelPlan(
        messageId,
        planData,
      );
      return Right(planId);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } on DioException catch (e) {
      return Left(_handleDioError(e));
    } catch (_) {
      return const Left(ServerFailure('确认旅行计划失败'));
    }
  }

  @override
  Future<Either<Failure, ChatJobResponse>> sendChatMessage({
    required String message,
    String? sessionId,
    double? latitude,
    double? longitude,
    String? locationName,
  }) async {
    try {
      final response = await remoteDataSource.sendChatMessage(
        message: message,
        sessionId: sessionId,
        latitude: latitude,
        longitude: longitude,
        locationName: locationName,
      );
      return Right(response);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } on DioException catch (e) {
      return Left(_handleDioError(e));
    } catch (_) {
      return const Left(ServerFailure('发送消息失败'));
    }
  }

  @override
  Future<Either<Failure, Map<String, dynamic>>> regenerateMessageWs({
    required String sessionId,
    required String messageId,
  }) async {
    try {
      final result = await remoteDataSource.regenerateMessageWs(
        sessionId: sessionId,
        messageId: messageId,
      );
      return Right(result);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } on DioException catch (e) {
      return Left(_handleDioError(e));
    } catch (_) {
      return const Left(ServerFailure('重新生成失败'));
    }
  }

  @override
  Future<Either<Failure, void>> cancelGeneration({
    required String sessionId,
  }) async {
    try {
      await remoteDataSource.cancelGeneration(sessionId: sessionId);
      return const Right(null);
    } on AppException catch (e) {
      return Left(ServerFailure(e.message));
    } on DioException catch (e) {
      return Left(_handleDioError(e));
    } catch (_) {
      return const Left(ServerFailure('停止生成失败'));
    }
  }
}
