import 'package:flutter_bloc/flutter_bloc.dart';

import '../../data/models/connector_metadata_model.dart';
import '../../data/models/data_connection_model.dart';
import '../../domain/entities/connection_stats.dart';
import '../../domain/repositories/data_connection_repository.dart';
import 'connection_event.dart';
import 'connection_state.dart';

/// BLoC for managing data connections
class ConnectionBloc extends Bloc<ConnectionEvent, DataConnectionState> {
  final DataConnectionRepository repository;

  List<ConnectorMetadataModel> _cachedConnectors = [];
  List<DataConnectionModel> _cachedConnections = [];
  ConnectionUsageSummary? _cachedUsageSummary;

  ConnectionBloc({
    required this.repository,
  }) : super(const ConnectionInitial()) {
    on<LoadConnectors>(_onLoadConnectors);
    on<LoadConnections>(_onLoadConnections);
    on<RefreshConnectionData>(_onRefreshData);
    on<InitiateConnection>(_onInitiateConnection);
    on<CompleteConnection>(_onCompleteConnection);
    on<DisconnectConnection>(_onDisconnectConnection);
    on<UpdateConnectionSettings>(_onUpdateSettings);
    on<TriggerSync>(_onTriggerSync);
    on<LoadUsageSummary>(_onLoadUsageSummary);
  }

  Future<void> _onLoadConnectors(
    LoadConnectors event,
    Emitter<DataConnectionState> emit,
  ) async {
    emit(const ConnectionLoading());

    final result = await repository.getAvailableConnectors(
      category: event.category,
      region: event.region,
    );

    result.fold(
      (failure) {
        emit(ConnectionError(failure.message));
      },
      (connectors) {
        _cachedConnectors = connectors.cast<ConnectorMetadataModel>();
        emit(ConnectionLoaded(
          connectors: _cachedConnectors,
          connections: _cachedConnections,
          usageSummary: _cachedUsageSummary,
        ));
      },
    );
  }

  Future<void> _onLoadConnections(
    LoadConnections event,
    Emitter<DataConnectionState> emit,
  ) async {
    emit(const ConnectionLoading());

    final result = await repository.getUserConnections(
      includeDisconnected: event.includeDisconnected,
    );

    result.fold(
      (failure) {
        emit(ConnectionError(failure.message));
      },
      (connections) {
        _cachedConnections = connections.cast<DataConnectionModel>();
        emit(ConnectionLoaded(
          connectors: _cachedConnectors,
          connections: _cachedConnections,
          usageSummary: _cachedUsageSummary,
        ));
      },
    );
  }

  Future<void> _onRefreshData(
    RefreshConnectionData event,
    Emitter<DataConnectionState> emit,
  ) async {
    emit(const ConnectionLoading());

    // Load connectors and connections in parallel
    final connectorsResult = await repository.getAvailableConnectors();
    final connectionsResult = await repository.getUserConnections();
    final summaryResult = await repository.getUsageSummary();

    connectorsResult.fold(
      (failure) {},
      (connectors) {
        _cachedConnectors = connectors.cast<ConnectorMetadataModel>();
      },
    );

    connectionsResult.fold(
      (failure) {},
      (connections) {
        _cachedConnections = connections.cast<DataConnectionModel>();
      },
    );

    summaryResult.fold(
      (failure) {},
      (summary) {
        _cachedUsageSummary = summary;
      },
    );

    if (_cachedConnectors.isNotEmpty || _cachedConnections.isNotEmpty) {
      emit(ConnectionLoaded(
        connectors: _cachedConnectors,
        connections: _cachedConnections,
        usageSummary: _cachedUsageSummary,
      ));
    } else {
      emit(const ConnectionError('加载数据连接失败'));
    }
  }

  Future<void> _onInitiateConnection(
    InitiateConnection event,
    Emitter<DataConnectionState> emit,
  ) async {
    final currentState = state;
    final previousLoaded = currentState is ConnectionLoaded ? currentState : null;

    if (previousLoaded != null) {
      emit(ConnectionOperationInProgress(
        operationType: 'initiate',
        previousState: previousLoaded,
      ));
    }

    final result = await repository.initiateConnection(
      connectorId: event.connectorId,
      scopes: event.scopes,
    );

    result.fold(
      (failure) {
        emit(ConnectionError(failure.message, previousState: previousLoaded));
      },
      (initResult) {
        emit(ConnectionAuthRequired(
          connectionId: initResult.connectionId,
          authUrl: initResult.authUrl,
          connectorId: initResult.connectorId,
          connectorName: initResult.connectorName,
          previousState: previousLoaded,
        ));
      },
    );
  }

  Future<void> _onCompleteConnection(
    CompleteConnection event,
    Emitter<DataConnectionState> emit,
  ) async {
    final currentState = state;
    final previousLoaded = currentState is ConnectionAuthRequired
        ? currentState.previousState
        : currentState is ConnectionLoaded
            ? currentState
            : null;

    if (previousLoaded != null) {
      emit(ConnectionOperationInProgress(
        operationType: 'complete',
        connectionId: event.connectionId,
        previousState: previousLoaded,
      ));
    }

    final result = await repository.completeConnection(
      connectionId: event.connectionId,
      code: event.code,
      state: event.state,
    );

    await result.fold(
      (failure) async {
        emit(ConnectionError(failure.message, previousState: previousLoaded));
      },
      (connection) async {
        // Refresh connections list
        final connectionsResult = await repository.getUserConnections();
        connectionsResult.fold(
          (failure) {
            if (previousLoaded != null) {
              final connectionModel = connection as DataConnectionModel;
              final updated = previousLoaded.copyWith(
                connections: [...previousLoaded.connections, connectionModel],
              );
              _cachedConnections = updated.connections;
              emit(ConnectionOperationSuccess(
                message: '连接成功',
                currentState: updated,
              ));
              emit(updated);
            }
          },
          (connections) {
            _cachedConnections = connections.cast<DataConnectionModel>();
            final newState = ConnectionLoaded(
              connectors: _cachedConnectors,
              connections: _cachedConnections,
              usageSummary: _cachedUsageSummary,
            );
            emit(ConnectionOperationSuccess(
              message: '连接成功',
              currentState: newState,
            ));
            emit(newState);
          },
        );
      },
    );
  }

  Future<void> _onDisconnectConnection(
    DisconnectConnection event,
    Emitter<DataConnectionState> emit,
  ) async {
    final currentState = state;
    if (currentState is! ConnectionLoaded) return;

    emit(ConnectionOperationInProgress(
      operationType: 'disconnect',
      connectionId: event.connectionId,
      previousState: currentState,
    ));

    final result = await repository.disconnect(event.connectionId);

    await result.fold(
      (failure) async {
        emit(currentState);
        emit(ConnectionError(failure.message, previousState: currentState));
      },
      (_) async {
        // Refresh connections list
        final connectionsResult = await repository.getUserConnections();
        connectionsResult.fold(
          (failure) {
            // Remove from cached list
            _cachedConnections = _cachedConnections
                .where((c) => c.id != event.connectionId)
                .toList();
            final newState = currentState.copyWith(connections: _cachedConnections);
            emit(ConnectionOperationSuccess(
              message: '已断开连接',
              currentState: newState,
            ));
            emit(newState);
          },
          (connections) {
            _cachedConnections = connections.cast<DataConnectionModel>();
            final newState = currentState.copyWith(connections: _cachedConnections);
            emit(ConnectionOperationSuccess(
              message: '已断开连接',
              currentState: newState,
            ));
            emit(newState);
          },
        );
      },
    );
  }

  Future<void> _onUpdateSettings(
    UpdateConnectionSettings event,
    Emitter<DataConnectionState> emit,
  ) async {
    final currentState = state;
    if (currentState is! ConnectionLoaded) return;

    emit(ConnectionOperationInProgress(
      operationType: 'update',
      connectionId: event.connectionId,
      previousState: currentState,
    ));

    final result = await repository.updateConnectionSettings(
      connectionId: event.connectionId,
      syncFrequency: event.syncFrequency,
      syncEnabled: event.syncEnabled,
      usagePermissions: event.usagePermissions,
    );

    result.fold(
      (failure) {
        emit(currentState);
        emit(ConnectionError(failure.message, previousState: currentState));
      },
      (updatedConnection) {
        // Update in cached list
        final updatedModel = updatedConnection as DataConnectionModel;
        _cachedConnections = _cachedConnections.map((c) {
          return c.id == event.connectionId ? updatedModel : c;
        }).toList();
        final newState = currentState.copyWith(connections: _cachedConnections);
        emit(ConnectionOperationSuccess(
          message: '设置已更新',
          currentState: newState,
        ));
        emit(newState);
      },
    );
  }

  Future<void> _onTriggerSync(
    TriggerSync event,
    Emitter<DataConnectionState> emit,
  ) async {
    final currentState = state;
    if (currentState is! ConnectionLoaded) return;

    emit(ConnectionOperationInProgress(
      operationType: 'sync',
      connectionId: event.connectionId,
      previousState: currentState,
    ));

    final result = await repository.triggerSync(
      connectionId: event.connectionId,
      fullSync: event.fullSync,
    );

    await result.fold(
      (failure) async {
        emit(currentState);
        emit(ConnectionError(failure.message, previousState: currentState));
      },
      (syncResult) async {
        // Refresh connections list to get updated sync times
        final connectionsResult = await repository.getUserConnections();
        connectionsResult.fold(
          (failure) {
            emit(ConnectionSyncComplete(
              result: syncResult,
              currentState: currentState,
            ));
            emit(currentState);
          },
          (connections) {
            _cachedConnections = connections.cast<DataConnectionModel>();
            final newState = currentState.copyWith(connections: _cachedConnections);
            emit(ConnectionSyncComplete(
              result: syncResult,
              currentState: newState,
            ));
            emit(newState);
          },
        );
      },
    );
  }

  Future<void> _onLoadUsageSummary(
    LoadUsageSummary event,
    Emitter<DataConnectionState> emit,
  ) async {
    final currentState = state;

    final result = await repository.getUsageSummary();

    result.fold(
      (failure) {
        // Silent fail, keep current state
      },
      (summary) {
        _cachedUsageSummary = summary;
        if (currentState is ConnectionLoaded) {
          emit(currentState.copyWith(usageSummary: summary));
        }
      },
    );
  }
}
