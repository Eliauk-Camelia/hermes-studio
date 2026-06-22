const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('camelia', {
  platform: process.platform,
  version: process.env.npm_package_version || '0.0.5',
});

contextBridge.exposeInMainWorld('settings', {
  getProviders: () => ipcRenderer.invoke('get-providers'),
  addProvider: (p) => ipcRenderer.invoke('add-provider', p),
  updateProvider: (id, p) => ipcRenderer.invoke('update-provider', id, p),
  deleteProvider: (id) => ipcRenderer.invoke('delete-provider', id),
  setActive: (id, model) => ipcRenderer.invoke('set-active', id, model),
  saveActive: (id, model) => ipcRenderer.invoke('save-active', id, model),
  restartBackend: () => ipcRenderer.invoke('restart-backend'),
  testConnection: (url, key) => ipcRenderer.invoke('test-connection', url, key),
  getBackendStatus: () => ipcRenderer.invoke('get-backend-status'),
  launchBackend: () => ipcRenderer.invoke('launch-backend'),
});
