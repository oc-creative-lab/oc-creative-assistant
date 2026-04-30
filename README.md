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

如果 PowerShell 阻止激活虚拟环境，可以先执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```
