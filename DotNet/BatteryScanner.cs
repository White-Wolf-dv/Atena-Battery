using System.Runtime.InteropServices;
using System.Text.RegularExpressions;
using Microsoft.Win32;

namespace AtenaBattery;

public sealed record BluetoothDevice(string Name, int Battery);

public static partial class BatteryScanner
{
    // DEVPKEY_Device_BatteryPercentage: {104EA319-6EE2-4701-BD47-8DDBF425BBE5}, 2
    private static readonly DevPropKey DevPKeyBatteryPercentage = new()
    {
        FmtId = new Guid("104EA319-6EE2-4701-BD47-8DDBF425BBE5"),
        Pid = 2
    };

    // DEVPKEY_Device_FriendlyName: {A45C254E-DF1C-4EFD-8020-67D146A850E0}, 14
    private static readonly DevPropKey DevPKeyFriendlyName = new()
    {
        FmtId = new Guid("A45C254E-DF1C-4EFD-8020-67D146A850E0"),
        Pid = 14
    };

    // DEVPKEY_Device_DeviceDesc: {A45C254E-DF1C-4EFD-8020-67D146A850E0}, 2
    private static readonly DevPropKey DevPKeyDeviceDesc = new()
    {
        FmtId = new Guid("A45C254E-DF1C-4EFD-8020-67D146A850E0"),
        Pid = 2
    };

    private const uint CM_GETIDLIST_FILTER_PRESENT = 0x00000100;
    private const uint CR_SUCCESS = 0;

    [StructLayout(LayoutKind.Sequential)]
    private struct DevPropKey
    {
        public Guid FmtId;
        public uint Pid;
    }

    [LibraryImport("CfgMgr32.dll", StringMarshalling = StringMarshalling.Utf16)]
    private static partial uint CM_Get_Device_ID_List_SizeW(out uint pulLen, string? pszFilter, uint ulFlags);

    [LibraryImport("CfgMgr32.dll", StringMarshalling = StringMarshalling.Utf16)]
    private static partial uint CM_Get_Device_ID_ListW(string? pszFilter, [Out] char[] buffer, uint bufferLen, uint ulFlags);

    [LibraryImport("CfgMgr32.dll", StringMarshalling = StringMarshalling.Utf16)]
    private static partial uint CM_Locate_DevNodeW(out uint pdnDevInst, string pDeviceID, uint ulFlags);

    [LibraryImport("CfgMgr32.dll")]
    private static partial uint CM_Get_DevNode_PropertyW(
        uint dnDevInst,
        in DevPropKey propertyKey,
        out uint propertyType,
        [Out] byte[]? propertyBuffer,
        ref uint propertyBufferSize,
        uint ulFlags);

    [GeneratedRegex(@"(?i)\s*(Hands-Free(\s*AG(\s*Audio)?)?|Avrcp\s*Transport|Bluetooth\s*(LE\s*)?Device|Stereo|Audio|Headphones|Headset|GATT|Service|\(BLE\))\s*$")]
    private static partial Regex TrailingNoiseRegex();

    [GeneratedRegex(@"(?i)^Bluetooth\s+LE\s+GATT\s+compliant\s+")]
    private static partial Regex LeadingNoiseRegex();

    public static List<BluetoothDevice> ScanDevices()
    {
        var found = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);

        // 1. Direct native PnP scan (Classic HFP, BLE GATT, and HID)
        ScanViaCfgMgr32(found);

        // 2. Registry fallback for older devices/drivers (including Device Parameters)
        ScanViaRegistryFallback(found);

        return found
            .OrderBy(kv => kv.Key, StringComparer.OrdinalIgnoreCase)
            .Select(kv => new BluetoothDevice(kv.Key, kv.Value))
            .ToList();
    }

    private static void ScanViaCfgMgr32(Dictionary<string, int> found)
    {
        if (CM_Get_Device_ID_List_SizeW(out uint size, null, CM_GETIDLIST_FILTER_PRESENT) != CR_SUCCESS || size == 0)
            return;

        char[] buffer = new char[size];
        if (CM_Get_Device_ID_ListW(null, buffer, size, CM_GETIDLIST_FILTER_PRESENT) != CR_SUCCESS)
            return;

        string raw = new(buffer);
        foreach (string instanceId in raw.Split('\0', StringSplitOptions.RemoveEmptyEntries))
        {
            if (!IsBluetoothRelated(instanceId))
                continue;

            if (CM_Locate_DevNodeW(out uint devInst, instanceId, 0) != CR_SUCCESS)
                continue;

            int? battery = GetByteOrIntProperty(devInst, DevPKeyBatteryPercentage);
            if (battery is null or < 0 or > 100)
                continue;

            string? name = GetStringProperty(devInst, DevPKeyFriendlyName)
                        ?? GetStringProperty(devInst, DevPKeyDeviceDesc);

            AddBatteryResult(found, name, battery.Value);
        }
    }

    private static bool IsBluetoothRelated(string instanceId)
    {
        return instanceId.StartsWith("BTHENUM\\", StringComparison.OrdinalIgnoreCase)
            || instanceId.StartsWith("BTHLE\\", StringComparison.OrdinalIgnoreCase)
            || instanceId.StartsWith("BTHLEDEVICE\\", StringComparison.OrdinalIgnoreCase)
            || instanceId.Contains("00001812", StringComparison.OrdinalIgnoreCase)
            || (instanceId.StartsWith("HID\\", StringComparison.OrdinalIgnoreCase) &&
                instanceId.Contains("BTH", StringComparison.OrdinalIgnoreCase));
    }

    private static int? GetByteOrIntProperty(uint devInst, DevPropKey key)
    {
        uint bufSize = 0;
        CM_Get_DevNode_PropertyW(devInst, in key, out _, null, ref bufSize, 0);
        if (bufSize == 0 || bufSize > 8) return null;

        byte[] buf = new byte[bufSize];
        if (CM_Get_DevNode_PropertyW(devInst, in key, out _, buf, ref bufSize, 0) != CR_SUCCESS)
            return null;

        return bufSize switch
        {
            1 => buf[0],
            2 => BitConverter.ToUInt16(buf, 0),
            4 => (int)BitConverter.ToUInt32(buf, 0),
            _ => null
        };
    }

    private static string? GetStringProperty(uint devInst, DevPropKey key)
    {
        uint bufSize = 0;
        CM_Get_DevNode_PropertyW(devInst, in key, out _, null, ref bufSize, 0);
        if (bufSize == 0) return null;

        byte[] buf = new byte[bufSize];
        if (CM_Get_DevNode_PropertyW(devInst, in key, out _, buf, ref bufSize, 0) != CR_SUCCESS)
            return null;

        return System.Text.Encoding.Unicode.GetString(buf).TrimEnd('\0');
    }

    private static void ScanViaRegistryFallback(Dictionary<string, int> found)
    {
        string[] rootPaths =
        [
            @"SYSTEM\CurrentControlSet\Enum\BTHLE",
            @"SYSTEM\CurrentControlSet\Enum\BTHLEDevice",
            @"SYSTEM\CurrentControlSet\Enum\BTHENUM"
        ];

        foreach (string rootPath in rootPaths)
        {
            using var rootKey = Registry.LocalMachine.OpenSubKey(rootPath);
            if (rootKey is null) continue;

            foreach (string deviceGroup in rootKey.GetSubKeyNames())
            {
                using var groupKey = rootKey.OpenSubKey(deviceGroup);
                if (groupKey is null) continue;

                foreach (string instance in groupKey.GetSubKeyNames())
                {
                    using var instKey = groupKey.OpenSubKey(instance);
                    if (instKey is null) continue;

                    string? devName = instKey.GetValue("FriendlyName") as string
                                   ?? instKey.GetValue("DeviceDesc") as string;

                    int? level = TryReadBatteryValue(instKey);
                    if (level is null)
                    {
                        using var devParams = instKey.OpenSubKey("Device Parameters");
                        if (devParams is not null)
                            level = TryReadBatteryValue(devParams);
                    }

                    if (level is >= 0 and <= 100 && !string.IsNullOrWhiteSpace(devName))
                    {
                        int semiIdx = devName.LastIndexOf(';');
                        if (semiIdx >= 0 && semiIdx + 1 < devName.Length)
                            devName = devName[(semiIdx + 1)..];

                        AddBatteryResult(found, devName, level.Value);
                    }
                }
            }
        }
    }

    private static int? TryReadBatteryValue(RegistryKey key)
    {
        object? raw = key.GetValue("BatteryLevel") ?? key.GetValue("BatteryPercentage");
        if (raw is null) return null;

        return raw switch
        {
            int i => i,
            byte[] b when b.Length > 0 => b[0],
            string s when int.TryParse(s, out int parsed) => parsed,
            _ => null
        };
    }

    private static string CleanDeviceName(string? rawName)
    {
        if (string.IsNullOrWhiteSpace(rawName)) return string.Empty;
        string n = TrailingNoiseRegex().Replace(rawName, string.Empty);
        n = LeadingNoiseRegex().Replace(n, string.Empty);
        return n.Trim();
    }

    private static void AddBatteryResult(Dictionary<string, int> found, string? rawName, int level)
    {
        string name = CleanDeviceName(rawName);
        if (string.IsNullOrWhiteSpace(name)) return;

        if (!found.TryGetValue(name, out int existing))
        {
            found[name] = level;
        }
        else if (existing % 10 == 0 && level % 10 != 0)
        {
            found[name] = level;
        }
    }
}
