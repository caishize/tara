import 'package:equatable/equatable.dart';

/// On-this-day item from a previous year
class OnThisDayItem extends Equatable {
  final String id;
  final String title;
  final String? eventType;
  final int year;
  final DateTime? startTime;
  final String? location;
  final String? notes;
  final String? tripId;
  final String? tripName;
  final String? coverImageUrl;
  final int participantCount;
  final int durationDays;
  final List<String> memorySummaries;

  const OnThisDayItem({
    required this.id,
    required this.title,
    this.eventType,
    required this.year,
    this.startTime,
    this.location,
    this.notes,
    this.tripId,
    this.tripName,
    this.coverImageUrl,
    this.participantCount = 0,
    this.durationDays = 1,
    this.memorySummaries = const [],
  });

  int get yearsAgo => DateTime.now().year - year;

  String get typeIcon {
    switch (eventType) {
      case 'business_trip':
        return '\u{1F4BC}';
      case 'travel':
        return '\u{2708}\u{FE0F}';
      case 'meeting':
        return '\u{1F91D}';
      case 'birthday':
        return '\u{1F382}';
      case 'anniversary':
        return '\u{1F491}';
      case 'holiday':
        return '\u{1F389}';
      default:
        return '\u{1F4CC}';
    }
  }

  @override
  List<Object?> get props => [
    id, title, eventType, year, startTime, location, notes, tripId,
    tripName, coverImageUrl, participantCount, durationDays, memorySummaries,
  ];
}

/// Response wrapper for on-this-day
class OnThisDayResponse extends Equatable {
  final List<OnThisDayItem> items;
  final int month;
  final int day;

  const OnThisDayResponse({
    required this.items,
    required this.month,
    required this.day,
  });

  @override
  List<Object?> get props => [items, month, day];
}

/// A participant in a story (for avatar display)
class StoryParticipant extends Equatable {
  final String name;
  final String? avatarColor; // hex color string

  const StoryParticipant({required this.name, this.avatarColor});

  @override
  List<Object?> get props => [name, avatarColor];
}

/// A single event within a story group (reuses backend KanbanEvent shape)
class StoryEvent extends Equatable {
  final String id;
  final String title;
  final String? eventType;
  final DateTime? startTime;
  final DateTime? endTime;
  final String? location;
  final String? status;
  final String? priority;
  final String? notes;
  final String? tripId;
  final String? tripName;
  final String? speaker;
  final List<String> photoUrls;
  final String? secretaryNote;
  final bool isPinned;

  const StoryEvent({
    required this.id,
    required this.title,
    this.eventType,
    this.startTime,
    this.endTime,
    this.location,
    this.status,
    this.priority,
    this.notes,
    this.tripId,
    this.tripName,
    this.speaker,
    this.photoUrls = const [],
    this.secretaryNote,
    this.isPinned = false,
  });

  String get typeIcon {
    switch (eventType) {
      case 'business_trip':
        return '\u{1F4BC}';
      case 'travel':
        return '\u{2708}\u{FE0F}';
      case 'meeting':
        return '\u{1F91D}';
      case 'birthday':
        return '\u{1F382}';
      case 'anniversary':
        return '\u{1F491}';
      case 'holiday':
        return '\u{1F389}';
      default:
        return '\u{1F4CC}';
    }
  }

  bool get isTravel => eventType == 'travel' || eventType == 'business_trip';

  int get durationDays {
    if (endTime == null || startTime == null) return 1;
    return endTime!.difference(startTime!).inDays + 1;
  }

  @override
  List<Object?> get props => [id, title, eventType, startTime, endTime, location, status, priority, notes, tripId, tripName, speaker, photoUrls, secretaryNote, isPinned];
}

/// A group of related events forming a "story" (e.g. a trip)
class StoryGroup extends Equatable {
  final String? tripId;
  final String title;
  final List<StoryEvent> events;
  final List<String> memorySummaries;
  final DateTime? startDate;
  final DateTime? endDate;
  final int participantCount;
  final List<StoryParticipant> participants;
  final String? emotionalTag;

  const StoryGroup({
    this.tripId,
    required this.title,
    required this.events,
    this.memorySummaries = const [],
    this.startDate,
    this.endDate,
    this.participantCount = 0,
    this.participants = const [],
    this.emotionalTag,
  });

  bool get isTrip => tripId != null;

  int get durationDays {
    if (startDate == null || endDate == null) return 1;
    return endDate!.difference(startDate!).inDays + 1;
  }

  /// Extract unique locations from events
  List<String> get locations {
    return events
        .where((e) => e.location != null && e.location!.isNotEmpty)
        .map((e) => e.location!)
        .toSet()
        .toList();
  }

  String get typeIcon {
    if (isTrip) {
      final firstType = events.isNotEmpty ? events.first.eventType : null;
      return firstType == 'business_trip' ? '\u{1F4BC}' : '\u{2708}\u{FE0F}';
    }
    if (events.isNotEmpty) return events.first.typeIcon;
    return '\u{1F4CC}';
  }

  @override
  List<Object?> get props => [tripId, title, events, memorySummaries, startDate, endDate, participantCount, participants, emotionalTag];
}

/// Yearly group containing stories
class YearlySummary extends Equatable {
  final int year;
  final List<StoryGroup> stories;
  final int eventCount;

  const YearlySummary({
    required this.year,
    this.stories = const [],
    this.eventCount = 0,
  });

  int get tripCount => stories.where((s) => s.isTrip).length;

  int get specialDayCount => stories
      .where((s) => !s.isTrip)
      .expand((s) => s.events)
      .where((e) =>
          e.eventType == 'birthday' ||
          e.eventType == 'anniversary' ||
          e.eventType == 'holiday')
      .length;

  @override
  List<Object?> get props => [year, stories, eventCount];
}

/// Top-level response for memory lane
class MemoryLaneResponse extends Equatable {
  final List<YearlySummary> years;
  final int totalEvents;

  const MemoryLaneResponse({
    this.years = const [],
    this.totalEvents = 0,
  });

  /// Recent stories across all years (for the top section)
  List<StoryGroup> get recentStories {
    final all = <StoryGroup>[];
    for (final year in years) {
      all.addAll(year.stories);
    }
    // Already sorted desc by backend
    return all.take(5).toList();
  }

  @override
  List<Object?> get props => [years, totalEvents];
}
