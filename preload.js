const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld(
  'api', {
    getCalendars: () => ipcRenderer.invoke('get-calendars'),
    sendPrompt: (prompt) => ipcRenderer.invoke('send-prompt', prompt),
    processAudio: (formData) => ipcRenderer.invoke('process-audio', formData),
    onCalendarUpdate: (callback) => {
      ipcRenderer.on('calendar-update', (event, data) => callback(data));
      return () => {
        ipcRenderer.removeAllListeners('calendar-update');
      };
    }
  }
);
