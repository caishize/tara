import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/property.dart';
import '../bloc/housing_bloc.dart';

class AddPropertySheet extends StatefulWidget {
  const AddPropertySheet({super.key});

  @override
  State<AddPropertySheet> createState() => _AddPropertySheetState();
}

class _AddPropertySheetState extends State<AddPropertySheet> {
  final _formKey = GlobalKey<FormState>();
  final _addressController = TextEditingController();
  final _areaController = TextEditingController();
  final _mortgageBankController = TextEditingController();
  final _mortgageAmountController = TextEditingController();
  final _mortgageDayController = TextEditingController();
  final _propertyFeeController = TextEditingController();
  final _propertyFeeDayController = TextEditingController();
  final _notesController = TextEditingController();

  DateTime? _purchaseDate;
  PropertyFeeCycle? _feeCycle;
  bool _hasMortgage = false;
  bool _hasPropertyFee = false;

  @override
  void dispose() {
    _addressController.dispose();
    _areaController.dispose();
    _mortgageBankController.dispose();
    _mortgageAmountController.dispose();
    _mortgageDayController.dispose();
    _propertyFeeController.dispose();
    _propertyFeeDayController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).viewInsets.bottom,
      ),
      child: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Form(
            key: _formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Handle bar
                Center(
                  child: Container(
                    width: 40,
                    height: 4,
                    decoration: BoxDecoration(
                      color: AppColors.textSecondary.withValues(alpha: 0.3),
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                ),
                const SizedBox(height: 16),

                // Title
                Text('添加房产', style: AppTextStyles.headline6),
                const SizedBox(height: 20),

                // Address field (required)
                TextFormField(
                  controller: _addressController,
                  decoration: const InputDecoration(
                    labelText: '房产地址 *',
                    hintText: '请输入完整地址',
                    prefixIcon: Icon(Icons.location_on_outlined),
                  ),
                  validator: (value) {
                    if (value == null || value.trim().isEmpty) {
                      return '请输入房产地址';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 16),

                // Area field
                TextFormField(
                  controller: _areaController,
                  decoration: const InputDecoration(
                    labelText: '面积 (平方米)',
                    hintText: '例如: 120',
                    prefixIcon: Icon(Icons.square_foot),
                  ),
                  keyboardType: TextInputType.number,
                ),
                const SizedBox(height: 16),

                // Purchase date
                InkWell(
                  onTap: () => _selectPurchaseDate(context),
                  child: InputDecorator(
                    decoration: const InputDecoration(
                      labelText: '入住日期',
                      prefixIcon: Icon(Icons.calendar_today),
                    ),
                    child: Text(
                      _purchaseDate != null
                          ? '${_purchaseDate!.year}-${_purchaseDate!.month.toString().padLeft(2, '0')}-${_purchaseDate!.day.toString().padLeft(2, '0')}'
                          : '选择日期',
                      style: TextStyle(
                        color: _purchaseDate != null
                            ? AppColors.textPrimary
                            : AppColors.textSecondary,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 20),

                // Mortgage section
                SwitchListTile(
                  title: const Text('有房贷'),
                  value: _hasMortgage,
                  onChanged: (value) => setState(() => _hasMortgage = value),
                  contentPadding: EdgeInsets.zero,
                ),

                if (_hasMortgage) ...[
                  TextFormField(
                    controller: _mortgageBankController,
                    decoration: const InputDecoration(
                      labelText: '贷款银行',
                      hintText: '例如: 招商银行',
                      prefixIcon: Icon(Icons.account_balance),
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: _mortgageAmountController,
                    decoration: const InputDecoration(
                      labelText: '贷款金额 (元)',
                      hintText: '例如: 1500000',
                      prefixIcon: Icon(Icons.attach_money),
                    ),
                    keyboardType: TextInputType.number,
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: _mortgageDayController,
                    decoration: const InputDecoration(
                      labelText: '还款日 (每月几号)',
                      hintText: '例如: 15',
                      prefixIcon: Icon(Icons.event),
                    ),
                    keyboardType: TextInputType.number,
                  ),
                  const SizedBox(height: 20),
                ],

                // Property fee section
                SwitchListTile(
                  title: const Text('有物业费'),
                  value: _hasPropertyFee,
                  onChanged: (value) => setState(() => _hasPropertyFee = value),
                  contentPadding: EdgeInsets.zero,
                ),

                if (_hasPropertyFee) ...[
                  TextFormField(
                    controller: _propertyFeeController,
                    decoration: const InputDecoration(
                      labelText: '物业费金额 (元)',
                      hintText: '例如: 500',
                      prefixIcon: Icon(Icons.receipt_long),
                    ),
                    keyboardType: TextInputType.number,
                  ),
                  const SizedBox(height: 16),
                  DropdownButtonFormField<PropertyFeeCycle>(
                    decoration: const InputDecoration(
                      labelText: '缴费周期',
                      prefixIcon: Icon(Icons.repeat),
                    ),
                    value: _feeCycle,
                    items: const [
                      DropdownMenuItem(
                        value: PropertyFeeCycle.monthly,
                        child: Text('每月'),
                      ),
                      DropdownMenuItem(
                        value: PropertyFeeCycle.quarterly,
                        child: Text('每季度'),
                      ),
                      DropdownMenuItem(
                        value: PropertyFeeCycle.semiAnnual,
                        child: Text('每半年'),
                      ),
                      DropdownMenuItem(
                        value: PropertyFeeCycle.annual,
                        child: Text('每年'),
                      ),
                    ],
                    onChanged: (value) => setState(() => _feeCycle = value),
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: _propertyFeeDayController,
                    decoration: const InputDecoration(
                      labelText: '缴费日 (每周期几号)',
                      hintText: '例如: 1',
                      prefixIcon: Icon(Icons.event),
                    ),
                    keyboardType: TextInputType.number,
                  ),
                  const SizedBox(height: 20),
                ],

                // Notes
                TextFormField(
                  controller: _notesController,
                  decoration: const InputDecoration(
                    labelText: '备注',
                    hintText: '可选备注信息',
                    prefixIcon: Icon(Icons.note),
                  ),
                  maxLines: 2,
                ),
                const SizedBox(height: 24),

                // Submit button
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _submit,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.primary,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: const Text('添加房产'),
                  ),
                ),
                const SizedBox(height: 16),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _selectPurchaseDate(BuildContext context) async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _purchaseDate ?? DateTime.now(),
      firstDate: DateTime(1990),
      lastDate: DateTime.now(),
    );
    if (picked != null) {
      setState(() => _purchaseDate = picked);
    }
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) return;

    final address = _addressController.text.trim();
    final area = double.tryParse(_areaController.text.trim());
    final mortgageBank = _hasMortgage ? _mortgageBankController.text.trim() : null;
    final mortgageAmount = _hasMortgage
        ? double.tryParse(_mortgageAmountController.text.trim())
        : null;
    final mortgageDay = _hasMortgage
        ? int.tryParse(_mortgageDayController.text.trim())
        : null;
    final propertyFee = _hasPropertyFee
        ? double.tryParse(_propertyFeeController.text.trim())
        : null;
    final propertyFeeDay = _hasPropertyFee
        ? int.tryParse(_propertyFeeDayController.text.trim())
        : null;
    final notes = _notesController.text.trim().isNotEmpty
        ? _notesController.text.trim()
        : null;

    context.read<HousingBloc>().add(PropertyCreateRequested(
      address: address,
      areaSqm: area,
      purchaseDate: _purchaseDate,
      mortgageBank: mortgageBank?.isNotEmpty == true ? mortgageBank : null,
      mortgageAmount: mortgageAmount,
      mortgageDay: mortgageDay,
      propertyFeeAmount: propertyFee,
      propertyFeeCycle: _hasPropertyFee ? _feeCycle : null,
      propertyFeeDay: propertyFeeDay,
      notes: notes,
    ));

    Navigator.of(context).pop();
  }
}
