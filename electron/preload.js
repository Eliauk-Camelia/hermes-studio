const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('camelia', {
  platform: process.platform,
  version: process.env.npm_package_version || '0.0.5',
});
