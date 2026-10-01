"""Turkish-first Windows TTS for JARVIS."""
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
