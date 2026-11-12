import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:permission_handler/permission_handler.dart';

class CameraErrorView extends StatelessWidget {
  const CameraErrorView({
    super.key,
    required this.error,
    required this.onRetry,
    required this.onSearchInstead,
  });

  final MobileScannerException error;
  final VoidCallback onRetry;
  final VoidCallback onSearchInstead;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final denied = error.errorCode == MobileScannerErrorCode.permissionDenied;
    final steps = theme.platform == TargetPlatform.iOS
        ? 'Open Settings → BiletFlow Verify → turn on Camera.'
        : 'Open Settings → Apps → BiletFlow Verify → Permissions → Camera → Allow.';

    return ColoredBox(
      color: theme.colorScheme.surface,
      child: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  denied ? Icons.no_photography_outlined : Icons.videocam_off_outlined,
                  size: 56,
                  color: theme.colorScheme.error,
                ),
                const SizedBox(height: 16),
                Text(
                  denied ? 'Camera access is turned off' : 'Camera unavailable',
                  style: theme.textTheme.titleLarge,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  denied
                      ? 'BiletFlow Verify needs the camera to read ticket QR codes.\n\n'
                          '$steps\n\nThe scanner restarts automatically when you come back.'
                      : (error.errorDetails?.message ??
                          'The camera could not be started. Close other apps using it and try again.'),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 24),
                if (denied) ...[
                  FilledButton.icon(
                    onPressed: openAppSettings,
                    icon: const Icon(Icons.settings),
                    label: const Text('Open settings'),
                  ),
                  const SizedBox(height: 8),
                ],
                OutlinedButton(onPressed: onRetry, child: const Text('Try again')),
                const SizedBox(height: 8),
                TextButton(
                  onPressed: onSearchInstead,
                  child: const Text('Search attendees manually instead'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}