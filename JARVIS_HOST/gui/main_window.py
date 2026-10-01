
import tkinter as tk
import customtkinter as ctk
import threading
import math
import time
from utils.logger import get_logger
from utils.config_manager import get_config

logger = get_logger()
config = get_config()

BG = "#020304"
PANEL = "#07090B"
GOLD = "#D6B23C"
GOLD2 = "#8C7220"
WHITE = "#E8E8E8"
MUTED = "#70777D"
GREEN = "#39C56E"
CYAN = "#5AC8E8"
RED = "#D95C5C"


class JarvisGUI:
    def __init__(self, jarvis):
        self.jarvis = jarvis
        self._running = True
        self._angle = 0.0
        self._pulse = 0.0
        self._voice_busy = False

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.root = ctk.CTk()
        self.root.title("J.A.R.V.I.S. // STAGEPULSE AI")
        self.root.geometry("1280x760")
        self.root.minsize(1050, 680)
        self.root.configure(fg_color=BG)

        self._setup_ui()
        self.jarvis.on_command(self._on_command)
        self.jarvis.on_response(self._on_response)

        self._animate_hud()
        self._clock_tick()

    def _setup_ui(self):
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0)
        top.grid(row=0, column=0, columnspan=3, sticky="ew", padx=18, pady=(12, 4))
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            top, text="J.A.R.V.I.S.", text_color=GOLD,
            font=("Segoe UI", 25, "bold")
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            top,
            text="JUST A RATHER VERY INTELLIGENT SYSTEM   //   STAGEPULSE",
            text_color=MUTED, font=("Consolas", 10)
        ).grid(row=1, column=0, sticky="w")

        self.clock = ctk.CTkLabel(
            top, text="", text_color=WHITE, font=("Consolas", 12)
        )
        self.clock.grid(row=0, column=2, sticky="e")

        self.status = ctk.CTkLabel(
            top, text="● ONLINE", text_color=GOLD,
            font=("Consolas", 10, "bold")
        )
        self.status.grid(row=1, column=2, sticky="e")

        left = ctk.CTkFrame(
            self.root, fg_color=PANEL, corner_radius=2,
            border_width=1, border_color=GOLD2, width=205
        )
        left.grid(row=1, column=0, sticky="ns", padx=(18, 7), pady=5)

        self._section(left, "SYSTEMS")
        self._telemetry(left, "AI CORE", "OLLAMA", GREEN)
        self._telemetry(left, "LOCAL CORE", "OLLAMA", GREEN)
        self._telemetry(left, "VOICE", "READY", GREEN)
        self._telemetry(left, "NETWORK", "ONLINE", GREEN)

        self._section(left, "AUDIO")
        self._meter(left, "MIC INPUT")
        self._meter(left, "TTS OUTPUT")
        self._meter(left, "SIGNAL")

        self._section(left, "CONTROL")
        self.voice_var = ctk.BooleanVar(
            value=config.get("voice.enabled", True)
        )
        ctk.CTkSwitch(
            left, text="Voice", variable=self.voice_var,
            command=self._toggle_voice,
            progress_color=GOLD2, button_color=GOLD,
            button_hover_color=WHITE, text_color=WHITE
        ).pack(anchor="w", padx=12, pady=4)

        if self.jarvis.wake_word_detector:
            self.wake_word_var = ctk.BooleanVar(value=False)
            ctk.CTkSwitch(
                left, text="Wake word", variable=self.wake_word_var,
                command=self._toggle_wake_word,
                progress_color=GOLD2, button_color=GOLD,
                text_color=WHITE
            ).pack(anchor="w", padx=12, pady=4)

        center = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0)
        center.grid(row=1, column=1, sticky="nsew", padx=7, pady=5)
        center.grid_rowconfigure(0, weight=1)
        center.grid_columnconfigure(0, weight=1)

        self.hud = tk.Canvas(
            center, bg=BG, highlightthickness=0, bd=0
        )
        self.hud.grid(row=0, column=0, sticky="nsew")
        self.hud.bind("<Configure>", self._redraw_hud)

        right = ctk.CTkFrame(
            self.root, fg_color=PANEL, corner_radius=2,
            border_width=1, border_color=GOLD2, width=215
        )
        right.grid(row=1, column=2, sticky="ns", padx=(7, 18), pady=5)

        self._section(right, "JARVIS STATUS")
        self.phase = ctk.CTkLabel(
            right, text="IDLE", text_color=GOLD,
            font=("Consolas", 18, "bold")
        )
        self.phase.pack(anchor="w", padx=12, pady=(2, 12))

        self._section(right, "CURRENT TASK")
        self.task = ctk.CTkLabel(
            right, text="Waiting for command...", text_color=WHITE,
            justify="left", wraplength=180, font=("Consolas", 10)
        )
        self.task.pack(anchor="w", padx=12, pady=(2, 16))

        self._section(right, "ACTIVITY")
        self.activity = ctk.CTkTextbox(
            right, width=190, height=245,
            fg_color="#030405", text_color=MUTED,
            border_width=0, font=("Consolas", 9)
        )
        self.activity.pack(fill="both", expand=True, padx=8, pady=5)
        self.activity.configure(state="disabled")

        bottom = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0)
        bottom.grid(row=2, column=0, columnspan=3, sticky="ew",
                    padx=18, pady=(5, 14))
        bottom.grid_columnconfigure(0, weight=1)

        self.command_entry = ctk.CTkEntry(
            bottom, placeholder_text="COMMAND // Türkçe komut gir...",
            height=44, fg_color="#090B0D",
            border_color=GOLD2, border_width=1,
            text_color=WHITE, placeholder_text_color=MUTED,
            font=("Consolas", 11)
        )
        self.command_entry.grid(row=0, column=0, sticky="ew", padx=(0, 7))
        self.command_entry.bind("<Return>", self._on_enter_pressed)

        ctk.CTkButton(
            bottom, text="EXECUTE", width=105, height=44,
            fg_color=GOLD2, hover_color=GOLD, text_color="#050505",
            font=("Consolas", 10, "bold"),
            command=self._on_send_clicked
        ).grid(row=0, column=1, padx=4)

        self.voice_button = ctk.CTkButton(
            bottom, text="◉ VOICE", width=105, height=44,
            fg_color="#0A0D10", hover_color="#171B20",
            border_width=1, border_color=GOLD, text_color=GOLD,
            font=("Consolas", 10, "bold"),
            command=self._on_voice_clicked
        )
        self.voice_button.grid(row=0, column=2, padx=4)

        ctk.CTkButton(
            bottom, text="CLEAR", width=80, height=44,
            fg_color="#090B0D", hover_color="#15181C",
            border_width=1, border_color="#34383D",
            text_color=MUTED, command=self._clear_chat
        ).grid(row=0, column=3, padx=(4, 0))

        self.chat_display = ctk.CTkTextbox(
            center, width=1, height=1, fg_color=BG,
            text_color=WHITE, border_width=0,
            font=("Consolas", 9)
        )
        self.chat_display.grid(row=1, column=0, sticky="ew", padx=8, pady=2)
        self.chat_display.configure(state="disabled")

        self._append_to_chat(
            "JARVIS", "PATRON, JARVIS çevrimiçi. Sistemler hazır.", "green"
        )
        self._activity("SYSTEM INITIALIZED")
        self._activity("AI CORE: OLLAMA ONLY")
        self._activity("LOCAL CORE: OLLAMA")

    def _section(self, parent, text):
        ctk.CTkLabel(
            parent, text=text, text_color=GOLD2,
            font=("Consolas", 9, "bold")
        ).pack(anchor="w", padx=12, pady=(13, 4))

    def _telemetry(self, parent, label, value, color):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(
            row, text=label, text_color=MUTED, font=("Consolas", 9)
        ).pack(side="left")
        ctk.CTkLabel(
            row, text=value, text_color=color, font=("Consolas", 9, "bold")
        ).pack(side="right")

    def _meter(self, parent, label):
        ctk.CTkLabel(
            parent, text=label, text_color=MUTED, font=("Consolas", 8)
        ).pack(anchor="w", padx=12, pady=(4, 0))
        meter = ctk.CTkProgressBar(
            parent, height=4, progress_color=GOLD, fg_color="#1B1D20"
        )
        meter.pack(fill="x", padx=12, pady=(2, 4))
        meter.set(0.08)

    def _redraw_hud(self, event=None):
        self._draw_hud()

    def _draw_hud(self):
        if not self._running:
            return
        w = max(self.hud.winfo_width(), 500)
        h = max(self.hud.winfo_height(), 400)
        self.hud.delete("all")

        cx = w / 2
        cy = h / 2 - 20
        base = min(w, h) * 0.31

        self.hud.create_rectangle(
            12, 12, w - 12, h - 12, outline="#171A1D", width=1
        )
        self.hud.create_line(25, cy, w - 25, cy, fill="#101417")
        self.hud.create_line(cx, 25, cx, h - 25, fill="#101417")

        for i, mult in enumerate((1.34, 1.20, 1.06, .91, .74)):
            r = base * mult
            self.hud.create_oval(
                cx-r, cy-r, cx+r, cy+r,
                outline=GOLD2 if i < 3 else "#5C4C1A",
                width=2 if i == 2 else 1
            )

        angle = self._angle
        for offset, extent in ((0, 62), (120, 36), (225, 55)):
            r = base * 1.27
            self.hud.create_arc(
                cx-r, cy-r, cx+r, cy+r,
                start=angle + offset, extent=extent,
                style="arc", outline=GOLD, width=3
            )

        r = base * .98
        self.hud.create_arc(
            cx-r, cy-r, cx+r, cy+r,
            start=-angle * 1.4, extent=115,
            style="arc", outline=CYAN, width=2
        )

        pulse = 1 + 0.035 * math.sin(self._pulse)
        core = base * .22 * pulse
        inner = core * .62

        self.hud.create_oval(
            cx-core, cy-core, cx+core, cy+core,
            outline=GOLD, width=3
        )
        self.hud.create_oval(
            cx-inner, cy-inner, cx+inner, cy+inner,
            fill="#0A0905", outline=GOLD, width=2
        )
        self.hud.create_oval(
            cx-inner*.48, cy-inner*.48,
            cx+inner*.48, cy+inner*.48,
            fill=GOLD, outline=GOLD
        )

        for i in range(6):
            a = math.radians(angle * .4 + i * 60)
            r1, r2 = base * .34, base * .55
            self.hud.create_line(
                cx + math.cos(a)*r1, cy + math.sin(a)*r1,
                cx + math.cos(a)*r2, cy + math.sin(a)*r2,
                fill=GOLD2, width=2
            )

        b, s = base * .64, 22
        for x, y, dx, dy in (
            (cx-b, cy-b, 1, 1), (cx+b, cy-b, -1, 1),
            (cx-b, cy+b, 1, -1), (cx+b, cy+b, -1, -1)
        ):
            self.hud.create_line(x, y, x+dx*s, y, fill=GOLD, width=2)
            self.hud.create_line(x, y, x, y+dy*s, fill=GOLD, width=2)

        self.hud.create_text(
            cx, cy + base*.48, text="J.A.R.V.I.S.",
            fill=GOLD, font=("Consolas", 13, "bold")
        )
        self.hud.create_text(
            cx, cy + base*.58, text="SYSTEM CORE // ONLINE",
            fill=MUTED, font=("Consolas", 8)
        )

        self.hud.create_text(
            38, 34, text="STAGEPULSE / AI CONTROL",
            fill=GOLD2, anchor="w", font=("Consolas", 8)
        )
        self.hud.create_text(
            38, h-34, text="VOICE // AI // SYSTEM // WEB",
            fill=MUTED, anchor="w", font=("Consolas", 8)
        )
        self.hud.create_text(
            w-38, 34, text="SECURE LINK",
            fill=GREEN, anchor="e", font=("Consolas", 8)
        )

    def _animate_hud(self):
        if not self._running:
            return
        self._angle = (self._angle + 1.4) % 360
        self._pulse += 0.14
        self._draw_hud()
        self.root.after(45, self._animate_hud)

    def _clock_tick(self):
        if not self._running:
            return
        self.clock.configure(text=time.strftime("%d.%m.%Y   %H:%M:%S"))
        self.root.after(1000, self._clock_tick)

    def _on_enter_pressed(self, event):
        self._on_send_clicked()

    def _on_send_clicked(self):
        command = self.command_entry.get().strip()
        if not command:
            return
        self.command_entry.delete(0, "end")
        self._append_to_chat("YOU", command, "gold")
        self.task.configure(text=command[:90])
        self.phase.configure(text="PROCESSING")
        self.status.configure(text="● PROCESSING", text_color=GOLD)
        self._activity("CMD > " + command[:46])
        self.jarvis.process_command(
            command, speak_response=self.voice_var.get()
        )

    def _on_voice_clicked(self):
        if self._voice_busy:
            return
        self._voice_busy = True
        self.voice_button.configure(
            text="◉ LISTENING", fg_color="#38240A", text_color=GOLD
        )
        self.phase.configure(text="LISTENING")
        self.status.configure(text="● LISTENING", text_color=GOLD)
        self._activity("VOICE INPUT ACTIVE")

        def worker():
            try:
                result = self.jarvis.process_voice_command()
                if isinstance(result, dict):
                    if result.get("success") is False and result.get("error") == "timeout":
                        self.root.after(
                            0, lambda: self._append_to_chat(
                                "SYSTEM", "Ses algılanmadı.", "yellow"
                            )
                        )
            except Exception as e:
                self.root.after(
                    0, lambda: self._append_to_chat("SYSTEM", str(e), "red")
                )
            finally:
                self.root.after(0, self._voice_finished)

        threading.Thread(
            target=worker, daemon=True, name="JARVIS-Voice"
        ).start()

    def _voice_finished(self):
        self._voice_busy = False
        self.voice_button.configure(
            text="◉ VOICE", fg_color="#0A0D10", text_color=GOLD
        )
        self.phase.configure(text="IDLE")
        self.status.configure(text="● ONLINE", text_color=GREEN)

    def _on_command(self, command):
        pass

    def _on_response(self, result):
        response = result.get("response", "")
        success = result.get("success", False)
        self._append_to_chat(
            "JARVIS", response, "green" if success else "red"
        )
        self.task.configure(text="Ready")
        self.phase.configure(text="IDLE")
        self.status.configure(
            text="● ONLINE" if success else "● ERROR",
            text_color=GREEN if success else RED
        )
        self._activity(
            ("OK  " if success else "ERR ") +
            response.replace("\n", " ")[:55]
        )

    def _append_to_chat(self, sender, message, color="white"):
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", f"{sender}: {message}\n")
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")

    def _activity(self, text):
        self.activity.configure(state="normal")
        self.activity.insert(
            "end", time.strftime("%H:%M:%S ") + text + "\n"
        )
        self.activity.see("end")
        self.activity.configure(state="disabled")

    def _toggle_wake_word(self):
        if self.wake_word_var.get():
            self.jarvis.start_wake_word_detection()
            self._activity("WAKE WORD ENABLED")
        elif self.jarvis.wake_word_detector:
            self.jarvis.wake_word_detector.stop()
            self._activity("WAKE WORD DISABLED")

    def _toggle_voice(self):
        enabled = self.voice_var.get()
        config.set("voice.enabled", enabled, save=False)
        self._activity("VOICE " + ("ENABLED" if enabled else "DISABLED"))

    def _clear_chat(self):
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        self.chat_display.configure(state="disabled")
        self._activity("CHAT CLEARED")

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.root.mainloop()

    def _on_closing(self):
        self._running = False
        self.jarvis.stop()
        self.root.destroy()

# === JARVIS THREAD SAFE GUI PATCH ===
def _jarvis_gui_response(self, result):
    try:
        self.root.after(0, lambda r=result: self._render_response_safe(r))
    except Exception:
        pass

def _render_response_safe(self, result):
    response = result.get("response", "")
    success = result.get("success", False)
    self._append_to_chat("JARVIS", response, "green" if success else "red")

    if hasattr(self, "task"):
        self.task.configure(text="Ready")
    if hasattr(self, "phase"):
        self.phase.configure(text="IDLE")
    if hasattr(self, "status"):
        self.status.configure(
            text="● ONLINE" if success else "● ERROR",
            text_color=GREEN if success else RED
        )
    if hasattr(self, "_activity"):
        self._activity(
            ("OK  " if success else "ERR ") +
            response.replace("\\n", " ")[:55]
        )

def _jarvis_gui_voice(self):
    if getattr(self, "_voice_busy", False):
        return

    self._voice_busy = True
    try:
        self.voice_button.configure(
            text="◉ LISTENING",
            fg_color="#38240A",
            text_color=GOLD
        )
        self.phase.configure(text="LISTENING")
        self.status.configure(text="● LISTENING", text_color=GOLD)
        self._activity("VOICE INPUT ACTIVE")
    except Exception:
        pass

    def worker():
        try:
            result = self.jarvis.process_voice_command()
            self.root.after(0, lambda r=result: self._voice_result_safe(r))
        except Exception as e:
            self.root.after(0, lambda e=e: self._voice_error_safe(e))

    threading.Thread(
        target=worker,
        daemon=True,
        name="JARVIS-Voice"
    ).start()

def _voice_result_safe(self, result):
    if isinstance(result, dict) and result.get("success"):
        text = result.get("text")
        if text:
            self._append_to_chat("YOU", text, "gold")
        self._activity("VOICE COMMAND RECEIVED")
    else:
        if isinstance(result, dict):
            msg = result.get("message") or result.get("error") or "Ses anlaşılamadı."
        else:
            msg = "Ses anlaşılamadı."
        if msg == "timeout":
            msg = "Ses algılanmadı. Mikrofonu kontrol edin."
        self._append_to_chat("SYSTEM", str(msg), "yellow")
        self._activity("VOICE ERROR: " + str(msg)[:50])
    self._voice_finished()

def _voice_error_safe(self, error):
    self._append_to_chat("SYSTEM", "Ses hatası: " + str(error), "red")
    self._activity("VOICE ERROR")
    self._voice_finished()

def _voice_finished_safe(self):
    self._voice_busy = False
    try:
        self.voice_button.configure(
            text="◉ VOICE",
            fg_color="#0A0D10",
            text_color=GOLD
        )
        self.phase.configure(text="IDLE")
        self.status.configure(text="● ONLINE", text_color=GREEN)
    except Exception:
        pass

JarvisGUI._on_response = _jarvis_gui_response
JarvisGUI._on_voice_clicked = _jarvis_gui_voice
JarvisGUI._voice_finished = _voice_finished_safe
