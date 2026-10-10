import 'dart:async';
import 'package:flutter/material.dart';

/// 智能行程生成加载对话框
/// 显示动态进度消息，让用户在等待时感受到进展
class SmartItineraryLoadingDialog extends StatefulWidget {
  final String destination;

  const SmartItineraryLoadingDialog({
    super.key,
    required this.destination,
  });

  @override
  State<SmartItineraryLoadingDialog> createState() => _SmartItineraryLoadingDialogState();
}

class _SmartItineraryLoadingDialogState extends State<SmartItineraryLoadingDialog>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _fadeAnimation;
  int _currentMessageIndex = 0;
  int _elapsedSeconds = 0;
  Timer? _elapsedTimer;

  // 进度消息基于实际AI处理阶段 - 每个阶段约对应实际处理时间
  // 阶段1 (0-15秒): 准备和分析
  // 阶段2 (15-60秒): AI正在生成
  // 阶段3 (60-120秒): 继续生成和优化
  // 阶段4 (120秒+): 等待完成
  final List<_ProgressMessage> _progressMessages = [
    _ProgressMessage('正在分析家庭成员和偏好...', Icons.family_restroom, Colors.blue),
    _ProgressMessage('正在获取天气预报...', Icons.cloud, Colors.cyan),
    _ProgressMessage('AI 正在规划行程（这需要一点时间）...', Icons.psychology, Colors.purple),
    _ProgressMessage('AI 正在安排每日活动...', Icons.calendar_today, Colors.orange),
    _ProgressMessage('AI 正在优化景点路线...', Icons.route, Colors.green),
    _ProgressMessage('AI 正在添加美食推荐...', Icons.restaurant, Colors.red),
    _ProgressMessage('AI 正在计算预算分配...', Icons.attach_money, Colors.amber),
    _ProgressMessage('AI 正在生成专业建议...', Icons.lightbulb, Colors.indigo),
    _ProgressMessage('正在保存行程数据...', Icons.save, Colors.teal),
  ];

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 500),
      vsync: this,
    );
    _fadeAnimation = Tween<double>(begin: 0.5, end: 1.0).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
    );
    _controller.repeat(reverse: true);

    // 基于时间的进度更新 - 更贴合实际AI处理阶段
    _elapsedTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (mounted) {
        setState(() {
          _elapsedSeconds++;
          // 根据已用时间切换到对应阶段的消息
          _currentMessageIndex = _getMessageIndexForTime(_elapsedSeconds);
        });
      }
    });
  }

  /// 根据已用时间返回对应的进度消息索引
  int _getMessageIndexForTime(int seconds) {
    // 阶段时间分布（基于实际AI处理流程，总时长可达5-10分钟）：
    // 0-10秒: 分析家庭成员 (index 0)
    // 10-20秒: 获取天气 (index 1)
    // 20-120秒: AI规划中 (index 2) - 主要的LLM处理阶段
    // 120-200秒: 安排活动 (index 3)
    // 200-280秒: 优化路线 (index 4)
    // 280-360秒: 美食推荐 (index 5)
    // 360-420秒: 预算计算 (index 6)
    // 420-480秒: 专业建议 (index 7)
    // 480秒+: 保存数据 (index 8)
    if (seconds < 10) return 0;
    if (seconds < 20) return 1;
    if (seconds < 120) return 2;
    if (seconds < 200) return 3;
    if (seconds < 280) return 4;
    if (seconds < 360) return 5;
    if (seconds < 420) return 6;
    if (seconds < 480) return 7;
    return 8;
  }

  @override
  void dispose() {
    _controller.dispose();
    _elapsedTimer?.cancel();
    super.dispose();
  }

  String _formatTime(int seconds) {
    final minutes = seconds ~/ 60;
    final secs = seconds % 60;
    if (minutes > 0) {
      return '$minutes分${secs.toString().padLeft(2, '0')}秒';
    }
    return '$secs秒';
  }

  @override
  Widget build(BuildContext context) {
    final currentMessage = _progressMessages[_currentMessageIndex];

    return Dialog(
      backgroundColor: Colors.transparent,
      child: Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.1),
              blurRadius: 20,
              offset: const Offset(0, 10),
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // AI 图标动画
            AnimatedBuilder(
              animation: _fadeAnimation,
              builder: (context, child) {
                return Container(
                  width: 80,
                  height: 80,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: LinearGradient(
                      colors: [
                        Theme.of(context).primaryColor.withValues(alpha: _fadeAnimation.value),
                        Theme.of(context).primaryColor.withValues(alpha: _fadeAnimation.value * 0.6),
                      ],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                  ),
                  child: const Icon(
                    Icons.auto_awesome,
                    color: Colors.white,
                    size: 40,
                  ),
                );
              },
            ),

            const SizedBox(height: 20),

            // 标题
            Text(
              'AI 正在规划 ${widget.destination} 行程',
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
              textAlign: TextAlign.center,
            ),

            const SizedBox(height: 24),

            // 当前进度消息
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 300),
              child: Row(
                key: ValueKey(_currentMessageIndex),
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    currentMessage.icon,
                    color: currentMessage.color,
                    size: 20,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    currentMessage.text,
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.grey[700],
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 20),

            // 进度条 - 基于估计的5-10分钟完成时间
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                // 估算进度: 假设总时间约500秒（8分钟），最多显示95%
                value: (_elapsedSeconds / 500.0).clamp(0.0, 0.95),
                backgroundColor: Colors.grey[200],
                valueColor: AlwaysStoppedAnimation<Color>(
                  Theme.of(context).primaryColor,
                ),
              ),
            ),

            const SizedBox(height: 16),

            // 已用时间
            Text(
              '已用时 ${_formatTime(_elapsedSeconds)}',
              style: TextStyle(
                fontSize: 12,
                color: Colors.grey[500],
              ),
            ),

            const SizedBox(height: 8),

            // 提示信息
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.blue[50],
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Icon(Icons.info_outline, size: 16, color: Colors.blue[700]),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'AI 正在为您精心规划，可能需要 5-10 分钟，请耐心等待',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.blue[700],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ProgressMessage {
  final String text;
  final IconData icon;
  final Color color;

  _ProgressMessage(this.text, this.icon, this.color);
}

/// 显示智能行程加载对话框
/// 返回一个函数用于关闭对话框
void Function() showSmartItineraryLoadingDialog(BuildContext context, String destination) {
  showDialog(
    context: context,
    barrierDismissible: false,
    builder: (context) => SmartItineraryLoadingDialog(destination: destination),
  );

  return () {
    if (Navigator.of(context, rootNavigator: true).canPop()) {
      Navigator.of(context, rootNavigator: true).pop();
    }
  };
}
