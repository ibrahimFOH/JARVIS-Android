"""Turkish response/personality layer."""
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
