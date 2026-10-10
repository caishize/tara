import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../data/models/insight_feed_models.dart';
import '../bloc/action_bloc.dart';
import '../bloc/action_event.dart' as action_events;
import '../bloc/insight_dismiss_bloc.dart';
import '../bloc/insight_dismiss_event.dart' as dismiss_events;
import '../bloc/insight_feed_bloc.dart';
import '../bloc/insight_feed_event.dart' as feed_events;
import '../bloc/insight_feed_state.dart';
import '../utils/insight_style.dart';
import '../widgets/insight_card_parts.dart';

/// PLAN-009: Email-style swipe triage mode for rapid insight processing.
///
/// Shows insights in a focused single-card view with enlarged swipe zones:
/// - Left swipe = dismiss
/// - Right swipe = primary action
/// - Progress indicator at top ("3/15 processed")
///
/// Uses existing InsightDismissBloc + ActionBloc for all mutations.
class InsightTriagePage extends StatefulWidget {
  const InsightTriagePage({super.key});

  @override
  State<InsightTriagePage> createState() => _InsightTriagePageState();
}

class _InsightTriagePageState extends State<InsightTriagePage> {
  int _processedCount = 0;
  int _currentIndex = 0;
  late List<InsightFeedItemModel> _insights;
  bool _initialized = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_initialized) {
      final feedState = context.read<InsightFeedBloc>().state;
      if (feedState is InsightFeedLoadedState) {
        // PLAN-002: Use allVisibleInsights so triage works in grouped mode
        _insights = List.from(feedState.allVisibleInsights);
      } else {
        _insights = [];
      }
      _initialized = true;
    }
  }

  InsightFeedItemModel? get _currentInsight {
    if (_currentIndex >= _insights.length) return null;
    return _insights[_currentIndex];
  }

  void _dismissCurrent() {
    final insight = _currentInsight;
    if (insight == null) return;

    HapticFeedback.mediumImpact();

    // Dispatch dismiss
    context.read<InsightDismissBloc>().add(
          dismiss_events.DismissInsight(
            insight: insight,
            originalIndex: _currentIndex,
          ),
        );
    context
        .read<InsightFeedBloc>()
        .add(feed_events.RemoveInsightFromFeed(insight.id));

    _advanceToNext();
  }

  void _actOnCurrent() {
    final insight = _currentInsight;
    if (insight == null) return;

    HapticFeedback.mediumImpact();

    // Primary action — extract canonical action_type from ActionOptionModel
    final primaryActionType = insight.actionOptions.isNotEmpty
        ? insight.actionOptions.first.actionType
        : insight.actionType;

    if (primaryActionType != null && primaryActionType.isNotEmpty) {
      context.read<ActionBloc>().add(action_events.RequestAction(
            insightId: insight.id,
            actionType: primaryActionType,
            actionData: insight.actionData,
          ));
    }

    _advanceToNext();
  }

  void _advanceToNext() {
    setState(() {
      _processedCount++;
      _currentIndex++;
    });
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final total = _insights.length;
    final insight = _currentInsight;

    return Scaffold(
      appBar: AppBar(
        title: Text(
          '\u5FEB\u901F\u5206\u62E3',
          style: TextStyle(
            fontSize: 17,
            fontWeight: FontWeight.w600,
            color: colorScheme.onSurface,
          ),
        ),
        centerTitle: true,
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: Column(
        children: [
          // Progress bar
          _TriageProgressBar(
            processed: _processedCount,
            total: total,
          ),
          // Content
          Expanded(
            child: insight == null
                ? _buildDoneState(context)
                : _buildTriageCard(context, insight),
          ),
          // Swipe hints
          if (insight != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 32),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: [
                  _SwipeHint(
                    icon: Icons.close,
                    label: '\u2190 \u5FFD\u7565',
                    color: colorScheme.error,
                  ),
                  Text(
                    '${_currentIndex + 1} / $total',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: colorScheme.onSurfaceVariant,
                    ),
                  ),
                  _SwipeHint(
                    icon: Icons.bolt,
                    label: '\u6267\u884C \u2192',
                    color: colorScheme.primary,
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildTriageCard(BuildContext context, InsightFeedItemModel insight) {
    final style = InsightStyle.resolve(
      context: context,
      insightType: insight.insightType,
      urgency: insight.urgency,
      visualWeight: insight.visualWeight,
      priority: insight.priority,
    );

    return Center(
      child: Dismissible(
        key: Key('triage-${insight.id}'),
        onDismissed: (direction) {
          if (direction == DismissDirection.endToStart) {
            _dismissCurrent();
          } else {
            _actOnCurrent();
          }
        },
        background: Container(
          alignment: Alignment.centerLeft,
          padding: const EdgeInsets.only(left: 32),
          color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.1),
          child: Icon(
            Icons.bolt,
            size: 32,
            color: Theme.of(context).colorScheme.primary,
          ),
        ),
        secondaryBackground: Container(
          alignment: Alignment.centerRight,
          padding: const EdgeInsets.only(right: 32),
          color: Theme.of(context).colorScheme.error.withValues(alpha: 0.1),
          child: Icon(
            Icons.close,
            size: 32,
            color: Theme.of(context).colorScheme.error,
          ),
        ),
        child: Container(
          width: double.infinity,
          margin: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: style.bgGradient,
            ),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: style.borderColor, width: 1.5),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Type badge
              Row(
                children: [
                  InsightUrgencyDot(urgency: insight.urgency),
                  const SizedBox(width: 8),
                  Text(
                    style.emoji,
                    style: const TextStyle(fontSize: 16),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    style.label,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                      color: style.accentColor,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              // Title
              Text(
                insight.title,
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: Theme.of(context).colorScheme.onSurface,
                  height: 1.3,
                ),
              ),
              const SizedBox(height: 10),
              // Content
              Text(
                insight.content,
                style: TextStyle(
                  fontSize: 15,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                  height: 1.6,
                ),
                maxLines: 6,
                overflow: TextOverflow.ellipsis,
              ),
              // Primary action indicator
              if (insight.actionOptions.isNotEmpty ||
                  insight.actionType != null) ...[
                const SizedBox(height: 16),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: style.accentColor.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.swipe, size: 14, color: style.accentColor),
                      const SizedBox(width: 6),
                      Text(
                        '\u53F3\u6ED1\u6267\u884C',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: style.accentColor,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildDoneState(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.check_circle_outline,
            size: 64,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(height: 16),
          Text(
            '\u5206\u62E3\u5B8C\u6210!',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w700,
              color: Theme.of(context).colorScheme.onSurface,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '\u5DF2\u5904\u7406 $_processedCount \u6761\u6D1E\u5BDF',
            style: TextStyle(
              fontSize: 15,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 24),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('\u8FD4\u56DE'),
          ),
        ],
      ),
    );
  }
}

class _TriageProgressBar extends StatelessWidget {
  final int processed;
  final int total;

  const _TriageProgressBar({required this.processed, required this.total});

  @override
  Widget build(BuildContext context) {
    final progress = total > 0 ? processed / total : 0.0;
    final colorScheme = Theme.of(context).colorScheme;

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '$processed / $total \u5DF2\u5904\u7406',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
              Text(
                '${(progress * 100).toInt()}%',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: colorScheme.primary,
                ),
              ),
            ],
          ),
        ),
        LinearProgressIndicator(
          value: progress,
          minHeight: 3,
          backgroundColor: colorScheme.surfaceContainerHighest,
          valueColor: AlwaysStoppedAnimation<Color>(colorScheme.primary),
        ),
      ],
    );
  }
}

class _SwipeHint extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;

  const _SwipeHint({
    required this.icon,
    required this.label,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 16, color: color.withValues(alpha: 0.6)),
        const SizedBox(width: 4),
        Text(
          label,
          style: TextStyle(
            fontSize: 12,
            color: color.withValues(alpha: 0.6),
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }
}
