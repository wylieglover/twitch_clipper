import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';
import '../models/clip_result.dart';

class EnlargedVideoPlayer extends StatefulWidget {
  final ClipResult clip;

  const EnlargedVideoPlayer({
    super.key,
    required this.clip,
  });

  @override
  State<EnlargedVideoPlayer> createState() => _EnlargedVideoPlayerState();
}

class _EnlargedVideoPlayerState extends State<EnlargedVideoPlayer> {
  VideoPlayerController? _controller;
  bool _initialized = false;
  bool _showControls = true;
  bool _isPlaying = false;
  bool _isLoading = true;
  Duration _position = Duration.zero;
  Duration _duration = Duration.zero;
  double _volume = 1.0;
  bool _showVolumeSlider = false;

  @override
  void initState() {
    super.initState();
    _initializeVideo();
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  void _initializeVideo() {
    _controller = VideoPlayerController.networkUrl(Uri.parse(widget.clip.videoUrl))
      ..initialize().then((_) {
        if (!mounted) return;
        setState(() {
          _initialized = true;
          _isLoading = false;
          _duration = _controller!.value.duration;
        });
        
        // Add listener for position updates
        _controller!.addListener(_videoListener);
        
        // Auto-play when initialized
        _playVideo();
      }).catchError((error) {
        debugPrint('Video initialization error: $error');
        if (mounted) {
          setState(() {
            _isLoading = false;
          });
        }
      });
  }

  void _videoListener() {
    if (!mounted || _controller == null) return;
    
    final position = _controller!.value.position;
    final duration = _controller!.value.duration;
    final isPlaying = _controller!.value.isPlaying;
    
    if (_position != position || _isPlaying != isPlaying || _duration != duration) {
      setState(() {
        _position = position;
        _isPlaying = isPlaying;
        _duration = duration;
      });
    }
  }

  void _playVideo() {
    if (_controller != null && _initialized) {
      _controller!.play();
      setState(() {
        _isPlaying = true;
      });
    }
  }

  void _pauseVideo() {
    if (_controller != null && _initialized) {
      _controller!.pause();
      setState(() {
        _isPlaying = false;
      });
    }
  }

  void _togglePlayPause() {
    if (!_initialized || _controller == null) return;
    
    if (_isPlaying) {
      _pauseVideo();
    } else {
      _playVideo();
    }
  }

  void _seekTo(Duration position) {
    if (_controller != null && _initialized) {
      _controller!.seekTo(position);
    }
  }

  void _skip(Duration offset) {
    if (_controller != null && _initialized) {
      final newPosition = _position + offset;
      final clampedPosition = Duration(
        milliseconds: newPosition.inMilliseconds.clamp(0, _duration.inMilliseconds),
      );
      _seekTo(clampedPosition);
    }
  }

  void _setVolume(double volume) {
    if (_controller != null && _initialized) {
      _controller!.setVolume(volume);
      setState(() {
        _volume = volume;
      });
    }
  }

  void _toggleControls() {
    setState(() {
      _showControls = !_showControls;
    });
  }

  void _toggleVolumeSlider() {
    setState(() {
      _showVolumeSlider = !_showVolumeSlider;
    });
  }

  String _formatDuration(Duration duration) {
    final hours = duration.inHours;
    final minutes = duration.inMinutes % 60;
    final seconds = duration.inSeconds % 60;
    
    if (hours > 0) {
      return '$hours:${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
    } else {
      return '$minutes:${seconds.toString().padLeft(2, '0')}';
    }
  }

  Widget _buildLoadingState() {
    return Container(
      color: Colors.black,
      child: Stack(
        children: [
          // Thumbnail as background
          Positioned.fill(
            child: Image.network(
              widget.clip.thumbnailUrl,
              fit: BoxFit.contain,
              errorBuilder: (context, error, stackTrace) {
                return Container(
                  color: Colors.grey[900],
                  child: const Center(
                    child: Icon(
                      Icons.error_outline,
                      color: Colors.white54,
                      size: 64,
                    ),
                  ),
                );
              },
            ),
          ),
          // Loading indicator
          Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const CircularProgressIndicator(
                  color: Colors.greenAccent,
                  strokeWidth: 3,
                ),
                const SizedBox(height: 16),
                Text(
                  'Loading video...',
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.8),
                    fontSize: 16,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildVideoPlayer() {
    return GestureDetector(
      onTap: _toggleControls,
      child: Container(
        color: Colors.black,
        child: Stack(
          children: [
            // Video player
            Positioned.fill(
              child: Center(
                child: AspectRatio(
                  aspectRatio: _controller!.value.aspectRatio,
                  child: VideoPlayer(_controller!),
                ),
              ),
            ),
            
            // Controls overlay
            if (_showControls)
              _buildControlsOverlay(),
          ],
        ),
      ),
    );
  }

  Widget _buildControlsOverlay() {
    return Positioned.fill(
      child: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Colors.black.withValues(alpha: 0.8),
              Colors.transparent,
              Colors.transparent,
              Colors.black.withValues(alpha: 0.8),
            ],
            stops: const [0.0, 0.25, 0.75, 1.0],
          ),
        ),
        child: Column(
          children: [
            // Top controls
            _buildTopControls(),
            
            // Center play/pause
            Expanded(
              child: Center(
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    // Skip backward
                    _buildControlButton(
                      icon: Icons.replay_10,
                      onPressed: () => _skip(const Duration(seconds: -10)),
                      size: 40,
                    ),
                    
                    const SizedBox(width: 32),
                    
                    // Play/Pause
                    Container(
                      decoration: BoxDecoration(
                        color: Colors.black.withValues(alpha: 0.7),
                        shape: BoxShape.circle,
                      ),
                      child: _buildControlButton(
                        icon: _isPlaying ? Icons.pause : Icons.play_arrow,
                        onPressed: _togglePlayPause,
                        size: 56,
                      ),
                    ),
                    
                    const SizedBox(width: 32),
                    
                    // Skip forward
                    _buildControlButton(
                      icon: Icons.forward_10,
                      onPressed: () => _skip(const Duration(seconds: 10)),
                      size: 40,
                    ),
                  ],
                ),
              ),
            ),
            
            // Bottom controls
            _buildBottomControls(),
          ],
        ),
      ),
    );
  }

  Widget _buildTopControls() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          Expanded(
            child: Text(
              'Video Player',
              style: const TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          // Volume control
          _buildControlButton(
            icon: _volume == 0 ? Icons.volume_off : Icons.volume_up,
            onPressed: _toggleVolumeSlider,
            size: 24,
          ),
          const SizedBox(width: 8),
          // Close button
          _buildControlButton(
            icon: Icons.close,
            onPressed: () => Navigator.of(context).pop(),
            size: 24,
          ),
        ],
      ),
    );
  }

  Widget _buildBottomControls() {
    return Container(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          // Volume slider
          if (_showVolumeSlider)
            Container(
              margin: const EdgeInsets.only(bottom: 16),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.black.withValues(alpha: 0.7),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  const Icon(Icons.volume_down, color: Colors.white, size: 20),
                  Expanded(
                    child: SliderTheme(
                      data: SliderTheme.of(context).copyWith(
                        activeTrackColor: Colors.greenAccent,
                        inactiveTrackColor: Colors.white24,
                        thumbColor: Colors.greenAccent,
                        overlayColor: Colors.greenAccent.withValues(alpha: 0.2),
                        trackHeight: 3,
                        thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 8),
                      ),
                      child: Slider(
                        value: _volume,
                        onChanged: _setVolume,
                        min: 0.0,
                        max: 1.0,
                      ),
                    ),
                  ),
                  const Icon(Icons.volume_up, color: Colors.white, size: 20),
                ],
              ),
            ),
          
          // Progress bar
          SliderTheme(
            data: SliderTheme.of(context).copyWith(
              activeTrackColor: Colors.greenAccent,
              inactiveTrackColor: Colors.white24,
              thumbColor: Colors.greenAccent,
              overlayColor: Colors.greenAccent.withValues(alpha: 0.2),
              trackHeight: 4,
              thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 10),
            ),
            child: Slider(
              value: _duration.inMilliseconds > 0 
                  ? _position.inMilliseconds / _duration.inMilliseconds 
                  : 0.0,
              onChanged: (value) {
                final newPosition = Duration(
                  milliseconds: (value * _duration.inMilliseconds).round(),
                );
                _seekTo(newPosition);
              },
              min: 0.0,
              max: 1.0,
            ),
          ),
          
          // Time display
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                _formatDuration(_position),
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                ),
              ),
              Text(
                _formatDuration(_duration),
                style: const TextStyle(
                  color: Colors.white70,
                  fontSize: 14,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildControlButton({
    required IconData icon,
    required VoidCallback onPressed,
    required double size,
  }) {
    return IconButton(
      onPressed: onPressed,
      icon: Icon(
        icon,
        size: size,
        color: Colors.white,
      ),
      splashRadius: size * 0.7,
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading || !_initialized || _controller == null) {
      return _buildLoadingState();
    }

    return _buildVideoPlayer();
  }
}