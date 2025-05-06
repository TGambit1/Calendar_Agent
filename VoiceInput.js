import React, { useState, useEffect } from 'react';
import { ReactMic } from 'react-mic';

/**
 * VoiceInput component for recording and processing voice commands
 * @param {function} onTranscription - Callback function that receives the transcribed text
 */
const VoiceInput = ({ onTranscription }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [audioBlob, setAudioBlob] = useState(null);
  const [visualizerData, setVisualizerData] = useState([]);

  // Toggle recording state
  const toggleRecording = () => {
    if (isProcessing) return;
    setIsRecording(!isRecording);
  };

  // Handle audio data during recording (for visualization)
  const onData = (recordedData) => {
    // Update visualizer data if needed
    const audioData = recordedData.getChannelData(0) || [];
    if (audioData.length > 0) {
      // Sample the audio data for visualization
      const sampledData = [];
      const sampleRate = Math.floor(audioData.length / 50);
      for (let i = 0; i < audioData.length; i += sampleRate) {
        sampledData.push(Math.abs(audioData[i]));
      }
      setVisualizerData(sampledData);
    }
  };

  // Handle recording stop event
  const onStop = async (recordedBlob) => {
    setAudioBlob(recordedBlob.blob);
    setIsProcessing(true);
    
    try {
      await processAudio(recordedBlob.blob);
    } catch (error) {
      console.error('Error processing audio:', error);
    } finally {
      setIsProcessing(false);
    }
  };

  // Process the recorded audio through the backend
  const processAudio = async (blob) => {
    // Create a FormData object to send the audio file
    const formData = new FormData();
    formData.append('audio', blob, 'recording.wav');
    
    try {
      // Send to backend for processing
      const response = await window.api.processAudio(formData);
      
      if (response && response.text) {
        onTranscription(response.text);
      } else if (response && response.error) {
        console.error('Speech recognition error:', response.error);
      }
    } catch (error) {
      console.error('Error sending audio to backend:', error);
      throw error;
    }
  };

  return (
    <div className="voice-input-container">
      <button 
        className={`voice-button ${isRecording ? 'recording' : ''} ${isProcessing ? 'processing' : ''}`}
        onClick={toggleRecording}
        disabled={isProcessing}
        title={isProcessing ? 'Processing...' : (isRecording ? 'Stop recording' : 'Start voice input')}
      >
        <svg viewBox="0 0 24 24" width="24" height="24">
          {isProcessing ? (
            // Loading spinner icon
            <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="30 60" />
          ) : (
            // Microphone icon
            <path 
              fill="currentColor" 
              d="M12,2A3,3 0 0,1 15,5V11A3,3 0 0,1 12,14A3,3 0 0,1 9,11V5A3,3 0 0,1 12,2M19,11C19,14.53 16.39,17.44 13,17.93V21H11V17.93C7.61,17.44 5,14.53 5,11H7A5,5 0 0,0 12,16A5,5 0 0,0 17,11H19Z" 
            />
          )}
        </svg>
        <span className="voice-button-text">
          {isProcessing ? 'Processing...' : (isRecording ? 'Listening...' : 'Speak')}
        </span>
      </button>
      
      {/* Hidden ReactMic component for recording */}
      <ReactMic
        record={isRecording}
        className="sound-wave"
        onStop={onStop}
        onData={onData}
        strokeColor="#4285F4"
        backgroundColor="#FFFFFF"
        mimeType="audio/wav"
        sampleRate={44100}
        channelCount={1}
      />
      
      {/* Audio visualizer */}
      {isRecording && (
        <div className="audio-visualizer">
          {visualizerData.map((value, index) => (
            <div 
              key={index} 
              className="visualizer-bar" 
              style={{ height: `${Math.max(2, value * 50)}px` }}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default VoiceInput;
