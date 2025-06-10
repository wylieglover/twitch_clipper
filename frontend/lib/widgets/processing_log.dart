import 'package:flutter/material.dart';

class ProcessingLog extends StatefulWidget {
  final List<String> logs;
  const ProcessingLog({super.key, required this.logs});

  @override
  State<ProcessingLog> createState() => _ProcessingLogState();
}

class _ProcessingLogState extends State<ProcessingLog> {
  final ScrollController _ctl = ScrollController();

  @override
  void didUpdateWidget(covariant ProcessingLog old) {
    super.didUpdateWidget(old);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_ctl.hasClients) _ctl.jumpTo(_ctl.position.maxScrollExtent);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.black87,
      padding: const EdgeInsets.all(12),
      child: ListView.builder(
        controller: _ctl,
        itemCount: widget.logs.length,
        itemBuilder: (ctx, i) => Text(
          widget.logs[i],
          style: const TextStyle(fontSize:12, color:Colors.greenAccent),
        ),
      ),
    );
  }
}
