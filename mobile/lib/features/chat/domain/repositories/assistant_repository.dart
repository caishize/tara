import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/chat_message.dart';
import '../../data/datasources/assistant_remote_datasource.dart'
    show StreamEvent, ChatJobResponse;
import '../../data/models/chat_message_model.dart';

abstract class AssistantRepository {
  Future<Either<Failure, ChatMessage>> sendMessage({
    required String message,
    String? sessionId,
  });

  Future<Either<Failure, List<ChatMessage>>> getSessionHistory({
    required String sessionId,
    int limit = 50,
  });

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
  });

  /// Returns a map of date string (YYYY-MM-DD) → summary text.
  Future<Map<String, String>> getDailySummaries({required String sessionId});

  Future<Either<Failure, List<ChatSession>>> getSessions({
    int limit = 20,
  });

  Future<Either<Failure, ChatSession>> createSession();

  Future<Either<Failure, List<QuickAction>>> getQuickActions();

  // Message Operations (与Web端一致) - 使用流式响应
  Stream<StreamEvent> streamEditMessage({
    required String sessionId,
    required String messageId,
    required String newContent,
  });

  // Suggestions API (与Web端一致)
  Future<Either<Failure, void>> dismissSuggestion(String suggestionId);
  Future<Either<Failure, Map<String, dynamic>>> actOnSuggestion(
      String suggestionId);

  // Task Assignment API (与Web端一致)
  Future<Either<Failure, TaskModel>> assignTask(
      String taskId, String assigneeId);

  // Holiday Details API (与Web端一致)
  Future<Either<Failure, Map<String, dynamic>>> getRedEnvelopes(String planId);
  Future<Either<Failure, Map<String, dynamic>>> getShoppingList(String planId);

  // Travel Plan Confirmation
  Future<Either<Failure, String>> confirmTravelPlan(
    String messageId,
    Map<String, dynamic> planData,
  );

  /// Stream voice message: upload audio, receive transcription + chat stream events
  Stream<StreamEvent> streamVoiceMessage({
    required String audioPath,
    String? sessionId,
    double? latitude,
    double? longitude,
    String? locationName,
  });

  /// Submit feedback (thumbs up/down) for a message
  Future<Either<Failure, void>> submitFeedback({
    required String messageId,
    required String feedback,
    String? reason,
  });

  /// Listen to WebSocket events as StreamEvent stream (for slow/hybrid path results)
  Stream<StreamEvent> listenWebSocketEvents();

  /// Non-streaming chat (WebSocket mode): returns job info, results arrive via WS
  Future<Either<Failure, ChatJobResponse>> sendChatMessage({
    required String message,
    String? sessionId,
    double? latitude,
    double? longitude,
    String? locationName,
  });

  /// Non-streaming regenerate (WebSocket mode)
  Future<Either<Failure, Map<String, dynamic>>> regenerateMessageWs({
    required String sessionId,
    required String messageId,
  });

  /// Cancel current generation for a session.
  Future<Either<Failure, void>> cancelGeneration({
    required String sessionId,
  });
}
