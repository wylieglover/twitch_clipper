// lib/services/clip/download_manager.dart

import 'dart:io';
import 'session_manager.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:path_provider/path_provider.dart';
import '../../models/clip_result.dart';
import '../../config.dart';
import 'package:http/http.dart' as http;

class DownloadManager {
  static Future<bool> downloadVideo({
    required ClipResult clip,
    String? customPath,
    Function(double)? onProgress,
    Function(String)? onLog,
  }) async {
    try {
      onLog?.call("📥 Starting download: ${clip.video}");
      if (Platform.isAndroid || Platform.isIOS) {
        final status = await Permission.storage.request();
        if (!status.isGranted) {
          onLog?.call("✖ Storage permission denied");
          return false;
        }
      }
      Directory downloadDir;
      if (customPath != null) {
        downloadDir = Directory(customPath);
      } else {
        if (Platform.isAndroid) {
          downloadDir = Directory('/storage/emulated/0/Download/TwitchClips');
        } else if (Platform.isIOS) {
          final appDir = await getApplicationDocumentsDirectory();
          downloadDir = Directory('${appDir.path}/Downloads');
        } else {
          final appDir = await getDownloadsDirectory() ?? await getApplicationDocumentsDirectory();
          downloadDir = Directory('${appDir.path}/TwitchClips');
        }
      }
      if (!await downloadDir.exists()) {
        await downloadDir.create(recursive: true);
      }
      final videoUri = Uri.parse('${Config.apiBaseUrl}/api/session/download/${clip.sessionId}/${Uri.encodeComponent(clip.video)}');
      final request = http.Request('GET', videoUri);
      final response = await request.send();
      if (response.statusCode != 200) {
        onLog?.call("✖ Download failed: HTTP ${response.statusCode}");
        return false;
      }
      final fileName = clip.video.split('/').last;
      final filePath = '${downloadDir.path}/$fileName';
      final file = File(filePath);
      final sink = file.openWrite();
      int downloadedBytes = 0;
      final totalBytes = response.contentLength ?? 0;
      await response.stream.listen(
        (chunk) {
          sink.add(chunk);
          downloadedBytes += chunk.length;
          if (totalBytes > 0) {
            final progress = downloadedBytes / totalBytes;
            onProgress?.call(progress);
          }
        },
        onDone: () {
          sink.close();
          onLog?.call("✅ Downloaded: $filePath");
        },
        onError: (error) {
          sink.close();
          onLog?.call("✖ Download error: $error");
        },
      ).asFuture();
      return true;
    } catch (e) {
      onLog?.call("✖ Download exception: $e");
      return false;
    }
  }

   static Future<bool> downloadSessionZip({
    String? customPath,
    Function(double)? onProgress,
    Function(String)? onLog,
  }) async {
    if (currentSession == null) {
      onLog?.call("✖ No active session for download");
      return false;
    }
    
    try {
      onLog?.call("📦 Starting session download: ${currentSession!.sessionId}");
      
      // Check permissions
      if (Platform.isAndroid || Platform.isIOS) {
        final status = await Permission.storage.request();
        if (!status.isGranted) {
          onLog?.call("✖ Storage permission denied");
          return false;
        }
      }
      
      Directory downloadDir;
      if (customPath != null) {
        downloadDir = Directory(customPath);
      } else {
        if (Platform.isAndroid) {
          downloadDir = Directory('/storage/emulated/0/Download/TwitchClips');
        } else if (Platform.isIOS) {
          final appDir = await getApplicationDocumentsDirectory();
          downloadDir = Directory('${appDir.path}/Downloads');
        } else {
          final appDir = await getDownloadsDirectory() ?? 
                         await getApplicationDocumentsDirectory();
          downloadDir = Directory('${appDir.path}/TwitchClips');
        }
      }
      
      if (!await downloadDir.exists()) {
        await downloadDir.create(recursive: true);
      }
      
      // Download the session zip
      final zipUri = Uri.parse('${Config.apiBaseUrl}/api/session/download_session/${currentSession!.sessionId}');
      final request = http.Request('GET', zipUri);
      final response = await request.send();
      
      if (response.statusCode != 200) {
        onLog?.call("✖ Session download failed: HTTP ${response.statusCode}");
        return false;
      }
      
      final fileName = 'clips_${currentSession!.sessionId.substring(0, 8)}.zip';
      final filePath = '${downloadDir.path}/$fileName';
      final file = File(filePath);
      
      final sink = file.openWrite();
      int downloadedBytes = 0;
      final totalBytes = response.contentLength ?? 0;
      
      await response.stream.listen(
        (chunk) {
          sink.add(chunk);
          downloadedBytes += chunk.length;
          
          if (totalBytes > 0) {
            final progress = downloadedBytes / totalBytes;
            onProgress?.call(progress);
          }
        },
        onDone: () {
          sink.close();
          onLog?.call("✅ Session downloaded: $filePath");
        },
        onError: (error) {
          sink.close();
          onLog?.call("✖ Session download error: $error");
        },
      ).asFuture();
      
      return true;
      
    } catch (e) {
      onLog?.call("✖ Session download exception: $e");
      return false;
    }
  }
}
