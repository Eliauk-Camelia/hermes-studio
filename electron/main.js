const { app, BrowserWindow, Menu, dialog, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const Store = require('electron-store');
const http = require('http');
const https = require('https');

// ─── 加密存储 ──────────────────────────────────
// 加密 key 由机器指纹确定性派生：不同用户/机器 key 不同，
// 同一台机器每次启动 key 相同，不依赖系统密钥环状态。
function getEncryptionKey() {
  return crypto
    .createHash('sha256')
    .update([
      require('os').hostname(),
      require('os').userInfo().username,
      app.getPath('userData'),
      'camelia-studio-v1',
    ].join(':'))
    .digest('hex');
}

// store 在 app.whenReady() 中初始化
let store = null;

function initStore() {
  if (store) return;

  const storeOptions = {
    name: 'config',
    encryptionKey: getEncryptionKey(),
    defaults: {
      providers: [],
      active_provider_id: null,
      active_model: null,
    },
  };

  try {
    store = new Store(storeOptions);
  } catch (e) {
    // 配置文件损坏 → 删除后重建
    console.error('配置文件损坏，正在重建:', e.message);
    const userData = app.getPath('userData');
    try { fs.unlinkSync(path.join(userData, 'config.json')); } catch {}
    store = new Store(storeOptions);
  }
}

// ─── 自动更新（生产环境才加载）──────────────────
let autoUpdater = null;
try {
  autoUpdater = require('electron-updater').autoUpdater;
} catch (e) {
  console.log('electron-updater 未安装，跳过自动更新');
}

let mainWindow;
let pythonProcess = null;

const isDev = !app.isPackaged;
const PORT = 8648;

// ══════════════════════════════════════════════════
//  Python 后端管理
// ══════════════════════════════════════════════════

function waitForBackend(retries = 20, delay = 400) {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const check = () => {
      attempts++;
      const req = http.get(`http://127.0.0.1:${PORT}/api/health`, (res) => {
        resolve();
      });
      req.on('error', () => {
        if (attempts >= retries) {
          reject(new Error('后端启动超时'));
        } else {
          setTimeout(check, delay);
        }
      });
      req.setTimeout(2000, () => { req.destroy(); });
    };
    setTimeout(check, 500);
  });
}

function startPythonBackend(provider) {
  const pythonExe = process.platform === 'win32' ? 'python' : 'python3';
  const serverPath = path.join(__dirname, '..', 'src', 'server.py');

  const env = {
    PATH: process.env.PATH,
    HOME: process.env.HOME,
  };

  if (provider) {
    env.OPENAI_API_KEY = provider.api_key;
    env.OPENAI_BASE_URL = provider.base_url;
    env.LLM_MODEL = provider.active_model;
  }

  console.log(`[启动] ${provider?.name || '无提供商'} / ${provider?.active_model || '无模型'}`);

  pythonProcess = spawn(pythonExe, [serverPath], {
    env,
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  pythonProcess.stdout.on('data', (data) => {
    console.log(`[Python] ${data}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`[Python] ${data}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`Python 进程退出，代码: ${code}`);
    pythonProcess = null;
  });

  return waitForBackend();
}

function killPythonBackend() {
  if (pythonProcess) {
    pythonProcess.kill('SIGTERM');
    pythonProcess = null;
  }
}

// 获取当前活跃的 provider 配置（含 active_model 字段）
function getActiveProviderConfig() {
  const providers = store.get('providers', []);
  const activeId = store.get('active_provider_id');
  const activeModel = store.get('active_model');
  if (!activeId || !activeModel || providers.length === 0) return null;
  const provider = providers.find(p => p.id === activeId);
  if (!provider) return null;
  if (!provider.api_key || !provider.base_url) return null; // Key 或 URL 为空视为未配置
  return { ...provider, active_model: activeModel };
}

// ══════════════════════════════════════════════════
//  IPC 处理器
// ══════════════════════════════════════════════════

function maskKey(key) {
  if (!key || key.length < 8) return key ? '***' : '';
  return key.slice(0, 4) + '****' + key.slice(-4);
}

ipcMain.handle('get-providers', () => {
  const providers = store.get('providers', []);
  const activeId = store.get('active_provider_id');
  const activeModel = store.get('active_model');
  return {
    providers: providers.map(p => ({
      ...p,
      api_key: maskKey(p.api_key), // 前端不拿明文 Key
    })),
    active_provider_id: activeId,
    active_model: activeModel,
  };
});

ipcMain.handle('add-provider', (_event, provider) => {
  const providers = store.get('providers', []);
  const newProvider = {
    id: 'prov_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    name: provider.name || '未命名',
    base_url: provider.base_url || 'https://api.deepseek.com/v1',
    api_key: provider.api_key || '',
    models: provider.models || [],
  };
  providers.push(newProvider);
  store.set('providers', providers);

  // 如果是第一个提供商，自动设为活跃
  if (providers.length === 1 && newProvider.models.length > 0) {
    store.set('active_provider_id', newProvider.id);
    store.set('active_model', newProvider.models[0]);
  }

  return { ok: true, provider: { ...newProvider, api_key: maskKey(newProvider.api_key) } };
});

ipcMain.handle('update-provider', (_event, id, updates) => {
  const providers = store.get('providers', []);
  const idx = providers.findIndex(p => p.id === id);
  if (idx === -1) return { ok: false, error: '提供商不存在' };

  if (updates.name !== undefined) providers[idx].name = updates.name;
  if (updates.base_url !== undefined) providers[idx].base_url = updates.base_url;
  if (updates.api_key !== undefined) providers[idx].api_key = updates.api_key;
  if (updates.models !== undefined) providers[idx].models = updates.models;

  store.set('providers', providers);
  return { ok: true, provider: { ...providers[idx], api_key: maskKey(providers[idx].api_key) } };
});

ipcMain.handle('delete-provider', (_event, id) => {
  let providers = store.get('providers', []);
  const deleted = providers.find(p => p.id === id);
  providers = providers.filter(p => p.id !== id);
  store.set('providers', providers);

  // 如果删除的是活跃提供商，清除活跃状态
  if (store.get('active_provider_id') === id) {
    store.set('active_provider_id', providers.length > 0 ? providers[0].id : null);
    store.set('active_model', providers.length > 0 && providers[0].models.length > 0
      ? providers[0].models[0] : null);
  }

  return { ok: true };
});

ipcMain.handle('set-active', async (_event, providerId, model) => {
  const providers = store.get('providers', []);
  const provider = providers.find(p => p.id === providerId);
  if (!provider) return { ok: false, error: '提供商不存在' };
  if (!provider.models.includes(model)) return { ok: false, error: '模型不在提供商列表中' };

  store.set('active_provider_id', providerId);
  store.set('active_model', model);

  // 重启后端以应用新配置
  try {
    killPythonBackend();
    await new Promise(r => setTimeout(r, 600)); // 等待端口释放
    const config = { ...provider, active_model: model };
    await startPythonBackend(config);
    return { ok: true };
  } catch (e) {
    return { ok: false, error: `后端启动失败: ${e.message}` };
  }
});

// 仅保存活跃设置，不重启后端（生成中切换时使用）
ipcMain.handle('save-active', (_event, providerId, model) => {
  const providers = store.get('providers', []);
  const provider = providers.find(p => p.id === providerId);
  if (!provider) return { ok: false, error: '提供商不存在' };
  if (!provider.models.includes(model)) return { ok: false, error: '模型不在提供商列表中' };

  store.set('active_provider_id', providerId);
  store.set('active_model', model);
  return { ok: true };
});

// 重启后端，使用当前活跃配置
ipcMain.handle('restart-backend', async () => {
  const config = getActiveProviderConfig();
  if (!config) return { ok: false, error: '无活跃提供商' };
  try {
    killPythonBackend();
    await new Promise(r => setTimeout(r, 600));
    await startPythonBackend(config);
    return { ok: true };
  } catch (e) {
    return { ok: false, error: `后端启动失败: ${e.message}` };
  }
});

ipcMain.handle('test-connection', async (_event, baseUrl, apiKey) => {
  return new Promise((resolve) => {
    const cleanUrl = baseUrl.replace(/\/$/, '');
    const url = new URL(cleanUrl);
    const transport = url.protocol === 'https:' ? https : http;

    function makeRequest(method, path, body) {
      return new Promise((reqResolve, reqReject) => {
        const req = transport.request(cleanUrl + path, {
          method,
          headers: {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/json',
          },
          timeout: 8000,
        }, (res) => {
          let data = '';
          res.on('data', chunk => data += chunk);
          res.on('end', () => reqResolve({ status: res.statusCode, body: data }));
        });
        req.on('error', reqReject);
        req.on('timeout', () => { req.destroy(); reqReject(new Error('超时')); });
        if (body) req.write(JSON.stringify(body));
        req.end();
      });
    }

    // 步骤 1：GET /models
    makeRequest('GET', '/models').then(({ status, body }) => {
      if (status === 401 || status === 403) {
        return resolve({ ok: false, error: 'API Key 无效 (HTTP ' + status + ')' });
      }
      if (status === 200) {
        try {
          const data = JSON.parse(body);
          // 尝试多种 model 列表格式
          let modelIds = [];
          if (Array.isArray(data.data)) {
            modelIds = data.data.map(m => m.id).filter(id => id && typeof id === 'string');
          } else if (Array.isArray(data)) {
            modelIds = data.map(m => m.id || m).filter(id => id && typeof id === 'string');
          } else if (data.models && Array.isArray(data.models)) {
            modelIds = data.models.map(m => m.id || m).filter(id => id && typeof id === 'string');
          }
          if (modelIds.length > 0) return resolve({ ok: true, models: modelIds });
          // 200 但没模型 → 连接正常，模型需手动填
          return resolve({ ok: true, models: [], hint: '连接正常，请手动填写模型名' });
        } catch {
          return resolve({ ok: true, models: [], hint: '连接正常，请手动填写模型名' });
        }
      }
      // /models 失败 → 尝试 chat completion 验证
      return tryChatCompletion();
    }).catch(() => {
      // 网络错误 → 也尝试 chat completion
      tryChatCompletion();
    });

    function tryChatCompletion() {
      makeRequest('POST', '/chat/completions', {
        model: 'unused',
        messages: [{ role: 'user', content: 'hi' }],
        max_tokens: 1,
      }).then(({ status, body }) => {
        if (status === 401 || status === 403) {
          resolve({ ok: false, error: 'API Key 无效' });
        } else if (status >= 200 && status < 500) {
          // 任何 2xx/4xx 都说明连接通了（model not found 也算通）
          resolve({ ok: true, models: [], hint: '连接正常（/models 不可用），请手动填写模型名' });
        } else {
          resolve({ ok: false, error: '连接失败 (HTTP ' + status + ')' });
        }
      }).catch(() => {
        resolve({ ok: false, error: '无法连接，请检查 Base URL 和网络' });
      });
    }
  });
});

ipcMain.handle('get-backend-status', () => {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${PORT}/api/health`, (res) => {
      resolve({ running: true });
    });
    req.on('error', () => {
      resolve({ running: false });
    });
    req.setTimeout(2000, () => { req.destroy(); resolve({ running: false }); });
  });
});

ipcMain.handle('launch-backend', async () => {
  const config = getActiveProviderConfig();
  if (!config) return { ok: false, error: '无活跃提供商' };
  try {
    await startPythonBackend(config);
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e.message };
  }
});

// ══════════════════════════════════════════════════
//  窗口 & 菜单
// ══════════════════════════════════════════════════

function createWindow(url) {
  mainWindow = new BrowserWindow({
    width: 1000,
    height: 700,
    minWidth: 600,
    minHeight: 400,
    title: 'Camelia Studio',
    icon: path.join(__dirname, '..', 'src', 'static', 'icon.svg'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  const menuTemplate = [
    {
      label: 'Camelia Studio',
      submenu: [
        { role: 'about' },
        {
          label: '设置',
          click: () => {
            mainWindow.loadFile(path.join(__dirname, 'settings.html'));
          },
        },
        { label: '检查更新', click: () => autoUpdater?.checkForUpdatesAndNotify() },
        { type: 'separator' },
        { role: 'quit' },
      ],
    },
    {
      label: '编辑',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
      ],
    },
    {
      label: '视图',
      submenu: [
        { role: 'reload' },
        { role: 'toggleDevTools' },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(menuTemplate));

  if (typeof url === 'string') {
    // 区分 URL 和本地路径：以 http 开头的是 URL，否则是文件路径
    if (url.startsWith('http://') || url.startsWith('https://')) {
      mainWindow.loadURL(url);
    } else {
      mainWindow.loadFile(url);
    }
  } else {
    mainWindow.loadFile(url.path);
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// ══════════════════════════════════════════════════
//  自动更新
// ══════════════════════════════════════════════════

function setupAutoUpdater() {
  if (!autoUpdater) return;

  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;

  autoUpdater.on('checking-for-update', () => console.log('检查更新中...'));

  autoUpdater.on('update-available', (info) => {
    dialog.showMessageBox(mainWindow, {
      type: 'info',
      title: '发现新版本',
      message: `Camelia Studio v${info.version} 可用，正在下载...`,
    });
  });

  autoUpdater.on('update-not-available', () => {
    dialog.showMessageBox(mainWindow, {
      type: 'info',
      title: '已是最新版本',
      message: '你正在使用最新版本。',
    });
  });

  autoUpdater.on('update-downloaded', () => {
    dialog.showMessageBox(mainWindow, {
      type: 'info',
      title: '更新已下载',
      message: '重启应用以安装更新。',
      buttons: ['立即重启', '稍后'],
    }).then((result) => {
      if (result.response === 0) {
        autoUpdater.quitAndInstall();
      }
    });
  });

  autoUpdater.on('error', (err) => console.error('更新错误:', err));

  setTimeout(() => autoUpdater.checkForUpdatesAndNotify(), 5000);
}

// ══════════════════════════════════════════════════
//  启动
// ══════════════════════════════════════════════════

app.whenReady().then(async () => {
  initStore(); // 此时 safeStorage 可用，生成正确的加密 key
  const config = getActiveProviderConfig();

  if (config) {
    // 有已保存的提供商 → 启动后端 → 打开聊天界面
    try {
      console.log('启动 Python 后端...');
      await startPythonBackend(config);
      console.log('后端就绪');
      createWindow(`http://127.0.0.1:${PORT}`);
    } catch (e) {
      console.error('后端启动失败:', e.message);
      // 启动失败 → 回退到设置页
      createWindow(path.join(__dirname, 'settings.html'));
    }
  } else {
    // 无提供商 → 打开设置页引导用户配置
    createWindow(path.join(__dirname, 'settings.html'));
  }

  if (!isDev && autoUpdater) {
    setupAutoUpdater();
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      const config = getActiveProviderConfig();
      if (config) {
        createWindow(`http://127.0.0.1:${PORT}`);
      } else {
        createWindow(path.join(__dirname, 'settings.html'));
      }
    }
  });
});

app.on('window-all-closed', () => {
  killPythonBackend();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  killPythonBackend();
});
