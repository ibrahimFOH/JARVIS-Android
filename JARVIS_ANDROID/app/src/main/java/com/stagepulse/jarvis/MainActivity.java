package com.stagepulse.jarvis;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.PendingIntent;
import android.content.*;
import android.content.pm.PackageManager;
import android.content.pm.PackageInstaller;
import android.os.*;
import android.provider.Settings;
import android.net.Uri;
import android.media.AudioManager;
import android.speech.*;
import android.speech.tts.TextToSpeech;
import android.view.Gravity;
import android.widget.*;
import java.text.SimpleDateFormat;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.*;
import java.util.concurrent.*;

public class MainActivity extends Activity {
    private static final int REQ_AUDIO=9001;
    private final ExecutorService io=Executors.newSingleThreadExecutor();
    private EditText command;
    private TextView status,chat,voiceControl;
    private ScrollView chatScroll;
    private HudView hud;
    private SpeechRecognizer speech;
    private TextToSpeech androidTts;
    private volatile boolean androidTtsReady = false;
    private volatile boolean speechRecognitionBusy = false;
    private AgencyAgent activeAgent;
    private android.content.SharedPreferences bridgePrefs;
    private android.content.SharedPreferences updatePrefs;
    private final UpdateManager updateManager = new UpdateManager();
    private File pendingUpdateFile;
    private String pendingUpdateVersion = "";
    private boolean updateInstallInProgress = false;

    private int gold(){return 0xFFD4AF37;}
    private int white(){return 0xFFF2F2F2;}
    private int muted(){return 0xFF8C8C8C;}
    private int panel(){return 0xFF0B0B0B;}

    @Override public void onCreate(Bundle b){
        super.onCreate(b);
        bridgePrefs = getSharedPreferences("jarvis_bridge", MODE_PRIVATE);
        updatePrefs = getSharedPreferences("jarvis_updates", MODE_PRIVATE);
        String pendingPath = updatePrefs.getString("pending_apk", "");
        if (!pendingPath.isEmpty()) {
            File candidate = new File(pendingPath);
            if (candidate.isFile()) pendingUpdateFile = candidate;
        }
        buildUi();
        initAndroidTts();
        initSpeech();
        append("JARVIS","PATRON, bağımsız Android çekirdeği hazır.");
        checkForUpdates(false);
    }

    private TextView tv(String s,int size,int color){
        TextView v=new TextView(this); v.setText(s); v.setTextSize(size); v.setTextColor(color); return v;
    }

    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private TextView control(String label, int backgroundColor, int foregroundColor, float textSize) {
        TextView view = tv(label, (int) textSize, foregroundColor);
        view.setGravity(Gravity.CENTER);
        view.setTypeface(null, 1);
        view.setPadding(dp(6), dp(4), dp(6), dp(4));
        view.setMinHeight(dp(40));
        android.graphics.drawable.GradientDrawable shape = new android.graphics.drawable.GradientDrawable();
        shape.setColor(backgroundColor);
        shape.setCornerRadius(dp(7));
        view.setBackground(shape);
        view.setClickable(true);
        view.setFocusable(true);
        view.setIncludeFontPadding(true);
        return view;
    }

    private void updateVoiceControl(boolean listening) {
        if (voiceControl != null) {
            voiceControl.setText(listening ? "DURDUR" : "KONUŞ");
            voiceControl.setContentDescription(listening
                    ? "Sesli komutu durdur" : "Türkçe sesli komut başlat");
        }
    }

    private void buildUi(){
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(12), dp(6), dp(12), dp(6));
        root.setBackgroundColor(0xFF050505);
        root.setFocusableInTouchMode(true);

        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.VERTICAL);
        TextView title = tv("J.A.R.V.I.S.", 26, gold());
        title.setTypeface(null, 1);
        header.addView(title, new LinearLayout.LayoutParams(-1, -2));
        header.addView(tv("STAGEPULSE  //  PERSONAL AI SYSTEM", 10, muted()),
                new LinearLayout.LayoutParams(-1, -2));
        status = tv("● STARTING LOCAL CORE", 12, gold());
        status.setTypeface(null, 1);
        LinearLayout.LayoutParams statusLp = new LinearLayout.LayoutParams(-1, -2);
        statusLp.topMargin = dp(3);
        header.addView(status, statusLp);
        root.addView(header, new LinearLayout.LayoutParams(-1, -2));

        hud = new HudView(this);
        LinearLayout.LayoutParams hudLp = new LinearLayout.LayoutParams(-1, dp(60));
        hudLp.topMargin = dp(2);
        root.addView(hud, hudLp);

        TextView systemLine = tv("LOCAL COMMANDS READY  •  WINDOWS LINK OPTIONAL", 10, muted());
        systemLine.setSingleLine(true);
        systemLine.setEllipsize(android.text.TextUtils.TruncateAt.END);
        systemLine.setGravity(Gravity.CENTER_VERTICAL);
        systemLine.setPadding(dp(2), 0, dp(2), 0);
        root.addView(systemLine, new LinearLayout.LayoutParams(-1, dp(24)));

        chat = tv("JARVIS  //  SESSION\n\nBağımsız Android çekirdeği başlatılıyor.\nWindows bağlantısı isteğe bağlıdır.", 14, white());
        chat.setGravity(Gravity.TOP | Gravity.START);
        chat.setPadding(dp(10), dp(10), dp(10), dp(10));
        chat.setBackgroundColor(panel());
        chat.setTextIsSelectable(true);
        chatScroll = new ScrollView(this);
        chatScroll.setFillViewport(true);
        chatScroll.setVerticalScrollBarEnabled(true);
        chatScroll.addView(chat, new ScrollView.LayoutParams(-1, -2));
        LinearLayout.LayoutParams chatLp = new LinearLayout.LayoutParams(-1, 0, 1f);
        chatLp.topMargin = dp(2);
        chatLp.bottomMargin = dp(5);
        root.addView(chatScroll, chatLp);

        LinearLayout commandBar = new LinearLayout(this);
        commandBar.setOrientation(LinearLayout.HORIZONTAL);
        commandBar.setGravity(Gravity.CENTER_VERTICAL);
        commandBar.setBaselineAligned(false);

        command = new EditText(this);
        command.setHint("Komutunu yaz...");
        command.setHintTextColor(muted());
        command.setTextColor(white());
        command.setTextSize(15);
        command.setSingleLine(true);
        command.setMaxLines(1);
        command.setImeOptions(android.view.inputmethod.EditorInfo.IME_ACTION_SEND);
        command.setInputType(android.text.InputType.TYPE_CLASS_TEXT
                | android.text.InputType.TYPE_TEXT_FLAG_AUTO_CORRECT);
        command.setBackgroundColor(panel());
        command.setPadding(dp(10), dp(5), dp(8), dp(5));
        command.setSelectAllOnFocus(false);
        LinearLayout.LayoutParams inputLp = new LinearLayout.LayoutParams(0, dp(48), 1f);
        inputLp.rightMargin = dp(5);
        commandBar.addView(command, inputLp);

        TextView send = control("GÖNDER", gold(), 0xFF080808, 13);
        send.setContentDescription("Yazılan komutu gönder");
        LinearLayout.LayoutParams sendLp = new LinearLayout.LayoutParams(dp(78), dp(48));
        sendLp.rightMargin = dp(5);
        commandBar.addView(send, sendLp);

        voiceControl = control("KONUŞ", 0xFF242014, gold(), 13);
        voiceControl.setContentDescription("Türkçe sesli komut başlat");
        commandBar.addView(voiceControl, new LinearLayout.LayoutParams(dp(78), dp(48)));

        LinearLayout.LayoutParams commandBarLp = new LinearLayout.LayoutParams(-1, dp(48));
        commandBarLp.bottomMargin = dp(5);
        root.addView(commandBar, commandBarLp);

        LinearLayout secondary = new LinearLayout(this);
        secondary.setOrientation(LinearLayout.HORIZONTAL);
        secondary.setGravity(Gravity.CENTER_VERTICAL);
        TextView agents = control("UZMANLAR", panel(), gold(), 9);
        TextView host = control("PC BAĞLANTI", panel(), gold(), 9);
        TextView update = control("GÜNCELLE", panel(), gold(), 9);
        TextView help = control("YARDIM", panel(), gold(), 9);
        TextView[] tools = {agents, host, update, help};
        for (int index = 0; index < tools.length; index++) {
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, dp(38), 1f);
            if (index > 0) lp.leftMargin = dp(4);
            secondary.addView(tools[index], lp);
        }
        root.addView(secondary, new LinearLayout.LayoutParams(-1, dp(38)));

        setContentView(root);
        getWindow().setSoftInputMode(
                android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);

        send.setOnClickListener(v -> sendCommand(command.getText().toString()));
        command.setOnEditorActionListener((v, actionId, event) -> {
            boolean keyboardSend = actionId == android.view.inputmethod.EditorInfo.IME_ACTION_SEND
                    || actionId == android.view.inputmethod.EditorInfo.IME_ACTION_DONE;
            boolean enterPressed = event != null
                    && event.getKeyCode() == android.view.KeyEvent.KEYCODE_ENTER
                    && event.getAction() == android.view.KeyEvent.ACTION_DOWN
                    && !event.isShiftPressed();
            if (keyboardSend || enterPressed) {
                sendCommand(command.getText().toString());
                return true;
            }
            return false;
        });
        voiceControl.setOnClickListener(v -> listen());
        agents.setOnClickListener(v -> showAgents());
        host.setOnClickListener(v -> showHostSettings());
        update.setOnClickListener(v -> checkForUpdates(true));
        help.setOnClickListener(v -> sendCommand("yardım"));
    }

    private void checkForUpdates(boolean manual) {
        final long now = System.currentTimeMillis();
        final long lastAttempt = updatePrefs.getLong("last_check_attempt", 0L);
        if (!manual && now - lastAttempt < 12L * 60L * 60L * 1000L) return;

        updatePrefs.edit().putLong("last_check_attempt", now).apply();
        if (manual) status.setText("● UPDATE CHECK");
        io.submit(() -> {
            try {
                int installed = getPackageManager().getPackageInfo(getPackageName(), 0).versionCode;
                UpdateManager.UpdateInfo update = updateManager.checkLatest(installed);
                updatePrefs.edit().putLong("last_check_success", System.currentTimeMillis()).apply();
                runOnUiThread(() -> {
                    if (update != null) {
                        offerUpdate(update);
                    } else if (manual) {
                        append("JARVIS", "Kurulu JARVIS sürümü güncel. Yeni bir sürüm yayımlanmamış.");
                        refreshVoiceStatus();
                    }
                });
            } catch (Exception e) {
                if (manual) {
                    runOnUiThread(() -> {
                        append("JARVIS", "Güncelleme kontrol edilemedi. Henüz resmî Release yayımlanmamış olabilir. Ayrıntı: "
                                + e.getMessage());
                        refreshVoiceStatus();
                    });
                }
            }
        });
    }

    private void offerUpdate(UpdateManager.UpdateInfo update) {
        String details = "Kurulu sürümden daha yeni bir sürüm bulundu.\n\n"
                + "Yeni sürüm: " + update.versionName + " (" + update.versionCode + ")\n"
                + update.notes + "\n\nAPK indirilecek, SHA-256 ile doğrulanacak ve Android kurulum onayı açılacak.";
        new AlertDialog.Builder(this)
                .setTitle("JARVIS GÜNCELLEMESİ")
                .setMessage(details)
                .setPositiveButton("İNDİR VE KUR", (dialog, which) -> downloadAndInstall(update))
                .setNegativeButton("SONRA", (dialog, which) -> append("JARVIS", "Güncelleme ertelendi."))
                .show();
    }

    private void downloadAndInstall(UpdateManager.UpdateInfo update) {
        status.setText("● DOWNLOADING UPDATE");
        append("JARVIS", "JARVIS " + update.versionName + " indiriliyor ve bütünlük kontrolü yapılıyor.");
        io.submit(() -> {
            try {
                File apk = new File(getCacheDir(), "jarvis-update-" + update.versionCode + ".apk");
                updateManager.downloadAndVerify(update, apk);
                runOnUiThread(() -> {
                    pendingUpdateFile = apk;
                    pendingUpdateVersion = update.versionName;
                    updatePrefs.edit().putString("pending_apk", apk.getAbsolutePath())
                            .putString("pending_version", pendingUpdateVersion).apply();
                    beginUpdateInstall();
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    append("JARVIS", "Güncelleme indirilemedi veya doğrulanamadı. Kurulum iptal edildi: " + e.getMessage());
                    refreshVoiceStatus();
                });
            }
        });
    }

    private void beginUpdateInstall() {
        if (pendingUpdateFile == null || !pendingUpdateFile.isFile() || updateInstallInProgress) return;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                && !getPackageManager().canRequestPackageInstalls()) {
            new AlertDialog.Builder(this)
                    .setTitle("Kurulum izni gerekli")
                    .setMessage("JARVIS'i resmî GitHub Release dosyasından indirdim ve bütünlük kontrolü geçti. Devam etmek için Android ayarlarında bu uygulamanın paket kurmasına izin ver.")
                    .setPositiveButton("AYARLARI AÇ", (dialog, which) -> {
                        try {
                            Intent settings = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                                    Uri.parse("package:" + getPackageName()));
                            startActivity(settings);
                        } catch (Exception e) {
                            append("JARVIS", "Kurulum izni ayarları açılamadı: " + e.getMessage());
                        }
                    })
                    .setNegativeButton("İPTAL", (dialog, which) -> {
                        File declined = pendingUpdateFile;
                        pendingUpdateFile = null;
                        pendingUpdateVersion = "";
                        updatePrefs.edit().remove("pending_apk").remove("pending_version").apply();
                        if (declined != null) declined.delete();
                        append("JARVIS", "Kurulum izni verilmedi; indirilmiş güncelleme iptal edildi.");
                        refreshVoiceStatus();
                    })
                    .setCancelable(false)
                    .show();
            return;
        }

        updateInstallInProgress = true;
        PackageInstaller installer = getPackageManager().getPackageInstaller();
        int sessionId = -1;
        try {
            PackageInstaller.SessionParams params =
                    new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL);
            params.setAppPackageName(getPackageName());
            params.setSize(pendingUpdateFile.length());
            sessionId = installer.createSession(params);

            try (PackageInstaller.Session session = installer.openSession(sessionId);
                 InputStream input = new FileInputStream(pendingUpdateFile);
                 OutputStream output = session.openWrite("base.apk", 0, pendingUpdateFile.length())) {
                byte[] buffer = new byte[65536];
                int count;
                while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
                session.fsync(output);

                Intent callback = new Intent(this, UpdateInstallReceiver.class);
                callback.setAction("com.stagepulse.jarvis.UPDATE_INSTALL_RESULT");
                int flags = PendingIntent.FLAG_UPDATE_CURRENT;
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) flags |= PendingIntent.FLAG_MUTABLE;
                PendingIntent resultIntent = PendingIntent.getBroadcast(this, sessionId, callback, flags);
                session.commit(resultIntent.getIntentSender());
            }

            updatePrefs.edit().remove("pending_apk").remove("pending_version").apply();
            pendingUpdateFile = null;
            append("JARVIS", "APK doğrulandı. Android'in resmî kurulum onayı açılıyor.");
            status.setText("● INSTALLING UPDATE");
        } catch (Exception e) {
            if (sessionId >= 0) {
                try { installer.abandonSession(sessionId); } catch (Exception ignored) {}
            }
            updatePrefs.edit().remove("pending_apk").remove("pending_version").apply();
            pendingUpdateFile = null;
            append("JARVIS", "Güncelleme kurulumu başlatılamadı: " + e.getMessage());
            refreshVoiceStatus();
        } finally {
            updateInstallInProgress = false;
        }
    }

    @Override protected void onResume() {
        super.onResume();
        if (pendingUpdateFile == null) {
            String path = updatePrefs == null ? "" : updatePrefs.getString("pending_apk", "");
            if (path != null && !path.isEmpty()) {
                File candidate = new File(path);
                if (candidate.isFile()) pendingUpdateFile = candidate;
            }
        }
        boolean installPermissionGranted = Build.VERSION.SDK_INT < Build.VERSION_CODES.O
                || getPackageManager().canRequestPackageInstalls();
        if (pendingUpdateFile != null && !updateInstallInProgress && installPermissionGranted) {
            beginUpdateInstall();
        }
    }

    private void showHostSettings(){
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(20, 8, 20, 0);
        EditText address = new EditText(this);
        address.setSingleLine(true);
        address.setHint("http://192.168.1.100:8765");
        address.setText(bridgePrefs.getString("url", ""));
        EditText token = new EditText(this);
        token.setSingleLine(true);
        token.setHint("Windows JARVIS bridge token");
        token.setInputType(129);
        token.setText(bridgePrefs.getString("token", ""));
        box.addView(address);
        box.addView(token);
        new AlertDialog.Builder(this)
            .setTitle("WINDOWS JARVIS BAĞLANTISI")
            .setMessage("Windows bilgisayarının yerel IP adresini ve android_bridge.py tarafından oluşturulan token'ı gir.")
            .setView(box)
            .setPositiveButton("KAYDET VE TEST ET", (d, which) -> {
                String url = address.getText().toString().trim();
                String secret = token.getText().toString().trim();
                bridgePrefs.edit().putString("url", url).putString("token", secret).apply();
                if (url.isEmpty() || secret.isEmpty()) {
                    append("JARVIS", "Ortak Windows çekirdeği kapalı. Yerel Android komutları kullanılacak.");
                    return;
                }
                status.setText("● HOST TEST");
                io.submit(() -> {
                    try {
                        boolean ok = BridgeClient.health(url, secret);
                        runOnUiThread(() -> {
                            status.setText(ok ? "● WINDOWS LINKED" : "● HOST ERROR");
                            append("JARVIS", ok
                                ? "Windows JARVIS ortak çekirdeğine bağlandım. Android ve EXE aynı host komut motorunu kullanacak."
                                : "Windows JARVIS köprüsü doğrulanamadı.");
                        });
                    } catch (Exception e) {
                        runOnUiThread(() -> {
                            status.setText("● HOST OFFLINE");
                            append("JARVIS", "Windows bağlantısı kurulamadı. IP, token, aynı Wi-Fi ağı ve Windows Güvenlik Duvarı'nı kontrol et.");
                        });
                    }
                });
            })
            .setNegativeButton("İPTAL", null)
            .show();
    }

    private void showAgents(){
        final List<AgencyAgent> list=AgencyCatalog.all();
        String[] names=new String[list.size()];
        for(int i=0;i<list.size();i++) names[i]=list.get(i).name;
        new AlertDialog.Builder(this)
                .setTitle("STAGEPULSE AGENTS")
                .setItems(names,(d,which)->activateAgent(list.get(which),null))
                .setNegativeButton("KAPAT",null)
                .show();
    }

    private void activateAgent(AgencyAgent agent,String task){
        activeAgent=agent;
        String t=(task==null||task.trim().isEmpty()) ? "Bu uzmanlık alanında gelen sonraki teknik görevi değerlendir." : task.trim();
        String prompt=agent.activationPrompt(t);
        append("AGENT AKTİF",agent.name+"\n\n"+prompt);
        status.setText("● AGENT: "+agent.name);
        status.setTextColor(gold());
        speak(agent.name+" aktif. Patron, teknik görevinizi bekliyorum.");
    }

    private AgencyAgent detectAgent(String c){
        String x=c.toLowerCase(new Locale("tr","TR"));
        for(AgencyAgent a:AgencyCatalog.all()){
            String n=a.name.toLowerCase(new Locale("tr","TR"));
            String id=a.id.replace("_"," ").toLowerCase(new Locale("tr","TR"));
            if(x.contains(n)||x.contains(id)) return a;
        }
        if(x.contains("ön taraf")||x.contains("foh")) return AgencyCatalog.find("FOH ENGINEER");
        if(x.contains("monitör")||x.contains("iem")) return AgencyCatalog.find("MONITOR ENGINEER");
        if(x.contains("rf")||x.contains("kablosuz")) return AgencyCatalog.find("RF ENGINEER");
        if(x.contains("dante")) return AgencyCatalog.find("DANTE NETWORK ENGINEER");
        if(x.contains("spl")) return AgencyCatalog.find("SPL CALCULATOR");
        if(x.contains("rider")) return AgencyCatalog.find("RIDER ANALYST");
        if(x.contains("sahne plan")) return AgencyCatalog.find("STAGE PLOT ENGINEER");
        return null;
    }

    private void initSpeech(){
        if(!SpeechRecognizer.isRecognitionAvailable(this)) {
            append("SES ALGILAMA","Bu cihazda konuşma tanıma servisi bulunamadı. Google uygulamasını veya desteklenen bir konuşma tanıma motorunu kurup etkinleştir.");
            return;
        }
        try {
            speech=SpeechRecognizer.createSpeechRecognizer(this);
            speech.setRecognitionListener(new RecognitionListener(){
                public void onReadyForSpeech(Bundle b){
                    speechRecognitionBusy = true;
                    updateVoiceControl(true);
                    hud.setActive(true);
                    status.setText("● ONLINE LISTENING");
                    status.setTextColor(gold());
                }
                public void onBeginningOfSpeech(){}
                public void onRmsChanged(float r){}
                public void onBufferReceived(byte[] b){}
                public void onEndOfSpeech(){
                    hud.setActive(false);
                    status.setText("● TRANSCRIBING");
                }
                public void onError(int e){
                    speechRecognitionBusy = false;
                    updateVoiceControl(false);
                    hud.setActive(false);
                    refreshVoiceStatus();
                    String detail;
                    switch(e) {
                        case SpeechRecognizer.ERROR_NETWORK:
                            detail = "İnternet bağlantısı veya konuşma sunucusu kullanılamıyor."; break;
                        case SpeechRecognizer.ERROR_NETWORK_TIMEOUT:
                            detail = "Konuşma tanıma sunucusunun yanıtı zaman aşımına uğradı."; break;
                        case SpeechRecognizer.ERROR_NO_MATCH:
                            detail = "Konuşma anlaşılamadı. Biraz daha net ve kısa söyle."; break;
                        case SpeechRecognizer.ERROR_AUDIO:
                            detail = "Mikrofon ses akışı başlatılamadı."; break;
                        case SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS:
                            detail = "Mikrofon izni gerekli."; break;
                        case SpeechRecognizer.ERROR_RECOGNIZER_BUSY:
                            detail = "Konuşma tanıma motoru meşgul. Biraz sonra tekrar dene."; break;
                        case SpeechRecognizer.ERROR_SERVER:
                            detail = "Konuşma tanıma sunucusu hata verdi."; break;
                        default:
                            detail = "Ses tanıma tamamlanamadı. Hata kodu: " + e; break;
                    }
                    append("SES ALGILAMA",detail);
                }
                public void onResults(Bundle b){
                    speechRecognitionBusy = false;
                    updateVoiceControl(false);
                    hud.setActive(false);
                    ArrayList<String> candidates = b.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                    if(candidates != null && !candidates.isEmpty()){
                        String recognized = normalizeVoiceCommand(chooseBestTranscript(candidates));
                        if (recognized.isEmpty()) {
                            refreshVoiceStatus();
                            append("SES ALGILAMA", "Komut anlaşılır bir metne dönüştürülemedi. Tekrar söyleyebilir veya yazabilirsin.");
                            return;
                        }
                        command.setText(recognized);
                        if (isWakePhraseOnly(recognized)) {
                            refreshVoiceStatus();
                            append("JARVIS", "Buradayım Patron. Komutunu söyle.");
                            speak("Buradayım Patron. Komutunu söyle.");
                        } else {
                            sendCommand(recognized);
                        }
                    } else {
                        refreshVoiceStatus();
                        append("SES ALGILAMA","Konuşma tanıma hizmetinden metin sonucu gelmedi.");
                    }
                }
                public void onPartialResults(Bundle b){
                    ArrayList<String> partial = b.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                    if (partial != null && !partial.isEmpty() && command != null
                            && command.getText().toString().trim().isEmpty()) {
                        command.setText(partial.get(0));
                        command.setSelection(command.getText().length());
                    }
                }
                public void onEvent(int t,Bundle b){}
            });
        } catch (Exception e) {
            speech = null;
            append("SES ALGILAMA","Konuşma tanıma başlatılamadı: " + e.getClass().getSimpleName());
        }
    }

    private String chooseBestTranscript(List<String> candidates) {
        String best = "";
        int bestScore = Integer.MIN_VALUE;
        for (String candidate : candidates) {
            if (candidate == null || candidate.trim().isEmpty()) continue;
            String normalized = normalizeVoiceCommand(candidate);
            String lower = normalized.toLowerCase(new Locale("tr", "TR"));
            int score = Math.min(normalized.length(), 120) / 12;
            if (lower.contains("hey jarvis") || lower.contains("hey jervis")
                    || lower.contains("hey carvis") || lower.contains("heijan biz")
                    || lower.contains("eğitim paketi") || lower.contains("egitim paketi")) score += 5;
            if (lower.contains("hazırla") || lower.contains("hazirla")
                    || lower.contains("oluştur") || lower.contains("olustur")
                    || lower.contains("aç") || lower.contains("ac")) score += 3;
            if (lower.matches(".*\\b(facebook|whatsapp|instagram)\\b.*")) score += 1;
            if (score > bestScore) {
                best = normalized;
                bestScore = score;
            }
        }
        return best;
    }

    private String normalizeVoiceCommand(String raw) {
        if (raw == null) return "";
        String value = raw.trim().replaceAll("\\s+", " ");
        String lower = value.toLowerCase(new Locale("tr", "TR"));
        lower = lower.replace("ı", "i").replace("ş", "s").replace("ğ", "g")
                .replace("ü", "u").replace("ö", "o").replace("ç", "c");
        // Common Turkish speech-recognition mishearings seen in device tests.
        lower = lower.replaceAll("\\b(heijan biz|hey jervis|hey carvis|hey jarvis|hey cervis|hey djarvis)\\b", "hey jarvis");
        lower = lower.replaceAll("\\b(jarvis|jervis|carvis|cervis|djarvis)\\b", "jarvis");
        lower = lower.replaceAll("\\b(pakeylri|pakeyli|paketleri|paketli)\\b", "paketi");
        lower = lower.replaceAll("\\b(baziela|bazila|haziela|hazirlaa|hazila)\\b", "hazirla");
        lower = lower.replaceAll("\\b(egitim paketi hazirla|egitim paketi hazila|egitim paketi baziela|egitim paketini hazirla)\\b", "egitim paketi hazirla");
        lower = lower.replaceAll("\\bhey jarvis[ ,:;.!-]*", "").trim();
        if (lower.matches("^(egitim|eğitim) paket(i|ini) (hazirla|haziela|baziela)$")) {
            return "eğitim paketi hazırla";
        }
        // Keep Turkish wording for display and downstream intent matching.
        if (lower.matches("^(hey )?jarvis$")) return "hey jarvis";
        return lower.replace("egitim", "eğitim").replace("hazirla", "hazırla");
    }

    private boolean isWakePhraseOnly(String commandText) {
        if (commandText == null) return false;
        String normalized = commandText.toLowerCase(new Locale("tr", "TR"))
                .replace("ı", "i").replace("ş", "s").replace("ğ", "g")
                .replace("ü", "u").replace("ö", "o").replace("ç", "c").trim();
        return normalized.equals("jarvis") || normalized.equals("hey jarvis");
    }

    private void listen(){
        if(speech==null){
            append("SES ALGILAMA","Bu cihazda kullanılabilir bir konuşma tanıma servisi bulunamadı. Google uygulamasını veya cihazın konuşma tanıma hizmetini etkinleştir.");
            return;
        }
        if(speechRecognitionBusy){
            try{speech.cancel();}catch(Exception ignored){}
            speechRecognitionBusy=false;
            updateVoiceControl(false);
            hud.setActive(false);
            refreshVoiceStatus();
            append("SES ALGILAMA","Dinleme durduruldu.");
            return;
        }
        if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},REQ_AUDIO);return;}
        try {
            speechRecognitionBusy = true;
            updateVoiceControl(true);
            hud.setActive(true);
            Intent i=new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            i.putExtra(RecognizerIntent.EXTRA_LANGUAGE,"tr-TR");
            i.putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE,"tr-TR");
            i.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
            i.putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE,false);
            i.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS,3);
            i.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS,true);
            i.putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE,getPackageName());
            status.setText("● CONNECTING TO SPEECH");
            speech.startListening(i);
        } catch (Exception e) {
            speechRecognitionBusy = false;
            updateVoiceControl(false);
            hud.setActive(false);
            refreshVoiceStatus();
            append("SES ALGILAMA","Mikrofon oturumu başlatılamadı: " + e.getClass().getSimpleName());
        }
    }

    private void sendCommand(String text){
        final String cmd = text == null ? "" : text.trim();
        if (cmd.isEmpty()) {
            toast("Önce bir komut yaz veya konuş.");
            return;
        }
        append("PATRON", cmd);
        if (command != null) {
            command.setText("");
            try {
                ((android.view.inputmethod.InputMethodManager) getSystemService(INPUT_METHOD_SERVICE))
                        .hideSoftInputFromWindow(command.getWindowToken(), 0);
            } catch (Exception ignored) {}
        }
        hud.setActive(true);
        status.setText("● PROCESSING");
        io.submit(()->{
            String a;
            try{
                String hostUrl = bridgePrefs.getString("url", "").trim();
                String hostToken = bridgePrefs.getString("token", "").trim();
                if (!hostUrl.isEmpty() && !hostToken.isEmpty() && !isAndroidLocalCommand(cmd)) {
                    statusPost("● WINDOWS JARVIS");
                    try {
                        BridgeClient.Result remote = BridgeClient.command(hostUrl, hostToken, cmd);
                        a = remote.response;
                    } catch (Exception hostError) {
                        statusPost("● LOCAL MODE");
                        String localAnswer = processLocal(cmd);
                        a = "Windows bağlantısı şu anda kullanılamıyor; komutu telefonda yerel olarak değerlendirdim.\\n\\n" + localAnswer;
                    }
                } else {
                AgencyAgent requested=detectAgent(cmd);
                if(requested!=null && (cmd.toLowerCase(new Locale("tr","TR")).contains("aktif") || cmd.toLowerCase(new Locale("tr","TR")).contains("agent") || cmd.toLowerCase(new Locale("tr","TR")).contains("mühendis") || cmd.toLowerCase(new Locale("tr","TR")).contains("uzman"))){
                    final AgencyAgent ag=requested;
                    runOnUiThread(()->activateAgent(ag,cmd));
                    a="STAGEPULSE "+ag.name+" aktif.";
                }else if(isResearchCommand(cmd)){
                    statusPost("● RESEARCHING");
                    ResearchEngine.Report report=ResearchEngine.research(extractResearchQuery(cmd));
                    a=report.text;
                }else{
                    a=processLocal(cmd);
                }
                }
            }catch(Exception e){
                a="İşlem tamamlanamadı Patron. Teknik bilgi: "+e.getClass().getSimpleName();
            }
            final String answer=a;
            runOnUiThread(()->{hud.setActive(false);if(!status.getText().toString().startsWith("● AGENT"))refreshVoiceStatus();append("JARVIS",answer);speak(answer);});
        });
    }

    private void statusPost(String text){runOnUiThread(()->status.setText(text));}

    private void refreshVoiceStatus(){
        boolean recognitionReady = speech != null;
        boolean voiceOutputReady = androidTtsReady;
        String label = recognitionReady
                ? (voiceOutputReady ? "● ONLINE VOICE READY" : "● ONLINE STT READY")
                : (voiceOutputReady ? "● SYSTEM TTS ONLY" : "● TEXT MODE");
        status.setText(label);
        status.setTextColor((recognitionReady || voiceOutputReady) ? gold() : 0xFFFFB74D);
    }

    private boolean isResearchCommand(String c){
        String x=c.toLowerCase(new Locale("tr","TR"));
        return x.contains("araştır")||x.contains("araştırsana")||x.contains("araştırma yap")||
               x.contains("webde bul")||x.contains("internetten bul")||x.contains("internette ara")||
               x.contains("kaynakları bul")||x.contains("rapor hazırla")||x.contains("raporla");
    }

    private String extractResearchQuery(String raw){
        String q=raw.trim();
        String[] prefixes={"jarvis ","araştır ","araştırma yap ","internette ara ","internetten bul ","webde bul ","kaynakları bul ","rapor hazırla ","raporla "};
        String low=q.toLowerCase(new Locale("tr","TR"));
        for(String p:prefixes) if(low.startsWith(p)) { q=q.substring(p.length()).trim(); break; }
        if(q.isEmpty()) q="güncel haberler";
        return q;
    }

    private boolean isAndroidLocalCommand(String raw) {
        String x = raw == null ? "" : raw.toLowerCase(new Locale("tr", "TR"));
        x = x.replace("ı","i").replace("ş","s").replace("ğ","g").replace("ü","u").replace("ö","o").replace("ç","c").trim();
        if (openDirectWebsite(raw) != null) return true;
        if (x.startsWith("hatirla") || x.startsWith("jarvis, hatirla") || x.startsWith("unut")
                || x.equals("hafizami goster") || x.equals("hafizamda ne var")
                || x.equals("ne hatirliyorsun")) return true;
        boolean launchVerb = x.contains(" ac") || x.startsWith("ac") || x.contains("baslat")
                || x.contains("open") || x.contains("calistir");
        boolean appCommand = launchVerb && (x.contains("youtube") || x.contains("whatsapp")
                || x.contains("instagram") || x.contains("chrome") || x.contains("harita")
                || x.contains("maps") || x.contains("music") || x.contains("muzik"));
        boolean settingsCommand = (x.contains("wifi") || x.contains("wi-fi")
                || x.contains("kablosuz ag") || x.contains("bluetooth")) && (launchVerb || x.contains("ayar"));
        boolean fileCommand = x.contains("dosya") && (launchVerb || x.contains("sec"));
        boolean volumeCommand = x.contains("ses artir") || x.contains("sesi yukselt")
                || x.contains("ses azalt") || x.contains("sesi kis") || x.contains("sessize al")
                || x.contains("sesi kapat") || x.contains("sesi ac");
        return appCommand || settingsCommand || fileCommand || volumeCommand
                || x.contains("kamera") || x.contains("telefon ara") || x.contains("arama yap")
                || x.contains("ekran parlakligi") || x.contains("pil tasarrufu")
                || x.equals("merhaba") || x.equals("selam") || x.contains("kimsin")
                || x.contains("adin ne") || x.contains("saat kac") || x.equals("saat")
                || x.contains("tarih") || x.contains("bugun") || x.contains("pil")
                || x.contains("batarya") || x.contains("ayarlar") || x.contains("tarayici")
                || x.contains("internet ac") || x.contains("yardim")
                || x.contains("ne yapabiliyorsun") || x.contains("nasilsin")
                || x.contains("iyi misin") || x.contains("tesekkur")
                || x.contains("sag ol") || x.contains("ne yapiyorsun");
    }

    private String handleLocalMemory(String raw) {
        String original = raw == null ? "" : raw.trim();
        String normalized = original.toLowerCase(new Locale("tr", "TR")).replace("ı", "i").replace("ş", "s").replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("ç", "c");
        android.content.SharedPreferences prefs = getSharedPreferences("jarvis_local_memory", MODE_PRIVATE);
        if (normalized.equals("hafizami goster") || normalized.equals("hafizamda ne var")
                || normalized.equals("ne hatirliyorsun")) {
            Set<String> stored = prefs.getStringSet("facts", Collections.emptySet());
            if (stored == null || stored.isEmpty()) return "Yerel hafızam henüz boş. 'Hatırla: ...' komutuyla bilgi kaydedebilirsin.";
            StringBuilder result = new StringBuilder("Bu cihazdaki kalıcı hafızam:\n");
            int index = 1;
            for (String fact : new TreeSet<>(stored)) result.append(index++).append(". ").append(fact).append("\n");
            return result.toString().trim();
        }
        String fact = null;
        if (normalized.startsWith("hatırla:") || normalized.startsWith("hatirla:")) fact = original.substring(original.indexOf(':') + 1).trim();
        else if (normalized.startsWith("hatırla ") || normalized.startsWith("hatirla ")) fact = original.substring(original.indexOf(' ') + 1).trim();
        else if (normalized.startsWith("jarvis, hatırla ") || normalized.startsWith("jarvis, hatirla ")) fact = original.substring(original.indexOf("hatırla") >= 0 ? original.indexOf("hatırla") + 7 : original.indexOf("hatirla") + 7).trim();
        if (fact != null) {
            if (fact.length() > 300) return "Tek bir hafıza kaydı en fazla 300 karakter olabilir.";
            if (fact.matches("(?is).*(password|parola|şifre|sifre|api\\s*key|access\\s*token|token|secret|otp|pin|tc kimlik|kredi kartı|credit card).*"))
                return "Güvenlik için parola, erişim anahtarı veya benzeri gizli bilgileri hafızaya kaydetmiyorum.";
            Set<String> stored = new LinkedHashSet<>(prefs.getStringSet("facts", Collections.emptySet()));
            for (String existing : stored) if (existing.equalsIgnoreCase(fact)) return "Bu bilgi zaten hafızamda kayıtlı.";
            stored.add(fact);
            while (stored.size() > 100) stored.remove(stored.iterator().next());
            prefs.edit().putStringSet("facts", stored).apply();
            return "Bu bilgiyi bu cihazın kalıcı hafızasına kaydettim.";
        }
        String forget = null;
        if (normalized.startsWith("unut:")) forget = original.substring(original.indexOf(':') + 1).trim();
        else if (normalized.startsWith("unut ")) forget = original.substring(original.indexOf(' ') + 1).trim();
        if (forget != null) {
            if (forget.isEmpty()) return "Hangi bilgiyi unutmamı istediğini belirt.";
            Set<String> stored = new LinkedHashSet<>(prefs.getStringSet("facts", Collections.emptySet()));
            int before = stored.size();
            String needle = forget.toLowerCase(new Locale("tr", "TR"));
            stored.removeIf(item -> item.toLowerCase(new Locale("tr", "TR")).contains(needle));
            int removed = before - stored.size();
            prefs.edit().putStringSet("facts", stored).apply();
            return removed > 0 ? "İstenen hafıza kaydını sildim. Silinen kayıt: " + removed : "Eşleşen hafıza kaydı bulamadım.";
        }
        return null;
    }

    private String openDirectWebsite(String raw) {
        String x = raw == null ? "" : raw.toLowerCase(new Locale("tr", "TR"));
        x = x.replace("ı","i").replace("ş","s").replace("ğ","g").replace("ü","u").replace("ö","o").replace("ç","c");
        if (!(x.contains("ac") || x.contains("gir") || x.contains("git") || x.contains("ziyaret et") || x.contains("open"))) return null;
        String url = null;
        String label = null;
        if (x.contains("benim sitem") || x.contains("sitemi") || x.contains("admin") || x.contains("yonetim panel")) {
            url = "https://stagepulse.com.tr/admin/"; label = "Stagepulse yönetim paneli";
        } else if (x.contains("personel") || x.contains("staff portal")) {
            url = "https://stagepulse.com.tr/portal/"; label = "Stagepulse personel portalı";
        } else if (x.contains("stagepulse.com.tr") || x.contains("stagepulse com tr")) {
            url = "https://stagepulse.com.tr/"; label = "Stagepulse ana sitesi";
        } else if (x.contains("facebook")) {
            url = "https://www.facebook.com/"; label = "Facebook";
        } else if (x.contains("siteyi") || x.contains("siteyi ac") || x.contains("stagepulse") || x.contains("siteyi aç")) {
            url = "https://stagepulse.com.tr/"; label = "Stagepulse ana sitesi";
        }
        if (url == null) return null;
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
            return label + " açılıyor.";
        } catch (Exception e) {
            return label + " açılamadı. Tarayıcı kurulumunu kontrol et.";
        }
    }

    private String launchAndroidAppOrWeb(String packageName, String fallbackUrl, String label) {
        try {
            Intent launch = getPackageManager().getLaunchIntentForPackage(packageName);
            if (launch != null) {
                startActivity(launch);
                return label + " uygulamasını açıyorum.";
            }
        } catch (Exception ignored) {}
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(fallbackUrl)));
            return label + " uygulaması bulunamadı; web sürümünü açıyorum.";
        } catch (Exception e) {
            return label + " açılamadı. Uygulamanın yüklü olup olmadığını kontrol et.";
        }
    }

    private String processLocal(String raw){
        String memoryResponse = handleLocalMemory(raw);
        if (memoryResponse != null) return memoryResponse;
        String websiteResponse = openDirectWebsite(raw);
        if (websiteResponse != null) return websiteResponse;
        String c=raw.toLowerCase(new Locale("tr","TR")).trim();
        String normalized=c.replace("ı","i").replace("ş","s").replace("ğ","g").replace("ü","u").replace("ö","o").replace("ç","c");
        boolean launchVerb = c.contains("aç") || normalized.contains(" ac") || normalized.startsWith("ac")
                || c.contains("başlat") || normalized.contains("baslat") || c.contains("open");
        if ((c.contains("wifi") || c.contains("wi-fi") || normalized.contains("kablosuz ag"))
                && (launchVerb || c.contains("ayar"))) {
            try { startActivity(new Intent(Settings.ACTION_WIFI_SETTINGS)); return "Wi-Fi ayarlarını açıyorum."; }
            catch (Exception e) { return "Wi-Fi ayarları açılamadı."; }
        }
        if (c.contains("bluetooth") && (launchVerb || c.contains("ayar"))) {
            try { startActivity(new Intent(Settings.ACTION_BLUETOOTH_SETTINGS)); return "Bluetooth ayarlarını açıyorum."; }
            catch (Exception e) { return "Bluetooth ayarları açılamadı."; }
        }
        if (c.contains("ses artır") || normalized.contains("ses artir") || c.contains("sesi yükselt") || normalized.contains("sesi yukselt")) {
            AudioManager audio=(AudioManager)getSystemService(AUDIO_SERVICE);
            if(audio!=null) audio.adjustStreamVolume(AudioManager.STREAM_MUSIC,AudioManager.ADJUST_RAISE,AudioManager.FLAG_SHOW_UI);
            return "Medya sesini artırdım.";
        }
        if (c.contains("ses azalt") || normalized.contains("ses azalt") || c.contains("sesi kıs") || normalized.contains("sesi kis")) {
            AudioManager audio=(AudioManager)getSystemService(AUDIO_SERVICE);
            if(audio!=null) audio.adjustStreamVolume(AudioManager.STREAM_MUSIC,AudioManager.ADJUST_LOWER,AudioManager.FLAG_SHOW_UI);
            return "Medya sesini azalttım.";
        }
        if (c.contains("sessize al") || c.contains("sesi kapat")) {
            AudioManager audio=(AudioManager)getSystemService(AUDIO_SERVICE);
            if(audio!=null) audio.adjustStreamVolume(AudioManager.STREAM_MUSIC,AudioManager.ADJUST_MUTE,AudioManager.FLAG_SHOW_UI);
            return "Medya sesini kapattım.";
        }
        if (normalized.contains("sesi ac") || c.contains("sesi aç") || c.contains("sesi aç")) {
            AudioManager audio=(AudioManager)getSystemService(AUDIO_SERVICE);
            if(audio!=null) audio.adjustStreamVolume(AudioManager.STREAM_MUSIC,AudioManager.ADJUST_UNMUTE,AudioManager.FLAG_SHOW_UI);
            return "Medya sesini açtım.";
        }
        if (c.contains("dosya") && (launchVerb || normalized.contains("dosya sec"))) {
            try {
                Intent pick=new Intent(Intent.ACTION_OPEN_DOCUMENT);
                pick.addCategory(Intent.CATEGORY_OPENABLE);
                pick.setType("*/*");
                startActivity(pick);
                return "Dosya seçiciyi açıyorum.";
            } catch (Exception e) { return "Dosya seçici açılamadı."; }
        }
        if (c.contains("kamera")) {
            try { startActivity(new Intent(android.provider.MediaStore.ACTION_IMAGE_CAPTURE)); return "Kamerayı açıyorum."; }
            catch (Exception e) { return "Kamera açılamadı."; }
        }
        if (c.contains("telefon ara") || c.contains("arama yap")) {
            try { startActivity(new Intent(Intent.ACTION_DIAL, Uri.parse("tel:"))); return "Telefon arama ekranını açıyorum."; }
            catch (Exception e) { return "Telefon arama ekranı açılamadı."; }
        }
        if (c.contains("ekran parlaklığı") || normalized.contains("ekran parlakligi")) {
            try { startActivity(new Intent(Settings.ACTION_DISPLAY_SETTINGS)); return "Ekran ayarlarını açıyorum."; }
            catch (Exception e) { return "Ekran ayarları açılamadı."; }
        }
        if (c.contains("pil tasarrufu") || normalized.contains("pil tasarrufu")) {
            try { startActivity(new Intent(Settings.ACTION_BATTERY_SAVER_SETTINGS)); return "Pil tasarrufu ayarlarını açıyorum."; }
            catch (Exception e) { return "Pil tasarrufu ayarları açılamadı."; }
        }
        if (c.contains("youtube") && launchVerb) return launchAndroidAppOrWeb("com.google.android.youtube","https://www.youtube.com/","YouTube");
        if (c.contains("whatsapp") && launchVerb) return launchAndroidAppOrWeb("com.whatsapp","https://www.whatsapp.com/","WhatsApp");
        if (c.contains("instagram") && launchVerb) return launchAndroidAppOrWeb("com.instagram.android","https://www.instagram.com/","Instagram");
        if (c.contains("chrome") && launchVerb) return launchAndroidAppOrWeb("com.android.chrome","https://www.google.com/","Chrome");
        if (c.contains("müzik") && launchVerb) {
            try {
                startActivity(Intent.makeMainSelectorActivity(Intent.ACTION_MAIN, Intent.CATEGORY_APP_MUSIC));
                return "Müzik uygulamasını açıyorum.";
            } catch (Exception e) { return "Bu cihazda varsayılan müzik uygulaması bulunamadı."; }
        }
        if ((c.contains("harita") || c.contains("maps")) && launchVerb) return launchAndroidAppOrWeb("com.google.android.apps.maps","https://maps.google.com/","Haritalar");
        if(c.equals("ajanlar")||c.equals("agentler")||c.contains("stagepulse agent"))return AgencyCatalog.listText();
        if(c.contains("aktif ajan")||c.contains("hangi ajan"))return activeAgent==null?"Şu anda aktif bir Stagepulse Agent yok.":"Aktif ajan: "+activeAgent.name+".";
        if(c.contains("merhaba")||c.equals("selam"))return "Merhaba Patron. Android JARVIS çekirdeği hazır.";
        if(c.contains("kimsin"))return "Ben J.A.R.V.I.S. Android sürümüyüm. Bu cihaz üzerinde bağımsız çalışıyorum.";
        if(c.contains("saat"))return "Şu an saat "+new SimpleDateFormat("HH:mm",Locale.getDefault()).format(new Date())+".";
        if(c.contains("tarih")||c.contains("bugün"))return "Bugün "+new SimpleDateFormat("dd MMMM yyyy, EEEE",new Locale("tr","TR")).format(new Date())+".";
        if(c.contains("pil")||c.contains("batarya")){BatteryManager b=(BatteryManager)getSystemService(BATTERY_SERVICE);return "Pil seviyesi yüzde "+b.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)+".";}
        if(c.contains("ayarlar")){try{startActivity(new Intent(Settings.ACTION_SETTINGS));return "Android ayarlarını açıyorum.";}catch(Exception e){return "Android ayarları açılamadı.";}}
        if(c.contains("tarayıcı")||c.contains("internet aç")){try{startActivity(new Intent(Intent.ACTION_VIEW,android.net.Uri.parse("https://www.google.com")));return "Tarayıcıyı açıyorum.";}catch(Exception e){return "Tarayıcı açılamadı.";}}
        if(c.contains("yardım")||c.contains("ne yapabiliyorsun"))return "Çevrimdışı: saat, tarih, pil, kalıcı hafıza, ses düzeyi, Wi-Fi/Bluetooth ayarları, dosya seçici, kamera ve bazı uygulamaları açma. PC bağlıyken Windows komutları, dosya/pencere otomasyonu ve ortak AI çekirdeği de kullanılabilir.";
        if(c.contains("nasılsın")||c.contains("nasılsın jarvis")||c.contains("iyi misin"))return "İyiyim Patron. Sistemler kararlı ve komut bekliyorum.";
        if(c.contains("ne yapıyorsun")||c.contains("ne yapıyorsun jarvis"))return "Sizi dinliyorum Patron. Vereceğiniz komutu bekliyorum.";
        if(c.contains("teşekkür")||c.contains("sağ ol"))return "Rica ederim Patron.";
        if(c.contains("adın ne"))return "Ben J.A.R.V.I.S. Patron.";
        if(c.contains("müzik"))return "Müzik komutları için Android çekirdeğine ses kontrol modülü eklenebilir.";
        if(c.contains("merhaba jarvis")||c.contains("selam jarvis"))return "Emrinizdeyim Patron.";
        if(c.endsWith("?"))return "Sorunuzu aldım Patron. Bu Android sürümünde henüz bu soruya cevap verecek yerel bilgi modülü bulunmuyor.";
        if(activeAgent!=null)return activeAgent.name+" aktif. Bu Android çekirdeğinde henüz bağlı bir LLM bulunmadığı için uzman ajan şu aşamada görev bağlamını ve çalışma talimatını hazırlar, fakat kendi başına üretken akıl yürütme yapmaz.";
        return "Komutunuz alındı Patron. Bu komut için Android yerel çekirdeğinde henüz bir işlem tanımlı değil.";
    }

    private void initAndroidTts(){
        androidTts = new TextToSpeech(this, result -> runOnUiThread(() -> {
            if (result != TextToSpeech.SUCCESS) {
                androidTtsReady = false;
                append("SES ÇIKIŞI", "Android sistem ses motoru başlatılamadı. Yazılı yanıtlar kullanılabilir; Ayarlar > Metin okuma bölümünü kontrol et.");
                refreshVoiceStatus();
                return;
            }
            int language = androidTts.setLanguage(new Locale("tr", "TR"));
            androidTts.setSpeechRate(1.0f);
            androidTts.setPitch(1.0f);
            androidTtsReady = language != TextToSpeech.LANG_MISSING_DATA
                    && language != TextToSpeech.LANG_NOT_SUPPORTED;
            if (!androidTtsReady) {
                int fallback = androidTts.setLanguage(Locale.getDefault());
                androidTtsReady = fallback != TextToSpeech.LANG_MISSING_DATA
                        && fallback != TextToSpeech.LANG_NOT_SUPPORTED;
            }
            refreshVoiceStatus();
            if (androidTtsReady) {
                append("SES ÇIKIŞI", "Piper kaldırıldı. Yanıtlar Android sistem ses motoruyla okunacak.");
            } else {
                append("SES ÇIKIŞI", "Türkçe sistem sesi bulunamadı. Android Ayarlar > Metin okuma bölümünden Türkçe ses indir veya etkinleştir.");
            }
        }));
    }

    private void speak(String s){
        if (s == null || s.trim().isEmpty()) return;
        if (androidTtsReady && androidTts != null) {
            androidTts.speak(s, TextToSpeech.QUEUE_FLUSH, null, "jarvis-" + System.currentTimeMillis());
        }
    }
    private void append(String who,String msg){
        if (chat == null) return;
        chat.append((chat.length() > 0 ? "\n\n" : "") + who + "\n" + msg);
        if (chatScroll != null) {
            chatScroll.post(() -> chatScroll.fullScroll(ScrollView.FOCUS_DOWN));
        }
    }
    private void toast(String s){Toast.makeText(this,s,Toast.LENGTH_SHORT).show();}

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_AUDIO) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                listen();
            } else {
                speechRecognitionBusy = false;
                updateVoiceControl(false);
                append("SES ALGILAMA", "Sesli komut için mikrofon izni gerekiyor. İzni Android uygulama ayarlarından açabilirsin.");
            }
        }
    }

    @Override protected void onDestroy(){
        if(speech!=null)speech.destroy();
        if(androidTts!=null){ androidTts.stop(); androidTts.shutdown(); }
        io.shutdownNow();
        super.onDestroy();
    }
}
