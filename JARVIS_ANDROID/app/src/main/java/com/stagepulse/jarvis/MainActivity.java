package com.stagepulse.jarvis;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.PendingIntent;
import android.content.*;
import android.database.Cursor;
import android.provider.ContactsContract;
import android.content.pm.PackageManager;
import android.content.pm.PackageInstaller;
import android.os.*;
import android.provider.Settings;
import android.net.Uri;
import android.speech.*;
import android.view.Gravity;
import android.view.inputmethod.EditorInfo;
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
    private static final int REQ_CONTACT=9002;
    private boolean pendingListenPermission = false;
    private boolean speechListening = false;
    private final ExecutorService io=Executors.newSingleThreadExecutor();
    private EditText command;
    private Button textSendButton;
    private TextView status,chat;
    private HudView hud;
    private SpeechRecognizer speech;
    private PiperTts piper;
    private android.speech.tts.TextToSpeech systemTts;
    private boolean systemTtsReady = false;
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
        initPiper();
        initSpeech();
        append("JARVIS","PATRON, bağımsız Android çekirdeği hazır.");
        checkForUpdates(false);
    }

    private TextView tv(String s,int size,int color){
        TextView v=new TextView(this); v.setText(s); v.setTextSize(size); v.setTextColor(color); return v;
    }

    private void buildUi(){
        LinearLayout root=new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(18,12,18,12); root.setBackgroundColor(0xFF050505);
        LinearLayout top=new LinearLayout(this); top.setOrientation(LinearLayout.VERTICAL);
        TextView title=tv("J.A.R.V.I.S.",27,gold()); title.setTypeface(null,1); top.addView(title);
        top.addView(tv("JUST A RATHER VERY INTELLIGENT SYSTEM   //   STAGEPULSE",10,muted()));
        status=tv("● ONLINE",11,gold()); status.setTypeface(null,1); top.addView(status); root.addView(top);
        boolean landscape = getResources().getConfiguration().orientation == android.content.res.Configuration.ORIENTATION_LANDSCAPE;
        hud=new HudView(this);
        chat=tv("",12,white()); chat.setGravity(Gravity.BOTTOM); chat.setPadding(12,12,12,12); chat.setBackgroundColor(panel());
        ScrollView scroll=new ScrollView(this); scroll.setBackgroundColor(panel()); scroll.addView(chat);
        if (landscape) {
            LinearLayout workArea = new LinearLayout(this);
            workArea.setOrientation(LinearLayout.HORIZONTAL);
            LinearLayout.LayoutParams hudParams = new LinearLayout.LayoutParams(0, -1, 0.48f);
            LinearLayout.LayoutParams chatParams = new LinearLayout.LayoutParams(0, -1, 0.52f);
            workArea.addView(hud, hudParams);
            workArea.addView(scroll, chatParams);
            root.addView(workArea, new LinearLayout.LayoutParams(-1, 0, 1));
        } else {
            root.addView(hud, new LinearLayout.LayoutParams(-1, 0, 0.42f));
            root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 0.58f));
        }
        LinearLayout inputRow=new LinearLayout(this);
        inputRow.setOrientation(LinearLayout.HORIZONTAL);
        inputRow.setGravity(Gravity.CENTER_VERTICAL);

        command=new EditText(this);
        command.setHint("Mesajını yaz...");
        command.setHintTextColor(muted());
        command.setTextColor(white());
        command.setMinLines(2);
        command.setMaxLines(4);
        command.setImeOptions(EditorInfo.IME_ACTION_SEND);
        command.setBackgroundColor(panel());
        command.setPadding(14,12,14,12);
        inputRow.addView(command,new LinearLayout.LayoutParams(0,-2,1));

        textSendButton=button("GÖNDER");
        textSendButton.setContentDescription("Yazılı komutu gönder");
        inputRow.addView(textSendButton,new LinearLayout.LayoutParams(112,66));
        root.addView(inputRow,new LinearLayout.LayoutParams(-1,-2));

        LinearLayout row=new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        Button voice=button("◉ SES"), agents=button("UZMANLAR"), host=button("BİLGİSAYAR"), update=button("GÜNCELLE"), call=button("ARA");
        row.addView(voice,new LinearLayout.LayoutParams(0,58,1));
        row.addView(agents,new LinearLayout.LayoutParams(0,58,1));
        row.addView(host,new LinearLayout.LayoutParams(0,58,1));
        row.addView(update,new LinearLayout.LayoutParams(0,58,1));
        row.addView(call,new LinearLayout.LayoutParams(0,58,1));
        root.addView(row);

        setContentView(root);
        textSendButton.setOnClickListener(v->sendCommand(command.getText().toString()));
        command.setOnEditorActionListener((v,actionId,event)->{
            if(actionId==EditorInfo.IME_ACTION_SEND){
                sendCommand(command.getText().toString());
                return true;
            }
            return false;
        });
        voice.setOnClickListener(v->listen());
        agents.setOnClickListener(v->showAgents());
        host.setOnClickListener(v->showHostSettings());
        update.setOnClickListener(v->checkForUpdates(true));
        call.setOnClickListener(v->pickContactForCall());
    }

    private void pickContactForCall() {
        try {
            Intent pick = new Intent(Intent.ACTION_PICK, ContactsContract.CommonDataKinds.Phone.CONTENT_URI);
            startActivityForResult(pick, REQ_CONTACT);
        } catch (Exception e) {
            toast("Kişi seçici açılamadı. Telefon uygulamasından numara seçebilirsin.");
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQ_CONTACT || resultCode != RESULT_OK || data == null || data.getData() == null) return;
        try (Cursor cursor = getContentResolver().query(
                data.getData(),
                new String[]{ContactsContract.CommonDataKinds.Phone.NUMBER},
                null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                String number = cursor.getString(0);
                confirmDial(number);
            } else {
                toast("Seçilen kişide telefon numarası bulunamadı.");
            }
        } catch (Exception e) {
            toast("Telefon numarası okunamadı.");
        }
    }

    private boolean handleDialCommand(String text) {
        java.util.regex.Matcher matcher = java.util.regex.Pattern
                .compile("^(?:ara|telefon ara|telefonu ara)\\s+([+0-9() .-]{7,24})$", java.util.regex.Pattern.CASE_INSENSITIVE | java.util.regex.Pattern.UNICODE_CASE)
                .matcher(text == null ? "" : text.trim());
        if (!matcher.matches()) return false;
        String rawNumber = matcher.group(1).trim();
        String digits = rawNumber.replaceAll("\\D", "");
        if (digits.length() < 7 || digits.length() > 15) return false;
        String number = (rawNumber.startsWith("+") ? "+" : "") + digits;
        append("PATRON", text.trim());
        command.setText("");
        confirmDial(number);
        return true;
    }

    private void confirmDial(String number) {
        if (number == null || number.trim().isEmpty()) {
            toast("Telefon numarası bulunamadı.");
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("TELEFON ARAMASI")
                .setMessage("Telefonun arama ekranı açılacak. Aramayı başlatmak için cihazdaki arama düğmesine sen basacaksın.\\n\\n" + number)
                .setPositiveButton("ARAMA EKRANINI AÇ", (dialog, which) -> {
                    try {
                        Intent dial = new Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + Uri.encode(number)));
                        startActivity(dial);
                    } catch (Exception e) {
                        toast("Telefon arama ekranı açılamadı.");
                    }
                })
                .setNegativeButton("İPTAL", null)
                .show();
    }

    private Button button(String s){Button b=new Button(this);b.setText(s);b.setTextColor(gold());b.setTextSize(11);b.setBackgroundColor(panel());return b;}

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

    private void initPiper(){
        piper=new PiperTts(this);
        status.setText("● VOICE INIT");
        piper.initialize(
                () -> runOnUiThread(() -> {
                    status.setText("● ONLINE");
                    status.setTextColor(gold());
                    append("JARVIS","Türkçe DFKI ses motoru hazır. Doğrudan cihaz üzerinde çalışıyorum.");
                    speak("PATRON, bağımsız Android çekirdeği hazır. Türkçe ses motoru da hazır.");
                }),
                () -> runOnUiThread(() -> {
                    status.setText("● VOICE FALLBACK");
                    status.setTextColor(gold());
                    append("JARVIS","Piper başlatılamadı. Android sistemindeki Türkçe ses motoru yedeği deneniyor.");
                    initSystemTtsFallback();
                })
        );
    }

    private void initSystemTtsFallback() {
        if (systemTts != null) return;
        systemTts = new android.speech.tts.TextToSpeech(getApplicationContext(), result -> runOnUiThread(() -> {
            if (systemTts == null) return;
            if (result == android.speech.tts.TextToSpeech.SUCCESS) {
                int languageResult = systemTts.setLanguage(new Locale("tr", "TR"));
                systemTts.setSpeechRate(0.95f);
                systemTtsReady = languageResult != android.speech.tts.TextToSpeech.LANG_MISSING_DATA
                        && languageResult != android.speech.tts.TextToSpeech.LANG_NOT_SUPPORTED;
                if (systemTtsReady) {
                    status.setText("● ONLINE · SYSTEM TTS");
                    status.setTextColor(gold());
                    append("JARVIS","Android sistem ses yedeği hazır. Türkçe ses desteği kullanılabilir.");
                    speak("PATRON, Piper kullanılamadı. Android sistem ses yedeği hazır.");
                } else {
                    status.setText("● VOICE ERROR");
                    status.setTextColor(0xFFFF5555);
                    append("JARVIS","Bu cihazın sistem TTS motorunda Türkçe dil verisi bulunamadı. Ayarlardan Türkçe ses verisini yükleyin.");
                }
            } else {
                systemTtsReady = false;
                status.setText("● VOICE ERROR");
                status.setTextColor(0xFFFF5555);
                append("JARVIS","Piper ve Android sistem ses motoru başlatılamadı.");
            }
        }));
    }

    private void initSpeech(){
        if(!SpeechRecognizer.isRecognitionAvailable(this))return;
        speech=SpeechRecognizer.createSpeechRecognizer(this);
        speech.setRecognitionListener(new RecognitionListener(){
            public void onReadyForSpeech(Bundle b){hud.setActive(true);status.setText("● LISTENING");}
            public void onBeginningOfSpeech(){} public void onRmsChanged(float r){} public void onBufferReceived(byte[] b){}
            public void onEndOfSpeech(){hud.setActive(false);}
            public void onError(int e){speechListening=false;hud.setActive(false);refreshVoiceStatus();append("JARVIS","Ses algılanamadı veya anlaşılmadı. Hata kodu: "+e);}
            public void onResults(Bundle b){speechListening=false;hud.setActive(false);ArrayList<String>x=b.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);if(x!=null&&!x.isEmpty()){command.setText(x.get(0));sendCommand(x.get(0));}}
            public void onPartialResults(Bundle b){} public void onEvent(int t,Bundle b){}
        });
    }

    private void listen(){
        if(speech==null){toast("Bu cihazda konuşma tanıma servisi yok veya cihaz hizmeti kullanılamıyor.");return;}
        if(speechListening){toast("Sesli komut zaten dinleniyor.");return;}
        if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){
            pendingListenPermission=true;
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},REQ_AUDIO);
            return;
        }
        Intent i=new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        i.putExtra(RecognizerIntent.EXTRA_LANGUAGE,"tr-TR");
        i.putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE,"tr-TR");
        i.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS,3);
        i.putExtra(RecognizerIntent.EXTRA_PROMPT,"JARVIS'a Türkçe komut verin");
        try{
            speechListening=true;
            speech.startListening(i);
        }catch(Exception e){
            speechListening=false;
            hud.setActive(false);
            append("JARVIS","Sesli komut başlatılamadı: "+e.getClass().getSimpleName());
            refreshVoiceStatus();
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults){
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if(requestCode!=REQ_AUDIO)return;
        boolean granted=grantResults.length>0 && grantResults[0]==PackageManager.PERMISSION_GRANTED;
        boolean resume=pendingListenPermission;
        pendingListenPermission=false;
        if(granted && resume){
            listen();
        }else if(resume){
            toast("Sesli komut için mikrofon izni gerekli.");
        }
    }

    private void sendCommand(String text){
        final String cmd=text.trim();
        if(cmd.isEmpty()){toast("Önce gönderilecek metni yaz.");return;}
        if(handleDialCommand(cmd)) return;
        if(textSendButton!=null)textSendButton.setEnabled(false);
        append("PATRON",cmd);
        command.setText("");
        hud.setActive(true);
        status.setText("● PROCESSING");
        io.submit(()->{
            String a;
            try{
                String hostUrl = bridgePrefs.getString("url", "").trim();
                String hostToken = bridgePrefs.getString("token", "").trim();
                if (!hostUrl.isEmpty() && !hostToken.isEmpty()) {
                    statusPost("● WINDOWS JARVIS");
                    BridgeClient.Result remote = BridgeClient.command(hostUrl, hostToken, cmd);
                    a = remote.response;
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
            runOnUiThread(()->{
                hud.setActive(false);
                if(textSendButton!=null)textSendButton.setEnabled(true);
                if(!status.getText().toString().startsWith("● AGENT"))refreshVoiceStatus();
                append("JARVIS",answer);
                speak(answer);
            });
        });
    }

    private void statusPost(String text){runOnUiThread(()->status.setText(text));}

    private void refreshVoiceStatus(){
        boolean piperReady=piper!=null&&piper.isReady();
        boolean ready=piperReady||systemTtsReady;
        status.setText(piperReady?"● ONLINE · PIPER":(systemTtsReady?"● ONLINE · SYSTEM TTS":"● VOICE ERROR"));
        status.setTextColor(ready?gold():0xFFFF5555);
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

    private String processLocal(String raw){
        String c=raw.toLowerCase(new Locale("tr","TR")).trim();
        if(c.equals("ajanlar")||c.equals("agentler")||c.contains("stagepulse agent"))return AgencyCatalog.listText();
        if(c.contains("aktif ajan")||c.contains("hangi ajan"))return activeAgent==null?"Şu anda aktif bir Stagepulse Agent yok.":"Aktif ajan: "+activeAgent.name+".";
        if(c.contains("merhaba")||c.equals("selam"))return "Merhaba Patron. Android JARVIS çekirdeği hazır.";
        if(c.contains("kimsin"))return "Ben J.A.R.V.I.S. Android sürümüyüm. Bu cihaz üzerinde bağımsız çalışıyorum.";
        if(c.contains("saat"))return "Şu an saat "+new SimpleDateFormat("HH:mm",Locale.getDefault()).format(new Date())+".";
        if(c.contains("tarih")||c.contains("bugün"))return "Bugün "+new SimpleDateFormat("dd MMMM yyyy, EEEE",new Locale("tr","TR")).format(new Date())+".";
        if(c.contains("pil")||c.contains("batarya")){BatteryManager b=(BatteryManager)getSystemService(BATTERY_SERVICE);return "Pil seviyesi yüzde "+b.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)+".";}
        if(c.contains("ayarlar")){try{startActivity(new Intent(Settings.ACTION_SETTINGS));return "Android ayarlarını açıyorum.";}catch(Exception e){return "Android ayarları açılamadı.";}}
        if(c.contains("tarayıcı")||c.contains("internet aç")){try{startActivity(new Intent(Intent.ACTION_VIEW,android.net.Uri.parse("https://www.google.com")));return "Tarayıcıyı açıyorum.";}catch(Exception e){return "Tarayıcı açılamadı.";}}
        if(c.contains("yardım")||c.contains("ne yapabiliyorsun"))return "Saat, tarih, pil, ayarlar, tarayıcı, web araştırması ve Stagepulse uzman ajanlarını çalıştırabiliyorum.";
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

    private void speak(String s){
        if (s == null || s.trim().isEmpty()) return;
        if (piper != null && piper.isReady()) {
            piper.speak(s);
            return;
        }
        if (systemTts != null && systemTtsReady) {
            systemTts.speak(s, android.speech.tts.TextToSpeech.QUEUE_ADD, null,
                    "stagepulse-jarvis-" + System.nanoTime());
        }
    }
    private void append(String who,String msg){chat.append((chat.length()>0?"\n\n":"")+who+"\n"+msg);}
    private void toast(String s){Toast.makeText(this,s,Toast.LENGTH_SHORT).show();}

    @Override protected void onDestroy(){
        if(speech!=null)speech.destroy();
        if(piper!=null)piper.release();
        if(systemTts!=null){systemTts.stop();systemTts.shutdown();systemTts=null;}
        io.shutdownNow();
        super.onDestroy();
    }
}
