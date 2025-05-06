// DOM Elements
const calendarsList = document.getElementById('calendars-list');
const addCalendarBtn = document.getElementById('add-calendar-btn');
const promptInput = document.getElementById('prompt-input');
const sendPromptBtn = document.getElementById('send-prompt-btn');
const responseContainer = document.getElementById('response-container');
const activityLog = document.getElementById('activity-log');
const modal = document.getElementById('modal');
const closeBtn = document.querySelector('.close-btn');
const providerBtns = document.querySelectorAll('.provider-btn');
const voiceInputContainer = document.getElementById('voice-input-container');

// Voice input component
class VoiceInput {
  constructor(container, onTranscription) {
    this.container = container;
    this.onTranscription = onTranscription;
    this.isRecording = false;
    this.isProcessing = false;
    this.audioContext = null;
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.render();
    this.setupEventListeners();
  }

  render() {
    this.container.innerHTML = `
      <div class="voice-input-container">
        <button class="voice-button" id="voice-button">
          <svg viewBox="0 0 24 24" width="24" height="24">
            <path 
              fill="currentColor" 
              d="M12,2A3,3 0 0,1 15,5V11A3,3 0 0,1 12,14A3,3 0 0,1 9,11V5A3,3 0 0,1 12,2M19,11C19,14.53 16.39,17.44 13,17.93V21H11V17.93C7.61,17.44 5,14.53 5,11H7A5,5 0 0,0 12,16A5,5 0 0,0 17,11H19Z" 
            />
          </svg>
          <span class="voice-button-text">Speak</span>
        </button>
      </div>
      <div class="audio-visualizer" id="audio-visualizer" style="display: none;"></div>
    `;

    this.voiceButton = this.container.querySelector('#voice-button');
    this.visualizer = this.container.querySelector('#audio-visualizer');
  }

  setupEventListeners() {
    this.voiceButton.addEventListener('click', () => this.toggleRecording());
  }

  async toggleRecording() {
    if (this.isProcessing) return;

    if (!this.isRecording) {
      await this.startRecording();
    } else {
      await this.stopRecording();
    }
  }

  async startRecording() {
    try {
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Initialize audio context
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      
      // Set up audio analyzer for visualization
      const analyser = this.audioContext.createAnalyser();
      const microphone = this.audioContext.createMediaStreamSource(stream);
      microphone.connect(analyser);
      analyser.fftSize = 256;
      
      // Set up media recorder
      this.mediaRecorder = new MediaRecorder(stream);
      this.audioChunks = [];
      
      // Handle data available event
      this.mediaRecorder.ondataavailable = (event) => {
        this.audioChunks.push(event.data);
      };
      
      // Handle recording stop event
      this.mediaRecorder.onstop = async () => {
        // Create audio blob
        const audioBlob = new Blob(this.audioChunks, { type: 'audio/wav' });
        
        // Process the audio
        await this.processAudio(audioBlob);
      };
      
      // Start recording
      this.mediaRecorder.start();
      this.isRecording = true;
      
      // Update UI
      this.voiceButton.classList.add('recording');
      this.voiceButton.querySelector('.voice-button-text').textContent = 'Listening...';
      this.visualizer.style.display = 'flex';
      
      // Start visualization
      this.startVisualization(analyser);
      
    } catch (error) {
      console.error('Error starting recording:', error);
      alert('Could not access microphone. Please check permissions.');
    }
  }

  async stopRecording() {
    if (!this.mediaRecorder || this.mediaRecorder.state === 'inactive') return;
    
    // Stop recording
    this.mediaRecorder.stop();
    this.isRecording = false;
    
    // Update UI
    this.voiceButton.classList.remove('recording');
    this.voiceButton.classList.add('processing');
    this.voiceButton.querySelector('.voice-button-text').textContent = 'Processing...';
    
    // Stop all tracks in the stream
    this.mediaRecorder.stream.getTracks().forEach(track => track.stop());
  }

  async processAudio(audioBlob) {
    this.isProcessing = true;
    
    try {
      // Create a FormData object to send the audio file
      const formData = new FormData();
      formData.append('audio', audioBlob, 'recording.wav');
      
      // Process the audio through the backend
      const response = await window.api.processAudio(formData);
      
      if (response && response.text) {
        // Display the transcribed text in the prompt input
        promptInput.value = response.text;
        
        // If there's a prompt response, process it automatically
        if (response.prompt_response) {
          // Display the response
          responseContainer.innerHTML = `<div class="agent-response">${response.prompt_response.message}</div>`;
          
          // Add to activity log
          addActivityItem(`Voice prompt: "${response.text}"`);
          addActivityItem(`Agent: "${response.prompt_response.message}"`);
        } else {
          // Otherwise, let the user review the transcription before sending
          addActivityItem(`Transcribed: "${response.text}"`);
        }
      } else if (response && response.error) {
        console.error('Speech recognition error:', response.error);
        responseContainer.innerHTML = `<p class="error">Error: ${response.error}</p>`;
      }
    } catch (error) {
      console.error('Error processing audio:', error);
      responseContainer.innerHTML = `<p class="error">Error processing audio: ${error.message}</p>`;
    } finally {
      // Reset UI
      this.isProcessing = false;
      this.voiceButton.classList.remove('processing');
      this.voiceButton.querySelector('.voice-button-text').textContent = 'Speak';
      this.visualizer.style.display = 'none';
      this.visualizer.innerHTML = '';
    }
  }

  startVisualization(analyser) {
    if (!this.isRecording) return;
    
    // Create visualization bars
    this.visualizer.innerHTML = '';
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    
    // Create initial bars
    for (let i = 0; i < 20; i++) {
      const bar = document.createElement('div');
      bar.className = 'visualizer-bar';
      bar.style.height = '2px';
      this.visualizer.appendChild(bar);
    }
    
    const bars = this.visualizer.querySelectorAll('.visualizer-bar');
    
    // Update visualization
    const updateVisualization = () => {
      if (!this.isRecording) return;
      
      analyser.getByteFrequencyData(dataArray);
      
      // Update bar heights based on frequency data
      for (let i = 0; i < bars.length; i++) {
        const index = Math.floor(i * bufferLength / bars.length);
        const value = dataArray[index] / 255;
        const height = Math.max(2, value * 30);
        bars[i].style.height = `${height}px`;
      }
      
      // Continue animation
      requestAnimationFrame(updateVisualization);
    };
    
    updateVisualization();
  }
}

// Load connected calendars
async function loadCalendars() {
  try {
    const calendars = await window.api.getCalendars();
    
    if (calendars.error) {
      calendarsList.innerHTML = `<p class="error">Error: ${calendars.error}</p>`;
      return;
    }
    
    if (calendars.length === 0) {
      calendarsList.innerHTML = `<p class="empty-state">No calendars connected. Click "Add Calendar" to get started.</p>`;
      return;
    }
    
    renderCalendarsList(calendars);
  } catch (error) {
    calendarsList.innerHTML = `<p class="error">Error loading calendars: ${error.message}</p>`;
  }
}

// Render calendars list
function renderCalendarsList(calendars) {
  calendarsList.innerHTML = '';
  
  calendars.forEach(calendar => {
    const calendarItem = document.createElement('div');
    calendarItem.className = 'calendar-item';
    
    const providerIcon = getProviderIcon(calendar.provider);
    
    calendarItem.innerHTML = `
      <img src="${providerIcon}" alt="${calendar.provider}">
      <span class="calendar-name">${calendar.name}</span>
      <div class="calendar-actions">
        <button class="disconnect-btn" data-id="${calendar.id}">Disconnect</button>
      </div>
    `;
    
    calendarsList.appendChild(calendarItem);
  });
  
  // Add event listeners to disconnect buttons
  document.querySelectorAll('.disconnect-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const calendarId = e.target.dataset.id;
      disconnectCalendar(calendarId);
    });
  });
}

// Get provider icon path
function getProviderIcon(provider) {
  const providers = {
    'google': 'assets/google-calendar.png',
    'microsoft': 'assets/microsoft-calendar.png',
    'apple': 'assets/apple-calendar.png'
  };
  
  return providers[provider.toLowerCase()] || 'assets/default-calendar.png';
}

// Disconnect calendar
async function disconnectCalendar(calendarId) {
  // In a real app, we would call the API to disconnect the calendar
  // For now, we'll just show a confirmation and refresh the list
  if (confirm('Are you sure you want to disconnect this calendar?')) {
    addActivityItem('Calendar disconnected');
    loadCalendars();
  }
}

// Set up event listeners
function setupEventListeners() {
  // Add calendar button
  addCalendarBtn.addEventListener('click', () => {
    modal.style.display = 'block';
  });
  
  // Close modal
  closeBtn.addEventListener('click', () => {
    modal.style.display = 'none';
  });
  
  // Close modal when clicking outside
  window.addEventListener('click', (e) => {
    if (e.target === modal) {
      modal.style.display = 'none';
    }
  });
  
  // Provider buttons
  providerBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      const provider = e.currentTarget.dataset.provider;
      connectCalendar(provider);
    });
  });
  
  // Send prompt button
  sendPromptBtn.addEventListener('click', sendPrompt);
  
  // Send prompt on Enter key (with Shift for new line)
  promptInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendPrompt();
    }
  });
}

// Connect calendar
function connectCalendar(provider) {
  // In a real app, we would redirect to OAuth flow
  // For now, we'll just simulate a successful connection
  modal.style.display = 'none';
  
  // Show loading state
  calendarsList.innerHTML = '<div class="loading">Connecting to calendar...</div>';
  
  // Simulate API call delay
  setTimeout(() => {
    addActivityItem(`Connected to ${provider} Calendar`);
    loadCalendars();
  }, 1500);
}

// Send prompt to AI agent
async function sendPrompt() {
  const prompt = promptInput.value.trim();
  
  if (!prompt) {
    return;
  }
  
  // Show loading state
  responseContainer.innerHTML = '<div class="loading">Processing your request...</div>';
  
  try {
    // Send prompt to backend
    const response = await window.api.sendPrompt(prompt);
    
    if (response.error) {
      responseContainer.innerHTML = `<p class="error">Error: ${response.error}</p>`;
      return;
    }
    
    // Display response
    responseContainer.innerHTML = `<div class="agent-response">${response.message}</div>`;
    
    // Add to activity log
    addActivityItem(`Prompt: "${prompt}"`);
    addActivityItem(`Agent: "${response.message}"`);
    
    // Clear input
    promptInput.value = '';
  } catch (error) {
    responseContainer.innerHTML = `<p class="error">Error: ${error.message}</p>`;
  }
}

// Add item to activity log
function addActivityItem(description) {
  const now = new Date();
  const timeString = now.toLocaleTimeString();
  
  const activityItem = document.createElement('div');
  activityItem.className = 'activity-item';
  
  activityItem.innerHTML = `
    <div class="activity-time">${timeString}</div>
    <div class="activity-description">${description}</div>
  `;
  
  // Add to the top of the list
  activityLog.insertBefore(activityItem, activityLog.firstChild);
  
  // Remove empty state if present
  const emptyState = activityLog.querySelector('.empty-state');
  if (emptyState) {
    emptyState.remove();
  }
}

// Initialize the app
document.addEventListener('DOMContentLoaded', async () => {
  loadCalendars();
  setupEventListeners();
  
  // Initialize voice input
  new VoiceInput(voiceInputContainer, (text) => {
    promptInput.value = text;
  });
  
  // Register for calendar updates from the main process
  window.api.onCalendarUpdate((data) => {
    addActivityItem(`Calendar updated: ${data.message}`);
    loadCalendars(); // Refresh calendars list
  });
});
