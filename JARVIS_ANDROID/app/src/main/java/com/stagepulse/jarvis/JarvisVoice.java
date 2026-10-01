package com.stagepulse.jarvis;

import android.os.Bundle;
import android.speech.tts.TextToSpeech;
import android.speech.tts.Voice;
import java.util.*;

public final class JarvisVoice {
    private JarvisVoice(){}

    public static void configure(TextToSpeech tts){
        if(tts==null) return;
        Voice selected=null;
        try{
            // Prefer an offline English male voice for the cinematic JARVIS character.
            for(Voice v:tts.getVoices()){
                Locale l=v.getLocale();
                String n=(v.getName()==null?"":v.getName()).toLowerCase(Locale.ROOT);
                if("en".equalsIgnoreCase(l.getLanguage())
                        && ("GB".equalsIgnoreCase(l.getCountry()) || "US".equalsIgnoreCase(l.getCountry()))
                        && !v.isNetworkConnectionRequired()
                        && !n.contains("female")){
                    selected=v;
                    if("GB".equalsIgnoreCase(l.getCountry())) break;
                }
            }
        }catch(Exception ignored){}

        if(selected!=null) tts.setVoice(selected);
        // Character profile: slower delivery and lower pitch.
        tts.setSpeechRate(.80f);
        tts.setPitch(.68f);
    }

    public static Bundle params(){
        Bundle b=new Bundle();
        b.putFloat(TextToSpeech.Engine.KEY_PARAM_VOLUME,1.0f);
        return b;
    }

    public static String prepare(String text){
        // Short sentence pauses give the assistant a more deliberate cinematic cadence.
        return text.replace("!","! ").replace("?","? ").replace(".",". ");
    }
}