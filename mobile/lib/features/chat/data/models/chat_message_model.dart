import '../../domain/entities/chat_message.dart';

class ChatMessageModel extends ChatMessage {
  const ChatMessageModel({
    required super.id,
    required super.sessionId,
    required super.role,
    required super.content,
    super.intent,
    super.data,
    super.quickActions,
    super.isStreaming,
    super.isSuperseded,
    super.cardType,
    super.feedback,
    super.feedbackReason,
    required super.createdAt,
  });

  factory ChatMessageModel.fromJson(Map<String, dynamic> json) {
    return ChatMessageModel(
      id: json['id'] ?? '',
      sessionId: json['session_id'] ?? '',
      role: json['role'] == 'user' ? MessageRole.user : MessageRole.assistant,
      content: json['content'] ?? '',
      intent: json['intent'],
      data: json['data'],
      quickActions: (json['quick_actions'] as List<dynamic>?)
          ?.map((a) => QuickActionModel.fromJson(a))
          .toList(),
      isSuperseded: json['is_superseded'] ?? false,
      cardType: json['card_type'],
      feedback: json['feedback'],
      feedbackReason: json['feedback_reason'],
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'])
          : DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'session_id': sessionId,
      'role': role == MessageRole.user ? 'user' : 'assistant',
      'content': content,
      'intent': intent,
      'data': data,
      'quick_actions': quickActions?.map((a) => (a as QuickActionModel).toJson()).toList(),
      if (isSuperseded) 'is_superseded': isSuperseded,
      if (cardType != null) 'card_type': cardType,
      if (feedback != null) 'feedback': feedback,
      if (feedbackReason != null) 'feedback_reason': feedbackReason,
      'created_at': createdAt.toIso8601String(),
    };
  }
}

class QuickActionModel extends QuickAction {
  const QuickActionModel({
    required super.label,
    required super.action,
    super.type,
    super.icon,
    super.variant,
    super.metadata,
  });

  factory QuickActionModel.fromJson(Map<String, dynamic> json) {
    return QuickActionModel(
      label: json['label'] is String ? json['label'] as String : '',
      action: json['action'] is String ? json['action'] as String : '',
      type: json['type'] is String ? json['type'] as String : null,
      icon: json['icon'] is String ? json['icon'] as String : null,
      variant: json['variant'] is String ? json['variant'] as String : null,
      metadata: json['metadata'] is Map<String, dynamic>
          ? json['metadata'] as Map<String, dynamic>
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'label': label,
      'action': action,
      if (type != null) 'type': type,
      if (icon != null) 'icon': icon,
      if (variant != null) 'variant': variant,
      if (metadata != null) 'metadata': metadata,
    };
  }
}

class ChatResponseModel {
  final String sessionId;
  final String response;
  final String? intent;
  final Map<String, dynamic>? data;
  final List<QuickActionModel>? quickActions;
  final bool requiresMoreInfo;
  final Map<String, dynamic>? collectedInfo;

  ChatResponseModel({
    required this.sessionId,
    required this.response,
    this.intent,
    this.data,
    this.quickActions,
    this.requiresMoreInfo = false,
    this.collectedInfo,
  });

  factory ChatResponseModel.fromJson(Map<String, dynamic> json) {
    return ChatResponseModel(
      sessionId: json['session_id'] ?? '',
      response: json['response'] ?? '',
      intent: json['intent'],
      data: json['data'],
      quickActions: (json['quick_actions'] as List<dynamic>?)
          ?.map((a) => QuickActionModel.fromJson(a))
          .toList(),
      requiresMoreInfo: json['requires_more_info'] ?? false,
      collectedInfo: json['collected_info'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'session_id': sessionId,
      'response': response,
      if (intent != null) 'intent': intent,
      if (data != null) 'data': data,
      if (quickActions != null)
        'quick_actions': quickActions!.map((a) => a.toJson()).toList(),
      'requires_more_info': requiresMoreInfo,
      if (collectedInfo != null) 'collected_info': collectedInfo,
    };
  }
}

class ChatSessionModel extends ChatSession {
  const ChatSessionModel({
    required super.id,
    super.title,
    required super.createdAt,
    super.lastMessageAt,
  });

  factory ChatSessionModel.fromJson(Map<String, dynamic> json) {
    return ChatSessionModel(
      id: json['id'] ?? json['session_id'] ?? '',
      title: json['title'],
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'])
          : DateTime.now(),
      lastMessageAt: json['last_active_at'] != null
          ? DateTime.parse(json['last_active_at'])
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'created_at': createdAt.toIso8601String(),
      'last_active_at': lastMessageAt?.toIso8601String(),
    };
  }
}

// Today View Models
class TodayItemModel {
  final String id;
  final String title;
  final String? description;
  final String urgency; // 'urgent', 'important', 'normal'
  final String sourceType;
  final String sourceId;
  final DateTime? dueDatetime;
  final List<Map<String, String>> actions;

  TodayItemModel({
    required this.id,
    required this.title,
    this.description,
    required this.urgency,
    required this.sourceType,
    required this.sourceId,
    this.dueDatetime,
    this.actions = const [],
  });

  factory TodayItemModel.fromJson(Map<String, dynamic> json) {
    return TodayItemModel(
      id: json['id'] ?? '',
      title: json['title'] ?? '',
      description: json['description'],
      urgency: json['urgency'] ?? 'normal',
      sourceType: json['source_type'] ?? '',
      sourceId: json['source_id'] ?? '',
      dueDatetime: json['due_datetime'] != null
          ? DateTime.parse(json['due_datetime'])
          : null,
      actions: (json['actions'] as List<dynamic>?)
              ?.map((a) => Map<String, String>.from(a))
              .toList() ??
          [],
    );
  }
}

class AISuggestionModel {
  final String id;
  final String suggestionType;
  final String content;
  final List<Map<String, String>> actions;
  final int priority;

  AISuggestionModel({
    required this.id,
    required this.suggestionType,
    required this.content,
    this.actions = const [],
    this.priority = 0,
  });

  factory AISuggestionModel.fromJson(Map<String, dynamic> json) {
    return AISuggestionModel(
      id: json['id'] ?? '',
      suggestionType: json['suggestion_type'] ?? '',
      content: json['content'] ?? '',
      actions: (json['actions'] as List<dynamic>?)
              ?.map((a) => Map<String, String>.from(a))
              .toList() ??
          [],
      priority: json['priority'] ?? 0,
    );
  }
}

class TodaySummaryModel {
  final int totalItems;
  final int urgentCount;
  final int importantCount;
  final int normalCount;
  final Map<String, int> sourceBreakdown;

  TodaySummaryModel({
    required this.totalItems,
    required this.urgentCount,
    required this.importantCount,
    required this.normalCount,
    this.sourceBreakdown = const {},
  });

  factory TodaySummaryModel.fromJson(Map<String, dynamic> json) {
    return TodaySummaryModel(
      totalItems: json['total_items'] ?? 0,
      urgentCount: json['urgent_count'] ?? 0,
      importantCount: json['important_count'] ?? 0,
      normalCount: json['normal_count'] ?? 0,
      sourceBreakdown: json['source_breakdown'] != null
          ? Map<String, int>.from(json['source_breakdown'])
          : {},
    );
  }
}

class TodayViewModel {
  final String date;
  final String greeting;
  final TodaySummaryModel summary;
  final List<TodayItemModel> urgentItems;
  final List<TodayItemModel> importantItems;
  final List<TodayItemModel> normalItems;
  final List<AISuggestionModel> suggestions;

  TodayViewModel({
    required this.date,
    required this.greeting,
    required this.summary,
    this.urgentItems = const [],
    this.importantItems = const [],
    this.normalItems = const [],
    this.suggestions = const [],
  });

  factory TodayViewModel.fromJson(Map<String, dynamic> json) {
    return TodayViewModel(
      date: json['date'] ?? '',
      greeting: json['greeting'] ?? '',
      summary: TodaySummaryModel.fromJson(json['summary'] ?? {}),
      urgentItems: (json['urgent_items'] as List<dynamic>?)
              ?.map((i) => TodayItemModel.fromJson(i))
              .toList() ??
          [],
      importantItems: (json['important_items'] as List<dynamic>?)
              ?.map((i) => TodayItemModel.fromJson(i))
              .toList() ??
          [],
      normalItems: (json['normal_items'] as List<dynamic>?)
              ?.map((i) => TodayItemModel.fromJson(i))
              .toList() ??
          [],
      suggestions: (json['suggestions'] as List<dynamic>?)
              ?.map((s) => AISuggestionModel.fromJson(s))
              .toList() ??
          [],
    );
  }
}

// Tasks Models
class TaskModel {
  final String id;
  final String title;
  final String? description;
  final String? taskType;
  final String status;
  final String priority;
  final DateTime? dueDate;
  final String? dueTime;
  final String? assigneeId;
  final bool isOverdue;
  final TaskProgressModel? progress;

  TaskModel({
    required this.id,
    required this.title,
    this.description,
    this.taskType,
    required this.status,
    required this.priority,
    this.dueDate,
    this.dueTime,
    this.assigneeId,
    this.isOverdue = false,
    this.progress,
  });

  factory TaskModel.fromJson(Map<String, dynamic> json) {
    return TaskModel(
      id: json['id'] ?? '',
      title: json['title'] ?? '',
      description: json['description'],
      taskType: json['task_type'],
      status: json['status'] ?? 'pending',
      priority: json['priority'] ?? 'medium',
      dueDate: json['due_date'] != null ? DateTime.parse(json['due_date']) : null,
      dueTime: json['due_time'],
      assigneeId: json['assignee_id'],
      isOverdue: json['is_overdue'] ?? false,
      progress: json['progress'] != null
          ? TaskProgressModel.fromJson(json['progress'])
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'description': description,
      'task_type': taskType,
      'status': status,
      'priority': priority,
      'due_date': dueDate?.toIso8601String().split('T').first,
      'due_time': dueTime,
      'assignee_id': assigneeId,
    };
  }
}

class TaskProgressModel {
  final int total;
  final int completed;
  final double percentage;

  TaskProgressModel({
    required this.total,
    required this.completed,
    required this.percentage,
  });

  factory TaskProgressModel.fromJson(Map<String, dynamic> json) {
    return TaskProgressModel(
      total: json['total'] ?? 0,
      completed: json['completed'] ?? 0,
      percentage: (json['percentage'] ?? 0).toDouble(),
    );
  }
}

class MyTasksModel {
  final List<TaskModel> overdue;
  final List<TaskModel> today;
  final List<TaskModel> upcoming;
  final List<TaskModel> noDueDate;

  MyTasksModel({
    this.overdue = const [],
    this.today = const [],
    this.upcoming = const [],
    this.noDueDate = const [],
  });

  factory MyTasksModel.fromJson(Map<String, dynamic> json) {
    return MyTasksModel(
      overdue: (json['overdue'] as List<dynamic>?)
              ?.map((t) => TaskModel.fromJson(t))
              .toList() ??
          [],
      today: (json['today'] as List<dynamic>?)
              ?.map((t) => TaskModel.fromJson(t))
              .toList() ??
          [],
      upcoming: (json['upcoming'] as List<dynamic>?)
              ?.map((t) => TaskModel.fromJson(t))
              .toList() ??
          [],
      noDueDate: (json['no_due_date'] as List<dynamic>?)
              ?.map((t) => TaskModel.fromJson(t))
              .toList() ??
          [],
    );
  }
}

class TaskStatsModel {
  final int total;
  final int pending;
  final int inProgress;
  final int completed;
  final int cancelled;
  final int overdue;
  final int today;
  final double completionRate;

  TaskStatsModel({
    required this.total,
    required this.pending,
    required this.inProgress,
    required this.completed,
    required this.cancelled,
    required this.overdue,
    required this.today,
    required this.completionRate,
  });

  factory TaskStatsModel.fromJson(Map<String, dynamic> json) {
    return TaskStatsModel(
      total: json['total'] ?? 0,
      pending: json['pending'] ?? 0,
      inProgress: json['in_progress'] ?? 0,
      completed: json['completed'] ?? 0,
      cancelled: json['cancelled'] ?? 0,
      overdue: json['overdue'] ?? 0,
      today: json['today'] ?? 0,
      completionRate: (json['completion_rate'] ?? 0).toDouble(),
    );
  }
}

// Holiday Models
class HolidayPlanModel {
  final String id;
  final String holidayType;
  final String holidayName;
  final int holidayYear;
  final DateTime holidayDate;
  final String status;
  final int daysUntilHoliday;
  final Map<String, dynamic> planContent;

  HolidayPlanModel({
    required this.id,
    required this.holidayType,
    required this.holidayName,
    required this.holidayYear,
    required this.holidayDate,
    required this.status,
    required this.daysUntilHoliday,
    this.planContent = const {},
  });

  factory HolidayPlanModel.fromJson(Map<String, dynamic> json) {
    return HolidayPlanModel(
      id: json['id'] ?? '',
      holidayType: json['holiday_type'] ?? '',
      holidayName: json['holiday_name'] ?? '',
      holidayYear: json['holiday_year'] ?? DateTime.now().year,
      holidayDate: json['holiday_date'] != null
          ? DateTime.parse(json['holiday_date'])
          : DateTime.now(),
      status: json['status'] ?? 'draft',
      daysUntilHoliday: json['days_until_holiday'] ?? 0,
      planContent: json['plan_content'] ?? {},
    );
  }
}
