# oc-creative-assistant
OC创作辅助系统

## 安装依赖

### 前端依赖

前端依赖在 `frontend/package.json` 中维护，进入 `frontend` 目录后安装：

```powershell
cd frontend
npm install
```

安装完成后可返回项目根目录：

```powershell
cd ..
```

### Electron 依赖

Electron 子项目在 `electron/package.json` 中维护。请按照以下顺序安装依赖：

```powershell
cd electron
npm install
```

完成后可返回项目根目录：

```powershell
cd ..
```

### 后端依赖

建议先在项目根目录创建 Python 虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

后端依赖在 `backend/requirements.txt` 中维护，激活虚拟环境后安装：

```powershell
pip install -r backend/requirements.txt
```

## 常用脚本

以下命令都在项目根目录执行，也就是包含根目录 `package.json` 的位置。

```powershell
npm run frontend:dev
```

启动前端 Vite 开发服务器。该命令会进入 `frontend` 子项目运行 `npm run dev`。

```powershell
npm run frontend:build
```

构建前端产物。该命令会进入 `frontend` 子项目运行类型检查和 Vite build。

```powershell
npm run backend:dev
```

启动后端 FastAPI 开发服务器，监听 `127.0.0.1:9000`。执行前建议先激活 Python 虚拟环境。

```powershell
npm run backend:build
```

运行后端构建脚本 `scripts/build-backend.mjs`，用于桌面端打包流程准备后端产物。

```powershell
npm run electron:dev
```

启动 Electron 子项目的开发模式。需先完成上文「Electron 依赖」中的安装。

```powershell
npm run electron:build
```

构建 Electron 子项目。需先完成上文「Electron 依赖」中的安装。

```powershell
npm run dev:desktop
```

启动桌面端联调流程，由 `scripts/dev-desktop.mjs` 协调前端、后端和 Electron 开发进程。

```powershell
npm run build:desktop
```

执行桌面端完整构建流程，由 `scripts/build-desktop.mjs` 协调前端、后端和 Electron 的打包步骤。
