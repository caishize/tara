import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';
import '../../data/datasources/relationship_remote_datasource.dart';

// Events
abstract class SmartGroupsEvent extends Equatable {
  const SmartGroupsEvent();
  @override
  List<Object?> get props => [];
}

class SmartGroupsLoadRequested extends SmartGroupsEvent {
  const SmartGroupsLoadRequested();
}

class SmartGroupsRefreshRequested extends SmartGroupsEvent {
  const SmartGroupsRefreshRequested();
}

class SmartGroupDetailRequested extends SmartGroupsEvent {
  final String groupKey;
  const SmartGroupDetailRequested({required this.groupKey});
  @override
  List<Object?> get props => [groupKey];
}

// States
abstract class SmartGroupsState extends Equatable {
  const SmartGroupsState();
  @override
  List<Object?> get props => [];
}

class SmartGroupsInitial extends SmartGroupsState {
  const SmartGroupsInitial();
}

class SmartGroupsLoading extends SmartGroupsState {
  const SmartGroupsLoading();
}

class SmartGroupsLoaded extends SmartGroupsState {
  final List<SmartGroup> groups;
  final SmartGroupDetail? selectedGroupDetail;

  const SmartGroupsLoaded({
    required this.groups,
    this.selectedGroupDetail,
  });

  int get totalMembers => groups.fold(0, (sum, g) => sum + g.memberCount);

  SmartGroup? get needsAttentionGroup =>
      groups.where((g) => g.key == 'needs_attention').firstOrNull;

  SmartGroupsLoaded copyWith({
    List<SmartGroup>? groups,
    SmartGroupDetail? selectedGroupDetail,
  }) {
    return SmartGroupsLoaded(
      groups: groups ?? this.groups,
      selectedGroupDetail: selectedGroupDetail ?? this.selectedGroupDetail,
    );
  }

  @override
  List<Object?> get props => [groups, selectedGroupDetail];
}

class SmartGroupsError extends SmartGroupsState {
  final String message;
  const SmartGroupsError(this.message);
  @override
  List<Object?> get props => [message];
}

// Models
class SmartGroup {
  final String key;
  final String name;
  final IconData icon;
  final String description;
  final Color color;
  final int memberCount;
  final List<GroupMemberPreview> previewMembers;

  const SmartGroup({
    required this.key,
    required this.name,
    required this.icon,
    required this.description,
    required this.color,
    required this.memberCount,
    required this.previewMembers,
  });

  factory SmartGroup.fromJson(Map<String, dynamic> json) {
    return SmartGroup(
      key: json['key'] ?? '',
      name: json['name'] ?? '',
      icon: _iconFromString(json['icon'] ?? 'group'),
      description: json['description'] ?? '',
      color: _colorFromHex(json['color'] ?? '#6B7280'),
      memberCount: json['member_count'] ?? 0,
      previewMembers: ((json['preview_members'] ?? []) as List)
          .map((m) => GroupMemberPreview.fromJson(m as Map<String, dynamic>))
          .toList(),
    );
  }

  static IconData _iconFromString(String iconName) {
    switch (iconName) {
      case 'warning':
        return Icons.warning_amber;
      case 'cake':
        return Icons.cake;
      case 'phone':
        return Icons.phone;
      case 'handshake':
        return Icons.handshake;
      case 'elderly':
        return Icons.elderly;
      case 'star':
        return Icons.star;
      case 'person_add':
        return Icons.person_add;
      default:
        return Icons.group;
    }
  }

  static Color _colorFromHex(String hexColor) {
    hexColor = hexColor.replaceAll('#', '');
    if (hexColor.length == 6) {
      hexColor = 'FF$hexColor';
    }
    return Color(int.parse(hexColor, radix: 16));
  }
}

class GroupMemberPreview {
  final String id;
  final String name;
  final String? avatar;

  const GroupMemberPreview({
    required this.id,
    required this.name,
    this.avatar,
  });

  factory GroupMemberPreview.fromJson(Map<String, dynamic> json) {
    return GroupMemberPreview(
      id: json['id']?.toString() ?? '',
      name: json['name'] ?? '',
      avatar: json['avatar'],
    );
  }
}

class SmartGroupDetail {
  final String key;
  final String name;
  final IconData icon;
  final String description;
  final Color color;
  final int memberCount;
  final List<GroupMember> members;

  const SmartGroupDetail({
    required this.key,
    required this.name,
    required this.icon,
    required this.description,
    required this.color,
    required this.memberCount,
    required this.members,
  });

  factory SmartGroupDetail.fromJson(Map<String, dynamic> json) {
    return SmartGroupDetail(
      key: json['key'] ?? '',
      name: json['name'] ?? '',
      icon: SmartGroup._iconFromString(json['icon'] ?? 'group'),
      description: json['description'] ?? '',
      color: SmartGroup._colorFromHex(json['color'] ?? '#6B7280'),
      memberCount: json['member_count'] ?? 0,
      members: ((json['members'] ?? []) as List)
          .map((m) => GroupMember.fromJson(m as Map<String, dynamic>))
          .toList(),
    );
  }
}

class GroupMember {
  final String id;
  final String name;
  final String? fullName;
  final String? avatar;
  final String? relationType;
  final String? phone;
  final int? lastInteractionDays;
  final String? birthday;

  const GroupMember({
    required this.id,
    required this.name,
    this.fullName,
    this.avatar,
    this.relationType,
    this.phone,
    this.lastInteractionDays,
    this.birthday,
  });

  factory GroupMember.fromJson(Map<String, dynamic> json) {
    return GroupMember(
      id: json['id']?.toString() ?? '',
      name: json['name'] ?? '',
      fullName: json['full_name'],
      avatar: json['avatar'],
      relationType: json['relation_type'],
      phone: json['phone'],
      lastInteractionDays: json['last_interaction_days'],
      birthday: json['birthday'],
    );
  }
}

class DailyReminder {
  final String type;
  final String memberId;
  final String memberName;
  final int daysUntil;
  final String title;
  final String body;
  final String priority;

  const DailyReminder({
    required this.type,
    required this.memberId,
    required this.memberName,
    required this.daysUntil,
    required this.title,
    required this.body,
    required this.priority,
  });

  factory DailyReminder.fromJson(Map<String, dynamic> json) {
    return DailyReminder(
      type: json['type'] ?? '',
      memberId: json['member_id']?.toString() ?? '',
      memberName: json['member_name'] ?? '',
      daysUntil: json['days_until'] ?? 0,
      title: json['title'] ?? '',
      body: json['body'] ?? '',
      priority: json['priority'] ?? 'normal',
    );
  }

  IconData get icon {
    switch (type) {
      case 'birthday':
        return Icons.cake;
      case 'contact':
        return Icons.phone;
      case 'festival':
        return Icons.card_giftcard;
      default:
        return Icons.notifications;
    }
  }

  Color get color {
    switch (type) {
      case 'birthday':
        return const Color(0xFFF59E0B);
      case 'contact':
        return const Color(0xFF3B82F6);
      case 'festival':
        return const Color(0xFF22C55E);
      default:
        return const Color(0xFF6B7280);
    }
  }
}

// BLoC
class SmartGroupsBloc extends Bloc<SmartGroupsEvent, SmartGroupsState> {
  final RelationshipRemoteDataSource _dataSource;

  SmartGroupsBloc({required RelationshipRemoteDataSource dataSource})
      : _dataSource = dataSource,
        super(const SmartGroupsInitial()) {
    on<SmartGroupsLoadRequested>(_onLoadRequested);
    on<SmartGroupsRefreshRequested>(_onRefreshRequested);
    on<SmartGroupDetailRequested>(_onDetailRequested);
  }

  Future<void> _onLoadRequested(
    SmartGroupsLoadRequested event,
    Emitter<SmartGroupsState> emit,
  ) async {
    emit(const SmartGroupsLoading());
    await _loadGroups(emit);
  }

  Future<void> _onRefreshRequested(
    SmartGroupsRefreshRequested event,
    Emitter<SmartGroupsState> emit,
  ) async {
    await _loadGroups(emit);
  }

  Future<void> _onDetailRequested(
    SmartGroupDetailRequested event,
    Emitter<SmartGroupsState> emit,
  ) async {
    final currentState = state;
    if (currentState is! SmartGroupsLoaded) return;

    try {
      final detailJson = await _dataSource.getSmartGroupDetail(event.groupKey);
      final detail = SmartGroupDetail.fromJson(detailJson);
      emit(currentState.copyWith(selectedGroupDetail: detail));
    } catch (_) {
      // Keep current state on error
    }
  }

  Future<void> _loadGroups(Emitter<SmartGroupsState> emit) async {
    try {
      final groupsJson = await _dataSource.getSmartGroups();
      final groups = groupsJson
          .map((item) => SmartGroup.fromJson(item as Map<String, dynamic>))
          .toList();

      emit(SmartGroupsLoaded(groups: groups));
    } catch (e) {
      // On error, show empty state (no hardcoded data)
      emit(const SmartGroupsLoaded(groups: []));
    }
  }

  Future<List<DailyReminder>> getDailyReminders() async {
    try {
      final response = await _dataSource.getDailyReminders();
      final reminders = (response['reminders'] as List<dynamic>? ?? [])
          .map((item) => DailyReminder.fromJson(item as Map<String, dynamic>))
          .toList();
      return reminders;
    } catch (_) {
      return [];
    }
  }
}
