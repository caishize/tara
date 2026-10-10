import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart' show debugPrint;
import 'package:dio/dio.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/network/websocket_service.dart';
import '../models/chat_message_model.dart';

/// Stream event types from backend
enum StreamEventType {
  session,
  thinkingStart,
  thinking,
  thinkingEnd,
  content,
  progress,
  memoryRecall, // 记忆召回事件
  tripPlan, // 行程规划事件
  intentUnderstood, // 意图理解事件
  toolExecution, // 工具执行事件
  toolStart, // 工具执行开始
  toolResult, // 工具执行结果
  toolProgress, // 工具执行进度更新
  agenticIteration, // AGENTIC: LLM反思迭代事件
  confirmCard, // SECURITY: 敏感操作确认卡片
  askUserQuestion, // Agent向用户提问，等待回答
  transcription, // 语音转写结果 {text, confidence, language}
  route, // 双脑路由决策 {route_type: "fast"|"slow"|"hybrid"}
  queued, // Slow path 任务已入队 {job_id: "xxx"}
  backgroundJob, // Hybrid 后台任务 {job_id: "xxx"}
  partialContent, // Full-duplex: 部分内容（可能被替换）
  bridging, // Full-duplex: 纠正/岔开信号过渡
  generationState, // Full-duplex: 生成状态变化（interrupt/resume/cancel）
  sidekickInsight, // Full-duplex: Sidekick 背景洞察卡片
  voiceTranscription, // Voice streaming: partial/final transcription
  voiceError, // Voice streaming: error message
  voiceChatStarted, // Voice streaming: chat job dispatched with job_id
  memoryExtracted, // System intelligence: memory extraction notification
  done,
  error
}

/// Response from non-streaming POST /chat (WebSocket mode)
class ChatJobResponse {
  final String jobId;
  final String sessionId;
  final String routeType;
  /// Non-null when status is "signal_accepted" (full-duplex intervention)
  final String? signalId;
  final String? signalType;
  final bool isSignalAccepted;

  ChatJobResponse({
    required this.jobId,
    required this.sessionId,
    required this.routeType,
    this.signalId,
    this.signalType,
    this.isSignalAccepted = false,
  });

  factory ChatJobResponse.fromJson(Map<String, dynamic> json) {
    final status = json['status'] as String?;
    final isSignal = status == 'signal_accepted';
    return ChatJobResponse(
      jobId: json['job_id'] as String? ?? '',
      sessionId: json['session_id'] as String? ?? '',
      routeType: json['route_type'] as String? ?? '',
      signalId: json['signal_id'] as String?,
      signalType: json['signal_type'] as String?,
      isSignalAccepted: isSignal,
    );
  }
}

/// Parsed stream event
class StreamEvent {
  final StreamEventType type;
  final String? content;
  final String? sessionId;
  final String? messageId;
  final String? stage;
  final String? message;
  final String? intent;
  final Map<String, dynamic>? data;
  final List<QuickActionModel>? quickActions;
  final List<Map<String, dynamic>>? progressHistory; // 进度历史
  final String? toolName; // 工具名称
  final String? toolStatus; // 工具执行状态
  final Map<String, dynamic>? toolResult; // 工具执行结果
  final List<Map<String, dynamic>>? toolExecutions; // 工具执行列表（done事件）
  final String? toolExecutionId; // 🔴 CONTEXT ENGINEERING: 执行ID，用于按需查看详情
  final String? toolSummary; // 🔴 CONTEXT ENGINEERING: 工具执行摘要
  final Map<String, dynamic>? toolKeyResults; // 🔴 NEW: 工具执行关键结果
  final int? toolDurationMs; // 🔴 NEW: 工具执行时长(毫秒)
  final Map<String, dynamic>? toolArguments; // 🔴 NEW: 工具调用参数
  final int? agenticIteration; // 🔴 AGENTIC: 当前反思迭代轮次
  final int? agenticMaxIterations; // 🔴 AGENTIC: 最大迭代轮次
  final int? agenticIterations; // 🔴 AGENTIC: 总共经过的迭代轮次（done事件）
  final Map<String, dynamic>? confirmCardPayload; // SECURITY: 确认卡片数据
  final Map<String, dynamic>? askUserQuestionPayload; // Agent提问数据
  final String? routeType; // 双脑路由类型: fast, slow, hybrid
  final String? jobId; // Slow/Hybrid path 任务ID
  final String?
      asyncSource; // Async push origin: "briefing" | "discovery" | "reminder"
  final String? cardType; // Explicit card type from backend normalizer
  final String?
      fullThinking; // Complete thinking from done event (reconciliation)
  final int? seq; // Sequence number within a job for ordering/resume
  final String? bridgingType; // Full-duplex: "correction" | "digression"
  final String? generationId; // Full-duplex: generation ID for partial content tracking
  final String? generationStateAction; // Full-duplex: "interrupt" | "resume" | "cancel"
  final String? interruptedBy; // Full-duplex: who triggered the interruption

  StreamEvent({
    required this.type,
    this.content,
    this.sessionId,
    this.messageId,
    this.stage,
    this.message,
    this.intent,
    this.data,
    this.quickActions,
    this.progressHistory,
    this.toolName,
    this.toolStatus,
    this.toolResult,
    this.toolExecutions,
    this.toolExecutionId,
    this.toolSummary,
    this.toolKeyResults,
    this.toolDurationMs,
    this.toolArguments,
    this.agenticIteration,
    this.agenticMaxIterations,
    this.agenticIterations,
    this.confirmCardPayload,
    this.askUserQuestionPayload,
    this.routeType,
    this.jobId,
    this.asyncSource,
    this.cardType,
    this.fullThinking,
    this.seq,
    this.bridgingType,
    this.generationId,
    this.generationStateAction,
    this.interruptedBy,
  });

  factory StreamEvent.fromJson(Map<String, dynamic> json) {
    final typeStr = json['type'] as String?;
    final type = _parseEventType(typeStr);
    final dataRaw = json['data'];
    final contentRaw = json['content'] as String?;
    final contentFromData = dataRaw is String ? dataRaw : null;
    final thinkingRaw = json['thinking'] as String?;
    final contentFromText = json['text'] as String?;
    final contentFromPartialText = json['partial_text'] as String?;
    String? contentFromPayload;
    final payload = json['payload'];
    if (payload is Map<String, dynamic>) {
      contentFromPayload =
          payload['content'] as String? ?? payload['text'] as String?;
    }

    // For "done" events, thinking is reconciliation data (not content).
    // For "thinking" events, thinking IS the content.
    final isDoneEvent = type == StreamEventType.done;
    final contentFromThinking = isDoneEvent ? null : thinkingRaw;

    return StreamEvent(
      type: type,
      // Some backends send final content in "data" as a string (done event).
      // Prefer explicit "content", but fall back to string "data" if present.
      content: contentRaw ??
          contentFromPartialText ??
          contentFromData ??
          contentFromThinking ??
          contentFromText ??
          contentFromPayload,
      fullThinking: isDoneEvent ? thinkingRaw : null,
      sessionId: json['session_id'] as String?,
      messageId: json['message_id'] as String?,
      stage: json['stage'] as String?,
      message: json['message'] as String?,
      intent: json['intent'] is String
          ? json['intent'] as String
          : (json['intent'] != null ? jsonEncode(json['intent']) : null),
      data: dataRaw is Map<String, dynamic> ? dataRaw : null,
      quickActions: (json['quick_actions'] as List<dynamic>?)
          ?.map((a) => QuickActionModel.fromJson(a as Map<String, dynamic>))
          .toList(),
      // Parse progress history from done event
      progressHistory: (json['progress_history'] as List<dynamic>?)
          ?.map((p) => p as Map<String, dynamic>)
          .toList(),
      // Parse tool execution data (for individual tool_execution events)
      toolName: json['tool_name'] as String? ?? json['tool'] as String?,
      toolStatus: json['status'] as String?,
      toolResult: json['result'] is Map<String, dynamic>
          ? json['result'] as Map<String, dynamic>
          : null,
      // 🔴 CONTEXT ENGINEERING: Execution ID for on-demand detail retrieval
      toolExecutionId: json['execution_id'] as String?,
      toolSummary: json['summary'] as String?,
      // 🔴 NEW: Key results and duration for expandable display
      toolKeyResults: _parseKeyResults(json['key_results']),
      toolDurationMs: _parseDurationMs(json['duration_ms']),
      // 🔴 NEW: Tool arguments for detailed display
      toolArguments: json['arguments'] is Map<String, dynamic>
          ? json['arguments'] as Map<String, dynamic>
          : null,
      // Parse tool executions list from done event
      toolExecutions: (json['tool_executions'] as List<dynamic>?)
          ?.map((t) => t as Map<String, dynamic>)
          .toList(),
      // 🔴 AGENTIC: Parse agentic iteration data
      agenticIteration: json['iteration'] as int?,
      agenticMaxIterations: json['max_iterations'] as int?,
      agenticIterations: json['agentic_iterations'] as int?,
      // SECURITY: Parse confirm card payload
      confirmCardPayload: type == StreamEventType.confirmCard ? json : null,
      // AskUserQuestion: Parse question payload
      askUserQuestionPayload:
          type == StreamEventType.askUserQuestion ? json : null,
      // Bi-modal routing fields
      routeType: json['route_type'] as String? ?? json['path'] as String?,
      jobId: json['job_id'] as String?,
      // Async push origin
      asyncSource: json['async_source'] as String?,
      // Card type from backend normalizer
      cardType: json['card_type'] as String?,
      // Sequence number for ordering/resume
      seq: json['seq'] as int?,
      // Full-duplex fields
      bridgingType: json['signal_type'] as String? ?? json['bridging_type'] as String?,
      generationId: json['generation_id'] as String? ?? json['new_generation_id'] as String?,
      generationStateAction: json['action'] as String?,
      interruptedBy: json['interrupted_by'] as String?,
    );
  }

  static Map<String, dynamic>? _parseKeyResults(dynamic value) {
    if (value == null) return null;
    if (value is Map<String, dynamic>) return value;
    if (value is Map) {
      return value.map((k, v) => MapEntry(k.toString(), v));
    }
    return null;
  }

  static int? _parseDurationMs(dynamic value) {
    if (value == null) return null;
    if (value is int) return value;
    if (value is double) return value.toInt();
    if (value is String) {
      return int.tryParse(value);
    }
    return null;
  }

  static StreamEventType _parseEventType(String? type) {
    switch (type) {
      case 'session':
        return StreamEventType.session;
      case 'thinking_start':
        return StreamEventType.thinkingStart;
      case 'thinking':
        return StreamEventType.thinking;
      case 'thinking_end':
        return StreamEventType.thinkingEnd;
      case 'transcription':
        return StreamEventType.transcription;
      case 'route':
        return StreamEventType.route;
      case 'queued':
        return StreamEventType.queued;
      case 'background_job':
      case 'hybrid_background':
        return StreamEventType.backgroundJob;
      case 'content':
        return StreamEventType.content;
      case 'progress':
        return StreamEventType.progress;
      case 'memory_recall':
        return StreamEventType.memoryRecall;
      case 'trip_plan':
        return StreamEventType.tripPlan;
      case 'intent_understood':
        return StreamEventType.intentUnderstood;
      case 'tool_execution':
      case 'tool_call':
        return StreamEventType.toolExecution;
      case 'tool_start':
        return StreamEventType.toolStart;
      case 'tool_result':
        return StreamEventType.toolResult;
      case 'tool_progress': // 🔴 NEW: Handle tool progress events
        return StreamEventType.toolProgress;
      case 'agentic_iteration':
        return StreamEventType.agenticIteration;
      case 'confirm_card': // 🔴 SECURITY
      case 'confirmCard':
        return StreamEventType.confirmCard;
      case 'ask_user_question':
      case 'askUserQuestion':
        return StreamEventType.askUserQuestion;
      case 'partial_content':
        return StreamEventType.partialContent;
      case 'bridging':
        return StreamEventType.bridging;
      case 'generation_state':
        return StreamEventType.generationState;
      case 'sidekick_insight':
        return StreamEventType.sidekickInsight;
      case 'voice_transcription':
        return StreamEventType.voiceTranscription;
      case 'voice_error':
        return StreamEventType.voiceError;
      case 'voice_chat_started':
        return StreamEventType.voiceChatStarted;
      case 'memory_extracted':
        return StreamEventType.memoryExtracted;
      case 'done':
      case 'complete': // Map V2 complete to done
        return StreamEventType.done;
      case 'error':
        return StreamEventType.error;
      default:
        return StreamEventType.content;
    }
  }
}

abstract class AssistantRemoteDataSource {
  Future<ChatResponseModel> sendMessage({
    required String message,
    String? sessionId,
  });

  Future<List<ChatMessageModel>> getSessionHistory({
    required String sessionId,
    String? beforeId,
    int limit = 50,
  });

  Future<({List<ChatMessageModel> messages, bool hasMore, String? oldestId})>
      getSessionHistoryWithMeta({
    String? sessionId,
    String? beforeId,
    int limit = 30,
  });

  Future<List<QuickActionModel>> getQuickActions();

  Future<List<ChatSessionModel>> getSessions({int limit = 20});

  Future<ChatSessionModel> createSession();

  // Today View API
  Future<TodayViewModel> getTodayView();
  Future<void> completeTodayItem(String itemId);
  Future<void> snoozeTodayItem(String itemId, {int hours = 24});
  Future<void> dismissTodayItem(String itemId);

  // Tasks API
  Future<List<TaskModel>> getTasks({String? status, int? limit});
  Future<MyTasksModel> getMyTasks({bool includeCreated = false});
  Future<TaskModel> createTask(TaskModel task);
  Future<void> completeTask(String taskId);
  Future<void> deleteTask(String taskId);
  Future<TaskStatsModel> getTaskStatistics();

  // Holiday API
  Future<List<HolidayPlanModel>> getHolidays({int days = 60});
  Future<HolidayPlanModel> generateHolidayPlan(String holidayType,
      {int? year, String? region});
  Future<void> adoptHolidayPlan(String planId);
  Future<Map<String, dynamic>> getRedEnvelopes(String planId);
  Future<Map<String, dynamic>> getShoppingList(String planId);

  // Message Operations API
  Stream<StreamEvent> streamEditMessage({
    required String sessionId,
    required String messageId,
    required String newContent,
  });

  // Suggestions API
  Future<void> dismissSuggestion(String suggestionId);
  Future<Map<String, dynamic>> actOnSuggestion(String suggestionId);

  // Task Assignment API
  Future<TaskModel> assignTask(String taskId, String assigneeId);

  // Travel Plan Confirmation
  Future<String> confirmTravelPlan(
    String messageId,
    Map<String, dynamic> planData,
  );

  // Pending Action API
  Future<Map<String, dynamic>> confirmAction(String actionId);
  Future<Map<String, dynamic>> rejectAction(String actionId);

  /// Stream voice message: upload audio, receive transcription + chat stream events
  Stream<StreamEvent> streamVoiceMessage({
    required String audioPath,
    String? sessionId,
    double? latitude,
    double? longitude,
    String? locationName,
  });

  /// Submit feedback (thumbs up/down) for a message
  Future<void> submitFeedback({
    required String messageId,
    required String feedback,
    String? reason,
  });

  /// Listen to WebSocket events as StreamEvent stream (for slow/hybrid path results)
  Stream<StreamEvent> listenWebSocketEvents();

  /// Non-streaming chat (WebSocket mode): returns job info, results arrive via WS
  Future<ChatJobResponse> sendChatMessage({
    required String message,
    String? sessionId,
    double? latitude,
    double? longitude,
    String? locationName,
  });

  /// Non-streaming regenerate (WebSocket mode)
  Future<Map<String, dynamic>> regenerateMessageWs({
    required String sessionId,
    required String messageId,
  });

  /// Cancel current generation for a session.
  Future<void> cancelGeneration({
    required String sessionId,
  });

  /// Fetch daily summaries for a session.
  /// Returns a map of date string (YYYY-MM-DD) → summary text.
  Future<Map<String, String>> getDailySummaries({required String sessionId});
}

class AssistantRemoteDataSourceImpl implements AssistantRemoteDataSource {
  final ApiClient apiClient;
  final Dio dio;
  final WebSocketService webSocketService;

  AssistantRemoteDataSourceImpl({
    required this.apiClient,
    required this.dio,
    required this.webSocketService,
  });

  @override
  Future<ChatResponseModel> sendMessage({
    required String message,
    String? sessionId,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/chat',
      data: {
        'message': message,
        if (sessionId != null) 'session_id': sessionId,
      },
    );
    return ChatResponseModel.fromJson(response);
  }

  @override
  Future<List<ChatMessageModel>> getSessionHistory({
    required String sessionId,
    String? beforeId,
    int limit = 50,
  }) async {
    final params = <String, dynamic>{
      'session_id': sessionId,
      'limit': limit,
    };
    if (beforeId != null) params['before_id'] = beforeId;
    final response = await apiClient.get<Map<String, dynamic>>(
      '/chat/history',
      queryParameters: params,
    );
    final messages = response['items'] as List<dynamic>? ?? [];
    return messages
        .map((m) => ChatMessageModel.fromJson(m as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<({List<ChatMessageModel> messages, bool hasMore, String? oldestId})>
      getSessionHistoryWithMeta({
    String? sessionId,
    String? beforeId,
    int limit = 30,
  }) async {
    final params = <String, dynamic>{
      'limit': limit,
    };
    if (sessionId != null && sessionId.isNotEmpty) {
      params['session_id'] = sessionId;
    }
    if (beforeId != null) params['before_id'] = beforeId;

    final response = await apiClient.get<Map<String, dynamic>>(
      '/chat/history',
      queryParameters: params,
    );
    final items = response['items'] as List<dynamic>? ?? [];
    final hasMore = response['has_more'] as bool? ?? false;
    final messages = items
        .where((m) => m is Map<String, dynamic> && m['type'] != 'session_divider')
        .map((m) => ChatMessageModel.fromJson(m as Map<String, dynamic>))
        .toList();
    final oldestId = messages.isNotEmpty ? messages.first.id : null;
    return (messages: messages, hasMore: hasMore, oldestId: oldestId);
  }

  @override
  Future<List<QuickActionModel>> getQuickActions() async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/chat/quick-actions',
    );
    final actions = response['actions'] as List<dynamic>? ?? [];
    return actions.map((a) => QuickActionModel.fromJson(a)).toList();
  }

  @override
  Future<List<ChatSessionModel>> getSessions({int limit = 20}) async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/chat/sessions',
      queryParameters: {'limit': limit, 'status': 'active'},
    );
    final sessions = response['sessions'] as List<dynamic>? ?? [];
    return sessions
        .map((s) => ChatSessionModel.fromJson(s as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<ChatSessionModel> createSession() async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/chat/new',
    );
    return ChatSessionModel(
      id: response['session_id'] ?? '',
      createdAt: DateTime.now(),
    );
  }

  // Today View API
  @override
  Future<TodayViewModel> getTodayView() async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/briefing/today',
    );
    return TodayViewModel.fromJson(response);
  }

  @override
  Future<void> completeTodayItem(String itemId) async {
    await apiClient.post<Map<String, dynamic>>(
      '/briefing/today/$itemId/complete',
    );
  }

  @override
  Future<void> snoozeTodayItem(String itemId, {int hours = 24}) async {
    await apiClient.post<Map<String, dynamic>>(
      '/briefing/today/$itemId/snooze',
      queryParameters: {'hours': hours},
    );
  }

  @override
  Future<void> dismissTodayItem(String itemId) async {
    await apiClient.post<Map<String, dynamic>>(
      '/briefing/today/$itemId/dismiss',
    );
  }

  // Tasks API
  @override
  Future<List<TaskModel>> getTasks({String? status, int? limit}) async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/kanban/tasks',
      queryParameters: {
        if (status != null) 'status': status,
        if (limit != null) 'limit': limit,
      },
    );
    final tasks = response['tasks'] as List<dynamic>? ?? [];
    return tasks
        .map((t) => TaskModel.fromJson(t as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<MyTasksModel> getMyTasks({bool includeCreated = false}) async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/kanban/tasks/my',
      queryParameters: {'include_created': includeCreated},
    );
    return MyTasksModel.fromJson(response);
  }

  @override
  Future<TaskModel> createTask(TaskModel task) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/kanban/tasks',
      data: task.toJson(),
    );
    return TaskModel.fromJson(response);
  }

  @override
  Future<void> completeTask(String taskId) async {
    await apiClient.post<Map<String, dynamic>>(
      '/kanban/tasks/$taskId/complete',
    );
  }

  @override
  Future<void> deleteTask(String taskId) async {
    await apiClient.delete<Map<String, dynamic>>(
      '/kanban/tasks/$taskId',
    );
  }

  @override
  Future<TaskStatsModel> getTaskStatistics() async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/kanban/tasks/statistics',
    );
    return TaskStatsModel.fromJson(response);
  }

  // Holiday API
  @override
  Future<List<HolidayPlanModel>> getHolidays({int days = 60}) async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/dates/holidays',
      queryParameters: {'days': days},
    );
    final plans = response['plans'] as List<dynamic>? ?? [];
    return plans
        .map((p) => HolidayPlanModel.fromJson(p as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<HolidayPlanModel> generateHolidayPlan(String holidayType,
      {int? year, String? region}) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/dates/holidays/$holidayType/plan',
      queryParameters: {
        if (year != null) 'year': year,
        if (region != null) 'region': region,
      },
    );
    return HolidayPlanModel.fromJson(response);
  }

  @override
  Future<void> adoptHolidayPlan(String planId) async {
    await apiClient.post<Map<String, dynamic>>(
      '/dates/holidays/$planId/adopt',
    );
  }

  @override
  Future<Map<String, dynamic>> getRedEnvelopes(String planId) async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/dates/holidays/$planId/red-envelopes',
    );
    return response;
  }

  @override
  Future<Map<String, dynamic>> getShoppingList(String planId) async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/dates/holidays/$planId/shopping',
    );
    return response;
  }

  // Message Operations API
  @override
  Stream<StreamEvent> streamEditMessage({
    required String sessionId,
    required String messageId,
    required String newContent,
  }) async* {
    try {
      final response = await apiClient.post<Map<String, dynamic>>(
        '/chat/edit',
        data: {
          'session_id': sessionId,
          'message_id': messageId,
          'new_content': newContent,
        },
      );

      yield* _emitWsBootstrapEvents(response);
    } on DioException catch (e) {
      yield StreamEvent(
        type: StreamEventType.error,
        message: _extractErrorMessage(e, fallback: '编辑失败，请稍后重试'),
      );
    } catch (_) {
      yield StreamEvent(
        type: StreamEventType.error,
        message: '编辑失败，请稍后重试',
      );
    }
  }

  @override
  Stream<StreamEvent> streamVoiceMessage({
    required String audioPath,
    String? sessionId,
    double? latitude,
    double? longitude,
    String? locationName,
  }) async* {
    try {
      final formData = FormData.fromMap({
        'audio': await MultipartFile.fromFile(audioPath),
        if (sessionId != null) 'session_id': sessionId,
        if (latitude != null) 'latitude': latitude,
        if (longitude != null) 'longitude': longitude,
        if (locationName != null) 'location_name': locationName,
      });

      final response = await dio.post<Map<String, dynamic>>(
        '/chat/voice',
        data: formData,
      );

      final transcription =
          response.data?['transcription'] as Map<String, dynamic>? ?? {};
      final text = (transcription['text'] as String? ?? '').trim();
      if (text.isNotEmpty) {
        yield StreamEvent(
          type: StreamEventType.transcription,
          content: text,
          data: transcription,
        );
      }

      yield* _emitWsBootstrapEvents(response.data ?? const {});
    } on DioException catch (e) {
      yield StreamEvent(
        type: StreamEventType.error,
        message: _extractErrorMessage(e, fallback: '语音消息发送失败，请稍后重试'),
      );
    } catch (_) {
      yield StreamEvent(
        type: StreamEventType.error,
        message: '语音消息发送失败，请稍后重试',
      );
    }
  }

  Stream<StreamEvent> _emitWsBootstrapEvents(
    Map<String, dynamic> response,
  ) async* {
    final sessionId = response['session_id'] as String?;
    final routeType = response['route_type'] as String?;
    final jobId = response['job_id'] as String?;

    if (sessionId != null && sessionId.isNotEmpty) {
      yield StreamEvent(
        type: StreamEventType.session,
        sessionId: sessionId,
      );
    }

    if (routeType != null && routeType.isNotEmpty) {
      yield StreamEvent(
        type: StreamEventType.route,
        routeType: routeType,
        jobId: jobId,
      );
    }

    if (jobId != null && jobId.isNotEmpty) {
      if (routeType == 'slow') {
        yield StreamEvent(
          type: StreamEventType.queued,
          jobId: jobId,
          routeType: routeType,
        );
      } else {
        yield StreamEvent(
          type: StreamEventType.backgroundJob,
          jobId: jobId,
          routeType: routeType,
        );
      }
    }
  }

  String _extractErrorMessage(
    DioException e, {
    required String fallback,
  }) {
    final data = e.response?.data;
    if (data is Map<String, dynamic>) {
      final detail = data['detail'];
      if (detail is String && detail.trim().isNotEmpty) {
        return detail;
      }
    } else if (data is String && data.trim().isNotEmpty) {
      return data;
    }
    return fallback;
  }

  // Suggestions API
  @override
  Future<void> dismissSuggestion(String suggestionId) async {
    await apiClient.post<Map<String, dynamic>>(
      '/briefing/suggestions/$suggestionId/dismiss',
    );
  }

  @override
  Future<Map<String, dynamic>> actOnSuggestion(String suggestionId) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/briefing/suggestions/$suggestionId/action',
    );
    return response;
  }

  // Task Assignment API
  @override
  Future<TaskModel> assignTask(String taskId, String assigneeId) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/kanban/tasks/$taskId/assign',
      data: {'assignee_id': assigneeId},
    );
    return TaskModel.fromJson(response);
  }

  // WebSocket event stream for slow/hybrid path results
  @override
  Stream<StreamEvent> listenWebSocketEvents() async* {
    await for (final rawMessage in webSocketService.messages) {
      // C-4: Skip binary frames (voice audio echoes) — only process text JSON
      if (rawMessage is! String) continue;
      try {
        final json = jsonDecode(rawMessage) as Map<String, dynamic>;

        // Skip non-PubSub messages (e.g. keepalive pings, server lifecycle, resume acks)
        final rawType = json['type'] as String?;

        // Voice streaming transcriptions are direct WS text messages (not PubSub).
        // Backend sends {type, text, partial, is_final, cancelled} at top level.
        // StreamEvent.fromJson expects nested 'data' Map for extra fields, so wrap them.
        if (rawType == 'voice_transcription' || rawType == 'voice_error') {
          yield StreamEvent.fromJson({
            'type': rawType,
            'text': json['text'] as String? ?? '',
            'message': json['message'] as String? ?? json['text'] as String? ?? '',
            'data': <String, dynamic>{
              'partial': json['partial'] ?? false,
              'is_final': json['is_final'] ?? false,
              'cancelled': json['cancelled'] ?? false,
            },
          });
          continue;
        }

        // Voice chat job started: backend dispatched a chat job for the
        // voice transcription.  Carries job_id, session_id, route_type so the
        // mobile can correlate subsequent AI response events.
        if (rawType == 'voice_chat_started') {
          yield StreamEvent.fromJson({
            'type': rawType,
            'job_id': json['job_id'] as String? ?? '',
            'session_id': json['session_id'] as String?,
            'route_type': json['route_type'] as String?,
          });
          continue;
        }

        if (rawType == 'keepalive' ||
            rawType == 'server_shutdown' ||
            rawType == 'resume_complete' ||
            rawType == 'resume_error' ||
            rawType == 'pong') {
          if (rawType == 'resume_complete' || rawType == 'resume_error') {
            debugPrint(
              '[WS EVENT] control type=$rawType job=${json['job_id']} recovered=${json['recovered_count']} message=${json['message']}',
            );
          }
          if (rawType == 'server_shutdown') {
            debugPrint(
                'WebSocket: received server_shutdown, reconnection will handle');
          }
          continue;
        }
        if (json['message_type'] == null) {
          debugPrint('[WS EVENT] dropped non-pubsub type=$rawType');
          continue;
        }

        // WebSocket messages from PubSub have {message_type, payload, trace_id, ...}
        // Map to StreamEvent format
        final messageType = json['message_type'] as String?;
        final payload = json['payload'] as Map<String, dynamic>? ?? {};
        final traceId = json['trace_id'] as String?;

        // Build a StreamEvent-compatible JSON from the PubSub message
        // For thinking messages, map phase to the correct event type
        String mappedType = _mapPubSubTypeToEventType(messageType);
        if (messageType == 'thinking') {
          final phase = payload['phase'] as String?;
          switch (phase) {
            case 'start':
              mappedType = 'thinking_start';
              break;
            case 'end':
              mappedType = 'thinking_end';
              break;
            default:
              mappedType = 'thinking';
              break;
          }
        }

        // Normalize payload to ensure thinking/content text is readable
        final normalizedPayload = Map<String, dynamic>.from(payload);
        if ((messageType == 'thinking' || messageType == 'content') &&
            normalizedPayload['content'] == null &&
            normalizedPayload['text'] is String) {
          normalizedPayload['content'] = normalizedPayload['text'];
        }

        // Route tool_execution progress events to tool_progress so the
        // BLoC renders real-time progress logs in the tool card.
        if (messageType == 'tool_execution') {
          final status = payload['status'] as String?;
          if (status == 'progress') {
            mappedType = 'tool_progress';
          }
        }

        // Preserve envelope-level job correlation fields.
        // Some payloads (notably hybrid fast-leg done) also carry `job_id`
        // for background tasks; that must not override the PubSub envelope
        // job id used by active-job filtering in the BLoC.
        final payloadJobId = normalizedPayload['job_id'] as String?;
        final eventJobId = mappedType == 'background_job' &&
                payloadJobId != null &&
                payloadJobId.isNotEmpty
            ? payloadJobId
            : (json['job_id'] as String? ?? traceId);
        final eventJson = <String, dynamic>{
          ...normalizedPayload,
          'type': mappedType,
          'job_id': eventJobId,
          'seq': json['seq'] as int?,
          'session_id': normalizedPayload['session_id'] as String?,
        };
        final shouldTrace = mappedType == 'done' ||
            mappedType == 'error' ||
            mappedType == 'background_job' ||
            mappedType == 'confirm_card' ||
            mappedType == 'ask_user_question' ||
            mappedType == 'generation_state' ||
            mappedType == 'bridging' ||
            mappedType == 'partial_content' ||
            (mappedType == 'content' &&
                (eventJson['seq'] == 1 ||
                    eventJson['seq'] == 2 ||
                    eventJson['seq'] == 3));
        if (shouldTrace) {
          final content = eventJson['content'];
          final contentLen = content is String ? content.length : 0;
          debugPrint(
            '[WS EVENT] mapped=$mappedType envelopeType=$messageType job=$eventJobId '
            'trace=$traceId seq=${eventJson['seq']} payloadJob=$payloadJobId contentLen=$contentLen',
          );
        }

        yield StreamEvent.fromJson(eventJson);
      } catch (e, stackTrace) {
        debugPrint(
            'WebSocket event parse error: $e raw=$rawMessage\n$stackTrace');
        // Terminal events must never be silently dropped — yield minimal
        // fallback so the BLoC can still transition out of streaming state.
        try {
          final fallbackJson =
              jsonDecode(rawMessage) as Map<String, dynamic>;
          final fbType =
              _mapPubSubTypeToEventType(fallbackJson['message_type'] as String?);
          if (fbType == 'done' || fbType == 'error') {
            final fbJobId = fallbackJson['job_id'] as String? ??
                fallbackJson['trace_id'] as String?;
            yield StreamEvent(
              type: fbType == 'done'
                  ? StreamEventType.done
                  : StreamEventType.error,
              jobId: fbJobId,
            );
          }
        } catch (_) {
          // Cannot even re-parse — nothing more we can do
        }
      }
    }
  }

  /// Map PubSub message_type to app stream event type string
  String _mapPubSubTypeToEventType(String? messageType) {
    switch (messageType) {
      case 'content':
        return 'content';
      case 'progress':
        return 'progress';
      case 'confirm_card':
        return 'confirm_card';
      case 'error':
        return 'error';
      case 'complete':
        return 'done';
      case 'background_job':
        return 'background_job';
      case 'tool_execution':
        return 'tool_execution';
      case 'thinking':
        return 'thinking';
      case 'ask_user_question':
        return 'ask_user_question';
      case 'partial_content':
        return 'partial_content';
      case 'bridging':
        return 'bridging';
      case 'generation_state':
        return 'generation_state';
      case 'sidekick_insight':
        return 'sidekick_insight';
      case 'memory_extracted':
        return 'memory_extracted';
      case 'voice_transcription':
        return 'voice_transcription';
      // V-M-10: Handle voice_chat_started via PubSub fallback path
      case 'voice_chat_started':
        return 'voice_chat_started';
      default:
        debugPrint('Unknown PubSub message type: $messageType');
        return 'error';
    }
  }

  @override
  Future<void> submitFeedback({
    required String messageId,
    required String feedback,
    String? reason,
  }) async {
    await apiClient.post<Map<String, dynamic>>(
      '/chat/feedback',
      data: {
        'message_id': messageId,
        'feedback': feedback,
        if (reason != null) 'reason': reason,
      },
    );
  }

  // Pending Action API
  @override
  Future<Map<String, dynamic>> confirmAction(String actionId) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/actions/$actionId/confirm',
    );
    return response;
  }

  @override
  Future<Map<String, dynamic>> rejectAction(String actionId) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/actions/$actionId/reject',
    );
    return response;
  }

  // Travel Plan Confirmation
  @override
  Future<String> confirmTravelPlan(
    String messageId,
    Map<String, dynamic> planData,
  ) async {
    final rawDestination = (planData['destination'] as String?)?.trim() ?? '';
    final destination = rawDestination.isEmpty ? '未知目的地' : rawDestination;
    final response = await apiClient.post<Map<String, dynamic>>(
      '/trips/plans',
      data: {
        'message_id': messageId,
        'trip_name': '$destination之旅',
        'destination': destination,
        'start_date': planData['start_date'],
        'end_date': planData['end_date'],
        'trip_type': planData['style'] ?? 'leisure',
        'itinerary': planData['itinerary'],
        'people_to_meet': planData['people_to_meet'],
        'tasks': planData['tasks'],
        'duration_days': planData['duration_days'],
      },
    );
    return response['trip_id'] as String;
  }

  // Non-streaming chat (WebSocket mode)
  @override
  Future<ChatJobResponse> sendChatMessage({
    required String message,
    String? sessionId,
    double? latitude,
    double? longitude,
    String? locationName,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/chat',
      data: {
        'message': message,
        if (sessionId != null) 'session_id': sessionId,
        if (latitude != null) 'latitude': latitude,
        if (longitude != null) 'longitude': longitude,
        if (locationName != null) 'location_name': locationName,
      },
    );
    return ChatJobResponse.fromJson(response);
  }

  // Non-streaming regenerate (WebSocket mode)
  @override
  Future<Map<String, dynamic>> regenerateMessageWs({
    required String sessionId,
    required String messageId,
  }) async {
    final response = await apiClient.post<Map<String, dynamic>>(
      '/chat/regenerate',
      data: {
        'session_id': sessionId,
        'message_id': messageId,
      },
    );
    return response;
  }

  @override
  Future<void> cancelGeneration({
    required String sessionId,
  }) async {
    await apiClient.post<Map<String, dynamic>>(
      '/chat/cancel',
      data: {
        'session_id': sessionId,
      },
    );
  }

  @override
  Future<Map<String, String>> getDailySummaries({
    required String sessionId,
  }) async {
    try {
      // Backend returns a JSON array: [{date: 'YYYY-MM-DD', summary: '...'}, ...]
      final raw = await apiClient.get<dynamic>(
        '/chat/daily-summaries',
        queryParameters: {'session_id': sessionId},
      );
      final list = raw is List ? raw : <dynamic>[];
      return {
        for (final item in list)
          if (item is Map<String, dynamic> &&
              (item['date'] as String? ?? '').isNotEmpty)
            item['date'] as String: item['summary'] as String? ?? '',
      };
    } catch (_) {
      return {};
    }
  }
}
