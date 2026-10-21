# JARVIS Türkçe TTS kurulumu

## Varsayılan ses: Emel (Türkçe kadın, çevrimiçi)

Windows host artık `edge-tts` üzerinden `tr-TR-EmelNeural` sesini tercih eder. API anahtarı istemez, ancak konuşma üretmek için internet gerekir. İnternet/servis hatasında JARVIS sessiz kalmak yerine yerel Windows SAPI sesine döner.

GUI'nin sol tarafındaki **TTS VOICE** menüsünden `Emel` seçin ve **TEST VOICE** düğmesiyle deneyin. `Ahmet` diğer çevrimiçi Türkçe neural sesidir.

## Çevrimdışı Türkçe Piper seçenekleri

Menüden `DFKI`, `Fahrettin` veya `Fettah` seçilirse JARVIS ilk kullanımda ilgili Sherpa-ONNX Piper modelini indirip kullanıcı profiline kaydeder:

`%LOCALAPPDATA%\Stagepulse\JARVIS\tts\`

Her model yaklaşık 60-70 MB seviyesindedir. Model bir kez indirildikten sonra konuşma üretimi çevrimdışı çalışır. İlk kurulum/ilk indirme için internet ve yeterli disk alanı gerekir. Bilgisayarın düşük özelliklerini gözetmek için Sherpa-ONNX bir iş parçacığıyla çalıştırılır.

Model arşivleri:
- [DFKI](https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-tr_TR-dfki-medium.tar.bz2)
- [Fahrettin](https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-tr_TR-fahrettin-medium.tar.bz2)
- [Fettah](https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-tr_TR-fettah-medium.tar.bz2)

## ZIP incelemesi

- `TTS-dev.zip`, Coqui TTS kaynak kodunu ve katalogda `tts_models/tr/common-voice/glow-tts` Türkçe model tanımını içeriyordu. Model ağırlıkları bu ZIP'te yoktu. Coqui tam çalışma yığını, bu 4 GB RAM'li Windows makine için daha ağır bir tercih olacağı için varsayılan motora alınmadı.
- `sherpa-onnx-master.zip`, Sherpa-ONNX kaynak kodunu ve DFKI/Fahrettin/Fettah model kullanımı örneklerini içeriyordu; ONNX ses ağırlıkları ZIP'in içinde değildi. Bu nedenle modeller, kullanıcı bu seslerden birini seçince resmî Sherpa-ONNX yayın adresinden otomatik indirilir.

## Bağımlılıkları kurma ve EXE oluşturma

Kaynak ortamda, `JARVIS_HOST` klasöründe:

```bat
python -m pip install -r requirements.txt
python main.py
```

Windows EXE iş akışı `edge_tts` ve `sherpa_onnx` paketlerini PyInstaller çıktısına dahil edecek şekilde güncellendi. Yeni kodun EXE'ye geçmesi için bu yeni dalın Windows build iş akışının başarılı tamamlanması gerekir.
