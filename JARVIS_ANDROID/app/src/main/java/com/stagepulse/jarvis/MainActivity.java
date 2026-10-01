package com.stagepulse.jarvis;

import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.os.Handler;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.view.*;
import android.widget.*;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final int REQ_AUDIO = 9001;
    private static final String PREFS = "jarvis_android";
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler();
    private SharedPreferences prefs;
    private EditText command, server, token;
    private TextView status, chat;
    private Button send, voice, connect;
    private HudView hud;
    private SpeechRecognizer speech;
    private TextToSpeech tts;
    private boolean ttsReady=false;

    private int gold(){ return 0xFFD4AF37; }
    private int white(){ return 0xFFF2F2F2; }
    private int muted(){ return 0xFF8C8C8C; }
    private int bg(){ return 0xFF050505; }
    private int panel(){ return 0xFF0B0B0B; }

    @Override public void onCreate(Bundle b){
        super.onCreate(b);
        prefs=getSharedPreferences(PREFS,Context.MODE_PRIVATE);
        buildUi();
        initTts();
        initSpeech();
        connect();
        append("JARVIS", "PATRON, Android arayüzü hazır. Ollama host bağlantısı bekleniyor.");
    }

    private String baseUrl(){ return server.getText().toString().trim(); }
    private String tokenValue(){ return token.getText().toString().trim(); }

    private TextView tv(String s,int size,int color){
        TextView v=new TextView(this); v.setText(s); v.setTextSize(size); v.setTextColor(color); v.setPadding(0,0,0,0); return v;
    }

    private void buildUi(){
        LinearLayout root=new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL); root.setPadding(18,12,18,12); root.setBackgroundColor(bg());
        LinearLayout top=new LinearLayout(this); top.setOrientation(LinearLayout.VERTICAL);
        TextView title=tv("J.A.R.V.I.S.",27,gold()); title.setTypeface(null,1); top.addView(title,new LinearLayout.LayoutParams(-1, -2));
        TextView sub=tv("JUST A RATHER VERY INTELLIGENT SYSTEM   //   STAGEPULSE",10,muted()); top.addView(sub,new LinearLayout.LayoutParams(-1,-2));
        status=tv("● OFFLINE",11,0xFFD95C5C); status.setTypeface(null,1); top.addView(status,new LinearLayout.LayoutParams(-1,-2));
        root.addView(top);

        hud=new HudView(this); root.addView(hud,new LinearLayout.LayoutParams(-1,0,1));

        chat=tv("",12,white()); chat.setGravity(Gravity.BOTTOM); chat.setPadding(8,8,8,8); chat.setBackgroundColor(panel());
        ScrollView scroll=new ScrollView(this); scroll.addView(chat); root.addView(scroll,new LinearLayout.LayoutParams(-1,0,0.65f));

        command=new EditText(this); command.setHint("COMMAND // Türkçe komut gir..."); command.setHintTextColor(muted()); command.setTextColor(white()); command.setSingleLine(false); command.setMinLines(2); command.setBackgroundColor(panel()); command.setPadding(14,12,14,12);
        root.addView(command,new LinearLayout.LayoutParams(-1,-2));

        LinearLayout row=new LinearLayout(this); row.setOrientation(LinearLayout.HORIZONTAL);
        send=button("EXECUTE"); voice=button("◉ VOICE"); connect=button("CONNECT");
        row.addView(send,new LinearLayout.LayoutParams(0,58,1)); row.addView(voice,new LinearLayout.LayoutParams(0,58,1)); row.addView(connect,new LinearLayout.LayoutParams(0,58,1)); root.addView(row);

        LinearLayout cfg=new LinearLayout(this); cfg.setOrientation(LinearLayout.VERTICAL); cfg.setPadding(0,8,0,0);
        server=new EditText(this); server.setHint("JARVIS Bridge URL (örn. http://192.168.1.10:8765)"); server.setHintTextColor(muted()); server.setTextColor(white()); server.setText(prefs.getString("server","http://192.168.1.100:8765")); server.setSingleLine();
        token=new EditText(this); token.setHint("Bridge token"); token.setHintTextColor(muted()); token.setTextColor(white()); token.setText(prefs.getString("token","JARVIS-ANDROID-2026-STAGEPULSE")); token.setSingleLine();
        cfg.addView(server,new LinearLayout.LayoutParams(-1,48)); cfg.addView(token,new LinearLayout.LayoutParams(-1,48)); root.addView(cfg);

        setContentView(root);
        send.setOnClickListener(v->sendCommand(command.getText().toString()));
        voice.setOnClickListener(v->listen());
        connect.setOnClickListener(v->connect());
    }

    private Button button(String text){ Button b=new Button(this); b.setText(text); b.setTextColor(gold()); b.setTextSize(11); b.setBackgroundColor(panel()); return b; }

    private void initTts(){
        tts=new TextToSpeech(this, code->{ if(code==TextToSpeech.SUCCESS){ int r=tts.setLanguage(new Locale("tr","TR")); ttsReady = r!=TextToSpeech.LANG_MISSING_DATA && r!=TextToSpeech.LANG_NOT_SUPPORTED; tts.setSpeechRate(0.95f); }});
    }

    private void initSpeech(){
        if(!SpeechRecognizer.isRecognitionAvailable(this)) return;
        speech=SpeechRecognizer.createSpeechRecognizer(this);
        speech.setRecognitionListener(new RecognitionListener(){
            public void onReadyForSpeech(Bundle b){ hud.setActive(true); status.setText("● LISTENING"); }
            public void onBeginningOfSpeech(){ }
            public void onRmsChanged(float rms){ }
            public void onBufferReceived(byte[] b){ }
            public void onEndOfSpeech(){ hud.setActive(false); }
            public void onError(int e){ hud.setActive(false); status.setText("● ONLINE"); append("JARVIS","Ses algılanamadı veya anlaşılmadı."); }
            public void onResults(Bundle b){ hud.setActive(false); ArrayList<String> rs=b.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION); if(rs!=null&&!rs.isEmpty()){ command.setText(rs.get(0)); sendCommand(rs.get(0)); } }
            public void onPartialResults(Bundle b){ }
            public void onEvent(int t,Bundle b){ }
        });
    }

    private void listen(){
        if(speech==null){ toast("Bu cihazda Android konuşma tanıma servisi yok."); return; }
        if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){ requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},REQ_AUDIO); return; }
        Intent i=new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH); i.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "tr-TR"); i.putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE,"tr-TR"); i.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS,false); i.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS,3); speech.startListening(i);
    }

    private void connect(){
        final String base=baseUrl();
        if(base.isEmpty()) return;
        prefs.edit().putString("server",base).putString("token",tokenValue()).apply();
        status.setText("● CONNECTING");
        io.submit(()->{
            try{ JSONObject j=BridgeClient.health(base); main.post(()->{ status.setText("● ONLINE"); status.setTextColor(gold()); hud.setActive(false); append("SYSTEM", "JARVIS host bağlantısı kuruldu. " + j.optString("ollama_model","qwen3:0.6b")); }); }
            catch(Exception e){ main.post(()->{ status.setText("● OFFLINE"); status.setTextColor(0xFFD95C5C); append("SYSTEM","Bağlantı kurulamadı: "+e.getMessage()); }); }
        });
    }

    private void sendCommand(String text){
        final String cmd=text.trim(); if(cmd.isEmpty()) return;
        append("PATRON",cmd); command.setText(""); hud.setActive(true); status.setText("● PROCESSING");
        io.submit(()->{
            try{
                JSONObject j=BridgeClient.chat(baseUrl(),tokenValue(),cmd); String answer=j.optString("response", j.optString("error","Yanıt alınamadı."));
                main.post(()->{ hud.setActive(false); status.setText(j.optBoolean("success",false)?"● ONLINE":"● READY"); append("JARVIS",answer); speak(answer); });
            }catch(Exception e){ main.post(()->{ hud.setActive(false); status.setText("● OFFLINE"); append("JARVIS","Bağlantı hatası: "+e.getMessage()); }); }
        });
    }

    private void speak(String text){ if(ttsReady && tts!=null && text!=null && !text.trim().isEmpty()) tts.speak(text,TextToSpeech.QUEUE_FLUSH,null,"jarvis-response"); }

    private void append(String who,String msg){ chat.append((chat.length()>0?"\n\n":"")+who+"\n"+msg); }
    private void toast(String s){ Toast.makeText(this,s,Toast.LENGTH_SHORT).show(); }

    @Override protected void onDestroy(){ if(speech!=null) speech.destroy(); if(tts!=null) tts.shutdown(); io.shutdownNow(); super.onDestroy(); }
}
