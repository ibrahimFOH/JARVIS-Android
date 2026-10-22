
import tkinter as tk
from tkinter import filedialog, messagebox
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
        self._voice_listening = False
        self._voice_stop_event = threading.Event()
        self._voice_response_event = threading.Event()
        self._voice_last_response = None
        self._pdf_path = None
        self._pdf_text = ""

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.root = ctk.CTk()
        self.root.title("J.A.R.V.I.S. // STAGEPULSE AI")
        self.root.geometry("1280x760")
        self.root.minsize(1050, 680)
        self.root.configure(fg_color=BG)
        # Open directly in fullscreen; F11 toggles it and Escape returns to windowed mode.
        self.root.attributes("-fullscreen", True)
        self.root.bind("<F11>", self._toggle_fullscreen)
        self.root.bind("<Escape>", self._leave_fullscreen)

        self._setup_ui()
        self.jarvis.on_command(self._on_command)
        self.jarvis.on_response(self._on_response)

        self._animate_hud()
        self._clock_tick()
        self._start_android_bridge()
        # Check for a signed-off GitHub Release shortly after startup, off the UI thread.
        self.root.after(5000, self._check_for_updates)

    def _check_for_updates(self):
        def worker():
            try:
                from core.updater import check_latest_release
                release = check_latest_release()
                if not release:
                    return
                def offer():
                    if not self._running:
                        return
                    answer = messagebox.askyesno(
                        "JARVIS güncellemesi",
                        "Yeni bir JARVIS sürümü bulundu: " + release["version"] +
                        "\\n\\nŞimdi indirip uygulamayı güncellemek ister misin? JARVIS kapatılıp yeniden açılacak.",
                        parent=self.root
                    )
                    if answer:
                        self._activity("UPDATE DOWNLOAD STARTED")
                        self._run_ai_task(
                            "JARVIS güncellemesi indiriliyor",
                            lambda: self._download_and_install_update(release),
                            should_speak=False
                        )
                self.root.after(0, offer)
            except Exception as exc:
                logger.info("Update check skipped: %s", exc)

        threading.Thread(target=worker, daemon=True, name="JARVIS-Update-Check").start()

    def _download_and_install_update(self, release):
        from core.updater import download_and_prepare_update
        result = download_and_prepare_update(release)
        # Let the UI display the result, then close so the helper can replace the EXE files.
        self.root.after(2500, self._on_closing)
        return result


    def _start_android_bridge(self):
        try:
            from android_bridge import start_in_background
            start_in_background()
            self._activity("ANDROID BRIDGE: AUTHENTICATED LAN READY")
        except Exception as exc:
            self._activity("ANDROID BRIDGE ERROR: " + str(exc)[:70])

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
            text="AKILLI DİJİTAL ASİSTAN   //   STAGEPULSE",
            text_color=MUTED, font=("Consolas", 10)
        ).grid(row=1, column=0, sticky="w")

        self.clock = ctk.CTkLabel(
            top, text="", text_color=WHITE, font=("Consolas", 12)
        )
        self.clock.grid(row=0, column=2, sticky="e")

        self.status = ctk.CTkLabel(
            top, text="● ÇEVRİMİÇİ", text_color=GOLD,
            font=("Consolas", 10, "bold")
        )
        self.status.grid(row=1, column=2, sticky="e")

        left = ctk.CTkFrame(
            self.root, fg_color=PANEL, corner_radius=2,
            border_width=1, border_color=GOLD2, width=205
        )
        left.grid(row=1, column=0, sticky="ns", padx=(18, 7), pady=5)

        self._section(left, "SİSTEMLER")
        brain = self.jarvis.command_processor.ai_brain
        self.ai_core_value = self._telemetry(left, "YAPAY ZEKÂ", brain.provider.upper(), GREEN)
        self.local_core_value = self._telemetry(left, "YEREL MODEL", "OLLAMA " + brain.model, GREEN)
        self._telemetry(left, "VOICE", "READY", GREEN)
        self._telemetry(left, "AĞ", "ONLINE", GREEN)

        self._section(left, "SES")
        self._meter(left, "MİKROFON GİRİŞİ")
        self._meter(left, "KONUŞMA ÇIKIŞI")
        self._meter(left, "SİNYAL")

        self._section(left, "KONUŞMA SESİ")
        self.tts_voice_choices = {
            "Emel • Kadın / Online": "tr-TR-EmelNeural",
            "Ahmet • Erkek / Online": "tr-TR-AhmetNeural",
            "DFKI • Türkçe / Offline": "piper:dfki",
            "Fahrettin • Türkçe / Offline": "piper:fahrettin",
            "Fettah • Türkçe / Offline": "piper:fettah",
        }
        stored_voice = str(config.get("voice.tts_voice", "tr-TR-EmelNeural")).lower()
        current_voice = "Emel • Kadın / Online"
        for label, voice_id in self.tts_voice_choices.items():
            if stored_voice == voice_id.lower() or stored_voice == voice_id.lower().replace("tr-tr-", ""):
                current_voice = label
            elif stored_voice in ("auto-turkish", "emel", "emelneural") and voice_id == "tr-TR-EmelNeural":
                current_voice = label
        if stored_voice.startswith("piper:"):
            for label, voice_id in self.tts_voice_choices.items():
                if voice_id.lower() == stored_voice:
                    current_voice = label
        self.tts_voice_var = ctk.StringVar(value=current_voice)
        ctk.CTkOptionMenu(
            left, variable=self.tts_voice_var,
            values=list(self.tts_voice_choices.keys()),
            command=self._on_tts_voice_changed,
            width=178, height=30,
            fg_color="#15181C", button_color=GOLD2,
            button_hover_color=GOLD, text_color=WHITE,
            font=("Consolas", 9),
        ).pack(fill="x", padx=10, pady=(2, 4))
        ctk.CTkButton(
            left, text="SESİ SINA", height=28,
            fg_color="#090B0D", hover_color="#15181C",
            border_width=1, border_color=GOLD2, text_color=GOLD,
            font=("Consolas", 9, "bold"),
            command=self._test_tts_voice,
        ).pack(fill="x", padx=10, pady=(0, 4))
        ctk.CTkButton(
            left, text="MİKROFONU SINA", height=28,
            fg_color="#090B0D", hover_color="#15181C",
            border_width=1, border_color=GOLD2, text_color=GOLD,
            font=("Consolas", 9, "bold"),
            command=self._test_microphone,
        ).pack(fill="x", padx=10, pady=(0, 6))

        self._section(left, "KONTROL")
        self.voice_var = ctk.BooleanVar(
            value=config.get("voice.enabled", True)
        )
        ctk.CTkSwitch(
            left, text="Sesli kontrol", variable=self.voice_var,
            command=self._toggle_voice,
            progress_color=GOLD2, button_color=GOLD,
            button_hover_color=WHITE, text_color=WHITE
        ).pack(anchor="w", padx=12, pady=4)

        # Keep the wake-word control visible even when it is not configured yet.
        # Detection starts only after the user explicitly enables this switch.
        self.wake_word_var = ctk.BooleanVar(
            value=config.get("voice.wake_word_enabled", False)
        )
        ctk.CTkSwitch(
            left, text="Uyandırma sözcüğü", variable=self.wake_word_var,
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

        self._section(right, "JARVIS DURUMU")
        self.phase = ctk.CTkLabel(
            right, text="HAZIR", text_color=GOLD,
            font=("Consolas", 18, "bold")
        )
        self.phase.pack(anchor="w", padx=12, pady=(2, 8))

        self._section(right, "YAPILAN İŞLEM")
        self.task = ctk.CTkLabel(
            right, text="Komut bekleniyor...", text_color=WHITE,
            justify="left", wraplength=180, font=("Segoe UI", 10)
        )
        self.task.pack(anchor="w", padx=12, pady=(2, 10))

        self._section(right, "HIZLI ERİŞİM")
        quick_button_style = {
            "height": 36, "fg_color": "#0A0D10", "hover_color": "#171B20",
            "border_width": 1, "border_color": GOLD2, "text_color": GOLD,
            "font": ("Segoe UI", 10, "bold")
        }
        ctk.CTkButton(
            right, text="Mikrofonu Sına",
            command=self._test_microphone, **quick_button_style
        ).pack(fill="x", padx=10, pady=4)
        ctk.CTkButton(
            right, text="Sesi Sına",
            command=self._test_tts_voice, **quick_button_style
        ).pack(fill="x", padx=10, pady=4)
        ctk.CTkButton(
            right, text="PDF Belgesi Aç",
            command=self._on_pdf_clicked, **quick_button_style
        ).pack(fill="x", padx=10, pady=4)
        ctk.CTkButton(
            right, text="Yapay Zekâ Ayarları",
            command=self._open_ai_settings, **quick_button_style
        ).pack(fill="x", padx=10, pady=4)
        ctk.CTkButton(
            right, text="Güncellemeleri Denetle",
            command=self._check_for_updates, **quick_button_style
        ).pack(fill="x", padx=10, pady=4)

        self._section(right, "ETKİN YAPAY ZEKÂ")
        self.right_ai_info = ctk.CTkLabel(
            right,
            text=str(self.jarvis.command_processor.ai_brain.provider).upper(),
            text_color=GREEN, justify="left", wraplength=180,
            font=("Consolas", 10, "bold")
        )
        self.right_ai_info.pack(anchor="w", padx=12, pady=(2, 8))

        self._section(right, "YEREL MODEL")
        self.right_model_info = ctk.CTkLabel(
            right,
            text=str(self.jarvis.command_processor.ai_brain.model),
            text_color=WHITE, justify="left", wraplength=180,
            font=("Consolas", 9)
        )
        self.right_model_info.pack(anchor="w", padx=12, pady=(2, 8))

        bottom = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0)
        bottom.grid(row=2, column=0, columnspan=3, sticky="ew",
                    padx=18, pady=(5, 14))
        bottom.grid_columnconfigure(0, weight=1)

        self.command_entry = ctk.CTkEntry(
            bottom, placeholder_text="KOMUT // Türkçe komut yaz...",
            height=44, fg_color="#090B0D",
            border_color=GOLD2, border_width=1,
            text_color=WHITE, placeholder_text_color=MUTED,
            font=("Consolas", 11)
        )
        self.command_entry.grid(row=0, column=0, sticky="ew", padx=(0, 7))
        self.command_entry.bind("<Return>", self._on_enter_pressed)

        ctk.CTkButton(
            bottom, text="ÇALIŞTIR", width=85, height=44,
            fg_color=GOLD2, hover_color=GOLD, text_color="#050505",
            font=("Consolas", 10, "bold"),
            command=self._on_send_clicked
        ).grid(row=0, column=1, padx=4)

        self.voice_button = ctk.CTkButton(
            bottom, text="◉ SESLİ KOMUT", width=85, height=44,
            fg_color="#0A0D10", hover_color="#171B20",
            border_width=1, border_color=GOLD, text_color=GOLD,
            font=("Consolas", 10, "bold"),
            command=self._on_voice_clicked
        )
        self.voice_button.grid(row=0, column=2, padx=4)

        ctk.CTkButton(
            bottom, text="TEMİZLE", width=64, height=44,
            fg_color="#090B0D", hover_color="#15181C",
            border_width=1, border_color="#34383D",
            text_color=MUTED, command=self._clear_chat
        ).grid(row=0, column=3, padx=(4, 0))

        ctk.CTkButton(
            bottom, text="GÖRSEL", width=68, height=44,
            fg_color="#090B0D", hover_color="#15181C",
            border_width=1, border_color=GOLD, text_color=GOLD,
            font=("Consolas", 9, "bold"), command=self._on_image_clicked
        ).grid(row=0, column=4, padx=4)

        ctk.CTkButton(
            bottom, text="PDF EKLE", width=78, height=44,
            fg_color="#090B0D", hover_color="#15181C",
            border_width=1, border_color=GOLD, text_color=GOLD,
            font=("Consolas", 9, "bold"), command=self._on_pdf_clicked
        ).grid(row=0, column=5, padx=4)

        ctk.CTkButton(
            bottom, text="YAPAY ZEKÂ AYARLARI", width=82, height=44,
            fg_color="#090B0D", hover_color="#15181C",
            border_width=1, border_color=GOLD, text_color=GOLD,
            font=("Consolas", 9, "bold"), command=self._open_ai_settings
        ).grid(row=0, column=6, padx=4)

        ctk.CTkButton(
            bottom, text="ANDROID BAĞLANTISI", width=82, height=44,
            fg_color="#090B0D", hover_color="#15181C",
            border_width=1, border_color=GOLD, text_color=GOLD,
            font=("Consolas", 9, "bold"), command=self._open_android_link
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
        brain = self.jarvis.command_processor.ai_brain
        self._activity("AI CORE: " + brain.provider.upper() + " (GEMINI / OLLAMA)")
        self._activity("LOCAL CORE: OLLAMA " + brain.model)

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
        value_label = ctk.CTkLabel(
            row, text=value, text_color=color, font=("Consolas", 9, "bold")
        )
        value_label.pack(side="right")
        return value_label

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
            cx, cy + base*.58, text="SİSTEM ÇEKİRDEĞİ // ÇEVRİMİÇİ",
            fill=MUTED, font=("Consolas", 8)
        )

        self.hud.create_text(
            38, 34, text="STAGEPULSE / YAPAY ZEKÂ KONTROLÜ",
            fill=GOLD2, anchor="w", font=("Consolas", 8)
        )
        self.hud.create_text(
            38, h-34, text="SES // YAPAY ZEKÂ // SİSTEM // AĞ",
            fill=MUTED, anchor="w", font=("Consolas", 8)
        )
        self.hud.create_text(
            w-38, 34, text="GÜVENLİ BAĞLANTI",
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


    def _image_prompt_from_command(self, command):
        import re
        prompt = re.sub(
            r"(?i)(?:görsel|resim|fotoğraf)\\s+(?:oluştur|üret)|(?:create|generate)\\s+(?:an?\\s+)?image",
            "", command
        ).strip(" \\t:,-")
        return prompt or command.strip()

    def _is_image_generation_request(self, command):
        import re
        return bool(re.search(
            r"(?i)(?:görsel|resim|fotoğraf)\\s+(?:oluştur|üret)|(?:create|generate)\\s+(?:an?\\s+)?image",
            command
        ))

    def _run_ai_task(self, title, task, should_speak=False):
        self.task.configure(text=title)
        self.phase.configure(text="İŞLENİYOR")
        self.status.configure(text="● GEMINI", text_color=GOLD)
        self._activity(title.upper())

        def worker():
            try:
                result = str(task())
                success = True
            except Exception as exc:
                result = "İşlem tamamlanamadı: " + str(exc)
                success = False

            def finish():
                self._append_to_chat("JARVIS", result, "green" if success else "red")
                self.task.configure(text="Hazır")
                self.phase.configure(text="HAZIR")
                self.status.configure(text="● ÇEVRİMİÇİ" if success else "● HATA",
                                      text_color=GREEN if success else RED)
                self._activity(("OK  " if success else "ERR ") + result.replace("\\n", " ")[:70])
                if should_speak and success and self.voice_var.get():
                    speak_text = "Görsel oluşturuldu ve kaydedildi." if result.lower().endswith((".png", ".jpg", ".jpeg", ".webp")) else result
                    threading.Thread(target=lambda: self.jarvis.speak(speak_text, wait=False), daemon=True).start()

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True, name="JARVIS-AI-Task").start()

    def _toggle_fullscreen(self, event=None):
        current = bool(self.root.attributes("-fullscreen"))
        self.root.attributes("-fullscreen", not current)
        return "break"

    def _leave_fullscreen(self, event=None):
        self.root.attributes("-fullscreen", False)
        return "break"

    def _on_pdf_clicked(self):
        path = filedialog.askopenfilename(
            parent=self.root, title="JARVIS'a PDF ekle",
            filetypes=[("PDF dosyaları", "*.pdf"), ("Tüm dosyalar", "*.*")]
        )
        if not path:
            return
        try:
            from pypdf import PdfReader
            reader = PdfReader(path)
            pages = []
            total_chars = 0
            for page in reader.pages:
                text = (page.extract_text() or "").strip()
                if text:
                    remaining = 30000 - total_chars
                    if remaining <= 0:
                        break
                    text = text[:remaining]
                    pages.append(text)
                    total_chars += len(text)
            extracted = "\\n\\n".join(pages).strip()
            if not extracted:
                messagebox.showwarning(
                    "PDF metni bulunamadı",
                    "Bu PDF metin içermiyor veya taranmış görüntülerden oluşuyor. OCR desteği olmadan içeriği okunamıyor.",
                    parent=self.root
                )
                return
            self._pdf_path = path
            self._pdf_text = extracted
            self._append_to_chat("SYSTEM", "PDF yüklendi: " + path, "green")
            self._activity("PDF LOADED: " + path.split("/")[-1][-48:])
            dialog = ctk.CTkInputDialog(
                title="PDF hakkında soru sor",
                text="PDF yüklendi. Ne yapayım? Örn. özetle, önemli maddeleri çıkar, SPL ölçüm adımlarını açıkla."
            )
            question = dialog.get_input()
            if question and question.strip():
                self._append_to_chat("YOU", "PDF: " + question.strip(), "gold")
                brain = self.jarvis.command_processor.ai_brain
                prompt = (
                    "Aşağıdaki metin kullanıcının yüklediği PDF'den çıkarılmıştır. "
                    "Yalnızca bu metne dayalı cevap ver; metinde olmayan bilgiyi uydurma. "
                    "Türkçe yanıtla. Gerekiyorsa kaynak sayfa metinde belirtilmediğini söyle.\\n\\n"
                    "PDF DOSYASI: " + path + "\\n\\nPDF İÇERİĞİ:\\n" +
                    self._pdf_text + "\\n\\nKULLANICI İSTEĞİ: " + question.strip()
                )
                self._run_ai_task("PDF analiz ediliyor", lambda: brain.ask(prompt), should_speak=True)
        except ImportError:
            messagebox.showerror(
                "PDF desteği eksik",
                "PDF okumak için pypdf paketi kurulu değil. JARVIS bağımlılıkları güncellenmeli.",
                parent=self.root
            )
        except Exception as exc:
            messagebox.showerror("PDF açılamadı", str(exc), parent=self.root)

    def _on_image_clicked(self):
        brain = self.jarvis.command_processor.ai_brain
        if not brain.gemini_key:
            messagebox.showwarning("Gemini ayarı gerekli", "Önce Yapay Zekâ Ayarları bölümünden Gemini API anahtarını ekleyin.", parent=self.root)
            return
        path = filedialog.askopenfilename(
            parent=self.root, title="Analiz edilecek görseli seç",
            filetypes=[("Görseller", "*.png *.jpg *.jpeg *.webp *.bmp"), ("Tüm dosyalar", "*.*")]
        )
        if not path:
            return
        dialog = ctk.CTkInputDialog(title="Gemini görsel analizi", text="Görsel hakkında ne analiz edilsin?")
        prompt = dialog.get_input()
        if prompt is None:
            return
        self._append_to_chat("YOU", "Görsel analizi: " + path, "gold")
        self._run_ai_task("Görsel analiz ediliyor", lambda: brain.analyze_image(prompt.strip(), path), should_speak=True)

    def _open_ai_settings(self):
        brain = self.jarvis.command_processor.ai_brain
        win = ctk.CTkToplevel(self.root)
        win.title("STAGEPULSE // AI SETTINGS")
        win.geometry("540x770")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        ctk.CTkLabel(win, text="YAPAY ZEKÂ SAĞLAYICISI", text_color=GOLD,
                     font=("Consolas", 12, "bold")).pack(anchor="w", padx=22, pady=(20, 6))
        provider = ctk.StringVar(value=brain.provider)
        ctk.CTkOptionMenu(win, variable=provider, values=["auto", "gemini", "groq", "ollama"],
                          width=490).pack(padx=22, pady=(0, 10))

        def field(label, value, secret=False):
            ctk.CTkLabel(win, text=label, text_color=WHITE,
                         font=("Consolas", 10)).pack(anchor="w", padx=22, pady=(8, 3))
            entry = ctk.CTkEntry(win, width=490, show="*" if secret else "")
            entry.pack(padx=22)
            entry.insert(0, value or "")
            return entry

        api_key = field("GEMINI API ANAHTARI", brain.gemini_key, secret=True)
        groq_key = field("GROQ API ANAHTARI", brain.groq_key, secret=True)
        text_model = field("GEMINI METİN / GÖRSEL MODELİ", brain.gemini_model)
        image_model = field("GEMINI GÖRSEL MODELİ", brain.gemini_image_model)
        ollama_host = field("OLLAMA ADRESİ", brain.host)
        ollama_model = field("OLLAMA MODELİ", brain.model)

        ctk.CTkLabel(
            win, text="OTOMATİK MOD: normal sohbette hızlı Groq; web araştırmasında Gemini Google araması ve URL bağlamı kullanılır. Hata olursa diğer sağlayıcılar denenir. Gemini ve Groq ayrı API anahtarı ister. Anahtarlar desteklenen Windows sistemlerinde DPAPI ile korunur.",
            text_color=MUTED, font=("Consolas", 9), wraplength=490, justify="left"
        ).pack(anchor="w", padx=22, pady=(12, 6))

        def test_backend(provider_name):
            try:
                brain.configure(
                    provider=provider.get(),
                    gemini_key=api_key.get(),
                    groq_key=groq_key.get(),
                    gemini_model=text_model.get(),
                    gemini_image_model=image_model.get(),
                    ollama_host=ollama_host.get(),
                    ollama_model=ollama_model.get(),
                )
            except Exception as exc:
                messagebox.showerror("AI ayarı", str(exc), parent=win)
                return

            self._append_to_chat("SYSTEM", provider_name.upper() + " bağlantısı test ediliyor...", "yellow")
            def worker():
                result = (brain.test_web_provider(provider_name) if provider_name in ("gemini", "groq") else brain.test_provider(provider_name))
                def show_result():
                    message = result.get("message", "Test tamamlandı.")
                    if result.get("success"):
                        messagebox.showinfo(provider_name.upper() + " bağlantı testi", message, parent=win)
                    else:
                        messagebox.showerror(provider_name.upper() + " bağlantı testi", message, parent=win)
                    self._append_to_chat(
                        "SYSTEM", message,
                        "green" if result.get("success") else "red"
                    )
                try:
                    self.root.after(0, show_result)
                except Exception:
                    pass
            threading.Thread(
                target=worker, daemon=True,
                name="JARVIS-AI-Test-" + provider_name
            ).start()

        def save():
            try:
                brain.configure(
                    provider=provider.get(),
                    gemini_key=api_key.get(),
                    groq_key=groq_key.get(),
                    gemini_model=text_model.get(),
                    gemini_image_model=image_model.get(),
                    ollama_host=ollama_host.get(),
                    ollama_model=ollama_model.get(),
                )
                self.ai_core_value.configure(text=brain.provider.upper())
                self.local_core_value.configure(text="OLLAMA " + brain.model)
                self._activity("AI PROVIDER SAVED: " + brain.provider.upper())
                self._append_to_chat("JARVIS", "AI ayarları kaydedildi. Sağlayıcı: " + brain.provider.upper(), "green")
                win.destroy()
            except Exception as exc:
                messagebox.showerror("Ayarlar kaydedilemedi", str(exc), parent=win)

        ctk.CTkButton(
            win, text="GEMINI WEB ARAMASINI SINA",
            command=lambda: test_backend("gemini"),
            fg_color="#090B0D", hover_color="#15181C",
            border_width=1, border_color=GOLD2, text_color=GOLD,
            font=("Consolas", 10, "bold")
        ).pack(fill="x", padx=22, pady=(8, 4))
        ctk.CTkButton(
            win, text="GROQ WEB ARAMASINI SINA",
            command=lambda: test_backend("groq"),
            fg_color="#090B0D", hover_color="#15181C",
            border_width=1, border_color=GOLD2, text_color=GOLD,
            font=("Consolas", 10, "bold")
        ).pack(fill="x", padx=22, pady=(0, 4))
        ctk.CTkButton(
            win, text="OLLAMA BAĞLANTISINI SINA",
            command=lambda: test_backend("ollama"),
            fg_color="#090B0D", hover_color="#15181C",
            border_width=1, border_color=GOLD2, text_color=GOLD,
            font=("Consolas", 10, "bold")
        ).pack(fill="x", padx=22, pady=(0, 4))

        ctk.CTkButton(win, text="AYARLARI KAYDET", command=save,
                      fg_color=GOLD2, hover_color=GOLD, text_color="#050505",
                      font=("Consolas", 10, "bold")).pack(fill="x", padx=22, pady=(8, 18))

    def _open_android_link(self):
        try:
            import socket
            import android_bridge
            android_bridge.start_in_background()
            ip = ""
            try:
                probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                probe.connect(("8.8.8.8", 80))
                ip = probe.getsockname()[0]
                probe.close()
            except OSError:
                for candidate in socket.gethostbyname_ex(socket.gethostname())[2]:
                    if not candidate.startswith("127.") and ":" not in candidate:
                        ip = candidate
                        break
            if not ip:
                ip = "WINDOWS-LAN-IP"
            url = "http://" + ip + ":8765"
            token = android_bridge.TOKEN

            win = ctk.CTkToplevel(self.root)
            win.title("STAGEPULSE // ANDROID LINK")
            win.geometry("620x360")
            win.resizable(False, False)
            win.transient(self.root)
            win.grab_set()
            ctk.CTkLabel(win, text="ANDROID UYGULAMA BAĞLANTISI", text_color=GOLD,
                         font=("Consolas", 15, "bold")).pack(anchor="w", padx=22, pady=(20, 5))
            ctk.CTkLabel(win, text="Android uygulamasında HOST bölümüne aşağıdaki adresi ve token'ı gir.",
                         text_color=WHITE, wraplength=570, justify="left").pack(anchor="w", padx=22, pady=(0, 14))

            def entry_row(label, value):
                ctk.CTkLabel(win, text=label, text_color=MUTED,
                             font=("Consolas", 9, "bold")).pack(anchor="w", padx=22, pady=(5, 3))
                row = ctk.CTkFrame(win, fg_color="transparent")
                row.pack(fill="x", padx=22)
                entry = ctk.CTkEntry(row, height=34)
                entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
                entry.insert(0, value)
                entry.configure(state="readonly")
                def copy_value(v=value):
                    self.root.clipboard_clear()
                    self.root.clipboard_append(v)
                    self.root.update()
                    self._activity("ANDROID LINK VALUE COPIED")
                ctk.CTkButton(row, text="KOPYALA", width=75, height=34,
                              fg_color=GOLD2, hover_color=GOLD, text_color="#050505",
                              command=copy_value).pack(side="right")
            entry_row("WINDOWS SUNUCU ADRESİ", url)
            entry_row("KİMLİK DOĞRULAMA ANAHTARI", token)
            ctk.CTkLabel(
                win, text="Güvenlik: Bu bağlantıyı internete açma. Yalnızca güvendiğin aynı yerel ağda kullan.",
                text_color=RED, wraplength=570, justify="left"
            ).pack(anchor="w", padx=22, pady=(12, 6))
        except Exception as exc:
            messagebox.showerror("Android bağlantısı başlatılamadı", str(exc), parent=self.root)

    def _on_send_clicked(self):
        command = self.command_entry.get().strip()
        if not command:
            return
        self.command_entry.delete(0, "end")
        self._append_to_chat("YOU", command, "gold")
        self.task.configure(text=command[:90])
        self.phase.configure(text="İŞLENİYOR")
        self.status.configure(text="● İŞLENİYOR", text_color=GOLD)
        self._activity("CMD > " + command[:46])
        if self._is_image_generation_request(command):
            brain = self.jarvis.command_processor.ai_brain
            prompt = self._image_prompt_from_command(command)
            self._run_ai_task("Gemini görsel üretiyor", lambda: brain.generate_image(prompt), should_speak=True)
        elif self._pdf_text and any(term in command.lower() for term in (
            "pdf", "belge", "belgede", "dosyada", "bu metin", "özetle", "özet",
            "içeriği", "ne anlatıyor", "önemli maddeler", "bu doküman", "bu dokuman"
        )):
            brain = self.jarvis.command_processor.ai_brain
            prompt = (
                "Kullanıcının yüklediği PDF metni aşağıdadır. Soruyu bu metne dayanarak Türkçe yanıtla. "
                "Metinde olmayan ayrıntıları uydurma.\\n\\nPDF: " + str(self._pdf_path) +
                "\\n\\nİÇERİK:\\n" + self._pdf_text +
                "\\n\\nSORU: " + command
            )
            self._run_ai_task("Yüklü PDF hakkında yanıt hazırlanıyor", lambda: brain.ask(prompt), should_speak=True)
        else:
            self.jarvis.process_command(
                command, speak_response=self.voice_var.get()
            )

    def _on_voice_clicked(self):
        if self._voice_busy:
            return
        self._voice_busy = True
        self.voice_button.configure(
            text="◉ DİNLİYOR", fg_color="#38240A", text_color=GOLD
        )
        self.phase.configure(text="DİNLİYOR")
        self.status.configure(text="● DİNLİYOR", text_color=GOLD)
        self._activity("SESLİ GİRİŞ ETKİN")

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
            text="◉ SESLİ KOMUT", fg_color="#0A0D10", text_color=GOLD
        )
        self.phase.configure(text="HAZIR")
        self.status.configure(text="● ÇEVRİMİÇİ", text_color=GREEN)

    def _on_command(self, command):
        pass

    def _on_response(self, result):
        response = result.get("response", "")
        success = result.get("success", False)
        self._append_to_chat(
            "JARVIS", response, "green" if success else "red"
        )
        self.task.configure(text="Hazır")
        self.phase.configure(text="HAZIR")
        self.status.configure(
            text="● ÇEVRİMİÇİ" if success else "● HATA",
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
        # The old right-side activity feed was removed from the interface.
        # Keep internal diagnostics in the log instead of showing chat or responses here.
        logger.debug("JARVIS activity: %s", text)

    def _toggle_wake_word(self):
        enabled = bool(self.wake_word_var.get())
        if enabled:
            started = self.jarvis.start_wake_word_detection()
            if started:
                config.set("voice.wake_word_enabled", True)
                self._activity("WAKE WORD ENABLED (INTERNET REQUIRED FOR FALLBACK)")
            else:
                self.wake_word_var.set(False)
                config.set("voice.wake_word_enabled", False)
                self._append_to_chat(
                    "SYSTEM",
                    "Wake word başlatılamadı. Voice ayarını, mikrofonu ve internet bağlantısını kontrol edin.",
                    "red"
                )
                self._activity("WAKE WORD START FAILED")
        else:
            detector = getattr(self.jarvis, "wake_word_detector", None)
            if detector:
                try:
                    detector.stop()
                except Exception as exc:
                    logger.warning("Wake word stop failed: %s", exc)
            self.jarvis.wake_word_enabled = False
            config.set("voice.wake_word_enabled", False)
            self._activity("WAKE WORD DISABLED")

    def _on_tts_voice_changed(self, label):
        voice_id = self.tts_voice_choices.get(label)
        if not voice_id:
            return
        try:
            if self.jarvis.set_voice(voice_id):
                self._activity("TTS VOICE SELECTED: " + label)
                self._append_to_chat("SYSTEM", "Konuşma sesi seçildi: " + label, "green")
            else:
                self._append_to_chat(
                    "SYSTEM", "Ses seçilemedi. TTS bağımlılıklarını ve ayarları kontrol edin.",
                    "red"
                )
        except Exception as exc:
            self._append_to_chat("SYSTEM", "TTS ayarı hatası: " + str(exc), "red")

    def _test_microphone(self):
        self._activity("MİKROFON TESTİ")
        def worker():
            try:
                result = self.jarvis.test_microphone()
            except Exception as exc:
                result = {"success": False, "message": "Mikrofon testi hatası: " + str(exc)}
            def show_result():
                message = result.get("message", "Mikrofon testi tamamlandı.")
                self._append_to_chat(
                    "SYSTEM", message,
                    "green" if result.get("success") else "red"
                )
                self._activity("MIC TEST: " + message[:60])
                if result.get("success"):
                    messagebox.showinfo("Mikrofon testi", message, parent=self.root)
                else:
                    messagebox.showerror("Mikrofon testi", message, parent=self.root)
            try:
                self.root.after(0, show_result)
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True, name="JARVIS-Mic-Test").start()

    def _test_tts_voice(self):
        self._activity("KONUŞMA SESİ TESTİ")
        def worker():
            result = self.jarvis.speak(
                "Merhaba Patron. Türkçe ses testi. JARVIS konuşma sistemi hazır.",
                wait=True
            )
            if not result:
                try:
                    self.root.after(
                        0, lambda: self._append_to_chat(
                            "SYSTEM", "Ses testi başarısız. İnternet veya yerel TTS modelini kontrol edin.",
                            "red"
                        )
                    )
                except Exception:
                    pass
        threading.Thread(target=worker, daemon=True, name="JARVIS-TTS-Test").start()

    def _toggle_voice(self):
        enabled = self.voice_var.get()
        config.set("voice.enabled", enabled, save=False)
        self._activity("SESLİ KONTROL " + ("ETKİN" if enabled else "DEVRE DIŞI"))

    def _clear_chat(self):
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        self.chat_display.configure(state="disabled")
        self._activity("YAZIŞMA TEMİZLENDİ")

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.root.mainloop()

    def _on_closing(self):
        self._running = False
        self._voice_stop_event.set()
        self._voice_response_event.set()
        self.jarvis.stop()
        self.root.destroy()

# === JARVIS THREAD SAFE GUI PATCH ===
def _jarvis_gui_response(self, result):
    if getattr(self, "_voice_listening", False):
        self._voice_last_response = result
        self._voice_response_event.set()
    try:
        self.root.after(0, lambda r=result: self._render_response_safe(r))
    except Exception:
        pass

def _jarvis_gui_command(self, command):
    # Command callbacks run on worker threads; all Tk updates must go via after().
    try:
        self.root.after(0, lambda c=str(command): self._append_to_chat("YOU", c, "gold"))
    except Exception:
        pass

def _render_response_safe(self, result):
    response = result.get("response", "")
    success = result.get("success", False)
    self._append_to_chat("JARVIS", response, "green" if success else "red")

    if hasattr(self, "task"):
        self.task.configure(text="Hazır")
    if hasattr(self, "phase"):
        self.phase.configure(text="HAZIR")
    if hasattr(self, "status"):
        self.status.configure(
            text="● ÇEVRİMİÇİ" if success else "● HATA",
            text_color=GREEN if success else RED
        )
    if hasattr(self, "_activity"):
        self._activity(
            ("OK  " if success else "ERR ") +
            response.replace("\\n", " ")[:55]
        )

def _jarvis_gui_voice(self):
    # Persistent voice loop. The mic is reopened for every capture and each state
    # transition is visible, so a stalled recognizer cannot masquerade as listening.
    if getattr(self, "_voice_listening", False):
        return
    if not self.voice_var.get():
        self._append_to_chat("SYSTEM", "Önce Voice anahtarını açın.", "yellow")
        return
    recognizer = getattr(self.jarvis, "speech_recognizer", None)
    if recognizer is None:
        self._append_to_chat("SYSTEM", "Ses tanıma başlatılmadı: SpeechRecognizer yok.", "red")
        return
    if getattr(recognizer, "microphone", None) is None:
        detail = getattr(recognizer, "microphone_error", None) or "Windows kullanılabilir mikrofon bulamadı."
        self._append_to_chat("SYSTEM", "Sürekli dinleme başlatılamadı: " + str(detail), "red")
        self._activity("MICROPHONE UNAVAILABLE")
        self.status.configure(text="● MİKROFON HATASI", text_color=RED)
        self.phase.configure(text="MİKROFON HATASI")
        return

    self._voice_listening = True
    self._voice_busy = True
    self._voice_stop_event.clear()
    self.voice_button.configure(text="◉ SÜREKLİ DİNLİYOR", fg_color="#38240A", text_color=GOLD)
    self.phase.configure(text="DİNLİYOR")
    self.status.configure(text="● DİNLİYOR", text_color=GOLD)
    self._activity("SÜREKLİ SESLİ KONTROL BAŞLADI")

    def ui_state(phase, status, activity):
        try:
            self.root.after(0, lambda: self._set_voice_state(phase, status, activity))
        except Exception:
            pass

    def worker():
        try:
            while not self._voice_stop_event.is_set() and self._running:
                ui_state("LISTENING", "● LISTENING", "KONUŞMA BEKLENİYOR")
                try:
                    result = recognizer.listen(timeout=5, phrase_time_limit=8)
                except Exception as exc:
                    if self._voice_stop_event.is_set() or not self._running:
                        break
                    message = "Mikrofon / ses tanıma hatası: " + str(exc)
                    self.root.after(0, lambda m=message: self._voice_input_error(m))
                    self._voice_stop_event.wait(1.0)
                    continue

                if self._voice_stop_event.is_set() or not self._running:
                    break
                if not isinstance(result, dict) or not result.get("success"):
                    error = str((result or {}).get("error", "unknown"))
                    message = str((result or {}).get("message") or error)
                    if error not in ("timeout", "no_recognition"):
                        self.root.after(0, lambda m=message: self._voice_input_error(m))
                        self._voice_stop_event.wait(1.0)
                    continue

                command = str(result.get("text", "")).strip()
                if not command:
                    continue
                self.root.after(0, lambda c=command: self._voice_command_heard(c))
                if command.lower().strip(" .,!?:;") in ("jarvis kapat", "uygulamayı kapat", "uygulamayi kapat"):
                    self.root.after(0, self._on_closing)
                    break

                # Stop capturing while the command runs, then resume explicitly.
                ui_state("PROCESSING", "● PROCESSING", "KOMUT ALGILANDI")
                self._voice_response_event.clear()
                self._voice_last_response = None
                queued = self.jarvis.process_command(command, speak_response=False)
                if isinstance(queued, dict) and queued.get("success") is False:
                    self.root.after(0, lambda q=queued: self._append_to_chat(
                        "SYSTEM", str(q.get("response", "Komut işlenemedi.")), "red"
                    ))
                    continue

                completed = self._voice_response_event.wait(timeout=180)
                if self._voice_stop_event.is_set() or not self._running:
                    break
                if not completed:
                    self.root.after(0, lambda: self._append_to_chat(
                        "SYSTEM", "Komut yanıtı 180 saniyede gelmedi. Yeniden dinlemeye geçiyorum.", "yellow"
                    ))
                    continue

                response = self._voice_last_response or {}
                spoken = str(response.get("response", "")).strip()
                if spoken and self.voice_var.get():
                    ui_state("SPEAKING", "● SPEAKING", "YANIT SESLENDİRİLİYOR")
                    try:
                        self.jarvis.speak(spoken, wait=True)
                    except Exception as exc:
                        self.root.after(0, lambda e=exc: self._append_to_chat(
                            "SYSTEM", "Sesli yanıt hatası: " + str(e), "red"
                        ))

                # Make the return to microphone capture explicit after every answer.
                self._voice_stop_event.wait(0.35)
                if not self._voice_stop_event.is_set() and self._running:
                    ui_state("LISTENING", "● LISTENING", "YENİ KOMUT BEKLENİYOR")
        except Exception as exc:
            if not self._voice_stop_event.is_set():
                self.root.after(0, lambda e=exc: self._append_to_chat(
                    "SYSTEM", "Sürekli ses döngüsü durdu: " + str(e), "red"
                ))
        finally:
            self._voice_listening = False
            self._voice_busy = False
            try:
                self.root.after(0, self._voice_finished_safe)
            except Exception:
                pass

    threading.Thread(target=worker, daemon=True, name="JARVIS-Persistent-Voice").start()

def _set_voice_state(self, phase, status, activity):
    if not self._running:
        return
    self.phase.configure(text=phase)
    self.status.configure(
        text=status,
        text_color=GOLD if phase in ("DİNLİYOR", "KONUŞUYOR", "İŞLENİYOR") else GREEN
    )
    self._activity(activity)


def _voice_input_error(self, message):
    self._append_to_chat("SYSTEM", "Ses girişi hatası: " + str(message), "red")
    self._activity("SES GİRİŞ HATASI: " + str(message).replace("\\n", " ")[:70])
    self.status.configure(text="● SES HATASI", text_color=RED)
    self.phase.configure(text="SES HATASI")

def _voice_command_heard(self, command):
    self._append_to_chat("YOU", command, "gold")
    self._activity("VOICE COMMAND HEARD")

def _voice_result_safe(self, result):
    if isinstance(result, dict) and result.get("success"):
        recognized = result.get("text")
        if recognized:
            self._append_to_chat("YOU", recognized, "gold")
        if result.get("async") or result.get("intent") == "processing":
            self._activity("VOICE COMMAND QUEUED")
        else:
            self._activity("VOICE INPUT COMPLETE")
    else:
        if isinstance(result, dict):
            msg = result.get("message") or result.get("response") or result.get("error") or "Ses anlaşılamadı."
        else:
            msg = "Ses anlaşılamadı."
        if msg == "timeout" or (isinstance(result, dict) and result.get("error") == "timeout"):
            msg = "Ses algılanmadı. Mikrofonu ve giriş seviyesini kontrol edin."
        self._append_to_chat("SYSTEM", str(msg), "yellow")
        self._activity("VOICE ERROR: " + str(msg)[:50])
    self._voice_finished_safe()

def _voice_error_safe(self, error):
    self._append_to_chat("SYSTEM", "Ses hatası: " + str(error), "red")
    self._activity("SES HATASI")
    self._voice_finished()

def _voice_finished_safe(self):
    self._voice_busy = False
    try:
        self.voice_button.configure(
            text="◉ SESLİ KOMUT",
            fg_color="#0A0D10",
            text_color=GOLD
        )
        self.phase.configure(text="HAZIR")
        self.status.configure(text="● ÇEVRİMİÇİ", text_color=GREEN)
    except Exception:
        pass

JarvisGUI._render_response_safe = _render_response_safe
JarvisGUI._on_response = _jarvis_gui_response
JarvisGUI._on_command = _jarvis_gui_command
JarvisGUI._on_voice_clicked = _jarvis_gui_voice
JarvisGUI._voice_finished = _voice_finished_safe
