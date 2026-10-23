# -*- coding: utf-8 -*-
"""Stagepulse domain-specialist runtime for JARVIS.

These are role-conditioned agents backed by the configured JARVIS LLM, with
small deterministic engineering tools where the math is well-defined. They
are not separate trained models and never claim to have measured real venues.
"""
from __future__ import annotations

import ipaddress
import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class AgentSpec:
    id: str
    name: str
    mission: str
    system_prompt: str
    aliases: tuple


_COMMON = (
    "Teknik yanıtı Türkçe ver; gerektiğinde standart İngilizce terimi parantez içinde yaz. "
    "Önce problemi ve karar ölçütünü tanımla. Kullanılmayan varsayımları gerçek gibi sunma. "
    "Bilinmeyen girdileri açıkça listele; gerekli olduğunda tek tek soru sor ama mevcut verilerle "
    "yararlı bir ön analiz üret. Hesaplamada formülü, birimi ve ara varsayımları göster. "
    "Cihaz/marka uyumluluğunu üretici belgesiyle doğrulanmadıkça kesin iddia etme. "
    "Fiziksel ölçüm, RF taraması, Dante Controller keşfi, gerçek cihaz kontrolü veya dosya üretimi "
    "gerçekten çalıştırılmadıysa yapılmış olduğunu söyleme. Sonucu şu sırayla düzenle: "
    "1) sonuç, 2) gerekçe/hesap, 3) uygulanabilir adımlar, 4) eksik veri ve risk, 5) doğrulama testi."
)

_SPECS = (
    AgentSpec("foh_engineer", "FOH ENGINEER",
        "Ana PA miksinin, kanal akışının ve dinleyici alanı ses dengesinin teknik lideri.",
        "FOH uzmanısın. Input list/patch, preamp gain ve headroom, polarite, HPF, filtre/EQ, "
        "dinamik işlem, bus/matrix, FX, LR/sub yönlendirme, PA-SPL dengesi ve soundcheck sırasını "
        "incele. Midas M32 Live varsayılan konsol tercihi; kullanıcı başka model verdiyse onu esas al. "
        "Kanal bazında tablo, bus planı, metreleme ve soundcheck kontrol listesi üret. "
        "Gerçek sinyal görmeden miksin veya gain'in doğrulandığını iddia et.",
        ("foh", "mix engineer", "ön alan", "ana miks", "gain structure")),
    AgentSpec("monitor_engineer", "MONITOR ENGINEER",
        "Sahne monitörü, aux bus ve IEM gereksinimlerinin tasarımı.",
        "Monitör uzmanısın. Her sanatçı için kaynaklar, wedge/IEM, mix bus, pre/post, EQ, "
        "talkback/cue, RF koordinasyon bağımlılıkları ve yedekleme gereksinimlerini ayır. "
        "Feedback riskini frekans ezberinden değil, mikrofon-hoparlör geometrisi ve gerçek testten değerlendir. "
        "Sanatçı miks tablosu, patch ve soundcheck akışı üret.",
        ("monitor", "iem", "wedge", "kulak ici", "monitör")),
    AgentSpec("rf_engineer", "RF ENGINEER",
        "Kablosuz mikrofon ve IEM sistemleri için güvenilir RF planı.",
        "RF uzmanısın. Sistem modeli, ülke/bölge, yasal spektrum aralığı, verici sayısı, cihaz bandı, "
        "antenler, kablolar ve çevredeki RF yoğunluğu olmadan kesin frekans listesi verme. "
        "Frekans koordinasyonu için scan verisi ve uygun üretici/koordinasyon aracı gerektiğini belirt. "
        "Ön kontrol, koordinasyon girdileri, anten dağıtımı, yedek kanal ve prova planı hazırla.",
        ("rf", "wireless", "kablosuz", "frekans", "shure", "ulx", "psm")),
    AgentSpec("system_tech", "SYSTEM TECH",
        "PA, sub, monitor, DSP, kablo ve sinyal zinciri saha kurulum denetimi.",
        "System tech uzmanısın. Sinyal akışını kaynak→konsol→DSP→amplifikasyon/aktif hoparlör şeklinde izle. "
        "Kablo, pinout, polarity, gain staging, güç, güvenli rigging, gecikme, faz ve devreye alma "
        "kontrollerini ayır. Hoparlör üreticisinin rigging/limit belgeleri yoksa askı güvenliğini onaylama. "
        "Saha kontrol listesi ve arıza izolasyon ağacı oluştur.",
        ("system tech", "sistem teknisyeni", "patch", "polarite", "sinyal akışı", "line array")),
    AgentSpec("rider_analyst", "RIDER ANALYST",
        "Teknik rider'ı denetlenebilir ekipman, kanal, personel ve risk listesine dönüştürmek.",
        "Rider uzmanısın. Verilen metinden şartları çıkar; MUST/SHOULD/OPTIONAL olarak sınıflandır; "
        "marka-model/adet, kanal listesi, mikrofon/DI, monitör/IEM, RF, backline, güç, sahne ölçüsü, "
        "ışık, LED, personel ve zaman çizelgesini tablolaştır. Çelişkileri, belirsiz adetleri ve "
        "alternatif kabul koşullarını ayrı göster. Belgeyi görmeden rider'ı analiz ettiğini iddia etme.",
        ("rider", "teknik şartname", "input list", "ekipman listesi", "backline")),
    AgentSpec("stage_plot_engineer", "STAGE PLOT ENGINEER",
        "Sahne yerleşimi, giriş/çıkış patch'i, monitor pozisyonları ve kablo yolları.",
        "Stage plot uzmanısın. Ölçülü koordinat sistemi tanımla; sahne ön/arka yönü, artist, drum, "
        "DI, mikrofon standı, monitör, IEM, stagebox, kablo yolları ve çıkış noktalarını numaralandır. "
        "Boyut verilmiyorsa ölçekli plan yaptığını iddia etme; taslak ve eksik ölçüleri belirt. "
        "Koordinatlı yerleşim tablosu ve patch legend üret.",
        ("stage plot", "sahne plan", "sahne yerleşimi", "stageplot", "sahne çizimi")),
    AgentSpec("spl_calculator", "SPL CALCULATOR",
        "Ses basınç seviyesi, uzaklık, kaynak toplamı, delay ve tahmin belirsizliği hesapları.",
        "SPL/akustik hesap uzmanısın. dB-SPL, dBA, peak/Leq ve ölçüm ağırlıklandırmasını karıştırma. "
        "Serbest alan noktasal kaynak tahmininde mesafe farkını 20 log10(r2/r1) ile uygula ve bunun "
        "idealize tahmin olduğunu belirt. Kaynakların seviyelerini her durumda aritmetik toplama; "
        "koherens/konum/oktav bilgisi yoksa basit enerji toplamının sınırını açıkla. "
        "Yasal sınırlar ve maruziyet için yer/zaman/ölçüm koşulları gerekir. Fiziksel SPL metre verisi "
        "yoksa hesap sonucunu ölçüm diye adlandırma.",
        ("spl", "ses basınç", "desibel", "db spl", "akustik hesap", "delay hesabı")),
    AgentSpec("audio_system_designer", "AUDIO SYSTEM DESIGNER",
        "Mekân ve etkinlik ihtiyaçlarından uçtan uca PA, sub, monitor, kontrol ve kapsama mimarisi.",
        "Sistem tasarım uzmanısın. Önce mekân, seyirci geometrisi, hedef SPL/Leq, gürültü kısıtları, "
        "açık/kapalı alan, elektrik, rigging, bütçe ve mevcut envanteri topla. Sonra kapsama, yönlenme, "
        "sub dağılımı, DSP, console/I/O, monitör, RF, güç ve yedeklemeyi tasarla. "
        "Tek bir marka/ürün kararını fiyat ve teknik veri doğrulanmadan kesinleştirme. "
        "Kapsama yazılımı/ölçüm olmadan precise SPL/coverage garantisi verme.",
        ("system design", "ses sistemi tasarla", "pa tasarımı", "ses sistemi", "coverage", "hoparlör yerleşimi")),
    AgentSpec("live_sound_troubleshooter", "LIVE SOUND TROUBLESHOOTER",
        "Canlı ses arızalarını güvenli ve tekrarlanabilir testlerle kök nedene indirmek.",
        "Canlı ses arıza uzmanısın. Belirtiyi netleştir, sinyal zincirini böl, bilinen-iyi kaynak/kabloyla "
        "tek değişken testi öner. No signal, hum, distortion, feedback, clipping, phase, dropout ve "
        "clock sorunlarını birbirinden ayır. Güç/rigging risklerinde sistemi güvenli duruma aldır. "
        "Olasılıkları kanıt düzeyine göre sırala; test etmeden kök nedeni kesin ilan etme.",
        ("troubleshoot", "arıza", "ses gelmiyor", "hum", "feedback", "distorsiyon", "cızırtı")),
    AgentSpec("dante_network_engineer", "DANTE NETWORK ENGINEER",
        "Dante/IP ses ağında clock, abonelik, IP, QoS, gecikme ve yedeklilik kontrolü.",
        "Dante ağ uzmanısın. Önce cihaz modeli/firmware, sample rate, IP subnet, switch topolojisi, "
        "primary/secondary ağ, clock leader ve subscription durumunu iste. Dante Controller çıktısı "
        "yoksa discovery veya clock durumunu görmüş gibi davranma. QoS/multicast önerisini switch modeli "
        "ve üretici kılavuzuna bağla. Aşamalı teşhis ve geri dönüş planı üret.",
        ("dante", "clock master", "subscription", "dante controller", "audio network")),
    AgentSpec("lighting_tech", "LIGHTING TECH",
        "DMX, fixture patch, adres/universe, cue ve show-file hazırlığı.",
        "Işık teknik uzmanısın. Fixture marka/model, mode, kanal sayısı, DMX adresi, universe, "
        "kontrol masası, güç ve rigging bilgileriyle patch planı oluştur. Fixture mode bilgisi olmadan "
        "DMX adreslerini kesinleştirme. Avolites kullanıcı belirtmedikçe sabit konsol varsayma; "
        "fixture library uyumluluğunu gerçek masa üzerinde kontrol etmeyi ekle.",
        ("lighting", "dmx", "ışık", "avolites", "fixture", "universe", "ışık masası")),
    AgentSpec("event_production_manager", "EVENT PRODUCTION MANAGER",
        "Etkinlik teknik prodüksiyonunu ekip, takvim, bütçe ve risk üzerinden koordine etmek.",
        "Prodüksiyon yöneticisisin. Brief'i teslim edilebilir iş paketlerine ayır; sorumlular, bağımlılıklar, "
        "load-in, line check, soundcheck, kapı, show call, load-out ve teslim tarihleri çıkar. "
        "Bütçede kira/satın alma, nakliye, işçilik, enerji, yedek ve vergi kalemlerini ayır; güncel fiyat "
        "kaynağı yoksa fiyat uydurma. Risk sahibi, önlem ve yedek planı belirt.",
        ("production", "etkinlik", "organizasyon", "prodüksiyon", "load in", "show plan")),
)

_REGISTRY: Dict[str, AgentSpec] = {spec.id: spec for spec in _SPECS}


def _norm(value: str) -> str:
    value = str(value or "").lower().replace("ı", "i")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9_ ]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def get_agent(agent_id: str) -> Optional[AgentSpec]:
    key = _norm(agent_id).replace(" ", "_")
    return _REGISTRY.get(key)


def route_agent(task: str) -> Optional[str]:
    text = _norm(task)
    # Specific tools/roles should win over the broad "audio system" role.
    priorities = (
        ("dante_network_engineer", ("dante", "clock master", "subscription")),
        ("rf_engineer", ("rf ", "rf engineer", "kablosuz", "ulx d", "psm300", "frekans koordin")),
        ("spl_calculator", ("spl", "db spl", "desibel", "ses basinc", "ses seviyesi hesap", "delay hesap")),
        ("rider_analyst", ("rider", "input list", "teknik sartname", "teknik gereksinim")),
        ("stage_plot_engineer", ("stage plot", "stageplot", "sahne plani", "sahne yerlesim")),
        ("monitor_engineer", ("monitor", "monitör", "iem", "wedge")),
        ("lighting_tech", ("dmx", "avolites", "fixture", "isık", "isik", "isiklandirma")),
        ("live_sound_troubleshooter", ("ses gelmiyor", "feedback", "cizirti", "hum", "distorsiyon", "dropout", "sorun gider")),
        ("foh_engineer", ("foh", "ana miks", "gain structure", "kanal eq", "miks ayar")),
        ("system_tech", ("patch", "sinyal akisi", "line array", "polarite", "sistem teknisyeni")),
        ("event_production_manager", ("etkinlik plani", "prodüksiyon", "produksiyon", "load in", "show call")),
        ("audio_system_designer", ("ses sistemi", "pa tasarim", "hoparlor yerlesim", "coverage", "kapsama")),
    )
    for agent_id, needles in priorities:
        if any(_norm(needle) in text for needle in needles):
            return agent_id
    return None


def _number(task: str, key: str):
    match = re.search(r"(?i)(?:^|\b)" + re.escape(key) + r"\s*=\s*(-?\d+(?:[.,]\d+)?)", task)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))

def _engineering_tool_output(agent_id: str, task: str) -> str:
    lines = []
    if agent_id == "spl_calculator":
        ref_db = _number(task, "ref_db")
        ref_m = _number(task, "ref_m")
        target_m = _number(task, "target_m")
        power_ratio = _number(task, "power_ratio")
        sources = _number(task, "sources")
        # Accept natural spoken forms such as "100 dB at 1 metre, how much at 10 metres?"
        level_match = re.search(r"(?i)(-?\\d+(?:[.,]\\d+)?)\\s*dB(?:\\s*SPL)?\\b", task)
        if ref_db is None and level_match:
            ref_db = float(level_match.group(1).replace(",", "."))
        distance_values = [
            float(value.replace(",", "."))
            for value in re.findall(r"(?i)(\\d+(?:[.,]\\d+)?)\\s*(?:m\\b|metre(?:de|den|ye|lik)?\\b)", task)
        ]
        if len(distance_values) >= 2:
            if ref_m is None:
                ref_m = distance_values[0]
            if target_m is None:
                target_m = distance_values[1]
        if ref_db is not None and ref_m is not None and target_m is not None:
            if ref_m <= 0 or target_m <= 0:
                lines.append("HESAPLAMA HATASI: ref_m ve target_m sıfırdan büyük olmalı.")
            else:
                power_ratio = 1.0 if power_ratio is None else power_ratio
                sources = 1.0 if sources is None else sources
                if power_ratio <= 0 or sources <= 0:
                    lines.append("HESAPLAMA HATASI: power_ratio ve sources sıfırdan büyük olmalı.")
                else:
                    result = ref_db - 20 * math.log10(target_m / ref_m)
                    result += 10 * math.log10(power_ratio) + 10 * math.log10(sources)
                    lines.append(
                        "ARAÇ SONUCU (idealize serbest alan tahmini): "
                        f"{result:.2f} dB; ref_db={ref_db:g}, ref_m={ref_m:g} m, "
                        f"target_m={target_m:g} m, power_ratio={power_ratio:g}, sources={sources:g}. "
                        "Yansıma, yönlülük, faz, sınır yüzeyleri, compression/limiting ve spektral içerik dahil değil."
                    )
        distance = _number(task, "delay_distance_m")
        if distance is None:
            delay_match = re.search(r"(?i)(?:delay|gecikme|mesafe)\\D{0,24}(\\d+(?:[.,]\\d+)?)\\s*(?:m\\b|metre)", task)
            if not delay_match:
                delay_match = re.search(r"(?i)(\\d+(?:[.,]\\d+)?)\\s*(?:m\\b|metre)\\D{0,12}(?:delay|gecikme)", task)
            if delay_match:
                distance = float(delay_match.group(1).replace(",", "."))
        if distance is not None:
            if distance < 0:
                lines.append("HESAPLAMA HATASI: delay_distance_m negatif olamaz.")
            else:
                lines.append(f"ARAÇ SONUCU: {distance / 343.0 * 1000.0:.2f} ms (343 m/s ses hızı varsayımı, yaklaşık 20 °C).")
    if agent_id == "spl_calculator":
        level1 = _number(task, "level1_db")
        level2 = _number(task, "level2_db")
        if level1 is not None and level2 is not None:
            high, low = max(level1, level2), min(level1, level2)
            combined = high + 10.0 * math.log10(1.0 + (10.0 ** ((low - high) / 10.0)))
            lines.append(f"ARAÇ SONUCU: İki bağımsız enerji kaynağının ideal enerji toplamı {combined:.2f} dB. Faz/koherens ve konum etkileri modele dahil değil.")

    if agent_id == "foh_engineer":
        peak = _number(task, "peak_dbfs")
        target_peak = _number(task, "target_peak_dbfs")
        if peak is not None and target_peak is not None:
            trim = target_peak - peak
            if trim < 0:
                lines.append(f"ARAÇ SONUCU: Belirtilen tepe seviyesini hedefe indirmek için yaklaşık {abs(trim):.2f} dB kazanç azaltımı gerekir.")
            else:
                lines.append(f"ARAÇ SONUCU: Verilen tepe/hedef değerlerine göre {trim:.2f} dB dijital pay bulunuyor. Bu, analog giriş headroom'unu tek başına doğrulamaz.")

    if agent_id == "audio_system_designer":
        distance = _number(task, "throw_m")
        angle = _number(task, "horizontal_coverage_deg")
        if distance is not None and angle is not None:
            if distance < 0 or angle <= 0 or angle >= 180:
                lines.append("HESAPLAMA HATASI: throw_m negatif olamaz; horizontal_coverage_deg 0 ile 180 arasında olmalı.")
            else:
                width = 2.0 * distance * math.tan(math.radians(angle) / 2.0)
                lines.append(f"ARAÇ SONUCU: {distance:g} m mesafede {angle:g}° yatay açı için ideal geometrik genişlik yaklaşık {width:.2f} m. Gerçek akustik kapsama/level uniformity garantisi değildir.")

    if agent_id == "lighting_tech":
        address = _number(task, "address")
        channels = _number(task, "channels")
        universe = _number(task, "universe")
        if address is not None and channels is not None:
            if int(address) != address or int(channels) != channels or address < 1 or address > 512 or channels < 1 or channels > 512:
                lines.append("HESAPLAMA HATASI: DMX address 1–512, channels ise 1–512 tam sayı olmalı.")
            elif address + channels - 1 > 512:
                lines.append(f"HESAPLAMA HATASI: Fixture {int(address)} adresinden başlayıp {int(channels)} kanal kullanırsa DMX 512 sınırını aşar.")
            else:
                suffix = f", universe={int(universe)}" if universe is not None and universe > 0 else ""
                lines.append(f"ARAÇ SONUCU: DMX adres aralığı {int(address)}–{int(address + channels - 1)}{suffix}; bir sonraki fixture için önerilen başlangıç {int(address + channels)}. Fixture mode kanal sayısı doğrulanmalı.")

    if agent_id == "dante_network_engineer":
        device_ip = re.search(r"(?i)\bdevice_ip\s*=\s*([0-9.]+)", task)
        peer_ip = re.search(r"(?i)\bpeer_ip\s*=\s*([0-9.]+)", task)
        subnet_mask = re.search(r"(?i)\bsubnet_mask\s*=\s*([0-9.]+)", task)
        if device_ip and peer_ip and subnet_mask:
            try:
                network = ipaddress.IPv4Network(f"{device_ip.group(1)}/{subnet_mask.group(1)}", strict=False)
                peer = ipaddress.IPv4Address(peer_ip.group(1))
                lines.append(f"ARAÇ SONUCU: {device_ip.group(1)} / {subnet_mask.group(1)} ağı {network}; karşı cihaz {peer} " + ("aynı alt ağda." if peer in network else "aynı alt ağda DEĞİL."))
            except ipaddress.AddressValueError:
                lines.append("HESAPLAMA HATASI: device_ip, peer_ip veya subnet_mask geçerli IPv4 adresi değil.")
            except ipaddress.NetmaskValueError:
                lines.append("HESAPLAMA HATASI: subnet_mask geçerli IPv4 maskesi değil.")

    if agent_id == "event_production_manager":
        duration = _number(task, "duration_min")
        buffer_pct = _number(task, "buffer_pct")
        if duration is not None:
            buffer_pct = 0.0 if buffer_pct is None else buffer_pct
            if duration < 0 or buffer_pct < 0 or buffer_pct > 500:
                lines.append("HESAPLAMA HATASI: duration_min negatif olamaz; buffer_pct 0–500 arasında olmalı.")
            else:
                total = duration * (1.0 + buffer_pct / 100.0)
                lines.append(f"ARAÇ SONUCU: {duration:g} dk temel süre + %{buffer_pct:g} tampon = {total:.1f} dk planlama süresi. Gerçek üretim süresi bağımlılık ve saha koşullarına bağlıdır.")

    if agent_id == "system_tech":
        distance = _number(task, "delay_distance_m")
        if distance is not None and distance >= 0:
            lines.append(f"ARAÇ SONUCU: {distance / 343.0 * 1000.0:.2f} ms teorik ses gecikmesi (343 m/s varsayımı).")
    return "\n".join(lines)


def prepare_expert_task(agent_id: str, task: str) -> tuple[str, str]:
    """Return (system instructions, optional deterministic tool result)."""
    spec = get_agent(agent_id) if agent_id else None
    if spec is None:
        spec_id = route_agent(task)
        spec = _REGISTRY.get(spec_id or "")
    if spec is None:
        return "", ""
    system = (
        f"STAGEPULSE DOMAIN AGENT: {spec.name}\nMISSION: {spec.mission}\n"
        f"{spec.system_prompt}\n\nENGINEERING QUALITY STANDARD: {_COMMON}"
    )
    tool_output = _engineering_tool_output(spec.id, task)
    return system, tool_output


def list_agents() -> list[dict]:
    return [{"id": s.id, "name": s.name, "mission": s.mission} for s in _SPECS]
