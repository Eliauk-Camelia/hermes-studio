const { app, BrowserWindow, Menu, dialog } = require('electron');
const { spawn } = require('child_process');
const path = require('path');

// 自动更新（生产环境才加载）
let autoUpdater = null;
try {
  autoUpdater = require('electron-updater').autoUpdater;
} catch (e) {
  console.log('electron-updater 未安装，跳过自动更新');
}

let mainWindow;
let pythonProcess;

const isDev = !app.isPackaged;
const PORT = 8648;

function startPythonBackend() {
  const pythonExe = process.platform === 'win32' ? 'python' : 'python3';
  const serverPath = path.join(__dirname, '..', 'src', 'server.py');

  pythonProcess = spawn(pythonExe, [serverPath], {
    env: { ...process.env },
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
  });

  // 等待服务启动
  return new Promise((resolve) => {
    const check = () => {
      const http = require('http');
      http.get(`http://127.0.0.1:${PORT}/api/health`, (res) => {
        resolve();
      }).on('error', () => {
        setTimeout(check, 300);
      });
    };
    setTimeout(check, 800);
  });
}

function createWindow() {
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

  // 菜单
  const menu = Menu.buildFromTemplate([
    {
      label: 'Camelia Studio',
      submenu: [
        { role: 'about' },
        { label: '检查更新', click: () => autoUpdater.checkForUpdatesAndNotify() },
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
  ]);
  Menu.setApplicationMenu(menu);

  mainWindow.loadURL(`http://127.0.0.1:${PORT}`);

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// 自动更新
function setupAutoUpdater() {
  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;

  autoUpdater.on('checking-for-update', () => {
    console.log('检查更新中...');
  });

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

  autoUpdater.on('error', (err) => {
    console.error('更新错误:', err);
  });

  // 启动 5 秒后检查更新
  setTimeout(() => {
    autoUpdater.checkForUpdatesAndNotify();
  }, 5000);
}

app.whenReady().then(async () => {
  console.log('启动 Python 后端...');
  await startPythonBackend();
  console.log('后端就绪');

  createWindow();

  if (!isDev && autoUpdater) {
    setupAutoUpdater();
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
});
