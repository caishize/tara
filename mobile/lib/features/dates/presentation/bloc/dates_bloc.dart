import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';
import '../../domain/entities/important_date.dart';
import '../../domain/usecases/get_dates_usecase.dart';

// Events
abstract class DatesEvent extends Equatable {
  const DatesEvent();
  @override
  List<Object?> get props => [];
}

class DatesLoadRequested extends DatesEvent {
  final String? memberId;
  final DateType? dateType;

  const DatesLoadRequested({this.memberId, this.dateType});

  @override
  List<Object?> get props => [memberId, dateType];
}

class UpcomingDatesLoadRequested extends DatesEvent {
  final int daysAhead;

  const UpcomingDatesLoadRequested({this.daysAhead = 30});

  @override
  List<Object?> get props => [daysAhead];
}

class DateCreated extends DatesEvent {
  final ImportantDate date;

  const DateCreated(this.date);

  @override
  List<Object?> get props => [date];
}

class DateUpdated extends DatesEvent {
  final ImportantDate date;

  const DateUpdated(this.date);

  @override
  List<Object?> get props => [date];
}

class DateDeleted extends DatesEvent {
  final String id;

  const DateDeleted(this.id);

  @override
  List<Object?> get props => [id];
}

// States
abstract class DatesState extends Equatable {
  const DatesState();
  @override
  List<Object?> get props => [];
}

class DatesInitial extends DatesState {
  const DatesInitial();
}

class DatesLoading extends DatesState {
  const DatesLoading();
}

class DatesLoaded extends DatesState {
  final List<ImportantDate> dates;
  final List<ImportantDate> upcomingDates;

  const DatesLoaded({
    required this.dates,
    this.upcomingDates = const [],
  });

  DatesLoaded copyWith({
    List<ImportantDate>? dates,
    List<ImportantDate>? upcomingDates,
  }) {
    return DatesLoaded(
      dates: dates ?? this.dates,
      upcomingDates: upcomingDates ?? this.upcomingDates,
    );
  }

  /// 按日期类型分组
  Map<DateType, List<ImportantDate>> get datesByType {
    final result = <DateType, List<ImportantDate>>{};
    for (final date in dates) {
      result.putIfAbsent(date.dateType, () => []).add(date);
    }
    return result;
  }

  /// 获取今天的日期
  List<ImportantDate> get todayDates =>
      dates.where((d) => d.isToday).toList();

  /// 获取本周的日期(7天内)
  List<ImportantDate> get thisWeekDates =>
      dates.where((d) => d.isUpcoming).toList();

  @override
  List<Object?> get props => [dates, upcomingDates];
}

class DatesError extends DatesState {
  final String message;
  const DatesError(this.message);
  @override
  List<Object?> get props => [message];
}

class DateOperationSuccess extends DatesState {
  final String message;
  final DatesLoaded previousState;

  const DateOperationSuccess({
    required this.message,
    required this.previousState,
  });

  @override
  List<Object?> get props => [message, previousState];
}

// BLoC
class DatesBloc extends Bloc<DatesEvent, DatesState> {
  final GetDatesUseCase getDatesUseCase;
  final GetUpcomingDatesUseCase getUpcomingDatesUseCase;
  final CreateDateUseCase createDateUseCase;
  final UpdateDateUseCase updateDateUseCase;
  final DeleteDateUseCase deleteDateUseCase;

  DatesBloc({
    required this.getDatesUseCase,
    required this.getUpcomingDatesUseCase,
    required this.createDateUseCase,
    required this.updateDateUseCase,
    required this.deleteDateUseCase,
  }) : super(const DatesInitial()) {
    on<DatesLoadRequested>(_onLoadRequested);
    on<UpcomingDatesLoadRequested>(_onUpcomingLoadRequested);
    on<DateCreated>(_onDateCreated);
    on<DateUpdated>(_onDateUpdated);
    on<DateDeleted>(_onDateDeleted);
  }

  Future<void> _onLoadRequested(
    DatesLoadRequested event,
    Emitter<DatesState> emit,
  ) async {
    emit(const DatesLoading());

    final result = await getDatesUseCase(
      memberId: event.memberId,
      dateType: event.dateType,
    );

    await result.fold(
      (failure) async => emit(DatesError(failure.message)),
      (dates) async {
        // 同时加载即将到来的日期
        final upcomingResult = await getUpcomingDatesUseCase(daysAhead: 30);
        final upcomingDates = upcomingResult.fold(
          (failure) => <ImportantDate>[],
          (dates) => dates,
        );

        emit(DatesLoaded(
          dates: dates,
          upcomingDates: upcomingDates,
        ));
      },
    );
  }

  Future<void> _onUpcomingLoadRequested(
    UpcomingDatesLoadRequested event,
    Emitter<DatesState> emit,
  ) async {
    final currentState = state;
    if (currentState is DatesLoaded) {
      final result = await getUpcomingDatesUseCase(daysAhead: event.daysAhead);
      result.fold(
        (failure) => emit(DatesError(failure.message)),
        (upcomingDates) => emit(currentState.copyWith(
          upcomingDates: upcomingDates,
        )),
      );
    }
  }

  Future<void> _onDateCreated(
    DateCreated event,
    Emitter<DatesState> emit,
  ) async {
    final currentState = state;
    if (currentState is! DatesLoaded) return;

    emit(const DatesLoading());

    final result = await createDateUseCase(event.date);
    result.fold(
      (failure) => emit(DatesError(failure.message)),
      (newDate) {
        final updatedDates = [...currentState.dates, newDate];
        emit(DateOperationSuccess(
          message: '日期添加成功',
          previousState: currentState.copyWith(dates: updatedDates),
        ));
        // 返回到正常状态
        emit(currentState.copyWith(dates: updatedDates));
      },
    );
  }

  Future<void> _onDateUpdated(
    DateUpdated event,
    Emitter<DatesState> emit,
  ) async {
    final currentState = state;
    if (currentState is! DatesLoaded) return;

    emit(const DatesLoading());

    final result = await updateDateUseCase(event.date);
    result.fold(
      (failure) => emit(DatesError(failure.message)),
      (updatedDate) {
        final updatedDates = currentState.dates.map((d) {
          return d.id == updatedDate.id ? updatedDate : d;
        }).toList();
        emit(DateOperationSuccess(
          message: '日期更新成功',
          previousState: currentState.copyWith(dates: updatedDates),
        ));
        emit(currentState.copyWith(dates: updatedDates));
      },
    );
  }

  Future<void> _onDateDeleted(
    DateDeleted event,
    Emitter<DatesState> emit,
  ) async {
    final currentState = state;
    if (currentState is! DatesLoaded) return;

    emit(const DatesLoading());

    final result = await deleteDateUseCase(event.id);
    result.fold(
      (failure) => emit(DatesError(failure.message)),
      (_) {
        final updatedDates = currentState.dates
            .where((d) => d.id != event.id)
            .toList();
        emit(DateOperationSuccess(
          message: '日期删除成功',
          previousState: currentState.copyWith(dates: updatedDates),
        ));
        emit(currentState.copyWith(dates: updatedDates));
      },
    );
  }
}
