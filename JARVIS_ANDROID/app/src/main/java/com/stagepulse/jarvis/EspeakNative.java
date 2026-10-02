package com.stagepulse.jarvis;

import android.util.Log;

public final class EspeakNative {
    private static final String TAG = "JARVIS_ESPEAK";
    static {
        try {
            System.loadLibrary("ttsespeak");
        } catch (Throwable t) {
            Log.e(TAG, "Could not load libttsespeak.so", t);
        }
        try {
            System.loadLibrary("jarvisphonemizer");
        } catch (Throwable t) {
            Log.e(TAG, "Could not load libjarvisphonemizer.so", t);
        }
    }

    private native int nativeInitialize(String dataPath);
    private native String nativeTextToPhonemes(String text, String language);

    public int initialize(String dataPath) {
        return nativeInitialize(dataPath);
    }

    public String textToPhonemes(String text, String language) {
        return nativeTextToPhonemes(text, language);
    }
}
