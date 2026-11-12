import 'package:dio/dio.dart';

typedef ApiPage = ({List<Map<String, dynamic>> items, int total});

ApiPage decodePage(Object? data) {
  if (data is! Map<String, dynamic> ||
      data['items'] is! List ||
      data['total'] is! int) {
    throw const FormatException('Expected a paginated API response.');
  }
  final items = (data['items'] as List).cast<Map<String, dynamic>>();
  final total = data['total'] as int;
  if (total < 0) throw const FormatException('Invalid page total.');
  return (items: items, total: total);
}

Future<List<Map<String, dynamic>>> fetchAllPages(
  Dio dio,
  String path, {
  Map<String, dynamic> query = const {},
}) async {
  final items = <Map<String, dynamic>>[];
  for (var offset = 0; ; offset += 100) {
    final response = await dio.get<Object>(
      path,
      queryParameters: {...query, 'limit': 100, 'offset': offset},
    );
    final page = decodePage(response.data);
    items.addAll(page.items);
    if (items.length >= page.total) return items;
    if (page.items.isEmpty) {
      throw const FormatException('Incomplete page response.');
    }
  }
}
