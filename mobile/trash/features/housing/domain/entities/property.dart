import 'package:equatable/equatable.dart';

/// Property fee payment cycle
enum PropertyFeeCycle {
  monthly,
  quarterly,
  semiAnnual,
  annual,
}

/// Property entity (房产)
class Property extends Equatable {
  final String id;
  final String familyId;
  final String ownerId;
  final String address;
  final double? areaSqm;
  final DateTime? purchaseDate;

  // Mortgage info
  final String? mortgageBank;
  final double? mortgageAmount;
  final int? mortgageDay;
  final String? mortgageAccount;

  // Property fee info
  final double? propertyFeeAmount;
  final PropertyFeeCycle? propertyFeeCycle;
  final int? propertyFeeDay;
  final DateTime? lastPropertyFeeDate;

  final String? notes;
  final DateTime createdAt;
  final DateTime updatedAt;

  const Property({
    required this.id,
    required this.familyId,
    required this.ownerId,
    required this.address,
    this.areaSqm,
    this.purchaseDate,
    this.mortgageBank,
    this.mortgageAmount,
    this.mortgageDay,
    this.mortgageAccount,
    this.propertyFeeAmount,
    this.propertyFeeCycle,
    this.propertyFeeDay,
    this.lastPropertyFeeDate,
    this.notes,
    required this.createdAt,
    required this.updatedAt,
  });

  /// Display formatted area
  String get areaDisplay => areaSqm != null ? '${areaSqm!.toStringAsFixed(0)}㎡' : '未知';

  /// Display formatted mortgage amount
  String get mortgageDisplay => mortgageAmount != null
      ? '${mortgageAmount!.toStringAsFixed(0)}元/月'
      : '无贷款';

  /// Display formatted mortgage amount (alias)
  String get displayMortgageAmount {
    if (mortgageAmount == null) return '无贷款';
    if (mortgageAmount! >= 10000) {
      return '${(mortgageAmount! / 10000).toStringAsFixed(1)}万元';
    }
    return '${mortgageAmount!.toStringAsFixed(0)}元';
  }

  /// Display formatted property fee
  String get propertyFeeDisplay {
    if (propertyFeeAmount == null) return '未设置';
    final cycle = switch (propertyFeeCycle) {
      PropertyFeeCycle.monthly => '/月',
      PropertyFeeCycle.quarterly => '/季',
      PropertyFeeCycle.semiAnnual => '/半年',
      PropertyFeeCycle.annual => '/年',
      null => '',
    };
    return '${propertyFeeAmount!.toStringAsFixed(0)}元$cycle';
  }

  /// Display formatted property fee (alias)
  String get displayPropertyFee {
    if (propertyFeeAmount == null) return '未设置';
    return '${propertyFeeAmount!.toStringAsFixed(0)}元';
  }

  /// Display fee cycle
  String get displayFeeCycle {
    return switch (propertyFeeCycle) {
      PropertyFeeCycle.monthly => '每月',
      PropertyFeeCycle.quarterly => '每季度',
      PropertyFeeCycle.semiAnnual => '每半年',
      PropertyFeeCycle.annual => '每年',
      null => '未设置',
    };
  }

  @override
  List<Object?> get props => [
    id, familyId, ownerId, address, areaSqm, purchaseDate,
    mortgageBank, mortgageAmount, mortgageDay, mortgageAccount,
    propertyFeeAmount, propertyFeeCycle, propertyFeeDay, lastPropertyFeeDate,
    notes, createdAt, updatedAt,
  ];
}

/// Mortgage payment record
class MortgagePayment extends Equatable {
  final String id;
  final String propertyId;
  final DateTime paymentDate;
  final double amount;
  final String? paymentMethod;
  final String? notes;
  final DateTime createdAt;

  const MortgagePayment({
    required this.id,
    required this.propertyId,
    required this.paymentDate,
    required this.amount,
    this.paymentMethod,
    this.notes,
    required this.createdAt,
  });

  @override
  List<Object?> get props => [id, propertyId, paymentDate, amount, paymentMethod, notes, createdAt];
}

/// Appliance entity (家电)
class Appliance extends Equatable {
  final String id;
  final String propertyId;
  final String name;
  final String? brand;
  final String? model;
  final DateTime? purchaseDate;
  final DateTime? warrantyExpiry;
  final DateTime? lastMaintenanceDate;
  final DateTime? nextMaintenanceDate;
  final int maintenanceCycleMonths;
  final bool isRetired;
  final String? notes;
  final DateTime createdAt;
  final DateTime updatedAt;

  const Appliance({
    required this.id,
    required this.propertyId,
    required this.name,
    this.brand,
    this.model,
    this.purchaseDate,
    this.warrantyExpiry,
    this.lastMaintenanceDate,
    this.nextMaintenanceDate,
    this.maintenanceCycleMonths = 12,
    this.isRetired = false,
    this.notes,
    required this.createdAt,
    required this.updatedAt,
  });

  /// Whether warranty is still valid
  bool get isUnderWarranty => warrantyExpiry != null && warrantyExpiry!.isAfter(DateTime.now());

  /// Whether warranty has expired (alias)
  bool get warrantyExpired => warrantyExpiry != null && warrantyExpiry!.isBefore(DateTime.now());

  /// Whether maintenance is due
  bool get isMaintenanceDue =>
      nextMaintenanceDate != null && nextMaintenanceDate!.isBefore(DateTime.now());

  /// Whether maintenance is needed (alias)
  bool get needsMaintenance => isMaintenanceDue;

  /// Days until next maintenance
  int? get daysUntilMaintenance {
    if (nextMaintenanceDate == null) return null;
    return nextMaintenanceDate!.difference(DateTime.now()).inDays;
  }

  @override
  List<Object?> get props => [
    id, propertyId, name, brand, model, purchaseDate, warrantyExpiry,
    lastMaintenanceDate, nextMaintenanceDate, maintenanceCycleMonths,
    isRetired, notes, createdAt, updatedAt,
  ];
}
