import 'package:intl/intl.dart';

String formatEventDateTime(DateTime value) => DateFormat('EEE d MMM y, HH:mm').format(value.toLocal());

String formatClockTime(DateTime value) => DateFormat.Hm().format(value.toLocal());