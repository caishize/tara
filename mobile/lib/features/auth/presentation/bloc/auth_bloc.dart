import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';

import '../../../../core/config/app_config.dart';
import '../../../../core/events/app_event_bus.dart';
import '../../../../core/storage/auth_storage.dart';
import '../../domain/entities/user.dart';
import '../../domain/repositories/auth_repository.dart';
import '../../domain/usecases/login_usecase.dart';

// Events
abstract class AuthEvent extends Equatable {
  const AuthEvent();

  @override
  List<Object?> get props => [];
}

class AuthCheckRequested extends AuthEvent {
  const AuthCheckRequested();
}

class AuthLoginRequested extends AuthEvent {
  final String email;
  final String password;

  const AuthLoginRequested({
    required this.email,
    required this.password,
  });

  @override
  List<Object?> get props => [email, password];
}

class AuthRegisterRequested extends AuthEvent {
  final String email;
  final String password;
  final String familyName;

  const AuthRegisterRequested({
    required this.email,
    required this.password,
    required this.familyName,
  });

  @override
  List<Object?> get props => [email, password, familyName];
}

class AuthLogoutRequested extends AuthEvent {
  const AuthLogoutRequested();
}

class AuthFetchProfileRequested extends AuthEvent {
  const AuthFetchProfileRequested();
}

class AuthUpdateProfileRequested extends AuthEvent {
  final String? username;
  final String? nickname;
  final String? phone;
  final String? email;
  final String? timezone;

  const AuthUpdateProfileRequested({
    this.username,
    this.nickname,
    this.phone,
    this.email,
    this.timezone,
  });

  @override
  List<Object?> get props => [username, nickname, phone, email, timezone];
}

class AuthChangePasswordRequested extends AuthEvent {
  final String currentPassword;
  final String newPassword;

  const AuthChangePasswordRequested({
    required this.currentPassword,
    required this.newPassword,
  });

  @override
  List<Object?> get props => [currentPassword, newPassword];
}

class AuthDeleteAccountRequested extends AuthEvent {
  final String password;

  const AuthDeleteAccountRequested({required this.password});

  @override
  List<Object?> get props => [password];
}

// States
abstract class AuthState extends Equatable {
  const AuthState();

  @override
  List<Object?> get props => [];
}

class AuthInitial extends AuthState {
  const AuthInitial();
}

class AuthLoading extends AuthState {
  const AuthLoading();
}

class AuthAuthenticated extends AuthState {
  final User user;

  const AuthAuthenticated(this.user);

  @override
  List<Object?> get props => [user];
}

class AuthUnauthenticated extends AuthState {
  const AuthUnauthenticated();
}

class AuthError extends AuthState {
  final String message;

  const AuthError(this.message);

  @override
  List<Object?> get props => [message];
}

class AuthOperationInProgress extends AuthState {
  final User user;

  const AuthOperationInProgress(this.user);

  @override
  List<Object?> get props => [user];
}

class AuthOperationSuccess extends AuthState {
  final User user;
  final String message;

  const AuthOperationSuccess({required this.user, required this.message});

  @override
  List<Object?> get props => [user, message];
}

// BLoC
class AuthBloc extends Bloc<AuthEvent, AuthState> {
  final LoginUseCase loginUseCase;
  final AuthStorage authStorage;
  final AuthRepository authRepository;

  AuthBloc({
    required this.loginUseCase,
    required this.authStorage,
    required this.authRepository,
  }) : super(const AuthInitial()) {
    on<AuthCheckRequested>(_onAuthCheckRequested);
    on<AuthRegisterRequested>(_onAuthRegisterRequested);
    on<AuthLoginRequested>(_onAuthLoginRequested);
    on<AuthLogoutRequested>(_onAuthLogoutRequested);
    on<AuthFetchProfileRequested>(_onAuthFetchProfileRequested);
    on<AuthUpdateProfileRequested>(_onAuthUpdateProfileRequested);
    on<AuthChangePasswordRequested>(_onAuthChangePasswordRequested);
    on<AuthDeleteAccountRequested>(_onAuthDeleteAccountRequested);
  }

  Future<void> _onAuthCheckRequested(
    AuthCheckRequested event,
    Emitter<AuthState> emit,
  ) async {
    emit(const AuthLoading());

    // Dev auto-login: seed auth storage with default dev credentials
    // so the app bypasses login when backend has STRICT_AUTH_ENABLED=false
    if (AppConfig.devAutoLogin && !authStorage.isAuthenticated) {
      await authStorage.saveTokens(
        accessToken: 'dev-token',
        refreshToken: 'dev-refresh-token',
      );
      await authStorage.saveUserInfo(
        userId: AppConfig.devUserId,
        familyId: AppConfig.devFamilyId,
        username: 'dev_user',
        email: 'dev@example.com',
      );
    }

    if (authStorage.isAuthenticated) {
      final userInfo = authStorage.getUserInfo();
      if (userInfo != null) {
        emit(AuthAuthenticated(User(
          id: userInfo['id'] as String,
          username: userInfo['username'] as String,
          email: userInfo['email'] as String?,
          familyId: userInfo['family_id'] as String,
        )));
      } else {
        emit(const AuthUnauthenticated());
      }
    } else {
      emit(const AuthUnauthenticated());
    }
  }

  Future<void> _onAuthRegisterRequested(
    AuthRegisterRequested event,
    Emitter<AuthState> emit,
  ) async {
    emit(const AuthLoading());

    final result = await authRepository.register(
      email: event.email,
      password: event.password,
      familyName: event.familyName,
    );

    result.fold(
      (failure) => emit(AuthError(failure.message)),
      (authResult) => emit(AuthAuthenticated(authResult.user)),
    );
  }

  Future<void> _onAuthLoginRequested(
    AuthLoginRequested event,
    Emitter<AuthState> emit,
  ) async {
    emit(const AuthLoading());

    final result = await loginUseCase(
      email: event.email,
      password: event.password,
    );

    result.fold(
      (failure) => emit(AuthError(failure.message)),
      (authResult) => emit(AuthAuthenticated(authResult.user)),
    );
  }

  Future<void> _onAuthLogoutRequested(
    AuthLogoutRequested event,
    Emitter<AuthState> emit,
  ) async {
    await authStorage.clearAuth();
    emit(const AuthUnauthenticated());
  }

  Future<void> _onAuthFetchProfileRequested(
    AuthFetchProfileRequested event,
    Emitter<AuthState> emit,
  ) async {
    final result = await authRepository.getProfile();
    result.fold(
      (failure) => null, // silently ignore fetch errors
      (user) => emit(AuthAuthenticated(user)),
    );
  }

  Future<void> _onAuthUpdateProfileRequested(
    AuthUpdateProfileRequested event,
    Emitter<AuthState> emit,
  ) async {
    final currentState = state;
    if (currentState is! AuthAuthenticated) return;

    emit(AuthOperationInProgress(currentState.user));

    final result = await authRepository.updateProfile(
      username: event.username,
      nickname: event.nickname,
      phone: event.phone,
      email: event.email,
      timezone: event.timezone,
    );

    result.fold(
      (failure) {
        emit(AuthError(failure.message));
        emit(AuthAuthenticated(currentState.user));
      },
      (user) {
        emit(AuthOperationSuccess(user: user, message: '资料更新成功'));
        emit(AuthAuthenticated(user));
        // Notify other BLoCs (e.g. MembersBloc) that the self-member was updated
        AppEventBus.instance.fire(MemberUpdatedEvent(memberId: user.id));
      },
    );
  }

  Future<void> _onAuthChangePasswordRequested(
    AuthChangePasswordRequested event,
    Emitter<AuthState> emit,
  ) async {
    final currentState = state;
    if (currentState is! AuthAuthenticated) return;

    emit(AuthOperationInProgress(currentState.user));

    final result = await authRepository.changePassword(
      currentPassword: event.currentPassword,
      newPassword: event.newPassword,
    );

    result.fold(
      (failure) {
        emit(AuthError(failure.message));
        emit(AuthAuthenticated(currentState.user));
      },
      (_) {
        emit(AuthOperationSuccess(user: currentState.user, message: '密码修改成功'));
        emit(AuthAuthenticated(currentState.user));
      },
    );
  }

  Future<void> _onAuthDeleteAccountRequested(
    AuthDeleteAccountRequested event,
    Emitter<AuthState> emit,
  ) async {
    final currentState = state;
    if (currentState is! AuthAuthenticated) return;

    emit(AuthOperationInProgress(currentState.user));

    final result = await authRepository.deleteAccount(
      password: event.password,
    );

    result.fold(
      (failure) {
        emit(AuthError(failure.message));
        emit(AuthAuthenticated(currentState.user));
      },
      (_) {
        emit(const AuthUnauthenticated());
      },
    );
  }
}
