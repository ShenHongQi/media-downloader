# Windows 打包说明

## 前置条件

- Windows 10/11
- Python 3.12+（安装时勾选 "Add to PATH"）

## 一键构建

双击 `build.bat` 或在命令行执行：

```powershell
cd packaging\windows
build.bat
```

构建完成后，exe 文件在 `packaging/windows/dist/MediaDownloader.exe`

## 使用

双击 `MediaDownloader.exe` 即可运行，会自动打开一个窗口：
- 内置后端服务，无需额外安装任何东西
- 粘贴链接，点击解析，点击下载
- 关闭窗口自动停止后端服务

## 手动构建（如 bat 失败）

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller pywebview

cd ..\packaging\windows
pyinstaller build.spec --clean --noconfirm
```
