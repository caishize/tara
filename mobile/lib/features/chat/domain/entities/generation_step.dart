import 'package:equatable/equatable.dart';
import 'tool_execution_step.dart';

/// Represents a step in the generation process (Thinking or Tool Execution)
abstract class GenerationStep extends Equatable {
  const GenerationStep();

  @override
  List<Object?> get props => [];
}

/// Represents a block of thinking/reasoning
class ThinkingStep extends GenerationStep {
  final String content;
  final bool isComplete;

  const ThinkingStep({
    required this.content,
    this.isComplete = false,
  });

  ThinkingStep copyWith({
    String? content,
    bool? isComplete,
  }) {
    return ThinkingStep(
      content: content ?? this.content,
      isComplete: isComplete ?? this.isComplete,
    );
  }

  @override
  List<Object?> get props => [content, isComplete];
}

/// Represents a tool execution
class ToolStep extends GenerationStep {
  final ToolExecutionStep tool;

  const ToolStep({
    required this.tool,
  });

  ToolStep copyWith({
    ToolExecutionStep? tool,
  }) {
    return ToolStep(
      tool: tool ?? this.tool,
    );
  }

  @override
  List<Object?> get props => [tool];
}

/// Represents the final content/answer block in the generation sequence
class ContentStep extends GenerationStep {
  final String content;
  final bool isComplete;

  const ContentStep({
    required this.content,
    this.isComplete = false,
  });

  ContentStep copyWith({
    String? content,
    bool? isComplete,
  }) {
    return ContentStep(
      content: content ?? this.content,
      isComplete: isComplete ?? this.isComplete,
    );
  }

  @override
  List<Object?> get props => [content, isComplete];
}
