import os
import time
from groq import Groq
from django.conf import settings
from .exceptions import VoiceProcessingError

class VoiceRecognitionService:
    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
    
    def transcribe_audio_file(self, audio_file, filename):
        """
        Transcribe an uploaded audio file using Whisper.
        
        Args:
            audio_file: Django's UploadedFile object
            filename: str - filename to use for the API
            
        Returns:
            dict: Transcription result
        """
        try:
            # Ensure we're at the start of the file
            audio_file.seek(0)
            
            transcription = self.client.audio.transcriptions.create(
                file=(filename, audio_file.read(), 'audio/mpeg'),  # Proper MIME type
                model="whisper-large-v3-turbo",
                response_format="verbose_json",
            )
            
            return {
                'text': transcription.text,
                'language': transcription.language,
                'duration': transcription.duration,
                'segments': transcription.segments
            }
        except Exception as e:
            raise VoiceProcessingError(f"Speech recognition failed: {str(e)}")