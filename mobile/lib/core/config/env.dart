abstract final class Env {
    static const String apiBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://10.0.2.2:8000');
    static const scanSlowThreshold = Duration(milliseconds: 3500);
    
}