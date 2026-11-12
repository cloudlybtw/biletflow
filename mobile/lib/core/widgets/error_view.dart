import 'package:flutter/material.dart';
import 'package:biletflow_verify/core/error/failure.dart';

class ErrorView extends StatelessWidget {
  const ErrorView({super.key, required this.error, this.onRetry});
  final Object error;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {

    final (icon, message) = switch (error) {

      NetworkFailure(:final message) || TimeoutFailure(:final message) =>
        (Icons.wifi_off_rounded, message),
      ForbiddenFailure(:final message) => (Icons.lock_outline, message),
      Failure(:final message) => (Icons.error_outline, message),
      _ => (Icons.error_outline, 'Something went wrong. Please try again.'),

    };
    return Center
    (
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 48, color: Theme.of(context).colorScheme.error),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            if (onRetry != null) ...[
              const SizedBox(height: 16),
              FilledButton.tonal(onPressed: onRetry, child: const Text('Try again')),
            ],
          ],
        ),
      ),
    );
  }
}