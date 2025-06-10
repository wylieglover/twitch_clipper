// lib/widgets/clip_result_card.dart

import 'dart:convert';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:twitchtok/config.dart';
import 'package:video_player/video_player.dart';
import 'package:font_awesome_flutter/font_awesome_flutter.dart';

// ignore: avoid_web_libraries_in_flutter, deprecated_member_use
import 'dart:html' as html;

import '../models/clip_result.dart';
import '../services/clip/download_manager.dart' show DownloadManager;

class ClipResultCard extends StatefulWidget {
  final ClipResult result;
  final ValueChanged<ClipResult> onTagsEdited;
  final ValueChanged<ClipResult> onVideoEnlarge;
  final VoidCallback? onCardVideoPlay; // to pause other cards

  const ClipResultCard({
    super.key,
    required this.result,
    required this.onTagsEdited,
    required this.onVideoEnlarge,
    this.onCardVideoPlay,
  });

  @override
  State<ClipResultCard> createState() => _ClipResultCardState();
}

class _ClipResultCardState extends State<ClipResultCard>
    with SingleTickerProviderStateMixin {
  VideoPlayerController? _controller;
  late final AnimationController _entryController;

  bool _initialized = false;
  bool _isPlaying   = false;
  bool _isLoading   = false;
  bool _hasError    = false;

  @override
  void initState() {
    super.initState();
    _entryController = AnimationController(
      duration: const Duration(milliseconds: 500),
      vsync: this,
    )..forward();
  }

  @override
  void dispose() {
    _entryController.dispose();
    _controller?.dispose();
    super.dispose();
  }

  void _loadVideo() {
    if (_controller != null || _isLoading) return;

    setState(() {
      _isLoading = true;
      _hasError  = false;
    });

    _controller = VideoPlayerController.networkUrl(
      Uri.parse(widget.result.videoUrl),
    )
      ..initialize().then((_) {
        if (!mounted) return;
        setState(() {
          _initialized = true;
          _isLoading   = false;
        });
        _controller!.addListener(_videoListener);
      }).catchError((error) {
        debugPrint('Video initialization error: $error');
        if (mounted) {
          setState(() {
            _isLoading = false;
            _hasError  = true;
          });
        }
      });
  }
  
  Future<void> _uploadToTikTok() async {
    final clip = widget.result;
    final sessionId = clip.sessionId;
    if (sessionId == null || sessionId.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("⚠️ No session ID found for this clip.")),
      );
      return;
    }

    // 1) Show a dialog to get description + hashtags
    String description = clip.description;
    String hashtags = clip.hashtags.join(","); // prefill with existing hashtags, if any

    final descController = TextEditingController(text: description);
    final hashController = TextEditingController(text: hashtags);

    final didUpload = await showDialog<bool>(
      context: context,
      builder: (ctx) {
        return AlertDialog(
          backgroundColor: Colors.grey[850],
          title: const Text("Upload to TikTok", style: TextStyle(color: Colors.white)),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: descController,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  labelText: "Description",
                  labelStyle: const TextStyle(color: Colors.white70),
                  enabledBorder: const UnderlineInputBorder(
                    borderSide: BorderSide(color: Colors.white30),
                  ),
                  focusedBorder: const UnderlineInputBorder(
                    borderSide: BorderSide(color: Colors.greenAccent),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: hashController,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  labelText: "Hashtags (comma‐separated)",
                  labelStyle: const TextStyle(color: Colors.white70),
                  hintText: "e.g. funny,cats,viral",
                  hintStyle: const TextStyle(color: Colors.white38),
                  enabledBorder: const UnderlineInputBorder(
                    borderSide: BorderSide(color: Colors.white30),
                  ),
                  focusedBorder: const UnderlineInputBorder(
                    borderSide: BorderSide(color: Colors.greenAccent),
                  ),
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              child: const Text("Cancel", style: TextStyle(color: Colors.redAccent)),
              onPressed: () => Navigator.of(ctx).pop(false),
            ),
            TextButton(
              child: const Text("Upload", style: TextStyle(color: Colors.greenAccent)),
              onPressed: () => Navigator.of(ctx).pop(true),
            ),
          ],
        );
      },
    );

    // 2) If user tapped "Upload", send the POST
    if (didUpload == true) {
      if (!mounted) return;
      
      description = descController.text.trim();
      hashtags = hashController.text.trim();

      final uri = Uri.parse("${Config.apiBaseUrl}/api/tiktok/upload");
      final request = http.MultipartRequest('POST', uri)
        ..fields['session_id'] = sessionId
        ..fields['video_filename'] = clip.video
        ..fields['description'] = description
        ..fields['hashtags'] = hashtags
        // optional: override privacy or post_mode here:
        ..fields['privacy_level'] = "PUBLIC_TO_EVERYONE"
        ..fields['post_mode'] = "DIRECT_POST";

      // Show a loading SnackBar
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("⏳ Uploading to TikTok…")),
      );

      try {
        final streamedResponse = await request.send();
        final responseBody = await streamedResponse.stream.bytesToString();
        if (!mounted) return;
        
        if (streamedResponse.statusCode == 200) {
          final Map<String, dynamic> data = jsonDecode(responseBody);
    
          if (data['status'] == 'uploaded') {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text("✅ Uploaded to TikTok!")),
            );
          } else {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text("⚠️ TikTok returned: ${data.toString()}")),
            );
          }
        } else {
          
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text("✖ HTTP ${streamedResponse.statusCode}: $responseBody")),
          );
        }
      } catch (e) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("✖ Upload failed: $e")),
        );
      }
    }
  }
  
  void _videoListener() {
    if (!mounted || _controller == null) return;

    final isPlaying = _controller!.value.isPlaying;
    final hasEnded  = _controller!.value.position >= _controller!.value.duration;

    if (hasEnded && _isPlaying) {
      setState(() {
        _isPlaying = false;
      });
    } else if (_isPlaying != isPlaying) {
      setState(() {
        _isPlaying = isPlaying;
      });
    }
  }

  void _togglePlay() {
    if (!_initialized || _controller == null) {
      _loadVideo();
      return;
    }
    if (_controller!.value.isPlaying) {
      _pauseVideo();
    } else {
      _playVideo();
    }
  }

  void _playVideo() {
    if (_controller != null && _initialized) {
      widget.onCardVideoPlay?.call(); // Pause other cards
      _controller!.play();
      setState(() {
        _isPlaying = true;
      });
    }
  }

  void _pauseVideo() {
    if (_initialized && _controller != null && _controller!.value.isPlaying) {
      _controller!.pause();
      setState(() {
        _isPlaying = false;
      });
    }
  }

  /// Exposed so parent can pause this card if needed
  void pauseVideo() => _pauseVideo();

  void _copyLink() {
    Clipboard.setData(ClipboardData(text: widget.result.videoUrl));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Link copied'), duration: Duration(seconds: 2)),
    );
  }

  Future<void> _download() async {
    if (kIsWeb) {
      // Web: Use the anchor trick for instant browser download
      final url = widget.result.downloadVideoUrl;
      html.AnchorElement(href: url)
        ..setAttribute('download', '')
        ..click();
    } else {
      // Native: Use your DownloadManager!
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('⬇️ Starting native download...')),
      );
      final ok = await DownloadManager.downloadVideo(
        clip: widget.result,
        onProgress: (progress) {
          // Optionally show a progress indicator or SnackBar
          // e.g.:
          // ScaffoldMessenger.of(context).showSnackBar(
          //   SnackBar(content: Text('⬇️ ${(progress * 100).toStringAsFixed(1)}% downloaded')));
        },
        onLog: (msg) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(msg), duration: const Duration(seconds: 2)),
          );
        },
      );
      if (!mounted) return;
      if (ok) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('✅ Download complete!'), duration: Duration(seconds: 2)),
        );
      } else {
        
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('✖ Download failed.'), duration: Duration(seconds: 2)),
        );
      }
    }
  }

  void _showTranscript() {
    showDialog(
      context: context,
      builder: (_) => Dialog(
        backgroundColor: Colors.grey[900],
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        insetPadding: const EdgeInsets.symmetric(horizontal: 24, vertical: 48),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxHeight: 400),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Show tags at top
              Padding(
                padding: const EdgeInsets.all(8),
                child: Wrap(
                  spacing: 4,
                  children: widget.result.tags
                      .map(
                        (t) => Chip(
                          label: Text(t,
                              style: const TextStyle(color: Colors.white, fontSize: 10)),
                          backgroundColor: Colors.greenAccent.shade700,
                        ),
                      )
                      .toList(),
                ),
              ),

              // Header "Transcript"
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                decoration: BoxDecoration(
                  color: Colors.green.shade900,
                  borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
                ),
                child: const Text(
                  'Transcript',
                  style: TextStyle(
                      color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                ),
              ),

              // Scrollable transcript
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(16),
                  child: Text(
                    widget.result.transcript,
                    style: const TextStyle(
                      color: Colors.greenAccent,
                      fontSize: 14,
                      fontFamily: 'monospace',
                      height: 1.4,
                    ),
                  ),
                ),
              ),

              // Close button
              Align(
                alignment: Alignment.centerRight,
                child: TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Close', style: TextStyle(color: Colors.tealAccent)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _editTags() {
    final currentTags = List<String>.from(widget.result.tags);
    showDialog(
      context: context,
      builder: (_) {
        String newTag = '';
        return StatefulBuilder(builder: (context, setDialogState) {
          return Dialog(
            backgroundColor: Colors.grey[900],
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            insetPadding: const EdgeInsets.symmetric(horizontal: 24, vertical: 48),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 400),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Header "Edit Tags"
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    decoration: BoxDecoration(
                      color: Colors.green.shade900,
                      borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
                    ),
                    child: const Text(
                      'Edit Tags',
                      style: TextStyle(
                          color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                    ),
                  ),

                  // Current tags as InputChips
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    child: Wrap(
                      spacing: 8,
                      children: currentTags
                          .map(
                            (t) => InputChip(
                              label: Text(t),
                              onDeleted: () {
                                setDialogState(() => currentTags.remove(t));
                              },
                              deleteIconColor: Colors.redAccent,
                            ),
                          )
                          .toList(),
                    ),
                  ),

                  // TextField to add a new tag
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    child: Row(
                      children: [
                        Expanded(
                          child: TextField(
                            style: const TextStyle(color: Colors.white),
                            decoration: const InputDecoration(
                              hintText: 'New tag',
                              hintStyle: TextStyle(color: Colors.grey),
                            ),
                            onChanged: (v) => newTag = v.trim(),
                            onSubmitted: (v) {
                              final trimmed = v.trim();
                              if (trimmed.isNotEmpty && !currentTags.contains(trimmed)) {
                                setDialogState(() => currentTags.add(trimmed));
                                newTag = '';
                              }
                            },
                          ),
                        ),
                        TextButton(
                          onPressed: () {
                            final trimmed = newTag.trim();
                            if (trimmed.isNotEmpty && !currentTags.contains(trimmed)) {
                              setDialogState(() => currentTags.add(trimmed));
                              newTag = '';
                            }
                          },
                          child: const Text('Add', style: TextStyle(color: Colors.tealAccent)),
                        ),
                      ],
                    ),
                  ),

                  const Spacer(),

                  // "Save" button
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton(
                      onPressed: () {
                        final updated = widget.result.copyWith(tags: currentTags);
                        widget.onTagsEdited(updated);
                        Navigator.pop(context);
                      },
                      child: const Text('Save', style: TextStyle(color: Colors.greenAccent)),
                    ),
                  ),
                ],
              ),
            ),
          );
        });
      },
    );
  }

  void _handleVideoEnlarge() {
    _pauseVideo();
    widget.onVideoEnlarge(widget.result);
  }

  /// Builds the circular overlay (spinner / error icon / play/pause icon).
  Widget _buildVideoOverlay() {
    return Positioned.fill(
      child: Container(
        color: Colors.black54,
        child: Center(
          child: Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.black.withValues(alpha: 0.8),
              shape: BoxShape.circle,
            ),
            child: _isLoading
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.greenAccent,
                    ),
                  )
                : _hasError
                    ? const Icon(
                        Icons.error_outline,
                        color: Colors.redAccent,
                        size: 32,
                      )
                    : Icon(
                        _isPlaying ? Icons.pause : Icons.play_arrow,
                        color: Colors.white,
                        size: 32,
                      ),
          ),
        ),
      ),
    );
  }

  /// Either show the embedded VideoPlayer (if initialized), or a thumbnail image.
  Widget _buildThumbnailOrVideo() {
    return Stack(
      children: [
        // 1. Video frame if initialized
        Positioned.fill(
          child: (_initialized && _controller != null)
              ? VideoPlayer(_controller!)
              : Image.network(
                  widget.result.thumbnailUrl,
                  fit: BoxFit.cover,
                  errorBuilder: (context, error, stackTrace) {
                    return Container(
                      color: Colors.grey[800],
                      child: const Center(
                        child: Icon(Icons.error_outline,
                            color: Colors.white54, size: 32),
                      ),
                    );
                  },
                ),
        ),

        // 2. Overlay if not playing OR loading OR error
        if (!_isPlaying || _isLoading || _hasError) _buildVideoOverlay(),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: CurvedAnimation(parent: _entryController, curve: Curves.easeOut),
      child: Card(
        elevation: 4,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        clipBehavior: Clip.hardEdge,
        child: LayoutBuilder(builder: (context, constraints) {
          // Use flexible layout with larger video section
          final totalWidth = constraints.maxWidth;
          
          // Keep a 16:9 aspect for video, but no more than 65% of card height
          final idealVideoHeight = totalWidth / (16 / 9);
          final maxVideoHeight = constraints.maxHeight * 0.65;
          final videoHeight = (idealVideoHeight < maxVideoHeight)
              ? idealVideoHeight
              : maxVideoHeight;

          return Column(
            children: [
              // ─── 1) Video Section ───────────────────────────────────────
              SizedBox(
                height: videoHeight,
                width: double.infinity,
                child: Stack(
                  children: [
                    // Thumbnail or video
                    Positioned.fill(
                      child: GestureDetector(
                        onTap: _togglePlay,
                        child: _buildThumbnailOrVideo(),
                      ),
                    ),

                    // Top-left: up to 3 tags - FIXED OVERFLOW
                    if (widget.result.tags.isNotEmpty)
                      Positioned(
                        left: 8,
                        top: 8,
                        right: 80, // Reserve space for fullscreen button
                        child: Wrap(
                          spacing: 4,
                          runSpacing: 4,
                          children: widget.result.tags
                              .take(3)
                              .map((t) => Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                    decoration: BoxDecoration(
                                      color: Colors.greenAccent.shade700,
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    child: Text(
                                      t,
                                      style: const TextStyle(
                                        color: Colors.white, 
                                        fontSize: 10,
                                        fontWeight: FontWeight.w500,
                                      ),
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ))
                              .toList(),
                        ),
                      ),

                    // Top-right: fullscreen button
                    Positioned(
                      right: 8,
                      top: 8,
                      child: Container(
                        decoration: BoxDecoration(
                          color: Colors.black54,
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: IconButton(
                          icon: const Icon(Icons.fullscreen, size: 20, color: Colors.white),
                          tooltip: 'Enlarge video',
                          onPressed: _handleVideoEnlarge,
                        ),
                      ),
                    ),
                  ],
                ),
              ),

              // ─── 2) Scrollable Content Section ───────────────────────────
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      // View Count Section
                      if (widget.result.viewCount! > 0) ...[
                        Row(
                          children: [
                            const Icon(
                              Icons.remove_red_eye,
                              size: 16,
                                color: Colors.grey,
                            ),
                            const SizedBox(width: 4),
                            Text(
                              '${widget.result.viewCount} views',
                                style: const TextStyle(
                                  fontSize: 12,
                                  color: Colors.grey,
                                ),
                              ),
                          ],
                        ),
                        const SizedBox(height: 8),
                      ],
                      // Description Section
                      if (widget.result.description.isNotEmpty) ...[
                        const Row(
                          children: [
                            Icon(Icons.description, size: 16, color: Colors.blueAccent),
                            SizedBox(width: 4),
                            Text(
                              'Description',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                color: Colors.white70,
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 6),
                        Text(
                          widget.result.description,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                            height: 1.3,
                          ),
                        ),
                        const SizedBox(height: 16),
                      ],
                      
                      // Hashtags Section
                      if (widget.result.hashtags.isNotEmpty) ...[
                        const Row(
                          children: [
                            Icon(Icons.tag, size: 16, color: Colors.greenAccent),
                            SizedBox(width: 4),
                            Text(
                              'Hashtags',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                color: Colors.white70,
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 6,
                          runSpacing: 6,
                          children: widget.result.hashtags
                              .map((hashtag) => Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 8, 
                                      vertical: 4
                                    ),
                                    decoration: BoxDecoration(
                                      color: Colors.greenAccent.shade700.withValues(alpha: 0.8),
                                      borderRadius: BorderRadius.circular(12),
                                      border: Border.all(
                                        color: Colors.greenAccent.withValues(alpha: 0.3),
                                        width: 1,
                                      ),
                                    ),
                                    child: Text(
                                      hashtag.startsWith('#') ? hashtag : '#$hashtag',
                                      style: const TextStyle(
                                        color: Colors.white,
                                        fontSize: 11,
                                        fontWeight: FontWeight.w500,
                                      ),
                                    ),
                                  ))
                              .toList(),
                        ),
                      ],
                      
                      // Empty state if no content
                      if (widget.result.description.isEmpty && widget.result.hashtags.isEmpty)
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: 20),
                          child: Center(
                            child: Text(
                              'No content available',
                              style: TextStyle(
                                color: Colors.white54,
                                fontSize: 12,
                                fontStyle: FontStyle.italic,
                              ),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),

              // ─── 3) Controls Row (fixed height) ──────────────────────────
              Container(
                height: 48,
                width: double.infinity,
                color: Colors.black54,
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: [
                    IconButton(
                      icon: Icon(
                        _initialized &&
                                _controller != null &&
                                _controller!.value.isPlaying
                            ? Icons.pause_circle
                            : Icons.play_circle,
                        size: 24,
                        color: Colors.greenAccent,
                      ),
                      tooltip: 'Play/Pause',
                      onPressed: _initialized ? _togglePlay : _loadVideo,
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(minWidth: 40, minHeight: 40),
                    ),
                    IconButton(
                      icon: const Icon(Icons.edit, size: 20, color: Colors.tealAccent),
                      tooltip: 'Edit tags',
                      onPressed: _editTags,
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(minWidth: 40, minHeight: 40),
                    ),
                    IconButton(
                      icon: const Icon(Icons.notes, size: 20, color: Colors.tealAccent),
                      tooltip: 'View transcript',
                      onPressed: _showTranscript,
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(minWidth: 40, minHeight: 40),
                    ),
                    IconButton(
                      icon: const Icon(Icons.link, size: 20, color: Colors.tealAccent),
                      tooltip: 'Copy link',
                      onPressed: _copyLink,
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(minWidth: 40, minHeight: 40),
                    ),
                    IconButton(
                      icon: const Icon(Icons.download, size: 20, color: Colors.tealAccent),
                      tooltip: 'Download',
                      onPressed: _download,
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(minWidth: 40, minHeight: 40),
                    ),
                     IconButton(
                     icon: const FaIcon(FontAwesomeIcons.tiktok, size: 16, color: Colors.white),
                      tooltip: 'Upload to TikTok',
                      onPressed: _uploadToTikTok,
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(minWidth: 40, minHeight: 40),
                    ),
                  ],
                ),
              ),
            ],
          );
        }),
      ),
    );
  }
}