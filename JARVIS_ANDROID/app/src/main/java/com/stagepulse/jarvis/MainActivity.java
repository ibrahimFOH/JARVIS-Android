package com.stagepulse.jarvis;

import android.Manifest;
import android.app.Activity;
import android.content.*;
import android.content.pm.PackageManager;
import android.os.*;
import android.provider.Settings;
import android.speech.*;
import android.speech.tts.TextToSpeech;
import android.view.Gravity;
import android.speech.tts.Voice;
import android.widget.*;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.concurrent.*;

public class MainActivity extends Activity {
    private static final int REQ_AUDIO=9001;
    private final ExecutorService io=Executors.newSingleThreadExecutor();
    private EditText command;
    private TextView status,chat;
    private HudView hud;
    private SpeechRecognizer speech;
    private TextToSpeech tts;
    private boolean ttsReady=false;

    private int gold(){return 0xFFD4AF37;}
    private int white(){return 0xFFF2F2F2;}
    private int muted(){return 0xFF8C8C8C;}
    private int panel(){return 0xFF0B0B0B;}

    @Override public void onCreate(Bundle b){
        super.onCreate(b); buildUi(); initTts(); initSpeech();
        status.setText("● ONLINE"); status.setTextColor(gold());
        append("JARVIS","PATRON, bağımsız Android çekirdeği hazır.");
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
        hud=new HudView(this); root.addView(hud,new LinearLayout.LayoutParams(-1,0,1));
        chat=tv("",12,white()); chat.setGravity(Gravity.BOTTOM); chat.setPadding(8,8,8,8); chat.setBackgroundColor(panel());
        ScrollView scroll=new ScrollView(this); scroll.addView(chat); root.addView(scroll,new LinearLayout.LayoutParams(-1,0,.65f));
        command=new EditText(this); command.setHint("COMMAND // Türkçe komut gir..."); command.setHintTextColor(muted());
        command.setTextColor(white()); command.setMinLines(2); command.setBackgroundColor(panel()); command.setPadding(14,12,14,12);
        root.addView(command,new LinearLayout.LayoutParams(-1,-2));
        LinearLayout row=new LinearLayout(this); row.setOrientation(LinearLayout.HORIZONTAL);
        Button send=button("EXECUTE"), voice=button("◉ VOICE"); row.addView(send,new LinearLayout.LayoutParams(0,58,1)); row.addView(voice,new LinearLayout.LayoutParams(0,58,1)); root.addView(row);
        setContentView(root); send.setOnClickListener(v->sendCommand(command.getText().toString())); voice.setOnClickListener(v->listen());
    }

    private Button button(String s){Button b=new Button(this);b.setText(s);b.setTextColor(gold());b.setTextSize(11);b.setBackgroundColor(panel());return b;}

    private void initTts(){
        // Force JARVIS to use the installed NekoSpeak TTS engine.
        // NekoSpeak keeps the voice selected by the user in its own settings
        // (for example Turkish DFKI medium Piper).
        try{
            tts=new TextToSpeech(this,c->{
                if(c==TextToSpeech.SUCCESS){
                    JarvisVoice.configure(tts);
                    // NekoSpeak exposes its voices through the Android TTS API.
                    // Its service currently advertises English locale metadata
                    // even when the selected voice is Turkish DFKI/Piper, so
                    // do not make readiness depend on setLanguage().
                    tts.setLanguage(Locale.US);
                    ttsReady=true;
                }else{
                    ttsReady=false;
                }
            },"com.nekospeak.tts");
        }catch(Exception e){
            // Fallback only if NekoSpeak is not installed.
            tts=new TextToSpeech(this,c->{
                if(c==TextToSpeech.SUCCESS){
                    JarvisVoice.configure(tts);
                    tts.setLanguage(new Locale("tr","TR"));
                    ttsReady=true;
                }else{
                    ttsReady=false;
                }
            });
        }
    }

    private void initSpeech(){
        if(!SpeechRecognizer.isRecognitionAvailable(this))return;
        speech=SpeechRecognizer.createSpeechRecognizer(this);
        speech.setRecognitionListener(new RecognitionListener(){
            public void onReadyForSpeech(Bundle b){hud.setActive(true);status.setText("● LISTENING");}
            public void onBeginningOfSpeech(){} public void onRmsChanged(float r){} public void onBufferReceived(byte[] b){}
            public void onEndOfSpeech(){hud.setActive(false);}
            public void onError(int e){hud.setActive(false);status.setText("● ONLINE");append("JARVIS","Ses algılanamadı veya anlaşılmadı.");}
            public void onResults(Bundle b){hud.setActive(false);ArrayList<String>x=b.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);if(x!=null&&!x.isEmpty()){command.setText(x.get(0));sendCommand(x.get(0));}}
            public void onPartialResults(Bundle b){} public void onEvent(int t,Bundle b){}
        });
    }

    private void listen(){
        if(speech==null){toast("Bu cihazda konuşma tanıma servisi yok.");return;}
        if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},REQ_AUDIO);return;}
        Intent i=new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);i.putExtra(RecognizerIntent.EXTRA_LANGUAGE,"tr-TR");i.putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE,"tr-TR");i.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS,3);speech.startListening(i);
    }

    private void sendCommand(String text){
        final String cmd=text.trim();if(cmd.isEmpty())return;append("PATRON",cmd);command.setText("");hud.setActive(true);status.setText("● PROCESSING");
        io.submit(()->{
            String a;
            try{
                if(isResearchCommand(cmd)){
                    statusPost("● RESEARCHING");
                    ResearchEngine.Report report=ResearchEngine.research(extractResearchQuery(cmd));
                    a=report.text;
                }else{
                    a=processLocal(cmd);
                }
            }catch(Exception e){
                a="Araştırma tamamlanamadı Patron. İnternet veya arama servisi yanıt vermedi.\n\nTeknik bilgi: "+e.getClass().getSimpleName();
            }
            final String answer=a;
            runOnUiThread(()->{hud.setActive(false);status.setText("● ONLINE");append("JARVIS",answer);speak(answer);});
        });
    }

    private void statusPost(String text){runOnUiThread(()->status.setText(text));}

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
        if(c.contains("merhaba")||c.equals("selam"))return "Merhaba Patron. Android JARVIS çekirdeği hazır.";
        if(c.contains("kimsin"))return "Ben J.A.R.V.I.S. Android sürümüyüm. Bu cihaz üzerinde bağımsız çalışıyorum.";
        if(c.contains("saat"))return "Şu an saat "+new SimpleDateFormat("HH:mm",Locale.getDefault()).format(new Date())+".";
        if(c.contains("tarih")||c.contains("bugün"))return "Bugün "+new SimpleDateFormat("dd MMMM yyyy, EEEE",new Locale("tr","TR")).format(new Date())+".";
        if(c.contains("pil")||c.contains("batarya")){BatteryManager b=(BatteryManager)getSystemService(BATTERY_SERVICE);return "Pil seviyesi yüzde "+b.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)+".";}
        if(c.contains("ayarlar")){try{startActivity(new Intent(Settings.ACTION_SETTINGS));return "Android ayarlarını açıyorum.";}catch(Exception e){return "Android ayarları açılamadı.";}}
        if(c.contains("tarayıcı")||c.contains("internet aç")){try{startActivity(new Intent(Intent.ACTION_VIEW,android.net.Uri.parse("https://www.google.com")));return "Tarayıcıyı açıyorum.";}catch(Exception e){return "Tarayıcı açılamadı.";}}
        if(c.contains("yardım")||c.contains("ne yapabiliyorsun"))return "Saat, tarih, pil, ayarlar ve tarayıcı gibi Android komutlarını yerel olarak çalıştırabiliyorum. Sesli komut da aktif.";
        if(c.contains("nasılsın")||c.contains("nasılsın jarvis")||c.contains("iyi misin"))return "İyiyim Patron. Sistemler kararlı ve komut bekliyorum.";
        if(c.contains("ne yapıyorsun")||c.contains("ne yapıyorsun jarvis"))return "Sizi dinliyorum Patron. Vereceğiniz komutu bekliyorum.";
        if(c.contains("teşekkür")||c.contains("sağ ol"))return "Rica ederim Patron.";
        if(c.contains("adın ne"))return "Ben J.A.R.V.I.S. Patron.";
        if(c.contains("müzik"))return "Müzik komutları için Android çekirdeğine ses kontrol modülü eklenebilir.";
        if(c.contains("merhaba jarvis")||c.contains("selam jarvis"))return "Emrinizdeyim Patron.";
        if(c.endsWith("?"))return "Sorunuzu aldım Patron. Bu Android sürümünde henüz bu soruya cevap verecek yerel bilgi modülü bulunmuyor.";
        return "Komutunuz alındı Patron. Bu komut için Android yerel çekirdeğinde henüz bir işlem tanımlı değil.";
    }

    private void speak(String s){if(ttsReady&&tts!=null)tts.speak(JarvisVoice.prepare(s),TextToSpeech.QUEUE_FLUSH,JarvisVoice.params(),"jarvis-response");}
    private void append(String who,String msg){chat.append((chat.length()>0?"\n\n":"")+who+"\n"+msg);}
    private void toast(String s){Toast.makeText(this,s,Toast.LENGTH_SHORT).show();}
    @Override protected void onDestroy(){if(speech!=null)speech.destroy();if(tts!=null)tts.shutdown();io.shutdownNow();super.onDestroy();}
}