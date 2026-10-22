package com.stagepulse.jarvis;

import android.accessibilityservice.AccessibilityService;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import android.provider.Settings;
import android.content.ComponentName;
import android.content.Context;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import java.util.ArrayList;
import android.widget.Toast;
import android.widget.TextView;
import android.view.WindowManager;
import android.view.Gravity;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.TextToSpeech;
import android.speech.SpeechRecognizer;
import android.speech.RecognizerIntent;
import android.speech.RecognitionListener;
import android.provider.MediaStore;
import android.net.Uri;
import android.media.AudioManager;
import android.graphics.drawable.GradientDrawable;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraManager;
import android.graphics.PixelFormat;
import android.graphics.Color;
import android.content.pm.ServiceInfo;
import android.content.pm.PackageManager;
import android.content.SharedPreferences;
import android.content.Intent;
import android.app.PendingIntent;
import android.app.NotificationManager;
import android.app.NotificationChannel;
import android.app.Notification;
import android.Manifest;

public final class JarvisAccessibilityService extends AccessibilityService {
    private static volatile JarvisAccessibilityService instance;
    private static final int VOICE_NOTIFICATION_ID = 24001;
    private static final String VOICE_CHANNEL_ID = "jarvis-accessibility-voice";
    private static final String EXTRA_COMMAND = "jarvis_command";
    private final Handler main = new Handler(Looper.getMainLooper());
    private WindowManager windowManager;
    private TextView overlayButton;
    private SpeechRecognizer overlaySpeech;
    private TextToSpeech overlayTts;
    private volatile boolean overlayTtsReady = false;
    private volatile boolean overlayConversation = false;
    private volatile boolean overlayRecognitionBusy = false;
    private volatile boolean foregroundVoice = false;
    private final java.util.concurrent.ExecutorService remoteWorker =
            java.util.concurrent.Executors.newSingleThreadExecutor();

    @Override public void onServiceConnected() {
        super.onServiceConnected();
        instance = this;
        main.post(() -> {
            showFloatingMicrophone();
            initOverlayTts();
        });
    }

    @Override public void onAccessibilityEvent(AccessibilityEvent event) {
        // No accessibility-event contents are logged or persisted. Screen text is read only
        // when the user explicitly issues a read-screen command.
    }

    @Override public void onInterrupt() {
        stopOverlayVoice();
    }

    @Override public void onDestroy() {
        stopOverlayVoice();
        removeFloatingMicrophone();
        if (overlaySpeech != null) {
            try { overlaySpeech.destroy(); } catch (Exception ignored) {}
            overlaySpeech = null;
        }
        if (overlayTts != null) {
            try { overlayTts.stop(); overlayTts.shutdown(); } catch (Exception ignored) {}
            overlayTts = null;
        }
        remoteWorker.shutdownNow();
        if (instance == this) instance = null;
        super.onDestroy();
    }

    public static boolean isEnabled(Context context) {
        String enabled = Settings.Secure.getString(
                context.getContentResolver(), Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES);
        if (enabled == null || enabled.isEmpty()) return false;
        String expected = new ComponentName(context, JarvisAccessibilityService.class).flattenToString();
        for (String part : enabled.split(":")) {
            if (expected.equalsIgnoreCase(part)) return true;
        }
        return false;
    }

    public static boolean requestGlobalAction(int action) {
        JarvisAccessibilityService current = instance;
        if (current == null) return false;
        current.main.post(() -> current.performGlobalAction(action));
        return true;
    }


    private static String norm(String value) {
        if (value == null) return "";
        return value.toLowerCase(java.util.Locale.ROOT)
                .replace("ı", "i").replace("ş", "s").replace("ğ", "g")
                .replace("ü", "u").replace("ö", "o").replace("ç", "c")
                .trim();
    }

    private AccessibilityNodeInfo findNode(AccessibilityNodeInfo node, String target) {
        if (node == null || target == null || target.trim().isEmpty()) return null;
        CharSequence text = node.getText();
        CharSequence description = node.getContentDescription();
        String label = (text == null ? "" : text.toString()) + " "
                + (description == null ? "" : description.toString());
        if (!label.trim().isEmpty() && norm(label).contains(norm(target))) return node;
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo found = findNode(node.getChild(i), target);
            if (found != null) return found;
        }
        return null;
    }

    private AccessibilityNodeInfo findEditable(AccessibilityNodeInfo node) {
        if (node == null) return null;
        if (node.isEditable() && node.isEnabled()) return node;
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo found = findEditable(node.getChild(i));
            if (found != null) return found;
        }
        return null;
    }

    private boolean clickTextOnMain(String target) {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        AccessibilityNodeInfo node = findNode(root, target);
        while (node != null) {
            if (node.isClickable() && node.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return true;
            node = node.getParent();
        }
        return false;
    }

    private boolean setFocusedTextOnMain(String value) {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        AccessibilityNodeInfo focused = root == null ? null : root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
        if (focused == null) focused = findEditable(root);
        if (focused != null && focused.isEditable()) {
            android.os.Bundle args = new android.os.Bundle();
            args.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, value);
            return focused.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args);
        }
        return false;
    }

    private String visibleTextOnMain() {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return "";
        StringBuilder out = new StringBuilder();
        collectText(root, out);
        return out.toString().trim();
    }

    private void collectText(AccessibilityNodeInfo node, StringBuilder out) {
        if (node == null || out.length() >= 6000) return;
        CharSequence text = node.getText();
        CharSequence description = node.getContentDescription();
        String label = text == null ? "" : text.toString().trim();
        if (label.isEmpty() && description != null) label = description.toString().trim();
        if (!label.isEmpty() && !out.toString().contains(label)) {
            if (out.length() > 0) out.append("\n");
            out.append(label);
        }
        for (int i = 0; i < node.getChildCount() && out.length() < 6000; i++) {
            collectText(node.getChild(i), out);
        }
    }

    private boolean scrollOnMain(boolean down) {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        return scrollFirst(root, down);
    }

    private boolean scrollFirst(AccessibilityNodeInfo node, boolean down) {
        if (node == null) return false;
        if (node.isScrollable()) {
            int action = down ? AccessibilityNodeInfo.ACTION_SCROLL_FORWARD
                    : AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD;
            if (node.performAction(action)) return true;
        }
        for (int i = 0; i < node.getChildCount(); i++) {
            if (scrollFirst(node.getChild(i), down)) return true;
        }
        return false;
    }

    public static boolean clickVisibleText(String target) {
        JarvisAccessibilityService current = instance;
        if (current == null || target == null || target.trim().isEmpty()) return false;
        current.main.post(() -> current.clickTextOnMain(target));
        return true;
    }

    public static boolean setFocusedText(String value) {
        JarvisAccessibilityService current = instance;
        if (current == null || value == null) return false;
        current.main.post(() -> current.setFocusedTextOnMain(value));
        return true;
    }

    public static boolean scrollVisibleWindow(boolean down) {
        JarvisAccessibilityService current = instance;
        if (current == null) return false;
        current.main.post(() -> {
            if (!current.scrollOnMain(down) && Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                android.util.DisplayMetrics dm = current.getResources().getDisplayMetrics();
                float x = dm.widthPixels * 0.5f;
                float y1 = dm.heightPixels * (down ? 0.78f : 0.30f);
                float y2 = dm.heightPixels * (down ? 0.30f : 0.78f);
                android.graphics.Path path = new android.graphics.Path();
                path.moveTo(x, y1);
                path.lineTo(x, y2);
                android.accessibilityservice.GestureDescription gesture =
                        new android.accessibilityservice.GestureDescription.Builder()
                                .addStroke(new android.accessibilityservice.GestureDescription.StrokeDescription(
                                        path, 0, 350)).build();
                current.dispatchGesture(gesture, null, null);
            }
        });
        return true;
    }

    public static String readVisibleWindowText() {
        JarvisAccessibilityService current = instance;
        if (current == null) return "";
        if (Looper.myLooper() == Looper.getMainLooper()) return "Ekran metni ana iş parçacığında eşzamanlı okunamaz.";
        final java.util.concurrent.atomic.AtomicReference<String> result =
                new java.util.concurrent.atomic.AtomicReference<>("");
        final java.util.concurrent.CountDownLatch latch = new java.util.concurrent.CountDownLatch(1);
        current.main.post(() -> {
            try { result.set(current.visibleTextOnMain()); }
            finally { latch.countDown(); }
        });
        try { latch.await(1500, java.util.concurrent.TimeUnit.MILLISECONDS); }
        catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        return result.get();
    }


    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void showFloatingMicrophone() {
        if (overlayButton != null) return;
        try {
            windowManager = (WindowManager) getSystemService(WINDOW_SERVICE);
            if (windowManager == null) return;
            TextView button = new TextView(this);
            button.setText("MIC");
            button.setTextSize(10);
            button.setTextColor(Color.rgb(10, 10, 10));
            button.setTypeface(null, 1);
            button.setGravity(Gravity.CENTER);
            button.setContentDescription("JARVIS yüzen sesli komut düğmesi. Dokunarak konuşmayı başlat veya durdur.");
            button.setPadding(dp(5), dp(5), dp(5), dp(5));
            GradientDrawable background = new GradientDrawable();
            background.setColor(Color.rgb(212, 175, 55));
            background.setCornerRadius(dp(28));
            background.setStroke(dp(2), Color.rgb(18, 18, 18));
            button.setBackground(background);
            button.setElevation(dp(8));
            button.setOnClickListener(v -> toggleOverlayVoice());
            WindowManager.LayoutParams params = new WindowManager.LayoutParams(
                    dp(54), dp(54),
                    WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                    WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                            | WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL
                            | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                    PixelFormat.TRANSLUCENT);
            params.gravity = Gravity.RIGHT | Gravity.CENTER_VERTICAL;
            params.x = dp(7);
            params.y = 0;
            windowManager.addView(button, params);
            overlayButton = button;
        } catch (Exception e) {
            overlayButton = null;
            Toast.makeText(this, "JARVIS yüzen mikrofonu açılamadı: " + e.getClass().getSimpleName(),
                    Toast.LENGTH_LONG).show();
        }
    }

    private void removeFloatingMicrophone() {
        if (windowManager != null && overlayButton != null) {
            try { windowManager.removeView(overlayButton); } catch (Exception ignored) {}
        }
        overlayButton = null;
    }

    private void setFloatingLabel(String label) {
        main.post(() -> {
            if (overlayButton != null) {
                overlayButton.setText(label);
                overlayButton.setContentDescription(overlayConversation
                        ? "JARVIS sesli komut modu etkin. Dokunarak durdur."
                        : "JARVIS sesli komut modu kapalı. Dokunarak başlat.");
            }
        });
    }

    private void toggleOverlayVoice() {
        if (overlayConversation) {
            stopOverlayVoice();
            overlaySpeak("Arka plan sesli komut modu durduruldu.");
        } else {
            startOverlayVoice();
        }
    }

    private void startVoiceForeground() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
                if (manager != null) {
                    NotificationChannel channel = new NotificationChannel(
                            VOICE_CHANNEL_ID, "JARVIS sesli kontrol", NotificationManager.IMPORTANCE_LOW);
                    channel.setDescription("Kullanıcı yüzen mikrofona dokunarak sesli kontrolü başlattığında gösterilir.");
                    manager.createNotificationChannel(channel);
                }
            }
            Intent launch = new Intent(this, MainActivity.class);
            launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
            PendingIntent pending = PendingIntent.getActivity(this, VOICE_NOTIFICATION_ID, launch,
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
            Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                    ? new Notification.Builder(this, VOICE_CHANNEL_ID)
                    : new Notification.Builder(this);
            Notification notification = builder
                    .setSmallIcon(android.R.drawable.ic_btn_speak_now)
                    .setContentTitle("JARVIS sesli kontrol etkin")
                    .setContentText("Ekrandaki altın MIC düğmesine dokunarak durdurabilirsin.")
                    .setContentIntent(pending)
                    .setCategory(Notification.CATEGORY_SERVICE)
                    .setOngoing(true)
                    .build();
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                startForeground(VOICE_NOTIFICATION_ID, notification,
                        ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE);
            } else {
                startForeground(VOICE_NOTIFICATION_ID, notification);
            }
            foregroundVoice = true;
        } catch (Exception e) {
            // Keep the feature user-triggered and surface provider/runtime failures through speech/toast.
            foregroundVoice = false;
        }
    }

    private void stopVoiceForeground() {
        if (!foregroundVoice) return;
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) stopForeground(STOP_FOREGROUND_REMOVE);
            else stopForeground(true);
        } catch (Exception ignored) {}
        foregroundVoice = false;
    }

    private void startOverlayVoice() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            Toast.makeText(this, "Önce JARVIS uygulamasını açıp mikrofon iznini ver.", Toast.LENGTH_LONG).show();
            try {
                Intent intent = new Intent(this, MainActivity.class);
                intent.putExtra("jarvis_request_microphone", true);
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
                startActivity(intent);
            } catch (Exception ignored) {}
            return;
        }
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            Toast.makeText(this, "Bu cihazda kullanılabilir konuşma tanıma hizmeti yok.", Toast.LENGTH_LONG).show();
            return;
        }
        try {
            overlayConversation = true;
            setFloatingLabel("DUR");
            startVoiceForeground();
            if (overlaySpeech == null) {
                overlaySpeech = SpeechRecognizer.createSpeechRecognizer(this);
                overlaySpeech.setRecognitionListener(new RecognitionListener() {
                    @Override public void onReadyForSpeech(Bundle params) { overlayRecognitionBusy = true; }
                    @Override public void onBeginningOfSpeech() { }
                    @Override public void onRmsChanged(float rmsdB) { }
                    @Override public void onBufferReceived(byte[] buffer) { }
                    @Override public void onEndOfSpeech() { overlayRecognitionBusy = false; }
                    @Override public void onError(int error) {
                        overlayRecognitionBusy = false;
                        if (!overlayConversation) return;
                        if (error == SpeechRecognizer.ERROR_NO_MATCH) {
                            overlaySpeak("Anlayamadım Patron. Tekrar söyle.");
                        } else {
                            String detail = error == SpeechRecognizer.ERROR_NETWORK
                                    || error == SpeechRecognizer.ERROR_NETWORK_TIMEOUT
                                    ? "İnternet veya konuşma tanıma sunucusu kullanılamıyor."
                                    : error == SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS
                                    ? "Mikrofon izni gerekli."
                                    : "Arka plan konuşma tanıma durdu. Kodu: " + error;
                            stopOverlayVoice();
                            overlaySpeak(detail);
                        }
                    }
                    @Override public void onResults(Bundle results) {
                        overlayRecognitionBusy = false;
                        ArrayList<String> candidates = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                        String recognized = candidates == null || candidates.isEmpty()
                                ? "" : normalizeOverlayCommand(candidates.get(0));
                        if (recognized.isEmpty()) {
                            overlaySpeak("Komut anlaşılmadı. Tekrar söyle.");
                            return;
                        }
                        handleOverlayCommand(recognized);
                    }
                    @Override public void onPartialResults(Bundle partialResults) { }
                    @Override public void onEvent(int eventType, Bundle params) { }
                });
            }
            startOverlayRecognitionRound();
        } catch (Exception e) {
            stopOverlayVoice();
            Toast.makeText(this, "Arka plan mikrofonu başlatılamadı: " + e.getClass().getSimpleName(),
                    Toast.LENGTH_LONG).show();
        }
    }

    private void startOverlayRecognitionRound() {
        if (!overlayConversation || overlayRecognitionBusy || overlaySpeech == null) return;
        try {
            Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "tr-TR");
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "tr-TR");
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
            intent.putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, false);
            intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 4);
            intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
            intent.putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, getPackageName());
            overlayRecognitionBusy = true;
            setFloatingLabel("DUR");
            overlaySpeech.startListening(intent);
        } catch (Exception e) {
            overlayRecognitionBusy = false;
            stopOverlayVoice();
            overlaySpeak("Sesli tanıma başlatılamadı: " + e.getClass().getSimpleName());
        }
    }

    private void stopOverlayVoice() {
        overlayConversation = false;
        overlayRecognitionBusy = false;
        if (overlaySpeech != null) {
            try { overlaySpeech.cancel(); } catch (Exception ignored) {}
        }
        setFloatingLabel("MIC");
        stopVoiceForeground();
    }

    private void initOverlayTts() {
        if (overlayTts != null) return;
        try {
            overlayTts = new TextToSpeech(this, result -> main.post(() -> {
                if (result != TextToSpeech.SUCCESS || overlayTts == null) return;
                int language = overlayTts.setLanguage(new java.util.Locale("tr", "TR"));
                overlayTtsReady = language != TextToSpeech.LANG_MISSING_DATA
                        && language != TextToSpeech.LANG_NOT_SUPPORTED;
                if (!overlayTtsReady) {
                    int fallback = overlayTts.setLanguage(java.util.Locale.getDefault());
                    overlayTtsReady = fallback != TextToSpeech.LANG_MISSING_DATA
                            && fallback != TextToSpeech.LANG_NOT_SUPPORTED;
                }
                overlayTts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                    @Override public void onStart(String utteranceId) { }
                    @Override public void onError(String utteranceId) {
                        main.post(() -> resumeOverlayListening());
                    }
                    @Override public void onDone(String utteranceId) {
                        main.post(() -> resumeOverlayListening());
                    }
                });
            }));
        } catch (Exception ignored) { overlayTtsReady = false; }
    }

    private void overlaySpeak(String text) {
        if (text == null || text.trim().isEmpty()) {
            resumeOverlayListening();
            return;
        }
        if (overlayTts == null) initOverlayTts();
        if (overlayTtsReady && overlayTts != null) {
            String spoken = text.trim();
            if (spoken.length() > 700) spoken = spoken.substring(0, 650) + ". Devamı uygulamadaki sohbet alanında.";
            overlayTts.speak(spoken, TextToSpeech.QUEUE_FLUSH, null, "jarvis-overlay-" + System.currentTimeMillis());
        } else {
            Toast.makeText(this, text.length() > 160 ? text.substring(0, 160) : text,
                    Toast.LENGTH_LONG).show();
            resumeOverlayListening();
        }
    }

    private void resumeOverlayListening() {
        if (!overlayConversation || overlayRecognitionBusy) return;
        main.postDelayed(() -> {
            if (overlayConversation && !overlayRecognitionBusy) startOverlayRecognitionRound();
        }, 450L);
    }

    private String normalizeOverlayCommand(String raw) {
        String value = raw == null ? "" : raw.toLowerCase(new java.util.Locale("tr", "TR")).trim();
        value = value.replaceAll("\\s+", " ").replace("ı", "i").replace("ş", "s")
                .replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("ç", "c");
        value = value.replaceAll("\\b(heijan biz|hey jervis|hey carvis|hey jarvis|hey cervis|hey djarvis)\\b", "hey jarvis");
        value = value.replaceAll("\\b(jarvis|jervis|carvis|cervis|djarvis)\\b", "jarvis");
        value = value.replaceAll("\\b(pakeylri|pakeyli|paketleri|paketli)\\b", "paketi");
        value = value.replaceAll("\\b(baziela|bazila|haziela|hazirlaa|hazila)\\b", "hazirla");
        if (value.matches("^hey jarvis[ ,:;.!-]*$") || value.matches("^jarvis[ ,:;.!-]*$")) return "hey jarvis";
        value = value.replaceAll("\\bhey jarvis[ ,:;.!-]*", "").trim();
        value = value.replaceAll("\\b(egitim paketi hazirla|egitim paketi hazila|egitim paketi baziela|egitim paketini hazirla)\\b", "egitim paketi hazirla");
        return value;
    }

    private void handleOverlayCommand(String raw) {
        String command = normalizeOverlayCommand(raw);
        if (command.isEmpty() || command.equals("hey jarvis") || command.equals("jarvis")) {
            overlaySpeak("Buradayım Patron. Komutunu söyle.");
            return;
        }
        String normalizedCommand = norm(command);
        boolean needsCameraPermission = (normalizedCommand.contains("fener")
                || normalizedCommand.contains("el feneri") || normalizedCommand.contains("flashlight"))
                && checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED;
        boolean needsBrightnessPermission = (normalizedCommand.contains("parlakligi artir")
                || normalizedCommand.contains("parlakligi azalt") || normalizedCommand.contains("ekrani aydinlat")
                || normalizedCommand.contains("ekrani karart"))
                && Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.System.canWrite(this);
        if (needsCameraPermission || needsBrightnessPermission) {
            stopOverlayVoice();
            launchMainForCommand(command);
            return;
        }
        String local = handleOverlayDeviceCommand(command);
        if (local != null) {
            overlaySpeak(local);
            return;
        }
        if (isOverlayDocumentTask(command)) {
            stopOverlayVoice();
            launchMainForCommand(command);
            return;
        }
        SharedPreferences hostPrefs = getSharedPreferences("jarvis_bridge", MODE_PRIVATE);
        String hostUrl = hostPrefs.getString("url", "").trim();
        String token = hostPrefs.getString("token", "").trim();
        if (!hostUrl.isEmpty() && !token.isEmpty()) {
            String profile = buildOverlayProfileContext();
            remoteWorker.submit(() -> {
                try {
                    BridgeClient.Result result = BridgeClient.command(hostUrl, token, command, profile);
                    String response = result.response == null ? "" : result.response.trim();
                    if (response.isEmpty()) response = result.success
                            ? "Windows JARVIS komutu işledi ancak yanıt metni döndürmedi."
                            : "Windows JARVIS işlemin başarıyla tamamlandığını doğrulamadı.";
                    if (!result.success) response += " İşlem başarıyla tamamlanmış olarak doğrulanmadı.";
                    if (result.requiresConfirmation) response += " Ek onay gerekiyor; işlemin yapıldığını varsayma.";
                    String finalResponse = response;
                    main.post(() -> overlaySpeak(finalResponse));
                } catch (Exception e) {
                    main.post(() -> {
                        stopOverlayVoice();
                        launchMainForCommand(command);
                    });
                }
            });
            return;
        }
        stopOverlayVoice();
        launchMainForCommand(command);
    }

    private String buildOverlayProfileContext() {
        SharedPreferences profile = getSharedPreferences("jarvis_profile", MODE_PRIVATE);
        String owner = profile.getString("owner_name", "").trim();
        String role = profile.getString("owner_role", "").trim();
        String company = profile.getString("owner_company", "").trim();
        String context = profile.getString("owner_context", "").trim();
        StringBuilder result = new StringBuilder();
        if (!owner.isEmpty()) result.append("Kullanıcı adı: ").append(owner).append(". ");
        if (!role.isEmpty()) result.append("Rol: ").append(role).append(". ");
        if (!company.isEmpty()) result.append("Şirket/proje: ").append(company).append(". ");
        if (!context.isEmpty()) result.append("Tercihler: ").append(context).append(". ");
        return result.toString();
    }

    private boolean isOverlayDocumentTask(String command) {
        String x = norm(command);
        return (x.contains("egitim paketi") && (x.contains("hazirla") || x.contains("olustur") || x.contains("yap")))
                || x.startsWith("dosya olustur ") || x.startsWith("dosya yarat ")
                || x.startsWith("metin dosyasi olustur ") || x.startsWith("not al ")
                || x.startsWith("not kaydet ") || x.startsWith("klasor olustur ")
                || x.startsWith("klasor yarat ") || x.startsWith("dosya oku ")
                || x.startsWith("dosyayi oku ") || x.startsWith("belge oku ")
                || x.startsWith("dosya ac ") || x.startsWith("dosyayi ac ")
                || x.startsWith("belge ac ") || x.contains("son dosyayi ac")
                || x.contains("jarvis dosyalarini listele") || x.contains("son dosyalari goster")
                || x.contains("son dosyayi sil") || x.contains("rapor hazirla")
                || x.contains("webde bul") || x.contains("internetten bul") || x.contains("internette ara")
                || x.contains("arastir ");
    }

    private String handleOverlayDeviceCommand(String command) {
        String x = norm(command);
        if (x.contains("ekrandaki metni oku") || x.equals("ekrani oku")
                || x.contains("bu ekranda ne yaziyor") || x.contains("ekranda ne var")) {
            String visible = visibleTextOnMain();
            if (visible.isEmpty()) return "Bu ekrandan okunabilir metin alınamadı. Bazı uygulamalar erişilebilirlik metnini gizleyebilir.";
            if (visible.length() > 620) visible = visible.substring(0, 620) + ".";
            return "Ekranda görünen metin: " + visible;
        }
        if (x.startsWith("tikla ") || x.startsWith("dokun ") || x.startsWith("bas ")) {
            int split = x.indexOf(' ');
            String target = split >= 0 ? x.substring(split + 1).trim() : "";
            if (target.isEmpty()) return "Tıklanacak öğeyi belirt. Örnek: Tıkla Kaydet.";
            boolean clicked = clickTextOnMain(target);
            return clicked ? "Ekrandaki öğeye tıklama isteğini gönderdim. Sonucu kontrol et." : "Belirttiğin metne sahip tıklanabilir bir öğe bulamadım.";
        }
        if (x.startsWith("alana yaz ") || x.startsWith("ekrana yaz ") || x.startsWith("metin gir ")) {
            int split = x.indexOf(' ');
            String rest = split >= 0 ? x.substring(split + 1).trim() : "";
            if (rest.startsWith("yaz ")) rest = rest.substring(4).trim();
            if (rest.startsWith("gir ")) rest = rest.substring(4).trim();
            if (rest.isEmpty()) return "Yazılacak metni belirt.";
            boolean typed = setFocusedTextOnMain(rest);
            return typed ? "Metni odaktaki alana yazma isteğini gönderdim. Gönderme işlemini ayrıca sen iste."
                    : "Odakta yazılabilir bir alan bulamadım.";
        }
        if (x.contains("asagi kaydir") || x.contains("sayfayi asagi kaydir")
                || x.contains("yukari kaydir") || x.contains("sayfayi yukari kaydir")) {
            boolean down = x.contains("asagi");
            boolean scrolled = scrollOnMain(down);
            if (!scrolled && Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                android.util.DisplayMetrics dm = getResources().getDisplayMetrics();
                android.graphics.Path path = new android.graphics.Path();
                path.moveTo(dm.widthPixels * 0.5f, dm.heightPixels * (down ? 0.78f : 0.30f));
                path.lineTo(dm.widthPixels * 0.5f, dm.heightPixels * (down ? 0.30f : 0.78f));
                android.accessibilityservice.GestureDescription gesture = new android.accessibilityservice.GestureDescription.Builder()
                        .addStroke(new android.accessibilityservice.GestureDescription.StrokeDescription(path, 0, 350))
                        .build();
                scrolled = dispatchGesture(gesture, null, null);
            }
            return scrolled ? "Ekranı kaydırdım." : "Ekrandaki alan kaydırılamadı.";
        }

        int action = -1;
        String response = null;
        if (x.contains("ana ekrana don") || x.equals("ana ekran") || x.contains("ana ekrani ac")) {
            action = GLOBAL_ACTION_HOME; response = "Ana ekrana gidiyorum.";
        } else if (x.equals("geri") || x.equals("geri don") || x.contains("bir adim geri")) {
            action = GLOBAL_ACTION_BACK; response = "Geri gidiyorum.";
        } else if (x.contains("bildirim panelini ac") || x.contains("bildirimleri ac")) {
            action = GLOBAL_ACTION_NOTIFICATIONS; response = "Bildirim panelini açıyorum.";
        } else if (x.contains("hizli ayarlari ac") || x.contains("kontrol merkezini ac") || x.contains("mobil veri")) {
            action = GLOBAL_ACTION_QUICK_SETTINGS; response = "Hızlı Ayarlar panelini açıyorum. Mobil veri ve kablosuz ayarını oradan değiştirebilirsin.";
        } else if (x.contains("son uygulamalari ac") || x.contains("uygulama gecmisini ac")) {
            action = GLOBAL_ACTION_RECENTS; response = "Son uygulamaları açıyorum.";
        } else if (x.contains("ekrani kilitle") || x.equals("telefonu kilitle") || x.contains("ekrani kapat")) {
            if (supportsScreenLock()) { action = GLOBAL_ACTION_LOCK_SCREEN; response = "Ekranı kilitliyorum."; }
            else return "Ekran kilitleme bu Android sürümünde desteklenmiyor.";
        } else if (x.contains("telefonu kapat") || x.contains("telefonu yeniden baslat") || x.contains("guc menusunu ac")) {
            action = GLOBAL_ACTION_POWER_DIALOG; response = "Android güç menüsünü açıyorum. Son işlemi telefonda sen onaylamalısın.";
        } else if (x.contains("ekran goruntusu al")) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) { action = GLOBAL_ACTION_TAKE_SCREENSHOT; response = "Ekran görüntüsü isteğini Android'e iletiyorum."; }
            else return "Bu Android sürümünde erişilebilirlik ekran görüntüsü desteklenmiyor.";
        }
        if (action >= 0) {
            boolean completed = performGlobalAction(action);
            return completed ? response : "Android bu sistem eylemini gerçekleştiremedi.";
        }

        if (x.contains("wifi") || x.contains("wi-fi") || x.contains("bluetooth")
                || x.contains("ucak modu") || x.contains("parlaklik") || x.contains("ekran ayarlari")) {
            String actionName = x.contains("wifi") || x.contains("wi-fi") ? Settings.ACTION_WIFI_SETTINGS
                    : x.contains("bluetooth") ? Settings.ACTION_BLUETOOTH_SETTINGS
                    : x.contains("ucak modu") ? Settings.ACTION_AIRPLANE_MODE_SETTINGS
                    : Settings.ACTION_DISPLAY_SETTINGS;
            return startSystemActivity(actionName, "Android ayarlarını açıyorum.");
        }
        if (x.contains("pil tasarrufu") || x.contains("guc tasarrufu"))
            return startSystemActivity(Settings.ACTION_BATTERY_SAVER_SETTINGS, "Pil tasarrufu ayarlarını açıyorum.");
        if (x.contains("rahatsiz etme") || x.contains("bildirim izinleri"))
            return startSystemActivity(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS, "Bildirim ayarlarını açıyorum.");

        if (x.contains("fener") || x.contains("el feneri") || x.contains("flashlight")) {
            if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
                stopOverlayVoice();
                launchMainForCommand(command);
                return "Fener izni için JARVIS uygulamasını açıyorum.";
            }
            try {
                CameraManager camera = (CameraManager) getSystemService(CAMERA_SERVICE);
                String selected = null;
                if (camera != null) {
                    for (String id : camera.getCameraIdList()) {
                        CameraCharacteristics details = camera.getCameraCharacteristics(id);
                        Boolean available = details.get(CameraCharacteristics.FLASH_INFO_AVAILABLE);
                        Integer facing = details.get(CameraCharacteristics.LENS_FACING);
                        if (Boolean.TRUE.equals(available)
                                && (facing == null || facing == CameraCharacteristics.LENS_FACING_BACK)) {
                            selected = id;
                            break;
                        }
                    }
                }
                if (selected == null) return "Bu telefonda kullanılabilir bir fener bulunamadı.";
                boolean off = x.contains("kapat") || x.contains("sondur");
                camera.setTorchMode(selected, !off);
                return off ? "Telefon fenerini kapattım." : "Telefon fenerini açtım.";
            } catch (Exception e) {
                return "Fener kontrol edilemedi: " + e.getClass().getSimpleName();
            }
        }
        if (x.contains("parlakligi artir") || x.contains("ekrani aydinlat")
                || x.contains("parlakligi azalt") || x.contains("ekrani karart")) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.System.canWrite(this)) {
                stopOverlayVoice();
                launchMainForCommand(command);
                return "Parlaklık ayarı için Android özel iznini açmanı istiyorum.";
            }
            try {
                int current = Settings.System.getInt(getContentResolver(), Settings.System.SCREEN_BRIGHTNESS, 128);
                int change = (x.contains("azalt") || x.contains("karart")) ? -32 : 32;
                int next = Math.max(5, Math.min(255, current + change));
                Settings.System.putInt(getContentResolver(), Settings.System.SCREEN_BRIGHTNESS_MODE,
                        Settings.System.SCREEN_BRIGHTNESS_MODE_MANUAL);
                boolean saved = Settings.System.putInt(getContentResolver(), Settings.System.SCREEN_BRIGHTNESS, next);
                return saved ? "Ekran parlaklığını yüzde " + Math.round(next * 100f / 255f) + " yaptım."
                        : "Android parlaklık ayarını kaydetmedi.";
            } catch (Exception e) { return "Parlaklık değiştirilemedi: " + e.getMessage(); }
        }
        if (x.contains("ses artir") || x.contains("sesi yukselt")) {
            AudioManager audio = (AudioManager) getSystemService(AUDIO_SERVICE);
            if (audio != null) audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_RAISE, AudioManager.FLAG_SHOW_UI);
            return "Medya sesini artırdım.";
        }
        if (x.contains("ses azalt") || x.contains("sesi kis")) {
            AudioManager audio = (AudioManager) getSystemService(AUDIO_SERVICE);
            if (audio != null) audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_LOWER, AudioManager.FLAG_SHOW_UI);
            return "Medya sesini azalttım.";
        }
        if (x.contains("sessize al") || x.contains("sesi kapat")) {
            AudioManager audio = (AudioManager) getSystemService(AUDIO_SERVICE);
            if (audio != null) audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_MUTE, AudioManager.FLAG_SHOW_UI);
            return "Medya sesini kapattım.";
        }
        boolean launchRequested = x.startsWith("ac ") || x.contains(" ac ") || x.endsWith(" ac")
                || x.startsWith("baslat ") || x.contains(" calistir") || x.startsWith("open ")
                || x.contains(" open ") || x.endsWith(" open");
        if (launchRequested) {
            if (x.contains("youtube")) return launchApp("com.google.android.youtube", "https://www.youtube.com/", "YouTube");
            if (x.contains("whatsapp")) return launchApp("com.whatsapp", "https://www.whatsapp.com/", "WhatsApp");
            if (x.contains("instagram")) return launchApp("com.instagram.android", "https://www.instagram.com/", "Instagram");
            if (x.contains("chrome") || x.contains("tarayici")) return launchApp("com.android.chrome", "https://www.google.com/", "Chrome");
            if (x.contains("harita") || x.contains("maps")) return launchApp("com.google.android.apps.maps", "https://maps.google.com/", "Haritalar");
            if (x.contains("spotify")) return launchApp("com.spotify.music", "https://open.spotify.com/", "Spotify");
            if (x.contains("gmail")) return launchApp("com.google.android.gm", "https://mail.google.com/", "Gmail");
            if (x.contains("facebook")) return launchApp("com.facebook.katana", "https://www.facebook.com/", "Facebook");
            if (x.contains("stagepulse.com.tr") || x.contains("stagepulse")) {
                String url = (x.contains("admin") || x.contains("benim sitem") || x.contains("yonetim panel"))
                        ? "https://stagepulse.com.tr/admin/"
                        : (x.contains("personel") ? "https://stagepulse.com.tr/portal/" : "https://stagepulse.com.tr/");
                return openUrl(url, "Stagepulse sayfasını açıyorum.");
            }
            if (x.contains("ayarlar")) return startSystemActivity(Settings.ACTION_SETTINGS, "Android ayarlarını açıyorum.");
            if (x.contains("dosya sec")) return openDocumentPicker();
        }
        if (x.contains("zamanlayici") || x.contains("geri sayim") || x.contains("timer")) {
            int length = 60;
            java.util.regex.Matcher match = java.util.regex.Pattern.compile("(\\d+)\\s*(saniye|dakika|saat)").matcher(x);
            if (match.find()) {
                try {
                    int amount = Math.max(1, Math.min(1440, Integer.parseInt(match.group(1))));
                    length = amount * (match.group(2).equals("saat") ? 3600 : match.group(2).equals("dakika") ? 60 : 1);
                } catch (Exception ignored) {}
            }
            int seconds = length;
            try {
                Intent timer = new Intent(android.provider.AlarmClock.ACTION_SET_TIMER)
                        .putExtra(android.provider.AlarmClock.EXTRA_LENGTH, seconds)
                        .putExtra(android.provider.AlarmClock.EXTRA_SKIP_UI, false);
                timer.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(timer);
                return "Zamanlayıcı ekranını açtım. Başlatmayı saat uygulamasında onayla.";
            } catch (Exception e) { return "Zamanlayıcı açılamadı."; }
        }
        if (x.contains("alarm kur") || x.contains("alarm ayarla")) {
            try {
                Intent alarm = new Intent(android.provider.AlarmClock.ACTION_SET_ALARM);
                alarm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(alarm);
                return "Alarm ekranını açtım. Saat ve tekrar günlerini orada onayla.";
            } catch (Exception e) { return "Alarm ekranı açılamadı."; }
        }
        if (x.contains("kamera ac") || x.equals("kamerayi ac")) {
            try {
                Intent camera = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
                camera.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(camera);
                return "Kamerayı açıyorum.";
            } catch (Exception e) { return "Kamera açılamadı."; }
        }
        if (x.contains("stagepulse.com.tr") || x.contains("stagepulse")) {
            if (x.contains("admin") || x.contains("benim sitem") || x.contains("yonetim panel"))
                return openUrl("https://stagepulse.com.tr/admin/", "Stagepulse yönetim panelini açıyorum.");
            if (x.contains("personel")) return openUrl("https://stagepulse.com.tr/portal/", "Stagepulse personel portalını açıyorum.");
            if (x.contains("site") || x.contains("ac")) return openUrl("https://stagepulse.com.tr/", "Stagepulse ana sitesini açıyorum.");
        }
        return null;
    }

    private String startSystemActivity(String action, String response) {
        try {
            Intent intent = new Intent(action);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
            return response;
        } catch (Exception e) { return "Android ayar ekranı açılamadı: " + e.getMessage(); }
    }

    private String launchApp(String packageName, String fallbackUrl, String label) {
        try {
            Intent intent = getPackageManager().getLaunchIntentForPackage(packageName);
            if (intent != null) {
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(intent);
                return label + " uygulamasını açıyorum.";
            }
        } catch (Exception ignored) {}
        return openUrl(fallbackUrl, label + " web sürümünü açıyorum.");
    }

    private String openUrl(String url, String message) {
        try {
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
            return message;
        } catch (Exception e) { return "Bağlantı açılamadı: " + e.getMessage(); }
    }

    private String openDocumentPicker() {
        try {
            Intent picker = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            picker.addCategory(Intent.CATEGORY_OPENABLE);
            picker.setType("*/*");
            picker.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(picker);
            return "Dosya seçicisini açıyorum.";
        } catch (Exception e) { return "Dosya seçicisi açılamadı."; }
    }

    private void launchMainForCommand(String command) {
        try {
            stopOverlayVoice();
            Intent intent = new Intent(this, MainActivity.class);
            intent.putExtra(EXTRA_COMMAND, command);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP
                    | Intent.FLAG_ACTIVITY_SINGLE_TOP);
            startActivity(intent);
        } catch (Exception e) {
            Toast.makeText(this, "JARVIS komutu uygulamaya aktarılamadı: " + e.getMessage(),
                    Toast.LENGTH_LONG).show();
        }
    }

    private void handleOverlayCommand(String raw) {
        String command = normalizeOverlayCommand(raw);
        if (command.isEmpty() || command.equals("hey jarvis") || command.equals("jarvis")) {
            overlaySpeak("Buradayım Patron. Komutunu söyle.");
            return;
        }
        String local = handleOverlayDeviceCommand(command);
        if (local != null) {
            overlaySpeak(local);
            return;
        }
        if (isOverlayDocumentTask(command)) {
            stopOverlayVoice();
            launchMainForCommand(command);
            return;
        }
        SharedPreferences hostPrefs = getSharedPreferences("jarvis_bridge", MODE_PRIVATE);
        String hostUrl = hostPrefs.getString("url", "").trim();
        String token = hostPrefs.getString("token", "").trim();
        if (!hostUrl.isEmpty() && !token.isEmpty()) {
            String profile = buildOverlayProfileContext();
            remoteWorker.submit(() -> {
                try {
                    BridgeClient.Result result = BridgeClient.command(hostUrl, token, command, profile);
                    String response = result.response == null ? "" : result.response.trim();
                    if (response.isEmpty()) response = result.success
                            ? "Windows JARVIS komutu işledi ancak yanıt metni döndürmedi."
                            : "Windows JARVIS işlemin başarıyla tamamlandığını doğrulamadı.";
                    if (!result.success) response += " İşlem başarıyla tamamlanmış olarak doğrulanmadı.";
                    if (result.requiresConfirmation) response += " Ek onay gerekiyor; işlemin yapıldığını varsayma.";
                    String finalResponse = response;
                    main.post(() -> overlaySpeak(finalResponse));
                } catch (Exception e) {
                    main.post(() -> {
                        stopOverlayVoice();
                        launchMainForCommand(command);
                    });
                }
            });
            return;
        }
        stopOverlayVoice();
        launchMainForCommand(command);
    }

    private String buildOverlayProfileContext() {
        SharedPreferences profile = getSharedPreferences("jarvis_profile", MODE_PRIVATE);
        String owner = profile.getString("owner_name", "").trim();
        String role = profile.getString("owner_role", "").trim();
        String company = profile.getString("owner_company", "").trim();
        String context = profile.getString("owner_context", "").trim();
        StringBuilder result = new StringBuilder();
        if (!owner.isEmpty()) result.append("Kullanıcı adı: ").append(owner).append(". ");
        if (!role.isEmpty()) result.append("Rol: ").append(role).append(". ");
        if (!company.isEmpty()) result.append("Şirket/proje: ").append(company).append(". ");
        if (!context.isEmpty()) result.append("Tercihler: ").append(context).append(". ");
        return result.toString();
    }

    private boolean isOverlayDocumentTask(String command) {
        String x = norm(command);
        return (x.contains("egitim paketi") && (x.contains("hazirla") || x.contains("olustur") || x.contains("yap")))
                || x.startsWith("dosya olustur ") || x.startsWith("dosya yarat ")
                || x.startsWith("metin dosyasi olustur ") || x.startsWith("not al ")
                || x.startsWith("not kaydet ") || x.startsWith("klasor olustur ")
                || x.startsWith("klasor yarat ") || x.startsWith("dosya oku ")
                || x.startsWith("dosyayi oku ") || x.startsWith("belge oku ")
                || x.startsWith("dosya ac ") || x.startsWith("dosyayi ac ")
                || x.startsWith("belge ac ") || x.contains("son dosyayi ac")
                || x.contains("jarvis dosyalarini listele") || x.contains("son dosyalari goster")
                || x.contains("son dosyayi sil") || x.contains("rapor hazirla")
                || x.contains("webde bul") || x.contains("internetten bul") || x.contains("internette ara")
                || x.contains("arastir ");
    }

    private String handleOverlayDeviceCommand(String command) {
        String x = norm(command);
        if (x.contains("ekrandaki metni oku") || x.equals("ekrani oku")
                || x.contains("bu ekranda ne yaziyor") || x.contains("ekranda ne var")) {
            String visible = visibleTextOnMain();
            if (visible.isEmpty()) return "Bu ekrandan okunabilir metin alınamadı. Bazı uygulamalar erişilebilirlik metnini gizleyebilir.";
            if (visible.length() > 620) visible = visible.substring(0, 620) + ".";
            return "Ekranda görünen metin: " + visible;
        }
        if (x.startsWith("tikla ") || x.startsWith("dokun ") || x.startsWith("bas ")) {
            int split = x.indexOf(' ');
            String target = split >= 0 ? x.substring(split + 1).trim() : "";
            if (target.isEmpty()) return "Tıklanacak öğeyi belirt. Örnek: Tıkla Kaydet.";
            boolean clicked = clickTextOnMain(target);
            return clicked ? "Ekrandaki öğeye tıklama isteğini gönderdim. Sonucu kontrol et." : "Belirttiğin metne sahip tıklanabilir bir öğe bulamadım.";
        }
        if (x.startsWith("alana yaz ") || x.startsWith("ekrana yaz ") || x.startsWith("metin gir ")) {
            int split = x.indexOf(' ');
            String rest = split >= 0 ? x.substring(split + 1).trim() : "";
            if (rest.startsWith("yaz ")) rest = rest.substring(4).trim();
            if (rest.startsWith("gir ")) rest = rest.substring(4).trim();
            if (rest.isEmpty()) return "Yazılacak metni belirt.";
            boolean typed = setFocusedTextOnMain(rest);
            return typed ? "Metni odaktaki alana yazma isteğini gönderdim. Gönderme işlemini ayrıca sen iste."
                    : "Odakta yazılabilir bir alan bulamadım.";
        }
        if (x.contains("asagi kaydir") || x.contains("sayfayi asagi kaydir")
                || x.contains("yukari kaydir") || x.contains("sayfayi yukari kaydir")) {
            boolean down = x.contains("asagi");
            boolean scrolled = scrollOnMain(down);
            if (!scrolled && Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                android.util.DisplayMetrics dm = getResources().getDisplayMetrics();
                android.graphics.Path path = new android.graphics.Path();
                path.moveTo(dm.widthPixels * 0.5f, dm.heightPixels * (down ? 0.78f : 0.30f));
                path.lineTo(dm.widthPixels * 0.5f, dm.heightPixels * (down ? 0.30f : 0.78f));
                android.accessibilityservice.GestureDescription gesture = new android.accessibilityservice.GestureDescription.Builder()
                        .addStroke(new android.accessibilityservice.GestureDescription.StrokeDescription(path, 0, 350))
                        .build();
                scrolled = dispatchGesture(gesture, null, null);
            }
            return scrolled ? "Ekranı kaydırdım." : "Ekrandaki alan kaydırılamadı.";
        }

        int action = -1;
        String response = null;
        if (x.contains("ana ekrana don") || x.equals("ana ekran") || x.contains("ana ekrani ac")) {
            action = GLOBAL_ACTION_HOME; response = "Ana ekrana gidiyorum.";
        } else if (x.equals("geri") || x.equals("geri don") || x.contains("bir adim geri")) {
            action = GLOBAL_ACTION_BACK; response = "Geri gidiyorum.";
        } else if (x.contains("bildirim panelini ac") || x.contains("bildirimleri ac")) {
            action = GLOBAL_ACTION_NOTIFICATIONS; response = "Bildirim panelini açıyorum.";
        } else if (x.contains("hizli ayarlari ac") || x.contains("kontrol merkezini ac") || x.contains("mobil veri")) {
            action = GLOBAL_ACTION_QUICK_SETTINGS; response = "Hızlı Ayarlar panelini açıyorum. Mobil veri ve kablosuz ayarını oradan değiştirebilirsin.";
        } else if (x.contains("son uygulamalari ac") || x.contains("uygulama gecmisini ac")) {
            action = GLOBAL_ACTION_RECENTS; response = "Son uygulamaları açıyorum.";
        } else if (x.contains("ekrani kilitle") || x.equals("telefonu kilitle") || x.contains("ekrani kapat")) {
            if (supportsScreenLock()) { action = GLOBAL_ACTION_LOCK_SCREEN; response = "Ekranı kilitliyorum."; }
            else return "Ekran kilitleme bu Android sürümünde desteklenmiyor.";
        } else if (x.contains("telefonu kapat") || x.contains("telefonu yeniden baslat") || x.contains("guc menusunu ac")) {
            action = GLOBAL_ACTION_POWER_DIALOG; response = "Android güç menüsünü açıyorum. Son işlemi telefonda sen onaylamalısın.";
        } else if (x.contains("ekran goruntusu al")) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) { action = GLOBAL_ACTION_TAKE_SCREENSHOT; response = "Ekran görüntüsü isteğini Android'e iletiyorum."; }
            else return "Bu Android sürümünde erişilebilirlik ekran görüntüsü desteklenmiyor.";
        }
        if (action >= 0) {
            boolean completed = performGlobalAction(action);
            return completed ? response : "Android bu sistem eylemini gerçekleştiremedi.";
        }

        if (x.contains("wifi") || x.contains("wi-fi") || x.contains("bluetooth")
                || x.contains("ucak modu") || x.contains("parlaklik") || x.contains("ekran ayarlari")) {
            String actionName = x.contains("wifi") || x.contains("wi-fi") ? Settings.ACTION_WIFI_SETTINGS
                    : x.contains("bluetooth") ? Settings.ACTION_BLUETOOTH_SETTINGS
                    : x.contains("ucak modu") ? Settings.ACTION_AIRPLANE_MODE_SETTINGS
                    : Settings.ACTION_DISPLAY_SETTINGS;
            return startSystemActivity(actionName, "Android ayarlarını açıyorum.");
        }
        if (x.contains("pil tasarrufu") || x.contains("guc tasarrufu"))
            return startSystemActivity(Settings.ACTION_BATTERY_SAVER_SETTINGS, "Pil tasarrufu ayarlarını açıyorum.");
        if (x.contains("rahatsiz etme") || x.contains("bildirim izinleri"))
            return startSystemActivity(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS, "Bildirim ayarlarını açıyorum.");

        if (x.contains("ses artir") || x.contains("sesi yukselt")) {
            AudioManager audio = (AudioManager) getSystemService(AUDIO_SERVICE);
            if (audio != null) audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_RAISE, AudioManager.FLAG_SHOW_UI);
            return "Medya sesini artırdım.";
        }
        if (x.contains("ses azalt") || x.contains("sesi kis")) {
            AudioManager audio = (AudioManager) getSystemService(AUDIO_SERVICE);
            if (audio != null) audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_LOWER, AudioManager.FLAG_SHOW_UI);
            return "Medya sesini azalttım.";
        }
        if (x.contains("sessize al") || x.contains("sesi kapat")) {
            AudioManager audio = (AudioManager) getSystemService(AUDIO_SERVICE);
            if (audio != null) audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_MUTE, AudioManager.FLAG_SHOW_UI);
            return "Medya sesini kapattım.";
        }
        if (x.contains("uygulamayi ac") || x.contains(" uygulamasini ac") || x.startsWith("ac ")) {
            if (x.contains("youtube")) return launchApp("com.google.android.youtube", "https://www.youtube.com/", "YouTube");
            if (x.contains("whatsapp")) return launchApp("com.whatsapp", "https://www.whatsapp.com/", "WhatsApp");
            if (x.contains("instagram")) return launchApp("com.instagram.android", "https://www.instagram.com/", "Instagram");
            if (x.contains("chrome") || x.contains("tarayici")) return launchApp("com.android.chrome", "https://www.google.com/", "Chrome");
            if (x.contains("harita") || x.contains("maps")) return launchApp("com.google.android.apps.maps", "https://maps.google.com/", "Haritalar");
            if (x.contains("spotify")) return launchApp("com.spotify.music", "https://open.spotify.com/", "Spotify");
            if (x.contains("gmail")) return launchApp("com.google.android.gm", "https://mail.google.com/", "Gmail");
            if (x.contains("facebook")) return launchApp("com.facebook.katana", "https://www.facebook.com/", "Facebook");
            if (x.contains("stagepulse.com.tr") || x.contains("stagepulse")) {
                String url = (x.contains("admin") || x.contains("benim sitem") || x.contains("yonetim panel"))
                        ? "https://stagepulse.com.tr/admin/"
                        : (x.contains("personel") ? "https://stagepulse.com.tr/portal/" : "https://stagepulse.com.tr/");
                return openUrl(url, "Stagepulse sayfasını açıyorum.");
            }
            if (x.contains("ayarlar")) return startSystemActivity(Settings.ACTION_SETTINGS, "Android ayarlarını açıyorum.");
            if (x.contains("dosya sec")) return openDocumentPicker();
        }
        if (x.contains("zamanlayici") || x.contains("geri sayim") || x.contains("timer")) {
            int length = 60;
            java.util.regex.Matcher match = java.util.regex.Pattern.compile("(\\d+)\\s*(saniye|dakika|saat)").matcher(x);
            if (match.find()) {
                try {
                    int amount = Math.max(1, Math.min(1440, Integer.parseInt(match.group(1))));
                    length = amount * (match.group(2).equals("saat") ? 3600 : match.group(2).equals("dakika") ? 60 : 1);
                } catch (Exception ignored) {}
            }
            int seconds = length;
            try {
                Intent timer = new Intent(android.provider.AlarmClock.ACTION_SET_TIMER)
                        .putExtra(android.provider.AlarmClock.EXTRA_LENGTH, seconds)
                        .putExtra(android.provider.AlarmClock.EXTRA_SKIP_UI, false);
                timer.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(timer);
                return "Zamanlayıcı ekranını açtım. Başlatmayı saat uygulamasında onayla.";
            } catch (Exception e) { return "Zamanlayıcı açılamadı."; }
        }
        if (x.contains("alarm kur") || x.contains("alarm ayarla")) {
            try {
                Intent alarm = new Intent(android.provider.AlarmClock.ACTION_SET_ALARM);
                alarm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(alarm);
                return "Alarm ekranını açtım. Saat ve tekrar günlerini orada onayla.";
            } catch (Exception e) { return "Alarm ekranı açılamadı."; }
        }
        if (x.contains("kamera ac") || x.equals("kamerayi ac")) {
            try {
                Intent camera = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
                camera.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(camera);
                return "Kamerayı açıyorum.";
            } catch (Exception e) { return "Kamera açılamadı."; }
        }
        if (x.contains("stagepulse.com.tr") || x.contains("stagepulse")) {
            if (x.contains("admin") || x.contains("benim sitem") || x.contains("yonetim panel"))
                return openUrl("https://stagepulse.com.tr/admin/", "Stagepulse yönetim panelini açıyorum.");
            if (x.contains("personel")) return openUrl("https://stagepulse.com.tr/portal/", "Stagepulse personel portalını açıyorum.");
            if (x.contains("site") || x.contains("ac")) return openUrl("https://stagepulse.com.tr/", "Stagepulse ana sitesini açıyorum.");
        }
        return null;
    }

    private String startSystemActivity(String action, String response) {
        try {
            Intent intent = new Intent(action);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
            return response;
        } catch (Exception e) { return "Android ayar ekranı açılamadı: " + e.getMessage(); }
    }

    private String launchApp(String packageName, String fallbackUrl, String label) {
        try {
            Intent intent = getPackageManager().getLaunchIntentForPackage(packageName);
            if (intent != null) {
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(intent);
                return label + " uygulamasını açıyorum.";
            }
        } catch (Exception ignored) {}
        return openUrl(fallbackUrl, label + " web sürümünü açıyorum.");
    }

    private String openUrl(String url, String message) {
        try {
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
            return message;
        } catch (Exception e) { return "Bağlantı açılamadı: " + e.getMessage(); }
    }

    private String openDocumentPicker() {
        try {
            Intent picker = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            picker.addCategory(Intent.CATEGORY_OPENABLE);
            picker.setType("*/*");
            picker.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(picker);
            return "Dosya seçicisini açıyorum.";
        } catch (Exception e) { return "Dosya seçicisi açılamadı."; }
    }

    public static boolean supportsScreenLock() {
        return Build.VERSION.SDK_INT >= Build.VERSION_CODES.P;
    }
}
