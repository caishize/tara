import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../../../app/theme/app_colors.dart';
import '../../domain/entities/memory_lane.dart';

/// Trip memory detail page (回忆详情页).
/// Displays a past trip as a narrative story with day-by-day timeline,
/// participant avatars, quotes with speaker attribution, secretary notes,
/// photo placeholders, and pinned quotes.
class TripMemoryPage extends StatelessWidget {
  final StoryGroup story;

  const TripMemoryPage({super.key, required this.story});

  static const _avatarColors = [
    AppColors.accentGreen,
    AppColors.accentWarm,
    AppColors.avatarGold,
    AppColors.avatarIndigo,
    AppColors.avatarPink,
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: Column(
        children: [
          Expanded(
            child: CustomScrollView(
              slivers: [
                SliverToBoxAdapter(child: _buildStatusBarSpacer(context)),
                SliverToBoxAdapter(child: _buildHeader(context)),
                SliverToBoxAdapter(child: _buildHeroArea()),
                SliverToBoxAdapter(child: _buildContent()),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatusBarSpacer(BuildContext context) {
    return SizedBox(height: MediaQuery.of(context).padding.top);
  }

  // ---------------------------------------------------------------------------
  // Header: back arrow + title + share icon
  // ---------------------------------------------------------------------------

  Widget _buildHeader(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: SizedBox(
        height: 48,
        child: Row(
          children: [
            GestureDetector(
              onTap: () => Navigator.of(context).pop(),
              child: const Icon(
                Icons.arrow_back,
                size: 24,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                story.title,
                style: const TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            const Icon(
              Icons.share_outlined,
              size: 22,
              color: AppColors.textSecondary,
            ),
          ],
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Hero area: warm brown background with title, subtitle, quote
  // ---------------------------------------------------------------------------

  Widget _buildHeroArea() {
    return Container(
      height: 180,
      width: double.infinity,
      color: const Color(0xFFD4B5A0),
      child: Stack(
        children: [
          Positioned.fill(
            child: Container(
              color: const Color(0x4D000000),
            ),
          ),
          Positioned(
            left: 20,
            right: 20,
            bottom: 16,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  story.title,
                  style: const TextStyle(
                    fontSize: 26,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  _buildHeroSubtitle(),
                  style: const TextStyle(
                    fontSize: 13,
                    color: Color(0xCCFFFFFF),
                  ),
                ),
                if (story.memorySummaries.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(
                    '\u300C${story.memorySummaries.first}\u300D',
                    style: const TextStyle(
                      fontSize: 12,
                      color: Color(0xAAFFFFFF),
                      height: 1.4,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _buildHeroSubtitle() {
    final parts = <String>[];

    if (story.startDate != null) {
      final start = DateFormat('yyyy\u5E74M\u6708d\u65E5')
          .format(story.startDate!);
      if (story.endDate != null && story.startDate != story.endDate) {
        final end = DateFormat('d\u65E5').format(story.endDate!);
        parts.add('$start - $end');
      } else {
        parts.add(start);
      }
    }

    if (story.participantCount > 0) {
      parts.add('${story.participantCount}\u4EBA');
    }

    if (story.durationDays > 1) {
      parts.add('${story.durationDays}\u5929');
    }

    return parts.join(' \u00B7 ');
  }

  // ---------------------------------------------------------------------------
  // Main content: people row, day cards, summary, related links
  // ---------------------------------------------------------------------------

  Widget _buildContent() {
    final dayGroups = _groupEventsByDay();

    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // People row
          if (story.participants.isNotEmpty) ...[
            _buildPeopleRow(),
            const SizedBox(height: 16),
          ],

          // Day cards
          ...dayGroups.entries.map(
            (entry) => Padding(
              padding: const EdgeInsets.only(bottom: 14),
              child: _buildDayCard(entry.key, entry.value),
            ),
          ),

          // Summary card
          if (story.memorySummaries.length > 1) ...[
            _buildSummaryCard(),
            const SizedBox(height: 14),
          ],

          // Related links
          _buildRelatedLinks(),

          const SizedBox(height: 24),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // People row: circular avatars with names
  // ---------------------------------------------------------------------------

  Widget _buildPeopleRow() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '\u540C\u884C\u4EBA',
          style: TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w600,
            color: AppColors.textSecondary,
          ),
        ),
        const SizedBox(height: 8),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: story.participants.asMap().entries.map((entry) {
              final color = _avatarColors[entry.key % _avatarColors.length];
              final participant = entry.value;
              return Padding(
                padding: const EdgeInsets.only(right: 14),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 36,
                      height: 36,
                      decoration: BoxDecoration(
                        color: participant.avatarColor != null
                            ? _parseColor(participant.avatarColor!)
                            : color,
                        shape: BoxShape.circle,
                      ),
                      alignment: Alignment.center,
                      child: Text(
                        participant.name.isNotEmpty
                            ? participant.name.substring(0, 1)
                            : '',
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: Colors.white,
                        ),
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      participant.name,
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ],
                ),
              );
            }).toList(),
          ),
        ),
      ],
    );
  }

  Color _parseColor(String hex) {
    final cleaned = hex.replaceFirst('#', '');
    if (cleaned.length == 6) {
      return Color(int.parse('FF$cleaned', radix: 16));
    }
    return AppColors.accentGreen;
  }

  // ---------------------------------------------------------------------------
  // Day card: date header + activity lines + photos + quotes + secretary notes
  // ---------------------------------------------------------------------------

  Widget _buildDayCard(String dayLabel, List<StoryEvent> events) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            dayLabel,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: AppColors.accentWarm,
            ),
          ),
          const SizedBox(height: 8),
          ...events.map((event) => _buildEventLines(event)),
        ],
      ),
    );
  }

  Widget _buildEventLines(StoryEvent event) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Pinned quote
        if (event.isPinned && event.notes != null) ...[
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('\uD83D\uDCCC', style: TextStyle(fontSize: 13)),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  event.notes!,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
        ],

        // Activity line
        Row(
          children: [
            Text(
              event.typeIcon,
              style: const TextStyle(fontSize: 13),
            ),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                _buildActivityText(event),
                style: const TextStyle(
                  fontSize: 13,
                  color: AppColors.textPrimary,
                ),
              ),
            ),
          ],
        ),

        // Photo thumbnails
        if (event.photoUrls.isNotEmpty) ...[
          const SizedBox(height: 8),
          SizedBox(
            height: 60,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              itemCount: event.photoUrls.length,
              itemBuilder: (_, i) => Container(
                width: 60,
                height: 60,
                margin: const EdgeInsets.only(right: 6),
                decoration: BoxDecoration(
                  color: AppColors.bgMuted,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.image_outlined,
                  size: 24,
                  color: AppColors.textTertiary,
                ),
              ),
            ),
          ),
        ],

        // Quote/notes with speaker attribution
        if (event.notes != null &&
            event.notes!.isNotEmpty &&
            !event.isPinned) ...[
          const SizedBox(height: 6),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('\uD83D\uDCAC', style: TextStyle(fontSize: 13)),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  event.speaker != null
                      ? '${event.speaker}\u8BF4\uFF1A\u300C${event.notes!}\u300D'
                      : event.notes!,
                  style: const TextStyle(
                    fontSize: 13,
                    color: AppColors.textSecondary,
                    height: 1.5,
                  ),
                ),
              ),
            ],
          ),
        ],

        // Secretary note
        if (event.secretaryNote != null &&
            event.secretaryNote!.isNotEmpty) ...[
          const SizedBox(height: 6),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('\uD83E\uDD16', style: TextStyle(fontSize: 13)),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  event.secretaryNote!,
                  style: const TextStyle(
                    fontSize: 13,
                    color: AppColors.accentGreen,
                    height: 1.5,
                  ),
                ),
              ),
            ],
          ),
        ],

        const SizedBox(height: 6),
      ],
    );
  }

  String _buildActivityText(StoryEvent event) {
    final parts = <String>[event.title];
    if (event.location != null && event.location!.isNotEmpty) {
      if (!event.title.contains(event.location!)) {
        parts.add(event.location!);
      }
    }
    return parts.join(' \u00B7 ');
  }

  // ---------------------------------------------------------------------------
  // Summary card: secretary's recap
  // ---------------------------------------------------------------------------

  Widget _buildSummaryCard() {
    final summaryText = story.memorySummaries.length > 1
        ? story.memorySummaries.sublist(1).join('\n')
        : '';

    if (summaryText.isEmpty) return const SizedBox.shrink();

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: AppColors.accentWarmLight,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '\uD83D\uDCDD \u79D8\u4E66\u7684\u5C0F\u7ED3',
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w700,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            summaryText,
            style: const TextStyle(
              fontSize: 13,
              color: AppColors.textPrimary,
              height: 1.6,
            ),
          ),
          const SizedBox(height: 10),
          SizedBox(
            width: double.infinity,
            height: 36,
            child: ElevatedButton(
              onPressed: () {
                // TODO: navigate to plan next trip
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.accentWarm,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(20),
                ),
                elevation: 0,
                padding: EdgeInsets.zero,
              ),
              child: Text(
                '\u660E\u5E74\u518D\u53BB${story.locations.isNotEmpty ? story.locations.first : ""}',
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Related links
  // ---------------------------------------------------------------------------

  Widget _buildRelatedLinks() {
    final links = <String>[];

    for (final loc in story.locations.take(2)) {
      links.add(loc);
    }

    if (links.isEmpty) {
      for (final event in story.events.take(2)) {
        if (event.notes != null && event.notes!.isNotEmpty) {
          links.add(event.notes!);
        }
      }
    }

    if (links.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '\u76F8\u5173\u7684\u4E8B',
          style: TextStyle(
            fontSize: 12,
            color: AppColors.textTertiary,
          ),
        ),
        const SizedBox(height: 6),
        ...links.map((text) => Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Row(
                children: [
                  const Text(
                    '\u00B7',
                    style: TextStyle(
                      fontSize: 14,
                      color: AppColors.textTertiary,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      text,
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppColors.accentGreen,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            )),
      ],
    );
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  Map<String, List<StoryEvent>> _groupEventsByDay() {
    final groups = <String, List<StoryEvent>>{};

    if (story.events.isEmpty) return groups;

    for (final event in story.events) {
      String dayLabel;
      if (event.startTime != null) {
        final date = event.startTime!.toLocal();
        dayLabel = '${date.month}\u6708${date.day}\u65E5';
        if (event.location != null && event.location!.isNotEmpty) {
          dayLabel += ' \u00B7 ${event.location!}';
        }
      } else {
        dayLabel = event.title;
      }

      groups.putIfAbsent(dayLabel, () => []).add(event);
    }

    return groups;
  }
}
