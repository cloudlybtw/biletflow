import 'package:biletflow_verify/features/check_in/presentation/widgets/camera_error_view.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

void main() {
  for (final platform in [TargetPlatform.android, TargetPlatform.iOS]) {
    testWidgets(
      'denied camera on $platform retains retry and manual admission',
      (tester) async {
        var retries = 0;
        var searches = 0;
        await tester.pumpWidget(
          MaterialApp(
            theme: ThemeData(platform: platform),
            home: Scaffold(
              body: CameraErrorView(
                error: MobileScannerException(
                  errorCode: MobileScannerErrorCode.permissionDenied,
                ),
                onRetry: () => retries++,
                onSearchInstead: () => searches++,
              ),
            ),
          ),
        );
        expect(find.text('Camera access is turned off'), findsOneWidget);
        expect(
          find.textContaining(
            platform == TargetPlatform.iOS
                ? 'Open Settings → BiletFlow'
                : 'Open Settings → Apps',
          ),
          findsOneWidget,
        );
        await tester.tap(find.text('Try again'));
        await tester.tap(find.text('Search attendees manually instead'));
        expect(retries, 1);
        expect(searches, 1);
      },
    );
  }
}
