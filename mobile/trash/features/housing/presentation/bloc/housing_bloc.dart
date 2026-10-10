import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';
import '../../domain/entities/property.dart';
import '../../domain/repositories/housing_repository.dart';

// Events
abstract class HousingEvent extends Equatable {
  const HousingEvent();
  @override
  List<Object?> get props => [];
}

class HousingLoadRequested extends HousingEvent {
  const HousingLoadRequested();
}

class PropertySelected extends HousingEvent {
  final String propertyId;
  const PropertySelected(this.propertyId);
  @override
  List<Object?> get props => [propertyId];
}

class PropertyCreateRequested extends HousingEvent {
  final String address;
  final double? areaSqm;
  final DateTime? purchaseDate;
  final String? mortgageBank;
  final double? mortgageAmount;
  final int? mortgageDay;
  final double? propertyFeeAmount;
  final PropertyFeeCycle? propertyFeeCycle;
  final int? propertyFeeDay;
  final String? notes;

  const PropertyCreateRequested({
    required this.address,
    this.areaSqm,
    this.purchaseDate,
    this.mortgageBank,
    this.mortgageAmount,
    this.mortgageDay,
    this.propertyFeeAmount,
    this.propertyFeeCycle,
    this.propertyFeeDay,
    this.notes,
  });

  @override
  List<Object?> get props => [address, areaSqm, purchaseDate, mortgageBank, mortgageAmount, mortgageDay, propertyFeeAmount, propertyFeeCycle, propertyFeeDay, notes];
}

class PropertyDeleteRequested extends HousingEvent {
  final String propertyId;
  const PropertyDeleteRequested(this.propertyId);
  @override
  List<Object?> get props => [propertyId];
}

class AppliancesLoadRequested extends HousingEvent {
  final String propertyId;
  const AppliancesLoadRequested(this.propertyId);
  @override
  List<Object?> get props => [propertyId];
}

class ApplianceCreateRequested extends HousingEvent {
  final String propertyId;
  final String name;
  final String? brand;
  final String? model;
  final DateTime? purchaseDate;
  final DateTime? warrantyExpiry;
  final int maintenanceCycleMonths;
  final String? notes;

  const ApplianceCreateRequested({
    required this.propertyId,
    required this.name,
    this.brand,
    this.model,
    this.purchaseDate,
    this.warrantyExpiry,
    this.maintenanceCycleMonths = 12,
    this.notes,
  });

  @override
  List<Object?> get props => [propertyId, name, brand, model, purchaseDate, warrantyExpiry, maintenanceCycleMonths, notes];
}

class MaintenanceRecordRequested extends HousingEvent {
  final String applianceId;
  final DateTime maintenanceDate;
  final String? content;
  final double? cost;
  final String? serviceProvider;
  final String? notes;

  const MaintenanceRecordRequested({
    required this.applianceId,
    required this.maintenanceDate,
    this.content,
    this.cost,
    this.serviceProvider,
    this.notes,
  });

  @override
  List<Object?> get props => [applianceId, maintenanceDate, content, cost, serviceProvider, notes];
}

// States
abstract class HousingState extends Equatable {
  const HousingState();
  @override
  List<Object?> get props => [];
}

class HousingInitial extends HousingState {
  const HousingInitial();
}

class HousingLoading extends HousingState {
  const HousingLoading();
}

class HousingLoaded extends HousingState {
  final List<Property> properties;
  final Property? selectedProperty;
  final List<Appliance> appliances;
  final List<MortgagePayment> mortgagePayments;

  const HousingLoaded({
    required this.properties,
    this.selectedProperty,
    this.appliances = const [],
    this.mortgagePayments = const [],
  });

  HousingLoaded copyWith({
    List<Property>? properties,
    Property? selectedProperty,
    List<Appliance>? appliances,
    List<MortgagePayment>? mortgagePayments,
  }) {
    return HousingLoaded(
      properties: properties ?? this.properties,
      selectedProperty: selectedProperty ?? this.selectedProperty,
      appliances: appliances ?? this.appliances,
      mortgagePayments: mortgagePayments ?? this.mortgagePayments,
    );
  }

  @override
  List<Object?> get props => [properties, selectedProperty, appliances, mortgagePayments];
}

class HousingError extends HousingState {
  final String message;
  const HousingError(this.message);
  @override
  List<Object?> get props => [message];
}

class HousingOperationSuccess extends HousingState {
  final String message;
  const HousingOperationSuccess(this.message);
  @override
  List<Object?> get props => [message];
}

// BLoC
class HousingBloc extends Bloc<HousingEvent, HousingState> {
  final HousingRepository repository;

  HousingBloc({required this.repository}) : super(const HousingInitial()) {
    on<HousingLoadRequested>(_onLoadRequested);
    on<PropertySelected>(_onPropertySelected);
    on<PropertyCreateRequested>(_onPropertyCreate);
    on<PropertyDeleteRequested>(_onPropertyDelete);
    on<AppliancesLoadRequested>(_onAppliancesLoad);
    on<ApplianceCreateRequested>(_onApplianceCreate);
    on<MaintenanceRecordRequested>(_onMaintenanceRecord);
  }

  Future<void> _onLoadRequested(
    HousingLoadRequested event,
    Emitter<HousingState> emit,
  ) async {
    emit(const HousingLoading());

    final result = await repository.getProperties();

    result.fold(
      (failure) => emit(HousingError(failure.message)),
      (properties) {
        final selected = properties.isNotEmpty ? properties.first : null;
        emit(HousingLoaded(
          properties: properties,
          selectedProperty: selected,
        ));

        // Load appliances for selected property
        if (selected != null) {
          add(AppliancesLoadRequested(selected.id));
        }
      },
    );
  }

  Future<void> _onPropertySelected(
    PropertySelected event,
    Emitter<HousingState> emit,
  ) async {
    final currentState = state;
    if (currentState is! HousingLoaded) return;

    final selected = currentState.properties.where((p) => p.id == event.propertyId).firstOrNull;
    if (selected != null) {
      emit(currentState.copyWith(selectedProperty: selected, appliances: []));
      add(AppliancesLoadRequested(selected.id));
    }
  }

  Future<void> _onPropertyCreate(
    PropertyCreateRequested event,
    Emitter<HousingState> emit,
  ) async {
    final result = await repository.createProperty(
      address: event.address,
      areaSqm: event.areaSqm,
      purchaseDate: event.purchaseDate,
      mortgageBank: event.mortgageBank,
      mortgageAmount: event.mortgageAmount,
      mortgageDay: event.mortgageDay,
      propertyFeeAmount: event.propertyFeeAmount,
      propertyFeeCycle: event.propertyFeeCycle,
      propertyFeeDay: event.propertyFeeDay,
      notes: event.notes,
    );

    result.fold(
      (failure) => emit(HousingError(failure.message)),
      (property) {
        emit(const HousingOperationSuccess('房产添加成功'));
        add(const HousingLoadRequested());
      },
    );
  }

  Future<void> _onPropertyDelete(
    PropertyDeleteRequested event,
    Emitter<HousingState> emit,
  ) async {
    final result = await repository.deleteProperty(event.propertyId);

    result.fold(
      (failure) => emit(HousingError(failure.message)),
      (_) {
        emit(const HousingOperationSuccess('房产删除成功'));
        add(const HousingLoadRequested());
      },
    );
  }

  Future<void> _onAppliancesLoad(
    AppliancesLoadRequested event,
    Emitter<HousingState> emit,
  ) async {
    final currentState = state;
    if (currentState is! HousingLoaded) return;

    final result = await repository.getAppliances(event.propertyId);

    result.fold(
      (failure) => {}, // Silent fail for appliances
      (appliances) => emit(currentState.copyWith(appliances: appliances)),
    );
  }

  Future<void> _onApplianceCreate(
    ApplianceCreateRequested event,
    Emitter<HousingState> emit,
  ) async {
    final result = await repository.createAppliance(
      propertyId: event.propertyId,
      name: event.name,
      brand: event.brand,
      model: event.model,
      purchaseDate: event.purchaseDate,
      warrantyExpiry: event.warrantyExpiry,
      maintenanceCycleMonths: event.maintenanceCycleMonths,
      notes: event.notes,
    );

    result.fold(
      (failure) => emit(HousingError(failure.message)),
      (appliance) {
        emit(const HousingOperationSuccess('家电添加成功'));
        add(AppliancesLoadRequested(event.propertyId));
      },
    );
  }

  Future<void> _onMaintenanceRecord(
    MaintenanceRecordRequested event,
    Emitter<HousingState> emit,
  ) async {
    final currentState = state;
    if (currentState is! HousingLoaded) return;

    final result = await repository.recordMaintenance(
      applianceId: event.applianceId,
      maintenanceDate: event.maintenanceDate,
      content: event.content,
      cost: event.cost,
      serviceProvider: event.serviceProvider,
      notes: event.notes,
    );

    result.fold(
      (failure) => emit(HousingError(failure.message)),
      (_) {
        emit(const HousingOperationSuccess('维护记录添加成功'));
        if (currentState.selectedProperty != null) {
          add(AppliancesLoadRequested(currentState.selectedProperty!.id));
        }
      },
    );
  }
}
