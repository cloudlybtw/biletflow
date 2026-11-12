import 'package:flutter/material.dart';


Future<String?> showUndoCheckInDialog(BuildContext context) =>
    showDialog<String>(context: context, builder: (_) => const _UndoCheckInDialog());

class _UndoCheckInDialog extends StatefulWidget {
  const _UndoCheckInDialog();

  @override
  State<_UndoCheckInDialog> createState() => _UndoCheckInDialogState();
}

class _UndoCheckInDialogState extends State<_UndoCheckInDialog> {
  final _reason = TextEditingController(text: 'Scanned by mistake');

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  void _confirm() {
    final reason = _reason.text.trim();
    if (reason.isNotEmpty) Navigator.of(context).pop(reason);
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
        icon: const Icon(Icons.undo),
        title: const Text('Undo this check-in?'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'The ticket becomes valid again. The reversal and its reason are '
              'recorded in the event history.',
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _reason,
              autofocus: true,
              maxLength: 200,
              decoration: const InputDecoration(labelText: 'Reason'),
              onSubmitted: (_) => _confirm(),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
          FilledButton(onPressed: _confirm, child: const Text('Undo check-in')),
        ],
      );
}