import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/research_session.dart';
import '../bloc/research_bloc.dart';
import '../widgets/candidate_card.dart';
import '../widgets/manual_input_sheet.dart';
import '../widgets/synthesis_panel.dart';

class ResearchPage extends StatefulWidget {
  final String? sessionId;
  final String? topic;
  final String? scenario;

  const ResearchPage({
    super.key,
    this.sessionId,
    this.topic,
    this.scenario,
  });

  @override
  State<ResearchPage> createState() => _ResearchPageState();
}

class _ResearchPageState extends State<ResearchPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final TextEditingController _searchController = TextEditingController();
  ResearchScenario _selectedScenario = ResearchScenario.general;
  bool _showSearchInput = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);

    // Initialize session
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final bloc = context.read<ResearchBloc>();
      if (widget.sessionId != null) {
        bloc.add(LoadSessionEvent(sessionId: widget.sessionId!));
      } else if (widget.topic != null) {
        final scenario = _parseScenario(widget.scenario);
        bloc.add(CreateSessionEvent(topic: widget.topic!, scenario: scenario));
      } else {
        // No topic provided, show search input
        setState(() => _showSearchInput = true);
      }
    });
  }

  ResearchScenario _parseScenario(String? value) {
    switch (value) {
      case 'gift':
        return ResearchScenario.gift;
      case 'travel':
        return ResearchScenario.travel;
      case 'holiday':
        return ResearchScenario.holiday;
      case 'health':
        return ResearchScenario.health;
      default:
        return ResearchScenario.general;
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocConsumer<ResearchBloc, ResearchState>(
      listener: (context, state) {
        if (state.error != null) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(state.error!),
              behavior: SnackBarBehavior.floating,
              backgroundColor: Colors.red,
            ),
          );
        }
        // Hide search input when session is created
        if (state.session != null && _showSearchInput) {
          setState(() => _showSearchInput = false);
        }
      },
      builder: (context, state) {
        // Show search input when no session
        if (_showSearchInput && state.session == null) {
          return Scaffold(
            backgroundColor: AppColors.background,
            appBar: AppBar(
              backgroundColor: Colors.white,
              elevation: 0,
              leading: IconButton(
                icon: const Icon(Icons.arrow_back_ios, color: AppColors.textPrimary),
                onPressed: () => Navigator.of(context).pop(),
              ),
              title: Text(
                '快速研究',
                style: AppTextStyles.headline6.copyWith(
                  color: AppColors.textPrimary,
                ),
              ),
            ),
            body: _buildSearchInputView(context, state),
          );
        }

        return Scaffold(
          backgroundColor: AppColors.background,
          appBar: _buildAppBar(context, state),
          body: state.isLoading && state.session == null
              ? const Center(child: CircularProgressIndicator())
              : Column(
                  children: [
                    _buildTabBar(),
                    Expanded(
                      child: TabBarView(
                        controller: _tabController,
                        children: [
                          _buildSearchResultsTab(context, state),
                          _buildSelectedTab(context, state),
                          _buildSynthesisTab(context, state),
                        ],
                      ),
                    ),
                  ],
                ),
        );
      },
    );
  }

  Widget _buildSearchInputView(BuildContext context, ResearchState state) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Search input card
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: AppColors.cardShadow,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '你想研究什么？',
                  style: AppTextStyles.headline5,
                ),
                const SizedBox(height: 8),
                Text(
                  '输入你感兴趣的主题，AI 会帮你搜索相关内容并生成综合报告',
                  style: AppTextStyles.bodyText2.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
                const SizedBox(height: 20),
                TextField(
                  controller: _searchController,
                  decoration: InputDecoration(
                    hintText: '例如：2024年最佳降噪耳机推荐',
                    prefixIcon: const Icon(Icons.search),
                    filled: true,
                    fillColor: AppColors.background,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide.none,
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(color: AppColors.primary, width: 2),
                    ),
                  ),
                  textInputAction: TextInputAction.search,
                  onSubmitted: (_) => _startSearch(context),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // Scenario selection
          Text(
            '选择研究场景（可选）',
            style: AppTextStyles.subtitle1.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: ResearchScenario.values.map((scenario) {
              final isSelected = _selectedScenario == scenario;
              return GestureDetector(
                onTap: () => setState(() => _selectedScenario = scenario),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                  decoration: BoxDecoration(
                    color: isSelected ? AppColors.primary : Colors.white,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(
                      color: isSelected ? AppColors.primary : AppColors.divider,
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(scenario.icon, style: const TextStyle(fontSize: 16)),
                      const SizedBox(width: 6),
                      Text(
                        scenario.displayName,
                        style: TextStyle(
                          color: isSelected ? Colors.white : AppColors.textPrimary,
                          fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                        ),
                      ),
                    ],
                  ),
                ),
              );
            }).toList(),
          ),
          const SizedBox(height: 32),

          // Start button
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: state.isLoading ? null : () => _startSearch(context),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: state.isLoading
                  ? const SizedBox(
                      width: 24,
                      height: 24,
                      child: CircularProgressIndicator(
                        color: Colors.white,
                        strokeWidth: 2,
                      ),
                    )
                  : const Text(
                      '开始研究',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                    ),
            ),
          ),
          const SizedBox(height: 24),

          // Quick suggestions
          Text(
            '热门研究主题',
            style: AppTextStyles.subtitle2.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              '送父母什么礼物好',
              '家庭旅行目的地推荐',
              '儿童教育资源',
              '健康饮食建议',
              '家庭理财规划',
            ].map((suggestion) => GestureDetector(
              onTap: () {
                _searchController.text = suggestion;
                _startSearch(context);
              },
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Text(
                  suggestion,
                  style: TextStyle(
                    color: AppColors.primary,
                    fontSize: 13,
                  ),
                ),
              ),
            )).toList(),
          ),
        ],
      ),
    );
  }

  void _startSearch(BuildContext context) {
    final topic = _searchController.text.trim();
    if (topic.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('请输入研究主题'),
          behavior: SnackBarBehavior.floating,
        ),
      );
      return;
    }
    context.read<ResearchBloc>().add(
      CreateSessionEvent(topic: topic, scenario: _selectedScenario),
    );
  }

  PreferredSizeWidget _buildAppBar(BuildContext context, ResearchState state) {
    return AppBar(
      backgroundColor: Colors.white,
      elevation: 0,
      leading: IconButton(
        icon: const Icon(Icons.arrow_back_ios, color: AppColors.textPrimary),
        onPressed: () => Navigator.of(context).pop(),
      ),
      title: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                state.session?.scenario.icon ?? '🔍',
                style: const TextStyle(fontSize: 18),
              ),
              const SizedBox(width: 8),
              Text(
                '快速研究',
                style: AppTextStyles.headline6.copyWith(
                  color: AppColors.textPrimary,
                ),
              ),
            ],
          ),
          if (state.session != null)
            Text(
              state.session!.topic,
              style: AppTextStyles.caption.copyWith(
                color: AppColors.textSecondary,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
        ],
      ),
      actions: [
        if (state.progressMessage != null)
          Padding(
            padding: const EdgeInsets.only(right: 16),
            child: Center(
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    state.progressMessage!,
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildTabBar() {
    return BlocBuilder<ResearchBloc, ResearchState>(
      builder: (context, state) {
        return Container(
          color: Colors.white,
          child: TabBar(
            controller: _tabController,
            labelColor: AppColors.primary,
            unselectedLabelColor: AppColors.textSecondary,
            indicatorColor: AppColors.primary,
            indicatorWeight: 3,
            tabs: [
              Tab(
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.search, size: 18),
                    const SizedBox(width: 4),
                    Text('搜索结果 (${state.candidates.length})'),
                  ],
                ),
              ),
              Tab(
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.check_circle_outline, size: 18),
                    const SizedBox(width: 4),
                    Text('已选 (${state.totalSelectedCount})'),
                  ],
                ),
              ),
              const Tab(
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.article_outlined, size: 18),
                    SizedBox(width: 4),
                    Text('报告'),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildSearchResultsTab(BuildContext context, ResearchState state) {
    if (state.isSearching && state.candidates.isEmpty) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('正在搜索相关内容...'),
          ],
        ),
      );
    }

    if (state.candidates.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.search_off, size: 64, color: AppColors.textTertiary),
            const SizedBox(height: 16),
            Text(
              '暂无搜索结果',
              style: AppTextStyles.bodyText1.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: 8),
            ElevatedButton(
              onPressed: () {
                context.read<ResearchBloc>().add(const StartSearchEvent());
              },
              child: const Text('重新搜索'),
            ),
          ],
        ),
      );
    }

    return Column(
      children: [
        // Action bar
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          color: Colors.white,
          child: Row(
            children: [
              Text(
                '找到 ${state.candidates.length} 个相关结果',
                style: AppTextStyles.caption.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
              const Spacer(),
              TextButton.icon(
                onPressed: () {
                  context.read<ResearchBloc>().add(const SelectAllCandidatesEvent());
                },
                icon: const Icon(Icons.select_all, size: 18),
                label: const Text('全选'),
              ),
              TextButton.icon(
                onPressed: () {
                  context.read<ResearchBloc>().add(const ClearSelectionEvent());
                },
                icon: const Icon(Icons.clear_all, size: 18),
                label: const Text('清空'),
              ),
            ],
          ),
        ),
        // Candidate list
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: state.candidates.length,
            itemBuilder: (context, index) {
              final candidate = state.candidates[index];
              final isSelected = state.selectedIds.contains(candidate.id);
              return CandidateCard(
                candidate: candidate,
                isSelected: isSelected,
                onTap: () {
                  context.read<ResearchBloc>().add(
                        ToggleCandidateEvent(candidateId: candidate.id),
                      );
                },
                onOpenUrl: () => _launchUrl(candidate.url),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _buildSelectedTab(BuildContext context, ResearchState state) {
    final selectedCandidates = state.candidates
        .where((c) => state.selectedIds.contains(c.id))
        .toList();

    return Column(
      children: [
        // Manual input button
        Container(
          padding: const EdgeInsets.all(16),
          color: Colors.white,
          child: Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => _showManualInputSheet(context, 'note'),
                  icon: const Icon(Icons.note_add),
                  label: const Text('添加笔记'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => _showManualInputSheet(context, 'url'),
                  icon: const Icon(Icons.link),
                  label: const Text('添加链接'),
                ),
              ),
            ],
          ),
        ),
        // Selected items list
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // Selected candidates
              if (selectedCandidates.isNotEmpty) ...[
                _buildSectionHeader('已选内容 (${selectedCandidates.length})'),
                ...selectedCandidates.map((candidate) => _buildSelectedItem(
                      context,
                      icon: Icons.search,
                      title: candidate.title,
                      subtitle: candidate.source ?? candidate.url,
                      onRemove: () {
                        context.read<ResearchBloc>().add(
                              ToggleCandidateEvent(candidateId: candidate.id),
                            );
                      },
                    )),
              ],
              // Manual items
              if (state.manualItems.isNotEmpty) ...[
                const SizedBox(height: 16),
                _buildSectionHeader('手动添加 (${state.manualItems.length})'),
                ...state.manualItems.map((item) => _buildSelectedItem(
                      context,
                      icon: item.type == 'note' ? Icons.note : Icons.link,
                      title: item.title ?? (item.type == 'note' ? '笔记' : '链接'),
                      subtitle: item.content,
                      onRemove: () {
                        context.read<ResearchBloc>().add(
                              RemoveManualItemEvent(itemId: item.id),
                            );
                      },
                    )),
              ],
              // Empty state
              if (selectedCandidates.isEmpty && state.manualItems.isEmpty)
                Center(
                  child: Padding(
                    padding: const EdgeInsets.all(32),
                    child: Column(
                      children: [
                        Icon(
                          Icons.inbox_outlined,
                          size: 64,
                          color: AppColors.textTertiary,
                        ),
                        const SizedBox(height: 16),
                        Text(
                          '还没有选择任何内容',
                          style: AppTextStyles.bodyText1.copyWith(
                            color: AppColors.textSecondary,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          '从搜索结果中选择，或手动添加笔记和链接',
                          style: AppTextStyles.caption.copyWith(
                            color: AppColors.textTertiary,
                          ),
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildSynthesisTab(BuildContext context, ResearchState state) {
    return SynthesisPanel(
      content: state.synthesisContent,
      sources: state.synthesisSources,
      isSynthesizing: state.isSynthesizing,
      selectedCount: state.totalSelectedCount,
      onGenerate: (format) {
        context.read<ResearchBloc>().add(GenerateSynthesisEvent(format: format));
        // Switch to synthesis tab
        _tabController.animateTo(2);
      },
      onCopy: () {
        Clipboard.setData(ClipboardData(text: state.synthesisContent));
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('已复制到剪贴板'),
            behavior: SnackBarBehavior.floating,
          ),
        );
      },
    );
  }

  Widget _buildSectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        title,
        style: AppTextStyles.subtitle2.copyWith(
          color: AppColors.textSecondary,
        ),
      ),
    );
  }

  Widget _buildSelectedItem(
    BuildContext context, {
    required IconData icon,
    required String title,
    required String subtitle,
    required VoidCallback onRemove,
  }) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: AppColors.primary.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(icon, color: AppColors.primary, size: 20),
        ),
        title: Text(
          title,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: AppTextStyles.bodyText2,
        ),
        subtitle: Text(
          subtitle,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: AppTextStyles.caption.copyWith(
            color: AppColors.textSecondary,
          ),
        ),
        trailing: IconButton(
          icon: const Icon(Icons.close, size: 20),
          onPressed: onRemove,
        ),
      ),
    );
  }

  void _showManualInputSheet(BuildContext context, String type) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => ManualInputSheet(
        type: type,
        onSubmit: (content) {
          context.read<ResearchBloc>().add(
                AddManualItemEvent(type: type, content: content),
              );
          Navigator.pop(context);
        },
      ),
    );
  }

  Future<void> _launchUrl(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }
}
