import 'package:flutter/material.dart';
import '../../domain/entities/smart_itinerary.dart';
import 'style_selection_sheet.dart';
import 'family_composition_form.dart';

class SmartItineraryConfigSheet extends StatefulWidget {
  final Function(SmartItineraryRequest) onGenerate;
  final SmartItineraryRequest? initialConfig;

  const SmartItineraryConfigSheet({
    super.key,
    required this.onGenerate,
    this.initialConfig,
  });

  @override
  State<SmartItineraryConfigSheet> createState() => _SmartItineraryConfigSheetState();
}

class _SmartItineraryConfigSheetState extends State<SmartItineraryConfigSheet> {
  late List<ItineraryStyle> _selectedStyles;
  late FamilyComposition _familyComposition;
  late ItineraryPreferences _preferences;
  int _currentStep = 0;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    // Use List.from to create a mutable copy
    _selectedStyles = List.from(widget.initialConfig?.styles ?? []);
    _familyComposition = widget.initialConfig?.familyComposition ??
        const FamilyComposition(children: [], elderly: []);
    _preferences = widget.initialConfig?.preferences ??
        const ItineraryPreferences(
          enableNapTime: true,
          weatherAware: true,
          includeLocalTips: true,
        );
  }

  void _goToNextStep() {
    if (_selectedStyles.isEmpty) {
      setState(() {
        _errorMessage = '请至少选择一种行程风格';
      });
      return;
    }
    setState(() {
      _errorMessage = null;
      _currentStep++;
    });
  }

  void _handleGenerate() {
    if (_selectedStyles.isEmpty) {
      setState(() {
        _currentStep = 0;
        _errorMessage = '请至少选择一种行程风格';
      });
      return;
    }

    final request = SmartItineraryRequest(
      styles: List.from(_selectedStyles),
      familyComposition: _familyComposition,
      preferences: _preferences,
    );

    widget.onGenerate(request);
    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      height: MediaQuery.of(context).size.height * 0.85,
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Column(
        children: [
          // Handle bar
          Container(
            margin: const EdgeInsets.only(top: 12),
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: Colors.grey[300],
              borderRadius: BorderRadius.circular(2),
            ),
          ),

          // Header
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Theme.of(context).primaryColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(
                    Icons.auto_awesome,
                    color: Theme.of(context).primaryColor,
                  ),
                ),
                const SizedBox(width: 12),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '智能行程规划',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      Text(
                        'AI将根据您的偏好生成专属行程',
                        style: TextStyle(
                          fontSize: 13,
                          color: Colors.grey,
                        ),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
          ),

          // Step indicator
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                _buildStepIndicator(0, '选择风格'),
                Expanded(
                  child: Container(
                    height: 2,
                    color: _currentStep >= 1
                        ? Theme.of(context).primaryColor
                        : Colors.grey[300],
                  ),
                ),
                _buildStepIndicator(1, '家庭设置'),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // Content
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: _currentStep == 0
                  ? _buildStyleSelection()
                  : _buildFamilySettings(),
            ),
          ),

          // Bottom buttons
          Container(
            padding: EdgeInsets.fromLTRB(
              16,
              16,
              16,
              16 + MediaQuery.of(context).padding.bottom,
            ),
            decoration: BoxDecoration(
              color: Colors.white,
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.05),
                  blurRadius: 10,
                  offset: const Offset(0, -2),
                ),
              ],
            ),
            child: Row(
              children: [
                if (_currentStep > 0)
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => setState(() => _currentStep--),
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      child: const Text('上一步'),
                    ),
                  ),
                if (_currentStep > 0) const SizedBox(width: 12),
                Expanded(
                  flex: _currentStep == 0 ? 1 : 1,
                  child: ElevatedButton(
                    onPressed: () {
                      if (_currentStep == 0) {
                        _goToNextStep();
                      } else {
                        _handleGenerate();
                      }
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Theme.of(context).primaryColor,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        if (_currentStep == 1) ...[
                          const Icon(Icons.auto_awesome, size: 18),
                          const SizedBox(width: 8),
                        ],
                        Text(_currentStep == 0 ? '下一步' : '生成智能行程'),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStepIndicator(int step, String label) {
    final isActive = _currentStep >= step;
    final isCurrent = _currentStep == step;

    return Column(
      children: [
        Container(
          width: 32,
          height: 32,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: isActive
                ? Theme.of(context).primaryColor
                : Colors.grey[300],
            border: isCurrent
                ? Border.all(
                    color: Theme.of(context).primaryColor.withValues(alpha: 0.3),
                    width: 3,
                  )
                : null,
          ),
          child: Center(
            child: isActive && !isCurrent
                ? const Icon(Icons.check, color: Colors.white, size: 18)
                : Text(
                    '${step + 1}',
                    style: TextStyle(
                      color: isActive ? Colors.white : Colors.grey[600],
                      fontWeight: FontWeight.bold,
                    ),
                  ),
          ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: TextStyle(
            fontSize: 12,
            color: isActive ? Theme.of(context).primaryColor : Colors.grey[600],
            fontWeight: isCurrent ? FontWeight.w600 : FontWeight.normal,
          ),
        ),
      ],
    );
  }

  Widget _buildStyleSelection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '选择行程风格',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          '最多选择3种风格，AI将综合考虑生成行程',
          style: TextStyle(
            fontSize: 13,
            color: Colors.grey[600],
          ),
        ),
        if (_errorMessage != null) ...[
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.red[50],
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.red[200]!),
            ),
            child: Row(
              children: [
                Icon(Icons.error_outline, color: Colors.red[700], size: 18),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _errorMessage!,
                    style: TextStyle(
                      color: Colors.red[700],
                      fontSize: 13,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
        const SizedBox(height: 16),
        ...ItineraryStyle.values.map((style) {
          final isSelected = _selectedStyles.contains(style);
          return Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: StyleChip(
              style: style,
              isSelected: isSelected,
              onTap: () {
                setState(() {
                  // Clear error when user interacts with selection
                  _errorMessage = null;
                  if (isSelected) {
                    _selectedStyles.remove(style);
                  } else if (_selectedStyles.length < 3) {
                    _selectedStyles.add(style);
                  } else {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('最多选择3种风格')),
                    );
                  }
                });
              },
            ),
          );
        }),
        if (_selectedStyles.isNotEmpty) ...[
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            children: _selectedStyles.map((style) {
              return Chip(
                label: Text(style.name),
                avatar: Text(style.icon),
                onDeleted: () {
                  setState(() => _selectedStyles.remove(style));
                },
                deleteIconColor: Colors.grey[600],
              );
            }).toList(),
          ),
        ],
      ],
    );
  }

  Widget _buildFamilySettings() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '家庭成员设置',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          '添加儿童或老人，AI会自动调整行程安排',
          style: TextStyle(
            fontSize: 13,
            color: Colors.grey[600],
          ),
        ),
        const SizedBox(height: 16),
        FamilyCompositionForm(
          initialComposition: _familyComposition,
          initialPreferences: _preferences,
          onCompositionChanged: (composition, preferences) {
            _familyComposition = composition;
            _preferences = preferences;
          },
        ),
        const SizedBox(height: 16),

        // Tips section
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.blue[50],
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: Colors.blue[100]!),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.lightbulb_outline, size: 18, color: Colors.blue[700]),
                  const SizedBox(width: 8),
                  Text(
                    '智能优化说明',
                    style: TextStyle(
                      fontWeight: FontWeight.w600,
                      color: Colors.blue[800],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              _buildTipItem('儿童模式：减少步行距离，增加亲子活动'),
              _buildTipItem('老人模式：放慢节奏，增加休息时间'),
              _buildTipItem('午睡时间：14:00-16:00 安排轻松活动'),
              _buildTipItem('天气感知：下雨时推荐室内景点'),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildTipItem(String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('• ', style: TextStyle(color: Colors.blue[700])),
          Expanded(
            child: Text(
              text,
              style: TextStyle(fontSize: 13, color: Colors.blue[900]),
            ),
          ),
        ],
      ),
    );
  }
}
