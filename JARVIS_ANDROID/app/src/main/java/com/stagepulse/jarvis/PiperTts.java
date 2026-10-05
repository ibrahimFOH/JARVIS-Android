package com.stagepulse.jarvis;

import android.content.Context;
import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioTrack;
import android.util.Log;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.FloatBuffer;
import java.nio.LongBuffer;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicBoolean;
import ai.onnxruntime.OnnxTensor;
import ai.onnxruntime.OrtEnvironment;
import ai.onnxruntime.OrtSession;

public final class PiperTts {
    private static final String TAG = "JARVIS_PIPER";
    private static final String VOICE_ID = "tr_TR-dfki-medium";
    private static final String MODEL_ASSET = "piper/" + VOICE_ID + ".onnx";
    private static final String CONFIG_ASSET = "piper/" + VOICE_ID + ".onnx.json";
    private static final String ESPEAK_ASSET = "espeak-ng-data";
    private String espeakVoice = "tr";

    private final Context context;
    private final ExecutorService engineExecutor = Executors.newSingleThreadExecutor();
    private final ExecutorService speechExecutor = Executors.newSingleThreadExecutor();
    private final AtomicBoolean stopRequested = new AtomicBoolean(false);
    private volatile boolean initialized = false;
    private Future<?> currentSpeech;
    private OrtEnvironment ortEnvironment;
    private OrtSession ortSession;
    private EspeakNative espeak;
    private int sampleRate = 22050;
    private float noiseScale = 0.667f, lengthScale = 1.0f, noiseW = 0.8f;
    private final Map<String, long[]> phonemeIds = new HashMap<>();

    public PiperTts(Context context) { this.context = context.getApplicationContext(); }

    public void initialize(Runnable onReady, Runnable onError) {
        engineExecutor.execute(() -> {
            try {
                if (initialized) { if (onReady != null) onReady.run(); return; }

                File modelFile = extractAsset(MODEL_ASSET, "piper", VOICE_ID + ".onnx");
                File configFile = extractAsset(CONFIG_ASSET, "piper", VOICE_ID + ".onnx.json");

                JSONObject root = new JSONObject(readText(configFile));
                JSONObject audio = root.getJSONObject("audio");
                JSONObject inference = root.getJSONObject("inference");
                JSONObject ids = root.getJSONObject("phoneme_id_map");
                sampleRate = audio.optInt("sample_rate", 22050);
                noiseScale = (float) inference.optDouble("noise_scale", 0.667);
                lengthScale = (float) inference.optDouble("length_scale", 1.0);
                noiseW = (float) inference.optDouble("noise_w", 0.8);\n                JSONObject espeakConfig = root.optJSONObject("espeak");\n                if (espeakConfig != null) espeakVoice = espeakConfig.optString("voice", "tr");

                phonemeIds.clear();
                java.util.Iterator<String> names = ids.keys();
                while (names.hasNext()) {
                    String key = names.next();
                    JSONArray arr = ids.getJSONArray(key);
                    long[] values = new long[arr.length()];
                    for (int i = 0; i < arr.length(); i++) values[i] = arr.getLong(i);
                    phonemeIds.put(key, values);
                }

                File espeakDir = new File(context.getFilesDir(), ESPEAK_ASSET);
                if (!new File(espeakDir, "voices").exists()) copyAssetTree(ESPEAK_ASSET, espeakDir);

                if (!new File(espeakDir, "voices").exists())
                    throw new IOException("eSpeak data missing: " + espeakDir.getAbsolutePath());

                espeak = new EspeakNative();

                // espeak_Initialize expects the directory that CONTAINS
                // the espeak-ng-data files (voices, dicts, lang, etc.).
                int init = espeak.initialize(context.getFilesDir().getAbsolutePath());
                if (init < 0)
                    throw new IllegalStateException("eSpeak-NG init failed: " + init + " data=" + espeakDir.getAbsolutePath());

                String probe = espeak.textToPhonemes("merhaba", espeakVoice);
                if (probe == null || probe.isEmpty())
                    throw new IllegalStateException("eSpeak-NG returned no Turkish phonemes");

                ortEnvironment = OrtEnvironment.getEnvironment();
                OrtSession.SessionOptions options = new OrtSession.SessionOptions();
                options.setIntraOpNumThreads(2);

                String abi = android.os.Build.SUPPORTED_ABIS.length > 0 ? android.os.Build.SUPPORTED_ABIS[0] : "";
                boolean is32BitArm = "armeabi-v7a".equals(abi) || "armeabi".equals(abi);

                if (is32BitArm) {
                    byte[] modelBytes = java.nio.file.Files.readAllBytes(modelFile.toPath());
                    ortSession = ortEnvironment.createSession(modelBytes, options);
                } else {
                    ortSession = ortEnvironment.createSession(modelFile.getAbsolutePath(), options);
                }
                options.close();

                initialized = true;
                Log.i(TAG, "Direct Piper ready. voice=" + VOICE_ID + " rate=" + sampleRate);
                if (onReady != null) onReady.run();
            } catch (Throwable t) {
                initialized = false;
                Log.e(TAG, "Direct Piper initialization failed", t);
                if (onError != null) onError.run();
            }
        });
    }

    public boolean isReady() { return initialized; }

    public void speak(String text) {
        if (!initialized || text == null || text.trim().isEmpty()) return;
        final String clean = prepareText(text);
        stopRequested.set(true);
        if (currentSpeech != null) currentSpeech.cancel(true);
        currentSpeech = speechExecutor.submit(() -> {
            stopRequested.set(false);
            AudioTrack track = null;
            try {
                String phonemes = espeak.textToPhonemes(clean, espeakVoice);
                if (phonemes == null || phonemes.isEmpty()) throw new IllegalStateException("No Turkish phonemes generated");
                long[] ids = tokenize(phonemes);
                if (ids.length < 4) throw new IllegalStateException("No valid Piper tokens");
                FloatBuffer audio = infer(ids);
                if (audio == null) return;

                int frameCount = audio.remaining();
                short[] pcm = new short[frameCount];
                for (int i = 0; i < frameCount; i++) {
                    float v = audio.get();
                    v = Math.max(-1.0f, Math.min(1.0f, v));
                    pcm[i] = (short) (v * 32767.0f);
                }

                int minBuffer = AudioTrack.getMinBufferSize(sampleRate, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT);
                int bufferBytes = Math.max(minBuffer, sampleRate);
                track = new AudioTrack.Builder()
                        .setAudioAttributes(new AudioAttributes.Builder()
                                .setUsage(AudioAttributes.USAGE_ASSISTANCE_ACCESSIBILITY)
                                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
                        .setAudioFormat(new AudioFormat.Builder()
                                .setSampleRate(sampleRate).setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                                .setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
                        .setBufferSizeInBytes(bufferBytes)
                        .setTransferMode(AudioTrack.MODE_STREAM).build();
                track.play();
                int offset = 0;
                while (offset < pcm.length && !stopRequested.get() && !Thread.currentThread().isInterrupted()) {
                    int count = Math.min(2048, pcm.length - offset);
                    int written = track.write(pcm, offset, count, AudioTrack.WRITE_BLOCKING);
                    if (written < 0) break;
                    offset += written;
                }
                try { track.stop(); } catch (Throwable ignored) {}
            } catch (Throwable t) {
                Log.e(TAG, "Piper speech failed", t);
            } finally {
                if (track != null) try { track.release(); } catch (Throwable ignored) {}
            }
        });
    }

    public void stop() { stopRequested.set(true); if (currentSpeech != null) currentSpeech.cancel(true); }

    public void release() {
        stop();
        speechExecutor.shutdownNow();
        engineExecutor.shutdownNow();
        try { if (ortSession != null) ortSession.close(); } catch (Throwable ignored) {}
        try { if (ortEnvironment != null) ortEnvironment.close(); } catch (Throwable ignored) {}
        ortSession = null; ortEnvironment = null; initialized = false;
    }

    private FloatBuffer infer(long[] ids) throws Exception {
        OnnxTensor input = OnnxTensor.createTensor(ortEnvironment, LongBuffer.wrap(ids), new long[]{1, ids.length});
        OnnxTensor lengths = OnnxTensor.createTensor(ortEnvironment, LongBuffer.wrap(new long[]{ids.length}), new long[]{1});
        OnnxTensor scaleTensor = OnnxTensor.createTensor(ortEnvironment, FloatBuffer.wrap(new float[]{noiseScale, lengthScale, noiseW}), new long[]{3});
        Map<String, OnnxTensor> inputs = new HashMap<>();
        inputs.put("input", input); inputs.put("input_lengths", lengths); inputs.put("scales", scaleTensor);
        OrtSession.Result result = null;
        try {
            if (stopRequested.get()) return null;
            result = ortSession.run(inputs);
            OnnxTensor output = (OnnxTensor) result.get(0);
            FloatBuffer buffer = output.getFloatBuffer();
            FloatBuffer copy = FloatBuffer.allocate(buffer.remaining());
            copy.put(buffer); copy.flip(); return copy;
        } finally {
            input.close(); lengths.close(); scaleTensor.close();
            if (result != null) result.close();
        }
    }

    private long[] tokenize(String phonemes) {
        List<Long> out = new ArrayList<>();
        addIds(out, phonemeIds.get("^"));
        addIds(out, phonemeIds.get("_"));

        // Piper phoneme_id_map keys are Unicode code points/phoneme symbols.
        // Java char indexing can split IPA symbols into surrogate pairs, so
        // match using Unicode code points instead of UTF-16 char units.
        int i = 0;
        int maxCodePoints = 1;
        for (String key : phonemeIds.keySet()) {
            maxCodePoints = Math.max(maxCodePoints, key.codePointCount(0, key.length()));
        }

        while (i < phonemes.length()) {
            boolean matched = false;
            int remaining = phonemes.codePointCount(i, phonemes.length());
            int limit = Math.min(maxCodePoints, remaining);

            for (int count = limit; count >= 1; count--) {
                int end = phonemes.offsetByCodePoints(i, count);
                String token = phonemes.substring(i, end);
                long[] ids = phonemeIds.get(token);
                if (ids != null) {
                    addIds(out, ids);
                    addIds(out, phonemeIds.get("_"));
                    i = end;
                    matched = true;
                    break;
                }
            }

            if (!matched) {
                i = phonemes.offsetByCodePoints(i, 1);
            }
        }

        addIds(out, phonemeIds.get("$"));
        long[] result = new long[out.size()];
        for (int n = 0; n < out.size(); n++) result[n] = out.get(n);
        return result;
    }

    private static void addIds(List<Long> target, long[] ids) { if (ids != null) for (long id : ids) target.add(id); }

    private static String prepareText(String text) {
        return text.replace("\n", ". ").replaceAll("\\s+", " ").trim();
    }

    private File extractAsset(String assetPath, String folder, String fileName) throws IOException {
        File dir = new File(context.getFilesDir(), folder);
        if (!dir.exists() && !dir.mkdirs()) throw new IOException("Cannot create " + dir);
        File out = new File(dir, fileName);
        if (out.exists() && out.length() > 1024) return out;
        try (InputStream in = context.getAssets().open(assetPath); FileOutputStream fos = new FileOutputStream(out)) {
            byte[] buffer = new byte[1024 * 1024]; int read;
            while ((read = in.read(buffer)) != -1) fos.write(buffer, 0, read);
        }
        return out;
    }

    private void copyAssetTree(String assetPath, File target) throws IOException {
        if (!target.exists() && !target.mkdirs()) throw new IOException("Cannot create " + target);
        String[] children = context.getAssets().list(assetPath);
        if (children == null || children.length == 0) {
            File parent = target.getParentFile();
            if (parent != null && !parent.exists() && !parent.mkdirs()) throw new IOException("Cannot create " + parent);
            try (InputStream in = context.getAssets().open(assetPath); FileOutputStream out = new FileOutputStream(target)) {
                byte[] buffer = new byte[64 * 1024]; int read;
                while ((read = in.read(buffer)) != -1) out.write(buffer, 0, read);
            }
            return;
        }
        for (String child : children) copyAssetTree(assetPath + "/" + child, new File(target, child));
    }

    private static String readText(File file) throws IOException {
        byte[] data = java.nio.file.Files.readAllBytes(file.toPath());
        return new String(data, java.nio.charset.StandardCharsets.UTF_8);
    }
}
