import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/user_stats.dart';
import '../entities/smart_service.dart';

/// Profile repository interface
abstract class ProfileRepository {
  /// Get user statistics
  Future<Either<Failure, UserStats>> getUserStats();

  /// Get all smart services with their status
  Future<Either<Failure, SmartServicesSummary>> getSmartServices();

  /// Pause a smart service
  Future<Either<Failure, void>> pauseService(String serviceId);

  /// Resume a smart service
  Future<Either<Failure, void>> resumeService(String serviceId);

  /// Manually trigger a job in a service
  Future<Either<Failure, void>> triggerServiceJob(String serviceId, String jobName);
}
