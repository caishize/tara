import 'package:dartz/dartz.dart';

import '../../../../core/error/failures.dart';
import '../../domain/entities/connector_metadata.dart';
import '../../domain/entities/data_connection.dart';
import '../../domain/entities/connection_stats.dart';
import '../../domain/repositories/data_connection_repository.dart';
import '../datasources/connection_remote_datasource.dart';

class DataConnectionRepositoryImpl implements DataConnectionRepository {
  final ConnectionRemoteDataSource remoteDataSource;

  DataConnectionRepositoryImpl({
    required this.remoteDataSource,
  });

  @override
  Future<Either<Failure, List<ConnectorMetadata>>> getAvailableConnectors({
    DataCategory? category,
    String region = 'CN',
  }) async {
    try {
      final connectors = await remoteDataSource.getAvailableConnectors(
        category: category?.name,
        region: region,
      );
      return Right(connectors);
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, ConnectorMetadata>> getConnectorDetails(
      String connectorId) async {
    try {
      final connector =
          await remoteDataSource.getConnectorDetails(connectorId);
      return Right(connector);
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, List<DataConnection>>> getUserConnections({
    bool includeDisconnected = false,
  }) async {
    try {
      final connections = await remoteDataSource.getUserConnections(
        includeDisconnected: includeDisconnected,
      );
      return Right(connections);
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, DataConnection>> getConnection(
      String connectionId) async {
    try {
      final connection = await remoteDataSource.getConnection(connectionId);
      return Right(connection);
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, InitiateConnectionResult>> initiateConnection({
    required String connectorId,
    String? redirectUri,
    List<String>? scopes,
  }) async {
    try {
      final response = await remoteDataSource.initiateConnection(
        connectorId: connectorId,
        redirectUri: redirectUri,
        scopes: scopes,
      );
      return Right(InitiateConnectionResult(
        connectionId: response['connection_id'] as String,
        authUrl: response['auth_url'] as String,
        connectorId: response['connector_id'] as String,
        connectorName: response['connector_name'] as String,
      ));
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, DataConnection>> completeConnection({
    required String connectionId,
    required String code,
    String? state,
  }) async {
    try {
      final connection = await remoteDataSource.completeConnection(
        connectionId: connectionId,
        code: code,
        state: state,
      );
      return Right(connection);
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, void>> disconnect(String connectionId) async {
    try {
      await remoteDataSource.disconnect(connectionId);
      return const Right(null);
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, DataConnection>> updateConnectionSettings({
    required String connectionId,
    SyncFrequency? syncFrequency,
    bool? syncEnabled,
    UsagePermissions? usagePermissions,
  }) async {
    try {
      final connection = await remoteDataSource.updateConnectionSettings(
        connectionId: connectionId,
        syncFrequency: syncFrequency,
        syncEnabled: syncEnabled,
        usagePermissions: usagePermissions,
      );
      return Right(connection);
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, SyncResult>> triggerSync({
    required String connectionId,
    bool fullSync = false,
  }) async {
    try {
      final result = await remoteDataSource.triggerSync(
        connectionId: connectionId,
        fullSync: fullSync,
      );
      return Right(result);
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, ConnectionStats>> getConnectionStats({
    required String connectionId,
    int sinceDays = 30,
  }) async {
    try {
      final stats = await remoteDataSource.getConnectionStats(
        connectionId: connectionId,
        sinceDays: sinceDays,
      );
      return Right(stats);
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, ConnectionUsageSummary>> getUsageSummary() async {
    try {
      final summary = await remoteDataSource.getUsageSummary();
      return Right(summary);
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, List<Map<String, dynamic>>>> getExternalCalendarEvents({
    required DateTime startDate,
    required DateTime endDate,
  }) async {
    try {
      final events = await remoteDataSource.getExternalCalendarEvents(
        startDate: startDate,
        endDate: endDate,
      );
      return Right(events);
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, List<Map<String, dynamic>>>> getExternalTravelBookings({
    required DateTime startDate,
    required DateTime endDate,
  }) async {
    try {
      final bookings = await remoteDataSource.getExternalTravelBookings(
        startDate: startDate,
        endDate: endDate,
      );
      return Right(bookings);
    } catch (e) {
      return Left(ServerFailure(e.toString()));
    }
  }
}
