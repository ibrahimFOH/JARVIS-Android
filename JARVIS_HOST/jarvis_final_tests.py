from pathlib import Path
import subprocess,time,json

ROOT=Path(r"C:\Jarvis\J.A.R.V.I.S")
PY=ROOT/"venv"/"Scripts"/"python.exe"
results=[]

def test(name,ok,detail):
    results.append({"test":name,"ok":bool(ok),"detail":str(detail)})
    print(("[OK] " if ok else "[FAIL] ")+name+" | "+str(detail),flush=True)

try:
    r=subprocess.run([str(PY),"-c","import requests; print(requests.get('http://127.0.0.1:11434/api/tags',timeout=3).status_code)"],cwd=ROOT,capture_output=True,text=True,timeout=6)
    test("Ollama API",r.returncode==0 and "200" in r.stdout,r.stdout.strip() or r.stderr.strip())
except Exception as e: test("Ollama API",False,e)

try:
    t=time.perf_counter()
    r=subprocess.run([str(PY),"-c","from core.ai_brain import AIBrain; b=AIBrain(); print(b.ask('kimsin')); print(b.ask('ne yapabilirsin'))"],cwd=ROOT,capture_output=True,text=True,timeout=45)
    test("AI",r.returncode==0 and len(r.stdout.strip())>10,f"{time.perf_counter()-t:.2f}s | {r.stdout.strip()}")
except Exception as e: test("AI",False,e)

try:
    import requests
    t=time.perf_counter()
    r=requests.get("https://www.google.com",timeout=5,headers={"User-Agent":"Mozilla/5.0"})
    test("Web",r.ok,f"{r.status_code} | {time.perf_counter()-t:.2f}s")
except Exception as e: test("Web",False,e)

try:
    import speech_recognition as sr
    names=sr.Microphone.list_microphone_names()
    test("Mikrofon",len(names)>0,f"{len(names)} cihaz")
except Exception as e: test("Mikrofon",False,e)

try:
    import pyttsx3
    e=pyttsx3.init(); voices=e.getProperty("voices") or []; e.stop()
    test("TTS",len(voices)>0,f"{len(voices)} ses")
except Exception as e: test("TTS",False,e)

for rel in ["main.py","core/jarvis.py"]:
    try:
        r=subprocess.run([str(PY),"-m","py_compile",rel],cwd=ROOT,capture_output=True,text=True)
        test("Syntax "+rel,r.returncode==0,r.stderr.strip() or "OK")
    except Exception as e: test("Syntax "+rel,False,e)

out=ROOT/"JARVIS_FINAL_SYSTEM_REPORT.txt"
out.write_text(json.dumps({"time":time.strftime("%Y-%m-%d %H:%M:%S"),"tests":results},ensure_ascii=False,indent=2),encoding="utf-8")
print("RAPOR:",out)
