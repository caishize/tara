/// Summary of an associated event linked to a trip.
class AssociationSummaryModel {
  final String id;
  final String eventType;
  final String title;
  final String? reason;
  final String priority;
  final String? icon;

  const AssociationSummaryModel({
    required this.id,
    required this.eventType,
    required this.title,
    this.reason,
    this.priority = 'normal',
    this.icon,
  });

  factory AssociationSummaryModel.fromJson(Map<String, dynamic> json) {
    return AssociationSummaryModel(
      id: json['id'] as String? ?? '',
      eventType: json['event_type'] as String? ?? '',
      title: json['title'] as String? ?? '',
      reason: json['reason'] as String?,
      priority: json['priority'] as String? ?? 'normal',
      icon: json['icon'] as String?,
    );
  }

  String get displayIcon {
    if (icon != null && icon!.isNotEmpty) return icon!;
    switch (eventType) {
      case 'birthday':
        return '🎂';
      case 'anniversary':
        return '💍';
      case 'meeting':
        return '📅';
      case 'holiday':
        return '🎉';
      case 'travel':
        return '✈️';
      default:
        return '🔗';
    }
  }

  String get priorityLabel {
    switch (priority) {
      case 'high':
        return '高';
      case 'medium':
        return '中';
      default:
        return '低';
    }
  }
}
