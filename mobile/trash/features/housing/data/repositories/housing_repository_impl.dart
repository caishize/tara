import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../../../../core/error/exceptions.dart';
import '../../domain/entities/property.dart';
import '../../domain/repositories/housing_repository.dart';
import '../datasources/housing_remote_datasource.dart';

/// Housing repository implementation
class HousingRepositoryImpl implements HousingRepository {
  final HousingRemoteDataSource remoteDataSource;

  HousingRepositoryImpl({required this.remoteDataSource});

  @override
  Future<Either<Failure, List<Property>>> getProperties() async {
    try {
      final properties = await remoteDataSource.getProperties();
      return Right(properties);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, Property>> getProperty(String propertyId) async {
    try {
      final property = await remoteDataSource.getProperty(propertyId);
      return Right(property);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, Property>> createProperty({
    required String address,
    double? areaSqm,
    DateTime? purchaseDate,
    String? mortgageBank,
    double? mortgageAmount,
    int? mortgageDay,
    double? propertyFeeAmount,
    PropertyFeeCycle? propertyFeeCycle,
    int? propertyFeeDay,
    String? notes,
  }) async {
    try {
      final property = await remoteDataSource.createProperty(
        address: address,
        areaSqm: areaSqm,
        purchaseDate: purchaseDate,
        mortgageBank: mortgageBank,
        mortgageAmount: mortgageAmount,
        mortgageDay: mortgageDay,
        propertyFeeAmount: propertyFeeAmount,
        propertyFeeCycle: propertyFeeCycle,
        propertyFeeDay: propertyFeeDay,
        notes: notes,
      );
      return Right(property);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, Property>> updateProperty({
    required String propertyId,
    String? address,
    double? areaSqm,
    String? mortgageBank,
    double? mortgageAmount,
    int? mortgageDay,
    double? propertyFeeAmount,
    PropertyFeeCycle? propertyFeeCycle,
    int? propertyFeeDay,
    String? notes,
  }) async {
    try {
      final property = await remoteDataSource.updateProperty(
        propertyId: propertyId,
        address: address,
        areaSqm: areaSqm,
        mortgageBank: mortgageBank,
        mortgageAmount: mortgageAmount,
        mortgageDay: mortgageDay,
        propertyFeeAmount: propertyFeeAmount,
        propertyFeeCycle: propertyFeeCycle,
        propertyFeeDay: propertyFeeDay,
        notes: notes,
      );
      return Right(property);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, void>> deleteProperty(String propertyId) async {
    try {
      await remoteDataSource.deleteProperty(propertyId);
      return const Right(null);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, List<MortgagePayment>>> getMortgagePayments(String propertyId, {int limit = 12}) async {
    try {
      final payments = await remoteDataSource.getMortgagePayments(propertyId, limit: limit);
      return Right(payments);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, MortgagePayment>> recordMortgagePayment({
    required String propertyId,
    required DateTime paymentDate,
    required double amount,
    String? paymentMethod,
    String? notes,
  }) async {
    try {
      final payment = await remoteDataSource.recordMortgagePayment(
        propertyId: propertyId,
        paymentDate: paymentDate,
        amount: amount,
        paymentMethod: paymentMethod,
        notes: notes,
      );
      return Right(payment);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, List<Appliance>>> getAppliances(String propertyId) async {
    try {
      final appliances = await remoteDataSource.getAppliances(propertyId);
      return Right(appliances);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, Appliance>> createAppliance({
    required String propertyId,
    required String name,
    String? brand,
    String? model,
    DateTime? purchaseDate,
    DateTime? warrantyExpiry,
    int maintenanceCycleMonths = 12,
    String? notes,
  }) async {
    try {
      final appliance = await remoteDataSource.createAppliance(
        propertyId: propertyId,
        name: name,
        brand: brand,
        model: model,
        purchaseDate: purchaseDate,
        warrantyExpiry: warrantyExpiry,
        maintenanceCycleMonths: maintenanceCycleMonths,
        notes: notes,
      );
      return Right(appliance);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, Appliance>> updateAppliance({
    required String applianceId,
    String? name,
    String? brand,
    String? model,
    DateTime? lastMaintenanceDate,
    int? maintenanceCycleMonths,
    String? notes,
  }) async {
    try {
      final appliance = await remoteDataSource.updateAppliance(
        applianceId: applianceId,
        name: name,
        brand: brand,
        model: model,
        lastMaintenanceDate: lastMaintenanceDate,
        maintenanceCycleMonths: maintenanceCycleMonths,
        notes: notes,
      );
      return Right(appliance);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, void>> deleteAppliance(String applianceId) async {
    try {
      await remoteDataSource.deleteAppliance(applianceId);
      return const Right(null);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, void>> recordMaintenance({
    required String applianceId,
    required DateTime maintenanceDate,
    String? content,
    double? cost,
    String? serviceProvider,
    String? notes,
  }) async {
    try {
      await remoteDataSource.recordMaintenance(
        applianceId: applianceId,
        maintenanceDate: maintenanceDate,
        content: content,
        cost: cost,
        serviceProvider: serviceProvider,
        notes: notes,
      );
      return const Right(null);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException {
      return const Left(NetworkFailure());
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }
}
