import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';
import '../../domain/entities/transaction.dart';
import '../../domain/repositories/finance_repository.dart';

// Events
abstract class FinanceEvent extends Equatable {
  const FinanceEvent();
  @override
  List<Object?> get props => [];
}

class FinanceLoadRequested extends FinanceEvent {
  final int year;
  final int month;

  const FinanceLoadRequested({required this.year, required this.month});

  @override
  List<Object?> get props => [year, month];
}

class TransactionCreateRequested extends FinanceEvent {
  final Transaction transaction;

  const TransactionCreateRequested(this.transaction);

  @override
  List<Object?> get props => [transaction];
}

class TransactionDeleteRequested extends FinanceEvent {
  final String transactionId;

  const TransactionDeleteRequested(this.transactionId);

  @override
  List<Object?> get props => [transactionId];
}

class TransactionUpdateRequested extends FinanceEvent {
  final String transactionId;
  final Transaction transaction;

  const TransactionUpdateRequested(this.transactionId, this.transaction);

  @override
  List<Object?> get props => [transactionId, transaction];
}

class MonthChanged extends FinanceEvent {
  final int year;
  final int month;

  const MonthChanged({required this.year, required this.month});

  @override
  List<Object?> get props => [year, month];
}

// States
abstract class FinanceState extends Equatable {
  const FinanceState();
  @override
  List<Object?> get props => [];
}

class FinanceInitial extends FinanceState {
  const FinanceInitial();
}

class FinanceLoading extends FinanceState {
  const FinanceLoading();
}

class FinanceLoaded extends FinanceState {
  final List<Transaction> transactions;
  final FinanceSummary? summary;
  final int year;
  final int month;

  const FinanceLoaded({
    required this.transactions,
    this.summary,
    required this.year,
    required this.month,
  });

  double get totalIncome => summary?.totalIncome ??
      transactions.where((t) => t.isIncome).fold(0.0, (sum, t) => sum + t.amount);

  double get totalExpense => summary?.totalExpense ??
      transactions.where((t) => t.isExpense).fold(0.0, (sum, t) => sum + t.amount);

  double get balance => totalIncome - totalExpense;

  double get savingRate => totalIncome > 0 ? (balance / totalIncome * 100) : 0;

  Map<TransactionCategory, double> get categoryBreakdown {
    if (summary?.categoryBreakdown != null) {
      return summary!.categoryBreakdown;
    }
    final breakdown = <TransactionCategory, double>{};
    for (final tx in transactions.where((t) => t.isExpense)) {
      breakdown[tx.category] = (breakdown[tx.category] ?? 0) + tx.amount;
    }
    return breakdown;
  }

  FinanceLoaded copyWith({
    List<Transaction>? transactions,
    FinanceSummary? summary,
    int? year,
    int? month,
  }) {
    return FinanceLoaded(
      transactions: transactions ?? this.transactions,
      summary: summary ?? this.summary,
      year: year ?? this.year,
      month: month ?? this.month,
    );
  }

  @override
  List<Object?> get props => [transactions, summary, year, month];
}

class FinanceError extends FinanceState {
  final String message;

  const FinanceError(this.message);

  @override
  List<Object?> get props => [message];
}

class FinanceOperationSuccess extends FinanceState {
  final String message;

  const FinanceOperationSuccess(this.message);

  @override
  List<Object?> get props => [message];
}

// BLoC
class FinanceBloc extends Bloc<FinanceEvent, FinanceState> {
  final FinanceRepository repository;

  FinanceBloc({required this.repository}) : super(const FinanceInitial()) {
    on<FinanceLoadRequested>(_onLoadRequested);
    on<TransactionCreateRequested>(_onCreateRequested);
    on<TransactionUpdateRequested>(_onUpdateRequested);
    on<TransactionDeleteRequested>(_onDeleteRequested);
    on<MonthChanged>(_onMonthChanged);
  }

  Future<void> _onLoadRequested(
    FinanceLoadRequested event,
    Emitter<FinanceState> emit,
  ) async {
    emit(const FinanceLoading());

    // Load transactions and summary in parallel
    final transactionsResult = await repository.getTransactions(
      year: event.year,
      month: event.month,
    );
    final summaryResult = await repository.getSummary(event.year, event.month);

    final transactions = transactionsResult.fold(
      (failure) => <Transaction>[],
      (data) => data,
    );

    final summary = summaryResult.fold(
      (failure) => null,
      (data) => data,
    );

    // Show actual data (empty if no transactions)
    emit(FinanceLoaded(
      transactions: transactions,
      summary: summary,
      year: event.year,
      month: event.month,
    ));
  }

  Future<void> _onCreateRequested(
    TransactionCreateRequested event,
    Emitter<FinanceState> emit,
  ) async {
    final currentState = state;
    if (currentState is! FinanceLoaded) return;

    final result = await repository.createTransaction(event.transaction);

    await result.fold(
      (failure) async {
        emit(FinanceError(failure.message));
        emit(currentState);
      },
      (transaction) async {
        emit(const FinanceOperationSuccess('交易添加成功'));
        // Reload data
        add(FinanceLoadRequested(year: currentState.year, month: currentState.month));
      },
    );
  }

  Future<void> _onUpdateRequested(
    TransactionUpdateRequested event,
    Emitter<FinanceState> emit,
  ) async {
    final currentState = state;
    if (currentState is! FinanceLoaded) return;

    final result = await repository.updateTransaction(event.transactionId, event.transaction);

    await result.fold(
      (failure) async {
        emit(FinanceError(failure.message));
        emit(currentState);
      },
      (transaction) async {
        emit(const FinanceOperationSuccess('交易更新成功'));
        // Reload data
        add(FinanceLoadRequested(year: currentState.year, month: currentState.month));
      },
    );
  }

  Future<void> _onDeleteRequested(
    TransactionDeleteRequested event,
    Emitter<FinanceState> emit,
  ) async {
    final currentState = state;
    if (currentState is! FinanceLoaded) return;

    final result = await repository.deleteTransaction(event.transactionId);

    await result.fold(
      (failure) async {
        emit(FinanceError(failure.message));
        emit(currentState);
      },
      (_) async {
        emit(const FinanceOperationSuccess('交易删除成功'));
        // Reload data
        add(FinanceLoadRequested(year: currentState.year, month: currentState.month));
      },
    );
  }

  Future<void> _onMonthChanged(
    MonthChanged event,
    Emitter<FinanceState> emit,
  ) async {
    add(FinanceLoadRequested(year: event.year, month: event.month));
  }
}
