// lib/services/clip_service.dart - Enhanced version with smart polling and keepalive

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';
import 'dart:async';
import '../../config.dart';
import '../../models/clip_result.dart';
import 'session_manager.dart';

class ClipService {
  static const String _sessionIdKey = 'current_session_id';
  
  // Stream controllers for real-time updates
  static final StreamController<ProcessingSession> _sessionController = 
      StreamController<ProcessingSession>.broadcast();
  static final StreamController<List<ClipResult>> _partialResultsController = 
      StreamController<List<ClipResult>>.broadcast();
  
  // Current session state
  static ProcessingSession? _currentSession;
  static Timer? _pollingTimer;
  static Timer? _keepaliveTimer;
  static bool _isPolling = false;
  static int _pollCount = 0;
  static int _consecutiveErrors = 0;
  static const int maxPollAttempts = 300; // 10 minutes with 2s intervals
  static const int maxConsecutiveErrors = 5;
  
  // Public streams
  static Stream<ProcessingSession> get sessionStream => _sessionController.stream;
  static Stream<List<ClipResult>> get partialResultsStream => _partialResultsController.stream;
  static ProcessingSession? get currentSession => _currentSession;
  
  /// Initialize the service
  static Future<void> initialize() async {
    final sessionId = await getCurrentSessionId();
    if (sessionId != null && sessionId.isNotEmpty) {
      await _restoreSession(sessionId);
    }
  }
  
  /// Enhanced session management with validation
  static Future<String> _getOrCreateSessionId() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      String? sessionId = prefs.getString(_sessionIdKey);
      
      if (sessionId != null && sessionId.isNotEmpty) {
        // Verify the session still exists on the backend
        if (await _validateSession(sessionId)) {
          debugPrint('✓ Reusing existing session: $sessionId');
          return sessionId;
        } else {
          debugPrint('⚠ Existing session invalid, creating new one');
          await prefs.remove(_sessionIdKey);
        }
      }
      
      // Create new session using dedicated endpoint
      debugPrint('🆕 Creating new session...');
      final newSessionId = await _createNewSession();
      await prefs.setString(_sessionIdKey, newSessionId);
      debugPrint('✓ Created and saved new session: $newSessionId');
      return newSessionId;
      
    } catch (e) {
      debugPrint('❌ Error managing session ID: $e');
      return DateTime.now().millisecondsSinceEpoch.toString();
    }
  }
  
  /// Validate if a session exists on the backend
  static Future<bool> _validateSession(String sessionId) async {
    try {
      final statusUri = Uri.parse('${Config.apiBaseUrl}/api/session/status/$sessionId');
      final response = await http.get(statusUri).timeout(const Duration(seconds: 5));
      return response.statusCode == 200;
    } catch (e) {
      debugPrint('⚠ Could not validate session: $e');
      return false;
    }
  }
  
  /// Create a new session using the dedicated session creation endpoint
  static Future<String> _createNewSession() async {
    final createUri = Uri.parse('${Config.apiBaseUrl}/api/session/create');
    
    try {
      final response = await http.post(createUri);
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        if (data['status'] == 'success') {
          return data['session_id'] as String;
        } else {
          throw Exception('Session creation failed: ${data['message']}');
        }
      } else {
        throw Exception('HTTP ${response.statusCode}: ${response.body}');
      }
    } catch (e) {
      debugPrint('Error creating session: $e');
      throw Exception('Failed to create session: $e');
    }
  }
  
  /// Send keepalive signal to prevent container shutdown
  static Future<void> _sendKeepalive() async {
    try {
      final keepaliveUri = Uri.parse('${Config.apiBaseUrl}/api/session/keepalive');
      final response = await http.get(
        keepaliveUri,
        headers: {
          'ngrok-skip-browser-warning': 'true',
          'Content-Type': 'application/json',
        }
      ).timeout(const Duration(seconds: 10));
      
      if (response.statusCode == 200) {
        debugPrint('💓 Keepalive sent successfully');
      } else {
        debugPrint('⚠ Keepalive failed: HTTP ${response.statusCode}');
      }
    } catch (e) {
      debugPrint('⚠ Keepalive error: $e');
    }
  }
  
  /// Start keepalive timer during processing
  static void _startKeepalive() {
    _stopKeepalive();
    _keepaliveTimer = Timer.periodic(const Duration(seconds: 15), (timer) async {
      await _sendKeepalive();
    });
    debugPrint('💓 Started keepalive timer (15s intervals)');
  }
  
  /// Stop keepalive timer
  static void _stopKeepalive() {
    _keepaliveTimer?.cancel();
    _keepaliveTimer = null;
  }
  
  /// Restore session from storage
  static Future<void> _restoreSession(String sessionId) async {
    try {
      final statusUri = Uri.parse('${Config.apiBaseUrl}/api/session/status/$sessionId');
      final response = await http.get(statusUri).timeout(const Duration(seconds: 5));
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final status = data['status'] as String;
        
        ProcessingStatus procStatus;
        switch (status) {
          case 'processing':
            procStatus = ProcessingStatus.processing;
            break;
          case 'completed':
            procStatus = ProcessingStatus.completed;
            break;
          case 'error':
            procStatus = ProcessingStatus.error;
            break;
          case 'cancelled':
            procStatus = ProcessingStatus.cancelled;
            break;
          case 'active':
            procStatus = ProcessingStatus.idle;
            break;
          default:
            procStatus = ProcessingStatus.idle;
        }
        
        // Get partial or complete results
        List<ClipResult> results = [];
        if (data.containsKey('partial_results')) {
          final partialOutputs = data['partial_results'] as List<dynamic>;
          results = partialOutputs
              .map((e) => ClipResult.fromJson(e as Map<String, dynamic>, sessionId: sessionId))
              .toList();
        } else if (data.containsKey('outputs')) {
          final outputs = data['outputs'] as List<dynamic>;
          results = outputs
              .map((e) => ClipResult.fromJson(e as Map<String, dynamic>, sessionId: sessionId))
              .toList();
        }
        
        _currentSession = ProcessingSession(
          sessionId: sessionId,
          status: procStatus,
          results: results,
          error: data['error'] as String?,
        );
        
        _sessionController.add(_currentSession!);
        
        if (results.isNotEmpty) {
          _partialResultsController.add(results);
        }
        
        // Start polling if still processing
        if (procStatus == ProcessingStatus.processing) {
          _startPolling();
          _startKeepalive(); // Keep container alive
        }
        
        debugPrint('✓ Restored session: $sessionId with ${results.length} results, status: $status');
      }
    } catch (e) {
      debugPrint('⚠ Could not restore session $sessionId: $e');
    }
  }
  
  /// Start processing pipeline - NON-BLOCKING
  static Future<bool> startPipeline({
    required String source,
    required String timeWindow,
    required bool isVOD,
    required int maxClips,
    required int segmentDuration,
    required bool includeSubtitles,
    required int minViews, 
    required Function(String) log,
  }) async {
    try {
      // Stop any existing polling and keepalive
      _stopPolling();
      _stopKeepalive();
      
      final sessionId = await _getOrCreateSessionId();
      
      _currentSession = ProcessingSession(
        sessionId: sessionId,
        status: ProcessingStatus.starting,
        results: [],
      );
      _sessionController.add(_currentSession!);
      
      final startUri = Uri.parse('${Config.apiBaseUrl}/api/session/process');
      final req = http.MultipartRequest('POST', startUri)
        ..fields['source'] = source
        ..fields['time_window'] = timeWindow
        ..fields['vod'] = isVOD.toString()
        ..fields['max_clips'] = maxClips.toString()
        ..fields['segment_duration'] = segmentDuration.toString()
        ..fields['session_id'] = sessionId 
        ..fields['include_subtitles'] = includeSubtitles.toString()
        ..fields['min_views'] = minViews.toString();

      log("▶️ Starting pipeline...");

      final streamed = await req.send();
      final res = await http.Response.fromStream(streamed);

      if (res.statusCode != 200) {
        log("✖ HTTP ${res.statusCode}: ${res.body}");
        _currentSession = _currentSession!.copyWith(
          status: ProcessingStatus.error,
          error: "HTTP ${res.statusCode}: ${res.body}",
        );
        _sessionController.add(_currentSession!);
        return false;
      }

      final startData = jsonDecode(res.body) as Map<String, dynamic>;
      final status = startData['status'] as String;
      if (status != 'processing') {
        log("✖ Unexpected response: ${res.body}");
        _currentSession = _currentSession!.copyWith(
          status: ProcessingStatus.error,
          error: "Unexpected response: ${res.body}",
        );
        _sessionController.add(_currentSession!);
        return false;
      }

      final responseSessionId = startData['session_id'] as String;
      log("🔄 Processing started with session: $responseSessionId");
      
      _currentSession = ProcessingSession(
        sessionId: responseSessionId,
        status: ProcessingStatus.processing,
        results: [],
      );
      _sessionController.add(_currentSession!);
      
      // Start aggressive polling and keepalive during processing
      _startPolling();
      _startKeepalive();
      
      return true;
      
    } catch (e) {
      final errorMsg = "Error starting pipeline: $e";
      log("✖ $errorMsg");
      _currentSession = _currentSession?.copyWith(
        status: ProcessingStatus.error,
        error: errorMsg,
      );
      if (_currentSession != null) {
        _sessionController.add(_currentSession!);
      }
      return false;
    }
  }
  
  /// Enhanced polling with adaptive intervals and error recovery
  static void _startPolling() {
    _stopPolling(); // Ensure no duplicate timers
    _isPolling = true;
    _pollCount = 0;
    _consecutiveErrors = 0;
    
    // Start with aggressive polling (1 second) during processing
    Duration initialInterval = const Duration(seconds: 1);
    
    _pollingTimer = Timer.periodic(initialInterval, (timer) async {
      // Check if we should stop polling BEFORE making any API calls
      if (!_isPolling || 
          _currentSession == null || 
          _currentSession!.status == ProcessingStatus.completed ||
          _currentSession!.status == ProcessingStatus.error ||
          _currentSession!.status == ProcessingStatus.cancelled ||
          _pollCount >= maxPollAttempts ||
          _consecutiveErrors >= maxConsecutiveErrors) {
        
        timer.cancel();
        _isPolling = false;
        _stopKeepalive(); // Stop keepalive when polling stops
        
        if (_pollCount >= maxPollAttempts) {
          debugPrint("⏰ Polling timeout reached");
          _currentSession = _currentSession?.copyWith(
            status: ProcessingStatus.error,
            error: "Processing timeout - no response after 10 minutes",
          );
          if (_currentSession != null) {
            _sessionController.add(_currentSession!);
          }
        } else if (_consecutiveErrors >= maxConsecutiveErrors) {
          debugPrint("❌ Too many consecutive errors, stopping polling");
          _currentSession = _currentSession?.copyWith(
            status: ProcessingStatus.error,
            error: "Connection lost - too many consecutive errors",
          );
          if (_currentSession != null) {
            _sessionController.add(_currentSession!);
          }
        }
        return;
      }
      
      _pollCount++;
      await _pollSessionStatus();
      
      // Adaptive polling: slow down after first minute
      if (_pollCount == 60 && timer.tick == 60) {
        timer.cancel();
        _startAdaptivePolling(); // Switch to slower polling
      }
    });
  }
  
  /// Switch to adaptive polling after initial aggressive phase
  static void _startAdaptivePolling() {
    if (!_isPolling || _currentSession == null) return;
    
    debugPrint("🔄 Switching to adaptive polling (2s intervals)");
    
    _pollingTimer = Timer.periodic(const Duration(seconds: 2), (timer) async {
      if (!_isPolling || 
          _currentSession == null || 
          _currentSession!.status == ProcessingStatus.completed ||
          _currentSession!.status == ProcessingStatus.error ||
          _currentSession!.status == ProcessingStatus.cancelled ||
          _pollCount >= maxPollAttempts ||
          _consecutiveErrors >= maxConsecutiveErrors) {
        
        timer.cancel();
        _isPolling = false;
        _stopKeepalive();
        return;
      }
      
      _pollCount++;
      await _pollSessionStatus();
    });
  }
  
  /// Stop polling
  static void _stopPolling() {
    _isPolling = false;
    _pollingTimer?.cancel();
    _pollingTimer = null;
    _pollCount = 0;
    _consecutiveErrors = 0;
  }
  
  /// Enhanced session status polling with error recovery
  static Future<void> _pollSessionStatus() async {
    // Double-check if we should still be polling
    if (!_isPolling || _currentSession == null) {
      return;
    }
    
    try {
      final statusUri = Uri.parse('${Config.apiBaseUrl}/api/session/status/${Uri.encodeComponent(_currentSession!.sessionId)}');
      final statusRes = await http.get(
        statusUri,
        headers: {
          'ngrok-skip-browser-warning': 'true',
          'Content-Type': 'application/json',
        }
      ).timeout(const Duration(seconds: 10));
      
      // Check again after the async call
      if (!_isPolling) {
        return;
      }
      
      if (statusRes.statusCode == 404) {
        // Session lost (likely container restart)
        debugPrint("⚠ Session lost (404) - attempting recovery...");
        _consecutiveErrors++;
        
        // Try to recreate session if we haven't exceeded error limit
        if (_consecutiveErrors < 3) {
          await _attemptSessionRecovery();
        }
        return;
      }
      
      if (statusRes.statusCode != 200) {
        debugPrint("⚠ Status poll failed: HTTP ${statusRes.statusCode}");
        _consecutiveErrors++;
        return;
      }

      // Reset error counter on successful response
      _consecutiveErrors = 0;
      
      final statusData = jsonDecode(statusRes.body) as Map<String, dynamic>;
      final status = statusData['status'] as String;
      
      debugPrint("📊 Poll #$_pollCount - Status: $status, Errors: $_consecutiveErrors");
      
      ProcessingStatus newStatus;
      switch (status) {
        case 'processing':
          newStatus = ProcessingStatus.processing;
          break;
        case 'completed':
          newStatus = ProcessingStatus.completed;
          break;
        case 'error':
          newStatus = ProcessingStatus.error;
          break;
        case 'cancelled':
          newStatus = ProcessingStatus.cancelled;
          break;
        case 'active':
          newStatus = ProcessingStatus.idle;
          break;
        default:
          newStatus = ProcessingStatus.processing;
      }
      
      // Get results (partial or complete)
      List<ClipResult> results = [];
      if (statusData.containsKey('partial_results')) {
        final partialOutputs = statusData['partial_results'] as List<dynamic>;
        results = partialOutputs
            .map((e) => ClipResult.fromJson(e as Map<String, dynamic>, sessionId: _currentSession!.sessionId))
            .toList();
      } else if (statusData.containsKey('outputs')) {
        final outputs = statusData['outputs'] as List<dynamic>;
        results = outputs
            .map((e) => ClipResult.fromJson(e as Map<String, dynamic>, sessionId: _currentSession!.sessionId))
            .toList();
      }
      
      // Check if we have new results
      final hadNewResults = results.length > _currentSession!.results.length;
      
      _currentSession = _currentSession!.copyWith(
        status: newStatus,
        results: results,
        error: statusData['error'] as String?,
        progress: (statusData['progress'] as int).toDouble(),
        currentStep: statusData['current_step'] as String? ?? "",
      );
      
      // Emit session update
      _sessionController.add(_currentSession!);
      
      // Emit partial results if new ones arrived
      if (hadNewResults && results.isNotEmpty) {
        _partialResultsController.add(results);
        debugPrint("📊 New partial results: ${results.length} clips available");
      }
      
      // Stop polling if finished
      if (newStatus == ProcessingStatus.completed ||
          newStatus == ProcessingStatus.error ||
          newStatus == ProcessingStatus.cancelled) {
        debugPrint("🏁 Processing finished with status: $status - stopping polls");
        _stopPolling();
      }
      
    } catch (e) {
      debugPrint("⚠ Error polling session status: $e");
      _consecutiveErrors++;
    }
  }
  
  /// Attempt to recover from session loss
  static Future<void> _attemptSessionRecovery() async {
    try {
      debugPrint("🔄 Attempting session recovery...");
      
      // Try to create a new session
      final newSessionId = await _createNewSession();
      
      // Update stored session ID
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_sessionIdKey, newSessionId);
      
      // Update current session but keep existing data
      _currentSession = _currentSession!.copyWith(
        sessionId: newSessionId,
        status: ProcessingStatus.error,
        error: "Session recovered after container restart - previous progress may be lost",
      );
      
      _sessionController.add(_currentSession!);
      debugPrint("✅ Session recovery completed: $newSessionId");
      
    } catch (e) {
      debugPrint("❌ Session recovery failed: $e");
      _currentSession = _currentSession?.copyWith(
        status: ProcessingStatus.error,
        error: "Session lost and recovery failed: $e",
      );
      if (_currentSession != null) {
        _sessionController.add(_currentSession!);
      }
    }
  }
  
  /// Enhanced cancel processing
  static Future<bool> cancelProcessing() async {
    if (_currentSession == null) return false;
    
    try {
      // Stop polling and keepalive immediately
      _stopPolling();
      _stopKeepalive();
      
      final cancelUri = Uri.parse('${Config.apiBaseUrl}/api/session/cancel/${_currentSession!.sessionId}');
      final response = await http.delete(cancelUri);
      
      if (response.statusCode == 200) {
        _currentSession = _currentSession!.copyWith(status: ProcessingStatus.cancelled);
        _sessionController.add(_currentSession!);
        return true;
      }
      return false;
    } catch (e) {
      debugPrint('Error cancelling processing: $e');
      return false;
    }
  }
  
  /// Get current stored session ID
  static Future<String?> getCurrentSessionId() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return prefs.getString(_sessionIdKey);
    } catch (e) {
      return null;
    }
  }
  
  /// Clear stored session
  static Future<void> clearStoredSession() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_sessionIdKey);
      _currentSession = null;
      _stopPolling();
      _stopKeepalive();
      debugPrint('🗑️ Cleared stored session');
    } catch (e) {
      debugPrint('Error clearing session: $e');
    }
  }
  
  /// Dispose resources
  static void dispose() {
    _stopPolling();
    _stopKeepalive();
    _sessionController.close();
    _partialResultsController.close();
  }
}