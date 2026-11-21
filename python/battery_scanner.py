"""
Bluetooth Battery Scanner for Windows (Enhanced 1% Precision & BLE GATT Support).
Queries Windows PnP (Classic + BLE + HID) and Registry for connected Bluetooth devices.
"""

import os
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

POWERSHELL_SCRIPT = r"""
$ErrorActionPreference = 'SilentlyContinue'
$batteryKey = "{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2"

# Scan Bluetooth, System, HIDClass, and Media devices (includes BTHENUM and BTHLE for 1% GATT battery)
$devices = Get-PnpDevice -Status "OK" | Where-Object {
    $_.InstanceId -match "^(BTHENUM|BTHLE|BTHLEDEVICE|HID\\\{00001812)" -or
    ($_.Class -in @("Bluetooth", "System", "HIDClass", "Media", "AudioEndpoint") -and $_.InstanceId -match "BTH")
}

$found = @{}

function Clean-DeviceName($rawName) {
    if ([string]::IsNullOrWhiteSpace($rawName)) { return "" }
    $n = $rawName -replace '(?i)\s*(Hands-Free(\s*AG(\s*Audio)?)?|Avrcp\s*Transport|Bluetooth\s*(LE\s*)?Device|Stereo|Audio|Headphones|Headset|GATT|Service|\(BLE\))\s*$', ''
    $n = $n -replace '(?i)^Bluetooth\s+LE\s+GATT\s+compliant\s+', ''
    return $n.Trim()
}

function Add-BatteryResult($rawName, $val) {
    $name = Clean-DeviceName $rawName
    if ([string]::IsNullOrWhiteSpace($name)) { return }
    $level = [int]$val
    if ($level -lt 0 -or $level -gt 100) { return }

    if (-not $found.ContainsKey($name)) {
        $found[$name] = $level
    } else {
        # Prefer 1%-granularity readings (non-multiples of 10) over coarse 10% HFP readings
        $existing = $found[$name]
        if (($existing % 10 -eq 0) -and ($level % 10 -ne 0)) {
            $found[$name] = $level
        }
    }
}

# 1. Check DEVPKEY_Device_BatteryPercentage across all matched PnP nodes (Classic + BLE)
foreach ($dev in $devices) {
    $prop = Get-PnpDeviceProperty -InstanceId $dev.InstanceId -KeyName $batteryKey
    if ($prop -and $null -ne $prop.Data) {
        Add-BatteryResult $dev.FriendlyName $prop.Data
    }
}

# 2. Registry Fallback for BLE GATT & HID Peripherals
$regPaths = @(
    "HKLM:\SYSTEM\CurrentControlSet\Enum\BTHLE",
    "HKLM:\SYSTEM\CurrentControlSet\Enum\BTHLEDevice",
    "HKLM:\SYSTEM\CurrentControlSet\Enum\BTHENUM"
)
foreach ($rp in $regPaths) {
    if (Test-Path $rp) {
        Get-ChildItem $rp | ForEach-Object {
            Get-ChildItem $_.PSPath | ForEach-Object {
                $p = Get-ItemProperty $_.PSPath
                if ($p -and $null -ne $p.BatteryLevel) {
                    $devName = if ($p.FriendlyName) { $p.FriendlyName } else { $_.PSChildName }
                    Add-BatteryResult $devName $p.BatteryLevel
                }
            }
        }
    }
}

foreach ($k in $found.Keys) {
    Write-Output "$k|$($found[$k])"
}
"""


def scan_devices():
    """
    Executes PowerShell script in background (no console window)
    and returns a list of dictionaries: [{'name': '...', 'battery': 73}, ...]
    """
    try:
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NO_WINDOW

        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                POWERSHELL_SCRIPT,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            startupinfo=startupinfo,
            creationflags=creationflags,
            timeout=15,
        )

        results = []
        if proc.returncode == 0 and proc.stdout:
            for line in proc.stdout.strip().splitlines():
                line = line.strip()
                if not line or "|" not in line:
                    continue
                parts = line.split("|", 1)
                if len(parts) == 2:
                    name = parts[0].strip()
                    try:
                        battery = int(parts[1].strip())
                        results.append({"name": name, "battery": battery})
                    except ValueError:
                        continue

        return results

    except Exception as e:
        logging.error(f"Error scanning Bluetooth devices: {e}")
        return []


if __name__ == "__main__":
    print("Scanning Bluetooth devices...")
    devs = scan_devices()
    print("Found devices:", devs)