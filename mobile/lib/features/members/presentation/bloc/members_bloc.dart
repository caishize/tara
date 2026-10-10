import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';

import '../../../../core/events/app_event_bus.dart';
import '../../domain/entities/member.dart';
import '../../domain/repositories/member_repository.dart';
import '../../domain/usecases/get_members_usecase.dart';
import '../../domain/usecases/create_member_usecase.dart';

// Events
abstract class MembersEvent extends Equatable {
  const MembersEvent();

  @override
  List<Object?> get props => [];
}

class MembersLoadRequested extends MembersEvent {
  const MembersLoadRequested();
}

class MemberCreateRequested extends MembersEvent {
  final Member member;

  const MemberCreateRequested(this.member);

  @override
  List<Object?> get props => [member];
}

class MemberUpdateRequested extends MembersEvent {
  final Member member;

  const MemberUpdateRequested(this.member);

  @override
  List<Object?> get props => [member];
}

class MemberDeleteRequested extends MembersEvent {
  final String memberId;

  const MemberDeleteRequested({required this.memberId});

  @override
  List<Object?> get props => [memberId];
}

class MemberRefreshRequested extends MembersEvent {
  const MemberRefreshRequested();
}

// States
abstract class MembersState extends Equatable {
  const MembersState();

  @override
  List<Object?> get props => [];
}

class MembersInitial extends MembersState {
  const MembersInitial();
}

class MembersLoading extends MembersState {
  const MembersLoading();
}

class MembersLoaded extends MembersState {
  final List<Member> members;

  const MembersLoaded(this.members);

  @override
  List<Object?> get props => [members];
}

class MembersError extends MembersState {
  final String message;

  const MembersError(this.message);

  @override
  List<Object?> get props => [message];
}

class MemberCreating extends MembersState {
  const MemberCreating();
}

class MemberCreated extends MembersState {
  final Member member;

  const MemberCreated(this.member);

  @override
  List<Object?> get props => [member];
}

class MemberDeleteSuccess extends MembersState {
  final String memberId;

  const MemberDeleteSuccess(this.memberId);

  @override
  List<Object?> get props => [memberId];
}

// BLoC
class MembersBloc extends Bloc<MembersEvent, MembersState> {
  final GetMembersUseCase getMembersUseCase;
  final CreateMemberUseCase createMemberUseCase;
  final MemberRepository repository;

  List<Member> _cachedMembers = [];
  StreamSubscription<MemberUpdatedEvent>? _memberUpdatedSub;

  MembersBloc({
    required this.getMembersUseCase,
    required this.createMemberUseCase,
    required this.repository,
  }) : super(const MembersInitial()) {
    on<MembersLoadRequested>(_onLoadRequested);
    on<MemberCreateRequested>(_onCreateRequested);
    on<MemberUpdateRequested>(_onUpdateRequested);
    on<MemberDeleteRequested>(_onDeleteRequested);
    on<MemberRefreshRequested>(_onRefreshRequested);

    // Refresh when profile is updated from another feature (e.g. AuthBloc)
    _memberUpdatedSub = AppEventBus.instance.on<MemberUpdatedEvent>().listen((_) {
      add(const MembersLoadRequested());
    });
  }

  @override
  Future<void> close() {
    _memberUpdatedSub?.cancel();
    return super.close();
  }

  Future<void> _onLoadRequested(
    MembersLoadRequested event,
    Emitter<MembersState> emit,
  ) async {
    emit(const MembersLoading());

    final result = await getMembersUseCase();

    result.fold(
      (failure) => emit(MembersError(failure.message)),
      (members) {
        _cachedMembers = members;
        emit(MembersLoaded(members));
      },
    );
  }

  Future<void> _onCreateRequested(
    MemberCreateRequested event,
    Emitter<MembersState> emit,
  ) async {
    emit(const MemberCreating());

    final result = await createMemberUseCase(event.member);

    result.fold(
      (failure) => emit(MembersError(failure.message)),
      (member) {
        _cachedMembers.add(member);
        emit(MemberCreated(member));
        emit(MembersLoaded(_cachedMembers));
      },
    );
  }

  Future<void> _onRefreshRequested(
    MemberRefreshRequested event,
    Emitter<MembersState> emit,
  ) async {
    final result = await getMembersUseCase();

    result.fold(
      (failure) {
        // Keep showing cached data on refresh failure
        if (_cachedMembers.isNotEmpty) {
          emit(MembersLoaded(_cachedMembers));
        } else {
          emit(MembersError(failure.message));
        }
      },
      (members) {
        _cachedMembers = members;
        emit(MembersLoaded(members));
      },
    );
  }

  Future<void> _onUpdateRequested(
    MemberUpdateRequested event,
    Emitter<MembersState> emit,
  ) async {
    emit(const MemberCreating()); // Reuse creating state for loading

    final result = await repository.updateMember(event.member);

    result.fold(
      (failure) => emit(MembersError(failure.message)),
      (member) {
        // Update cached member
        final index = _cachedMembers.indexWhere((m) => m.id == member.id);
        if (index != -1) {
          _cachedMembers[index] = member;
        }
        emit(MemberCreated(member)); // Reuse for success notification
        emit(MembersLoaded(List.from(_cachedMembers)));
      },
    );
  }

  Future<void> _onDeleteRequested(
    MemberDeleteRequested event,
    Emitter<MembersState> emit,
  ) async {
    final result = await repository.deleteMember(event.memberId);

    result.fold(
      (failure) => emit(MembersError(failure.message)),
      (_) {
        // Remove from cache
        _cachedMembers.removeWhere((m) => m.id == event.memberId);
        // Emit delete success first so listeners can react (e.g., pop page)
        emit(MemberDeleteSuccess(event.memberId));
        // Then emit updated list
        emit(MembersLoaded(List.from(_cachedMembers)));
      },
    );
  }
}
