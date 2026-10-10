/// Barrel file for shared business card widgets.
///
/// These widgets are used by both the chat and kanban features.
/// Currently they live in `features/chat/presentation/widgets/` and are
/// re-exported here so other features can import from a shared location.
library cards;

export '../../../features/chat/presentation/widgets/briefing_message_card.dart';
export '../../../features/chat/presentation/widgets/trip_bubble.dart';
export '../../../features/chat/presentation/widgets/gift_recommendation_bubble.dart';
export '../../../features/chat/presentation/widgets/ask_user_question_bubble.dart';
export '../../../features/chat/presentation/widgets/pending_action_bubble.dart';
export '../../../features/chat/presentation/widgets/event_card_bubble.dart';
export '../../../features/chat/presentation/widgets/task_list_bubble.dart';
export '../../../features/chat/presentation/widgets/card_quick_actions.dart';
export '../../../features/chat/presentation/widgets/markdown_bubble.dart';
export 'graph_preview_card.dart';
export 'reminder_card.dart';
