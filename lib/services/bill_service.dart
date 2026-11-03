// Reads the bill photo on the phone with Google ML Kit text recognition (Feature 11,
// NFR-PRV-2). Only the recognized text is sent to the server, which finds the values.
import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';

class BillService {
  static Future<String> readText(String path) async {
    final recognizer = TextRecognizer(script: TextRecognitionScript.latin);
    try {
      final result = await recognizer.processImage(InputImage.fromFilePath(path));
      return result.text;
    } finally {
      await recognizer.close();
    }
  }
}
