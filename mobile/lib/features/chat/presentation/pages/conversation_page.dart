import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/di/injection.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../core/network/websocket_service.dart';
import '../../../../core/storage/auth_storage.dart';
import '../../domain/entities/chat_message.dart';
import '../../domain/repositories/assistant_repository.dart';
import '../../domain/entities/generation_step.dart';
import '../bloc/assistant_bloc.dart';
import '../widgets/chat_bubble.dart';
import '../widgets/chat_input.dart';
import '../bloc/daily_briefing_bloc.dart';
import '../../domain/entities/daily_briefing.dart';
import '../../data/models/memory_model.dart';
import '../../../kanban/presentation/bloc/schedule_bloc.dart';
import '../../../kanban/presentation/bloc/schedule_event.dart';
import '../../../kanban/presentation/bloc/schedule_state.dart';
import '../widgets/animated_message_entry.dart';
import '../widgets/briefing_message_card.dart';
import '../widgets/network_status_banner.dart';
import '../widgets/onboarding_guide.dart';
import '../widgets/time_separator.dart';
import '../widgets/async_push_badge.dart';
import '../widgets/briefing_compact_strip.dart';
import '../widgets/history_load_trigger.dart';
import '../widgets/day_summary_marker.dart';
import '../../../../core/storage/local_storage.dart';

/// Hybrid conversation page (对话空间).
/// Fixed header + quick badges + chat interface with briefing as first message.
class ConversationPage extends StatefulWidget {
  const ConversationPage({super.key});

  @override
  State<ConversationPage> createState() => _ConversationPageState();
}

class _ConversationPageState extends State<ConversationPage>
    with WidgetsBindingObserver {
  final ScrollController _scrollController = ScrollController();
  final TextEditingController _textController = TextEditingController();
  final FocusNode _focusNode = FocusNode();

  /// True while a real finger-touch drag is in progress.
  bool _isUserDragging = false;

  /// Number of new messages received while user is scrolled up.
  int _unreadCount = 0;

  /// Threshold (in pixels) from bottom — if within this range, auto-scroll.
  static const double _nearBottomThreshold = 200.0;

  /// Time gap threshold for inserting time separators (30 minutes).
  static const Duration _timeSeparatorThreshold = Duration(minutes: 30);

  late DailyBriefingBloc _dailyBriefingBloc;
  late AssistantBloc _assistantBloc;
  StreamSubscription<DailyBriefingState>? _briefingSubscription;
  StreamSubscription<void>? _reconnectSubscription;
  StreamSubscription<WsConnectionStatus>? _wsStatusSubscription;

  /// Cache the current greeting to detect changes
  String _currentGreeting = '';

  /// Track message IDs that have already been animated.
  final Set<String> _animatedMessageIds = {};

  /// Current WebSocket connection status for the network banner.
  ConnectionStatus _connectionStatus = ConnectionStatus.connected;

  /// Stable timestamp for the streaming bubble — set once when streaming starts.
  DateTime _streamingStartTime = DateTime.now();

  /// True when briefing has been scrolled out of view (or read today).
  bool _briefingScrolledOff = false;

  /// GlobalKey for BriefingCompactStrip to call .pulse()
  final GlobalKey<BriefingCompactStripState> _compactStripKey = GlobalKey();

  /// Daily session summaries by date string (preloaded in initState).
  final Map<String, String> _dailySummaries = {};

  /// Track last known urgentInsights count to detect new insights.
  int _lastUrgentInsightCount = 0;

  /// LocalStorage key for briefing read date.
  static const String _briefingReadDateKey = 'briefing_read_date';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _currentGreeting = _getGreeting();
    _assistantBloc = context.read<AssistantBloc>();
    _dailyBriefingBloc = getIt<DailyBriefingBloc>()
      ..add(LoadDailyBriefingRequested(targetDate: DateTime.now()));
    // Watch for new urgent insights to trigger compact strip pulse.
    _briefingSubscription = _dailyBriefingBloc.stream.listen((briefState) {
      if (briefState is DailyBriefingLoaded) {
        final newCount = briefState.urgentInsights.length;
        if (newCount > _lastUrgentInsightCount && _briefingScrolledOff) {
          _compactStripKey.currentState?.pulse();
        }
        _lastUrgentInsightCount = newCount;
      }
    });
    // Ensure ScheduleBloc loads data for quick action badges
    final scheduleBloc = getIt<ScheduleBloc>();
    if (scheduleBloc.state is ScheduleInitial) {
      scheduleBloc.add(const ScheduleLoadRequested());
    }
    _connectWebSocket();
    _assistantBloc.startWebSocketListening();
    // Restore active session and load chat history on cold start.
    _assistantBloc.add(const AssistantRestoreSession());
    _reconnectSubscription =
        getIt<WebSocketService>().onReconnected.listen((_) {
      _assistantBloc.add(const AssistantSyncPendingActions());
    });

    // Listen to WebSocket connection status changes.
    final wsService = getIt<WebSocketService>();
    _connectionStatus = _mapWsStatus(wsService.connectionStatus);
    _wsStatusSubscription = wsService.onStatusChanged.listen((wsStatus) {
      final mapped = _mapWsStatus(wsStatus);
      if (mounted && mapped != _connectionStatus) {
        setState(() => _connectionStatus = mapped);
      }
    });

    _scrollController.addListener(_onScroll);
    // Check if briefing was already read today (auto-collapse).
    _checkBriefingReadDate();
    // Preload daily summaries in background.
    _loadDailySummaries();
  }

  /// Map WsConnectionStatus to the banner's ConnectionStatus.
  ConnectionStatus _mapWsStatus(WsConnectionStatus ws) {
    switch (ws) {
      case WsConnectionStatus.connected:
        return ConnectionStatus.connected;
      case WsConnectionStatus.disconnected:
        return ConnectionStatus.disconnected;
      case WsConnectionStatus.reconnecting:
        return ConnectionStatus.reconnecting;
    }
  }

  void _connectWebSocket() {
    try {
      final authStorage = getIt<AuthStorage>();
      final userId = authStorage.getUserId();
      if (userId != null) {
        getIt<WebSocketService>().connect(userId);
      }
    } catch (e) {
      // WebSocket connection failure is non-fatal
    }
  }

  void _onScroll() {
    if (!_scrollController.hasClients) return;
    // With reverse: true, position 0.0 = bottom of chat.
    final isNearBottom =
        _scrollController.position.pixels < _nearBottomThreshold;
    if (isNearBottom && _unreadCount > 0) {
      setState(() => _unreadCount = 0);
    }
    // Detect if user has scrolled up far enough to hide the briefing.
    if (!_briefingScrolledOff) {
      final pixels = _scrollController.position.pixels;
      // A reasonable heuristic: briefing is typically ~200px tall.
      // When user scrolls more than 250px up, consider briefing scrolled off.
      if (pixels > 250) {
        setState(() => _briefingScrolledOff = true);
        _markBriefingReadToday();
      }
    }
  }

  void _checkBriefingReadDate() {
    try {
      final storage = getIt<LocalStorage>();
      final savedDate = storage.get<String>(_briefingReadDateKey);
      final today = _todayDateString();
      final shouldCollapse = savedDate == today;
      if (mounted && _briefingScrolledOff != shouldCollapse) {
        setState(() => _briefingScrolledOff = shouldCollapse);
      } else if (!mounted) {
        _briefingScrolledOff = shouldCollapse;
      }
    } catch (_) {}
  }

  void _markBriefingReadToday() {
    try {
      final storage = getIt<LocalStorage>();
      storage.save<String>(_briefingReadDateKey, _todayDateString());
    } catch (_) {}
  }

  String _todayDateString() {
    final now = DateTime.now();
    return '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';
  }

  Future<void> _loadDailySummaries() async {
    try {
      final state = _assistantBloc.state;
      if (state is! AssistantLoaded) return;
      final sessionId = state.sessionId;
      if (sessionId == null || sessionId.isEmpty) return;
      final summaries = await getIt<AssistantRepository>()
          .getDailySummaries(sessionId: sessionId);
      if (mounted && summaries.isNotEmpty) {
        setState(() => _dailySummaries.addAll(summaries));
      }
    } catch (_) {}
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    super.didChangeAppLifecycleState(state);
    if (state == AppLifecycleState.resumed) {
      final newGreeting = _getGreeting();
      if (newGreeting != _currentGreeting) {
        setState(() => _currentGreeting = newGreeting);
      }
      _dailyBriefingBloc.add(const RefreshDailyBriefingRequested());
      _assistantBloc.add(const AssistantSyncPendingActions());
      // Re-check briefing date on resume (handles cross-day reset).
      _checkBriefingReadDate();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _briefingSubscription?.cancel();
    _wsStatusSubscription?.cancel();
    _scrollController.removeListener(_onScroll);
    _scrollController.dispose();
    _textController.dispose();
    _focusNode.dispose();
    _assistantBloc.stopWebSocketListening();
    _reconnectSubscription?.cancel();
    super.dispose();
  }

  /// Track whether a real finger-drag is in progress.
  bool _handleScrollNotification(ScrollNotification notification) {
    if (notification is ScrollStartNotification) {
      _isUserDragging = notification.dragDetails != null;
    } else if (notification is ScrollEndNotification && _isUserDragging) {
      _isUserDragging = false;
    }
    return false;
  }

  /// Smooth scroll to bottom (position 0.0 in reverse mode).
  void _scrollToBottom({bool force = false}) {
    if (!_scrollController.hasClients) return;
    if (_isUserDragging) return;

    final position = _scrollController.position;
    // With reverse: true, pixels == 0.0 means "at the newest message".
    final isNearBottom = position.pixels < _nearBottomThreshold;

    if (force || isNearBottom) {
      _scrollController.animateTo(
        0.0,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOutCubic,
      );
      if (_unreadCount > 0) {
        setState(() => _unreadCount = 0);
      }
    } else {
      // User is scrolled up — increment unread.
      setState(() => _unreadCount++);
    }
  }

  void _sendMessage([String? message]) {
    final text = message ?? _textController.text.trim();
    if (text.isEmpty) return;
    context.read<AssistantBloc>().add(AssistantStreamMessage(text));
    _textController.clear();
    _scrollToBottom(force: true);
  }

  void _fillInput(String text) {
    _textController.text = text;
    _focusNode.requestFocus();
  }

  bool get _isDisconnected =>
      _connectionStatus == ConnectionStatus.disconnected ||
      _connectionStatus == ConnectionStatus.reconnecting;

  String _getUsername() {
    try {
      final authStorage = getIt<AuthStorage>();
      final info = authStorage.getUserInfo();
      final name = info?['username'] as String?;
      if (name != null && name.isNotEmpty) return name;
    } catch (_) {}
    return '老板';
  }

  String _getUserInitial() {
    final name = _getUsername();
    if (name.isEmpty) return '我';
    return name.characters.first;
  }

  String _getGreeting() {
    final hour = DateTime.now().hour;
    final name = _getUsername();
    final String timeWord;
    final String emoji;
    if (hour < 6 || hour >= 22) {
      timeWord = '夜深了';
      emoji = '🌙';
    } else if (hour < 9) {
      timeWord = '早安';
      emoji = '☀️';
    } else if (hour < 12) {
      timeWord = '上午好';
      emoji = '🌤️';
    } else if (hour < 14) {
      timeWord = '中午好';
      emoji = '🌞';
    } else if (hour < 18) {
      timeWord = '下午好';
      emoji = '⛅';
    } else {
      timeWord = '晚上好';
      emoji = '🌆';
    }
    return '$timeWord，$name $emoji';
  }

  String _getDateSublineWithWeather(dynamic briefingState) {
    final now = DateTime.now();
    final weekday = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][now.weekday - 1];
    final base = '$weekday · ${now.month}月${now.day}日';
    // Try to extract weather info from briefing greeting (e.g. "北京 -3°C 晴")
    if (briefingState is DailyBriefingLoaded) {
      final greeting = briefingState.briefing.greeting;
      // The greeting often contains location + weather, extract if available
      final weatherMatch =
          RegExp(r'[\u4e00-\u9fff]+\s*-?\d+°?C?\s*[\u4e00-\u9fff]*')
              .firstMatch(greeting);
      if (weatherMatch != null) {
        return '$base · ${weatherMatch.group(0)!.trim()}';
      }
    }
    return base;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            _buildGreetingHeader(),
            _buildQuickActionBadges(),
            const SizedBox(height: 8),
            NetworkStatusBanner(status: _connectionStatus),
            Expanded(
              child: BlocConsumer<AssistantBloc, AssistantState>(
                listener: _onAssistantStateChanged,
                buildWhen: (previous, current) {
                  if (previous is! AssistantLoaded ||
                      current is! AssistantLoaded) {
                    return true;
                  }
                  // Only rebuild for fields that affect the chat area.
                  return previous.messages != current.messages ||
                      previous.isStreaming != current.isStreaming ||
                      previous.streamingContent != current.streamingContent ||
                      previous.generationSteps != current.generationSteps ||
                      previous.progressHistory != current.progressHistory ||
                      previous.hasPartialMessage != current.hasPartialMessage ||
                      previous.currentGenerationId != current.currentGenerationId ||
                      previous.awaitingBridging != current.awaitingBridging ||
                      previous.interruptionType != current.interruptionType ||
                      previous.historyHasMore != current.historyHasMore ||
                      previous.isLoadingHistory != current.isLoadingHistory;
                },
                builder: (context, state) {
                  return Stack(
                    children: [
                      _buildChatArea(state),
                      if (_unreadCount > 0) _buildNewMessageFAB(),
                      if (_briefingScrolledOff) _buildCompactBriefingStrip(),
                      if (_briefingScrolledOff &&
                          state is AssistantLoaded &&
                          state.messages.isNotEmpty)
                        _buildJumpToTodayFAB(),
                    ],
                  );
                },
              ),
            ),
            BlocBuilder<AssistantBloc, AssistantState>(
              buildWhen: (previous, current) {
                if (previous is! AssistantLoaded ||
                    current is! AssistantLoaded) {
                  return true;
                }
                return previous.isLoading != current.isLoading ||
                    previous.isStreaming != current.isStreaming ||
                    previous.queuedInputCount != current.queuedInputCount ||
                    previous.progressStage != current.progressStage ||
                    previous.signalHint != current.signalHint ||
                    previous.signalHintType != current.signalHintType;
              },
              builder: (context, state) {
                final loaded =
                    state is AssistantLoaded ? state : const AssistantLoaded();
                return ChatInput(
                  controller: _textController,
                  focusNode: _focusNode,
                  onSend: () => _sendMessage(),
                  isLoading: loaded.isLoading,
                  isStreaming: loaded.isStreaming,
                  queuedCount: loaded.queuedInputCount,
                  isDisconnected: _isDisconnected,
                  signalHint: loaded.signalHint,
                  signalHintType: loaded.signalHintType,
                  onStop: () {
                    context
                        .read<AssistantBloc>()
                        .add(const AssistantStopGeneration());
                  },
                  onVoiceMessage: (path) {
                    context
                        .read<AssistantBloc>()
                        .add(AssistantVoiceMessage(path));
                    _scrollToBottom(force: true);
                  },
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildGreetingHeader() {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          // User avatar (larger, ~48px to match prototype)
          Container(
            width: 48,
            height: 48,
            decoration: const BoxDecoration(
              color: AppColors.primary,
              shape: BoxShape.circle,
            ),
            child: Center(
              child: Text(
                _getUserInitial(),
                style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w600,
                  color: Colors.white,
                ),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _currentGreeting,
                  style: const TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                BlocBuilder(
                  bloc: _dailyBriefingBloc,
                  builder: (context, state) {
                    return Text(
                      _getDateSublineWithWeather(state),
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppColors.textSecondary,
                      ),
                    );
                  },
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQuickActionBadges() {
    return BlocBuilder<ScheduleBloc, ScheduleState>(
      bloc: getIt<ScheduleBloc>(),
      builder: (context, scheduleState) {
        return BlocBuilder(
          bloc: _dailyBriefingBloc,
          builder: (context, briefingState) {
            // Today's schedule: prefer ScheduleBloc, fall back to briefing count
            int todayCount = 0;
            if (scheduleState is ScheduleLoaded) {
              todayCount = scheduleState.todayCount;
            } else if (briefingState is DailyBriefingLoaded) {
              todayCount = briefingState.briefing.todayEventCount;
            }

            // Urgent reminders: insights + alerts
            int reminderCount = 0;
            if (briefingState is DailyBriefingLoaded) {
              reminderCount = briefingState.urgentInsights.length +
                  briefingState.briefing.alerts.length;
            }

            // Preparation to-dos
            int todoCount = 0;
            if (briefingState is DailyBriefingLoaded) {
              todoCount = briefingState.briefing.preparationReminders.length;
            }

            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: [
                    _buildBadge(
                      icon: Icons.event_outlined,
                      label: '日程',
                      count: todayCount,
                      accentColor: AppColors.primary,
                      onTap: () => context.go(Routes.kanban),
                    ),
                    const SizedBox(width: 10),
                    _buildBadge(
                      icon: Icons.notifications_none_outlined,
                      label: '提醒',
                      count: reminderCount,
                      accentColor: AppColors.alertOrange,
                      onTap: () => context.push(Routes.insightHistory),
                    ),
                    const SizedBox(width: 10),
                    _buildBadge(
                      icon: Icons.check_circle_outline,
                      label: '待办',
                      count: todoCount,
                      accentColor: AppColors.secondary,
                      onTap: () => context.go(Routes.kanban),
                    ),
                    const SizedBox(width: 10),
                    _buildBadge(
                      icon: Icons.explore_outlined,
                      label: '发现',
                      accentColor: AppColors.accentBlue,
                      showArrow: true,
                      onTap: () => context.push(Routes.tripExploration),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  Widget _buildBadge({
    required IconData icon,
    required String label,
    int count = 0,
    required Color accentColor,
    bool showArrow = false,
    VoidCallback? onTap,
  }) {
    final ext = Theme.of(context).extension<AppColorsExtension>()!;
    final hasItems = count > 0;

    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOutCubic,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: hasItems
              ? accentColor.withValues(alpha: 0.08)
              : ext.cardBackground,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: hasItems
                ? accentColor.withValues(alpha: 0.18)
                : Theme.of(context).dividerColor,
            width: 0.5,
          ),
          boxShadow: hasItems
              ? [
                  BoxShadow(
                    color: accentColor.withValues(alpha: 0.10),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ]
              : null,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 15,
              color: hasItems ? accentColor : AppColors.textSecondary,
            ),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(
                fontSize: 13,
                color:
                    hasItems ? AppColors.textPrimary : AppColors.textSecondary,
                fontWeight: FontWeight.w500,
              ),
            ),
            if (count > 0) ...[
              const SizedBox(width: 5),
              Container(
                constraints: const BoxConstraints(minWidth: 18),
                height: 18,
                padding: const EdgeInsets.symmetric(horizontal: 5),
                decoration: BoxDecoration(
                  color: accentColor,
                  borderRadius: BorderRadius.circular(9),
                ),
                child: Center(
                  child: Text(
                    count > 99 ? '99+' : '$count',
                    style: const TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                      color: Colors.white,
                      height: 1.0,
                    ),
                  ),
                ),
              ),
            ],
            if (showArrow) ...[
              const SizedBox(width: 2),
              Icon(
                Icons.chevron_right,
                size: 14,
                color: accentColor.withValues(alpha: 0.6),
              ),
            ],
          ],
        ),
      ),
    );
  }

  void _onAssistantStateChanged(BuildContext context, AssistantState state) {
    if (state is AssistantLoaded) {
      // Guard: do not auto-scroll while the user is actively typing.
      if (_focusNode.hasFocus) return;
      // Scroll to bottom on state change.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _scrollToBottom();
      });
    }
  }

  Widget _buildChatArea(AssistantState state) {
    final messages =
        state is AssistantLoaded ? state.messages : <ChatMessage>[];
    final isStreaming = state is AssistantLoaded && state.isStreaming;
    final streamingContent =
        state is AssistantLoaded ? state.streamingContent : '';
    final generationSteps =
        state is AssistantLoaded ? state.generationSteps : <GenerationStep>[];
    final progressHistory = state is AssistantLoaded
        ? state.progressHistory
            .map((p) => MessageProgressStep(
                  stage: p.stage,
                  message: p.message,
                  timestamp: p.timestamp,
                  data: p.data,
                ))
            .toList()
        : <MessageProgressStep>[];

    // Filter out streaming messages — rendered separately at the end.
    final nonStreamingMessages = messages.where((m) => !m.isStreaming).toList();

    final hasMessages = nonStreamingMessages.isNotEmpty || isStreaming;

    if (!hasMessages) {
      // No chat messages: show briefing at top + onboarding suggestions below.
      return SingleChildScrollView(
        controller: _scrollController,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildBriefingSection(),
            const SizedBox(height: 16),
            OnboardingGuide(
              onPromptTap: _sendMessage,
              onFillInput: _fillInput,
            ),
          ],
        ),
      );
    }

    // Build the item list: briefing + (time separators interleaved with messages) + streaming.
    final items = _buildItemList(nonStreamingMessages, isStreaming,
        streamingContent, generationSteps, progressHistory);

    return NotificationListener<ScrollNotification>(
      onNotification: _handleScrollNotification,
      child: ListView.builder(
        controller: _scrollController,
        reverse: true,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        itemCount: items.length,
        itemBuilder: (context, index) {
          // reverse: true means index 0 = last item in list = newest.
          final item = items[items.length - 1 - index];
          return item;
        },
      ),
    );
  }

  /// Builds the list of widgets to display: briefing, time separators, messages, streaming bubble.
  List<Widget> _buildItemList(
    List<ChatMessage> messages,
    bool isStreaming,
    String streamingContent,
    List<GenerationStep> generationSteps,
    List<MessageProgressStep> progressHistory,
  ) {
    final items = <Widget>[];

    // History load trigger at physical top (oldest content, rendered last
    // in reverse ListView). Only present when AssistantLoaded.
    final assistantState = _assistantBloc.state;
    if (assistantState is AssistantLoaded) {
      items.add(HistoryLoadTrigger(
        key: const ValueKey('history-trigger'),
        hasMore: assistantState.historyHasMore,
        isLoading: assistantState.isLoadingHistory,
        onTrigger: () => _assistantBloc.add(const LoadMoreHistoryRequested()),
      ));
    }

    // Interleave time separators and day markers between messages.
    DateTime? lastTimestamp;
    for (final message in messages) {
      var dayMarkerInserted = false;
      // Check if we need a day boundary marker.
      if (lastTimestamp != null) {
        final prevDay = DateTime(
            lastTimestamp.year, lastTimestamp.month, lastTimestamp.day);
        final currDay = DateTime(
            message.createdAt.year,
            message.createdAt.month,
            message.createdAt.day);
        if (currDay != prevDay) {
          final dateKey =
              '${currDay.year}-${currDay.month.toString().padLeft(2, '0')}-${currDay.day.toString().padLeft(2, '0')}';
          items.add(DaySummaryMarker(
            key: ValueKey('day-marker-$dateKey'),
            date: currDay,
            summary: _dailySummaries[dateKey],
          ));
          dayMarkerInserted = true;
        }
      }
      // Check if we need a time separator — skip when day marker already fills the gap.
      if (!dayMarkerInserted && lastTimestamp != null) {
        final gap = message.createdAt.difference(lastTimestamp);
        if (gap > _timeSeparatorThreshold) {
          items.add(TimeSeparator(
            key: ValueKey('sep-${message.createdAt.millisecondsSinceEpoch}'),
            timestamp: message.createdAt,
          ));
        }
      }
      lastTimestamp = message.createdAt;

      // Inline additive acknowledgment (E-005): compact centered pill
      if (message.intent == 'additive_ack') {
        final isNew = !_animatedMessageIds.contains(message.id);
        if (isNew) _animatedMessageIds.add(message.id);
        items.add(AnimatedMessageEntry(
          key: ValueKey('anim-${message.id}'),
          isNew: isNew,
          isUser: false,
          child: Center(
            child: Container(
              margin: const EdgeInsets.symmetric(vertical: 4),
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: Colors.blue.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.link, size: 12, color: Colors.blue.withValues(alpha: 0.7)),
                  const SizedBox(width: 4),
                  Text(
                    message.content,
                    style: TextStyle(
                      fontSize: 11,
                      color: Colors.blue.withValues(alpha: 0.7),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ));
        continue;
      }

      // Wrap with async push badge if applicable.
      Widget messageWidget = ChatBubble(
        key: ValueKey(message.id),
        message: message,
        onRegenerate: (messageId) {
          context
              .read<AssistantBloc>()
              .add(AssistantRegenerateMessage(messageId));
        },
        onEdit: (messageId, newContent) {
          context
              .read<AssistantBloc>()
              .add(AssistantEditMessage(messageId, newContent));
        },
        onFeedback: (messageId, isLike, reason) {
          context.read<AssistantBloc>().add(AssistantFeedbackSubmitted(
                messageId: messageId,
                isPositive: isLike,
                reason: reason,
              ));
        },
        onConfirmTravelPlan: (messageId, planData) {
          final completer = Completer<String?>();
          context.read<AssistantBloc>().add(
                AssistantConfirmTravelPlan(
                  messageId,
                  planData,
                  onComplete: completer.complete,
                ),
              );
          return completer.future;
        },
        onQuickAction: (action) {
          if (action.type == 'navigate') {
            _handleNavigateAction(context, action);
          } else {
            context
                .read<AssistantBloc>()
                .add(AssistantQuickActionTapped(action));
          }
        },
      );

      // Superseded/stopped rendering is handled by ChatBubble (E-001 consolidation).

      // Sidekick insight messages get a distinctive visual wrapper:
      // teal left border strip + "Secretary" label badge.
      final isSidekick = message.cardType == 'sidekick_insight' ||
          message.intent == 'sidekick_insight';
      if (isSidekick) {
        messageWidget = _buildSidekickWrapper(messageWidget);
      }

      if (message.asyncSource != null) {
        messageWidget = Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.only(left: 4),
              child: AsyncPushBadge(source: message.asyncSource!, messageTime: message.createdAt),
            ),
            messageWidget,
          ],
        );
      }

      // Wrap with entrance animation.
      final isNew = !_animatedMessageIds.contains(message.id);
      if (isNew) {
        _animatedMessageIds.add(message.id);
      }
      final isUser = message.role == MessageRole.user;

      items.add(AnimatedMessageEntry(
        key: ValueKey('anim-${message.id}'),
        isNew: isNew,
        isUser: isUser,
        child: messageWidget,
      ));
    }

    // Briefing card after messages (at the newest end, so it appears at the
    // bottom of the reverse ListView — visible when user first opens the app).
    items.add(KeyedSubtree(
      key: const ValueKey('briefing'),
      child: _buildBriefingSection(),
    ));

    // Streaming bubble at the end.
    if (isStreaming) {
      final isStreamNew = !_animatedMessageIds.contains('streaming');
      if (isStreamNew) {
        _animatedMessageIds.add('streaming');
        _streamingStartTime = DateTime.now();
      }

      final loaded =
          _assistantBloc.state is AssistantLoaded ? _assistantBloc.state as AssistantLoaded : null;
      items.add(AnimatedMessageEntry(
        key: const ValueKey('anim-streaming'),
        isNew: isStreamNew,
        isUser: false,
        child: ChatBubble(
          key: const ValueKey('streaming-bubble'),
          message: ChatMessage(
            id: 'streaming',
            sessionId: '',
            role: MessageRole.assistant,
            content: streamingContent,
            generationSteps: generationSteps,
            progressHistory: progressHistory,
            isStreaming: true,
            isPartial: loaded?.hasPartialMessage ?? false,
            generationId: loaded?.currentGenerationId,
            createdAt: _streamingStartTime,
          ),
        ),
      ));
    } else {
      // When streaming ends, remove the 'streaming' marker so the next
      // streaming session gets a fresh animation.
      _animatedMessageIds.remove('streaming');
    }

    // Processing interruption indicator (E-003): shown while awaiting bridging.
    final loaded =
        _assistantBloc.state is AssistantLoaded ? _assistantBloc.state as AssistantLoaded : null;
    if (loaded != null && loaded.awaitingBridging) {
      items.add(KeyedSubtree(
        key: const ValueKey('interruption-processing'),
        child: _buildInterruptionIndicator(loaded.interruptionType),
      ));
    }

    return items;
  }

  Widget _buildInterruptionIndicator(String? interruptionType) {
    final String text;
    final IconData icon;
    final Color color;
    switch (interruptionType) {
      case 'correction':
        text = '正在重新组织回复...';
        icon = Icons.refresh;
        color = Colors.orange;
        break;
      case 'digression':
        text = '正在切换话题...';
        icon = Icons.swap_horiz;
        color = Colors.deepPurple;
        break;
      case 'cancel':
        // CANCEL is immediate — no processing visual needed
        return const SizedBox.shrink();
      default:
        text = '正在处理...';
        icon = Icons.hourglass_top;
        color = AppColors.primary;
        break;
    }
    return Padding(
      padding: const EdgeInsets.only(left: 4, top: 8, bottom: 8),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(
            width: 14,
            height: 14,
            child: CircularProgressIndicator.adaptive(
              strokeWidth: 2,
              valueColor: AlwaysStoppedAnimation<Color>(color),
            ),
          ),
          const SizedBox(width: 8),
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 4),
          Text(
            text,
            style: TextStyle(
              fontSize: 12,
              color: color,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCompactBriefingStrip() {
    final briefingState = _dailyBriefingBloc.state;
    final urgentInsights = briefingState is DailyBriefingLoaded
        ? briefingState.urgentInsights
        : <InsightModel>[];
    return Positioned(
      top: 0,
      left: 0,
      right: 0,
      child: BriefingCompactStrip(
        key: _compactStripKey,
        urgentInsights: urgentInsights,
        onTap: () {
          _scrollToBottom(force: true);
          setState(() => _briefingScrolledOff = false);
        },
      ),
    );
  }

  Widget _buildJumpToTodayFAB() {
    return Positioned(
      bottom: 60,
      right: 16,
      child: FloatingActionButton.small(
        heroTag: 'jump_to_today',
        onPressed: () {
          _scrollToBottom(force: true);
          setState(() => _briefingScrolledOff = false);
        },
        backgroundColor: Theme.of(context).colorScheme.primary,
        child: const Icon(
          Icons.keyboard_double_arrow_down,
          color: Colors.white,
          size: 20,
        ),
      ),
    );
  }

  Widget _buildNewMessageFAB() {
    return Positioned(
      bottom: 16,
      left: 0,
      right: 0,
      child: Center(
        child: GestureDetector(
          onTap: () => _scrollToBottom(force: true),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            decoration: BoxDecoration(
              color: AppColors.primary,
              borderRadius: BorderRadius.circular(20),
              boxShadow: [
                BoxShadow(
                  color: AppColors.primary.withValues(alpha: 0.3),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.arrow_downward, color: Colors.white, size: 16),
                const SizedBox(width: 6),
                Text(
                  '$_unreadCount 条新消息',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  /// Wraps a sidekick insight message with a teal left border and
  /// "Secretary" label badge for visual distinction from normal messages.
  Widget _buildSidekickWrapper(Widget child) {
    return Container(
      margin: const EdgeInsets.only(bottom: 2),
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              width: 3,
              decoration: BoxDecoration(
                color: AppColors.connectionAccent,
                borderRadius: BorderRadius.circular(1.5),
              ),
            ),
            const SizedBox(width: 6),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 8, vertical: 2),
                    margin: const EdgeInsets.only(bottom: 4),
                    decoration: BoxDecoration(
                      color: AppColors.connectionAccent
                          .withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Text(
                      'Secretary',
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w600,
                        color: AppColors.connectionAccent,
                      ),
                    ),
                  ),
                  child,
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _handleBriefingSuggestion(BriefingSuggestion suggestion) {
    switch (suggestion.actionType) {
      case 'navigate_to_trip':
        final tripId = suggestion.actionData['trip_id'] as String?;
        if (tripId != null) {
          context.push(Routes.tripDetail(tripId));
        }
        break;
      case 'navigate_to_kanban':
        context.go(Routes.kanban);
        break;
      case 'open_chat':
        final prefill = suggestion.actionData['prefill_text'] as String?;
        if (prefill != null) {
          _sendMessage(prefill);
        }
        break;
      case 'view_graph':
        context.push(Routes.insightGraph);
        break;
      case 'view_insights':
        context.push(Routes.insightSettings);
        break;
      case 'view_gifts':
        final insightContent =
            suggestion.actionData['insight_content'] as String?;
        final giftMessage = insightContent != null && insightContent.isNotEmpty
            ? '帮我准备礼物，$insightContent'
            : '帮我推荐合适的礼物';
        _sendMessage(giftMessage);
        break;
      default:
        _sendMessage(suggestion.label);
        break;
    }
  }

  void _handleNavigateAction(BuildContext context, QuickAction action) {
    final metadata = action.metadata;
    final tripId = metadata?['trip_id'] as String?;
    final eventId = metadata?['event_id'] as String?;
    final memberId = metadata?['member_id'] as String?;

    if (tripId != null) {
      context.push(Routes.tripDetail(tripId));
    } else if (eventId != null) {
      context.push(Routes.eventDetail(eventId));
    } else if (memberId != null) {
      context.push(Routes.memberDetail(memberId));
    } else if (action.action.startsWith('/')) {
      context.push(action.action);
    } else {
      // Fallback: send as message when no entity ID or route available.
      context.read<AssistantBloc>().add(AssistantQuickActionTapped(action));
    }
  }

  Widget _buildBriefingSection() {
    return BlocBuilder(
      bloc: _dailyBriefingBloc,
      builder: (context, state) {
        if (state is DailyBriefingLoading) {
          return _buildLoadingBriefing();
        }

        if (state is DailyBriefingLoaded) {
          return BriefingMessageCard(
            briefing: state.briefing,
            insights: state.urgentInsights,
            onSuggestionTap: _handleBriefingSuggestion,
          );
        }

        if (state is DailyBriefingError) {
          return BriefingMessageCard(
            briefing: DailyBriefing.empty(),
            insights: const [],
            onSuggestionTap: _handleBriefingSuggestion,
          );
        }

        return const SizedBox.shrink();
      },
    );
  }

  Widget _buildLoadingBriefing() {
    return Container(
      margin: const EdgeInsets.only(bottom: 16, right: 40),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: const Row(
        children: [
          SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              valueColor: AlwaysStoppedAnimation<Color>(AppColors.primary),
            ),
          ),
          SizedBox(width: 12),
          Text(
            '正在准备今日简报...',
            style: TextStyle(
              fontSize: 14,
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }
}
