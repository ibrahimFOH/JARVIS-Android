package com.stagepulse.jarvis;

import android.os.Bundle;
import android.speech.tts.TextToSpeech;

public final class JarvisVoice {
    private JarvisVoice(){}

    public static void configure(TextToSpeech tts){
        if(tts==null) return;
        // Use the Android default TTS engine selected by the user.
        // NekoSpeak can be selected as the system TTS engine and configured
        // with the Turkish DFKI voice. We deliberately do not force an
        // English voice here.
        tts.setSpeechRate(.86f);
        tts.setPitch(.78f);
    }

    public static Bundle params(){
        Bundle b=new Bundle();
        b.putFloat(TextToSpeech.Engine.KEY_PARAM_VOLUME,1.0f);
        return b;
    }

    public static String prepare(String text){
        return text.replace("!","! ").replace("?","? ").replace(".",". ");
    }
}
