// lib/services/clip/session_manager.dart

import '../../models/clip_result.dart';
import 'dart:async';

enum ProcessingStatus { idle, starting, processing, completed, error, cancelled }

class ProcessingSession {
  final String sessionId;
  ProcessingStatus status;
  List<ClipResult> results;
  String? error;
  DateTime createdAt;
  double progress;
  String currentStep;

  ProcessingSession({
    required this.sessionId,
    this.status = ProcessingStatus.idle,
    this.results = const [],
    this.error,
    this.progress = 0.0,
    this.currentStep = "",
    DateTime? createdAt,
  }) : createdAt = createdAt ?? DateTime.now();

  ProcessingSession copyWith({
    String? sessionId,
    ProcessingStatus? status,
    List<ClipResult>? results,
    String? error,
    double? progress,
    String? currentStep,
  }) {
    return ProcessingSession(
      sessionId: sessionId ?? this.sessionId,
      status: status ?? this.status,
      results: results ?? this.results,
      error: error ?? this.error,
      progress: progress ?? this.progress,
      currentStep: currentStep ?? this.currentStep,
      createdAt: createdAt,
    );
  }
}

// Stream controllers and session state
final StreamController<ProcessingSession> sessionController =
    StreamController<ProcessingSession>.broadcast();
final StreamController<List<ClipResult>> partialResultsController =
    StreamController<List<ClipResult>>.broadcast();

ProcessingSession? currentSession;
