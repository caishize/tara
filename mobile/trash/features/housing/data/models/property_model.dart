import '../../domain/entities/property.dart';

/// Property model for API serialization
class PropertyModel extends Property {
  const PropertyModel({
    required super.id,
    required super.familyId,
    required super.ownerId,
    required super.address,
    super.areaSqm,
    super.purchaseDate,
    super.mortgageBank,
    super.mortgageAmount,
    super.mortgageDay,
    super.mortgageAccount,
    super.propertyFeeAmount,
    super.propertyFeeCycle,
    super.propertyFeeDay,
    super.lastPropertyFeeDate,
    super.notes,
    required super.createdAt,
    required super.updatedAt,
  });

  factory PropertyModel.fromJson(Map<String, dynamic> json) {
    return PropertyModel(
      id: json['property_id'] as String? ?? '',
      familyId: json['family_id'] as String? ?? '',
      ownerId: json['owner_id'] as String? ?? '',
      address: json['address'] as String? ?? '',
      areaSqm: _parseDouble(json['area_sqm']),
      purchaseDate: json['purchase_date'] != null
          ? DateTime.parse(json['purchase_date'] as String)
          : null,
      mortgageBank: json['mortgage_bank'] as String?,
      mortgageAmount: _parseDouble(json['mortgage_amount']),
      mortgageDay: _parseInt(json['mortgage_day']),
      mortgageAccount: json['mortgage_account'] as String?,
      propertyFeeAmount: _parseDouble(json['property_fee_amount']),
      propertyFeeCycle: _parseFeeCycle(json['property_fee_cycle'] as String?),
      propertyFeeDay: _parseInt(json['property_fee_day']),
      lastPropertyFeeDate: json['last_property_fee_date'] != null
          ? DateTime.parse(json['last_property_fee_date'] as String)
          : null,
      notes: json['notes'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String? ?? DateTime.now().toIso8601String()),
      updatedAt: DateTime.parse(json['updated_at'] as String? ?? DateTime.now().toIso8601String()),
    );
  }

  /// Parse a value that could be String or num to double
  static double? _parseDouble(dynamic value) {
    if (value == null) return null;
    if (value is num) return value.toDouble();
    if (value is String) return double.tryParse(value);
    return null;
  }

  /// Parse a value that could be String or num to int
  static int? _parseInt(dynamic value) {
    if (value == null) return null;
    if (value is int) return value;
    if (value is num) return value.toInt();
    if (value is String) return int.tryParse(value);
    return null;
  }

  Map<String, dynamic> toJson() {
    return {
      'property_id': id,
      'family_id': familyId,
      'owner_id': ownerId,
      'address': address,
      if (areaSqm != null) 'area_sqm': areaSqm,
      if (purchaseDate != null) 'purchase_date': purchaseDate!.toIso8601String().split('T').first,
      if (mortgageBank != null) 'mortgage_bank': mortgageBank,
      if (mortgageAmount != null) 'mortgage_amount': mortgageAmount,
      if (mortgageDay != null) 'mortgage_day': mortgageDay,
      if (mortgageAccount != null) 'mortgage_account': mortgageAccount,
      if (propertyFeeAmount != null) 'property_fee_amount': propertyFeeAmount,
      if (propertyFeeCycle != null) 'property_fee_cycle': _feeCycleToString(propertyFeeCycle!),
      if (propertyFeeDay != null) 'property_fee_day': propertyFeeDay,
      if (notes != null) 'notes': notes,
    };
  }

  static PropertyFeeCycle? _parseFeeCycle(String? value) {
    if (value == null) return null;
    return switch (value) {
      'monthly' => PropertyFeeCycle.monthly,
      'quarterly' => PropertyFeeCycle.quarterly,
      'semi_annual' => PropertyFeeCycle.semiAnnual,
      'annual' => PropertyFeeCycle.annual,
      _ => null,
    };
  }

  static String _feeCycleToString(PropertyFeeCycle cycle) {
    return switch (cycle) {
      PropertyFeeCycle.monthly => 'monthly',
      PropertyFeeCycle.quarterly => 'quarterly',
      PropertyFeeCycle.semiAnnual => 'semi_annual',
      PropertyFeeCycle.annual => 'annual',
    };
  }
}

/// Mortgage payment model
class MortgagePaymentModel extends MortgagePayment {
  const MortgagePaymentModel({
    required super.id,
    required super.propertyId,
    required super.paymentDate,
    required super.amount,
    super.paymentMethod,
    super.notes,
    required super.createdAt,
  });

  factory MortgagePaymentModel.fromJson(Map<String, dynamic> json) {
    return MortgagePaymentModel(
      id: json['payment_id'] as String? ?? '',
      propertyId: json['property_id'] as String? ?? '',
      paymentDate: DateTime.parse(json['payment_date'] as String),
      amount: _parseAmount(json['amount']),
      paymentMethod: json['payment_method'] as String?,
      notes: json['notes'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String? ?? DateTime.now().toIso8601String()),
    );
  }

  static double _parseAmount(dynamic value) {
    if (value == null) return 0;
    if (value is num) return value.toDouble();
    if (value is String) return double.tryParse(value) ?? 0;
    return 0;
  }
}

/// Appliance model
class ApplianceModel extends Appliance {
  const ApplianceModel({
    required super.id,
    required super.propertyId,
    required super.name,
    super.brand,
    super.model,
    super.purchaseDate,
    super.warrantyExpiry,
    super.lastMaintenanceDate,
    super.nextMaintenanceDate,
    super.maintenanceCycleMonths = 12,
    super.isRetired = false,
    super.notes,
    required super.createdAt,
    required super.updatedAt,
  });

  factory ApplianceModel.fromJson(Map<String, dynamic> json) {
    return ApplianceModel(
      id: json['appliance_id'] as String? ?? '',
      propertyId: json['property_id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      brand: json['brand'] as String?,
      model: json['model'] as String?,
      purchaseDate: json['purchase_date'] != null
          ? DateTime.parse(json['purchase_date'] as String)
          : null,
      warrantyExpiry: json['warranty_expiry'] != null
          ? DateTime.parse(json['warranty_expiry'] as String)
          : null,
      lastMaintenanceDate: json['last_maintenance_date'] != null
          ? DateTime.parse(json['last_maintenance_date'] as String)
          : null,
      nextMaintenanceDate: json['next_maintenance_date'] != null
          ? DateTime.parse(json['next_maintenance_date'] as String)
          : null,
      maintenanceCycleMonths: json['maintenance_cycle_months'] as int? ?? 12,
      isRetired: json['is_retired'] as bool? ?? false,
      notes: json['notes'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String? ?? DateTime.now().toIso8601String()),
      updatedAt: DateTime.parse(json['updated_at'] as String? ?? DateTime.now().toIso8601String()),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'appliance_id': id,
      'property_id': propertyId,
      'name': name,
      if (brand != null) 'brand': brand,
      if (model != null) 'model': model,
      if (purchaseDate != null) 'purchase_date': purchaseDate!.toIso8601String().split('T').first,
      if (warrantyExpiry != null) 'warranty_expiry': warrantyExpiry!.toIso8601String().split('T').first,
      'maintenance_cycle_months': maintenanceCycleMonths,
      if (notes != null) 'notes': notes,
    };
  }
}
