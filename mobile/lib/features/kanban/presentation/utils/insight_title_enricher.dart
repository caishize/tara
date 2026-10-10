import '../../data/models/insight_feed_models.dart';

/// Pure utility for enriching mechanical backend titles with member context.
///
/// Transforms template titles like "妈妈生日的准备建议" into contextual titles
/// like "妈妈 — 还有3天" using data already present in [InsightFeedItemModel].
abstract final class InsightTitleEnricher {
  /// Returns an enriched title using member + event context when available.
  ///
  /// Enrichment priority:
  /// 1. Member name + countdown: "妈妈 — 还有3天"
  /// 2. Member name + type label: "妈妈的提醒"
  /// 3. Fallback: original [insight.title]
  static String enrich(InsightFeedItemModel insight) {
    if (insight.relatedMembers.isEmpty) return insight.title;

    final member = insight.relatedMembers.first;
    if (member.name.isEmpty) return insight.title;

    // Path 1: Member + countdown: "妈妈 — 还有3天"
    final daysUntil = _daysUntilNextEvent(insight);
    if (daysUntil != null && daysUntil >= 0) {
      final countdown = _formatCountdown(daysUntil);
      final enriched = '${member.name} — $countdown';
      if (enriched.length <= 26) return enriched;
    }

    // Path 2: Member + type label: "妈妈的提醒"
    final typeLabel = _typeLabel(insight.insightType);
    if (typeLabel != null) {
      final enriched = '${member.name}\u7684$typeLabel';
      if (enriched.length <= 26) return enriched;
    }

    return insight.title;
  }

  /// Computes days until the first related event's start time.
  /// Returns null if no event has a start time.
  static int? _daysUntilNextEvent(InsightFeedItemModel insight) {
    if (insight.relatedEvents.isEmpty) return null;
    final startTime = insight.relatedEvents.first.startTime;
    if (startTime == null) return null;

    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final eventDay = DateTime(startTime.year, startTime.month, startTime.day);
    return eventDay.difference(today).inDays;
  }

  /// Maps insight type to a short Chinese label for path 2 enrichment.
  static String? _typeLabel(String insightType) => switch (insightType) {
    'reminder' || 'favor_reminder' => '\u63D0\u9192',
    'suggestion' => '\u5EFA\u8BAE',
    'observation' || 'pattern_observation' => '\u89C2\u5BDF',
    'correlation' || 'relationship_maintenance' => '\u5173\u8054',
    'event_preparation' => '\u51C6\u5907',
    'followup' => '\u8DDF\u8FDB',
    _ => null,
  };

  static String _formatCountdown(int days) {
    if (days == 0) return '就是今天';
    if (days == 1) return '明天';
    if (days < 7) return '还有$days天';
    if (days < 30) return '还有${(days / 7).floor()}周';
    return '还有${(days / 30).floor()}个月';
  }
}
