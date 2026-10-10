import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';

import '../../data/datasources/connections_remote_datasource.dart';
import '../../data/models/connection_model.dart';

// Events
abstract class ConnectionsEvent extends Equatable {
  const ConnectionsEvent();

  @override
  List<Object?> get props => [];
}

class LoadConnections extends ConnectionsEvent {
  const LoadConnections();
}

class ConnectProvider extends ConnectionsEvent {
  final String providerName;

  const ConnectProvider(this.providerName);

  @override
  List<Object?> get props => [providerName];
}

class DisconnectProvider extends ConnectionsEvent {
  final String connectionId;

  const DisconnectProvider(this.connectionId);

  @override
  List<Object?> get props => [connectionId];
}

class CreateCustomMcpConnection extends ConnectionsEvent {
  final String displayName;
  final String mcpServerUrl;
  final Map<String, dynamic>? mcpServerConfig;

  const CreateCustomMcpConnection({
    required this.displayName,
    required this.mcpServerUrl,
    this.mcpServerConfig,
  });

  @override
  List<Object?> get props => [displayName, mcpServerUrl, mcpServerConfig];
}

// States
abstract class ConnectionsState extends Equatable {
  const ConnectionsState();

  @override
  List<Object?> get props => [];
}

class ConnectionsInitial extends ConnectionsState {
  const ConnectionsInitial();
}

class ConnectionsLoading extends ConnectionsState {
  const ConnectionsLoading();
}

class ConnectionsLoaded extends ConnectionsState {
  final List<UserConnection> connections;
  final List<AvailableProvider> availableProviders;

  const ConnectionsLoaded({
    required this.connections,
    required this.availableProviders,
  });

  @override
  List<Object?> get props => [connections, availableProviders];

  List<UserConnection> get connectedList =>
      connections.where((c) => c.isConnected).toList();

  Map<String, List<AvailableProvider>> get groupedProviders {
    final result = <String, List<AvailableProvider>>{};
    // Filter out already-connected providers
    final connectedNames =
        connections.map((c) => c.providerName).toSet();
    for (final provider in availableProviders) {
      if (connectedNames.contains(provider.providerName)) continue;
      result.putIfAbsent(provider.category, () => []).add(provider);
    }
    return result;
  }
}

class ConnectionsError extends ConnectionsState {
  final String message;

  const ConnectionsError(this.message);

  @override
  List<Object?> get props => [message];
}

// BLoC
class ConnectionsBloc extends Bloc<ConnectionsEvent, ConnectionsState> {
  final ConnectionsRemoteDataSource dataSource;

  ConnectionsBloc({required this.dataSource})
      : super(const ConnectionsInitial()) {
    on<LoadConnections>(_onLoadConnections);
    on<ConnectProvider>(_onConnectProvider);
    on<DisconnectProvider>(_onDisconnectProvider);
    on<CreateCustomMcpConnection>(_onCreateCustomMcpConnection);
  }

  Future<void> _onLoadConnections(
    LoadConnections event,
    Emitter<ConnectionsState> emit,
  ) async {
    emit(const ConnectionsLoading());
    try {
      final connections = await dataSource.fetchConnections();
      final available = await dataSource.fetchAvailableProviders();
      emit(ConnectionsLoaded(
        connections: connections,
        availableProviders: available,
      ));
    } catch (e) {
      emit(ConnectionsError('\u52a0\u8f7d\u8fde\u63a5\u5931\u8d25: $e'));
    }
  }

  Future<void> _onConnectProvider(
    ConnectProvider event,
    Emitter<ConnectionsState> emit,
  ) async {
    try {
      await dataSource.connectProvider(event.providerName);
      add(const LoadConnections());
    } catch (e) {
      emit(ConnectionsError('\u8fde\u63a5\u5931\u8d25: $e'));
    }
  }

  Future<void> _onDisconnectProvider(
    DisconnectProvider event,
    Emitter<ConnectionsState> emit,
  ) async {
    try {
      await dataSource.disconnectProvider(event.connectionId);
      add(const LoadConnections());
    } catch (e) {
      emit(ConnectionsError('\u65ad\u5f00\u8fde\u63a5\u5931\u8d25: $e'));
    }
  }

  Future<void> _onCreateCustomMcpConnection(
    CreateCustomMcpConnection event,
    Emitter<ConnectionsState> emit,
  ) async {
    try {
      await dataSource.createCustomConnection(
        displayName: event.displayName,
        mcpServerUrl: event.mcpServerUrl,
        mcpServerConfig: event.mcpServerConfig,
      );
      add(const LoadConnections());
    } catch (e) {
      emit(ConnectionsError('\u521b\u5efa MCP \u8fde\u63a5\u5931\u8d25: $e'));
    }
  }
}
