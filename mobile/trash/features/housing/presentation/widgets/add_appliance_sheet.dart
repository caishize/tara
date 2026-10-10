import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../bloc/housing_bloc.dart';

class AddApplianceSheet extends StatefulWidget {
  final String propertyId;

  const AddApplianceSheet({
    super.key,
    required this.propertyId,
  });

  @override
  State<AddApplianceSheet> createState() => _AddApplianceSheetState();
}

class _AddApplianceSheetState extends State<AddApplianceSheet> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _brandController = TextEditingController();
  final _modelController = TextEditingController();
  final _notesController = TextEditingController();

  DateTime? _purchaseDate;
  DateTime? _warrantyExpiry;
  int _maintenanceCycle = 12;

  final List<Map<String, dynamic>> _commonAppliances = [
    {'name': '空调', 'icon': Icons.ac_unit},
    {'name': '冰箱', 'icon': Icons.kitchen},
    {'name': '洗衣机', 'icon': Icons.local_laundry_service},
    {'name': '热水器', 'icon': Icons.hot_tub},
    {'name': '净水器', 'icon': Icons.water_drop},
    {'name': '油烟机', 'icon': Icons.blur_on},
    {'name': '燃气灶', 'icon': Icons.whatshot},
    {'name': '微波炉', 'icon': Icons.microwave},
  ];

  @override
  void dispose() {
    _nameController.dispose();
    _brandController.dispose();
    _modelController.dispose();
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
                Text('添加家电', style: AppTextStyles.headline6),
                const SizedBox(height: 16),

                // Quick selection
                Text('快速选择', style: AppTextStyles.subtitle2),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: _commonAppliances.map((appliance) {
                    return ActionChip(
                      avatar: Icon(appliance['icon'] as IconData, size: 18),
                      label: Text(appliance['name'] as String),
                      onPressed: () {
                        _nameController.text = appliance['name'] as String;
                      },
                    );
                  }).toList(),
                ),
                const SizedBox(height: 20),

                // Name field (required)
                TextFormField(
                  controller: _nameController,
                  decoration: const InputDecoration(
                    labelText: '设备名称 *',
                    hintText: '例如: 客厅空调',
                    prefixIcon: Icon(Icons.devices),
                  ),
                  validator: (value) {
                    if (value == null || value.trim().isEmpty) {
                      return '请输入设备名称';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 16),

                // Brand and model in a row
                Row(
                  children: [
                    Expanded(
                      child: TextFormField(
                        controller: _brandController,
                        decoration: const InputDecoration(
                          labelText: '品牌',
                          hintText: '例如: 格力',
                        ),
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: TextFormField(
                        controller: _modelController,
                        decoration: const InputDecoration(
                          labelText: '型号',
                          hintText: '例如: KFR-35',
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),

                // Purchase date
                InkWell(
                  onTap: () => _selectPurchaseDate(context),
                  child: InputDecorator(
                    decoration: const InputDecoration(
                      labelText: '购买日期',
                      prefixIcon: Icon(Icons.shopping_cart),
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
                const SizedBox(height: 16),

                // Warranty expiry
                InkWell(
                  onTap: () => _selectWarrantyExpiry(context),
                  child: InputDecorator(
                    decoration: const InputDecoration(
                      labelText: '保修到期',
                      prefixIcon: Icon(Icons.verified_user),
                    ),
                    child: Text(
                      _warrantyExpiry != null
                          ? '${_warrantyExpiry!.year}-${_warrantyExpiry!.month.toString().padLeft(2, '0')}-${_warrantyExpiry!.day.toString().padLeft(2, '0')}'
                          : '选择日期',
                      style: TextStyle(
                        color: _warrantyExpiry != null
                            ? AppColors.textPrimary
                            : AppColors.textSecondary,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 16),

                // Maintenance cycle
                DropdownButtonFormField<int>(
                  decoration: const InputDecoration(
                    labelText: '保养周期',
                    prefixIcon: Icon(Icons.build),
                  ),
                  value: _maintenanceCycle,
                  items: const [
                    DropdownMenuItem(value: 3, child: Text('3个月')),
                    DropdownMenuItem(value: 6, child: Text('6个月')),
                    DropdownMenuItem(value: 12, child: Text('12个月')),
                    DropdownMenuItem(value: 24, child: Text('24个月')),
                  ],
                  onChanged: (value) {
                    if (value != null) {
                      setState(() => _maintenanceCycle = value);
                    }
                  },
                ),
                const SizedBox(height: 16),

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
                    child: const Text('添加家电'),
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
      firstDate: DateTime(2000),
      lastDate: DateTime.now(),
    );
    if (picked != null) {
      setState(() => _purchaseDate = picked);
    }
  }

  Future<void> _selectWarrantyExpiry(BuildContext context) async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _warrantyExpiry ?? DateTime.now().add(const Duration(days: 365)),
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 365 * 10)),
    );
    if (picked != null) {
      setState(() => _warrantyExpiry = picked);
    }
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) return;

    final name = _nameController.text.trim();
    final brand = _brandController.text.trim().isNotEmpty
        ? _brandController.text.trim()
        : null;
    final model = _modelController.text.trim().isNotEmpty
        ? _modelController.text.trim()
        : null;
    final notes = _notesController.text.trim().isNotEmpty
        ? _notesController.text.trim()
        : null;

    context.read<HousingBloc>().add(ApplianceCreateRequested(
      propertyId: widget.propertyId,
      name: name,
      brand: brand,
      model: model,
      purchaseDate: _purchaseDate,
      warrantyExpiry: _warrantyExpiry,
      maintenanceCycleMonths: _maintenanceCycle,
      notes: notes,
    ));

    Navigator.of(context).pop();
  }
}
