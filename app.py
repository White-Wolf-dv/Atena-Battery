"""
Atena Bluetooth Battery - Modern Anti-Aliased Circular Overlay
- Ultra-crisp 4x Super-Sampled rendering via Pillow (smooth circles, rounded arc caps, neon glow)
- Smooth 1% step animation when battery level updates
- Sleek floating pill badge with interactive Next/Prev device buttons
- Draggable anywhere, Always-on-Top, Windows Startup integration
"""

import sys
import os
import math
import threading
import json
import winreg
import colorsys
import tkinter as tk
from battery_scanner import scan_devices

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

#Make high-DPI aware on Windows for crisp fonts and graphics
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

APP_NAME = "BluetoothBatteryOverlay"
REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "BluetoothBattery")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def load_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_config(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


def is_startup_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except Exception:
        return False


def set_startup(enable: bool):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                if getattr(sys, "frozen", False):
                    cmd = f'"{sys.executable}"'
                else:
                    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
                    if not os.path.exists(pythonw):
                        pythonw = sys.executable
                    script_path = os.path.abspath(__file__)
                    cmd = f'"{pythonw}" "{script_path}"'
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        print("Startup registry error:", e)
        return False


def get_battery_rgb(percent):
    """Returns (R, G, B) tuple on a smooth emerald -> cyan/amber -> coral -> crimson spectrum."""
    pct = max(0.0, min(100.0, float(percent)))
    hue = (pct / 100.0) * 0.38
    r, g, b = colorsys.hsv_to_rgb(hue, 0.85, 0.98)
    return int(r * 255), int(g * 255), int(b * 255)


def get_battery_hex(percent):
    r, g, b = get_battery_rgb(percent)
    return f"#{r:02x}{g:02x}{b:02x}"


class ModernBatteryOverlay:
    def __init__(self, root):
        self.root = root
        self.root.title("Atena Battery")

        self.width = 148
        self.height = 168

        # Transparent chroma key for Windows
        self.chroma_color = "#010101"
        self.chroma_rgb = (1, 1, 1)

        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", self.chroma_color)
        self.root.configure(bg=self.chroma_color)

        icon_path = os.path.join(os.path.dirname(__file__), "app_icon.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

        self.config = load_config()
        screen_w = self.root.winfo_screenwidth()
        x = self.config.get("pos_x", screen_w - self.width - 35)
        y = self.config.get("pos_y", 50)
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")

        # State
        self.devices = []
        self.selected_idx = 0
        self.is_scanning = False
        self.always_on_top = True
        self.displayed_battery = 0
        self.target_battery = -1
        self.current_name = "Scanning..."
        self.anim_job = None
        self.tk_img = None  # Keep reference for GC

        self.drag_x = 0
        self.drag_y = 0

        self.setup_ui()
        self.schedule_auto_refresh()

    def setup_ui(self):
        self.canvas = tk.Canvas(
            self.root,
            width=self.width,
            height=self.height,
            bg=self.chroma_color,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<Button-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.do_drag)
        self.canvas.bind("<ButtonRelease-1>", self.end_drag)
        self.canvas.bind("<Button-3>", self.show_context_menu)
        self.canvas.bind("<Double-Button-1>", lambda e: self.trigger_scan())

        self.render(-1, "Scanning...")

    def animate_to(self, new_level, device_name):
        """Smoothly animates the percentage 1% at a time for visual polish."""
        self.current_name = device_name
        self.target_battery = new_level

        if self.anim_job:
            self.root.after_cancel(self.anim_job)
            self.anim_job = None

        if new_level < 0:
            self.displayed_battery = -1
            self.render(-1, device_name)
            return

        if self.displayed_battery < 0:
            self.displayed_battery = 0

        self._step_animation()

    def _step_animation(self):
        if self.displayed_battery == self.target_battery:
            self.render(self.displayed_battery, self.current_name)
            return

        diff = self.target_battery - self.displayed_battery
        step = 1 if diff > 0 else -1
        # Speed up if difference is large, then 1% steps near the target
        if abs(diff) > 15:
            step *= 2

        self.displayed_battery += step
        self.render(self.displayed_battery, self.current_name)
        self.anim_job = self.root.after(18, self._step_animation)

    def _create_aa_backdrop(self, battery_level):
        """Renders ultra-smooth anti-aliased circular gauge + neon glow + pill via 4x supersampling."""
        scale = 4
        W, H = self.width * scale, self.height * scale
        cx, cy = (self.width // 2) * scale, 62 * scale
        outer_r = 52 * scale
        ring_r = 41 * scale
        thick = 7 * scale

        # Base RGBA canvas for compositing
        base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(base)

        # 1. Outer dark glass disc with subtle double rim
        draw.ellipse(
            [cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r],
            fill=(15, 19, 28, 255),
            outline=(38, 47, 68, 255),
            width=int(1.5 * scale),
        )
        inner_rim = outer_r - 4 * scale
        draw.ellipse(
            [cx - inner_rim, cy - inner_rim, cx + inner_rim, cy + inner_rim],
            outline=(24, 30, 44, 255),
            width=scale,
        )

        # 2. Subtle tick marks around inner ring
        tick_r1 = ring_r - 9 * scale
        tick_r2 = ring_r - 6 * scale
        for deg in range(0, 360, 15):
            rad = math.radians(deg)
            x1 = cx + tick_r1 * math.cos(rad)
            y1 = cy + tick_r1 * math.sin(rad)
            x2 = cx + tick_r2 * math.cos(rad)
            y2 = cy + tick_r2 * math.sin(rad)
            draw.line([x1, y1, x2, y2], fill=(34, 42, 60, 255), width=scale)

        # 3. Recessed track ring
        bbox = [cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r]
        draw.arc(bbox, start=0, end=360, fill=(30, 37, 52, 255), width=thick)

        # 4. Active glowing progress arc with rounded caps
        if battery_level > 0:
            r, g, b = get_battery_rgb(battery_level)
            start_deg = -90.0
            sweep_deg = (battery_level / 100.0) * 360.0
            end_deg = start_deg + sweep_deg

            # Soft Neon Glow layer
            glow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            gdraw = ImageDraw.Draw(glow_layer)
            gdraw.arc(bbox, start=start_deg, end=end_deg, fill=(r, g, b, 115), width=int(thick * 1.9))
            glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=3.5 * scale))
            base = Image.alpha_composite(base, glow_layer)
            draw = ImageDraw.Draw(base)

            # Main crisp arc
            draw.arc(bbox, start=start_deg, end=end_deg, fill=(r, g, b, 255), width=thick)

            # Rounded end caps on the arc
            cap_r = (thick - scale) / 2.0
            for angle in (start_deg, end_deg):
                rad = math.radians(angle)
                px = cx + (ring_r - thick / 2.0) * math.cos(rad)
                py = cy + (ring_r - thick / 2.0) * math.sin(rad)
                draw.ellipse([px - cap_r, py - cap_r, px + cap_r, py + cap_r], fill=(r, g, b, 255))

        # 5. Bottom pill badge for device name
        pill_w = 128 * scale
        pill_h = 26 * scale
        pill_y = 136 * scale
        px1 = cx - pill_w // 2
        py1 = pill_y - pill_h // 2
        px2 = cx + pill_w // 2
        py2 = pill_y + pill_h // 2

        draw.rounded_rectangle(
            [px1, py1, px2, py2],
            radius=pill_h // 2,
            fill=(15, 19, 28, 255),
            outline=(38, 47, 68, 255),
            width=int(1.5 * scale),
        )

        # Status dot inside pill
        dot_rgb = get_battery_rgb(battery_level) if battery_level >= 0 else (96, 109, 128)
        dot_x = px1 + (22 * scale if len(self.devices) > 1 else 14 * scale)
        dot_r = 3.5 * scale
        draw.ellipse([dot_x - dot_r, pill_y - dot_r, dot_x + dot_r, pill_y + dot_r], fill=(*dot_rgb, 255))

        # Flatten onto chroma background so edge pixels never bleed #010101
        final_rgb = Image.new("RGB", (W, H), self.chroma_rgb)
        alpha = base.split()[3].point(lambda a: 255 if a > 180 else 0)
        final_rgb.paste(base.convert("RGB"), mask=alpha)

        resampled = final_rgb.resize((self.width, self.height), Image.Resampling.LANCZOS)
        # Re-enforce pure chroma on transparent outer pixels
        mask_small = alpha.resize((self.width, self.height), Image.Resampling.NEAREST)
        out = Image.new("RGB", (self.width, self.height), self.chroma_rgb)
        out.paste(resampled, mask=mask_small)
        return ImageTk.PhotoImage(out)

    def render(self, battery_level, device_name):
        self.canvas.delete("all")
        cx = self.width // 2
        cy = 62
        pill_y = 136

        if HAS_PIL:
            self.tk_img = self._create_aa_backdrop(battery_level)
            self.canvas.create_image(0, 0, image=self.tk_img, anchor="nw")
        else:
            # Fallback if Pillow is not installed
            r = 50
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#0F131C", outline="#262F44", width=2)

        # Center typography
        if battery_level >= 0:
            accent_hex = get_battery_hex(battery_level)
            # Numeric readout + smaller % symbol
            self.canvas.create_text(
                cx, cy - 6,
                text=f"{battery_level}%",
                font=("Segoe UI", 17, "bold"),
                fill="#FFFFFF",
                anchor="center",
            )
            self.canvas.create_text(
                cx, cy + 16,
                text="⚡ BATTERY",
                font=("Segoe UI", 6, "bold"),
                fill=accent_hex,
                anchor="center",
            )
        else:
            self.canvas.create_text(
                cx, cy - 4,
                text="--%",
                font=("Segoe UI", 16, "bold"),
                fill="#7D8CA3",
                anchor="center",
            )
            self.canvas.create_text(
                cx, cy + 16,
                text="OFFLINE",
                font=("Segoe UI", 6, "bold"),
                fill="#526075",
                anchor="center",
            )

        # Device Name formatting inside bottom pill
        max_chars = 12 if len(self.devices) > 1 else 15
        clean_name = device_name if len(device_name) <= max_chars else device_name[: max_chars - 1] + "…"

        text_x = cx + 4
        self.canvas.create_text(
            text_x, pill_y,
            text=clean_name,
            font=("Segoe UI", 8, "bold"),
            fill="#F0F4F8",
            anchor="center",
        )

        # Interactive Prev / Next arrows when multiple Bluetooth devices are connected
        if len(self.devices) > 1:
            self.canvas.create_text(
                cx - 52, pill_y,
                text="◀",
                font=("Segoe UI", 7, "bold"),
                fill="#8B9BB4",
                activefill="#FFFFFF",
                anchor="center",
                tags="btn_prev",
            )
            self.canvas.create_text(
                cx + 52, pill_y,
                text="▶",
                font=("Segoe UI", 7, "bold"),
                fill="#8B9BB4",
                activefill="#FFFFFF",
                anchor="center",
                tags="btn_next",
            )
            self.canvas.tag_bind("btn_prev", "<Button-1>", self.prev_device)
            self.canvas.tag_bind("btn_next", "<Button-1>", self.next_device)

    def next_device(self, event=None):
        if self.devices:
            self.selected_idx = (self.selected_idx + 1) % len(self.devices)
            curr = self.devices[self.selected_idx]
            self.animate_to(curr["battery"], curr["name"])
        return "break"

    def prev_device(self, event=None):
        if self.devices:
            self.selected_idx = (self.selected_idx - 1) % len(self.devices)
            curr = self.devices[self.selected_idx]
            self.animate_to(curr["battery"], curr["name"])
        return "break"

    def start_drag(self, event):
        # Ignore drag if user clicked on next/prev buttons
        clicked_tags = self.canvas.gettags("current")
        if "btn_next" in clicked_tags or "btn_prev" in clicked_tags:
            return
        self.drag_x = event.x
        self.drag_y = event.y

    def do_drag(self, event):
        clicked_tags = self.canvas.gettags("current")
        if "btn_next" in clicked_tags or "btn_prev" in clicked_tags:
            return
        dx = event.x - self.drag_x
        dy = event.y - self.drag_y
        new_x = self.root.winfo_x() + dx
        new_y = self.root.winfo_y() + dy
        self.root.geometry(f"+{new_x}+{new_y}")

    def end_drag(self, event):
        self.config["pos_x"] = self.root.winfo_x()
        self.config["pos_y"] = self.root.winfo_y()
        save_config(self.config)

    def trigger_scan(self):
        if self.is_scanning:
            return
        self.is_scanning = True

        def worker():
            devs = scan_devices()
            self.root.after(0, self.on_scan_finished, devs)

        threading.Thread(target=worker, daemon=True).start()

    def on_scan_finished(self, devs):
        self.is_scanning = False
        self.devices = devs

        if self.devices:
            if self.selected_idx >= len(self.devices):
                self.selected_idx = 0
            curr = self.devices[self.selected_idx]
            self.animate_to(curr["battery"], curr["name"])
        else:
            self.animate_to(-1, "No Device")

    def schedule_auto_refresh(self):
        self.trigger_scan()
        self.root.after(20000, self.schedule_auto_refresh)

    def build_context_menu(self):
        menu = tk.Menu(
            self.root,
            tearoff=0,
            bg="#121621",
            fg="#FFFFFF",
            activebackground="#2E6FF2",
            activeforeground="#FFFFFF",
            font=("Segoe UI", 9),
        )
        menu.add_command(label="↻  Refresh Now", command=self.trigger_scan)

        if len(self.devices) > 1:
            menu.add_separator()
            for idx, dev in enumerate(self.devices):
                prefix = "● " if idx == self.selected_idx else "   "
                menu.add_command(
                    label=f"{prefix}{dev['name']} ({dev['battery']}%)",
                    command=lambda i=idx: self.select_device(i),
                )
            menu.add_separator()

        startup_state = is_startup_enabled()
        startup_label = "✔  Start with Windows" if startup_state else "    Start with Windows"
        menu.add_command(label=startup_label, command=self.toggle_startup_state)

        top_label = "✔  Always on Top" if self.always_on_top else "    Always on Top"
        menu.add_command(label=top_label, command=self.toggle_topmost)

        menu.add_separator()
        menu.add_command(label="✕  Close Widget", command=self.root.destroy)
        return menu

    def select_device(self, idx):
        if 0 <= idx < len(self.devices):
            self.selected_idx = idx
            curr = self.devices[idx]
            self.animate_to(curr["battery"], curr["name"])

    def toggle_startup_state(self):
        set_startup(not is_startup_enabled())

    def toggle_topmost(self):
        self.always_on_top = not self.always_on_top
        self.root.attributes("-topmost", self.always_on_top)

    def show_context_menu(self, event):
        menu = self.build_context_menu()
        menu.tk_popup(event.x_root, event.y_root)


def main():
    root = tk.Tk()
    app = ModernBatteryOverlay(root)
    root.mainloop()


if __name__ == "__main__":
    main()
