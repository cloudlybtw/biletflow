import 'package:flutter/material.dart';
import 'package:biletflow_verify/features/check_in/domain/entities/check_in_entities.dart';
import 'package:biletflow_verify/features/check_in/presentation/providers/scan_controller.dart';
import 'package:biletflow_verify/features/check_in/presentation/widgets/scan_verdict_card.dart';


class ScanStatusPanel extends StatelessWidget {
  const ScanStatusPanel({
    super.key,
    required this.state,
    required this.onScanNext,
    required this.onRetry,
    required this.onUndo,
    required this.onSearch,
  });

  final ScanState state;
  final VoidCallback onScanNext;
  final VoidCallback onRetry;
  final VoidCallback onUndo;
  final VoidCallback onSearch;

  static const _unconfirmedNote =
      'Your previous attempt may have checked this ticket in. '
      'Compare the check-in time before refusing entry.';

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scanNextButton = FilledButton.icon(
      onPressed: onScanNext,
      icon: const Icon(Icons.qr_code_scanner),
      label: const Text('Scan next'),
    );

    final Widget content = switch (state) {
      ScanReady() => Row(
          children: [
            const Icon(Icons.qr_code_2, size: 32),
            const SizedBox(width: 12),
            const Expanded(child: Text('Point the camera at the ticket QR code')),
            TextButton(onPressed: onSearch, child: const Text('Search')),
          ],
        ),
      ScanValidating(:final isSlow) => Row(
          children: [
            const SizedBox.square(dimension: 28, child: CircularProgressIndicator(strokeWidth: 3)),
            const SizedBox(width: 16),
            Expanded(
              child: Text(
                isSlow
                    ? 'Slower than usual — still waiting for the server. Do not admit yet.'
                    : 'Validating ticket…',
                style: theme.textTheme.titleMedium
                    ?.copyWith(color: isSlow ? Colors.orange.shade800 : null),
              ),
            ),
          ],
        ),
      ScanDecided(undo: UndoStatus.done) => _WithActions(
          body: _Notice(
            icon: Icons.undo,
            color: theme.colorScheme.primary,
            text: 'Check-in undone. The ticket is valid again.',
          ),
          primary: scanNextButton,
        ),
      ScanDecided(
        :final outcome,
        :final undo,
        :final undoError,
        :final followsUnconfirmedAttempt,
      ) =>
        _WithActions(
          body: ScanVerdictCard(
            outcome: outcome,
            footnote: undoError ??
                (followsUnconfirmedAttempt && outcome.verdict == ScanVerdict.alreadyUsed
                    ? _unconfirmedNote
                    : null),
          ),
          secondary: outcome.canUndo
              ? OutlinedButton.icon(
                  onPressed: undo == UndoStatus.inProgress ? null : onUndo,
                  icon: const Icon(Icons.undo),
                  label: Text(undo == UndoStatus.inProgress ? 'Undoing…' : 'Undo'),
                )
              : null,
          primary: undo == UndoStatus.inProgress
              ? const FilledButton(onPressed: null, child: Text('Scan next'))
              : scanNextButton,
        ),
      ScanNotVerified(:final failure) => _WithActions(
          body: _Notice(
            icon: Icons.error,
            color: theme.colorScheme.error,
            text: 'NOT VERIFIED — do not admit.\n${failure.message}',
          ),
          secondary: OutlinedButton(onPressed: onScanNext, child: const Text('Dismiss')),
          primary: FilledButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: const Text('Retry'),
          ),
        ),
    };

    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Material(
          color: theme.colorScheme.surface,
          elevation: 6,
          borderRadius: BorderRadius.circular(24),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: AnimatedSize(duration: const Duration(milliseconds: 150), child: content),
          ),
        ),
      ),
    );
  }
}

class _WithActions extends StatelessWidget {
  const _WithActions({required this.body, required this.primary, this.secondary});

  final Widget body;
  final Widget primary;
  final Widget? secondary;

  @override
  Widget build(BuildContext context) => Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          body,
          const SizedBox(height: 12),
          Row(
            children: [
              if (secondary != null) ...[
                Expanded(child: SizedBox(height: 52, child: secondary!)),
                const SizedBox(width: 12),
              ],
              Expanded(flex: 2, child: SizedBox(height: 52, child: primary)),
            ],
          ),
        ],
      );
}

class _Notice extends StatelessWidget {
  const _Notice({required this.icon, required this.color, required this.text});

  final IconData icon;
  final Color color;
  final String text;

  @override
  Widget build(BuildContext context) => Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 32),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              text,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(color: color),
            ),
          ),
        ],
      );
}