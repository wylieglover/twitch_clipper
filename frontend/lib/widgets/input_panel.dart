import 'package:flutter/material.dart';

class InputPanel extends StatefulWidget {
  final bool isLoading;
  final void Function(
    String source,
    String timeWindow,
    bool isVOD,
    int maxClips,
    int segmentDuration,
    bool includeSubtitles, 
    int minViews
  ) onStart;
  final ValueChanged<String> onLog;

  const InputPanel({
    super.key,
    required this.isLoading,
    required this.onStart,
    required this.onLog,
  });

  @override
  State<InputPanel> createState() => _InputPanelState();
}

class _InputPanelState extends State<InputPanel> {
  final TextEditingController _ctrl = TextEditingController();
  bool _vod = false;
  String _window = 'day';
  int _max = 1;
  int _seg = 30;
  bool _includeSubtitles = false;
  int _minViews = 0;  
  
  void _onSubmit() {
    final src = _ctrl.text.trim();
    if (src.isEmpty || widget.isLoading) return;

    widget.onLog('🔄 Starting ${_vod ? "VOD" : "Clips"} for $src');
    widget.onStart(
      src, 
      _window, 
      _vod,
      _max,
      _seg, 
      _includeSubtitles, 
      _minViews
    );
  }

  @override
  Widget build(BuildContext context) {
    // Subtle background fill color based on theme
    final fillColor = Theme.of(context).brightness == Brightness.dark
        ? Colors.grey[900]!.withValues(alpha: 0.7)
        : Colors.grey[200]!.withValues(alpha: 0.7);

    const borderRadius = 12.0;

    InputDecoration inputDecoration(String label) => InputDecoration(
      labelText: label,
      filled: true,
      fillColor: fillColor,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(borderRadius),
        borderSide: BorderSide.none,
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
    );

    return Column(
      children: [
        // Source Field
        TextField(
          controller: _ctrl,
          enabled: !widget.isLoading,
          decoration: inputDecoration('Twitch Username or VOD URL').copyWith(
            prefixIcon: const Icon(Icons.videocam),
          ),
        ),
        const SizedBox(height: 12),

        // Mode Toggle + Dropdowns + Start
        Row(
          children: [
            // Clips / VOD toggle
            SegmentedButton<bool>(
              segments: const [
                ButtonSegment(value: false, label: Text('Clips')),
                ButtonSegment(value: true, label: Text('VOD')),
              ],
              selected: <bool>{_vod},
              onSelectionChanged: widget.isLoading
                  ? null
                  : (s) => setState(() => _vod = s.contains(true)),
            ),
            const SizedBox(width: 12),

            // Time Window
            Expanded(
              child: DropdownButtonFormField<String>(
                value: _window,
                decoration: inputDecoration('Time Window'),
                items: ['day', 'week', 'month', 'all']
                    .map((w) => DropdownMenuItem(value: w, child: Text(w)))
                    .toList(),
                onChanged: widget.isLoading
                    ? null
                    : (v) => setState(() => _window = v!),
                dropdownColor: fillColor,
                borderRadius: BorderRadius.circular(borderRadius),
              ),
            ),
            const SizedBox(width: 12),

            // Max Clips
            SizedBox(
              width: 64,
              child: TextFormField(
                initialValue: '$_max',
                enabled: !widget.isLoading, 
                decoration: inputDecoration('Max'),
                keyboardType: TextInputType.number,
                onChanged: widget.isLoading
                    ? null
                    : (v) {
                        final n = int.tryParse(v) ?? _max;
                        setState(() => _max = n.clamp(1, 20));
                      },
              ),
            ),
            const SizedBox(width: 12),

            // Segment Duration
            SizedBox(
              width: 80,
              child: DropdownButtonFormField<int>(
                value: _seg,
                decoration: inputDecoration('Segment'),
                items: [15, 30, 60]
                    .map((s) => DropdownMenuItem(value: s, child: Text('$s s')))
                    .toList(),
                onChanged: widget.isLoading
                    ? null
                    : (v) => setState(() => _seg = v!),
                dropdownColor: fillColor,
                borderRadius: BorderRadius.circular(borderRadius),
              ),
            ),
            const SizedBox(width: 12),

             // Min Views
            SizedBox(
              width: 80,
              child: TextFormField(
                initialValue: '$_minViews',
                decoration: inputDecoration('Min Views'),
                keyboardType: TextInputType.number,
                enabled: !widget.isLoading,
                onChanged: (v) {
                  final parsed = int.tryParse(v) ?? 0;
                  setState(() => _minViews = parsed.clamp(0, 1000000000));
                },
              ),
            ),
            const SizedBox(width: 12),

            // ───── Compact “Include Subtitles” IconButton ─────
            Tooltip(
              message: _includeSubtitles
                    ? 'Disable burned-in subtitles'
                    : 'Enable burned-in subtitles',
              child: IconButton(
                icon: Icon(
                  _includeSubtitles
                      ? Icons.closed_caption
                      : Icons.closed_caption_off,
                    color: _includeSubtitles
                      ? Colors.greenAccent
                      : Colors.grey.shade600,
                ),
                onPressed: widget.isLoading
                    ? null
                    : () {
                        setState(() => _includeSubtitles = !_includeSubtitles);
                      },
              ),
            ),
           const SizedBox(width: 8),
            // Start Button
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8)),
                elevation: 4,
                padding:
                    const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
              ),
              onPressed: widget.isLoading ? null : _onSubmit,
              child: AnimatedSwitcher(
                duration: const Duration(milliseconds: 200),
                transitionBuilder: (c, a) => ScaleTransition(
                  scale: a,
                  child: FadeTransition(opacity: a, child: c),
                ),
                child: widget.isLoading
                    ? const SizedBox(
                        key: ValueKey('busy'),
                        width: 24,
                        height: 24,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text(
                        'Start',
                        key: ValueKey('idle'),
                      ),
              ),
            ),
          ],
        ),
      ],
    );
  }
}
