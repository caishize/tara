import '../../../../core/network/api_client.dart';
import '../models/property_model.dart';
import '../../domain/entities/property.dart';

/// Housing remote data source
class HousingRemoteDataSource {
  final ApiClient _apiClient;

  HousingRemoteDataSource({required ApiClient apiClient}) : _apiClient = apiClient;

  /// Get all properties
  Future<List<PropertyModel>> getProperties() async {
    final response = await _apiClient.get('/housing/properties');
    final List<dynamic> data = response is List ? response : [];
    return data.map((e) => PropertyModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// Get a single property
  Future<PropertyModel> getProperty(String propertyId) async {
    final response = await _apiClient.get('/housing/properties/$propertyId');
    return PropertyModel.fromJson(response as Map<String, dynamic>);
  }

  /// Create a property
  Future<PropertyModel> createProperty({
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
    final response = await _apiClient.post('/housing/properties', data: {
      'address': address,
      if (areaSqm != null) 'area_sqm': areaSqm,
      if (purchaseDate != null) 'purchase_date': purchaseDate.toIso8601String().split('T').first,
      if (mortgageBank != null) 'mortgage_bank': mortgageBank,
      if (mortgageAmount != null) 'mortgage_amount': mortgageAmount,
      if (mortgageDay != null) 'mortgage_day': mortgageDay,
      if (propertyFeeAmount != null) 'property_fee_amount': propertyFeeAmount,
      if (propertyFeeCycle != null) 'property_fee_cycle': _feeCycleToString(propertyFeeCycle),
      if (propertyFeeDay != null) 'property_fee_day': propertyFeeDay,
      if (notes != null) 'notes': notes,
    });
    return PropertyModel.fromJson(response as Map<String, dynamic>);
  }

  /// Update a property
  Future<PropertyModel> updateProperty({
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
    final response = await _apiClient.patch('/housing/properties/$propertyId', data: {
      if (address != null) 'address': address,
      if (areaSqm != null) 'area_sqm': areaSqm,
      if (mortgageBank != null) 'mortgage_bank': mortgageBank,
      if (mortgageAmount != null) 'mortgage_amount': mortgageAmount,
      if (mortgageDay != null) 'mortgage_day': mortgageDay,
      if (propertyFeeAmount != null) 'property_fee_amount': propertyFeeAmount,
      if (propertyFeeCycle != null) 'property_fee_cycle': _feeCycleToString(propertyFeeCycle),
      if (propertyFeeDay != null) 'property_fee_day': propertyFeeDay,
      if (notes != null) 'notes': notes,
    });
    return PropertyModel.fromJson(response as Map<String, dynamic>);
  }

  /// Delete a property
  Future<void> deleteProperty(String propertyId) async {
    await _apiClient.delete('/housing/properties/$propertyId');
  }

  /// Get mortgage payment history
  Future<List<MortgagePaymentModel>> getMortgagePayments(String propertyId, {int limit = 12}) async {
    final response = await _apiClient.get('/housing/properties/$propertyId/payments/mortgage?limit=$limit');
    final List<dynamic> data = response is List ? response : [];
    return data.map((e) => MortgagePaymentModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// Record a mortgage payment
  Future<MortgagePaymentModel> recordMortgagePayment({
    required String propertyId,
    required DateTime paymentDate,
    required double amount,
    String? paymentMethod,
    String? notes,
  }) async {
    final response = await _apiClient.post('/housing/properties/$propertyId/payments/mortgage', data: {
      'payment_date': paymentDate.toIso8601String().split('T').first,
      'amount': amount,
      if (paymentMethod != null) 'payment_method': paymentMethod,
      if (notes != null) 'notes': notes,
    });
    return MortgagePaymentModel.fromJson(response as Map<String, dynamic>);
  }

  /// Get appliances for a property
  Future<List<ApplianceModel>> getAppliances(String propertyId) async {
    final response = await _apiClient.get('/housing/appliances?property_id=$propertyId');
    final List<dynamic> data = response is List ? response : [];
    return data.map((e) => ApplianceModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// Create an appliance
  Future<ApplianceModel> createAppliance({
    required String propertyId,
    required String name,
    String? brand,
    String? model,
    DateTime? purchaseDate,
    DateTime? warrantyExpiry,
    int maintenanceCycleMonths = 12,
    String? notes,
  }) async {
    final response = await _apiClient.post('/housing/appliances', data: {
      'property_id': propertyId,
      'name': name,
      if (brand != null) 'brand': brand,
      if (model != null) 'model': model,
      if (purchaseDate != null) 'purchase_date': purchaseDate.toIso8601String().split('T').first,
      if (warrantyExpiry != null) 'warranty_expiry': warrantyExpiry.toIso8601String().split('T').first,
      'maintenance_cycle_months': maintenanceCycleMonths,
      if (notes != null) 'notes': notes,
    });
    return ApplianceModel.fromJson(response as Map<String, dynamic>);
  }

  /// Update an appliance
  Future<ApplianceModel> updateAppliance({
    required String applianceId,
    String? name,
    String? brand,
    String? model,
    DateTime? lastMaintenanceDate,
    int? maintenanceCycleMonths,
    String? notes,
  }) async {
    final response = await _apiClient.patch('/housing/appliances/$applianceId', data: {
      if (name != null) 'name': name,
      if (brand != null) 'brand': brand,
      if (model != null) 'model': model,
      if (lastMaintenanceDate != null) 'last_maintenance_date': lastMaintenanceDate.toIso8601String().split('T').first,
      if (maintenanceCycleMonths != null) 'maintenance_cycle_months': maintenanceCycleMonths,
      if (notes != null) 'notes': notes,
    });
    return ApplianceModel.fromJson(response as Map<String, dynamic>);
  }

  /// Delete an appliance
  Future<void> deleteAppliance(String applianceId) async {
    await _apiClient.delete('/housing/appliances/$applianceId');
  }

  /// Record appliance maintenance
  Future<void> recordMaintenance({
    required String applianceId,
    required DateTime maintenanceDate,
    String? content,
    double? cost,
    String? serviceProvider,
    String? notes,
  }) async {
    await _apiClient.post('/housing/appliances/$applianceId/maintenance', data: {
      'maintenance_date': maintenanceDate.toIso8601String().split('T').first,
      if (content != null) 'content': content,
      if (cost != null) 'cost': cost,
      if (serviceProvider != null) 'service_provider': serviceProvider,
      if (notes != null) 'notes': notes,
    });
  }

  String _feeCycleToString(PropertyFeeCycle cycle) {
    return switch (cycle) {
      PropertyFeeCycle.monthly => 'monthly',
      PropertyFeeCycle.quarterly => 'quarterly',
      PropertyFeeCycle.semiAnnual => 'semi_annual',
      PropertyFeeCycle.annual => 'annual',
    };
  }
}
