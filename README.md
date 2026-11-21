# 🔵 Atena Battery

<p align="center">
  <img src="app_icon.ico" width="80" height="80" alt="Atena Battery Overlay Icon" />
</p>

<p align="center">
  <strong>A lightweight, frameless floating circular desktop widget for Windows that displays real-time battery levels for connected Bluetooth peripherals and audio devices.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Windows-0078D6?style=flat&logo=windows&logoColor=white" alt="Windows" />
  <img src="https://img.shields.io/badge/.NET-11.0%20WPF-512BD4?style=flat&logo=dotnet&logoColor=white" alt=".NET 11" />
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/License-MIT-blue.svg?style=flat" alt="License" />
</p>

---

## 🌟 Overview

Windows often buries Bluetooth device battery percentages deep within the Settings panel. **Atena Battery** brings that information directly to your desktop as a sleek, minimalist floating HUD ring.

Whether you use Bluetooth earbuds (AirPods, QCY, Sony, Galaxy Buds), wireless headphones, mice, keyboards, or game controllers—including **legacy Bluetooth devices**—this overlay tracks your remaining charge with a smooth, color-coded gauge.

This repository includes **two complete editions**:
- **⚡ .NET 11 (WPF) Edition *(Recommended)*** — Native Win32 `CfgMgr32.dll` scanning (zero PowerShell overhead), hardware-accelerated true transparency, single-instance protection, and an Inno Setup installer.
- **🐍 Python Edition** — The original lightweight script built with `tkinter` and optional `Pillow` 4x supersampled rendering.

---

<div align="center">
  <img src="https://github.com/White-Wolf-dv/White-Wolf-dv/blob/main/Gif/55.gif?raw=true" alt="Atena Battery Preview" width="550" />
</div>

---

## ⚖️ .NET 11 vs. Python Edition

| Feature | ⚡ .NET 11 (WPF) Edition | 🐍 Python Edition |
| :--- | :--- | :--- |
| **Battery Scanner** | Native Win32 P/Invoke (`CfgMgr32.dll`, `<10ms`, no subprocess) | Background PowerShell subprocess |
| **Rendering** | DirectX Hardware-Accelerated Vector WPF (Per-Pixel Alpha) | `tkinter` Canvas + Pillow 4x Supersampling (Chroma Key) |
| **Legacy Device Support** | PnP + Registry + `Device Parameters` deep fallback | PnP + Registry fallback |
| **Multi-Monitor Safety** | Automatic Virtual Screen boundary clamping | Basic coordinate restore |
| **Single-Instance Guard** | Built-in `Global` Mutex | Manual |
| **Packaging** | Portable `.exe` & Windows Installer (`Inno Setup`) | PyInstaller `.exe` or `run.bat` |

---

## ✨ Features

- **🎯 1% Precision & Legacy Bluetooth Support**:
  - Reads `DEVPKEY_Device_BatteryPercentage` across **BLE GATT**, **Hands-Free Profile (HFP / AVRCP)**, and **HID over GATT** nodes.
  - Automatically prioritizes **1%-granularity** readings over coarse 10% HFP readings while still fully supporting older devices that only report 10% steps.
  - Deep Registry fallback (`BTHLE`, `BTHLEDevice`, `BTHENUM`, and `Device Parameters`) for older drivers and peripherals.
- **🎨 Dynamic Circular Progress Gauge**:
  - Smooth 1% step animation when battery levels change.
  - Mathematical HSV-to-RGB color spectrum:
    - 🟢 **Emerald Green** (60% – 100%)
    - 🟡 **Amber / Orange** (21% – 59%)
    - 🔴 **Crimson Red** (0% – 20%)
- **🪟 True Transparent Floating Overlay**:
  - Borderless, floating HUD ring and compact device pill.
  - **Always-on-Top** (toggleable and persisted in config).
  - **Draggable** from anywhere on the widget with automatic **Position Memory**.
- **🚀 Auto-Start with Windows**:
  - One-click toggle in the right-click context menu (fully synced with the Inno Setup installer).
- **🎧 Multi-Device Support**:
  - Cycle through multiple connected Bluetooth devices using the `◀` and `▶` buttons or select directly from the right-click menu.

---

## 📸 Widget Layout

```text
       .---.
     /   90% \          <- Dynamic glowing progress arc
    | ⚡BATTERY|        <- Percentage readout
     \       /
       '---'
 [ ◀ ● Device Name ▶ ]  <- Compact device pill with switcher
```

---

## 🚀 Quick Start

### Option 1: Windows Installer or Portable Executable (.NET 11 — Recommended)
1. Download `AtenaBattery-Setup.exe` (or the portable `AtenaBattery.exe`) from the **Releases** page.
2. Run the installer or launch the portable executable directly.
3. Right-click the widget and check **Start with Windows** to keep it running automatically.

### Option 2: Build & Run .NET 11 Edition from Source
Requires the **.NET 11 SDK** on Windows:

```bash
# Clone the repository
git clone https://github.com/White-Wolf-dv/Atena-Battery.git
cd Atena-Battery/AtenaBattery

# Run directly
dotnet run

# Publish a self-contained single-file .exe
dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true
```

*(Optional)* To build the Windows Installer, open `AtenaBattery.iss` in **Inno Setup 6+** and press **Compile (`Ctrl+F9`)**.

### Option 3: Run Python Edition from Source
Requires **Python 3.10+** on Windows (`Pillow` is optional for anti-aliased rendering):

```bash
cd Atena-Battery/python

# Run directly
python app.py
```

*Tip: Double-click `run.bat` to launch the Python edition silently in the background via `pythonw`.*

---

## 🖱️ Controls & Shortcuts

| Action | Function |
| :--- | :--- |
| **Left Click + Drag** | Move widget to any location on your screen |
| **Double Click** | Trigger an immediate battery re-scan |
| **Right Click** | Open Context Menu (Refresh, Device List, Start with Windows, Always on Top, Close) |
| **Arrow Buttons (`◀` / `▶`)** | Switch between multiple connected Bluetooth devices |

---

## 📁 Repository Structure

```text
Atena-Battery/
├── app_icon.ico                 # Multi-resolution application icon
├── README.md                    # Project documentation
├── DotNet/                      # ⚡ .NET 11 (WPF) Edition
│   ├── AtenaBattery.csproj      # Project configuration (.NET 11)
│   ├── App.xaml / App.xaml.cs   # App entry point & Single-Instance Mutex
│   ├── MainWindow.xaml / .cs    # Hardware-accelerated HUD, animations & config
│   ├── BatteryScanner.cs        # Native Win32 CfgMgr32 PnP + Registry scanner
│   ├── AtenaBattery.iss         # Inno Setup installer script
│   └── app_icon.ico             # Embedded window & exe icon
└── python/                      # 🐍 Python Edition
    ├── app.py                   # Tkinter/Pillow floating overlay
    ├── battery_scanner.py       # PowerShell PnP & Registry scanner
    ├── make_icon.py             # Multi-resolution .ico generator
    ├── run.bat                  # Silent launcher (pythonw)
    └── requirements.txt         # Optional build/rendering dependencies
```

---

## ⚙️ How It Works

Windows stores Bluetooth battery telemetry differently depending on the device generation, driver, and profile:

1. **Native Plug-and-Play (`CfgMgr32.dll` / PnP)**: Modern BLE GATT peripherals and Bluetooth audio devices (HFP / AVRCP) expose battery levels through the PnP property store (`DEVPKEY_Device_BatteryPercentage` — `{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2`).
2. **Deep Registry Fallback**: Older Bluetooth headsets, mice, keyboards, and gamepads often store battery values under `HKLM\SYSTEM\CurrentControlSet\Enum\BTHENUM`, `BTHLE`, `BTHLEDevice`, or inside their `Device Parameters` subkeys (`BatteryLevel` / `BatteryPercentage`).

Both editions query these sources asynchronously every 20 seconds without blocking the UI.

---

## 📜 License

This project is licensed under the [MIT License](LICENSE). Feel free to use, modify, and distribute.
