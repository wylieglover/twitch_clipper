import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:twitchtok/widgets/enlarge_video_player.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';
import 'dart:async';
import '../models/clip_result.dart';
import '../services/clip/session_manager.dart' show ProcessingSession, ProcessingStatus;
import '../services/clip/download_manager.dart';
import '../widgets/input_panel.dart';
import '../widgets/processing_log.dart';
import '../widgets/clip_result_card.dart';
import '../services/clip/service.dart';

class EditorScreen extends StatefulWidget {
  final VoidCallback onToggleTheme;
  const EditorScreen({super.key, required this.onToggleTheme});

  @override
  State<EditorScreen> createState() => _EditorScreenState();
}

class _EditorScreenState extends State<EditorScreen> {
  List<ClipResult> clips = [];
  List<String> logs = [];
  Set<String> filterTags = {};
  bool _isInitialized = false;

  // Real-time processing state
  ProcessingSession? currentSession;
  StreamSubscription<ProcessingSession>? _sessionSubscription;
  StreamSubscription<List<ClipResult>>? _partialResultsSubscription;

  // UI state
  bool _showProcessingIndicator = false;
  double _processingProgress = 0.0;
  String _processingStatus = '';

  @override
  void initState() {
    super.initState();
    _initializeApp();
  }

  @override
  void dispose() {
    _sessionSubscription?.cancel();
    _partialResultsSubscription?.cancel();
    super.dispose();
  }

  Future<void> _initializeApp() async {
    // Initialize ClipService
    await ClipService.initialize();

    // Subscribe to real-time updates
    _sessionSubscription =
        ClipService.sessionStream.listen(_onSessionUpdate);
    _partialResultsSubscription =
        ClipService.partialResultsStream.listen(_onPartialResults);

    // Load persisted data
    await _loadPersistedData();

    // Update initial session state
    currentSession = ClipService.currentSession;
    if (currentSession != null) {
      _updateProcessingUI();
    }
  }

  void _onSessionUpdate(ProcessingSession session) {
    if (!mounted) return;

    setState(() {
      currentSession = session;
      _updateProcessingUI();
    });

    // Log status changes
    switch (session.status) {
      case ProcessingStatus.starting:
        updateStatus('🔄 Starting processing...');
        break;
      case ProcessingStatus.processing:
        updateStatus('⚙️ Processing in progress...');
        break;
      case ProcessingStatus.completed:
        if (session.results.isNotEmpty) {
          updateStatus('✅ Processing completed! ${session.results.length} clips ready.');
        } else {
          updateStatus('✅ Processing completed, but no highlight clips were found. Try adjusting your time window or source.');
        }
        break;
      case ProcessingStatus.error:
        updateStatus('✖️ Error: ${session.error ?? 'Unknown error'}');
        break;
      case ProcessingStatus.cancelled:
        updateStatus('⏹️ Processing cancelled.');
        break;
      case ProcessingStatus.idle:
        updateStatus('💤 Ready for processing.');
        break;
    }
  }

  void _onPartialResults(List<ClipResult> newResults) {
    if (!mounted) return;

    setState(() {
      // Merge new results with existing ones, avoiding duplicates
      final existingUrls = clips.map((c) => c.videoUrl).toSet();
      final uniqueNewResults = newResults
          .where((r) => !existingUrls.contains(r.videoUrl))
          .toList();

      if (uniqueNewResults.isNotEmpty) {
        clips.addAll(uniqueNewResults);
        updateStatus(
            '📊 ${uniqueNewResults.length} new clips arrived! Total: ${clips.length}');
      }
    });

    _saveData();
  }

  void _updateProcessingUI() {
    if (currentSession == null) {
      _showProcessingIndicator = false;
      return;
    }

    final status = currentSession!.status;

    // If we’re in “starting” or “processing,” show the progress bar
    if (status == ProcessingStatus.starting || status == ProcessingStatus.processing) {
      _showProcessingIndicator = true;

      // USE THE BACKEND’S “progress” (0–100) → 0.0–1.0
      _processingProgress = (currentSession!.progress.clamp(0.0, 100.0)) / 100.0;

      // SHOW THE “currentStep” string (e.g. “Transcribing clip 2/5”)
      _processingStatus = currentSession!.currentStep.isNotEmpty
          ? currentSession!.currentStep
          : 'Processing…';
    } else {
      // Hide spinner once completed, error, cancelled, or idle
      _showProcessingIndicator = false;
      _processingProgress = 0.0;
      _processingStatus = "";
    }
  }

  // Load persisted data on app start
  Future<void> _loadPersistedData() async {
    try {
      final prefs = await SharedPreferences.getInstance();

      // Load clips
      final clipsJson = prefs.getString('saved_clips');
      if (clipsJson != null && clipsJson.isNotEmpty) {
        try {
          final clipsList = jsonDecode(clipsJson) as List<dynamic>;
          final loadedClips = clipsList
              .map((json) => ClipResult.fromJson(
                    json as Map<String, dynamic>,
                    sessionId: json['session_id'] as String?,
                  ))
              .toList();

          if (mounted) {
            setState(() {
              clips = loadedClips;
            });
            debugPrint(
                '✓ Loaded ${loadedClips.length} clips from storage');
          }
        } catch (e) {
          debugPrint('Error parsing saved clips: $e');
          await prefs.remove('saved_clips');
        }
      }

      // Load logs
      final logsJson = prefs.getString('saved_logs');
      if (logsJson != null && logsJson.isNotEmpty) {
        try {
          final logsList = jsonDecode(logsJson) as List<dynamic>;
          if (mounted) {
            setState(() {
              logs = logsList.cast<String>();
            });
            debugPrint(
                '✓ Loaded ${logsList.length} logs from storage');
          }
        } catch (e) {
          debugPrint('Error parsing saved logs: $e');
          await prefs.remove('saved_logs');
        }
      }

      // Load filter tags
      final filterTagsJson = prefs.getString('saved_filter_tags');
      if (filterTagsJson != null && filterTagsJson.isNotEmpty) {
        try {
          final tagsList = jsonDecode(filterTagsJson) as List<dynamic>;
          if (mounted) {
            setState(() {
              filterTags = tagsList.cast<String>().toSet();
            });
            debugPrint(
                '✓ Loaded ${tagsList.length} filter tags from storage');
          }
        } catch (e) {
          debugPrint('Error parsing saved filter tags: $e');
          await prefs.remove('saved_filter_tags');
        }
      }
    } catch (e) {
      debugPrint('Error accessing SharedPreferences: $e');
      if (kIsWeb) {
        debugPrint(
            'Note: If on web, make sure your browser allows localStorage');
      }
    } finally {
      if (mounted) {
        setState(() {
          _isInitialized = true;
        });
        debugPrint('✓ Data loading completed, app initialized');
      }
    }
  }

  // Save data to persistence
  Future<void> _saveData() async {
    if (!_isInitialized) {
      debugPrint('⚠ Skipping save - app not yet initialized');
      return;
    }

    try {
      final prefs = await SharedPreferences.getInstance();

      // Save clips with session ID
      if (clips.isNotEmpty) {
        final clipsJson = jsonEncode(clips.map((clip) {
          return {
            ...clip.toJson(),
            'session_id': clip.sessionId,
          };
        }).toList());
        await prefs.setString('saved_clips', clipsJson);
        debugPrint('✓ Saved ${clips.length} clips to storage');
      } else {
        await prefs.remove('saved_clips');
        debugPrint('✓ Cleared clips from storage (empty list)');
      }

      // Save logs
      if (logs.isNotEmpty) {
        final logsJson = jsonEncode(logs);
        await prefs.setString('saved_logs', logsJson);
        debugPrint('✓ Saved ${logs.length} logs to storage');
      } else {
        await prefs.remove('saved_logs');
      }

      // Save filter tags
      if (filterTags.isNotEmpty) {
        final filterTagsJson = jsonEncode(filterTags.toList());
        await prefs.setString('saved_filter_tags', filterTagsJson);
        debugPrint(
            '✓ Saved ${filterTags.length} filter tags to storage');
      } else {
        await prefs.remove('saved_filter_tags');
      }
    } catch (e) {
      debugPrint('✖ Error saving data: $e');
      if (kIsWeb) {
        debugPrint(
            'Note: If on web, make sure your browser allows localStorage');
      }
    }
  }

  void updateStatus(String msg) {
    setState(() => logs.add(msg));
    _saveData();
  }

  void clearLogs() {
    setState(() => logs.clear());
    _saveData();
  }

  void clearClips() {
    setState(() => clips.clear());
    _saveData();
  }

  void updateFilterTags(Set<String> newFilterTags) {
    setState(() => filterTags = newFilterTags);
    _saveData();
  }

  void updateClip(ClipResult updatedClip) {
    final idx =
        clips.indexWhere((e) => e.videoUrl == updatedClip.videoUrl);
    if (idx != -1) {
      setState(() => clips[idx] = updatedClip);
      _saveData();
    }
  }

  Future<void> _downloadAll() async {
    if (currentSession == null || currentSession!.sessionId.isEmpty) {
      updateStatus('✖ No active session for download');
      return;
    }
    updateStatus('📦 Starting native session download...');
    final ok = await DownloadManager.downloadSessionZip(
      onProgress: (progress) {
        updateStatus('⬇️ Download progress: ${(progress * 100).toStringAsFixed(1)}%');
      },
      onLog: updateStatus,
    );
    if (ok) {
      updateStatus('✅ All clips downloaded as ZIP!');
    } else {
      updateStatus('✖ Download failed.');
    }
  }

  void _showEnlargedVideo(ClipResult clip) {
    showDialog(
      context: context,
      barrierColor: Colors.black87,
      builder: (context) => Dialog(
        backgroundColor: Colors.transparent,
        insetPadding: const EdgeInsets.all(24),
        child: Container(
          constraints: BoxConstraints(
            maxWidth:
                MediaQuery.of(context).size.width * 0.8,
            maxHeight:
                MediaQuery.of(context).size.height * 0.8,
          ),
          decoration: BoxDecoration(
            color: Colors.black,
            borderRadius: BorderRadius.circular(16),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.5),
                blurRadius: 20,
                spreadRadius: 5,
              ),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Header with title and close button
              Container(
                padding: const EdgeInsets.all(16),
                decoration: const BoxDecoration(
                  color: Color(0xFF1F1F23),
                  borderRadius: BorderRadius.vertical(
                      top: Radius.circular(16)),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        'Video Player',
                        style: Theme.of(context)
                            .textTheme
                            .titleLarge
                            ?.copyWith(
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                            ),
                      ),
                    ),
                    IconButton(
                      onPressed: () =>
                          Navigator.of(context).pop(),
                      icon: const Icon(Icons.close,
                          color: Colors.white),
                      tooltip: 'Close',
                    ),
                  ],
                ),
              ),
              // Video player area
              Flexible(
                child: Container(
                  margin: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(12),
                    boxShadow: [
                      BoxShadow(
                        color:
                            Colors.black.withValues(alpha: 0.3),
                        blurRadius: 10,
                        spreadRadius: 2,
                      ),
                    ],
                  ),
                  child: ClipRRect(
                    borderRadius:
                        BorderRadius.circular(12),
                    child: AspectRatio(
                      aspectRatio: 16 / 9,
                      child:
                          EnlargedVideoPlayer(clip: clip),
                    ),
                  ),
                ),
              ),
              // Tags display
              if (clip.tags.isNotEmpty)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(
                      horizontal: 16, vertical: 8),
                  child: Wrap(
                    spacing: 8,
                    runSpacing: 4,
                    children: clip.tags
                        .map(
                          (tag) => Chip(
                            label: Text(
                              tag,
                              style:
                                  const TextStyle(
                                color: Colors.white,
                                fontSize: 12,
                              ),
                            ),
                            backgroundColor:
                                Colors.greenAccent
                                    .shade700,
                          ),
                        )
                        .toList(),
                  ),
                ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }

  // Debug method to check storage state
  Future<void> _debugStorage() async {
    if (kDebugMode) {
      try {
        final prefs = await SharedPreferences.getInstance();
        final keys = prefs.getKeys();
        debugPrint('🔍 Storage Debug:');
        debugPrint(
            '  Current Session ID: ${currentSession?.sessionId}');
        debugPrint('  Keys in storage: $keys');
        for (final key in keys) {
          if (key.startsWith('saved_')) {
            final value = prefs.getString(key);
            debugPrint(
                '  $key: ${value?.length ?? 0} characters');
          }
        }
        final serviceSessionId =
            await ClipService.getCurrentSessionId();
        debugPrint(
            '  ClipService Session ID: $serviceSessionId');
      } catch (e) {
        debugPrint('🔍 Storage Debug Error: $e');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    // Show loading indicator during initialization
    if (!_isInitialized) {
      return const Scaffold(
        body: Center(
          child: Column(
            mainAxisAlignment:
                MainAxisAlignment.center,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text('Loading saved data...'),
            ],
          ),
        ),
      );
    }

    // collect all tags
    final allTags = <String>{};
    for (var c in clips) {
      allTags.addAll(c.tags);
    }
    // filtered clips
    final displayed = filterTags.isEmpty
        ? clips
        : clips.where((c) {
            return c.tags.any(filterTags.contains);
          }).toList();

    return DefaultTabController(
      length: 2,
      child: Stack(
        children: [
          Scaffold(
            appBar: AppBar(
              title: Text(
                'TwitchTok'
                '${clips.isNotEmpty ? ' (${clips.length} ${clips.length == 1 ? 'clip' : 'clips'})' : ''}'
                '${_showProcessingIndicator ? ' - Processing…' : ''}'
              ),
              actions: [
                if (kIsWeb)
                  IconButton(
                    icon: const Icon(Icons.bug_report),
                    onPressed: _debugStorage,
                    tooltip: 'Debug Storage',
                  ),
                IconButton(
                  icon: const Icon(Icons.clear),
                  onPressed: clearLogs,
                  tooltip: 'Clear Logs',
                ),
                IconButton(
                  icon: const Icon(Icons.delete),
                  onPressed: clearClips,
                  tooltip: 'Clear Clips',
                ),
                IconButton(
                  icon: const Icon(Icons.download),
                  onPressed: _downloadAll,
                  tooltip: 'Download All',
                ),
                IconButton(
                  icon: const Icon(Icons.brightness_6),
                  onPressed: widget.onToggleTheme,
                  tooltip: 'Toggle Theme',
                ),
              ],
              bottom: const TabBar(
                tabs: [
                  Tab(text: 'Clips', icon: Icon(Icons.movie)),
                  Tab(text: 'Logs', icon: Icon(Icons.list)),
                ],
              ),
            ),
            body: Column(
              children: [
                // Show progress/status row when processing
                if (_showProcessingIndicator)
                  Padding(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          _processingStatus,
                          style: const TextStyle(
                              fontSize: 12, color: Colors.white70),
                        ),
                        const SizedBox(height: 4),
                        LinearProgressIndicator(
                          value: _processingProgress.clamp(0.0, 1.0),
                          minHeight: 4,
                          color: Colors.greenAccent,
                          backgroundColor: Colors.white24,
                        ),
                      ],
                    ),
                  ),

                // InputPanel inside a Card
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Card(
                    elevation: 4,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: InputPanel(
                        // We no longer use isLoading directly;
                        // showProcessingIndicator is used above.
                        isLoading: _showProcessingIndicator,
                        onStart: (
                          String source, 
                          String timeWindow, 
                          bool vod,
                          int maxClips, 
                          int segmentDuration,
                          bool includeSubtitles,
                          int minViews, 
                          ) {
                          ClipService.startPipeline(
                            source: source,
                            timeWindow: timeWindow,
                            isVOD: vod,
                            maxClips: maxClips,
                            segmentDuration: segmentDuration,
                            includeSubtitles: includeSubtitles,
                            minViews: minViews, 
                            log: updateStatus,
                          );
                        },
                        onLog: updateStatus,
                      ),
                    ),
                  ),
                ),

                // Filter chips
                if (allTags.isNotEmpty)
                  Padding(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 16),
                    child: SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Wrap(
                        spacing: 8,
                        children: [
                          ActionChip(
                            label: const Text('All'),
                            onPressed: () =>
                                updateFilterTags({}),
                          ),
                          ...allTags.map((t) => FilterChip(
                                label: Text(t),
                                selected: filterTags
                                    .contains(t),
                                onSelected: (on) {
                                  final newFilterTags =
                                      Set<String>.from(
                                          filterTags);
                                  if (on) {
                                    newFilterTags.add(t);
                                  } else {
                                    newFilterTags.remove(t);
                                  }
                                  updateFilterTags(
                                      newFilterTags);
                                },
                              )),
                        ],
                      ),
                    ),
                  ),

                // Tab Views
                Expanded(
                  child: TabBarView(
                    children: [
                      // --- Clips Grid ---
                      displayed.isEmpty &&
                              !_showProcessingIndicator
                          ? Center(
                              child: Column(
                                mainAxisAlignment:
                                    MainAxisAlignment.center,
                                children: [
                                  Icon(
                                    Icons.movie_outlined,
                                    size: 64,
                                    color: Colors.grey.shade600,
                                  ),
                                  const SizedBox(height: 16),
                                  Text(
                                    'No clips yet',
                                    style: TextStyle(
                                      fontSize: 18,
                                      color: Colors.grey.shade600,
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  Text(
                                    'Process a Twitch stream or VOD to get started',
                                    style: TextStyle(
                                      fontSize: 14,
                                      color: Colors.grey.shade500,
                                    ),
                                  ),
                                ],
                              ),
                            )
                          : Padding(
                              padding: const EdgeInsets.all(8),
                              child: LayoutBuilder(
                                builder: (ctx, bc) {
                                  final cross =
                                      (bc.maxWidth ~/ 300).clamp(1, 4);
                                  // one extra cell if processing
                                  final itemCount =
                                      displayed.length +
                                          (_showProcessingIndicator ? 1 : 0);

                                  return GridView.builder(
                                    itemCount: itemCount,
                                    gridDelegate:
                                        SliverGridDelegateWithFixedCrossAxisCount(
                                      crossAxisCount: cross,
                                      crossAxisSpacing: 12,
                                      mainAxisSpacing: 12,
                                      childAspectRatio: 16 / 11,
                                    ),
                                    itemBuilder: (c, i) {
                                      // spinner in the "extra" slot
                                      if (_showProcessingIndicator &&
                                          i == displayed.length) {
                                        return Card(
                                          elevation: 4,
                                          shape: RoundedRectangleBorder(
                                            borderRadius:
                                                BorderRadius.circular(16),
                                          ),
                                          child: const Center(
                                              child:
                                                  CircularProgressIndicator()),
                                        );
                                      }
                                      // otherwise the clip card
                                      final clip = displayed[i];
                                      return ClipResultCard(
                                        result: clip,
                                        onTagsEdited: updateClip,
                                        onVideoEnlarge: _showEnlargedVideo,
                                      );
                                    },
                                  );
                                },
                              ),
                            ),

                      // --- Logs Panel ---
                      Padding(
                        padding: const EdgeInsets.all(16),
                        child: ProcessingLog(logs: logs),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
