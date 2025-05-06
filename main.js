const { app, BrowserWindow, ipcMain, Tray, Menu } = require('electron');
const path = require('path');
const axios = require('axios');
const Store = require('electron-store');
const fs = require('fs');
const FormData = require('form-data');

// Initialize store for app settings
const store = new Store();

// Keep a global reference of the window object
let mainWindow;
let tray;
let backendProcess;
let isQuitting = false;

// Backend API URL
const backendUrl = 'http://localhost:5000';

function createWindow() {
  // Create the browser window
  mainWindow = new BrowserWindow({
    width: 1000,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, 'assets/icon.png')
  });

  // Load the index.html file
  mainWindow.loadFile(path.join(__dirname, 'index.html'));

  // Open DevTools in development mode
  if (process.env.NODE_ENV === 'development') {
    mainWindow.webContents.openDevTools();
  }

  // Handle window close event
  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
      return false;
    }
  });
}

function createTray() {
  tray = new Tray(path.join(__dirname, 'assets/tray-icon.png'));
  const contextMenu = Menu.buildFromTemplate([
    { 
      label: 'Open Calendar AI Agent', 
      click: () => { mainWindow.show(); } 
    },
    { 
      label: 'Agent Status', 
      submenu: [
        { 
          label: 'Running in Background',
          type: 'radio',
          checked: true
        }
      ]
    },
    { type: 'separator' },
    { 
      label: 'Quit', 
      click: () => {
        isQuitting = true;
        app.quit();
      } 
    }
  ]);
  
  tray.setToolTip('Calendar AI Agent');
  tray.setContextMenu(contextMenu);
  
  tray.on('click', () => {
    mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show();
  });
}

function startBackendServer() {
  // Check if backend is already running
  axios.get(`${backendUrl}/health`)
    .then(() => {
      console.log('Backend server is already running');
    })
    .catch(() => {
      console.log('Starting backend server...');
      // In a production app, we would start the Python backend here
      // For now, we'll rely on the npm script to start it
    });
}

// This method will be called when Electron has finished initialization
app.whenReady().then(() => {
  createWindow();
  createTray();
  startBackendServer();

  app.on('activate', function () {
    // On macOS it's common to re-create a window in the app when the
    // dock icon is clicked and there are no other windows open.
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

// Handle IPC messages from renderer process
ipcMain.handle('get-calendars', async () => {
  try {
    const response = await axios.get(`${backendUrl}/calendars`);
    return response.data;
  } catch (error) {
    console.error('Error fetching calendars:', error);
    return { error: 'Failed to fetch calendars' };
  }
});

ipcMain.handle('send-prompt', async (event, prompt) => {
  try {
    const response = await axios.post(`${backendUrl}/process-prompt`, { prompt });
    return response.data;
  } catch (error) {
    console.error('Error processing prompt:', error);
    return { error: 'Failed to process prompt' };
  }
});

ipcMain.handle('process-audio', async (event, formData) => {
  try {
    // Create a temporary file to save the audio blob
    const tempFilePath = path.join(app.getPath('temp'), `recording-${Date.now()}.wav`);
    
    // Extract the audio blob from the formData
    const audioBlob = formData.get('audio');
    const audioBuffer = Buffer.from(await audioBlob.arrayBuffer());
    
    // Write the audio data to a temporary file
    fs.writeFileSync(tempFilePath, audioBuffer);
    
    // Create a form data object for the API request
    const apiFormData = new FormData();
    apiFormData.append('audio', fs.createReadStream(tempFilePath));
    
    // Send the audio file to the backend for processing
    const response = await axios.post(`${backendUrl}/speech-to-text`, apiFormData, {
      headers: {
        ...apiFormData.getHeaders(),
      },
    });
    
    // Clean up the temporary file
    fs.unlinkSync(tempFilePath);
    
    return response.data;
  } catch (error) {
    console.error('Error processing audio:', error);
    return { error: 'Failed to process audio' };
  }
});

// Quit when all windows are closed, except on macOS
app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') app.quit();
});

// Handle app quit
app.on('before-quit', () => {
  isQuitting = true;
});
