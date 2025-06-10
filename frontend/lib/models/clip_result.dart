import '../config.dart';

class ClipResult {
  /// raw filenames coming from the backend JSON
  final String video;
  final String thumbnail;
  final String transcript;
  final List<String> tags;
  final String description;
  final List<String> hashtags;
  final String? sessionId; // Add session ID to track which session this belongs to
  final int? viewCount; 

  ClipResult({
    required this.video,
    required this.thumbnail,
    required this.transcript,
    required this.tags,
    required this.description,  
    required this.hashtags,
    this.sessionId,
    required this.viewCount,
  });

  /// build the full URL on‐demand with proper URL encoding and session path
  String get videoUrl => 
    '${Config.apiBaseUrl}/api/session/output/${Uri.encodeComponent(sessionId!)}/${Uri.encodeComponent(video)}';
  String get thumbnailUrl => 
      '${Config.apiBaseUrl}/api/session/output/${Uri.encodeComponent(sessionId!)}/${Uri.encodeComponent(thumbnail)}';
  String get downloadVideoUrl =>
      '${Config.apiBaseUrl}/api/session/download/${Uri.encodeComponent(sessionId!)}/${Uri.encodeComponent(video)}';
  String get downloadSessionZipUrl =>
      '${Config.apiBaseUrl}/api/session/download_session/${Uri.encodeComponent(sessionId!)}';
  
  factory ClipResult.fromJson(Map<String, dynamic> json, {String? sessionId}) {
    final rawTags = json['hashtags'];
    final List<String> hashtags = rawTags is String
        ? rawTags.split(' ')                    // split the space-separated string
        : List<String>.from(rawTags as List);   // already a list

    return ClipResult(
      video: json['video'] as String,
      thumbnail: json['thumbnail'] as String,
      transcript: json['transcript'] as String,
      tags: List<String>.from(json['tags'] as List),
      description: json['description'] as String,
      hashtags: hashtags,
      sessionId: sessionId ?? json['session_id'] as String?, // Try to get from JSON if not provided
      viewCount: (json['view_count'] as int?) ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'video': video,        // Store the filename, not the full URL
      'thumbnail': thumbnail, // Store the filename, not the full URL  
      'transcript': transcript,
      'tags': tags,
      'description': description,
      'hashtags': hashtags,
      'session_id': sessionId, // Include session ID in JSON
      'view_count': viewCount,
    };
  }

  ClipResult copyWith({
    List<String>? tags, 
    String? sessionId,
    String? video,
    String? thumbnail,
    String? transcript,
    String? description,
    List<String>? hashtags,
    int? viewCount,
  }) {
    return ClipResult(
      video: video ?? this.video,
      thumbnail: thumbnail ?? this.thumbnail,
      transcript: transcript ?? this.transcript,
      tags: tags ?? this.tags,
      description: description ?? this.description,
      hashtags: hashtags ?? this.hashtags,
      sessionId: sessionId ?? this.sessionId,
      viewCount: viewCount ?? this.viewCount,
    );
  }
}