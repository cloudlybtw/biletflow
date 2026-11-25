import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:biletflow_verify/app/routes.dart';
import 'package:biletflow_verify/core/widgets/offline_banner.dart';
import 'package:biletflow_verify/features/check_in/presentation/providers/scan_controller.dart';
import 'package:biletflow_verify/features/check_in/presentation/widgets/camera_error_view.dart';
import 'package:biletflow_verify/features/check_in/presentation/widgets/scan_status_panel.dart';
import 'package:biletflow_verify/features/check_in/presentation/widgets/undo_check_in_dialog.dart';


class ScannerScreen extends ConsumerStatefulWidget {
  const ScannerScreen({super.key, required this.eventId});
  final String eventId;

  @override
  ConsumerState<ScannerScreen> createState() => _ScannerScreenState();
}



class _ScannerScreenState extends ConsumerState<ScannerScreen> with WidgetsBindingObserver {

  final _camera = MobileScannerController(
    formats: const [BarcodeFormat.qrCode],
    detectionSpeed: DetectionSpeed.normal,
    detectionTimeoutMs: 250,
  );

  ScanController get _scan => ref.read(scanControllerProvider.notifier);

  @override
  void initState() {

    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {

    WidgetsBinding.instance.removeObserver(this);
    unawaited(_camera.dispose());
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState lifecycle) {
    
    if (lifecycle == AppLifecycleState.resumed && _camera.value.error != null) {
      unawaited(_restartCamera());
    }
  }

  void _onDetect(BarcodeCapture capture) {
    final raw = capture.barcodes.map((b) => b.rawValue).nonNulls.firstOrNull;
    if (raw != null) {
      unawaited(_scan.onDetected(eventId: widget.eventId, rawPayload: raw));
    }
  }

  Future<void> _restartCamera() async {
    try {
      await _camera.start();
    } on MobileScannerException {
      // error.
    }
  }

  Future<void> _openManualSearch() async {
    await _camera.stop(); 
    if (!mounted) return;
    await context.push(AppRoutes.search(widget.eventId));
    if (mounted) await _restartCamera();
  }

  Future<void> _undo() async {
    final reason = await showUndoCheckInDialog(context);
    if (reason != null && mounted) {
      await _scan.undoCheckIn(eventId: widget.eventId, reason: reason);
    }
  }

  void _hapticFor(ScanState? previous, ScanState next) {
    if (next is ScanDecided && previous is! ScanDecided) {
      unawaited(next.outcome.admitted ? HapticFeedback.mediumImpact() : HapticFeedback.vibrate());
    } else if (next is ScanNotVerified && previous is! ScanNotVerified) {
      unawaited(HapticFeedback.vibrate());
    }
  }

  @override
  Widget build(BuildContext context) {
    final scanState = ref.watch(scanControllerProvider);
    ref.listen<ScanState>(scanControllerProvider, _hapticFor);


    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: const Text('SCAN TICKETS'),
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        actions: [
          ValueListenableBuilder<MobileScannerState>(
            valueListenable: _camera,
            builder: (context, camera, _) {
              if (!camera.isRunning || camera.torchState == TorchState.unavailable) {
                return const SizedBox.shrink();
              }
              return IconButton(
                constraints: const BoxConstraints.tightFor(width: 48, height: 48),
                tooltip: 'Flashlight',
                icon: Icon(camera.torchState == TorchState.on ? Icons.flash_on : Icons.flash_off),
                onPressed: _camera.toggleTorch,
              );
            },
          ),
          IconButton(
            constraints: const BoxConstraints.tightFor(width: 48, height: 48),
            tooltip: 'Find attendee manually',
            icon: const Icon(Icons.person_search),
            onPressed: _openManualSearch,
          ),
        ],
      ),
      body: Column(
        children: [
          const OfflineBanner(),
          Expanded(
            child: Stack(
              fit: StackFit.expand,
              children: [
                MobileScanner(
                  controller: _camera,
                  onDetect: _onDetect,
                  
                  errorBuilder: (context, error) => CameraErrorView(
                    error: error,
                    onRetry: _restartCamera,
                    onSearchInstead: _openManualSearch,
                  ),
                ),
                
                ValueListenableBuilder<MobileScannerState>(
                  valueListenable: _camera,
                  builder: (context, camera, _) {
                    if (camera.error != null) return const SizedBox.shrink();
                    return Stack(
                      fit: StackFit.expand,
                      children: [
                        const _AimingFrame(),
                        Align(
                          alignment: Alignment.bottomCenter,
                          child: ScanStatusPanel(
                            state: scanState,
                            onScanNext: _scan.scanNext,
                            onRetry: () => _scan.retry(widget.eventId),
                            onUndo: _undo,
                            onSearch: _openManualSearch,
                          ),
                        ),
                      ],
                    );
                  },
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Corners extends CustomPainter {
  const _Corners(this.color);
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final pen = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3;
    for (final left in [true, false]) {
      for (final top in [true, false]) {
        final x = left ? 2.0 : size.width - 2;
        final y = top ? 2.0 : size.height - 2;
        final corner = Path()
          ..moveTo(x + (left ? 24 : -24), y)
          ..lineTo(x, y)
          ..lineTo(x, y + (top ? 24 : -24));
        canvas.drawPath(corner, pen);
      }
    }
  }

  @override
  bool shouldRepaint(_Corners oldDelegate) => oldDelegate.color != color;
}

class _AimingFrame extends StatelessWidget {
  const _AimingFrame();

  @override
  Widget build(BuildContext context) => IgnorePointer(
        child: Align(
          alignment: const Alignment(0, -0.4),
          child: CustomPaint(
            size: const Size.square(240),
            painter: _Corners(Theme.of(context).colorScheme.secondary),
          ),
        ),
      );
}