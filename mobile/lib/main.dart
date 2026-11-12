import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:biletflow_verify/app/app.dart';


void main() {

  WidgetsFlutterBinding.ensureInitialized();
  runApp(
    ProviderScope(

      retry: (retryCount, error) => null,
      child: const BiletFlowVerifyApp(),
      
    ),
  );
}