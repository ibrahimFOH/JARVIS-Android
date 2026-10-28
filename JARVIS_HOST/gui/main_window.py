
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import threading
import math
import time
import sys
import os
from pathlib import Path
from tkinter import filedialog
from xml.sax.saxutils import escape
from utils.logger import get_logger
from utils.config_manager import get_config
from core.update_manager import WindowsUpdateManager

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
        self.update_manager = WindowsUpdateManager()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.root = ctk.CTk()
        self.root.title("J.A.R.V.I.S. // STAGEPULSE AI")
        self.root.geometry("1280x760")
        self.root.minsize(1050, 680)
        self.root.configure(fg_color=BG)
        self._fullscreen = bool(config.get("gui.fullscreen_start", True))
        self.root.bind("<F11>", self._toggle_fullscreen)
        self.root.bind("<Escape>", self._exit_fullscreen)
        self.root.after(100, self._start_fullscreen)

        self._setup_ui()
        self.jarvis.on_command(self._on_command)
        self.jarvis.on_response(self._on_response)

        self._animate_hud()
        self._clock_tick()
        self._check_for_updates(manual=False)
        if config.get("voice.continuous_listening", True):
            self.root.after(900, self._start_continuous_listening)

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

        ctk.CTkButton(
            top, text="AI PROVIDER", width=125, height=28,
            fg_color="#11100A", hover_color="#28210D",
            border_width=1, border_color=GOLD2, text_color=GOLD,
            font=("Consolas", 9, "bold"),
            command=self._open_ai_settings
        ).grid(row=1, column=1, sticky="e", padx=(0, 18), pady=(0, 2))

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

        self.always_listening_var = ctk.BooleanVar(
            value=config.get("voice.continuous_listening", True)
        )
        ctk.CTkSwitch(
            left, text="Always listen", variable=self.always_listening_var,
            command=self._toggle_continuous_listening,
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
            bottom, text="UZMANLAR", width=105, height=44,
            fg_color="#11100A", hover_color="#28210D",
            border_width=1, border_color=GOLD, text_color=GOLD,
            font=("Consolas", 10, "bold"),
            command=self._open_experts
        ).grid(row=0, column=3, padx=(4, 0))

        ctk.CTkButton(
            bottom, text="CLEAR", width=80, height=44,
            fg_color="#090B0D", hover_color="#15181C",
            border_width=1, border_color="#34383D",
            text_color=MUTED, command=self._clear_chat
        ).grid(row=0, column=4, padx=(4, 0))

        ctk.CTkButton(
            bottom, text="UPDATE", width=90, height=44,
            fg_color="#090B0D", hover_color="#171B20",
            border_width=1, border_color=GOLD, text_color=GOLD,
            command=lambda: self._check_for_updates(manual=True)
        ).grid(row=0, column=5, padx=(4, 0))

        ctk.CTkButton(
            bottom, text="PDF AÇ", width=78, height=44,
            fg_color="#090B0D", hover_color="#171B20",
            border_width=1, border_color=GOLD, text_color=GOLD,
            command=self._on_pdf_clicked
        ).grid(row=0, column=6, padx=(4, 0))

        ctk.CTkButton(
            bottom, text="SOHBET PDF", width=105, height=44,
            fg_color="#090B0D", hover_color="#171B20",
            border_width=1, border_color=GOLD, text_color=GOLD,
            command=self._export_chat_pdf
        ).grid(row=0, column=7, padx=(4, 0))

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

    def _check_for_updates(self, manual=False):
        if manual:
            self._activity("CHECKING FOR UPDATES")

        def worker():
            try:
                update = self.update_manager.check_for_update(force=manual)
                if update is not None:
                    self.root.after(0, lambda item=update: self._offer_update(item))
                elif manual:
                    self.root.after(0, lambda: messagebox.showinfo(
                        "JARVIS Güncelleme", "Kurulu Windows JARVIS sürümü güncel."
                    ))
            except Exception as exc:
                if manual:
                    self.root.after(0, lambda error=exc: messagebox.showerror(
                        "Güncelleme Kontrolü", "Güncelleme kontrol edilemedi.\n" + str(error)
                    ))
                else:
                    self.root.after(0, lambda: self._activity("UPDATE CHECK FAILED"))

        threading.Thread(
            target=worker, daemon=True, name="JARVIS-Update-Check"
        ).start()

    def _offer_update(self, update):
        message = (
            "Yeni Windows JARVIS sürümü bulundu: " + update.version_name + "\n\n"
            + update.notes + "\n\n"
            + "Paket HTTPS üzerinden indirilecek, SHA-256 ile doğrulanacak ve mevcut "
            + "kurulum klasörüne uygulanacak. Kişisel config ve bridge token korunacak; "
            + "eski sürüm geri dönüş için yedek klasörde tutulacak."
        )
        if not getattr(sys, "frozen", False):
            open_release = messagebox.askyesno(
                "JARVIS Güncellemesi",
                "Yeni sürüm bulundu: " + update.version_name
                + "\nJARVIS kaynak koduyla çalışıyor; bu modda kendini değiştiremez. "
                + "GitHub Release sayfasını açayım mı?"
            )
            if open_release:
                import webbrowser
                webbrowser.open(
                    "https://github.com/ibrahimFOH/JARVIS-Android/releases/tag/"
                    + update.tag_name
                )
            return

        if not messagebox.askyesno("JARVIS Güncellemesi", message):
            self._activity("UPDATE DEFERRED")
            return

        self.status.configure(text="● DOWNLOADING UPDATE", text_color=GOLD)
        self.phase.configure(text="UPDATING")
        self._activity("UPDATE DOWNLOAD STARTED")

        def worker():
            try:
                result = self.update_manager.download_and_launch_installer(update)
                self.root.after(0, lambda: self._append_to_chat("SYSTEM", result, "green"))
                self.root.after(1200, self._on_closing)
            except Exception as exc:
                self.root.after(0, lambda error=exc: messagebox.showerror(
                    "Güncelleme Başarısız", "JARVIS güncellenemedi. Mevcut kurulum korundu.\n" + str(error)
                ))
                self.root.after(0, lambda: self.status.configure(
                    text="● UPDATE FAILED", text_color=RED
                ))
                self.root.after(0, lambda: self._activity("UPDATE FAILED"))

        threading.Thread(
            target=worker, daemon=True, name="JARVIS-Update-Install"
        ).start()

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
        enabled = bool(self.voice_var.get())
        config.set("voice.enabled", enabled, save=True)
        self.jarvis.set_voice_enabled(enabled)
        if not enabled and self.always_listening_var.get():
            self.always_listening_var.set(False)
            config.set("voice.continuous_listening", False, save=True)
            self.jarvis.stop_listening()
        elif enabled and self.always_listening_var.get():
            self._start_continuous_listening()
        self._activity("VOICE " + ("ENABLED" if enabled else "DISABLED"))

    def _toggle_continuous_listening(self):
        enabled = bool(self.always_listening_var.get()) and bool(self.voice_var.get())
        config.set("voice.continuous_listening", enabled, save=True)
        if enabled:
            started = self.jarvis.start_listening()
            if started:
                self.status.configure(text="● ALWAYS LISTENING", text_color=GOLD)
                self.phase.configure(text="LISTENING")
                self._activity("CONTINUOUS LISTENING STARTED")
            else:
                self.always_listening_var.set(False)
                config.set("voice.continuous_listening", False, save=True)
                messagebox.showwarning(
                    "Mikrofon", "Sürekli dinleme başlatılamadı. Mikrofonu ve Windows izinlerini kontrol edin.",
                    parent=self.root
                )
        else:
            self.jarvis.stop_listening()
            self.status.configure(text="● ONLINE", text_color=GREEN)
            self.phase.configure(text="IDLE")
            self._activity("CONTINUOUS LISTENING STOPPED")

    def _start_continuous_listening(self):
        if not self._running or not self.voice_var.get() or not self.always_listening_var.get():
            return
        self._toggle_continuous_listening()

    def _start_fullscreen(self):
        try:
            self.root.attributes("-fullscreen", self._fullscreen)
        except Exception as exc:
            logger.warning("Tam ekran başlatılamadı: " + str(exc))

    def _toggle_fullscreen(self, _event=None):
        self._fullscreen = not self._fullscreen
        try:
            self.root.attributes("-fullscreen", self._fullscreen)
        except Exception as exc:
            logger.warning("Tam ekran değiştirilemedi: " + str(exc))
        return "break"

    def _exit_fullscreen(self, _event=None):
        self._fullscreen = False
        try:
            self.root.attributes("-fullscreen", False)
            self.root.geometry("1280x760")
        except Exception as exc:
            logger.warning("Tam ekrandan çıkılamadı: " + str(exc))
        return "break"

    def _on_pdf_clicked(self):
        filename = filedialog.askopenfilename(
            parent=self.root, title="Analiz edilecek PDF dosyasını seçin",
            filetypes=[("PDF dosyaları", "*.pdf")]
        )
        if not filename:
            return
        try:
            from pypdf import PdfReader
            reader = PdfReader(filename)
            pages = []
            for page in reader.pages:
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(text.strip())
                if sum(len(item) for item in pages) >= 45000:
                    break
            document_text = "\n\n".join(pages).strip()
            if not document_text:
                messagebox.showwarning(
                    "PDF", "Bu PDF'den metin çıkarılamadı. Tarama/görüntü tabanlı PDF'ler için OCR gerekir.",
                    parent=self.root
                )
                return
            document_text = document_text[:45000]
            prompt = (
                "Aşağıdaki PDF belgesini Türkçe incele. Önce kapsamlı ama anlaşılır bir özet, "
                "sonra önemli maddeler, tarihler ve varsa riskleri ver. Belgede bulunmayan bilgi uydurma.\n\n"
                "DOSYA: " + Path(filename).name + "\n\nBELGE METNİ:\n" + document_text
            )
            self._append_to_chat("YOU", "PDF analizi: " + Path(filename).name, "gold")
            self.task.configure(text="PDF analiz ediliyor: " + Path(filename).name[:60])
            self.phase.configure(text="PROCESSING PDF")
            self.status.configure(text="● PROCESSING", text_color=GOLD)
            self.jarvis.process_command(prompt, speak_response=self.voice_var.get())
        except Exception as exc:
            logger.error("PDF analizi başarısız")
            messagebox.showerror("PDF", "PDF okunamadı: " + str(exc), parent=self.root)

    def _export_chat_pdf(self):
        transcript = self.chat_display.get("1.0", "end").strip()
        if not transcript:
            messagebox.showwarning("Sohbet PDF", "Kaydedilecek sohbet bulunamadı.", parent=self.root)
            return
        filename = filedialog.asksaveasfilename(
            parent=self.root, title="Sohbeti PDF olarak kaydet",
            defaultextension=".pdf", filetypes=[("PDF dosyası", "*.pdf")],
            initialfile="Stagepulse-JARVIS-Sohbet.pdf"
        )
        if not filename:
            return
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

            font_name = "Helvetica"
            font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf"
            bold_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arialbd.ttf"
            if font_path.is_file():
                pdfmetrics.registerFont(TTFont("StagepulseArial", str(font_path)))
                font_name = "StagepulseArial"
                if bold_path.is_file():
                    pdfmetrics.registerFont(TTFont("StagepulseArial-Bold", str(bold_path)))
                    pdfmetrics.registerFontFamily(font_name, normal=font_name, bold="StagepulseArial-Bold", italic=font_name, boldItalic="StagepulseArial-Bold")
            styles = getSampleStyleSheet()
            body = ParagraphStyle("StagepulseBody", parent=styles["BodyText"], fontName=font_name, fontSize=9, leading=13, textColor=colors.HexColor("#202020"), wordWrap="CJK", spaceAfter=5)
            heading = ParagraphStyle("StagepulseHeading", parent=styles["Title"], fontName=font_name, fontSize=16, leading=20, textColor=colors.HexColor("#8C7220"), spaceAfter=10)
            story = [Paragraph("STAGEPULSE JARVIS SOHBET RAPORU", heading),
                     Paragraph(escape(time.strftime("%d.%m.%Y %H:%M")), body), Spacer(1, 4 * mm)]
            for line in transcript.splitlines():
                story.append(Paragraph(escape(line) if line.strip() else "&#160;", body))
            doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=17*mm, bottomMargin=17*mm, title="Stagepulse JARVIS Sohbet Raporu", author="Stagepulse")
            doc.build(story)
            messagebox.showinfo("Sohbet PDF", "PDF kaydedildi:\n" + filename, parent=self.root)
        except Exception as exc:
            logger.error("Sohbet PDF dışa aktarma başarısız")
            messagebox.showerror("Sohbet PDF", "PDF oluşturulamadı: " + str(exc), parent=self.root)

    def _clear_chat(self):
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        self.chat_display.configure(state="disabled")
        self._activity("CHAT CLEARED")

    def _open_ai_settings(self):
        """Configure optional cloud AI providers without replacing Turkish/local defaults."""
        brain = self.jarvis.command_processor.ai_brain
        win = ctk.CTkToplevel(self.root)
        win.title("STAGEPULSE // AI PROVIDER")
        win.geometry("650x850")
        win.minsize(590, 650)
        win.configure(fg_color=BG)
        win.transient(self.root)
        win.grab_set()

        content = ctk.CTkScrollableFrame(win, fg_color=BG, corner_radius=0)
        content.pack(fill="both", expand=True, padx=8, pady=(8, 0))
        actions = ctk.CTkFrame(win, fg_color=BG, corner_radius=0)
        actions.pack(fill="x", padx=12, pady=8)

        ctk.CTkLabel(
            content, text="YAPAY ZEKÂ SAĞLAYICISI", text_color=GOLD,
            font=("Consolas", 12, "bold")
        ).pack(anchor="w", padx=20, pady=(16, 5))
        provider = ctk.StringVar(value=brain.provider)
        ctk.CTkOptionMenu(
            content, variable=provider,
            values=["auto", "ollama", "gemini", "groq", "openai", "grok",
                    "anthropic", "deepseek", "perplexity", "openrouter", "custom"],
            width=550, fg_color="#17191C", button_color=GOLD2,
            button_hover_color=GOLD, text_color=WHITE
        ).pack(anchor="w", padx=20, pady=(0, 10))

        def field(label, value="", secret=False):
            ctk.CTkLabel(
                content, text=label, text_color=WHITE,
                font=("Consolas", 10)
            ).pack(anchor="w", padx=20, pady=(7, 2))
            entry = ctk.CTkEntry(
                content, width=550, show="*" if secret else "",
                fg_color="#08090A", border_color=GOLD2,
                text_color=WHITE
            )
            entry.pack(anchor="w", padx=20)
            if value:
                entry.insert(0, str(value))
            return entry

        ctk.CTkLabel(
            content, text="YEREL / GOOGLE / GROQ", text_color=GOLD,
            font=("Consolas", 11, "bold")
        ).pack(anchor="w", padx=20, pady=(12, 3))
        ollama_host = field("OLLAMA ADRESİ", brain.host)
        ollama_model = field("OLLAMA MODELİ", brain.model)
        gemini_key = field("GEMINI API ANAHTARI", brain.gemini_key, secret=True)
        gemini_model = field("GEMINI MODELİ", brain.gemini_model)
        gemini_image_model = field("GEMINI GÖRSEL MODELİ", brain.gemini_image_model)
        groq_key = field("GROQ API ANAHTARI", brain.groq_key, secret=True)
        groq_model = field("GROQ MODELİ", brain.groq_model)

        ctk.CTkLabel(
            content, text="DİĞER API SAĞLAYICILARI", text_color=GOLD,
            font=("Consolas", 11, "bold")
        ).pack(anchor="w", padx=20, pady=(14, 3))
        ctk.CTkLabel(
            content,
            text="API anahtarları yerel ayar dosyasında saklanır; Windows'ta DPAPI ile korunmaya çalışılır. Anahtarları kaynak koduna veya GitHub'a yazma.",
            text_color=MUTED, wraplength=550, justify="left",
            font=("Consolas", 9)
        ).pack(anchor="w", padx=20, pady=(0, 4))

        key_entries, model_entries, url_entries = {}, {}, {}
        labels = [
            ("openai", "OPENAI"), ("grok", "GROK / XAI"),
            ("anthropic", "ANTHROPIC"), ("deepseek", "DEEPSEEK"),
            ("perplexity", "PERPLEXITY"), ("openrouter", "OPENROUTER"),
            ("custom", "ÖZEL OPENAI-UYUMLU API"),
        ]
        for name, label in labels:
            default_url, default_model = brain.api_defaults[name]
            key_entries[name] = field(label + " API ANAHTARI", brain.api_keys.get(name, ""), secret=True)
            url_entries[name] = field(label + " BASE URL", brain.api_base_urls.get(name, default_url))
            model_entries[name] = field(label + " MODEL", brain.api_models.get(name, default_model))

        ctk.CTkLabel(
            content,
            text="Otomatik mod, anahtarı tanımlı sağlayıcıları sırayla deneyip yerel Ollama'ya dönebilir. Kendi adresiniz için OpenAI Chat Completions uyumlu bir /chat/completions uç noktası kullanın.",
            text_color=MUTED, wraplength=550, justify="left",
            font=("Consolas", 9)
        ).pack(anchor="w", padx=20, pady=(14, 12))

        def persist():
            brain.configure(
                provider=provider.get(),
                gemini_key=gemini_key.get(),
                gemini_model=gemini_model.get(),
                gemini_image_model=gemini_image_model.get(),
                ollama_host=ollama_host.get(),
                ollama_model=ollama_model.get(),
                groq_key=groq_key.get(),
                groq_model=groq_model.get(),
                api_keys={key: entry.get() for key, entry in key_entries.items()},
                api_models={key: entry.get() for key, entry in model_entries.items()},
                api_base_urls={key: entry.get() for key, entry in url_entries.items()},
            )
            self._activity("AI PROVIDER CONFIGURED: " + brain.provider.upper())

        def save():
            try:
                persist()
                self._append_to_chat(
                    "SYSTEM", "AI ayarları kaydedildi. Sağlayıcı: " + brain.provider.upper(), "green"
                )
                win.destroy()
            except Exception as exc:
                messagebox.showerror("AI ayarları", str(exc), parent=win)

        def test():
            try:
                persist()
            except Exception as exc:
                messagebox.showerror("AI ayarları", str(exc), parent=win)
                return
            target = provider.get()
            self._append_to_chat("SYSTEM", target.upper() + " bağlantısı test ediliyor...", "yellow")

            def worker():
                result = brain.test_provider(target)

                def finish():
                    message = str(result.get("message", "Test tamamlandı."))
                    self._append_to_chat(
                        "SYSTEM", message, "green" if result.get("success") else "red"
                    )
                    if result.get("success"):
                        messagebox.showinfo("AI bağlantı testi", message, parent=win)
                    else:
                        messagebox.showerror("AI bağlantı testi", message, parent=win)
                try:
                    self.root.after(0, finish)
                except Exception:
                    pass

            threading.Thread(
                target=worker, daemon=True,
                name="JARVIS-AI-Provider-Test"
            ).start()

        ctk.CTkButton(
            actions, text="SEÇİLİ SAĞLAYICIYI TEST ET",
            command=test, fg_color="#090B0D", hover_color="#15181C",
            border_width=1, border_color=GOLD2, text_color=GOLD,
            font=("Consolas", 10, "bold")
        ).pack(fill="x", padx=6, pady=3)
        ctk.CTkButton(
            actions, text="AYARLARI KAYDET",
            command=save, fg_color=GOLD2, hover_color=GOLD,
            text_color="#050505", font=("Consolas", 10, "bold")
        ).pack(fill="x", padx=6, pady=3)

    def _open_experts(self):
        """Open the APK-inspired expert workspace in the Windows host."""
        roles = {
            "Genel Asistan": "Türkçe genel amaçlı uzman asistan olarak yanıtla.",
            "FOH ENGINEER": "Canlı miksin ana kontrolünü üstlen. Gain structure, routing, EQ, dynamics, bus/FX, LR/matrix, PA tuning, input list ve soundcheck süreçlerini adım adım ele al.",
            "MONITOR ENGINEER": "Sahne monitörü ve IEM mikslerini yönet. Wedge, PSM300, Behringer P2, aux/mix bus, feedback, cue, talkback, monitor patch ve sanatçı soundcheck konularını ele al.",
            "RF ENGINEER": "Kablosuz mikrofon ve IEM RF koordinasyon uzmanı ol. Shure ULX-D/PSM, frekans planı, scan, intermodülasyon, anten dağıtımı, RF gain ve yedek frekansları değerlendir.",
            "SYSTEM TECH": "PA sisteminin kurulum, patch, kablolama, polarity/phase, delay, DSP, ölçüm, test ve arıza izolasyonu adımlarını planla.",
            "RIDER ANALYST": "Teknik rider'ı ekipman BOM, input list, backline, mikrofon, monitör, RF, PA, sahne, enerji, ışık ve teknik personel gereksinimine dönüştür; çelişkileri ve eksikleri işaretle.",
            "STAGE PLOT ENGINEER": "Sahne planı, sanatçı yerleşimi, davul/mikrofon yerleşimi, DI, monitör, IEM, kablo yolları ve input/patch çizelgesini ölçülü ve tutarlı biçimde hazırla.",
            "SPL CALCULATOR": "SPL hesaplarında referans mesafesi, dB toplama, mesafe kaybı, hoparlör hassasiyeti, güç, headroom ve ölçüm belirsizliğini açık varsayımlarla hesapla.",
            "AUDIO SYSTEM DESIGNER": "Etkinlik için aktif line array/PA, subwoofer, monitör, DSP, konsol, Dante ve sinyal mimarisini mekân, seyirci, SPL hedefi ve kapsama üzerinden tasarla.",
            "LIVE SOUND TROUBLESHOOTER": "Canlı ses arızalarını belirti, sinyal zinciri, bilinen iyi noktadan test, kök neden, düzeltme ve tekrar test sırasıyla teşhis et.",
            "DANTE NETWORK ENGINEER": "Dante ağlarında clock leader, sample rate, subscriptions, IP adresleme, switch/QoS, multicast, latency ve yedek ağ sorunlarını değerlendir.",
            "LIGHTING TECH": "Avolites, DMX, universe, fixture patch/address, moving head, wash/beam, cue, show dosyası ve sahne güvenliği konularında çalış.",
            "EVENT PRODUCTION MANAGER": "Ses, ışık, sahne, LED, ekip, rider, bütçe, load-in/out, venue koordinasyonu, zaman çizelgesi ve etkinlik günü risklerini tek üretim akışında planla.",
            "Stüdyo / Kayıt": "Kayıt, edit, miks, mastering, oda akustiği, monitoring ve sinyal seviyesi uzmanı olarak uygulanabilir teknik adımlar sun.",
            "Windows / Linux": "Windows ve Linux sistem yönetimi ve sorun giderme uzmanı gibi güvenli, geri alınabilir adımlar öner.",
            "Web / SEO": "Web geliştirme, teknik SEO, yerel SEO, erişilebilirlik ve performans konusunda kanıta dayalı öneriler sun.",
            "Yazılım / Kodlama": "Yazılım mühendisi gibi kodu, bağımlılıkları, testleri ve hata ayıklamayı sistematik biçimde ele al.",
            "Eğitim / Dokümantasyon": "Türkçe teknik eğitim, uygulama laboratuvarı, değerlendirme anahtarı ve kaynaklı dokümantasyon hazırla.",
            "İş / Şirket": "Kurumsal teklif, hizmet fiyatlandırması, etkinlik üretimi, pazarlama ve iş geliştirme konusunda gerçekçi öneriler sun.",
            "Araştırma / Kaynak": "Araştırma uzmanı olarak güncel bilgileri doğrula; tarihleri, varsayımları ve belirsizlikleri açıkça belirt, kaynak uydurma."
        }
        win = ctk.CTkToplevel(self.root)
        win.title("STAGEPULSE JARVIS // UZMANLAR")
        win.geometry("760x600")
        win.minsize(620, 500)
        win.configure(fg_color=BG)
        win.transient(self.root)

        ctk.CTkLabel(
            win, text="UZMAN MODÜLLERİ", text_color=GOLD,
            font=("Segoe UI", 20, "bold")
        ).pack(anchor="w", padx=22, pady=(20, 4))
        ctk.CTkLabel(
            win, text="Bir uzmanlık seç ve görevini yaz. Yanıt ana JARVIS sohbetinde gösterilir.",
            text_color=MUTED, wraplength=680, justify="left"
        ).pack(anchor="w", padx=22, pady=(0, 14))

        role_var = tk.StringVar(value="Genel Asistan")
        ctk.CTkLabel(win, text="UZMANLIK", text_color=GOLD2).pack(anchor="w", padx=22)
        ctk.CTkOptionMenu(
            win, variable=role_var, values=list(roles.keys()),
            fg_color="#17191C", button_color=GOLD2,
            button_hover_color=GOLD, text_color=WHITE,
            dropdown_fg_color="#101214", dropdown_text_color=WHITE,
            width=330, height=38
        ).pack(anchor="w", padx=22, pady=(5, 14))

        ctk.CTkLabel(win, text="GÖREV / SORU", text_color=GOLD2).pack(anchor="w", padx=22)
        question = ctk.CTkTextbox(
            win, height=260, fg_color="#08090A",
            text_color=WHITE, border_width=1, border_color=GOLD2,
            font=("Consolas", 11), wrap="word"
        )
        question.pack(fill="both", expand=True, padx=22, pady=(5, 16))

        def submit():
            query = question.get("1.0", "end").strip()
            if not query:
                messagebox.showwarning("Uzmanlar", "Önce bir görev veya soru yaz.", parent=win)
                return
            role = role_var.get()
            system_prompt = ""
            tool_output = ""
            try:
                from core.specialist_agents import route_agent, prepare_expert_task
                specialist_id = route_agent(role + "\n" + query)
                if specialist_id:
                    system_prompt, tool_output = prepare_expert_task(specialist_id, query)
            except Exception as exc:
                logger.warning("Uzman profil/araç sistemi kullanılamadı: " + str(exc))
            prompt = (
                "UZMANLIK: " + role + "\n" + roles[role] +
                ("\n\nUZMAN TEKNİK TALİMATLARI:\n" + system_prompt if system_prompt else "") +
                ("\n\nDOĞRULANABİLİR HESAPLAMA ARAÇLARI:\n" + tool_output if tool_output else "") +
                "\n\nKullanıcı isteği: " + query +
                "\n\nYanıtı Türkçe ver. Gerektiğinde adım adım yönerge, kontrol listesi, "
                "riskler ve doğrulanması gereken varsayımları ek. Hesap sonuçlarının varsayımlarını açıkla."
            )
            self._append_to_chat("YOU / " + role, query, "gold")
            self._activity("EXPERT TASK: " + role)
            win.destroy()

            def worker():
                try:
                    self.jarvis.process_command(
                        prompt, speak_response=self.voice_var.get()
                    )
                    self.root.after(0, lambda: self._activity("EXPERT TASK COMPLETE"))
                except Exception as exc:
                    self.root.after(
                        0, lambda err=exc: self._append_to_chat(
                            "SYSTEM", "Uzman görevi başarısız: " + str(err), "red"
                        )
                    )
            threading.Thread(
                target=worker, daemon=True, name="JARVIS-Expert-Task"
            ).start()

        ctk.CTkButton(
            win, text="UZMAN YANITINI AL", height=44,
            fg_color=GOLD2, hover_color=GOLD, text_color="#050505",
            font=("Consolas", 10, "bold"), command=submit
        ).pack(fill="x", padx=22, pady=(0, 20))

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
        listening = bool(getattr(self, "always_listening_var", None) and self.always_listening_var.get())
        self.status.configure(
            text=("● ALWAYS LISTENING" if listening else "● ONLINE") if success else "● ERROR",
            text_color=GOLD if listening and success else (GREEN if success else RED)
        )
    if hasattr(self, "phase") and getattr(self, "always_listening_var", None) is not None and self.always_listening_var.get() and success:
        self.phase.configure(text="LISTENING")
    if hasattr(self, "_activity"):
        self._activity(
            ("OK  " if success else "ERR ") +
            response.replace("\\n", " ")[:55]
        )

def _jarvis_gui_voice(self):
    if getattr(self, "always_listening_var", None) is not None and self.always_listening_var.get():
        self._activity("SÜREKLİ DİNLEME ETKİN; ayrı kayıt başlatılmadı.")
        return
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
