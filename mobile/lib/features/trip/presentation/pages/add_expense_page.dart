import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../domain/entities/trip_expense.dart';
import '../bloc/trip_bloc.dart';

class AddExpensePage extends StatefulWidget {
  final String tripId;

  const AddExpensePage({super.key, required this.tripId});

  @override
  State<AddExpensePage> createState() => _AddExpensePageState();
}

class _AddExpensePageState extends State<AddExpensePage> {
  final _formKey = GlobalKey<FormState>();
  final _amountController = TextEditingController();
  final _descriptionController = TextEditingController();
  final _locationController = TextEditingController();

  ExpenseCategory _category = ExpenseCategory.food;
  DateTime _expenseDate = DateTime.now();
  String? _paymentMethod;
  bool _isLoading = false;

  final List<String> _paymentMethods = [
    '现金',
    '微信支付',
    '支付宝',
    '银行卡',
    '信用卡',
  ];

  @override
  void dispose() {
    _amountController.dispose();
    _descriptionController.dispose();
    _locationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocListener<TripBloc, TripState>(
      listener: (context, state) {
        if (state is TripDetailLoaded) {
          // Expense created successfully
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('支出记录已添加')),
          );
          context.pop();
        } else if (state is TripError) {
          setState(() => _isLoading = false);
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(state.message)),
          );
        }
      },
      child: Scaffold(
        appBar: AppBar(
          title: const Text('记录支出'),
        ),
        body: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // Amount (large input)
              Container(
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.primaryContainer.withValues(alpha: 0.3),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Column(
                  children: [
                    const Text(
                      '支出金额',
                      style: TextStyle(
                        fontSize: 14,
                        color: Colors.grey,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          '¥',
                          style: TextStyle(
                            fontSize: 24,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(width: 4),
                        SizedBox(
                          width: 150,
                          child: TextFormField(
                            controller: _amountController,
                            style: const TextStyle(
                              fontSize: 48,
                              fontWeight: FontWeight.bold,
                            ),
                            textAlign: TextAlign.center,
                            decoration: const InputDecoration(
                              hintText: '0',
                              border: InputBorder.none,
                              contentPadding: EdgeInsets.zero,
                            ),
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                            validator: (value) {
                              if (value == null || value.isEmpty) {
                                return '请输入金额';
                              }
                              if (double.tryParse(value) == null) {
                                return '请输入有效金额';
                              }
                              return null;
                            },
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),

              // Category selection
              const Text(
                '支出类别',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: ExpenseCategory.values.map((category) {
                  final isSelected = _category == category;
                  return ChoiceChip(
                    label: Text(_getCategoryName(category)),
                    avatar: Text(_getCategoryIcon(category)),
                    selected: isSelected,
                    onSelected: (selected) {
                      if (selected) {
                        setState(() => _category = category);
                      }
                    },
                  );
                }).toList(),
              ),
              const SizedBox(height: 24),

              // Date picker
              InkWell(
                onTap: _selectDate,
                child: InputDecorator(
                  decoration: const InputDecoration(
                    labelText: '消费日期',
                    prefixIcon: Icon(Icons.calendar_today),
                    border: OutlineInputBorder(),
                  ),
                  child: Text(
                    DateFormat('yyyy年MM月dd日').format(_expenseDate),
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Description
              TextFormField(
                controller: _descriptionController,
                decoration: const InputDecoration(
                  labelText: '备注说明',
                  hintText: '例如：午餐、景点门票',
                  prefixIcon: Icon(Icons.description),
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 16),

              // Location
              TextFormField(
                controller: _locationController,
                decoration: const InputDecoration(
                  labelText: '消费地点（可选）',
                  hintText: '例如：西湖景区',
                  prefixIcon: Icon(Icons.location_on),
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 16),

              // Payment method
              DropdownButtonFormField<String>(
                value: _paymentMethod,
                decoration: const InputDecoration(
                  labelText: '支付方式（可选）',
                  prefixIcon: Icon(Icons.payment),
                  border: OutlineInputBorder(),
                ),
                items: _paymentMethods
                    .map((method) => DropdownMenuItem(
                          value: method,
                          child: Text(method),
                        ))
                    .toList(),
                onChanged: (value) {
                  setState(() => _paymentMethod = value);
                },
              ),
              const SizedBox(height: 32),

              // Submit button
              ElevatedButton(
                onPressed: _isLoading ? null : _onSubmit,
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                ),
                child: _isLoading
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('保存'),
              ),

              // Quick add buttons
              const SizedBox(height: 24),
              const Text(
                '快速添加',
                style: TextStyle(
                  fontSize: 14,
                  color: Colors.grey,
                ),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  _QuickAddChip(
                    label: '门票 ¥80',
                    onTap: () => _quickAdd(ExpenseCategory.tickets, 80, '门票'),
                  ),
                  _QuickAddChip(
                    label: '午餐 ¥50',
                    onTap: () => _quickAdd(ExpenseCategory.food, 50, '午餐'),
                  ),
                  _QuickAddChip(
                    label: '晚餐 ¥100',
                    onTap: () => _quickAdd(ExpenseCategory.food, 100, '晚餐'),
                  ),
                  _QuickAddChip(
                    label: '出租车 ¥30',
                    onTap: () => _quickAdd(ExpenseCategory.transportation, 30, '出租车'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _selectDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _expenseDate,
      firstDate: DateTime.now().subtract(const Duration(days: 365)),
      lastDate: DateTime.now(),
    );
    if (picked != null) {
      setState(() => _expenseDate = picked);
    }
  }

  void _quickAdd(ExpenseCategory category, double amount, String description) {
    setState(() {
      _category = category;
      _amountController.text = amount.toString();
      _descriptionController.text = description;
    });
    _onSubmit();
  }

  void _onSubmit() {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isLoading = true);

    final expense = TripExpense(
      id: '',
      tripId: widget.tripId,
      category: _category,
      amount: double.parse(_amountController.text),
      expenseDate: _expenseDate,
      description: _descriptionController.text.isEmpty ? null : _descriptionController.text,
      location: _locationController.text.isEmpty ? null : _locationController.text,
      paymentMethod: _paymentMethod,
      createdAt: DateTime.now(),
      updatedAt: DateTime.now(),
    );

    context.read<TripBloc>().add(
      ExpenseCreateRequested(widget.tripId, expense),
    );
  }

  String _getCategoryName(ExpenseCategory category) {
    switch (category) {
      case ExpenseCategory.transportation:
        return '交通';
      case ExpenseCategory.accommodation:
        return '住宿';
      case ExpenseCategory.tickets:
        return '门票';
      case ExpenseCategory.food:
        return '餐饮';
      case ExpenseCategory.shopping:
        return '购物';
      case ExpenseCategory.other:
        return '其他';
    }
  }

  String _getCategoryIcon(ExpenseCategory category) {
    switch (category) {
      case ExpenseCategory.transportation:
        return '🚗';
      case ExpenseCategory.accommodation:
        return '🏨';
      case ExpenseCategory.tickets:
        return '🎟️';
      case ExpenseCategory.food:
        return '🍽️';
      case ExpenseCategory.shopping:
        return '🛍️';
      case ExpenseCategory.other:
        return '💰';
    }
  }
}

class _QuickAddChip extends StatelessWidget {
  final String label;
  final VoidCallback onTap;

  const _QuickAddChip({
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return ActionChip(
      label: Text(label),
      onPressed: onTap,
    );
  }
}
