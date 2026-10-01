package com.stagepulse.jarvis;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.regex.*;

public final class ResearchEngine {
    public static final class Source {
        public final String title, url, snippet;
        Source(String t,String u,String s){title=t;url=u;snippet=s;}
    }
    public static final class Report {
        public final String query;
        public final List<Source> sources;
        public final String text;
        Report(String q,List<Source>s,String t){query=q;sources=s;text=t;}
    }

    private ResearchEngine(){}

    public static Report research(String query) throws Exception {
        List<Source> sources = search(query, 5);
        if(sources.isEmpty()) throw new IOException("Arama sonucu bulunamadı.");
        StringBuilder r=new StringBuilder();
        r.append("ARAŞTIRMA RAPORU\n");
        r.append("Konu: ").append(query).append("\n");
        r.append("Tarih: ").append(new java.text.SimpleDateFormat("dd.MM.yyyy HH:mm",new Locale("tr","TR")).format(new Date())).append("\n");
        r.append("Kaynak sayısı: ").append(sources.size()).append("\n\n");
        r.append("BULGULAR\n");
        int n=1;
        for(Source s:sources){
            r.append(n++).append(". ").append(s.title).append("\n");
            r.append("   ").append(s.snippet).append("\n");
            r.append("   Kaynak: ").append(s.url).append("\n\n");
        }
        r.append("DEĞERLENDİRME\n");
        r.append("Bu rapor, açık web arama sonuçlarındaki kaynak başlıkları ve özetlerinden oluşturuldu. ");
        r.append("Kaynaklar arasında farklılık varsa ayrıca doğrulama gerekir. JARVIS doğrulanmamış bilgiyi kesin gerçek olarak sunmamalıdır.");
        return new Report(query,sources,r.toString());
    }

    private static List<Source> search(String q,int max) throws Exception {
        String endpoint="https://html.duckduckgo.com/html/?q="+URLEncoder.encode(q,"UTF-8");
        String html=http(endpoint,12000);
        List<Source> out=new ArrayList<>();
        Pattern p=Pattern.compile("<a[^>]+class=[\\\"']result__a[\\\"'][^>]+href=[\\\"']([^\\\"']+)[\\\"'][^>]*>(.*?)</a>",Pattern.CASE_INSENSITIVE|Pattern.DOTALL);
        Matcher m=p.matcher(html);
        while(m.find()&&out.size()<max){
            String url=decode(m.group(1));
            String title=clean(m.group(2));
            if(url.startsWith("//")) url="https:"+url;
            String block=html.substring(m.start(),Math.min(html.length(),m.end()+1800));
            String snippet="";
            Matcher sm=Pattern.compile("result__snippet[^>]*>(.*?)</",Pattern.CASE_INSENSITIVE|Pattern.DOTALL).matcher(block);
            if(sm.find()) snippet=clean(sm.group(1));
            if(!url.isEmpty()&&!title.isEmpty()) out.add(new Source(title,url,snippet));
        }
        return out;
    }

    private static String http(String u,int timeout) throws Exception{
        HttpURLConnection c=(HttpURLConnection)new URL(u).openConnection();
        c.setConnectTimeout(timeout); c.setReadTimeout(timeout);
        c.setRequestMethod("GET");
        c.setRequestProperty("User-Agent","Mozilla/5.0 (Android) JARVIS-Stagepulse/2.2");
        c.setInstanceFollowRedirects(true);
        try(InputStream in=c.getInputStream();ByteArrayOutputStream b=new ByteArrayOutputStream()){
            byte[] buf=new byte[8192]; int x,total=0;
            while((x=in.read(buf))!=-1&&total<300000){b.write(buf,0,x);total+=x;}
            return new String(b.toByteArray(),StandardCharsets.UTF_8);
        } finally { c.disconnect(); }
    }

    private static String clean(String s){
        s=s.replaceAll("<[^>]+>"," ");
        s=decode(s).replaceAll("\\s+"," ").trim();
        return s.replace("&quot;","\\\"").replace("&#39;","'");
    }

    private static String decode(String s){
        try{
            return URLDecoder.decode(s,"UTF-8")
                .replace("&amp;","&").replace("&lt;","<").replace("&gt;",">")
                .replace("&quot;","\\\"").replace("&#x27;","'");
        }catch(Exception e){return s;}
    }
}