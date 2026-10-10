import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../domain/entities/trip.dart';
import '../../../auth/presentation/bloc/auth_bloc.dart';
import '../bloc/trip_bloc.dart';

class CreateTripPage extends StatefulWidget {
  final String? tripId; // If provided, edit mode

  const CreateTripPage({super.key, this.tripId});

  @override
  State<CreateTripPage> createState() => _CreateTripPageState();
}

class _CreateTripPageState extends State<CreateTripPage> {
  final _formKey = GlobalKey<FormState>();
  final _destinationController = TextEditingController();
  final _tripNameController = TextEditingController();
  final _budgetController = TextEditingController();
  final _notesController = TextEditingController();

  DateTime _startDate = DateTime.now().add(const Duration(days: 7));
  DateTime _endDate = DateTime.now().add(const Duration(days: 10));
  TripCategory _category = TripCategory.personal;
  TripType _tripType = TripType.leisure;
  bool _isSubmitting = false;
  bool _isLoadingData = false;
  bool _dataLoaded = false;

  bool get isEditMode => widget.tripId != null;

  @override
  void initState() {
    super.initState();
    if (isEditMode) {
      _isLoadingData = true;
      context.read<TripBloc>().add(TripLoadRequested(widget.tripId!));
    }
  }

  void _populateFromTrip(Trip trip) {
    if (_dataLoaded) return;
    _dataLoaded = true;
    _destinationController.text = trip.destination;
    _tripNameController.text = trip.tripName ?? '';
    _budgetController.text = trip.budget != null ? trip.budget!.toStringAsFixed(0) : '';
    _notesController.text = trip.notes ?? '';
    setState(() {
      _startDate = trip.startDate;
      _endDate = trip.endDate;
      _category = trip.category;
      _tripType = trip.tripType;
    });
  }

  @override
  void dispose() {
    _destinationController.dispose();
    _tripNameController.dispose();
    _budgetController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocListener<TripBloc, TripState>(
      listener: (context, state) {
        if (state is TripDetailLoaded && isEditMode && !_dataLoaded) {
          _populateFromTrip(state.plan);
          setState(() => _isLoadingData = false);
        } else if (state is TripOperationSuccess) {
          setState(() => _isSubmitting = false);
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(state.message)),
          );
          context.pop();
        } else if (state is TripError) {
          setState(() {
            _isSubmitting = false;
            _isLoadingData = false;
          });
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(state.message)),
          );
        }
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(isEditMode ? '编辑行程' : '新建行程'),
        ),
        body: _isLoadingData
            ? const Center(child: CircularProgressIndicator())
            : Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // Destination
              TextFormField(
                controller: _destinationController,
                decoration: const InputDecoration(
                  labelText: '目的地 *',
                  hintText: '例如：杭州、三亚、日本东京',
                  prefixIcon: Icon(Icons.location_on),
                  border: OutlineInputBorder(),
                ),
                validator: (value) {
                  if (value == null || value.isEmpty) {
                    return '请输入目的地';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),

              // Trip name (optional)
              TextFormField(
                controller: _tripNameController,
                decoration: const InputDecoration(
                  labelText: '行程名称（可选）',
                  hintText: '例如：国庆全家游、蜜月之旅',
                  prefixIcon: Icon(Icons.flight_takeoff),
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 24),

              // Date selection
              const Text(
                '出行日期',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: _DatePickerField(
                      label: '出发日期',
                      date: _startDate,
                      onChanged: (date) {
                        setState(() {
                          _startDate = date;
                          if (_endDate.isBefore(_startDate)) {
                            _endDate = _startDate.add(const Duration(days: 2));
                          }
                        });
                      },
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: _DatePickerField(
                      label: '返回日期',
                      date: _endDate,
                      firstDate: _startDate,
                      onChanged: (date) {
                        setState(() {
                          _endDate = date;
                        });
                      },
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.primaryContainer,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Text(
                    '${_endDate.difference(_startDate).inDays + 1}天${_endDate.difference(_startDate).inDays}晚',
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.onPrimaryContainer,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 24),

              // Category selection (top-level)
              const Text(
                '行程分类',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: _CategoryCard(
                      icon: Icons.person,
                      label: '个人出行',
                      isSelected: _category == TripCategory.personal,
                      onTap: () => _onCategoryChanged(TripCategory.personal),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _CategoryCard(
                      icon: Icons.business_center,
                      label: '公务差旅',
                      isSelected: _category == TripCategory.business,
                      onTap: () => _onCategoryChanged(TripCategory.business),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),

              // Trip type selection (sub-category)
              const Text(
                '行程类型',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: Trip.getTypesForCategory(_category).map((type) {
                  final isSelected = _tripType == type;
                  return ChoiceChip(
                    label: Text(_getTripTypeName(type)),
                    avatar: Text(_getTripTypeIcon(type)),
                    selected: isSelected,
                    onSelected: (selected) {
                      if (selected) {
                        setState(() => _tripType = type);
                      }
                    },
                  );
                }).toList(),
              ),
              const SizedBox(height: 24),

              // Budget
              TextFormField(
                controller: _budgetController,
                decoration: const InputDecoration(
                  labelText: '预算（可选）',
                  hintText: '请输入预算金额',
                  prefixIcon: Icon(Icons.account_balance_wallet),
                  prefixText: '¥ ',
                  border: OutlineInputBorder(),
                ),
                keyboardType: TextInputType.number,
              ),
              const SizedBox(height: 16),

              // Notes
              TextFormField(
                controller: _notesController,
                decoration: const InputDecoration(
                  labelText: '备注（可选）',
                  hintText: '添加一些备注信息...',
                  prefixIcon: Icon(Icons.note),
                  border: OutlineInputBorder(),
                ),
                maxLines: 3,
              ),
              const SizedBox(height: 32),

              // Submit button
              ElevatedButton(
                onPressed: _isSubmitting ? null : _onSubmit,
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                ),
                child: _isSubmitting
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Text(isEditMode ? '保存修改' : '创建行程计划'),
              ),
              const SizedBox(height: 16),

              // AI suggestion hint
              if (!isEditMode)
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.blue[50],
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.auto_awesome, color: Colors.blue[700]),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '不知道去哪？',
                              style: TextStyle(
                                color: Colors.blue[900],
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '创建计划后，可以让 AI 帮你智能推荐目的地和生成行程！',
                              style: TextStyle(
                                color: Colors.blue[800],
                                fontSize: 13,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  void _onCategoryChanged(TripCategory newCategory) {
    setState(() {
      _category = newCategory;
      // Reset trip type to first type of new category
      final types = Trip.getTypesForCategory(newCategory);
      _tripType = types.first;
    });
  }

  void _onSubmit() {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isSubmitting = true);

    final budget = _budgetController.text.isNotEmpty
        ? double.tryParse(_budgetController.text)
        : null;

    // Get familyId from auth state
    final authState = context.read<AuthBloc>().state;
    final familyId = authState is AuthAuthenticated
        ? authState.user.familyId
        : '';

    final plan = Trip(
      id: widget.tripId ?? '',
      familyId: familyId,
      tripName: _tripNameController.text.isEmpty ? null : _tripNameController.text,
      destination: _destinationController.text,
      startDate: _startDate,
      endDate: _endDate,
      category: _category,
      tripType: _tripType,
      budget: budget,
      status: TripStatus.planning,
      notes: _notesController.text.isEmpty ? null : _notesController.text,
      createdAt: DateTime.now(),
      updatedAt: DateTime.now(),
    );

    if (isEditMode) {
      context.read<TripBloc>().add(
        TripUpdateRequested(widget.tripId!, plan),
      );
    } else {
      context.read<TripBloc>().add(TripCreateRequested(plan));
    }
  }

  String _getTripTypeName(TripType type) {
    switch (type) {
      case TripType.leisure:
        return '休闲游';
      case TripType.family:
        return '亲子游';
      case TripType.visit:
        return '探亲访友';
      case TripType.businessTrip:
        return '商务出差';
      case TripType.conference:
        return '会议培训';
      case TripType.clientVisit:
        return '客户拜访';
      case TripType.other:
        return '其他';
    }
  }

  String _getTripTypeIcon(TripType type) {
    switch (type) {
      case TripType.leisure:
        return '🏖️';
      case TripType.family:
        return '👨‍👩‍👧‍👦';
      case TripType.visit:
        return '🏠';
      case TripType.businessTrip:
        return '💼';
      case TripType.conference:
        return '📋';
      case TripType.clientVisit:
        return '🤝';
      case TripType.other:
        return '📍';
    }
  }
}

class _CategoryCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool isSelected;
  final VoidCallback onTap;

  const _CategoryCard({
    required this.icon,
    required this.label,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = isSelected ? theme.colorScheme.primary : Colors.grey[400];

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 12),
        decoration: BoxDecoration(
          border: Border.all(
            color: isSelected ? theme.colorScheme.primary : Colors.grey[300]!,
            width: isSelected ? 2 : 1,
          ),
          borderRadius: BorderRadius.circular(12),
          color: isSelected
              ? theme.colorScheme.primaryContainer.withOpacity(0.3)
              : null,
        ),
        child: Column(
          children: [
            Icon(icon, size: 32, color: color),
            const SizedBox(height: 8),
            Text(
              label,
              style: TextStyle(
                fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                color: isSelected ? theme.colorScheme.primary : Colors.grey[700],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _DatePickerField extends StatelessWidget {
  final String label;
  final DateTime date;
  final DateTime? firstDate;
  final ValueChanged<DateTime> onChanged;

  const _DatePickerField({
    required this.label,
    required this.date,
    this.firstDate,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final dateFormat = DateFormat('MM月dd日');

    return InkWell(
      onTap: () async {
        final picked = await showDatePicker(
          context: context,
          initialDate: date,
          firstDate: firstDate ?? DateTime.now(),
          lastDate: DateTime.now().add(const Duration(days: 365)),
        );
        if (picked != null) {
          onChanged(picked);
        }
      },
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          border: Border.all(color: Colors.grey[300]!),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              label,
              style: TextStyle(
                color: Colors.grey[600],
                fontSize: 12,
              ),
            ),
            const SizedBox(height: 4),
            Row(
              children: [
                const Icon(Icons.calendar_today, size: 18),
                const SizedBox(width: 8),
                Text(
                  dateFormat.format(date),
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
