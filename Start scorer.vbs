' TheJobStash scorer. Double-click to start it, hidden - the same three pieces as
' scorer.cmd, with no windows:
'   py_server.py (localhost:3300), cloudflared tunnel (scorer.thejobstash.com), n8n
' Output goes to D:\AIO Freelance\TheJobStash\logs\scorer.log, tunnel.log, n8n.log.
' To stop them: Task Manager -> end python.exe, cloudflared.exe, node.exe (n8n).
Set sh = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
root = "D:\AIO Freelance\TheJobStash"
logs = root & "\logs"
If Not fs.FolderExists(logs) Then fs.CreateFolder logs

' py_server reads its token and the n8n URL from the environment, exactly as
' scorer.cmd sets them. Child processes inherit this process's environment.
Set env = sh.Environment("Process")
Set f = fs.OpenTextFile(root & "\.env.cloudflare")
Do Until f.AtEndOfStream
  line = f.ReadLine
  i = InStr(line, "=")
  If i > 1 And Len(line) > i And Left(line, 1) <> "#" Then env(Left(line, i - 1)) = Mid(line, i + 1)
Loop
f.Close
env("PYTHONUNBUFFERED") = "1"

q = Chr(34)
cloudflared = sh.ExpandEnvironmentStrings("%APPDATA%") & "\npm\node_modules\cloudflared\bin\cloudflared.exe"
sh.CurrentDirectory = root
' Safe to click twice: each piece
' starts only if it is not already running.
Set wmi = GetObject("winmgmts:")
Function Running(exe, pat)
  Running = wmi.ExecQuery("SELECT ProcessId FROM Win32_Process WHERE Name='" & exe & "' AND CommandLine LIKE '%" & pat & "%'").Count > 0
End Function
If Not Running("python.exe", "py_server.py") Then sh.Run "cmd /c python py_server.py >> " & q & logs & "\scorer.log" & q & " 2>&1", 0, False
If Not Running("cloudflared.exe", "tunnel run jobstash-scorer") Then sh.Run "cmd /c " & q & q & cloudflared & q & " tunnel run jobstash-scorer >> " & q & logs & "\tunnel.log" & q & " 2>&1" & q, 0, False
If Not Running("node.exe", "n8n%start") Then sh.Run "cmd /c " & q & q & "D:\AIO Freelance\n8n\start_n8n.cmd" & q & " >> " & q & logs & "\n8n.log" & q & " 2>&1" & q, 0, False
