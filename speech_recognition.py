import os
import logging
import tempfile
import whisper
import soundfile as sf
import numpy as np
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class SpeechRecognizer:
    """Speech recognition module using Whisper"""
    
    def __init__(self, model_name: str = "base"):
        """Initialize the speech recognizer with the specified model"""
        self.model_name = model_name
        self.model = None
        self.initialized = False
    
    async def initialize(self):
        """Load the Whisper model"""
        try:
            if not self.initialized:
                logger.info(f"Loading Whisper model: {self.model_name}")
                self.model = whisper.load_model(self.model_name)
                self.initialized = True
                logger.info("Whisper model loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Error loading Whisper model: {str(e)}")
            return False
    
    async def transcribe_audio(self, audio_file_path: str) -> Dict[str, Any]:
        """Transcribe audio file to text using Whisper"""
        if not self.initialized:
            await self.initialize()
        
        if not self.model:
            return {"error": "Speech recognition model not initialized"}
        
        try:
            # Transcribe the audio file
            result = self.model.transcribe(audio_file_path)
            
            # Extract the transcribed text
            text = result.get("text", "").strip()
            
            if not text:
                return {"error": "No speech detected"}
            
            logger.info(f"Transcribed text: {text}")
            return {"text": text}
        
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            return {"error": f"Error transcribing audio: {str(e)}"}
    
    async def process_audio_data(self, audio_data: bytes, sample_rate: int = 16000) -> Dict[str, Any]:
        """Process raw audio data and transcribe it"""
        if not self.initialized:
            await self.initialize()
        
        try:
            # Create a temporary file to save the audio data
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Convert and save the audio data to the temporary file
            # This assumes the audio data is in a format that soundfile can read
            try:
                # Try to read the audio data directly
                data, samplerate = sf.read(audio_data)
                # Resample if necessary
                if samplerate != sample_rate:
                    # Simple resampling (for more advanced resampling, consider using librosa)
                    data = self._resample(data, samplerate, sample_rate)
                sf.write(temp_path, data, sample_rate)
            except Exception as e:
                # If direct reading fails, write the bytes to the file
                with open(temp_path, "wb") as f:
                    f.write(audio_data)
            
            # Transcribe the audio file
            result = await self.transcribe_audio(temp_path)
            
            # Clean up the temporary file
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"Error removing temporary file: {str(e)}")
            
            return result
        
        except Exception as e:
            logger.error(f"Error processing audio data: {str(e)}")
            return {"error": f"Error processing audio data: {str(e)}"}
    
    def _resample(self, data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Simple resampling function"""
        # This is a very basic resampling method
        # For production, consider using a library like librosa for better quality
        if orig_sr == target_sr:
            return data
        
        # Calculate ratio
        ratio = target_sr / orig_sr
        
        # For mono audio
        if len(data.shape) == 1:
            # Calculate new length
            new_length = int(len(data) * ratio)
            # Create indices for interpolation
            indices = np.arange(new_length) / ratio
            # Use linear interpolation
            resampled = np.interp(indices, np.arange(len(data)), data)
            return resampled
        
        # For stereo audio
        elif len(data.shape) == 2:
            # Calculate new length
            new_length = int(data.shape[0] * ratio)
            # Create indices for interpolation
            indices = np.arange(new_length) / ratio
            # Use linear interpolation for each channel
            resampled = np.zeros((new_length, data.shape[1]))
            for channel in range(data.shape[1]):
                resampled[:, channel] = np.interp(indices, np.arange(data.shape[0]), data[:, channel])
            return resampled
        
        else:
            raise ValueError("Unsupported audio format")
