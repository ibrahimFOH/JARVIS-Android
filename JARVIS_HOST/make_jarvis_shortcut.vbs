Set oWS = WScript.CreateObject("WScript.Shell")
Set lnk = oWS.CreateShortcut(oWS.SpecialFolders("Desktop") & "\JARVIS.lnk")
lnk.TargetPath = "C:\Jarvis\J.A.R.V.I.S\start_jarvis.bat"
lnk.WorkingDirectory = "C:\Jarvis\J.A.R.V.I.S"
lnk.Description = "JARVIS - Gemini + Ollama"
lnk.Save
