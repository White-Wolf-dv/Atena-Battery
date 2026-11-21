using System.IO;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Threading;
using Microsoft.Win32;

namespace AtenaBattery;

public sealed class AppConfig
{
    public double? PosX { get; set; }
    public double? PosY { get; set; }
    public bool AlwaysOnTop { get; set; } = true;
    public string? LastSelectedDevice { get; set; }
}

public partial class MainWindow : Window
{
    private const string AppName = "BluetoothBatteryOverlay";
    private const string RegRunKey = @"Software\Microsoft\Windows\CurrentVersion\Run";
    private static readonly string ConfigDir = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "BluetoothBattery");
    private static readonly string ConfigFile = Path.Combine(ConfigDir, "config.json");

    private AppConfig _config = new();
    private List<BluetoothDevice> _devices = [];
    private string? _selectedDeviceName;
    private bool _isScanning;

    private int _displayedBattery = -1;
    private int _targetBattery = -1;
    private DateTime _lastClickTime = DateTime.MinValue;

    private readonly DispatcherTimer _scanTimer;
    private readonly DispatcherTimer _animTimer;

    public MainWindow()
    {
        InitializeComponent();
        LoadConfig();

        _animTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(16) };
        _animTimer.Tick += AnimTimer_Tick;

        _scanTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(20) };
        _scanTimer.Tick += async (_, _) => await TriggerScanAsync();

        Loaded += async (_, _) =>
        {
            await TriggerScanAsync();
            _scanTimer.Start();
        };
    }

    private void LoadConfig()
    {
        try
        {
            if (File.Exists(ConfigFile))
            {
                string json = File.ReadAllText(ConfigFile);
                _config = JsonSerializer.Deserialize<AppConfig>(json) ?? new AppConfig();
            }
        }
        catch { _config = new AppConfig(); }

        Topmost = _config.AlwaysOnTop;
        _selectedDeviceName = _config.LastSelectedDevice;

        double defaultX = SystemParameters.WorkArea.Right - Width - 35;
        double defaultY = SystemParameters.WorkArea.Top + 50;

        double x = _config.PosX ?? defaultX;
        double y = _config.PosY ?? defaultY;

        double minX = SystemParameters.VirtualScreenLeft;
        double maxX = minX + SystemParameters.VirtualScreenWidth - Width;
        double minY = SystemParameters.VirtualScreenTop;
        double maxY = minY + SystemParameters.VirtualScreenHeight - Height;

        Left = Math.Clamp(x, minX, maxX);
        Top = Math.Clamp(y, minY, maxY);
    }

    private void SaveConfig()
    {
        try
        {
            _config.PosX = Left;
            _config.PosY = Top;
            _config.AlwaysOnTop = Topmost;
            _config.LastSelectedDevice = _selectedDeviceName;

            Directory.CreateDirectory(ConfigDir);
            File.WriteAllText(ConfigFile, JsonSerializer.Serialize(_config, new JsonSerializerOptions { WriteIndented = true }));
        }
        catch { }
    }

    private async Task TriggerScanAsync()
    {
        if (_isScanning) return;
        _isScanning = true;

        try
        {
            var result = await Task.Run(BatteryScanner.ScanDevices);
            _devices = result;

            if (_devices.Count > 0)
            {
                var current = _devices.FirstOrDefault(d =>
                    string.Equals(d.Name, _selectedDeviceName, StringComparison.OrdinalIgnoreCase))
                    ?? _devices[0];

                _selectedDeviceName = current.Name;
                AnimateTo(current.Battery, current.Name);
            }
            else
            {
                AnimateTo(-1, "No Device");
            }

            Visibility navVis = _devices.Count > 1 ? Visibility.Visible : Visibility.Collapsed;
            PrevBtn.Visibility = navVis;
            NextBtn.Visibility = navVis;
        }
        finally
        {
            _isScanning = false;
        }
    }

    private void AnimateTo(int newLevel, string deviceName)
    {
        DeviceNameText.Text = deviceName;
        _targetBattery = newLevel;

        if (newLevel < 0)
        {
            _animTimer.Stop();
            _displayedBattery = -1;
            RenderGauge(-1);
            return;
        }

        if (_displayedBattery < 0) _displayedBattery = 0;
        _animTimer.Start();
    }

    private void AnimTimer_Tick(object? sender, EventArgs e)
    {
        if (_displayedBattery == _targetBattery)
        {
            _animTimer.Stop();
            RenderGauge(_displayedBattery);
            return;
        }

        int diff = _targetBattery - _displayedBattery;
        int step = diff > 0 ? 1 : -1;
        if (Math.Abs(diff) > 15) step *= 2;

        _displayedBattery += step;
        RenderGauge(_displayedBattery);
    }

    private void RenderGauge(int level)
    {
        if (level < 0)
        {
            PercentText.Text = "--%";
            PercentText.Foreground = new SolidColorBrush(Color.FromRgb(125, 140, 163));
            StatusText.Text = "OFFLINE";
            StatusText.Foreground = new SolidColorBrush(Color.FromRgb(82, 96, 117));
            StatusDot.Fill = new SolidColorBrush(Color.FromRgb(96, 109, 128));
            ProgressArc.Data = null;
            GlowArc.Data = null;
            return;
        }

        Color accent = GetBatteryColor(level);
        var brush = new SolidColorBrush(accent);

        PercentText.Text = $"{level}%";
        PercentText.Foreground = Brushes.White;
        StatusText.Text = "⚡ BATTERY";
        StatusText.Foreground = brush;
        StatusDot.Fill = brush;

        Geometry arc = CreateArcGeometry(78, 64, 41, level);
        ProgressArc.Stroke = brush;
        ProgressArc.Data = arc;
        GlowArc.Stroke = brush;
        GlowArc.Data = arc;
    }

    private static Geometry CreateArcGeometry(double cx, double cy, double radius, int percent)
    {
        if (percent <= 0) return Geometry.Empty;

        double clamped = Math.Min(percent, 99.99);
        double angleDeg = (clamped / 100.0) * 360.0;
        double startRad = -Math.PI / 2.0;
        double endRad = startRad + (angleDeg * Math.PI / 180.0);

        Point start = new(cx + radius * Math.Cos(startRad), cy + radius * Math.Sin(startRad));
        Point end = new(cx + radius * Math.Cos(endRad), cy + radius * Math.Sin(endRad));

        bool isLargeArc = angleDeg > 180.0;

        var figure = new PathFigure { StartPoint = start, IsClosed = false };
        figure.Segments.Add(new ArcSegment(end, new Size(radius, radius), 0, isLargeArc, SweepDirection.Clockwise, true));

        return new PathGeometry([figure]);
    }

    private static Color GetBatteryColor(int percent)
    {
        double pct = Math.Clamp(percent, 0, 100);
        double hue = (pct / 100.0) * 136.8;
        return HsvToColor(hue, 0.85, 0.98);
    }

    private static Color HsvToColor(double h, double s, double v)
    {
        double c = v * s;
        double x = c * (1 - Math.Abs((h / 60.0) % 2 - 1));
        double m = v - c;

        (double r, double g, double b) = h switch
        {
            < 60 => (c, x, 0.0),
            < 120 => (x, c, 0.0),
            < 180 => (0.0, c, x),
            _ => (0.0, x, c)
        };

        return Color.FromRgb((byte)((r + m) * 255), (byte)((g + m) * 255), (byte)((b + m) * 255));
    }

    private void Window_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        var now = DateTime.UtcNow;
        if ((now - _lastClickTime).TotalMilliseconds < 350)
        {
            _ = TriggerScanAsync();
            _lastClickTime = DateTime.MinValue;
            return;
        }
        _lastClickTime = now;

        if (e.LeftButton == MouseButtonState.Pressed)
            DragMove();
    }

    private void Window_MouseLeftButtonUp(object sender, MouseButtonEventArgs e) => SaveConfig();

    private void PrevBtn_Click(object sender, MouseButtonEventArgs e)
    {
        e.Handled = true;
        CycleDevice(-1);
    }

    private void NextBtn_Click(object sender, MouseButtonEventArgs e)
    {
        e.Handled = true;
        CycleDevice(1);
    }

    private void CycleDevice(int delta)
    {
        if (_devices.Count <= 1) return;
        int idx = _devices.FindIndex(d => string.Equals(d.Name, _selectedDeviceName, StringComparison.OrdinalIgnoreCase));
        if (idx < 0) idx = 0;

        idx = (idx + delta + _devices.Count) % _devices.Count;
        var next = _devices[idx];
        _selectedDeviceName = next.Name;
        AnimateTo(next.Battery, next.Name);
        SaveConfig();
    }

    private void Window_MouseRightButtonUp(object sender, MouseButtonEventArgs e)
    {
        var menu = new ContextMenu();

        var refreshItem = new MenuItem { Header = "↻  Refresh Now" };
        refreshItem.Click += async (_, _) => await TriggerScanAsync();
        menu.Items.Add(refreshItem);

        if (_devices.Count > 1)
        {
            menu.Items.Add(new Separator());
            foreach (var dev in _devices)
            {
                bool isSelected = string.Equals(dev.Name, _selectedDeviceName, StringComparison.OrdinalIgnoreCase);
                var devItem = new MenuItem { Header = $"{(isSelected ? "● " : "   ")}{dev.Name} ({dev.Battery}%)" };
                devItem.Click += (_, _) =>
                {
                    _selectedDeviceName = dev.Name;
                    AnimateTo(dev.Battery, dev.Name);
                    SaveConfig();
                };
                menu.Items.Add(devItem);
            }
        }

        menu.Items.Add(new Separator());

        var startupItem = new MenuItem { Header = "Start with Windows", IsCheckable = true, IsChecked = IsStartupEnabled() };
        startupItem.Click += (_, _) => SetStartup(startupItem.IsChecked);
        menu.Items.Add(startupItem);

        var topItem = new MenuItem { Header = "Always on Top", IsCheckable = true, IsChecked = Topmost };
        topItem.Click += (_, _) =>
        {
            Topmost = topItem.IsChecked;
            SaveConfig();
        };
        menu.Items.Add(topItem);

        menu.Items.Add(new Separator());

        var closeItem = new MenuItem { Header = "✕  Close Widget" };
        closeItem.Click += (_, _) => Close();
        menu.Items.Add(closeItem);

        menu.IsOpen = true;
    }

    private static bool IsStartupEnabled()
    {
        using var key = Registry.CurrentUser.OpenSubKey(RegRunKey, false);
        return key?.GetValue(AppName) is not null;
    }

    private static void SetStartup(bool enable)
    {
        using var key = Registry.CurrentUser.OpenSubKey(RegRunKey, true);
        if (key is null) return;

        if (enable)
        {
            string? exePath = Environment.ProcessPath;
            if (!string.IsNullOrEmpty(exePath))
                key.SetValue(AppName, $"\"{exePath}\"");
        }
        else
        {
            key.DeleteValue(AppName, false);
        }
    }
}
