import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../domain/entities/destination_recommendation.dart';
import '../bloc/trip_bloc.dart';
import '../widgets/recommendation_card.dart';

class DestinationRecommendationPage extends StatefulWidget {
  const DestinationRecommendationPage({super.key});

  @override
  State<DestinationRecommendationPage> createState() => _DestinationRecommendationPageState();
}

class _DestinationRecommendationPageState extends State<DestinationRecommendationPage> {
  final _budgetController = TextEditingController();
  int _selectedDays = 3;
  OccasionType _selectedOccasion = OccasionType.vacation;
  bool _hasRequestedRecommendations = false;

  final _occasionOptions = [
    {'type': OccasionType.vacation, 'label': '假期出游', 'icon': '🏖️'},
    {'type': OccasionType.honeymoon, 'label': '蜜月旅行', 'icon': '💑'},
    {'type': OccasionType.weekend, 'label': '周末游', 'icon': '🌅'},
    {'type': OccasionType.anniversary, 'label': '纪念日', 'icon': '💝'},
    {'type': OccasionType.birthday, 'label': '生日旅行', 'icon': '🎂'},
    {'type': OccasionType.teamBuilding, 'label': '团建', 'icon': '👥'},
  ];

  @override
  void dispose() {
    _budgetController.dispose();
    super.dispose();
  }

  void _requestRecommendations() {
    final budget = double.tryParse(_budgetController.text);

    // For demo purposes, using a placeholder familyId
    // In real implementation, this should come from user context
    context.read<TripBloc>().add(
      DestinationRecommendationRequested(
        familyId: 'default', // TODO: Get from user context
        occasion: _selectedOccasion.value,
        budgetMax: budget,
        durationDays: _selectedDays,
      ),
    );

    setState(() => _hasRequestedRecommendations = true);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('目的地推荐'),
        centerTitle: true,
      ),
      body: Column(
        children: [
          // Filter section
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.05),
                  blurRadius: 4,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Budget and Days row
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _budgetController,
                        keyboardType: TextInputType.number,
                        decoration: InputDecoration(
                          labelText: '预算(可选)',
                          hintText: '人均预算',
                          prefixText: '¥ ',
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 12,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12),
                        decoration: BoxDecoration(
                          border: Border.all(color: Colors.grey[400]!),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: DropdownButton<int>(
                          value: _selectedDays,
                          isExpanded: true,
                          underline: const SizedBox(),
                          items: List.generate(14, (i) => i + 1)
                              .map((days) => DropdownMenuItem(
                                    value: days,
                                    child: Text('$days 天'),
                                  ))
                              .toList(),
                          onChanged: (value) {
                            if (value != null) {
                              setState(() => _selectedDays = value);
                            }
                          },
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),

                // Occasion selection
                const Text(
                  '出行场合',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 8),
                SizedBox(
                  height: 36,
                  child: ListView.builder(
                    scrollDirection: Axis.horizontal,
                    itemCount: _occasionOptions.length,
                    itemBuilder: (context, index) {
                      final option = _occasionOptions[index];
                      final isSelected = _selectedOccasion == option['type'];
                      return Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: FilterChip(
                          selected: isSelected,
                          label: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(option['icon'] as String),
                              const SizedBox(width: 4),
                              Text(option['label'] as String),
                            ],
                          ),
                          onSelected: (selected) {
                            setState(() {
                              _selectedOccasion = option['type'] as OccasionType;
                            });
                          },
                          selectedColor: Theme.of(context).primaryColor.withValues(alpha: 0.2),
                          checkmarkColor: Theme.of(context).primaryColor,
                        ),
                      );
                    },
                  ),
                ),
                const SizedBox(height: 12),

                // Search button
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: _requestRecommendations,
                    icon: const Icon(Icons.auto_awesome),
                    label: const Text('获取AI推荐'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Theme.of(context).primaryColor,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),

          // Results section
          Expanded(
            child: BlocBuilder<TripBloc, TripState>(
              builder: (context, state) {
                if (!_hasRequestedRecommendations) {
                  return _buildEmptyState();
                }

                if (state is TripLoading) {
                  return _buildLoadingState();
                }

                if (state is DestinationRecommendationsLoaded) {
                  if (state.recommendations.recommendations.isEmpty) {
                    return _buildNoResultsState();
                  }
                  return _buildResultsList(state.recommendations.recommendations);
                }

                if (state is TripError) {
                  return _buildErrorState(state.message);
                }

                return _buildEmptyState();
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.explore, size: 64, color: Colors.grey[300]),
          const SizedBox(height: 16),
          Text(
            '设置筛选条件获取推荐',
            style: TextStyle(
              fontSize: 16,
              color: Colors.grey[600],
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'AI将根据您的偏好推荐最适合的目的地',
            style: TextStyle(
              fontSize: 13,
              color: Colors.grey[500],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLoadingState() {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: 3,
      itemBuilder: (context, index) => const RecommendationLoadingCard(),
    );
  }

  Widget _buildNoResultsState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.search_off, size: 64, color: Colors.grey[300]),
          const SizedBox(height: 16),
          Text(
            '暂无匹配的推荐',
            style: TextStyle(
              fontSize: 16,
              color: Colors.grey[600],
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '尝试调整筛选条件',
            style: TextStyle(
              fontSize: 13,
              color: Colors.grey[500],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorState(String message) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.error_outline, size: 64, color: Colors.red[300]),
          const SizedBox(height: 16),
          Text(
            '获取推荐失败',
            style: TextStyle(
              fontSize: 16,
              color: Colors.grey[600],
            ),
          ),
          const SizedBox(height: 8),
          Text(
            message,
            style: TextStyle(
              fontSize: 13,
              color: Colors.grey[500],
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          OutlinedButton(
            onPressed: _requestRecommendations,
            child: const Text('重试'),
          ),
        ],
      ),
    );
  }

  Widget _buildResultsList(List<DestinationRecommendation> recommendations) {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: recommendations.length,
      itemBuilder: (context, index) {
        final recommendation = recommendations[index];
        return RecommendationCard(
          recommendation: recommendation,
          onTap: () {
            // Navigate to create trip with pre-filled destination
          },
          onSelect: () {
            // Navigate to create trip page with destination
            context.push('/trips/create', extra: {
              'destination': recommendation.destinationName,
              'days': recommendation.recommendedDays,
              'budget': recommendation.estimatedBudget,
            });
          },
        );
      },
    );
  }
}
