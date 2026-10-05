package com.stagepulse.jarvis;

import android.Manifest;
import android.app.Activity;
import android.content.*;
import android.content.pm.PackageManager;
import android.os.*;
import android.provider.Settings;
import android.speech.*;
import android.view.Gravity;
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
    private PiperTts piper;
    private AgencyAgent activeAgent;

    private int gold(){return 0xFFD4AF37;}
    private int white(){return 0xFFF2F2F2;}
    private int muted(){return 0xFF8C8C8C;}
    private int panel(){return 0xFF0B0B0B;}

    @Override public void onCreate(Bundle b){
        super.onCreate(b);
        buildUi();
        initPiper();
        initSpeech();
        status.setText("● ONLINE");
        status.setTextColor(gold());
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
        Button send=button("EXECUTE"), voice=button("◉ VOICE"), agents=button("AGENTS");
        row.addView(send,new LinearLayout.LayoutParams(0,58,1));
        row.addView(voice,new LinearLayout.LayoutParams(0,58,1));
        row.addView(agents,new LinearLayout.LayoutParams(0,58,1));
        root.addView(row);
        setContentView(root);
        send.setOnClickListener(v->sendCommand(command.getText().toString()));
        voice.setOnClickListener(v->listen());
        agents.setOnClickListener(v->showAgents());
    }

    private Button button(String s){Button b=new Button(this);b.setText(s);b.setTextColor(gold());b.setTextSize(11);b.setBackgroundColor(panel());return b;}

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
                    status.setText("● VOICE ERROR");
                    status.setTextColor(0xFFFF5555);
                    append("JARVIS","Türkçe ses motoru başlatılamadı. Piper/eSpeak başlatma hatası. Logcat: JARVIS_PIPER.");
                })
        );
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
            }catch(Exception e){
                a="İşlem tamamlanamadı Patron. Teknik bilgi: "+e.getClass().getSimpleName();
            }
            final String answer=a;
            runOnUiThread(()->{hud.setActive(false);if(!status.getText().toString().startsWith("● AGENT"))status.setText("● ONLINE");append("JARVIS",answer);speak(answer);});
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

    private void speak(String s){if(piper!=null&&piper.isReady())piper.speak(s);}
    private void append(String who,String msg){chat.append((chat.length()>0?"\n\n":"")+who+"\n"+msg);}
    private void toast(String s){Toast.makeText(this,s,Toast.LENGTH_SHORT).show();}

    @Override protected void onDestroy(){
        if(speech!=null)speech.destroy();
        if(piper!=null)piper.release();
        io.shutdownNow();
        super.onDestroy();
    }
}
