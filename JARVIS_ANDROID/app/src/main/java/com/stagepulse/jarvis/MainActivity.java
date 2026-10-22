package com.stagepulse.jarvis;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.PendingIntent;
import android.content.*;
import android.content.pm.PackageManager;
import android.content.pm.PackageInstaller;
import android.database.Cursor;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraManager;
import android.os.*;
import android.provider.Settings;
import android.provider.MediaStore;
import android.net.Uri;
import android.media.AudioManager;
import android.speech.*;
import android.speech.tts.TextToSpeech;
import android.view.Gravity;
import android.widget.*;
import java.text.SimpleDateFormat;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.*;
import java.util.concurrent.*;

public class MainActivity extends Activity {
    private static final int REQ_AUDIO=9001;
    private static final int REQ_CAMERA=9002;
    private static final int REQ_OPEN_DOCUMENT=9003;
    private volatile boolean pendingFileRead = false;
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
    private android.content.SharedPreferences profilePrefs;
    private volatile boolean pendingTorchState = false;
    private volatile int pendingBrightnessDelta = 0;
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
        profilePrefs = getSharedPreferences("jarvis_profile", MODE_PRIVATE);
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
        if (!profilePrefs.getBoolean("setup_complete", false)) {
            new Handler(Looper.getMainLooper()).postDelayed(() -> showProfileSettings(true), 650L);
        }
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

        HorizontalScrollView toolsScroll = new HorizontalScrollView(this);
        toolsScroll.setHorizontalScrollBarEnabled(false);
        toolsScroll.setFillViewport(false);
        LinearLayout secondary = new LinearLayout(this);
        secondary.setOrientation(LinearLayout.HORIZONTAL);
        secondary.setGravity(Gravity.CENTER_VERTICAL);
        TextView agents = control("UZMANLAR", panel(), gold(), 9);
        TextView host = control("PC BAĞLANTI", panel(), gold(), 9);
        TextView profile = control("PROFİL", panel(), gold(), 9);
        TextView update = control("GÜNCELLE", panel(), gold(), 9);
        TextView help = control("YARDIM", panel(), gold(), 9);
        TextView[] tools = {agents, host, profile, update, help};
        int[] toolWidths = {dp(88), dp(108), dp(78), dp(88), dp(78)};
        for (int index = 0; index < tools.length; index++) {
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(toolWidths[index], dp(38));
            if (index > 0) lp.leftMargin = dp(4);
            secondary.addView(tools[index], lp);
        }
        toolsScroll.addView(secondary);
        root.addView(toolsScroll, new LinearLayout.LayoutParams(-1, dp(38)));

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
        profile.setOnClickListener(v -> showProfileSettings(false));
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
        if (pendingBrightnessDelta != 0 && Build.VERSION.SDK_INT >= Build.VERSION_CODES.M
                && Settings.System.canWrite(this)) {
            int delta = pendingBrightnessDelta;
            pendingBrightnessDelta = 0;
            append("TELEFON", applyBrightness(delta));
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


    private void showProfileSettings(boolean firstRun) {
        LinearLayout form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        form.setPadding(dp(18), dp(4), dp(18), 0);

        EditText name = new EditText(this);
        name.setSingleLine(true);
        name.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(80)});
        name.setHint("Profil adı (ör. İbrahim)");
        name.setText(profilePrefs.getString("owner_name", ""));
        EditText role = new EditText(this);
        role.setSingleLine(true);
        role.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(120)});
        role.setHint("Meslek / rol (isteğe bağlı)");
        role.setText(profilePrefs.getString("owner_role", ""));
        EditText organization = new EditText(this);
        organization.setSingleLine(true);
        organization.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(120)});
        organization.setHint("Şirket / proje (isteğe bağlı)");
        organization.setText(profilePrefs.getString("owner_company", ""));
        EditText context = new EditText(this);
        context.setHint("Tercihler ve hatırlanacak genel bilgiler");
        context.setMinLines(2);
        context.setMaxLines(4);
        context.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(600)});
        context.setText(profilePrefs.getString("owner_context", ""));
        form.addView(name);
        form.addView(role);
        form.addView(organization);
        form.addView(context);
        TextView notice = tv("Profil yalnızca bu cihazda saklanır. Bu özellik konuşmacıyı biyometrik olarak tanımaz; hassas işlemler için Android kilidi ve izinleri geçerlidir.", 11, muted());
        notice.setPadding(0, dp(8), 0, dp(4));
        form.addView(notice);

        AlertDialog.Builder dialog = new AlertDialog.Builder(this)
                .setTitle(firstRun ? "JARVIS KİŞİSEL PROFİLİ" : "PROFİL VE HAFIZA")
                .setMessage("JARVIS'in kiminle çalıştığını ve hangi tercihleri hatırlayacağını ayarla.")
                .setView(form)
                .setPositiveButton("KAYDET", (d, which) -> {
                    String owner = name.getText().toString().trim();
                    if (owner.isEmpty()) owner = "Patron";
                    profilePrefs.edit()
                            .putString("owner_name", owner)
                            .putString("owner_role", role.getText().toString().trim())
                            .putString("owner_company", organization.getText().toString().trim())
                            .putString("owner_context", context.getText().toString().trim())
                            .putBoolean("setup_complete", true)
                            .apply();
                    append("JARVIS", owner + " profili bu cihazda kaydedildi.");
                    speak("Profil kaydedildi. Seni bu cihazdaki profilin üzerinden hatırlayacağım.");
                });
        if (firstRun) {
            dialog.setNegativeButton("ŞİMDİ DEĞİL", (d, which) -> {
                profilePrefs.edit().putString("owner_name", "Patron")
                        .putBoolean("setup_complete", true).apply();
                append("JARVIS", "Profil kurulumu ertelendi. Dilediğinde PROFİL bölümünden ayarlayabilirsin.");
            });
        } else {
            dialog.setNegativeButton("İPTAL", null);
        }
        dialog.show();
    }

    private String normalizeIntent(String raw) {
        if (raw == null) return "";
        String value = raw.toLowerCase(new Locale("tr", "TR"));
        return value.replace("ı", "i").replace("ş", "s").replace("ğ", "g")
                .replace("ü", "u").replace("ö", "o").replace("ç", "c")
                .replaceAll("\\s+", " ").trim();
    }

    private String handleOwnerProfileCommand(String raw) {
        String x = normalizeIntent(raw);
        if (x.contains("profilimi ayarla") || x.contains("profil ayarlari")
                || x.equals("profil") || x.contains("hafizam ve profil")) {
            runOnUiThread(() -> showProfileSettings(false));
            return "Profil ayarlarını açıyorum.";
        }
        if (x.equals("ben kimim") || x.contains("beni taniyor musun")
                || x.equals("beni tani") || x.equals("patron kim")
                || x.contains("hakkimda ne biliyorsun") || x.contains("beni hatirliyor musun")) {
            String owner = profilePrefs.getString("owner_name", "Patron");
            String role = profilePrefs.getString("owner_role", "").trim();
            String company = profilePrefs.getString("owner_company", "").trim();
            String context = profilePrefs.getString("owner_context", "").trim();
            StringBuilder answer = new StringBuilder("Bu cihazdaki profil sahibi: ").append(owner).append(".");
            if (!role.isEmpty()) answer.append("\nMeslek/rol: ").append(role).append(".");
            if (!company.isEmpty()) answer.append("\nŞirket/proje: ").append(company).append(".");
            if (!context.isEmpty()) answer.append("\nHatırladığım tercihler: ").append(context);
            Set<String> facts = getSharedPreferences("jarvis_local_memory", MODE_PRIVATE)
                    .getStringSet("facts", Collections.emptySet());
            if (facts != null && !facts.isEmpty()) {
                answer.append("\nKayıtlı hafıza:");
                int count = 0;
                for (String fact : new TreeSet<>(facts)) {
                    if (count++ >= 8) break;
                    answer.append("\n• ").append(fact);
                }
            }
            answer.append("\nNot: Bu bir cihaz profili ve kayıtlı hafızadır; ses kaydından kişinin kimliği biyometrik olarak doğrulanmıyor.");
            return answer.toString();
        }
        if (x.startsWith("adimi ") && (x.contains(" olarak hatirla") || x.contains(" olarak kaydet"))) {
            String name = x.substring("adimi ".length());
            name = name.replace(" olarak hatirla", "").replace(" olarak kaydet", "").trim();
            if (!name.isEmpty() && name.length() <= 80) {
                profilePrefs.edit().putString("owner_name", name).putBoolean("setup_complete", true).apply();
                return "Profil adını " + name + " olarak kaydettim.";
            }
        }
        if (x.startsWith("meslegimi ") && x.contains(" olarak hatirla")) {
            String role = x.substring("meslegimi ".length()).replace(" olarak hatirla", "").trim();
            if (!role.isEmpty() && role.length() <= 120) {
                profilePrefs.edit().putString("owner_role", role).apply();
                return "Meslek bilgisini profile kaydettim.";
            }
        }
        return null;
    }

    private String safeName(String value, String fallback) {
        String name = value == null ? "" : value.trim();
        name = name.replaceAll("[\\\\/:*?\"<>|\\r\\n]", "_").replaceAll("\\s+", "_");
        name = name.replaceAll("^\\.+", "").replaceAll("_+", "_");
        if (name.isEmpty()) name = fallback;
        if (name.length() > 90) name = name.substring(0, 90);
        return name;
    }

    private String createDownloadTextFile(String requestedName, String body, String childFolder) throws IOException {
        String fileName = safeName(requestedName, "JARVIS-Notu");
        String lowerName = fileName.toLowerCase(Locale.ROOT);
        boolean supportedTextType = lowerName.endsWith(".txt") || lowerName.endsWith(".md")
                || lowerName.endsWith(".csv") || lowerName.endsWith(".json")
                || lowerName.endsWith(".html") || lowerName.endsWith(".xml")
                || lowerName.endsWith(".log");
        if (!supportedTextType) fileName += ".txt";
        String stamp = new SimpleDateFormat("yyyyMMdd-HHmmss", Locale.ROOT).format(new Date());
        int dot = fileName.lastIndexOf('.');
        fileName = (dot > 0 ? fileName.substring(0, dot) : fileName) + "-" + stamp
                + (dot > 0 ? fileName.substring(dot) : ".txt");

        String folder = "JARVIS";
        if (childFolder != null && !childFolder.trim().isEmpty()) {
            String safeFolder = safeName(childFolder, "Dosyalar");
            folder += "/" + safeFolder;
        }

        Uri savedUri = null;
        String savedPath;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ContentValues values = new ContentValues();
            values.put(MediaStore.MediaColumns.DISPLAY_NAME, fileName);
            String mime = lowerName.endsWith(".csv") ? "text/csv"
                    : lowerName.endsWith(".json") ? "application/json"
                    : lowerName.endsWith(".html") ? "text/html"
                    : lowerName.endsWith(".xml") ? "application/xml" : "text/plain";
            values.put(MediaStore.MediaColumns.MIME_TYPE, mime);
            values.put(MediaStore.MediaColumns.RELATIVE_PATH,
                    Environment.DIRECTORY_DOWNLOADS + "/" + folder + "/");
            values.put(MediaStore.MediaColumns.IS_PENDING, 1);
            savedUri = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
            if (savedUri == null) throw new IOException("Android dosya sağlayıcısı dosya oluşturamadı.");
            try (OutputStream output = getContentResolver().openOutputStream(savedUri, "w")) {
                if (output == null) throw new IOException("Dosya yazma akışı açılamadı.");
                output.write((body == null ? "" : body).getBytes(java.nio.charset.StandardCharsets.UTF_8));
                output.flush();
            } catch (IOException ex) {
                getContentResolver().delete(savedUri, null, null);
                throw ex;
            }
            ContentValues ready = new ContentValues();
            ready.put(MediaStore.MediaColumns.IS_PENDING, 0);
            getContentResolver().update(savedUri, ready, null, null);
            savedPath = Environment.DIRECTORY_DOWNLOADS + "/" + folder + "/" + fileName;
            profilePrefs.edit().putString("last_file_uri", savedUri.toString())
                    .putString("last_file_name", fileName).putString("last_file_path", savedPath).apply();
        } else {
            File root = getExternalFilesDir(Environment.DIRECTORY_DOCUMENTS);
            if (root == null) throw new IOException("Harici belge klasörü kullanılamıyor.");
            File parent = new File(root, folder);
            if (!parent.exists() && !parent.mkdirs()) throw new IOException("Belge klasörü oluşturulamadı.");
            File destination = new File(parent, fileName);
            try (FileOutputStream output = new FileOutputStream(destination)) {
                output.write((body == null ? "" : body).getBytes(java.nio.charset.StandardCharsets.UTF_8));
                output.flush();
            }
            savedPath = destination.getAbsolutePath();
            profilePrefs.edit().putString("last_file_uri", "")
                    .putString("last_file_name", fileName).putString("last_file_path", savedPath).apply();
        }
        return "Dosya oluşturuldu: İndirilenler/" + folder + "/" + fileName
                + "\nDosya adı ve konumu hafızaya kaydedildi. 'Son dosyayı aç' diyebilirsin.";
    }

    private void launchDocumentPicker(boolean readText) {
        pendingFileRead = readText;
        try {
            Intent picker = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            picker.addCategory(Intent.CATEGORY_OPENABLE);
            picker.setType("*/*");
            startActivityForResult(picker, REQ_OPEN_DOCUMENT);
        } catch (Exception e) {
            append("DOSYA", "Dosya seçici açılamadı: " + e.getMessage());
        }
    }

    private void openContentUri(Uri uri) {
        try {
            Intent view = new Intent(Intent.ACTION_VIEW);
            String mime = getContentResolver().getType(uri);
            view.setDataAndType(uri, mime == null ? "*/*" : mime);
            view.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startActivity(view);
        } catch (Exception e) {
            append("DOSYA", "Dosyayı açacak uygun uygulama bulunamadı: " + e.getMessage());
        }
    }

    private Uri findCreatedFile(String requestedName) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return null;
        String needle = normalizeIntent(requestedName).replaceAll("[^a-z0-9]", "");
        if (needle.isEmpty()) return null;
        Cursor cursor = null;
        try {
            String[] columns = {MediaStore.MediaColumns._ID, MediaStore.MediaColumns.DISPLAY_NAME};
            cursor = getContentResolver().query(MediaStore.Downloads.EXTERNAL_CONTENT_URI, columns,
                    MediaStore.MediaColumns.RELATIVE_PATH + " LIKE ?",
                    new String[]{Environment.DIRECTORY_DOWNLOADS + "/JARVIS/%"},
                    MediaStore.MediaColumns.DATE_ADDED + " DESC");
            if (cursor == null) return null;
            while (cursor.moveToNext()) {
                String name = cursor.getString(1);
                if (name != null) {
                    String nameKey = normalizeIntent(name).replaceAll("[^a-z0-9]", "");
                    if (nameKey.equals(needle) || nameKey.contains(needle)) {
                        return android.content.ContentUris.withAppendedId(
                                MediaStore.Downloads.EXTERNAL_CONTENT_URI, cursor.getLong(0));
                    }
                }

            }
        } catch (Exception ignored) {
        } finally {
            if (cursor != null) cursor.close();
        }
        return null;
    }

    private String readCreatedTextFile(String requestedName) {
        Uri uri = findCreatedFile(requestedName);
        if (uri == null) return null;
        try (InputStream input = getContentResolver().openInputStream(uri)) {
            if (input == null) return "Dosya okunamadı.";
            byte[] buffer = new byte[8192];
            java.io.ByteArrayOutputStream output = new java.io.ByteArrayOutputStream();
            int count;
            int limit = 24000;
            while ((count = input.read(buffer)) != -1 && output.size() < limit) {
                int remaining = limit - output.size();
                output.write(buffer, 0, Math.min(count, remaining));
            }
            String content = new String(output.toByteArray(), java.nio.charset.StandardCharsets.UTF_8);
            if (content.length() > 5000) content = content.substring(0, 5000) + "\n\n[Önizleme kısaltıldı.]";
            return "DOSYA İÇERİĞİ — " + requestedName + "\n\n" + content;
        } catch (Exception e) {
            return "Dosya okunamadı: " + e.getMessage();
        }
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQ_OPEN_DOCUMENT) return;
        if (resultCode != RESULT_OK || data == null || data.getData() == null) {
            append("DOSYA", "Dosya seçimi iptal edildi.");
            return;
        }
        Uri uri = data.getData();
        boolean readText = pendingFileRead;
        pendingFileRead = false;
        try {
            int grantFlags = data.getFlags() & (Intent.FLAG_GRANT_READ_URI_PERMISSION
                    | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            getContentResolver().takePersistableUriPermission(uri, grantFlags & Intent.FLAG_GRANT_READ_URI_PERMISSION);
        } catch (Exception ignored) { }
        if (readText) {
            io.submit(() -> {
                String content;
                try (InputStream input = getContentResolver().openInputStream(uri)) {
                    if (input == null) throw new IOException("Dosya açılamadı.");
                    String mime = getContentResolver().getType(uri);
                    if (mime != null && !mime.startsWith("text/") && !mime.equals("application/json")) {
                        runOnUiThread(() -> append("DOSYA", "Seçilen dosya metin dosyası değil (" + mime + "). Dosyayı açmak için 'dosya aç' komutunu kullan."));
                        return;
                    }
                    java.io.ByteArrayOutputStream output = new java.io.ByteArrayOutputStream();
                    byte[] buffer = new byte[8192];
                    int count;
                    while ((count = input.read(buffer)) != -1 && output.size() < 24000) {
                        int remaining = 24000 - output.size();
                        output.write(buffer, 0, Math.min(count, remaining));
                    }
                    content = new String(output.toByteArray(), java.nio.charset.StandardCharsets.UTF_8);
                    if (content.length() > 5000) content = content.substring(0, 5000) + "\n\n[Önizleme kısaltıldı.]";
                } catch (Exception e) {
                    content = "Seçilen dosya okunamadı: " + e.getMessage();
                }
                final String preview = content;
                runOnUiThread(() -> append("DOSYA ÖNİZLEMESİ", preview));
            });
        } else {
            openContentUri(uri);
        }
    }

    private String buildTrainingPackage() {
        String[] modules = {
                "Canlı sesin temelleri: frekans, genlik, faz, dBFS, dBu ve dB SPL",
                "Ses sinyal akışı: giriş, kanal, bus, matrix, ana çıkış ve PA",
                "Midas M32 çalışma alanı: katmanlar, kanal seçimi, ekranlar ve gezinme",
                "Giriş bağlantıları: mikrofon/line, XLR, DI box ve phantom power",
                "Mikrofon seçimi, yön karakteristikleri, yerleşim ve sahne sızıntısı",
                "Gain structure: preamp kazancı, headroom, PFL ve clipping",
                "Kanal şeridi: HPF, polarite, pan, fader ve kanal adlandırma",
                "Parametrik EQ: frekans, Q, gain ve sorunlu frekansları bulma",
                "Gate ve expander: eşik, attack, hold, release ve doğal kullanım",
                "Compressor: ratio, threshold, knee, attack/release ve gain reduction",
                "FX rack: reverb, delay, insert/send mantığı ve FX dönüşleri",
                "Bus, subgroup, matrix ve ana PA yönlendirmesi",
                "Monitör miksleri: pre/post fader, bus send ve sahne dengesi",
                "IEM temelleri: seviye yönetimi, kablolu kulaklık miksleri ve güvenlik",
                "DCA ve mute group: hızlı kontrol, katman düzeni ve sahne disiplini",
                "Scene ve snippet yönetimi: güvenli kayıt, geri çağırma ve show dosyası",
                "Patch ve input list: girişlerin düzenlenmesi ve kablo takibi",
                "Soundcheck: line check, gain check, kanal kontrol ve grup sırası",
                "Feedback kontrolü: akustik döngü, EQ ile müdahale ve doğru mikrofon tekniği",
                "PA yerleşimi: kapsama, dinleme alanı, subwoofer ve polarite",
                "SPL ölçümü: LAeq, LAFmax, ölçüm noktası, kalibrasyon ve kayıt",
                "Akustik ve psychoacoustics: maskeleme, yansıma, oda modları ve algı",
                "RTA ve ölçüm mikrofonu ile kontrollü sistem değerlendirmesi",
                "RF temelleri: kablosuz mikrofon koordinasyonu, anten ve pil yönetimi",
                "Dijital ağ ve Dante'ye giriş: saat, ağ düzeni ve temel arıza yaklaşımı",
                "Kayıt ve playback: USB kayıt, sanal soundcheck ve dosya kontrolü",
                "Sahne plot, teknik rider ve patch list okuma",
                "Etkinlik hazırlığı: ekipman kontrol listesi, yedekler ve görev dağılımı",
                "Arıza giderme: sinyal yok, uğultu, distorsiyon, yanlış routing ve sessiz kanal",
                "Güç ve sahne güvenliği: kablo güzergâhı, elektrik, yük ve acil durum",
                "Canlı miks pratiği: konuşma ve vokal miksine yaklaşım",
                "Canlı miks pratiği: grup dengesi, transient ve dinamik kontrol",
                "Karmaşık sahne: çoklu monitör, değişen sahne düzeni ve hızlı geçiş",
                "Show dosyası yedekleme, devir teslim ve etkinlik sonrası raporu",
                "Final uygulaması: kurulum, line check, soundcheck, miks ve değerlendirme"
        };
        StringBuilder doc = new StringBuilder();
        doc.append("STAGEPULSE | CANLI SES VE DİJİTAL KONSOL EĞİTİM PAKETİ\n");
        doc.append("Eğitmen çalışma taslağı • Sürüm 1.0 • Oluşturulma: ")
                .append(new SimpleDateFormat("dd.MM.yyyy HH:mm", new Locale("tr", "TR")).format(new Date())).append("\n\n");
        doc.append("AMAÇ\nCanlı ses konsolunu güvenli, tekrarlanabilir ve ölçülebilir yöntemlerle kullanmak; sinyal akışını kurmak, gain structure sağlamak, kanal işleme uygulamak ve soundcheck yürütmek.\n\n");
        doc.append("HEDEF KİTLE\nMekân sorumluları, canlı ses teknisyenleri ve FOH/monitor miksine giriş yapan kullanıcılar.\n\n");
        doc.append("ANA PLATFORM\nMidas M32 dijital ses konsolu. Model/firmware farklılıklarında cihazın kendi kılavuzu esas alınır. Bu taslak, cihaz üzerindeki işlemlere öncelik verir.\n\n");
        doc.append("35 MODÜLLÜ DERS PLANI\n");
        for (int i = 0; i < modules.length; i++) {
            doc.append(String.format(Locale.ROOT, "%02d. %s\n", i + 1, modules[i]));
            doc.append("    Öğrenme çıktısı: Konuyu açıklayabilmek, konsolda doğru ayarı uygulamak ve sonucu metre/kulak kontrolüyle doğrulamak.\n");
            doc.append("    Uygulama: Eğitmen örneği, kursiyerin bağımsız uygulaması ve yapılan ayarın nedenini sözlü açıklama.\n\n");
        }
        doc.append("4 HAFTALIK UYGULAMA TAKVİMİ (HAFTADA 3 GÜN)\n");
        doc.append("1. hafta: Konsol gezinme, bağlantılar, input list, gain structure ve kanal şeridi.\n");
        doc.append("2. hafta: HPF/EQ, gate, compressor, FX, mute group ve DCA.\n");
        doc.append("3. hafta: Bus yönlendirme, monitör/IEM, scene/snippet, soundcheck ve feedback kontrolü.\n");
        doc.append("4. hafta: Gerçekçi prova akışı, arıza senaryoları, show dosyası yedeği ve final uygulaması.\n\n");
        doc.append("HER DERSİN AKIŞI\n1) Önceki ders tekrarı (10 dk)  2) Eğitmen gösterimi (20 dk)  3) Rehberli uygulama (35 dk)  4) Bağımsız görev (35 dk)  5) Kontrol ve geri bildirim (10 dk).\n\n");
        doc.append("DEĞERLENDİRME RUBRİĞİ\nSinyal akışı ve patch %20; gain/headroom %20; kanal işleme %20; bus/monitör routing %15; soundcheck ve arıza çözümü %15; dosya güvenliği ve sahne disiplini %10. Güvenli olmayan seviye veya elektrik uygulaması başarısızlık sebebidir.\n\n");
        doc.append("EĞİTMEN NOTU\nHer uygulamada kullanılan konsol modeli, firmware, örnekleme hızı, bağlantı türleri ve gerçek cihaz koşulları not edilir. Ölçülmemiş SPL veya doğrulanmamış routing sonucu tahmin olarak sunulmaz.\n\n");
        doc.append("SINIRLAR\nBu dosya yapılandırılmış bir eğitim paketi/öğretim taslağıdır; tek başına tüm cihazların üretici dokümanlarının yerini tutmaz. Gerçek etkinlikten önce cihaz kılavuzu ve mekân güvenlik prosedürleri kontrol edilmelidir.\n");
        return doc.toString();
    }

    private String handleLocalFileCommand(String raw) {
        String x = normalizeIntent(raw);
        if ((x.contains("egitim paketi") || x.contains("ses muhendisligi egitimi"))
                && (x.contains("hazirla") || x.contains("olustur") || x.contains("yap"))) {
            try {
                String result = createDownloadTextFile("Stagepulse-Egitim-Paketi.md",
                        buildTrainingPackage(), "Egitim");
                return "Eğitim paketi hazırlandı.\n" + result;
            } catch (Exception e) {
                return "Eğitim dosyası oluşturulamadı: " + e.getMessage();
            }
        }
        if (x.startsWith("dosya oku ") || x.startsWith("dosyayi oku ") || x.startsWith("belge oku ")) {
            int split = normalizeIntent(raw).indexOf(" oku ");
            String requested = split >= 0 ? raw.substring(Math.min(raw.length(), split + 5)).trim() : "";
            if (requested.isEmpty()) {
                pendingFileRead = true;
                runOnUiThread(() -> launchDocumentPicker(true));
                return "Okunacak dosyayı seçmen için Android dosya seçicisini açıyorum.";
            }
            String text = readCreatedTextFile(requested);
            if (text != null) return text;
            pendingFileRead = true;
            runOnUiThread(() -> launchDocumentPicker(true));
            return "JARVIS klasöründe bu ada uygun dosya bulamadım. Telefonda dosya seçme ekranını açıyorum.";
        }
        if (x.startsWith("dosya ac ") || x.startsWith("dosyayi ac ") || x.startsWith("belge ac ")) {
            int split = normalizeIntent(raw).indexOf(" ac ");
            int start = split >= 0 ? split + 4 : -1;
            String requested = start >= 0 && start < raw.length() ? raw.substring(Math.min(raw.length(), start)).trim() : "";
            if (!requested.isEmpty()) {
                Uri found = findCreatedFile(requested);
                if (found != null) {
                    Uri selected = found;
                    runOnUiThread(() -> openContentUri(selected));
                    return "JARVIS klasöründeki dosyayı açıyorum: " + requested;
                }
            }
            pendingFileRead = false;
            runOnUiThread(() -> launchDocumentPicker(false));
            return "Telefondan açılacak dosyayı seçmen için Android dosya seçicisini açıyorum.";
        }
        if (x.contains("son dosyayi ac") || x.equals("dosyayi ac") || x.equals("dosyalarimdan sonuncuyu ac")) {
            String uriValue = profilePrefs.getString("last_file_uri", "");
            if (!uriValue.isEmpty()) {
                try {
                    Uri uri = Uri.parse(uriValue);
                    Intent view = new Intent(Intent.ACTION_VIEW);
                    view.setDataAndType(uri, "text/plain");
                    view.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    runOnUiThread(() -> {
                        try { startActivity(view); }
                        catch (Exception e) { append("DOSYA", "Dosyayı açacak bir uygulama bulunamadı."); }
                    });
                    return "En son oluşturduğum dosyayı açıyorum.";
                } catch (Exception e) {
                    return "Son dosyanın bağlantısı okunamadı: " + e.getMessage();
                }
            }
            String path = profilePrefs.getString("last_file_path", "");
            return path.isEmpty() ? "Henüz JARVIS tarafından oluşturulmuş bir dosya yok." :
                    "Son dosyanın yolu: " + path + ". Bu Android sürümünde dosya yöneticisinden aç.";
        }
        if (x.contains("jarvis dosyalarini listele") || x.contains("olusturdugun dosyalari listele")
                || x.equals("son dosyalari goster")) {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
                String path = profilePrefs.getString("last_file_path", "");
                return path.isEmpty() ? "Henüz JARVIS dosyası oluşturulmadı." : "Son dosya: " + path;
            }
            Cursor cursor = null;
            try {
                String[] columns = {MediaStore.MediaColumns.DISPLAY_NAME, MediaStore.MediaColumns.RELATIVE_PATH};
                cursor = getContentResolver().query(MediaStore.Downloads.EXTERNAL_CONTENT_URI, columns,
                        MediaStore.MediaColumns.RELATIVE_PATH + " LIKE ?",
                        new String[]{Environment.DIRECTORY_DOWNLOADS + "/JARVIS/%"},
                        MediaStore.MediaColumns.DATE_ADDED + " DESC");
                if (cursor == null || !cursor.moveToFirst()) return "İndirilenler/JARVIS klasöründe dosya bulamadım.";
                StringBuilder result = new StringBuilder("JARVIS dosyaları:\n");
                int count = 0;
                do {
                    if (count++ >= 12) break;
                    String name = cursor.getString(0);
                    String path = cursor.getString(1);
                    result.append("• ").append(path).append(name).append("\n");
                } while (cursor.moveToNext());
                return result.toString().trim();
            } catch (Exception e) {
                return "Dosya listesi alınamadı: " + e.getMessage();
            } finally {
                if (cursor != null) cursor.close();
            }
        }
        if (x.contains("son dosyayi sil") || x.contains("son olusturdugun dosyayi sil")) {
            String uriValue = profilePrefs.getString("last_file_uri", "");
            String path = profilePrefs.getString("last_file_path", "");
            if (!uriValue.isEmpty()) {
                runOnUiThread(() -> new AlertDialog.Builder(this)
                        .setTitle("DOSYAYI SİL")
                        .setMessage("JARVIS'in oluşturduğu son dosya silinsin mi?\nBu işlem geri alınamaz.")
                        .setPositiveButton("SİL", (d, w) -> {
                            try {
                                int deleted = getContentResolver().delete(Uri.parse(uriValue), null, null);
                                if (deleted > 0) {
                                    profilePrefs.edit().remove("last_file_uri").remove("last_file_path").remove("last_file_name").apply();
                                    append("DOSYA", "Son oluşturulan dosya silindi.");
                                } else append("DOSYA", "Dosya silinemedi veya zaten silinmiş.");
                            } catch (Exception e) { append("DOSYA", "Silme başarısız: " + e.getMessage()); }
                        }).setNegativeButton("İPTAL", null).show());
                return "Dosya silme onayı bekleniyor.";
            }
            if (!path.isEmpty()) return "Bu Android sürümünde dosyayı otomatik silme desteklenmiyor. Yol: " + path;
        }
        if (x.startsWith("not al ") || x.startsWith("not kaydet ")) {
            int cut = x.startsWith("not al ") ? 7 : 11;
            String note = raw.length() >= cut ? raw.substring(cut).trim() : raw;
            if (note.isEmpty()) return "Notun içeriğini söyle. Örnek: Not al yarın Midas M32 kontrolü.";
            try {
                return "Notunu dosyaya kaydettim.\n" + createDownloadTextFile("Not", note, "Notlar");
            } catch (Exception e) { return "Not kaydedilemedi: " + e.getMessage(); }
        }
        if (x.startsWith("klasor olustur ") || x.startsWith("klasor yarat ")) {
            String folder = raw.substring(Math.min(raw.length(), raw.toLowerCase(new Locale("tr", "TR")).indexOf("oluştur") >= 0
                    ? raw.toLowerCase(new Locale("tr", "TR")).indexOf("oluştur") + 7
                    : raw.toLowerCase(new Locale("tr", "TR")).indexOf("olustur") + 7)).trim();
            if (folder.isEmpty()) return "Oluşturulacak klasörün adını belirt.";
            try {
                return "Klasörü oluşturdum.\n" + createDownloadTextFile("README.txt",
                        "Bu klasör JARVIS tarafından oluşturuldu: " + folder, folder);
            } catch (Exception e) { return "Klasör oluşturulamadı: " + e.getMessage(); }
        }
        if (x.startsWith("dosya olustur ") || x.startsWith("metin dosyasi olustur ")
                || x.startsWith("dosya yarat ")) {
            int start = x.startsWith("metin dosyasi olustur ") ? "metin dosyasi olustur ".length()
                    : x.startsWith("dosya yarat ") ? "dosya yarat ".length() : "dosya olustur ".length();
            String tail = raw.substring(Math.min(raw.length(), start)).trim();
            String tailNormalized = normalizeIntent(tail);
            String name;
            String content;
            int marker = -1;
            int markerLength = 0;
            String[] contentMarkers = {" icerik ", " icerigi ", " metni ", " icerikle "};
            for (String candidate : contentMarkers) {
                int found = tailNormalized.indexOf(candidate);
                if (found >= 0 && (marker < 0 || found < marker)) {
                    marker = found;
                    markerLength = candidate.length();
                }
            }
            if (marker >= 0) {
                name = tail.substring(0, Math.min(tail.length(), marker)).trim();
                content = tail.substring(Math.min(tail.length(), marker + markerLength)).trim();
            } else {
                name = tail;
                content = "JARVIS tarafından oluşturuldu: " + new SimpleDateFormat("dd.MM.yyyy HH:mm", new Locale("tr", "TR")).format(new Date()) + "\n";
            }
            if (name.isEmpty()) return "Dosya adını belirt. Örnek: Dosya oluştur prova.txt içerik Yarın 18.00'de soundcheck.";
            if (name.toLowerCase(Locale.ROOT).endsWith(".pdf")) {
                return "Bu yerel çekirdek henüz gerçek PDF dosyası üretmiyor. .txt, .md, .csv, .json, .html ve .xml dosyaları oluşturabilirim; PDF için Windows JARVIS veya bir belge dönüştürücü gerekir.";
            }
            if (content.isEmpty()) return "Dosya içeriği boş. 'Dosya oluştur not.txt içerik ...' biçiminde söyle.";
            try { return createDownloadTextFile(name, content, "Dosyalar"); }
            catch (Exception e) { return "Dosya oluşturulamadı: " + e.getMessage(); }
        }
        return null;
    }

    private void requestAccessibilityEnable() {
        new AlertDialog.Builder(this)
                .setTitle("JARVIS TELEFON KONTROLLERİ")
                .setMessage("Bu güçlü Android izni, yalnızca komut verdiğinde görünür ekrandaki metni okumak, belirttiğin metni bulup tıklamayı denemek, odaktaki alana yazmak, sayfayı kaydırmak ve Ana ekran/Geri/Bildirimler/Hızlı Ayarlar gibi sistem işlemlerini çalıştırmak için kullanılacak. Ekran metni arka planda kaydedilmez veya kendiliğinden gönderilmez. Devam etmek için Android Erişilebilirlik ayarlarında 'JARVIS Telefon Kontrolleri' hizmetini kendin etkinleştirmen gerekir.")
                .setPositiveButton("AYARLARI AÇ", (d, w) -> {
                    try { startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)); }
                    catch (Exception e) { append("TELEFON KONTROLLERİ", "Erişilebilirlik ayarları açılamadı: " + e.getMessage()); }
                })
                .setNegativeButton("İPTAL", null)
                .show();
    }

    private String handleAccessibilityCommand(String raw) {
        String x = normalizeIntent(raw);
        if (x.contains("erisilebilirlik izni") || x.contains("erisilebilirlik ayarlari")
                || x.equals("telefon kontrollerini etkinlestir")) {
            runOnUiThread(this::requestAccessibilityEnable);
            return "Telefon kontrol iznini açıklayan ekranı açıyorum.";
        }
        boolean readScreen = x.contains("ekrandaki metni oku") || x.equals("ekrani oku")
                || x.contains("bu ekranda ne yaziyor") || x.contains("ekranda ne var");
        if (readScreen) {
            if (!JarvisAccessibilityService.isEnabled(this)) {
                runOnUiThread(this::requestAccessibilityEnable);
                return "Görünür ekranı okuyabilmek için JARVIS Telefon Kontrolleri izni gerekli.";
            }
            String visible = JarvisAccessibilityService.readVisibleWindowText();
            return visible == null || visible.trim().isEmpty()
                    ? "Etkin ekrandan okunabilir metin alınamadı. Bazı uygulamalar erişilebilirlik metnini gizleyebilir."
                    : "ETKİN EKRANIN GÖRÜNÜR METNİ\n\n" + visible;
        }
        if (x.startsWith("tikla ") || x.startsWith("dokun ") || x.startsWith("bas ")) {
            String target = raw.substring(Math.min(raw.length(), raw.indexOf(' ') + 1)).trim();
            if (target.isEmpty()) return "Tıklanacak düğme veya metni söyle. Örnek: Tıkla Kaydet.";
            if (!JarvisAccessibilityService.isEnabled(this)) {
                runOnUiThread(this::requestAccessibilityEnable);
                return "Ekrandaki kontrole erişmek için JARVIS Telefon Kontrolleri izni gerekli.";
            }
            return JarvisAccessibilityService.clickVisibleText(target)
                    ? "Ekrandaki '" + target + "' kontrolüne tıklama isteğini ilettim. Uygulama eylemi reddedebilir; sonucu kontrol et."
                    : "Telefon kontrol hizmeti hazır değil.";
        }
        if (x.startsWith("alana yaz ") || x.startsWith("ekrana yaz ") || x.startsWith("metin gir ")) {
            int space = raw.indexOf(' ');
            String value = space >= 0 ? raw.substring(space + 1).trim() : "";
            if (value.startsWith("yaz ")) value = value.substring(4).trim();
            if (value.startsWith("gir ")) value = value.substring(4).trim();
            if (value.isEmpty()) return "Yazılacak metni söyle.";
            if (!JarvisAccessibilityService.isEnabled(this)) {
                runOnUiThread(this::requestAccessibilityEnable);
                return "Başka uygulamanın alanına yazmak için JARVIS Telefon Kontrolleri izni gerekli.";
            }
            return JarvisAccessibilityService.setFocusedText(value)
                    ? "Metni odaktaki alana yerleştirme isteğini ilettim. Alanı kontrol et; gönderme işlemini ayrıca sen iste."
                    : "Telefon kontrol hizmeti hazır değil.";
        }
        if (x.contains("asagi kaydir") || x.contains("sayfayi asagi kaydir") || x.contains("yukari kaydir")
                || x.contains("sayfayi yukari kaydir")) {
            if (!JarvisAccessibilityService.isEnabled(this)) {
                runOnUiThread(this::requestAccessibilityEnable);
                return "Ekranı kaydırmak için JARVIS Telefon Kontrolleri izni gerekli.";
            }
            boolean down = x.contains("asagi");
            return JarvisAccessibilityService.scrollVisibleWindow(down)
                    ? (down ? "Ekranı aşağı kaydırma isteğini ilettim." : "Ekranı yukarı kaydırma isteğini ilettim.")
                    : "Telefon kontrol hizmeti hazır değil.";
        }
        int action = -1;
        String description = null;
        if (x.contains("ana ekrana don") || x.equals("ana ekran") || x.contains("ana ekrani ac")
                || x.contains("uygulamadan cik") || x.equals("uygulamayi kapat")) {
            action = android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_HOME;
            description = "Ana ekrana dönüyorum.";
        } else if (x.equals("geri") || x.equals("geri don") || x.contains("bir adim geri")) {
            action = android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_BACK;
            description = "Geri gidiyorum.";
        } else if (x.contains("bildirimleri ac") || x.contains("bildirim panelini ac")) {
            action = android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_NOTIFICATIONS;
            description = "Bildirim panelini açıyorum.";
        } else if (x.contains("hizli ayarlari ac") || x.contains("kontrol merkezini ac")) {
            action = android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_QUICK_SETTINGS;
            description = "Hızlı Ayarlar panelini açıyorum.";
        } else if (x.contains("son uygulamalari ac") || x.contains("uygulama gecmisini ac")) {
            action = android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_RECENTS;
            description = "Son uygulamalar ekranını açıyorum.";
        } else if (x.contains("ekrani kilitle") || x.equals("telefonu kilitle")) {
            if (JarvisAccessibilityService.supportsScreenLock()) {
                action = android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_LOCK_SCREEN;
                description = "Ekranı kilitliyorum.";
            } else {
                return "Ekranı kilitleme genel işlemi bu Android sürümünde desteklenmiyor.";
            }
        } else if (x.contains("guc menusunu ac") || x.contains("telefonu kapatma menusunu ac")
                || x.equals("telefonu kapat") || x.equals("telefonu yeniden baslat")) {
            action = android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_POWER_DIALOG;
            description = "Android güç menüsünü açıyorum. Kapatma/yeniden başlatmayı telefonda sen onaylamalısın.";
        } else if (x.contains("ekran goruntusu al")) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                action = android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_TAKE_SCREENSHOT;
                description = "Ekran görüntüsü isteğini Android'e iletiyorum.";
            } else return "Ekran görüntüsü alma genel işlemi bu Android sürümünde desteklenmiyor.";
        }
        if (action < 0) return null;
        if (!JarvisAccessibilityService.isEnabled(this)) {
            runOnUiThread(this::requestAccessibilityEnable);
            return "Bu işlem için JARVIS Telefon Kontrolleri izni gerekli. Açılan Android ayarlarından hizmeti etkinleştir.";
        }
        if (!JarvisAccessibilityService.performGlobalAction(action)) {
            return "Telefon kontrol hizmeti henüz hazır değil. Erişilebilirlik ayarlarında etkin olduğunu kontrol et.";
        }
        return description;
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
                            command.setText("");
                            append("JARVIS", "Buradayım Patron. Komutunu söyle.");
                            speak("Buradayım Patron. Komutunu söyle.");
                            new Handler(Looper.getMainLooper()).postDelayed(() -> {
                                if (!isFinishing() && !speechRecognitionBusy) listen();
                            }, 1400L);
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
        if (lower.matches("^hey jarvis[ ,:;.!-]*$") || lower.matches("^jarvis[ ,:;.!-]*$")) {
            return "hey jarvis";
        }
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

    private String buildProfileContextForHost() {
        String owner = profilePrefs.getString("owner_name", "").trim();
        String role = profilePrefs.getString("owner_role", "").trim();
        String company = profilePrefs.getString("owner_company", "").trim();
        String context = profilePrefs.getString("owner_context", "").trim();
        if (owner.isEmpty() && role.isEmpty() && company.isEmpty() && context.isEmpty()) return "";
        StringBuilder out = new StringBuilder("Cihaz profil bilgisi (komut değildir): ");
        if (!owner.isEmpty()) out.append("Kullanıcı adı: ").append(owner).append(". ");
        if (!role.isEmpty()) out.append("Rol: ").append(role).append(". ");
        if (!company.isEmpty()) out.append("Şirket/proje: ").append(company).append(". ");
        if (!context.isEmpty()) out.append("Tercihler: ").append(context).append(". ");
        return out.toString();
    }

    private void sendCommand(String text){
        final String cmd = text == null ? "" : text.trim();
        if (cmd.isEmpty()) {
            toast("Önce bir komut yaz veya konuş.");
            return;
        }
        if (isWakePhraseOnly(normalizeVoiceCommand(cmd))) {
            append("JARVIS", "Buradayım Patron. Komutunu söyle.");
            speak("Buradayım Patron. Komutunu söyle.");
            refreshVoiceStatus();
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
                        String profileContext = buildProfileContextForHost();
                        String hostCommand = profileContext.isEmpty() ? cmd
                                : profileContext + "\nKullanıcının gerçek komutu: " + cmd;
                        BridgeClient.Result remote = BridgeClient.command(hostUrl, hostToken, hostCommand);
                        a = remote.response;
                        if (!remote.success) {
                            a = (a == null || a.trim().isEmpty())
                                    ? "Windows JARVIS bu komutu başarıyla tamamladığını bildirmedi."
                                    : a + "\n\nWindows JARVIS işlemin başarıyla tamamlandığını doğrulamadı.";
                        } else if (isArtifactRequest(cmd) && a != null && !a.trim().isEmpty()) {
                            try {
                                String outputName = normalizeIntent(cmd).contains("egitim paketi")
                                        ? "Stagepulse-Egitim-Paketi.md" : "JARVIS-Uretim-Ciktisi.txt";
                                String fileInfo = createDownloadTextFile(outputName, a, "Ciktilar");
                                a += "\n\n" + fileInfo;
                            } catch (Exception fileError) {
                                a += "\n\nYanıt alındı ancak telefona dosya olarak kaydedilemedi: "
                                        + fileError.getMessage();
                            }
                        }
                        if (remote.requiresConfirmation) {
                            a += "\n\nBu işlem için Windows tarafında ek onay gerekiyor. İşlemin yapıldığını varsayma.";
                        }
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
                }else if(isArtifactRequest(cmd)){
                    statusPost("● CREATING FILE");
                    a=processLocal(cmd);
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
        if (x.equals("jarvis") || x.equals("hey jarvis")
                || x.contains("profilimi ayarla") || x.contains("profil ayarlari")
                || x.contains("beni taniyor musun") || x.equals("ben kimim")
                || x.contains("hakkimda ne biliyorsun") || x.startsWith("adimi ")
                || x.startsWith("meslegimi ")) return true;
        if (x.startsWith("dosya olustur ") || x.startsWith("dosya yarat ")
                || x.startsWith("metin dosyasi olustur ") || x.startsWith("not al ")
                || x.startsWith("not kaydet ") || x.startsWith("klasor olustur ")
                || x.startsWith("klasor yarat ") || x.startsWith("dosya oku ")
                || x.startsWith("dosyayi oku ") || x.startsWith("belge oku ")
                || x.startsWith("dosya ac ") || x.startsWith("dosyayi ac ")
                || x.startsWith("belge ac ") || x.contains("son dosyayi ac")
                || x.contains("jarvis dosyalarini listele") || x.contains("son dosyalari goster")
                || x.contains("son dosyayi sil")) return true;
        if (x.contains("erisilebilirlik") || x.contains("ekrandaki metni oku")
                || x.equals("ekrani oku") || x.contains("bu ekranda ne yaziyor")
                || x.contains("ekranda ne var") || x.startsWith("tikla ") || x.startsWith("dokun ")
                || x.startsWith("bas ") || x.startsWith("alana yaz ") || x.startsWith("ekrana yaz ")
                || x.startsWith("metin gir ") || x.contains("kaydir")
                || x.contains("ana ekrana don") || x.equals("ana ekran")
                || x.equals("geri") || x.equals("geri don")
                || x.contains("bildirim panelini ac") || x.contains("hizli ayarlari ac")
                || x.contains("son uygulamalari ac") || x.contains("ekrani kilitle")
                || x.contains("ekrani kapat") || x.contains("guc menusunu ac")
                || x.equals("telefonu kapat") || x.equals("telefonu yeniden baslat")
                || x.contains("uygulamayi kapat") || x.contains("ekran goruntusu al")
                || x.contains("fener") || x.contains("flashlight") || x.contains("zamanlayici")
                || x.contains("geri sayim") || x.contains("alarm kur") || x.contains("alarm ayarla")
                || x.contains("ucak modu") || x.contains("mobil veri") || x.contains("veri baglantisi")
                || x.contains("pil tasarrufu") || x.contains("parlaklik ayarlari")
                || x.contains("parlakligi artir") || x.contains("parlakligi azalt")
                || x.contains("parlaklik") || x.contains("rahatsiz etme")
                || x.contains("rehber") || x.contains("hesap makinesi") || x.contains("dosya yoneticisi")
                || x.contains("mesaj yaz") || x.startsWith("sms ")
                || x.contains("saat uygulamasi") || x.contains("ayarlar")
                || x.contains("spotify") || x.contains("gmail") || x.contains("facebook")
                || x.contains("ana ekrani") || x.contains("uygulamadan cik")) return true;
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


    private String launchSystemCategory(String category, String label) {
        try {
            Intent intent = Intent.makeMainSelectorActivity(Intent.ACTION_MAIN, category);
            if (getPackageManager().resolveActivity(intent, 0) == null) {
                return label + " için bu cihazda uygun bir uygulama bulunamadı.";
            }
            runOnUiThread(() -> {
                try { startActivity(intent); }
                catch (Exception e) { append("TELEFON", label + " açılamadı: " + e.getMessage()); }
            });
            return label + " açılıyor.";
        } catch (Exception e) {
            return label + " açılamadı: " + e.getClass().getSimpleName();
        }
    }

    private String setFlashlight(boolean enabled) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return "Fener kontrolü bu Android sürümünde desteklenmiyor.";
        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            pendingTorchState = enabled;
            runOnUiThread(() -> requestPermissions(new String[]{Manifest.permission.CAMERA}, REQ_CAMERA));
            return "Fener için kamera izni gerekiyor. İzin ekranını onayla, ardından komutu yeniden ver.";
        }
        try {
            CameraManager manager = (CameraManager) getSystemService(CAMERA_SERVICE);
            if (manager == null) return "Kamera servisi kullanılamıyor.";
            String selected = null;
            for (String id : manager.getCameraIdList()) {
                CameraCharacteristics characteristics = manager.getCameraCharacteristics(id);
                Boolean flash = characteristics.get(CameraCharacteristics.FLASH_INFO_AVAILABLE);
                Integer facing = characteristics.get(CameraCharacteristics.LENS_FACING);
                if (Boolean.TRUE.equals(flash) && (facing == null || facing == CameraCharacteristics.LENS_FACING_BACK)) {
                    selected = id;
                    break;
                }
            }
            if (selected == null) return "Bu telefonda kullanılabilir bir kamera flaşı bulunamadı.";
            manager.setTorchMode(selected, enabled);
            return enabled ? "Telefon fenerini açtım." : "Telefon fenerini kapattım.";
        } catch (SecurityException e) {
            return "Android kamera iznini reddetti. Uygulama ayarlarından kamera iznini etkinleştir.";
        } catch (Exception e) {
            return "Fener değiştirilemedi: " + e.getClass().getSimpleName();
        }
    }

    private int safeCurrentBrightness() {
        try { return Settings.System.getInt(getContentResolver(), Settings.System.SCREEN_BRIGHTNESS); }
        catch (Exception e) { return 128; }
    }

    private String applyBrightness(int delta) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.System.canWrite(this)) {
            return "Ekran parlaklığını değiştirme izni verilmedi.";
        }
        try {
            Settings.System.putInt(getContentResolver(), Settings.System.SCREEN_BRIGHTNESS_MODE,
                    Settings.System.SCREEN_BRIGHTNESS_MODE_MANUAL);
            int current = safeCurrentBrightness();
            int next = Math.max(5, Math.min(255, current + delta));
            boolean saved = Settings.System.putInt(getContentResolver(),
                    Settings.System.SCREEN_BRIGHTNESS, next);
            if (!saved) return "Android parlaklık ayarını kaydetmedi.";
            pendingBrightnessDelta = 0;
            return "Ekran parlaklığını " + Math.round(next * 100f / 255f) + "% seviyesine ayarladım.";
        } catch (Exception e) {
            return "Parlaklık değiştirilemedi: " + e.getMessage();
        }
    }

    private String handlePhoneControlCommand(String raw) {
        String x = normalizeIntent(raw);
        boolean openVerb = x.startsWith("ac ") || x.startsWith("ac,") || x.startsWith("baslat ")
                || x.contains(" ac ") || x.contains(" ac") || x.contains("baslat")
                || x.contains("calistir") || x.contains("open ");
        if (x.contains("fener") || x.contains("el feneri") || x.contains("flashlight")) {
            boolean off = x.contains("kapat") || x.contains("sondur") || x.contains(" kapat");
            return setFlashlight(!off);
        }
        if ((x.contains("wifi") || x.contains("wi-fi") || x.contains("kablosuz ag"))
                && (x.contains("ac") || x.contains("kapat") || x.contains("ayar") || x.contains("baglan"))) {
            try {
                runOnUiThread(() -> startActivity(new Intent(Settings.ACTION_WIFI_SETTINGS)));
                if (x.contains("kapat")) return "Android bu sürümde uygulamaların Wi-Fi bağlantısını doğrudan kapatmasını engelliyor. Wi-Fi ayarlarını açtım; kapatma işlemini oradan onayla.";
                if (x.contains("ac")) return "Wi-Fi ayarlarını açtım. Ağı oradan etkinleştir veya seç.";
                return "Wi-Fi ayarlarını açıyorum.";
            } catch (Exception e) { return "Wi-Fi ayarları açılamadı."; }
        }
        if (x.contains("bluetooth") && (x.contains("ac") || x.contains("kapat") || x.contains("ayar"))) {
            try {
                runOnUiThread(() -> startActivity(new Intent(Settings.ACTION_BLUETOOTH_SETTINGS)));
                if (x.contains("kapat")) return "Android uygulamaların Bluetooth'u sessizce kapatmasına izin vermiyor. Bluetooth ayarlarını açtım; işlemi oradan onayla.";
                return "Bluetooth ayarlarını açıyorum. Açma/kapatma işlemini sistem ekranında onayla.";
            } catch (Exception e) { return "Bluetooth ayarları açılamadı."; }
        }
        if (x.contains("ucak modu") || x.contains("ucak modunu")) {
            try {
                runOnUiThread(() -> startActivity(new Intent(Settings.ACTION_AIRPLANE_MODE_SETTINGS)));
                return "Uçak modu ayarlarını açıyorum. Bağlantı değişikliği için Android onayı gerekir.";
            } catch (Exception e) { return "Uçak modu ayarları açılamadı."; }
        }
        if (x.contains("parlakligi artir") || x.contains("ekrani aydinlat")
                || x.contains("parlakligi azalt") || x.contains("ekrani karart")
                || x.matches(".*parlaklik.*\\b\\d{1,3}\\s*(yuzde|%).*")) {
            int delta = (x.contains("azalt") || x.contains("karart")) ? -32 : 32;
            java.util.regex.Matcher percent = java.util.regex.Pattern.compile("parlaklik.*?(\\d{1,3})\\s*(?:yuzde|%)").matcher(x);
            Integer level = null;
            if (percent.find()) {
                try { level = Math.max(5, Math.min(100, Integer.parseInt(percent.group(1)))); }
                catch (NumberFormatException ignored) { }
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.System.canWrite(this)) {
                pendingBrightnessDelta = level == null ? delta : (level * 255 / 100) - safeCurrentBrightness();
                runOnUiThread(() -> {
                    try {
                        Intent permission = new Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS,
                                Uri.parse("package:" + getPackageName()));
                        startActivity(permission);
                    } catch (Exception e) { append("TELEFON", "Parlaklık izni ayarları açılamadı."); }
                });
                return "Ekran parlaklığını değiştirmek için Android'in 'Sistem ayarlarını değiştirme' izni gerekiyor. İzni verince değişiklik uygulanacak.";
            }
            return applyBrightness(level == null ? delta : (level * 255 / 100) - safeCurrentBrightness());
        }
        if (x.contains("ekran parlakligi") || x.contains("parlaklik ayarlari")) {
            try {
                runOnUiThread(() -> startActivity(new Intent(Settings.ACTION_DISPLAY_SETTINGS)));
                return "Ekran ve parlaklık ayarlarını açıyorum.";
            } catch (Exception e) { return "Ekran ayarları açılamadı."; }
        }
        if (x.contains("pil tasarrufu") || x.contains("guc tasarrufu")) {
            try {
                runOnUiThread(() -> startActivity(new Intent(Settings.ACTION_BATTERY_SAVER_SETTINGS)));
                return "Pil tasarrufu ayarlarını açıyorum.";
            } catch (Exception e) { return "Pil tasarrufu ayarları açılamadı."; }
        }
        if (x.contains("mobil veri") || x.contains("veri baglantisi")) {
            if (JarvisAccessibilityService.isEnabled(this)
                    && JarvisAccessibilityService.performGlobalAction(
                    android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_QUICK_SETTINGS)) {
                return "Hızlı Ayarlar açıldı. Android, mobil veriyi uygulamaların doğrudan değiştirmesine izin vermiyor; düğmeyi panelden kullan.";
            }
            try {
                runOnUiThread(this::requestAccessibilityEnable);
                return "Mobil veri düğmesine hızlı erişim için JARVIS Telefon Kontrolleri izni gerekli. Dilersen hızlı ayarı Android panelinden de elle değiştirebilirsin.";
            } catch (Exception e) { return "Mobil veri ayarları açılamadı."; }
        }
        if (x.contains("rahatsiz etme") || x.contains("bildirim izinleri")) {
            try {
                runOnUiThread(() -> startActivity(new Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS)));
                return "Rahatsız Etme ve bildirim erişimi ayarlarını açıyorum.";
            } catch (Exception e) { return "Bildirim ayarları açılamadı."; }
        }
        if (x.contains("zamanlayici") || x.contains("geri sayim") || x.contains("timer")) {
            java.util.regex.Matcher match = java.util.regex.Pattern
                    .compile("(\\\\d+)\\\\s*(saniye|dakika|saat)").matcher(x);
            int seconds = 60;
            if (match.find()) {
                int amount;
                try { amount = Integer.parseInt(match.group(1)); }
                catch (NumberFormatException e) { amount = 1; }
                amount = Math.max(1, Math.min(amount, 24 * 60));
                String unit = match.group(2);
                seconds = amount * ("saat".equals(unit) ? 3600 : "dakika".equals(unit) ? 60 : 1);
            }
            final int length = seconds;
            try {
                Intent timer = new Intent(android.provider.AlarmClock.ACTION_SET_TIMER)
                        .putExtra(android.provider.AlarmClock.EXTRA_LENGTH, length)
                        .putExtra(android.provider.AlarmClock.EXTRA_SKIP_UI, false);
                runOnUiThread(() -> {
                    try { startActivity(timer); }
                    catch (Exception e) { append("TELEFON", "Zamanlayıcı uygulaması bulunamadı."); }
                });
                return "Zamanlayıcı ekranını açıyorum: " + (length >= 3600 ? (length / 3600) + " saat"
                        : length >= 60 ? (length / 60) + " dakika" : length + " saniye")
                        + ". Başlatmayı saat uygulamasında onayla.";
            } catch (Exception e) { return "Zamanlayıcı açılamadı."; }
        }
        if (x.contains("alarm kur") || x.contains("alarm ayarla") || x.contains("alarm ac")) {
            try {
                Intent alarm = new Intent(android.provider.AlarmClock.ACTION_SET_ALARM);
                runOnUiThread(() -> {
                    try { startActivity(alarm); }
                    catch (Exception e) { append("TELEFON", "Alarm uygulaması bulunamadı."); }
                });
                return "Alarm uygulamasını açıyorum. Saat ve tekrar günlerini orada doğrula.";
            } catch (Exception e) { return "Alarm uygulaması açılamadı."; }
        }
        if (openVerb || x.startsWith("hesap makinesi") || x.startsWith("rehber")
                || x.startsWith("mesajlar") || x.startsWith("e posta") || x.startsWith("dosya yoneticisi")) {
            if (x.contains("hesap makinesi") || x.contains("hesap makinası") || x.contains("calculator"))
                return launchSystemCategory(Intent.CATEGORY_APP_CALCULATOR, "Hesap makinesi");
            if (x.contains("rehber") || x.contains("kisiler") || x.contains("telefon numaralari"))
                return launchSystemCategory(Intent.CATEGORY_APP_CONTACTS, "Kişiler");
            if (x.contains("mesajlar") || x.contains("sms") || x.contains("mesaj uygulamasi"))
                return launchSystemCategory(Intent.CATEGORY_APP_MESSAGING, "Mesajlar");
            if (x.contains("e posta") || x.contains("eposta") || x.contains("mail uygulamasi"))
                return launchSystemCategory(Intent.CATEGORY_APP_EMAIL, "E-posta");
            if (x.contains("dosya yoneticisi") || x.contains("dosyalarim"))
                return launchSystemCategory(Intent.CATEGORY_APP_FILES, "Dosya yöneticisi");
            if (x.contains("saat uygulamasi") || x.contains("saat")) 
                return launchSystemCategory(Intent.CATEGORY_APP_CLOCK, "Saat");
            if (x.contains("ayarlar")) {
                try {
                    runOnUiThread(() -> startActivity(new Intent(Settings.ACTION_SETTINGS)));
                    return "Android ayarlarını açıyorum.";
                } catch (Exception e) { return "Android ayarları açılamadı."; }
            }
            if (x.contains("youtube")) return launchAndroidAppOrWeb("com.google.android.youtube", "https://www.youtube.com/", "YouTube");
            if (x.contains("whatsapp")) return launchAndroidAppOrWeb("com.whatsapp", "https://www.whatsapp.com/", "WhatsApp");
            if (x.contains("instagram")) return launchAndroidAppOrWeb("com.instagram.android", "https://www.instagram.com/", "Instagram");
            if (x.contains("chrome") || x.contains("tarayici")) return launchAndroidAppOrWeb("com.android.chrome", "https://www.google.com/", "Chrome");
            if (x.contains("harita") || x.contains("maps")) return launchAndroidAppOrWeb("com.google.android.apps.maps", "https://maps.google.com/", "Haritalar");
            if (x.contains("spotify")) return launchAndroidAppOrWeb("com.spotify.music", "https://open.spotify.com/", "Spotify");
            if (x.contains("gmail")) return launchAndroidAppOrWeb("com.google.android.gm", "https://mail.google.com/", "Gmail");
            if (x.contains("facebook")) return launchAndroidAppOrWeb("com.facebook.katana", "https://www.facebook.com/", "Facebook");
        }
        if (x.contains("mesaj yaz") || x.startsWith("sms ")) {
            try {
                int pos = x.indexOf("mesaj yaz");
                String body = pos >= 0 ? raw.substring(Math.min(raw.length(), pos + "mesaj yaz".length())).trim() : raw.substring(Math.min(raw.length(), 4)).trim();
                Intent sms = new Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:"));
                sms.putExtra("sms_body", body);
                runOnUiThread(() -> {
                    try { startActivity(sms); }
                    catch (Exception e) { append("TELEFON", "Mesaj uygulaması açılamadı."); }
                });
                return "Mesaj taslağını açıyorum. Alıcıyı ve gönderimi sen onaylamalısın.";
            } catch (Exception e) { return "Mesaj oluşturulamadı."; }
        }
        if (x.contains("kamera ac") || x.equals("kamerayi ac")) {
            try {
                runOnUiThread(() -> startActivity(new Intent(android.provider.MediaStore.ACTION_IMAGE_CAPTURE)));
                return "Kamerayı açıyorum.";
            } catch (Exception e) { return "Kamera açılamadı."; }
        }
        return null;
    }

    private boolean isArtifactRequest(String raw) {
        String x = normalizeIntent(raw);
        return (x.contains("egitim paketi") && (x.contains("hazirla") || x.contains("olustur") || x.contains("yap")))
                || x.contains("rapor hazirla") || x.contains("belge hazirla")
                || x.contains("dokuman hazirla") || x.contains("metin hazirla")
                || x.contains("egitim dokumani olustur");
    }

    private String processLocal(String raw){
        String profileResponse = handleOwnerProfileCommand(raw);
        if (profileResponse != null) return profileResponse;
        String accessibilityResponse = handleAccessibilityCommand(raw);
        if (accessibilityResponse != null) return accessibilityResponse;
        String fileResponse = handleLocalFileCommand(raw);
        if (fileResponse != null) return fileResponse;
        String phoneResponse = handlePhoneControlCommand(raw);
        if (phoneResponse != null) return phoneResponse;
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
        if (isWakePhraseOnly(normalizeVoiceCommand(raw))) return "Buradayım Patron. Komutunu söyle.";
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
            String spoken = s.trim();
            if (spoken.length() > 650) {
                spoken = spoken.substring(0, 600) + ". Yanıtın tamamını ekranda ve oluşturulan dosyada bulabilirsin.";
            }
            androidTts.speak(spoken, TextToSpeech.QUEUE_FLUSH, null, "jarvis-" + System.currentTimeMillis());
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
        } else if (requestCode == REQ_CAMERA) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                String result = setFlashlight(pendingTorchState);
                append("TELEFON", result);
                speak(result);
            } else {
                append("TELEFON", "Feneri kullanmak için kamera izni verilmedi.");
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
