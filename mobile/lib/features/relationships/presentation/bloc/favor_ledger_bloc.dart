import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';
import '../../data/datasources/relationship_remote_datasource.dart';
import '../../../members/data/datasources/member_remote_datasource.dart';
import '../../../members/domain/entities/member.dart';

// Events
abstract class FavorLedgerEvent extends Equatable {
  const FavorLedgerEvent();
  @override
  List<Object?> get props => [];
}

class FavorLedgerLoadRequested extends FavorLedgerEvent {
  final String familyId;
  const FavorLedgerLoadRequested({required this.familyId});
  @override
  List<Object?> get props => [familyId];
}

class FavorLedgerRefreshRequested extends FavorLedgerEvent {
  const FavorLedgerRefreshRequested();
}

class FavorCreateRequested extends FavorLedgerEvent {
  final String contactName;
  final String? contactId;
  final double amount;
  final String direction;
  final String eventType;

  const FavorCreateRequested({
    required this.contactName,
    this.contactId,
    required this.amount,
    required this.direction,
    required this.eventType,
  });

  @override
  List<Object?> get props => [contactName, contactId, amount, direction, eventType];
}

// States
abstract class FavorLedgerState extends Equatable {
  const FavorLedgerState();
  @override
  List<Object?> get props => [];
}

class FavorLedgerInitial extends FavorLedgerState {
  const FavorLedgerInitial();
}

class FavorLedgerLoading extends FavorLedgerState {
  const FavorLedgerLoading();
}

class FavorLedgerLoaded extends FavorLedgerState {
  final FavorStatistics statistics;
  final List<FavorRecord> records;
  final List<FavorContact> contacts;
  final List<Member> members;

  const FavorLedgerLoaded({
    required this.statistics,
    required this.records,
    required this.contacts,
    this.members = const [],
  });

  List<FavorRecord> get pendingRecords =>
      records.where((r) => r.status == 'pending').toList();

  @override
  List<Object?> get props => [statistics, records, contacts, members];
}

class FavorLedgerError extends FavorLedgerState {
  final String message;
  const FavorLedgerError(this.message);
  @override
  List<Object?> get props => [message];
}

// Models
class FavorStatistics {
  final double totalReceived;
  final double totalGiven;
  final double netBalance;
  final int pendingCount;

  const FavorStatistics({
    required this.totalReceived,
    required this.totalGiven,
    required this.netBalance,
    required this.pendingCount,
  });

  factory FavorStatistics.fromJson(Map<String, dynamic> json) {
    return FavorStatistics(
      totalReceived: (json['total_received'] ?? 0).toDouble(),
      totalGiven: (json['total_given'] ?? 0).toDouble(),
      netBalance: (json['net_balance'] ?? 0).toDouble(),
      pendingCount: json['pending_count'] ?? 0,
    );
  }

  factory FavorStatistics.empty() {
    return const FavorStatistics(
      totalReceived: 0,
      totalGiven: 0,
      netBalance: 0,
      pendingCount: 0,
    );
  }
}

class FavorRecord {
  final String id;
  final String contactName;
  final String direction;
  final double amount;
  final String eventType;
  final String date;
  final String status;

  const FavorRecord({
    required this.id,
    required this.contactName,
    required this.direction,
    required this.amount,
    required this.eventType,
    required this.date,
    required this.status,
  });

  factory FavorRecord.fromJson(Map<String, dynamic> json) {
    // Backend returns 'recorded_at', not 'event_date'
    final dateStr = json['recorded_at'] ?? json['event_date'] ?? '';
    return FavorRecord(
      id: json['id']?.toString() ?? '',
      contactName: json['contact_name'] ?? '',
      direction: json['direction'] ?? 'receive',
      amount: (json['amount'] ?? 0).toDouble(),
      eventType: json['event_type'] ?? 'other',
      date: dateStr.toString().split('T')[0],
      status: json['status'] ?? 'pending',
    );
  }
}

class FavorContact {
  final String name;
  final double totalReceived;
  final double totalGiven;
  final double balance;
  final String? position;
  final String? company;

  const FavorContact({
    required this.name,
    required this.totalReceived,
    required this.totalGiven,
    required this.balance,
    this.position,
    this.company,
  });

  factory FavorContact.fromJson(Map<String, dynamic> json) {
    return FavorContact(
      name: json['name'] ?? '',
      totalReceived: (json['total_received'] ?? 0).toDouble(),
      totalGiven: (json['total_given'] ?? 0).toDouble(),
      balance: (json['balance'] ?? 0).toDouble(),
      position: json['position'] as String?,
      company: json['company'] as String?,
    );
  }
}

// BLoC
class FavorLedgerBloc extends Bloc<FavorLedgerEvent, FavorLedgerState> {
  final RelationshipRemoteDataSource _dataSource;
  final MemberRemoteDataSource? _memberDataSource;
  String? _familyId;

  FavorLedgerBloc({
    required RelationshipRemoteDataSource dataSource,
    MemberRemoteDataSource? memberDataSource,
  })  : _dataSource = dataSource,
        _memberDataSource = memberDataSource,
        super(const FavorLedgerInitial()) {
    on<FavorLedgerLoadRequested>(_onLoadRequested);
    on<FavorLedgerRefreshRequested>(_onRefreshRequested);
    on<FavorCreateRequested>(_onCreateRequested);
  }

  Future<void> _onLoadRequested(
    FavorLedgerLoadRequested event,
    Emitter<FavorLedgerState> emit,
  ) async {
    _familyId = event.familyId;
    emit(const FavorLedgerLoading());
    await _loadData(emit);
  }

  Future<void> _onRefreshRequested(
    FavorLedgerRefreshRequested event,
    Emitter<FavorLedgerState> emit,
  ) async {
    if (_familyId == null) return;
    await _loadData(emit);
  }

  Future<void> _onCreateRequested(
    FavorCreateRequested event,
    Emitter<FavorLedgerState> emit,
  ) async {
    if (_familyId == null) {
      emit(const FavorLedgerError('Family ID not found'));
      return;
    }

    try {
      await _dataSource.createQuickFavor(
        familyId: _familyId!,
        contactName: event.contactName,
        contactId: event.contactId,
        amount: event.amount,
        direction: event.direction,
        eventType: event.eventType,
      );
      // Reload data after successful creation
      await _loadData(emit);
    } catch (e) {
      emit(FavorLedgerError('创建失败: ${e.toString()}'));
    }
  }

  Future<void> _loadData(Emitter<FavorLedgerState> emit) async {
    if (_familyId == null) {
      emit(const FavorLedgerError('Family ID not found'));
      return;
    }

    try {
      // Load members independently so they're available even if favor APIs fail
      final membersFuture = _memberDataSource != null
          ? _memberDataSource.getMembers().then<List<Member>>(
              (models) => models.cast<Member>(),
              onError: (_) => <Member>[],
            )
          : Future.value(<Member>[]);

      // Load statistics and records in parallel with members
      final results = await Future.wait([
        _dataSource.getFavorStatistics(_familyId!),
        _dataSource.getFavorRecords(familyId: _familyId!),
        membersFuture,
      ]);

      final statsJson = results[0] as Map<String, dynamic>;
      final recordsJson = results[1] as Map<String, dynamic>;
      final members = results[2] as List<Member>;

      final statistics = FavorStatistics.fromJson(statsJson);
      final recordsList = (recordsJson['items'] as List<dynamic>? ?? [])
          .map((item) => FavorRecord.fromJson(item as Map<String, dynamic>))
          .toList();

      // Build contact summaries from records
      final contactMap = <String, _ContactAccumulator>{};
      for (final record in recordsList) {
        final acc = contactMap.putIfAbsent(
          record.contactName,
          () => _ContactAccumulator(record.contactName),
        );
        if (record.direction == 'receive') {
          acc.totalReceived += record.amount;
        } else {
          acc.totalGiven += record.amount;
        }
      }

      final contacts = contactMap.values
          .map((acc) => FavorContact(
                name: acc.name,
                totalReceived: acc.totalReceived,
                totalGiven: acc.totalGiven,
                balance: acc.totalReceived - acc.totalGiven,
              ))
          .toList();

      emit(FavorLedgerLoaded(
        statistics: statistics,
        records: recordsList,
        contacts: contacts,
        members: members,
      ));
    } catch (e) {
      // If favor APIs fail, still try to load members for the add form
      var members = <Member>[];
      if (_memberDataSource != null) {
        try {
          final models = await _memberDataSource.getMembers();
          members = models.cast<Member>();
        } catch (_) {}
      }

      emit(FavorLedgerLoaded(
        statistics: FavorStatistics.empty(),
        records: const [],
        contacts: const [],
        members: members,
      ));
    }
  }
}

/// Helper for accumulating contact totals from records.
class _ContactAccumulator {
  final String name;
  double totalReceived = 0;
  double totalGiven = 0;

  _ContactAccumulator(this.name);
}
