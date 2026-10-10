/// A buffer that tracks incomplete Markdown tokens during streaming,
/// holding back partial blocks that would render incorrectly.
///
/// Handles:
/// - Unclosed bold `**`, italic `*`, and inline code backticks
/// - Unclosed fenced code blocks (``` without closing ```)
/// - Incomplete tables (rows with `|` but no header separator `|---|`)
class StreamMarkdownBuffer {
  /// Process streaming markdown content and return the safe-to-render portion.
  ///
  /// Returns a [BufferResult] with the renderable text and any held-back tail.
  BufferResult process(String raw) {
    if (raw.isEmpty) return const BufferResult(renderable: '', held: '');

    // 1. Check for unclosed fenced code block — degrade entire block to plain text
    final codeBlockResult = _handleCodeBlocks(raw);
    if (codeBlockResult != null) return codeBlockResult;

    // 2. Check for incomplete table at the end
    final tableResult = _handleIncompleteTable(raw);

    // 3. Strip unclosed inline tokens from the tail
    final safeText = _stripUnclosedInlineTokens(tableResult.renderable);

    return BufferResult(
      renderable: safeText,
      held: tableResult.held,
    );
  }

  /// If there's an odd number of ``` fences, the last code block is unclosed.
  /// We strip the opening ``` and render the code section as plain text.
  BufferResult? _handleCodeBlocks(String text) {
    final fencePattern = RegExp(r'```');
    final matches = fencePattern.allMatches(text).toList();

    if (matches.isEmpty) return null;

    // Even number of fences means all code blocks are closed
    if (matches.length.isEven) return null;

    // Odd fences: last code block is unclosed
    final lastFenceStart = matches.last.start;
    final beforeFence = text.substring(0, lastFenceStart);
    final afterFence = text.substring(lastFenceStart);

    // Remove the opening ``` and any language hint on that line,
    // render the rest as plain text
    final cleaned = afterFence.replaceFirst(RegExp(r'```\w*\n?'), '');

    return BufferResult(
      renderable: beforeFence + cleaned,
      held: '',
    );
  }

  /// If the text ends with table rows (lines starting with `|`) but
  /// the table has no header separator (`|---|`), hold back the incomplete table.
  BufferResult _handleIncompleteTable(String text) {
    final lines = text.split('\n');

    // Find trailing table-like lines (lines that start and end with |)
    int tableStart = lines.length;
    for (int i = lines.length - 1; i >= 0; i--) {
      final trimmed = lines[i].trim();
      if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
        tableStart = i;
      } else if (trimmed.isEmpty && tableStart < lines.length) {
        // Allow blank lines within a potential table block
        continue;
      } else {
        break;
      }
    }

    // No trailing table lines
    if (tableStart >= lines.length) {
      return BufferResult(renderable: text, held: '');
    }

    // Check if the table block has a separator line (|---|)
    final tableLines = lines.sublist(tableStart);
    final hasSeparator = tableLines.any(
      (line) => RegExp(r'^\|[\s:-]+\|$').hasMatch(line.trim()),
    );

    if (hasSeparator) {
      // Table is well-formed enough to render
      return BufferResult(renderable: text, held: '');
    }

    // Hold back the incomplete table
    final renderable = lines.sublist(0, tableStart).join('\n');
    final held = tableLines.join('\n');

    return BufferResult(renderable: renderable, held: held);
  }

  /// Strip unclosed inline tokens from the end of text.
  /// Only strips if the token count is odd (meaning one is unclosed).
  String _stripUnclosedInlineTokens(String text) {
    if (text.isEmpty) return text;

    var result = text;

    // Handle unclosed bold **
    result = _stripTrailingUnclosedToken(result, '**');

    // Handle unclosed italic * (but not **)
    result = _stripTrailingSingleStar(result);

    // Handle unclosed inline code `
    result = _stripTrailingUnclosedToken(result, '`');

    return result;
  }

  /// If the text has an odd number of [token] occurrences,
  /// strip the last occurrence and everything after it.
  String _stripTrailingUnclosedToken(String text, String token) {
    final count = _countNonOverlapping(text, token);
    if (count.isEven || count == 0) return text;

    // Find the last occurrence and strip from there
    final lastIndex = text.lastIndexOf(token);
    if (lastIndex < 0) return text;

    return text.substring(0, lastIndex);
  }

  /// Special handling for single `*` (italic) that isn't part of `**` (bold).
  String _stripTrailingSingleStar(String text) {
    // Count single stars that aren't part of double stars
    // Replace ** temporarily to count single * accurately
    final withoutBold = text.replaceAll('**', '\x00\x00');
    final singleStarCount = _countNonOverlapping(withoutBold, '*');

    if (singleStarCount.isEven || singleStarCount == 0) return text;

    // Find the last single * (not part of **)
    for (int i = text.length - 1; i >= 0; i--) {
      if (text[i] == '*') {
        // Check it's not part of **
        final isDoubleBefore = i > 0 && text[i - 1] == '*';
        final isDoubleAfter = i < text.length - 1 && text[i + 1] == '*';
        if (!isDoubleBefore && !isDoubleAfter) {
          return text.substring(0, i);
        }
      }
    }

    return text;
  }

  int _countNonOverlapping(String text, String token) {
    int count = 0;
    int index = 0;
    while (index < text.length) {
      final found = text.indexOf(token, index);
      if (found < 0) break;
      count++;
      index = found + token.length;
    }
    return count;
  }
}

/// Result of processing streaming markdown through the buffer.
class BufferResult {
  /// The portion that is safe to render as markdown.
  final String renderable;

  /// The portion held back because it contains incomplete blocks.
  final String held;

  const BufferResult({
    required this.renderable,
    required this.held,
  });
}
