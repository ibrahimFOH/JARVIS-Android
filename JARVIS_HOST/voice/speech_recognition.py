"""Turkish-first speech recognition for JARVIS."""
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
