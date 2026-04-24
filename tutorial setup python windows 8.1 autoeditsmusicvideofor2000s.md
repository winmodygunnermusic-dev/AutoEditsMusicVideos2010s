# Tutorial: Setup Python + FFmpeg on Windows 8.1 for AutoEditsMusicVideos2010s

## 1) Install Python 3.8+
1. Download Python for Windows from python.org.
2. During install, enable **Add Python to PATH**.
3. Verify in Command Prompt:
   ```bat
   python --version
   ```

## 2) Install FFmpeg/FFprobe
1. Download a Windows build that supports your machine.
2. Extract to a folder such as `C:\ffmpeg`.
3. Add `C:\ffmpeg\bin` to PATH, or pick `ffmpeg.exe` and `ffprobe.exe` directly in the GUI.
4. Verify:
   ```bat
   ffmpeg -version
   ffprobe -version
   ```

## 3) Run the GUI
```bat
python autoedit_gui.py
```

## 4) Optional launch modes
```bat
python autoedit_gui_normal.py
python autoedit_gui_small.py
```

## 5) Common troubleshooting
- If `tkinter` import fails, reinstall Python using the standard installer.
- If FFmpeg is not found, use the GUI Browse buttons for FFmpeg and FFprobe.
- For long renders, enable **10x draft mode** first for previews.
