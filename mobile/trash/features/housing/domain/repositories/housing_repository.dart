import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/property.dart';

/// Housing repository interface
abstract class HousingRepository {
  /// Get all properties for the current user/family
  Future<Either<Failure, List<Property>>> getProperties();

  /// Get a single property by ID
  Future<Either<Failure, Property>> getProperty(String propertyId);

  /// Create a new property
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
  });

  /// Update a property
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
  });

  /// Delete a property
  Future<Either<Failure, void>> deleteProperty(String propertyId);

  /// Get mortgage payment history
  Future<Either<Failure, List<MortgagePayment>>> getMortgagePayments(String propertyId, {int limit = 12});

  /// Record a mortgage payment
  Future<Either<Failure, MortgagePayment>> recordMortgagePayment({
    required String propertyId,
    required DateTime paymentDate,
    required double amount,
    String? paymentMethod,
    String? notes,
  });

  /// Get appliances for a property
  Future<Either<Failure, List<Appliance>>> getAppliances(String propertyId);

  /// Create an appliance
  Future<Either<Failure, Appliance>> createAppliance({
    required String propertyId,
    required String name,
    String? brand,
    String? model,
    DateTime? purchaseDate,
    DateTime? warrantyExpiry,
    int maintenanceCycleMonths = 12,
    String? notes,
  });

  /// Update an appliance
  Future<Either<Failure, Appliance>> updateAppliance({
    required String applianceId,
    String? name,
    String? brand,
    String? model,
    DateTime? lastMaintenanceDate,
    int? maintenanceCycleMonths,
    String? notes,
  });

  /// Delete an appliance
  Future<Either<Failure, void>> deleteAppliance(String applianceId);

  /// Record appliance maintenance
  Future<Either<Failure, void>> recordMaintenance({
    required String applianceId,
    required DateTime maintenanceDate,
    String? content,
    double? cost,
    String? serviceProvider,
    String? notes,
  });
}
