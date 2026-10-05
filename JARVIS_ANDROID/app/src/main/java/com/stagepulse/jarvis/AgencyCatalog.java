package com.stagepulse.jarvis;

import java.util.*;

public final class AgencyCatalog {
    private static final List<AgencyAgent> AGENTS = Collections.unmodifiableList(Arrays.asList(
        new AgencyAgent("foh_engineer","FOH ENGINEER",
            "Canlı miksin ana kontrolünü üstlenmek; FOH gain structure, routing, EQ, dynamics ve sistem dengesini yönetmek.",
            "Midas M32, X32, Yamaha CL5, Avantis, Soundcraft; input list, patch, gain, EQ, comp, FX, bus, matrix, PA tuning.",
            "Input/patch kontrolü -> gain structure -> kanal işleme -> bus/FX -> LR/matrix -> soundcheck -> show kontrolü."),
        new AgencyAgent("monitor_engineer","MONITOR ENGINEER",
            "Sahnedeki sanatçıların güvenli ve temiz monitör/IEM mikslerini yönetmek.",
            "Wedge, IEM, PSM300, P2, aux/mix bus, feedback yönetimi, cue, talkback, monitor patch.",
            "Rider ve input list -> monitor ihtiyaçları -> aux/IEM patch -> gain/EQ -> line check -> sanatçı soundcheck -> show."),
        new AgencyAgent("rf_engineer","RF ENGINEER",
            "Kablosuz mikrofon ve IEM sistemlerinin RF koordinasyonunu yapmak ve paraziti önlemek.",
            "Shure ULX-D, PSM, frekans planı, anten dağıtımı, scan/coordination, intermodulation, RF gain ve kablo kontrolü.",
            "Sistem envanteri -> frekans bandı -> scan -> koordinasyon -> anten planı -> RF test -> yedek frekanslar."),
        new AgencyAgent("system_tech","SYSTEM TECH",
            "PA sisteminin fiziksel kurulum, patch, sinyal akışı ve sahada çalışırlığını yönetmek.",
            "Line array, sub, monitor, amplifier/DSP, cabling, polarity, delay, phase, system patch ve arıza izolasyonu.",
            "Sistem taslağı -> kablo/patch -> güç ve sinyal -> polarity/phase -> test -> ölçüm -> FOH handoff."),
        new AgencyAgent("rider_analyst","RIDER ANALYST",
            "Teknik rider'ı eksiksiz ekipman, kanal, mikrofon, monitör ve personel gereksinimine dönüştürmek.",
            "Input list, backline, RF, monitor, PA, stage, power, lighting ve teknik personel gereksinimi analizi.",
            "Rider parse -> eksik/çelişkili maddeler -> ekipman BOM -> kanal listesi -> stage/patch -> kritik notlar."),
        new AgencyAgent("stage_plot_engineer","STAGE PLOT ENGINEER",
            "Sahne planını ölçülebilir yerleşim, patch ve kablo mantığıyla hazırlamak.",
            "Stage dimensions, artist positions, drum/mic placement, DI, monitor, IEM, multicore, FOH bağlantıları.",
            "Sahne ölçüsü -> sanatçı yerleşimi -> mikrofon/DI -> monitor -> kablo yolları -> giriş/çıkış patch."),
        new AgencyAgent("spl_calculator","SPL CALCULATOR",
            "SPL, mesafe, hassasiyet, güç ve headroom ilişkilerini teknik hesaplara dönüştürmek.",
            "dB/dB-SPL, inverse-square, sensitivity, amplifier power, array/sub seviyeleri ve güvenlik marjı.",
            "Girdileri doğrula -> birimleri normalize et -> hesabı yap -> varsayımları göster -> sonucu saha notuna dönüştür."),
        new AgencyAgent("audio_system_designer","AUDIO SYSTEM DESIGNER",
            "Konser ve etkinlik için PA, sub, monitor ve sinyal mimarisini tasarlamak.",
            "Aktif line array, dual/single 18 sub, monitor, IEM, DSP, console, Dante ve sistem ölçeklendirme.",
            "Venue/seyirci -> SPL/hedef -> PA coverage -> sub -> monitor -> console/I/O -> güç/sinyal -> sistem kontrolü."),
        new AgencyAgent("live_sound_troubleshooter","LIVE SOUND TROUBLESHOOTER",
            "Canlı ses problemlerini hızlı ve güvenli biçimde kök nedene indirmek.",
            "No signal, hum, distortion, feedback, phase, RF dropouts, clipping, clock/Dante ve patch sorunları.",
            "Belirti -> sinyal zincirini böl -> bilinen iyi noktadan test -> kök neden -> düzeltme -> tekrar test."),
        new AgencyAgent("dante_network_engineer","DANTE NETWORK ENGINEER",
            "Dante ağlarında clock, routing, addressing ve multicast/latency problemlerini çözmek.",
            "Dante Controller, clock master, sample rate, subscriptions, IP, switch, QoS, multicast ve redundant network.",
            "Topoloji -> IP -> clock -> device discovery -> subscriptions -> latency/QoS -> failover testi."),
        new AgencyAgent("lighting_tech","LIGHTING TECH",
            "Sahne ışık sisteminin kurulum, patch, adresleme ve operasyonunu yönetmek.",
            "Avolites, DMX, universe, fixture patch, moving head, wash, beam, strobe, dimmer ve sahne güvenliği.",
            "Fixture list -> adres/universe -> patch -> test -> cue/scene -> show operasyonu -> yedekleme."),
        new AgencyAgent("event_production_manager","EVENT PRODUCTION MANAGER",
            "Ses, ışık, sahne, LED, ekip ve zaman planını tek üretim akışında koordine etmek.",
            "Technical schedule, crew call, load-in/out, venue coordination, rider, risk, budget ve show call.",
            "Brief -> teknik kapsam -> ekipman -> ekip -> zaman çizelgesi -> risk -> load-in -> show -> load-out.")
    ));

    private AgencyCatalog() {}

    public static List<AgencyAgent> all() { return AGENTS; }

    public static AgencyAgent find(String query) {
        if (query == null) return null;
        String q = normalize(query);
        for (AgencyAgent a : AGENTS) {
            if (normalize(a.id).equals(q) || normalize(a.name).equals(q)) return a;
            if (q.contains(normalize(a.name)) || normalize(a.name).contains(q)) return a;
        }
        return null;
    }

    public static String listText() {
        StringBuilder b = new StringBuilder("STAGEPULSE AGENTS\n");
        for (int i = 0; i < AGENTS.size(); i++) {
            b.append(i + 1).append(". ").append(AGENTS.get(i).name).append("\n");
        }
        return b.toString().trim();
    }

    private static String normalize(String s) {
        return s.toLowerCase(new Locale("tr","TR"))
                .replace("ı","i").replace("ğ","g").replace("ü","u")
                .replace("ş","s").replace("ö","o").replace("ç","c")
                .replace("_"," ").trim();
    }
}
