# -*- coding: utf-8 -*-
import os,sys,subprocess
from pathlib import Path
import requests
class ToolEngine:
 def __init__(self,repo=None): self.repo=Path(repo or Path.cwd()).resolve()
 def list_dir(self,path="."):
  p=Path(path).expanduser().resolve(); return {"ok":p.exists(),"path":str(p),"items":[x.name for x in p.iterdir()] if p.exists() else []}
 def read_text(self,path,max_chars=30000):
  p=Path(path).expanduser().resolve()
  if not p.is_file(): return {"ok":False,"error":"Dosya bulunamadı"}
  return {"ok":True,"path":str(p),"content":p.read_text(encoding="utf-8",errors="replace")[:max_chars]}
 def write_text(self,path,content):
  p=Path(path).expanduser().resolve(); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content,encoding="utf-8"); return {"ok":True,"path":str(p)}
 def git(self,*args):
  r=subprocess.run(["git",*args],cwd=self.repo,text=True,capture_output=True,timeout=60); return {"ok":r.returncode==0,"stdout":r.stdout[-30000:],"stderr":r.stderr[-10000:]}
 def run_safe(self,command,timeout=120):
  blocked=["format ","diskpart","reg delete","shutdown","del /s","rmdir /s","cipher /w"]
  if any(x in command.lower() for x in blocked): return {"ok":False,"error":"Komut güvenlik nedeniyle engellendi."}
  r=subprocess.run(command,cwd=self.repo,shell=True,text=True,capture_output=True,timeout=timeout); return {"ok":r.returncode==0,"code":r.returncode,"stdout":r.stdout[-30000:],"stderr":r.stderr[-15000:]}
 def fetch_text(self,url):
  if not url.lower().startswith(("http://","https://")): return {"ok":False,"error":"Sadece HTTP/HTTPS kullanılabilir."}
  r=requests.get(url,timeout=20,headers={"User-Agent":"JARVIS/1.0"}); return {"ok":r.ok,"status":r.status_code,"content":r.text[:50000]}
 def audio_separate(self,input_file):
  p=Path(input_file).expanduser().resolve()
  if not p.exists(): return {"ok":False,"error":"Dosya bulunamadı"}
  r=subprocess.run([sys.executable,"-m","demucs",str(p)],cwd=self.repo,text=True,capture_output=True,timeout=3600); return {"ok":r.returncode==0,"stdout":r.stdout[-20000:],"stderr":r.stderr[-20000:]}
