import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/chat_message.dart';
import '../../domain/entities/generation_step.dart';
import 'event_card_bubble.dart';
import 'favor_balance_bubble.dart';
import 'gift_recommendation_bubble.dart';
import 'key_results_widget.dart';
import 'markdown_bubble.dart';
import 'member_profile_bubble.dart';
import 'message_action_bar.dart';
import 'ask_user_question_bubble.dart';
import 'pending_action_bubble.dart';
import 'task_list_bubble.dart';
import 'thinking_step_widget.dart';
import 'tool_display_names.dart';
import 'tool_step_widget.dart';
import 'trip_bubble.dart';
import 'upcoming_dates_bubble.dart';

/// Shared quick actions row widget used by ChatBubble and card bubbles.
/// Renders a horizontally scrollable row of action chips.
Widget buildQuickActionsRow(
  List<QuickAction> actions, {
  void Function(QuickAction action)? onTap,
}) {
  return SizedBox(
    height: 36,
    child: ListView.separated(
      scrollDirection: Axis.horizontal,
      shrinkWrap: true,
      itemCount: actions.length,
      separatorBuilder: (_, __) => const SizedBox(width: 8),
      itemBuilder: (context, index) {
        final action = actions[index];
        final (bgColor, fgColor, borderColor) = _resolveVariantColors(context, action.variant);
        final IconData? iconData = _resolveIconData(action.icon);

        return Material(
          color: bgColor,
          borderRadius: BorderRadius.circular(18),
          child: InkWell(
            onTap: onTap != null
                ? () {
                    HapticFeedback.lightImpact();
                    onTap(action);
                  }
                : null,
            borderRadius: BorderRadius.circular(18),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: borderColor != null
                  ? BoxDecoration(
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(color: borderColor),
                    )
                  : null,
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (iconData != null) ...[
                    Icon(iconData, size: 16, color: fgColor),
                    const SizedBox(width: 4),
                  ],
                  Text(
                    action.label,
                    style: AppTextStyles.caption.copyWith(
                      color: fgColor,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    ),
  );
}

(Color, Color, Color?) _resolveVariantColors(BuildContext context, String? variant) {
  final theme = Theme.of(context);
  final ext = theme.extension<AppColorsExtension>()!;
  switch (variant) {
    case 'primary':
      return (theme.colorScheme.primary, theme.colorScheme.onPrimary, null);
    case 'secondary':
    case 'outlined':
      return (
        theme.colorScheme.primary.withValues(alpha: 0.08),
        theme.colorScheme.primary,
        theme.colorScheme.primary.withValues(alpha: 0.3),
      );
    case 'destructive':
      return (theme.colorScheme.error.withValues(alpha: 0.1), theme.colorScheme.error, null);
    case 'text':
      return (Colors.transparent, theme.colorScheme.onSurfaceVariant, null);
    default:
      return (ext.chipBackground, theme.colorScheme.onSurface, null);
  }
}

IconData? _resolveIconData(String? name) {
  if (name == null || name.isEmpty) return null;
  const iconMap = <String, IconData>{
    'calendar_month': Icons.calendar_month,
    'cancel': Icons.cancel_outlined,
    'add_task': Icons.add_task,
    'check_circle': Icons.check_circle_outline,
    'edit': Icons.edit_outlined,
    'favorite': Icons.favorite_outline,
    'flight_takeoff': Icons.flight_takeoff,
    'edit_calendar': Icons.edit_calendar,
    'event': Icons.event,
    'info': Icons.info_outline,
    'handshake': Icons.handshake_outlined,
    'lightbulb': Icons.lightbulb_outline,
    'card_giftcard': Icons.card_giftcard,
    'refresh': Icons.refresh,
    'list_alt': Icons.list_alt,
    'location_on': Icons.location_on_outlined,
  };
  return iconMap[name];
}

class ChatBubble extends StatefulWidget {
  final ChatMessage message;
  final void Function(String messageId)? onRegenerate;
  final void Function(String messageId, String newContent)? onEdit;
  final void Function(String messageId, bool isLike, String? reason)? onFeedback;
  final Future<String?> Function(String messageId, Map<String, dynamic> planData)?
      onConfirmTravelPlan;
  final void Function(QuickAction action)? onQuickAction;

  const ChatBubble({
    super.key,
    required this.message,
    this.onRegenerate,
    this.onEdit,
    this.onFeedback,
    this.onConfirmTravelPlan,
    this.onQuickAction,
  });

  @override
  State<ChatBubble> createState() => _ChatBubbleState();
}

class _ChatBubbleState extends State<ChatBubble> {
  bool _showActions = false;
  bool _thinkingExpanded = false;
  bool _toolsExpanded = false;
  final Set<int> _expandedToolIndices = {};
  final Map<int, bool> _stepExpansionStates = {};
  static final RegExp _uuidRegex = RegExp(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$',
  );

  ChatMessage get message => widget.message;
  bool get _isServerMessageId => _uuidRegex.hasMatch(message.id);

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == MessageRole.user;

    // Route to specialized card bubbles
    if (!isUser) {
      // Sidekick insight card
      if (message.cardType == 'sidekick_insight' ||
          message.intent == 'sidekick_insight') {
        return _buildSidekickInsightCard(context);
      }

      final cardWidget = _routeToCardBubble();
      if (cardWidget != null) return cardWidget;
    }

    final generationSteps = message.generationSteps ?? const <GenerationStep>[];
    final hasRenderableSteps = generationSteps.any((step) {
      if (step is ThinkingStep) {
        return !(step.content.isEmpty && step.isComplete);
      }
      return true;
    });

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!isUser) _buildAvatar(),
          if (!isUser) const SizedBox(width: 8),
          Flexible(
            child: Column(
              crossAxisAlignment: isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
              children: [
                AnimatedSwitcher(
                  duration: const Duration(milliseconds: 300),
                  switchInCurve: Curves.easeIn,
                  switchOutCurve: Curves.easeOut,
                  transitionBuilder: (Widget child, Animation<double> animation) {
                    // Correction-specific: slide up + fade out for old, slide down + fade in for new
                    if (message.signalType == 'correction') {
                      return SlideTransition(
                        position: Tween<Offset>(
                          begin: const Offset(0, 0.05),
                          end: Offset.zero,
                        ).animate(CurvedAnimation(
                          parent: animation,
                          curve: Curves.easeOut,
                        )),
                        child: FadeTransition(opacity: animation, child: child),
                      );
                    }
                    return FadeTransition(opacity: animation, child: child);
                  },
                  child: Opacity(
                  key: isUser
                      ? null
                      : message.isStreaming
                          ? ValueKey('${message.id}_streaming')
                          : ValueKey('${message.id}_${message.isPartial}_${message.content.hashCode}'),
                  opacity: (!isUser && !message.isStreaming && (message.isPartial || message.isSuperseded)) ? 0.5 : 1.0,
                  child: Container(
                  constraints: BoxConstraints(
                    maxWidth: MediaQuery.of(context).size.width * 0.75,
                  ),
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  decoration: BoxDecoration(
                    color: isUser
                        ? Theme.of(context).extension<AppColorsExtension>()!.userBubble
                        : Theme.of(context).extension<AppColorsExtension>()!.assistantBubble,
                    borderRadius: isUser
                        ? BorderRadius.circular(20)
                        : const BorderRadius.only(
                            topLeft: Radius.circular(18),
                            topRight: Radius.circular(18),
                            bottomLeft: Radius.circular(4),
                            bottomRight: Radius.circular(18),
                          ),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.05 * Theme.of(context).extension<AppColorsExtension>()!.shadowOpacity),
                        blurRadius: 8,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      ...[
                        // Streaming placeholder
                        if (message.isStreaming &&
                            message.content.isEmpty &&
                            !hasRenderableSteps)
                          Column(
                            children: [
                              ThinkingStepWidget(
                                step: const ThinkingStep(content: '', isComplete: false),
                                isExpanded: true,
                              ),
                              const SizedBox(height: 8),
                            ],
                          ),
                        // Generation steps
                        if (!isUser && generationSteps.isNotEmpty)
                          ...generationSteps.asMap().entries.map((entry) {
                            final index = entry.key;
                            final step = entry.value;

                            if (step is ThinkingStep) {
                              if (step.content.isEmpty && step.isComplete) {
                                return const SizedBox.shrink();
                              }
                              final isExpanded = _stepExpansionStates[index] ?? !step.isComplete;
                              return Column(
                                children: [
                                  ThinkingStepWidget(
                                    step: step,
                                    isExpanded: isExpanded,
                                    onToggle: () {
                                      setState(() {
                                        _stepExpansionStates[index] = !isExpanded;
                                      });
                                    },
                                  ),
                                  const SizedBox(height: 8),
                                ],
                              );
                            } else if (step is ToolStep) {
                              final isExpanded = _stepExpansionStates[index] ?? false;
                              return Column(
                                children: [
                                  ToolStepWidget(
                                    tool: step.tool,
                                    isExpanded: isExpanded,
                                    onToggle: () {
                                      setState(() {
                                        _stepExpansionStates[index] = !isExpanded;
                                      });
                                    },
                                  ),
                                  const SizedBox(height: 8),
                                ],
                              );
                            } else if (step is ContentStep) {
                              return GestureDetector(
                                onTap: () {
                                  if (!message.isStreaming) {
                                    setState(() => _showActions = !_showActions);
                                  }
                                },
                                onLongPress: () => _showMessageActions(context),
                                behavior: HitTestBehavior.opaque,
                                child: ContentStepWidget(step: step),
                              );
                            }
                            return const SizedBox.shrink();
                          }),

                        // Legacy rendering fallback
                        if (!isUser &&
                            (message.generationSteps == null ||
                                message.generationSteps!.isEmpty)) ...[
                          if (!message.isStreaming &&
                              message.toolExecutions != null &&
                              message.toolExecutions!.isNotEmpty)
                            _buildToolExecutionsSection(),
                          if (message.thinking != null &&
                              message.thinking!.isNotEmpty)
                            _buildThinkingSection(),
                          if (message.content.isNotEmpty)
                            GestureDetector(
                              onTap: () {
                                if (!message.isStreaming) {
                                  setState(() => _showActions = !_showActions);
                                }
                              },
                              onLongPress: () => _showMessageActions(context),
                              behavior: HitTestBehavior.opaque,
                              child: MarkdownBubbleContent(
                                content: message.content,
                                isUser: false,
                                isStreaming: message.isStreaming,
                              ),
                            ),
                        ],

                        // User message content
                        if (isUser && message.content.isNotEmpty)
                          GestureDetector(
                            onTap: () {
                              if (!message.isStreaming) {
                                setState(() => _showActions = !_showActions);
                              }
                            },
                            onLongPress: () => _showMessageActions(context),
                            behavior: HitTestBehavior.opaque,
                            child: MarkdownBubbleContent(
                              content: message.content,
                              isUser: true,
                            ),
                          ),
                      ],
                      // Typing indicator
                      if (message.isStreaming &&
                          message.generationSteps != null &&
                          message.generationSteps!.any(
                            (s) => s is ContentStep && !s.isComplete,
                          ))
                        Padding(
                          padding: const EdgeInsets.only(top: 4),
                          child: _buildTypingIndicator(),
                        ),
                    ],
                  ),
                ),
                ),
                ),
                // Partial / stopped message tag (consolidated E-001)
                if (!isUser && !message.isStreaming &&
                    (message.isPartial || message.isStopped))
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(
                      message.isStopped
                          ? '已停止'
                          : message.signalType == 'cancel'
                              ? '已取消'
                              : message.signalType == 'correction'
                                  ? '已更新'
                                  : message.signalType == 'digression'
                                      ? '话题已切换'
                                      : message.isSuperseded
                                          ? '已被纠正'
                                          : '部分回复',
                      style: AppTextStyles.caption.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant.withValues(alpha: 0.6),
                        fontSize: 11,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                  ),
                // Quick actions
                if (!isUser && !message.isStreaming && message.quickActions != null && message.quickActions!.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: buildQuickActionsRow(
                      message.quickActions!,
                      onTap: widget.onQuickAction,
                    ),
                  ),
                const SizedBox(height: 4),
                // Action bar
                if (!message.isStreaming)
                  MessageActionBar(
                    createdAt: message.createdAt,
                    showActionsHighlighted: _showActions,
                    config: MessageActionBarConfig(
                      showCopy: true,
                      showRegenerate: !isUser && _isServerMessageId,
                      showFeedback: !isUser && _isServerMessageId,
                      showEdit: isUser && widget.onEdit != null && _isServerMessageId,
                      initialFeedback: message.feedback == 'positive'
                          ? true
                          : message.feedback == 'negative'
                              ? false
                              : null,
                      onCopy: () => _copyMessage(context),
                      onRegenerate: widget.onRegenerate != null
                          ? () => widget.onRegenerate!.call(message.id)
                          : null,
                      onFeedback: (isLike, reason) =>
                          widget.onFeedback?.call(message.id, isLike, reason),
                      onEdit: widget.onEdit != null
                          ? () => _showEditDialog(context)
                          : null,
                    ),
                  ),
              ],
            ),
          ),
          if (isUser) const SizedBox(width: 12),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Card bubble routing
  // ---------------------------------------------------------------------------

  Widget? _routeToCardBubble() {
    // Priority 1: Explicit cardType from backend normalizer
    if (message.cardType != null) {
      final routed = _routeByCardType(message.cardType!);
      if (routed != null) return routed;
    }

    // Priority 2: Heuristic detection (backward compatibility)
    if (_isGiftRecommendation()) {
      return GiftRecommendationBubble(
        message: message,
        onRegenerate: widget.onRegenerate,
        onFeedback: widget.onFeedback,
        onQuickAction: widget.onQuickAction,
      );
    }
    if (_isTravelPlan()) {
      return TripBubble(
        message: message,
        onRegenerate: widget.onRegenerate,
        onFeedback: widget.onFeedback,
        onConfirmPlan: widget.onConfirmTravelPlan,
        onQuickAction: widget.onQuickAction,
      );
    }
    if (_isPendingAction()) {
      return PendingActionBubble(
        message: message,
        onRegenerate: widget.onRegenerate,
        onFeedback: widget.onFeedback,
      );
    }
    if (_isAskUserQuestion()) {
      return AskUserQuestionBubble(
        message: message,
        onSubmitAnswer: null,
      );
    }
    if (_isEventCard()) {
      return EventCardBubble(
        message: message,
        onRegenerate: widget.onRegenerate,
        onFeedback: widget.onFeedback,
        onQuickAction: widget.onQuickAction,
      );
    }
    if (_isTaskCard()) {
      return TaskListBubble(
        message: message,
        onRegenerate: widget.onRegenerate,
        onFeedback: widget.onFeedback,
        onQuickAction: widget.onQuickAction,
      );
    }
    if (_isMemberProfile()) {
      return MemberProfileBubble(
        message: message,
        onRegenerate: widget.onRegenerate,
        onFeedback: widget.onFeedback,
        onQuickAction: widget.onQuickAction,
      );
    }
    if (_isUpcomingDates()) {
      return UpcomingDatesBubble(
        message: message,
        onRegenerate: widget.onRegenerate,
        onFeedback: widget.onFeedback,
        onQuickAction: widget.onQuickAction,
      );
    }
    if (_isFavorBalance()) {
      return FavorBalanceBubble(
        message: message,
        onRegenerate: widget.onRegenerate,
        onFeedback: widget.onFeedback,
        onQuickAction: widget.onQuickAction,
      );
    }
    return null;
  }

  Widget _buildSidekickInsightCard(BuildContext context) {
    final data = message.data ?? {};
    final title = data['title'] as String? ?? '背景洞察';
    final content = message.content.isNotEmpty
        ? message.content
        : (data['content'] as String? ?? '');

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildAvatar(),
          const SizedBox(width: 8),
          Flexible(
            child: Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.75,
              ),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.tertiaryContainer.withValues(alpha: 0.3),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: Theme.of(context).colorScheme.tertiary.withValues(alpha: 0.2),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        Icons.lightbulb_outline,
                        size: 14,
                        color: Theme.of(context).colorScheme.tertiary,
                      ),
                      const SizedBox(width: 6),
                      Text(
                        title,
                        style: AppTextStyles.caption.copyWith(
                          color: Theme.of(context).colorScheme.tertiary,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                  if (content.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    MarkdownBubbleContent(
                      content: content,
                      isUser: false,
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Route by explicit card_type field from backend.
  Widget? _routeByCardType(String cardType) {
    switch (cardType) {
      case 'gift':
      case 'recommend_gift':
        return GiftRecommendationBubble(
          message: message,
          onRegenerate: widget.onRegenerate,
          onFeedback: widget.onFeedback,
          onQuickAction: widget.onQuickAction,
        );
      case 'travel':
      case 'trip_itinerary':
      case 'plan_smart_trip':
        return TripBubble(
          message: message,
          onRegenerate: widget.onRegenerate,
          onFeedback: widget.onFeedback,
          onConfirmPlan: widget.onConfirmTravelPlan,
          onQuickAction: widget.onQuickAction,
        );
      case 'pending_action':
        return PendingActionBubble(
          message: message,
          onRegenerate: widget.onRegenerate,
          onFeedback: widget.onFeedback,
        );
      case 'ask_user_question':
        return AskUserQuestionBubble(
          message: message,
          onSubmitAnswer: null,
        );
      case 'event':
      case 'event_card':
        return EventCardBubble(
          message: message,
          onRegenerate: widget.onRegenerate,
          onFeedback: widget.onFeedback,
          onQuickAction: widget.onQuickAction,
        );
      case 'task':
      case 'task_card':
        return TaskListBubble(
          message: message,
          onRegenerate: widget.onRegenerate,
          onFeedback: widget.onFeedback,
          onQuickAction: widget.onQuickAction,
        );
      case 'member_profile':
        return MemberProfileBubble(
          message: message,
          onRegenerate: widget.onRegenerate,
          onFeedback: widget.onFeedback,
          onQuickAction: widget.onQuickAction,
        );
      case 'upcoming_dates':
        return UpcomingDatesBubble(
          message: message,
          onRegenerate: widget.onRegenerate,
          onFeedback: widget.onFeedback,
          onQuickAction: widget.onQuickAction,
        );
      case 'favor_balance':
        return FavorBalanceBubble(
          message: message,
          onRegenerate: widget.onRegenerate,
          onFeedback: widget.onFeedback,
          onQuickAction: widget.onQuickAction,
        );
      default:
        return null; // Unknown card type, fall through to heuristics
    }
  }

  // ---------------------------------------------------------------------------
  // Intent detection
  // ---------------------------------------------------------------------------

  bool _isGiftRecommendation() {
    if (message.intent == 'recommend_gift') return true;
    final data = message.data;
    if (data != null) {
      final hasRecommendations = data['recommendations'] is List &&
          (data['recommendations'] as List).isNotEmpty;
      final hasMemberId = data['member_id'] != null;
      final hasMemberName = data['member_name'] != null;
      if (hasRecommendations && (hasMemberId || hasMemberName)) return true;
    }
    return false;
  }

  bool _isTravelPlan() {
    if (message.intent == 'trip_itinerary' ||
        message.intent == 'plan_smart_trip' ||
        message.intent == 'travel_plan' ||
        message.intent == 'travel_itinerary') {
      return true;
    }
    final data = message.data;
    if (data != null) {
      final hasDestination = data['destination'] != null;
      final hasItinerary = data['itinerary'] is List;
      final hasPeopleToMeet = data['people_to_meet'] is List;
      final hasTasks = data['tasks'] is List;
      final hasDurationDays = data['duration_days'] != null;
      final hasTripId = data['trip_id'] != null;
      if (hasDestination && (hasItinerary || hasPeopleToMeet || hasTasks || hasDurationDays || hasTripId)) {
        return true;
      }
    }
    return false;
  }

  bool _isAskUserQuestion() {
    return message.intent == 'ask_user_question';
  }

  bool _isPendingAction() {
    if (message.intent == 'confirmation_required' || message.intent == 'pending_action') {
      return true;
    }
    final data = message.data;
    if (data != null) {
      final hasActionId = data['action_id'] != null || data['id'] != null;
      final hasActionType = data['action_type'] != null;
      final hasDisplayTitle = data['display_title'] != null;
      if (hasActionId && (hasActionType || hasDisplayTitle)) return true;
    }
    return false;
  }

  bool _isEventCard() {
    if (message.intent == 'event_card') return true;
    final data = message.data;
    if (data != null) {
      if (data['events'] is List && (data['events'] as List).isNotEmpty) return true;
      final hasEventTitle = data['event_title'] != null;
      final hasStartTime = data['start_time'] != null;
      if (hasEventTitle && hasStartTime) return true;
    }
    return false;
  }

  bool _isTaskCard() {
    if (message.intent == 'task_card') return true;
    final data = message.data;
    if (data != null) {
      if (data['tasks'] is List && (data['tasks'] as List).isNotEmpty) {
        final firstTask = (data['tasks'] as List).first;
        if (firstTask is Map && (firstTask['title'] != null || firstTask['task_title'] != null)) {
          return true;
        }
      }
    }
    return false;
  }

  bool _isMemberProfile() {
    if (message.intent == 'member_profile') return true;
    final data = message.data;
    if (data != null) {
      if (data['members'] is List && (data['members'] as List).isNotEmpty) return true;
      final hasMemberName = data['member_name'] != null || data['name'] != null;
      final hasRelation = data['relation'] != null;
      if (hasMemberName && hasRelation) return true;
    }
    return false;
  }

  bool _isUpcomingDates() {
    if (message.intent == 'upcoming_dates') return true;
    final data = message.data;
    if (data != null) {
      if (data['dates'] is List && (data['dates'] as List).isNotEmpty) return true;
      if (data['upcoming_dates'] is List && (data['upcoming_dates'] as List).isNotEmpty) return true;
    }
    return false;
  }

  bool _isFavorBalance() {
    if (message.intent == 'favor_balance') return true;
    final data = message.data;
    if (data != null) {
      final hasReceived = data['total_received'] != null || data['received_count'] != null;
      final hasGiven = data['total_given'] != null || data['given_count'] != null;
      if (hasReceived && hasGiven) return true;
      if (data['records'] is List || data['recent_records'] is List) {
        final hasFavorType = data['favor_type'] != null;
        if (hasFavorType) return true;
      }
    }
    return false;
  }

  // ---------------------------------------------------------------------------
  // Avatars
  // ---------------------------------------------------------------------------

  Widget _buildAvatar() {
    return Container(
      width: 32,
      height: 32,
      decoration: BoxDecoration(
        color: AppColors.primary.withValues(alpha: 0.15),
        shape: BoxShape.circle,
      ),
      child: const Center(
        child: Icon(Icons.auto_awesome, color: AppColors.primary, size: 16),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Legacy tool executions section (for historical messages without generationSteps)
  // ---------------------------------------------------------------------------

  Widget _buildToolExecutionsSection() {
    final allToolExecutions = message.toolExecutions!;
    final completedTools = allToolExecutions.where((t) =>
      t.status == 'success' || t.status == 'error'
    ).toList();
    if (completedTools.isEmpty) return const SizedBox.shrink();

    final toolCount = completedTools.length;
    final successCount = completedTools.where((t) => t.status == 'success').length;

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              InkWell(
                onTap: () {
                  setState(() => _toolsExpanded = !_toolsExpanded);
                },
                borderRadius: BorderRadius.circular(12),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.blue.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        successCount == toolCount
                            ? Icons.build_circle_outlined
                            : Icons.warning_amber_rounded,
                        size: 14,
                        color: successCount == toolCount
                            ? Colors.blue.shade600
                            : Colors.orange.shade600,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        '执行了 $toolCount 个工具',
                        style: AppTextStyles.caption.copyWith(
                          color: Colors.blue.shade700,
                          fontWeight: FontWeight.w500,
                          fontSize: 12,
                        ),
                      ),
                      const SizedBox(width: 2),
                      Icon(
                        _toolsExpanded
                            ? Icons.keyboard_arrow_up
                            : Icons.keyboard_arrow_down,
                        size: 14,
                        color: Colors.blue.shade500,
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
          AnimatedCrossFade(
            firstChild: const SizedBox.shrink(),
            secondChild: Container(
              margin: const EdgeInsets.only(top: 8),
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.05),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.1),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: completedTools.asMap().entries.map((entry) {
                  final index = entry.key;
                  final tool = entry.value;
                  final isExpanded = _expandedToolIndices.contains(index);
                  final hasKeyResults = tool.keyResults != null && tool.keyResults!.isNotEmpty;
                  final isSuccess = tool.status == 'success';

                  return Container(
                    margin: EdgeInsets.only(bottom: index < completedTools.length - 1 ? 6 : 0),
                    child: InkWell(
                      onTap: hasKeyResults ? () {
                        setState(() {
                          if (isExpanded) {
                            _expandedToolIndices.remove(index);
                          } else {
                            _expandedToolIndices.add(index);
                          }
                        });
                      } : null,
                      borderRadius: BorderRadius.circular(6),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Container(
                                width: 18,
                                height: 18,
                                decoration: BoxDecoration(
                                  color: isSuccess
                                      ? Colors.green.withValues(alpha: 0.1)
                                      : Colors.red.withValues(alpha: 0.1),
                                  borderRadius: BorderRadius.circular(9),
                                ),
                                child: Icon(
                                  isSuccess ? Icons.check : Icons.close,
                                  size: 12,
                                  color: isSuccess ? AppColors.success : AppColors.error,
                                ),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  getToolDisplayName(tool.toolName),
                                  style: AppTextStyles.caption.copyWith(
                                    color: Theme.of(context).colorScheme.onSurface,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              ),
                              if (hasKeyResults)
                                Icon(
                                  isExpanded
                                      ? Icons.keyboard_arrow_up
                                      : Icons.keyboard_arrow_down,
                                  size: 16,
                                  color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
                                ),
                            ],
                          ),
                          if (tool.summary != null && tool.summary!.isNotEmpty) ...[
                            const SizedBox(height: 2),
                            Padding(
                              padding: const EdgeInsets.only(left: 26),
                              child: Text(
                                tool.summary!,
                                maxLines: isExpanded ? null : 1,
                                overflow: isExpanded ? null : TextOverflow.ellipsis,
                                style: AppTextStyles.overline.copyWith(
                                  color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
                                  fontSize: 11,
                                ),
                              ),
                            ),
                          ],
                          if (hasKeyResults)
                            AnimatedCrossFade(
                              firstChild: const SizedBox.shrink(),
                              secondChild: Container(
                                width: double.infinity,
                                margin: const EdgeInsets.only(top: 6, left: 26),
                                padding: const EdgeInsets.all(8),
                                decoration: BoxDecoration(
                                  color: Theme.of(context).colorScheme.surface,
                                  borderRadius: BorderRadius.circular(4),
                                  border: Border.all(
                                    color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.15),
                                  ),
                                ),
                                child: KeyResultsDisplay(keyResults: tool.keyResults!),
                              ),
                              crossFadeState: isExpanded
                                  ? CrossFadeState.showSecond
                                  : CrossFadeState.showFirst,
                              duration: const Duration(milliseconds: 150),
                            ),
                        ],
                      ),
                    ),
                  );
                }).toList(),
              ),
            ),
            crossFadeState: _toolsExpanded
                ? CrossFadeState.showSecond
                : CrossFadeState.showFirst,
            duration: const Duration(milliseconds: 200),
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Legacy thinking section
  // ---------------------------------------------------------------------------

  Widget _buildThinkingSection() {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.15),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InkWell(
            onTap: () {
              setState(() => _thinkingExpanded = !_thinkingExpanded);
            },
            borderRadius: const BorderRadius.vertical(top: Radius.circular(8)),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              child: Row(
                children: [
                  Icon(
                    Icons.psychology_outlined,
                    size: 14,
                    color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.7),
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      '思考过程',
                      style: AppTextStyles.caption.copyWith(
                        color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.8),
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                  Icon(
                    _thinkingExpanded
                        ? Icons.keyboard_arrow_up
                        : Icons.keyboard_arrow_down,
                    size: 18,
                    color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.6),
                  ),
                ],
              ),
            ),
          ),
          AnimatedCrossFade(
            firstChild: const SizedBox.shrink(),
            secondChild: Container(
              padding: const EdgeInsets.fromLTRB(10, 0, 10, 10),
              child: Text(
                message.thinking!,
                style: AppTextStyles.bodyText2.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                  height: 1.5,
                  fontSize: 13,
                ),
              ),
            ),
            crossFadeState: _thinkingExpanded
                ? CrossFadeState.showSecond
                : CrossFadeState.showFirst,
            duration: const Duration(milliseconds: 200),
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Typing indicator
  // ---------------------------------------------------------------------------

  Widget _buildTypingIndicator() {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(3, (index) {
        return Padding(
          padding: const EdgeInsets.symmetric(horizontal: 2),
          child: _TypingDot(delay: index * 200),
        );
      }),
    );
  }

  // ---------------------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------------------

  void _copyMessage(BuildContext context) {
    HapticFeedback.lightImpact();
    final textContent = message.content.replaceAllMapped(
      RegExp(r'\[([^\]]+)\]\(([^)]+)\)'),
      (match) => match.group(1) ?? '',
    );
    Clipboard.setData(ClipboardData(text: textContent));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Row(
          children: [
            Icon(Icons.check_circle, color: Colors.white, size: 18),
            SizedBox(width: 8),
            Text('已复制到剪贴板'),
          ],
        ),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        duration: const Duration(seconds: 2),
        margin: const EdgeInsets.all(16),
      ),
    );
  }

  void _showMessageActions(BuildContext context) {
    HapticFeedback.mediumImpact();
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (context) => Container(
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surface,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                margin: const EdgeInsets.only(top: 12),
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: Theme.of(context).dividerColor,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              ListTile(
                leading: const Icon(Icons.copy),
                title: const Text('复制'),
                onTap: () {
                  Clipboard.setData(ClipboardData(text: message.content));
                  Navigator.pop(context);
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: const Text('已复制到剪贴板'),
                      behavior: SnackBarBehavior.floating,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                  );
                },
              ),
              if (message.role == MessageRole.user &&
                  widget.onEdit != null &&
                  _isServerMessageId)
                ListTile(
                  leading: const Icon(Icons.edit),
                  title: const Text('编辑'),
                  onTap: () {
                    Navigator.pop(context);
                    _showEditDialog(context);
                  },
                ),
              if (message.role == MessageRole.assistant &&
                  widget.onRegenerate != null &&
                  _isServerMessageId)
                ListTile(
                  leading: const Icon(Icons.refresh),
                  title: const Text('重新生成'),
                  onTap: () {
                    Navigator.pop(context);
                    widget.onRegenerate?.call(message.id);
                  },
                ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }

  void _showEditDialog(BuildContext context) {
    final controller = TextEditingController(text: message.content);
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('编辑消息'),
        content: TextField(
          controller: controller,
          maxLines: null,
          decoration: const InputDecoration(
            hintText: '输入新的消息内容',
            border: OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () {
              final newContent = controller.text.trim();
              if (newContent.isNotEmpty && newContent != message.content) {
                widget.onEdit?.call(message.id, newContent);
              }
              Navigator.pop(context);
            },
            child: const Text('确定'),
          ),
        ],
      ),
    );
  }

  // Legacy tool display name uses shared utility from tool_display_names.dart
}

// ---------------------------------------------------------------------------
// Typing dot animation (private to this file)
// ---------------------------------------------------------------------------

class _TypingDot extends StatefulWidget {
  final int delay;

  const _TypingDot({required this.delay});

  @override
  State<_TypingDot> createState() => _TypingDotState();
}

class _TypingDotState extends State<_TypingDot> with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _animation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    );

    _animation = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
    );

    Future.delayed(Duration(milliseconds: widget.delay), () {
      if (mounted) {
        _controller.repeat(reverse: true);
      }
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _animation,
      builder: (context, child) {
        return Transform.translate(
          offset: Offset(0, -4 * _animation.value),
          child: child,
        );
      },
      child: Container(
        width: 8,
        height: 8,
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.6),
          shape: BoxShape.circle,
        ),
      ),
    );
  }
}
