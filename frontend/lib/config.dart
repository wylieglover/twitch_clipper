/// Centralized config for API base URL.
/// Override at runtime with:
/// flutter run -d chrome --dart-define=API_BASE_URL=https://yourserver.com
class Config {
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://twitchtok-backend-service-726148196121.us-central1.run.app',
  );
}
