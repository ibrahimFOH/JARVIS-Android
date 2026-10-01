# -*- coding: utf-8 -*-
"""JARVIS V2 - Free Multi-AI + Turkish full installer.
Run from the root of the existing J.A.R.V.I.S repository.
"""
from pathlib import Path
from datetime import datetime
import json, shutil, subprocess, sys, re

ROOT = Path(__file__).resolve().parent
if not (ROOT / 'core').exists() or not (ROOT / 'voice').exists():
    print('Bu dosyayi C:\\Jarvis\\J.A.R.V.I.S klasorunde calistirin.')
    sys.exit(2)

STAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
BACKUP = ROOT / 'backup_free_multi_ai' / STAMP

FILES = [
    'core/ai_brain.py','core/command_processor.py','core/intent_recognizer.py',
    'core/jarvis.py','voice/speech_recognition.py','voice/text_to_speech.py',
    'personality/response_generator.py','gui/main_window.py','config/config.json',
    'config/config.example.json','requirements.txt'
]

def backup():
    for rel in FILES:
        src = ROOT / rel
        if src.exists():
            dst = BACKUP / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    print('[OK] Yedek:', BACKUP)

def write(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')
    print('[OK]', rel)

def update_config():
    p = ROOT / 'config/config.json'
    data = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    data.setdefault('voice', {}).update({
        'recognition_engine':'google','recognition_language':'tr-TR',
        'recognition_timeout':5,'phrase_time_limit':10,
        'tts_voice':'auto-turkish','tts_rate':165,'tts_volume':0.9,
        'dynamic_energy_threshold':True
    })
    data.setdefault('personality', {}).update({'address_user_as':'Patron','language':'tr-TR'})
    data['ai'] = {
        'enabled': True, 'strategy':'automatic', 'free_only':True,
        'max_output_tokens':450, 'timeout_seconds':25,
        'providers': [
            {'name':'gemini','enabled':True,'model':'gemini-2.5-flash-lite','key_env':'GEMINI_API_KEY'},
            {'name':'groq','enabled':True,'model':'openai/gpt-oss-20b','key_env':'GROQ_API_KEY'},
            {'name':'huggingface','enabled':True,'model':'google/gemma-2-2b-it','key_env':'HF_TOKEN'},
            {'name':'openai','enabled':True,'model':'gpt-5.6-luna','key_env':'OPENAI_API_KEY'}
        ]
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print('[OK] config/config.json')

AI_BRAIN = r'''# -*- coding: utf-8 -*-
"""Provider-agnostic AI router with free-tier-first failover."""
import os, re
from typing import Dict, Any, Optional
import requests
from utils.logger import get_logger
from utils.config_manager import get_config

logger = get_logger()
config = get_config()

SYSTEM = ("Sen JARVIS'sin. Daima Türkçe konuş. Kullanıcıya PATRON diye hitap et. "
          "Kısa, doğal, doğru ve faydalı cevap ver. Bilmediğin bilgiyi uydurma. "
          "Komut gerekiyorsa net ve uygulanabilir anlat.")

class AIBrain:
    def __init__(self):
        self.enabled = bool(config.get('ai.enabled', True))
        self.timeout = int(config.get('ai.timeout_seconds', 25))
        self.max_tokens = int(config.get('ai.max_output_tokens', 450))
        self.providers = config.get('ai.providers', []) or []
        logger.info('AI router ready: ' + ', '.join(p.get('name','?') for p in self.providers))

    def ask(self, command: str) -> Dict[str, Any]:
        command = (command or '').strip()
        local = self._local(command)
        if local:
            return {'success': True, 'response': local, 'intent':'ai_local', 'provider':'local'}
        weather = self._weather(command)
        if weather:
            return {'success': True, 'response': weather, 'intent':'weather', 'provider':'wttr.in'}
        if not self.enabled:
            return self._offline()

        errors=[]
        for p in self.providers:
            if not p.get('enabled', True):
                continue
            name=p.get('name','')
            key_env=p.get('key_env','')
            key=os.getenv(key_env,'')
            if not key:
                logger.info(f'AI provider skipped: {name} (missing {key_env})')
                continue
            try:
                text=self._call(name, key, p.get('model',''), command)
                if text:
                    logger.info(f'AI response provider: {name}')
                    return {'success':True,'response':text.strip(),'intent':'ai','provider':name}
            except Exception as e:
                msg=str(e)
                errors.append(f'{name}: {msg}')
                logger.warning(f'AI provider failed: {name}: {msg}')
                continue
        logger.error('All AI providers failed: ' + ' | '.join(errors[-4:]))
        return self._offline(errors)

    def _call(self, name, key, model, command):
        if name == 'gemini':
            url=f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
            payload={'system_instruction':{'parts':[{'text':SYSTEM}]},
                     'contents':[{'role':'user','parts':[{'text':command}]}],
                     'generationConfig':{'maxOutputTokens':self.max_tokens,'temperature':0.4}}
            r=requests.post(url, params={'key':key}, json=payload, timeout=self.timeout)
            self._raise(r)
            data=r.json()
            return data['candidates'][0]['content']['parts'][0]['text']
        if name == 'groq':
            return self._openai_compatible('https://api.groq.com/openai/v1/chat/completions',key,model,command)
        if name == 'huggingface':
            return self._openai_compatible('https://router.huggingface.co/v1/chat/completions',key,model,command)
        if name == 'openai':
            # OpenAI is intentionally last. A zero-credit key simply falls through to the next provider.
            try:
                from openai import OpenAI
                client=OpenAI(api_key=key, timeout=self.timeout)
                r=client.responses.create(model=model,instructions=SYSTEM,input=command,max_output_tokens=self.max_tokens)
                return getattr(r,'output_text','') or ''
            except Exception as e:
                raise RuntimeError(str(e))
        raise RuntimeError('unknown provider')

    def _openai_compatible(self,url,key,model,command):
        payload={'model':model,'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':command}],
                 'temperature':0.4,'max_tokens':self.max_tokens}
        r=requests.post(url,headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'},json=payload,timeout=self.timeout)
        self._raise(r)
        data=r.json()
        return data['choices'][0]['message']['content']

    @staticmethod
    def _raise(r):
        if r.ok: return
        try: detail=r.json().get('error', r.text)
        except Exception: detail=r.text
        raise RuntimeError(f'HTTP {r.status_code}: {detail}')

    def _local(self,c):
        low=c.lower().strip()
        if 'neden ingilizce' in low or 'neden ingilizce konuş' in low or 'neden ingilizce konus' in low:
            return 'Artık Türkçe konuşuyorum, PATRON. AI yönlendiricisi de ücretsiz sağlayıcılar arasında otomatik geçiş yapacak şekilde ayarlandı.'
        if low in ('merhaba','selam','selam jarvis','merhaba jarvis','hey jarvis'):
            return 'Merhaba PATRON. Hazırım.'
        return None

    def _weather(self,c):
        low=c.lower()
        keys=('hava kaç','hava nasil','hava nasıl','kaç derece','kac derece','sıcaklık kaç','sicaklik kac','hava durumu')
        if not any(k in low for k in keys): return None
        city='Hatay'
        for n in ['istanbul','ankara','izmir','hatay','antalya','adana','gaziantep','reyhanlı','reyhanli','antakya']:
            if n in low: city=n
        try:
            r=requests.get(f'https://wttr.in/{city}?format=j1',timeout=10)
            if not r.ok: return None
            d=r.json()['current_condition'][0]
            temp=d.get('temp_C','?'); feels=d.get('FeelsLikeC','?'); desc=d.get('lang_tr',[{'value':''}])[0].get('value','')
            return f'{city.title()} için sıcaklık {temp} derece, hissedilen {feels} derece. {desc}'.strip()
        except Exception as e:
            logger.warning('Weather request failed: '+str(e)); return None

    def _offline(self,errors=None):
        if errors:
            return {'success':False,'response':'PATRON, ücretsiz AI sağlayıcılarının hiçbiri şu anda cevap vermiyor. API anahtarları veya kotalar kontrol edilmeli.','intent':'ai_unavailable'}
        return {'success':False,'response':'PATRON, AI bağlantısı şu anda kullanılamıyor.','intent':'ai_unavailable'}
'''

SPEECH = r'''"""Turkish-first speech recognition for JARVIS."""
import speech_recognition as sr
from typing import Optional, Dict, Any
from utils.logger import get_logger
from utils.config_manager import get_config
logger=get_logger(); config=get_config()
class SpeechRecognizer:
    def __init__(self):
        self.recognizer=sr.Recognizer(); self.microphone=sr.Microphone()
        self.engine=config.get('voice.recognition_engine','google')
        self.language=config.get('voice.recognition_language','tr-TR')
        self.timeout=config.get('voice.recognition_timeout',5)
        self.phrase_limit=config.get('voice.phrase_time_limit',10)
        self.recognizer.energy_threshold=config.get('voice.energy_threshold',4000)
        self.recognizer.dynamic_energy_threshold=config.get('voice.dynamic_energy_threshold',True)
        self._calibrate()
    def _calibrate(self):
        try:
            logger.info('Calibrating microphone for ambient noise...')
            with self.microphone as source: self.recognizer.adjust_for_ambient_noise(source,duration=1)
            logger.info(f'Calibration complete. Energy threshold: {self.recognizer.energy_threshold}')
        except Exception as e: logger.warning('Could not calibrate microphone: '+str(e))
    def listen(self,timeout:Optional[float]=None,phrase_time_limit:Optional[float]=None)->Dict[str,Any]:
        try:
            with self.microphone as source:
                try: audio=self.recognizer.listen(source,timeout=timeout or self.timeout,phrase_time_limit=phrase_time_limit or self.phrase_limit)
                except sr.WaitTimeoutError: return {'success':False,'error':'timeout','message':'No speech detected'}
            text=self._recognize_audio(audio)
            if text: logger.info('Recognized: '+text); return {'success':True,'text':text}
            return {'success':False,'error':'no_recognition','message':'Ses anlaşılamadı'}
        except Exception as e:
            logger.error('Speech recognition error: '+str(e)); return {'success':False,'error':'exception','message':str(e)}
    def _recognize_audio(self,audio):
        try:
            if self.engine=='google': return self.recognizer.recognize_google(audio,language=self.language)
            if self.engine=='sphinx': return self.recognizer.recognize_sphinx(audio)
            return self.recognizer.recognize_google(audio,language=self.language)
        except sr.UnknownValueError: return None
        except sr.RequestError as e: logger.error('Recognition service error: '+str(e)); return None
        except Exception as e: logger.error('Recognition error: '+str(e)); return None
    def test_microphone(self):
        try:
            with self.microphone as source: self.recognizer.listen(source,timeout=2,phrase_time_limit=2)
            return {'success':True,'message':'Mikrofon çalışıyor'}
        except sr.WaitTimeoutError: return {'success':True,'message':'Mikrofon çalışıyor, ses algılanmadı'}
        except Exception as e: return {'success':False,'message':'Mikrofon testi başarısız: '+str(e)}
    def set_energy_threshold(self,threshold:int): self.recognizer.energy_threshold=threshold
    def recalibrate(self): self._calibrate()
'''

TTS = r'''"""Turkish-first Windows TTS for JARVIS."""
import pyttsx3
from utils.logger import get_logger
from utils.config_manager import get_config
logger=get_logger(); config=get_config()
class TextToSpeech:
    def __init__(self):
        try:
            self.engine=pyttsx3.init(); self.rate=config.get('voice.tts_rate',165); self.volume=config.get('voice.tts_volume',0.9)
            self.engine.setProperty('rate',self.rate); self.engine.setProperty('volume',self.volume)
            voice=config.get('voice.tts_voice','auto-turkish'); self.available=True
            if voice=='auto-turkish': self._find_turkish_voice()
            elif voice!='default': self._set_voice(voice)
            logger.info('Text-to-speech initialized successfully')
        except Exception as e: logger.error('Failed to initialize text-to-speech: '+str(e)); self.engine=None; self.available=False
    def _find_turkish_voice(self):
        try:
            voices=self.engine.getProperty('voices') or []
            needles=('turkish','tr-tr','tr_tr','turk','türk')
            for v in voices:
                blob=(str(getattr(v,'id',''))+' '+str(getattr(v,'name',''))+' '+str(getattr(v,'languages',''))).lower()
                if any(n in blob for n in needles):
                    self.engine.setProperty('voice',v.id); logger.info('Turkish voice selected: '+str(v.name)); return True
            logger.warning('No Turkish Windows TTS voice found; using default voice'); return False
        except Exception as e: logger.warning('Turkish voice scan failed: '+str(e)); return False
    def speak(self,text,wait=True):
        if not self.available or not self.engine: return False
        try:
            self.engine.say(text)
            if wait: self.engine.runAndWait()
            return True
        except Exception as e: logger.error('Speech error: '+str(e)); return False
    def stop(self):
        if self.available and self.engine:
            try:self.engine.stop()
            except Exception:pass
    def set_rate(self,rate): self.rate=rate; self.engine.setProperty('rate',rate)
    def set_volume(self,volume): self.volume=max(0,min(1,volume)); self.engine.setProperty('volume',self.volume)
    def get_voices(self):
        try:return [{'id':v.id,'name':v.name} for v in self.engine.getProperty('voices')]
        except Exception:return []
    def set_voice(self,voice_id): return self._set_voice(voice_id)
    def _set_voice(self,voice_id):
        try:
            for v in self.engine.getProperty('voices'):
                if voice_id in v.id or voice_id.lower() in v.name.lower(): self.engine.setProperty('voice',v.id); return True
        except Exception: pass
        return False
    def save_to_file(self,text,filename):
        try:self.engine.save_to_file(text,filename); self.engine.runAndWait(); return True
        except Exception:return False
'''

RESPONSE = r'''"""Turkish response/personality layer."""
import random
from utils.config_manager import get_config
from utils.helpers import get_time_greeting
config=get_config()
class ResponseTemplates:
    def __init__(self):
        p=config.get('personality',{}); self.address_as=p.get('address_user_as','Patron'); self.wit_enabled=p.get('wit_enabled',True)
    def get_greeting(self):
        g=get_time_greeting(); return random.choice([f'{g}, {self.address_as}. JARVIS çevrimiçi ve hazır.',f'{g}, {self.address_as}. Tüm sistemler çalışıyor.',f'{g}, {self.address_as}. Hazırım.'])
    def get_acknowledgment(self,intent): return None
    def format_success(self,intent,details=None): return f'İşlem tamamlandı, {self.address_as}.' if not details else f'{details}, {self.address_as}.'
    def format_error(self,intent,error): return f'Bir sorun oluştu, {self.address_as}. {error}'
    def format_confirmation_request(self,intent,details): return f'{details} işlemini gerçekleştirmemi onaylıyor musunuz?'
    def format_clarification_request(self,intent,context=None): return f'Biraz daha ayrıntı verir misiniz, {self.address_as}?'
    def format_suggestion(self,suggestions): return '\n'.join('- '+s for s in suggestions)
    def get_witty_response(self,context): return None
    def get_status_response(self): return f'Sistemler çevrimiçi ve çalışıyor, {self.address_as}.'
    def get_help_response(self): return f'Komutlarınızı doğal Türkçe ile verebilirsiniz, {self.address_as}. Uygulama açma, kapatma, ekran görüntüsü, ses, dosya, sistem durumu, hava durumu ve genel sorular destekleniyor.'
    def get_thank_response(self): return f'Rica ederim, {self.address_as}.'
    def get_unknown_intent_response(self): return f'Komutu tam anlayamadım, {self.address_as}. AI yönlendiricisini de deneyeceğim.'
class ResponseGenerator:
    def __init__(self): self.templates=ResponseTemplates()
    def generate(self,response_type,**kwargs):
        m=getattr(self,'_generate_'+response_type,None); return m(**kwargs) if m else self.templates.get_unknown_intent_response()
    def _generate_greeting(self,**k): return self.templates.get_greeting()
    def _generate_acknowledgment(self,intent,**k): return self.templates.get_acknowledgment(intent) or ''
    def _generate_success(self,intent,details=None,**k): return self.templates.format_success(intent,details)
    def _generate_error(self,intent,error,**k): return self.templates.format_error(intent,error)
    def _generate_confirmation(self,intent,details,**k): return self.templates.format_confirmation_request(intent,details)
    def _generate_clarification(self,intent,context=None,**k): return self.templates.format_clarification_request(intent,context)
    def _generate_suggestion(self,suggestions,**k): return self.templates.format_suggestion(suggestions)
    def _generate_status(self,**k): return self.templates.get_status_response()
    def _generate_help(self,**k): return self.templates.get_help_response()
    def _generate_thank(self,**k): return self.templates.get_thank_response()
    def _generate_unknown(self,**k): return self.templates.get_unknown_intent_response()
'''


def patch_command_processor():
    p=ROOT/'core/command_processor.py'; s=p.read_text(encoding='utf-8')
    if 'from core.ai_brain import AIBrain' not in s:
        s=s.replace('from datetime import datetime\n','from datetime import datetime\nfrom core.ai_brain import AIBrain\n')
    if 'self.ai_brain = AIBrain()' not in s:
        s=s.replace('        self.window_manager = WindowManager()\n','        self.window_manager = WindowManager()\n        self.ai_brain = AIBrain()\n')
    start=s.find('    def process(self, command: str) -> Dict[str, Any]:')
    end=s.find('    def _execute_command(',start)
    if start<0 or end<0: raise RuntimeError('command_processor.py process() bölümü bulunamadı')
    method='''    def process(self, command: str) -> Dict[str, Any]:\n        logger.command(command)\n        intent_result = self.intent_recognizer.recognize(command)\n        intent = intent_result['intent']\n        confidence = intent_result['confidence']\n        parameters = intent_result['parameters']\n        logger.debug(f"Intent: {intent}, Confidence: {confidence:.2f}, Params: {parameters}")\n\n        if intent == 'unknown' or confidence < 0.3:\n            ai = self.ai_brain.ask(command)\n            if ai.get('success') or ai.get('intent') in ('ai','ai_local','weather'):\n                return ai\n            return {'success': False, 'response': ai.get('response', self.response_generator.generate('unknown')), 'intent': 'unknown'}\n\n        is_valid, error, warning = self.validator.validate(intent, parameters)\n        if not is_valid:\n            return {'success': False, 'response': self.response_generator.generate('error', intent=intent, error=error), 'intent': intent}\n        if warning and self.validator.requires_confirmation(intent):\n            return {'success': False, 'requires_confirmation': True, 'intent': intent, 'parameters': parameters, 'warning': warning, 'response': self.response_generator.generate('confirmation', intent=intent, details=warning)}\n        return self._execute_command(intent, parameters)\n\n'''
    s=s[:start]+method+s[end:]
    p.write_text(s,encoding='utf-8'); print('[OK] core/command_processor.py -> multi-AI')

def patch_intents():
    p=ROOT/'core/intent_recognizer.py'; s=p.read_text(encoding='utf-8')
    additions={
        "launch_app": "(re.compile(r'\\b(aç|ac|başlat|baslat|çalıştır|calistir)\\s+(.+)', re.I), {'target_group': 2}),",
        "close_app": "(re.compile(r'\\b(kapat|sonlandır|sonlandir)\\s+(.+)', re.I), {'target_group': 2}),",
        "screenshot": "(re.compile(r'\\b(ekran görüntüsü|ekran goruntusu|ekranı çek|ekrani cek)', re.I), {}),",
        "volume": "(re.compile(r'\\b(ses|sesi)\\s+(aç|ac|kıs|kis|artır|artir|azalt|azalt)', re.I), {}),",
        "system_info": "(re.compile(r'\\b(sistem|bilgisayar)\\s+(durumu|bilgisi)', re.I), {}),",
        "time": "(re.compile(r'\\b(saat kaç|saat kac)', re.I), {}),",
        "date": "(re.compile(r'\\b(bugün tarih|bugun tarih|tarih ne)', re.I), {}),",
        "weather": "(re.compile(r'\\b(hava nasıl|hava nasil|hava durumu|kaç derece|kac derece)', re.I), {}),",
        "greeting": "(re.compile(r'\\b(merhaba|selam|günaydın|gunaydin|iyi akşamlar|iyi aksamlar)', re.I), {}),",
        "status": "(re.compile(r'\\b(çevrimiçi misin|cevrimici misin|çalışıyor musun|calisiyor musun|durumun nasıl|durumun nasil)', re.I), {}),",
        "help": "(re.compile(r'\\b(ne yapabiliyorsun|ne yapabilirsin|yardım|yardim)', re.I), {}),",
        "thank": "(re.compile(r'\\b(teşekkürler|tesekkurler|teşekkür ederim|tesekkur ederim)', re.I), {}),"
    }
    for intent,line in additions.items():
        marker=f"'{intent}': ["
        pos=s.find(marker)
        if pos>=0:
            insert=s.find('\n',pos)+1
            if line.strip() not in s[pos:s.find('],',insert)+2]: s=s[:insert]+'                '+line+'\n'+s[insert:]
    p.write_text(s,encoding='utf-8'); print('[OK] core/intent_recognizer.py -> Turkish patterns')

def patch_jarvis():
    p=ROOT/'core/jarvis.py'; s=p.read_text(encoding='utf-8').replace('self.speak("Yes, sir?")','self.speak("Evet, Patron?")')
    p.write_text(s,encoding='utf-8'); print('[OK] core/jarvis.py -> Turkish wake response')

def patch_gui():
    p=ROOT/'gui/main_window.py'; s=p.read_text(encoding='utf-8')
    s=s.replace('ctk.set_default_color_theme("blue")','ctk.set_default_color_theme("dark-blue")')
    s=s.replace('self.root.title("Jarvis V2 - Desktop AI Assistant")','self.root.title("JARVIS • STAGEPULSE AI")')
    s=s.replace('text="Just A Rather Very Intelligent System"','text="YAPAY ZEKA • SES • SİSTEM KONTROLÜ"')
    s=s.replace('text="● ONLINE"','text="● ÇEVRİMİÇİ"')
    s=s.replace('text="Enter command or say \'hey jarvis\'..."','text="Komut yazın veya JARVIS ile konuşun..."')
    s=s.replace('text="Send"','text="Gönder"').replace('text="🎤 Voice"','text="🎤 Ses"').replace('text="Wake Word Detection"','text="Uyandırma Kelimesi"').replace('text="Voice Enabled"','text="Ses Aktif"').replace('text="Clear"','text="Temizle"')
    s=s.replace('greeting = "Good morning, sir. Jarvis online and ready. All systems operational."','greeting = self.jarvis.response_generator.generate(\'greeting\')')
    p.write_text(s,encoding='utf-8'); print('[OK] gui/main_window.py -> Turkish UI')

def update_requirements():
    p=ROOT/'requirements.txt'; s=p.read_text(encoding='utf-8')
    if 'requests>=' not in s: s += '\nrequests>=2.31.0\n'
    p.write_text(s,encoding='utf-8'); print('[OK] requirements.txt')

def update_example():
    p=ROOT/'config/config.example.json'
    data=json.loads(p.read_text(encoding='utf-8'))
    data['voice'].update({'recognition_language':'tr-TR','tts_voice':'auto-turkish','tts_rate':165})
    data['personality'].update({'address_user_as':'Patron','language':'tr-TR'})
    data['ai']={
      'enabled':True,'strategy':'automatic','free_only':True,'max_output_tokens':450,'timeout_seconds':25,
      'providers':[
        {'name':'gemini','enabled':True,'model':'gemini-2.5-flash-lite','key_env':'GEMINI_API_KEY'},
        {'name':'groq','enabled':True,'model':'openai/gpt-oss-20b','key_env':'GROQ_API_KEY'},
        {'name':'huggingface','enabled':True,'model':'google/gemma-2-2b-it','key_env':'HF_TOKEN'},
        {'name':'openai','enabled':True,'model':'gpt-5.6-luna','key_env':'OPENAI_API_KEY'}]}
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8'); print('[OK] config/config.example.json')

def compile_all():
    targets=['core/ai_brain.py','core/command_processor.py','core/intent_recognizer.py','core/jarvis.py','voice/speech_recognition.py','voice/text_to_speech.py','personality/response_generator.py','gui/main_window.py']
    for rel in targets:
        r=subprocess.run([sys.executable,'-m','py_compile',str(ROOT/rel)],capture_output=True,text=True)
        if r.returncode: raise RuntimeError(f'Syntax hatası: {rel}\n{r.stderr}')
        print('[OK] syntax:',rel)

def main():
    print('=== JARVIS FREE MULTI-AI + TURKCE FULL KURULUM ===')
    backup(); update_config(); write('core/ai_brain.py',AI_BRAIN); write('voice/speech_recognition.py',SPEECH); write('voice/text_to_speech.py',TTS); write('personality/response_generator.py',RESPONSE)
    patch_command_processor(); patch_intents(); patch_jarvis(); patch_gui(); update_requirements(); update_example(); compile_all()
    print('\n=== TAMAMLANDI ===')
    print('AI sirasi: Gemini -> Groq -> Hugging Face -> OpenAI -> yerel/offline')
    print('Dil: Türkçe / tr-TR')
    print('GUI: koyu + Stagepulse altın/beyaz yönü')
    print('Yedek:',BACKUP)
    print('\nAPI anahtarlarını Windows ortam değişkeni olarak ekleyin:')
    print('  GEMINI_API_KEY   (Google AI Studio ücretsiz katman)')
    print('  GROQ_API_KEY     (Groq ücretsiz plan)')
    print('  HF_TOKEN         (Hugging Face ücretsiz kredi)')
    print('OpenAI anahtarı son sıradadır ve kredi yoksa otomatik atlanır.')
    print('\nBaşlat: python main.py')

if __name__=='__main__': main()
