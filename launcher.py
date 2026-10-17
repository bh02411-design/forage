#!/usr/bin/env python3
"""Supervise Forage so application files change only while its server is stopped."""
import argparse, json, os, shutil, socket, subprocess, sys, time, urllib.request, urllib.error, webbrowser, traceback
from pathlib import Path
import updater

ROOT=Path(__file__).resolve().parent

RUN_KEY=r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_NAME='ForageLocalDeckBuilder'

def windowless_python():
    executable=Path(sys.executable).with_name('pythonw.exe')
    if not executable.is_file():raise ValueError('Python windowless launcher was not found. Install Python for Windows with pythonw.exe.')
    return executable

def install_tray_bootstrap(root,data):
    folder=Path(data)/'desktop';folder.mkdir(parents=True,exist_ok=True)
    fallback=folder/'tray_launcher.py'
    if Path(__file__).resolve()!=fallback.resolve():shutil.copy2(__file__,fallback)
    bootstrap=folder/'Forage.py'
    text="""import importlib.util, pathlib, shutil, sys
root=pathlib.Path(ROOT_VALUE)
sys.path.insert(0,str(root))
source=root/'launcher.py'
fallback=pathlib.Path(__file__).with_name('tray_launcher.py')
if 'def start_tray(' in source.read_text(encoding='utf-8'):
    shutil.copy2(source,fallback)
else:source=fallback
spec=importlib.util.spec_from_file_location('forage_desktop_launcher',source)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.ROOT=root
module.main()
""".replace('ROOT_VALUE',repr(str(Path(root).resolve())))
    bootstrap.write_text(text,encoding='utf-8')
    return bootstrap

def desktop_args(root,data,port=8765,open_browser=False):
    bootstrap=Path(data)/'desktop'/'Forage.py'
    args=[str(bootstrap if bootstrap.is_file() else Path(root)/'launcher.py'),'--tray']
    if Path(data).resolve()!=(Path(root)/'data').resolve():args+=['--data-dir',str(Path(data).resolve())]
    if port!=8765:args+=['--port',str(port)]
    if open_browser:args.append('--open')
    return args

def startup_command(root,data,port=8765):
    return subprocess.list2cmdline([str(windowless_python())]+desktop_args(root,data,port))

def desktop_status(root,data,port=8765):
    info={'supported':os.name=='nt','tray_running':os.environ.get('FORAGE_TRAY')=='1','startup_enabled':False}
    if os.name!='nt':return info
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,RUN_KEY) as key:value=winreg.QueryValueEx(key,RUN_NAME)[0]
        info['startup_enabled']=value==startup_command(root,data,port)
    except FileNotFoundError:pass
    except ValueError as exc:info['message']=str(exc)
    return info

def powershell():
    path=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32'/'WindowsPowerShell'/'v1.0'/'powershell.exe'
    if not path.is_file():raise ValueError('Windows PowerShell is required for the tray icon and Start-menu shortcut.')
    return str(path)

def configure_desktop(root,data,port,startup):
    if os.name!='nt':raise ValueError('System tray integration is available on Windows.')
    if type(startup) is not bool:raise ValueError('Start with Windows must be true or false.')
    import winreg
    install_tray_bootstrap(root,data)
    command=startup_command(root,data,port)
    if startup and len(command)>260:raise ValueError('The startup command exceeds the Windows limit. Move Forage to a shorter folder path and retry.')
    appdata=os.environ.get('APPDATA')
    if not appdata:raise ValueError('Windows Start-menu folder is unavailable.')
    shortcut=Path(appdata)/'Microsoft'/'Windows'/'Start Menu'/'Programs'/'Forage.lnk'
    shortcut.parent.mkdir(parents=True,exist_ok=True)
    script='$ErrorActionPreference="Stop"; $c=[Console]::In.ReadToEnd()|ConvertFrom-Json; $w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut($c.path); $s.TargetPath=$c.exe; $s.Arguments=$c.args; $s.WorkingDirectory=$c.root; $s.Description="Forage local deck builder"; $s.Save()'
    payload={'path':str(shortcut),'exe':str(windowless_python()),'args':subprocess.list2cmdline(desktop_args(root,data,port,True)),'root':str(root)}
    result=subprocess.run([powershell(),'-NoProfile','-NonInteractive','-Command',script],input=json.dumps(payload),text=True,capture_output=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise ValueError('Could not create the Start-menu shortcut: '+result.stderr[-500:])
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,RUN_KEY) as key:
        if startup:winreg.SetValueEx(key,RUN_NAME,0,winreg.REG_SZ,command)
        else:
            try:winreg.DeleteValue(key,RUN_NAME)
            except FileNotFoundError:pass
    return desktop_status(root,data,port)

# PowerShell receives a JSON configuration on stdin, never interpolated executable code.
TRAY_SCRIPT=r'''$ErrorActionPreference='Stop'
$c=[Console]::In.ReadToEnd()|ConvertFrom-Json
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$ctx=New-Object System.Windows.Forms.ApplicationContext
$icon=New-Object System.Windows.Forms.NotifyIcon
$icon.Icon=[System.Drawing.SystemIcons]::Application
$icon.Text='Forage - local deck builder'
$menu=New-Object System.Windows.Forms.ContextMenuStrip
$open=$menu.Items.Add('Open Forage')
$open.add_Click({ Start-Process $c.url })
$startup=$menu.Items.Add('Start with Windows')
$reg='HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$name='ForageLocalDeckBuilder'
$value=Get-ItemPropertyValue -Path $reg -Name $name -ErrorAction SilentlyContinue
$startup.Checked=($value -eq $c.startup)
$startup.add_Click({
 try {
  if ($startup.Checked) { Remove-ItemProperty -Path $reg -Name $name -ErrorAction SilentlyContinue; $startup.Checked=$false }
  else {
   if ($c.startup.Length -gt 260) { throw 'The startup command is too long. Move Forage to a shorter folder path.' }
   if (-not (Test-Path $reg)) { New-Item -Path $reg | Out-Null }
   New-ItemProperty -Path $reg -Name $name -Value $c.startup -PropertyType String -Force | Out-Null
   $startup.Checked=$true
  }
 } catch { [System.Windows.Forms.MessageBox]::Show($_.Exception.Message,'Forage') | Out-Null }
})
$menu.Items.Add('-') | Out-Null
$quit=$menu.Items.Add('Quit Forage')
$quit.add_Click({$ctx.ExitThread()})
$icon.ContextMenuStrip=$menu
$icon.add_DoubleClick({Start-Process $c.url})
$icon.Visible=$true
try { [System.Windows.Forms.Application]::Run($ctx) }
finally { $icon.Visible=$false; $icon.Dispose(); $menu.Dispose(); $ctx.Dispose() }
'''

def start_tray(root,data,port,log):
    process=subprocess.Popen([powershell(),'-NoProfile','-NonInteractive','-STA','-WindowStyle','Hidden','-Command',TRAY_SCRIPT],stdin=subprocess.PIPE,stdout=log,stderr=log,text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    process.stdin.write(json.dumps({'url':'http://127.0.0.1:'+str(port),'startup':startup_command(root,data,port)}));process.stdin.close()
    return process

def launch_background(root,data,port=8765,open_browser=True,wait=False):
    if os.name!='nt':raise ValueError('Background tray mode is available on Windows.')
    install_tray_bootstrap(root,data)
    args=[str(windowless_python())]+desktop_args(root,data,port,open_browser)
    if wait:args.append('--wait-for-port')
    return subprocess.Popen(args,cwd=root,env=dict(os.environ,FORAGE_DATA_DIR=str(data)),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

def stop_server(process,port):
    if process.poll() is not None:return
    base='http://127.0.0.1:'+str(port)
    try:
        with urllib.request.urlopen(base+'/api/state',timeout=3) as response:token=json.load(response)['token']
        request=urllib.request.Request(base+'/api/desktop',data=b'{"action":"quit"}',headers={'Content-Type':'application/json','X-Forage-Token':token})
        with urllib.request.urlopen(request,timeout=3):pass
    except urllib.error.HTTPError as exc:
        if exc.code==400:return  # An active edit/request will be allowed to finish.
        process.terminate()  # Earlier releases do not have a shutdown endpoint.
    except (OSError,ValueError):return  # Startup/restart or a temporarily busy server; retry.

def healthy(process,port,expected,timeout=20):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if process.poll() is not None:return False
        try:
            with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/api/health',timeout=.6) as r:
                if json.load(r).get('version')==expected:return True
        except Exception:pass
        time.sleep(.25)
    return False

def supervise(args,data,tray=None,log=None):
    updater.recover(ROOT,data)
    first=True;verify_start=False
    while True:
        if tray and tray.poll() is not None:return
        cmd=[sys.executable,str(ROOT/'server.py'),'--port',str(args.port)]
        if args.open and first:cmd.append('--open')
        env=dict(os.environ,FORAGE_LAUNCHER='1',FORAGE_VERSION_SWITCH='1',FORAGE_DATA_DIR=str(data),FORAGE_TRAY='1' if tray else '0')
        options={'stdin':subprocess.DEVNULL,'stdout':log,'stderr':log,'creationflags':getattr(subprocess,'CREATE_NO_WINDOW',0)} if tray else {}
        process=subprocess.Popen(cmd,cwd=ROOT,env=env,**options);first=False
        try:
            if verify_start and not healthy(process,args.port,updater.current_version(ROOT)):
                if process.poll() is None:process.terminate();process.wait(timeout=10)
                updater.rollback(ROOT,data);print('Update failed its startup check. Previous application restored.',flush=True)
                verify_start=False;continue
            verify_start=False
            if tray:
                while process.poll() is None:
                    if tray.poll() is not None:stop_server(process,args.port)
                    time.sleep(.25)
            code=process.wait()
        except KeyboardInterrupt:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()
            return
        if code not in [75,76]:return code
        try:
            if code==75:updater.install_pending(ROOT,data);verify_start=True
            else:updater.rollback(ROOT,data)
        except Exception as exc:
            print('Update was not applied: '+str(exc),flush=True)
            try:updater.recover(ROOT,data)
            except Exception as recovery:
                print('Recovery needs attention: '+str(recovery)+'. Application was not restarted.',flush=True);return
            print('Restarting the existing application.',flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);parser.add_argument('--open',action='store_true');parser.add_argument('--tray',action='store_true');parser.add_argument('--background',action='store_true');parser.add_argument('--wait-for-port',action='store_true');parser.add_argument('--data-dir');args=parser.parse_args()
    data=Path(args.data_dir or os.environ.get('FORAGE_DATA_DIR',str(ROOT/'data'))).resolve()
    if args.background:
        launch_background(ROOT,data,args.port,args.open);return
    if not args.tray:return supervise(args,data)
    if os.name!='nt':raise ValueError('Tray mode requires Windows.')
    import msvcrt
    data.mkdir(parents=True,exist_ok=True)
    lock=(data/('tray-'+str(args.port)+'.lock')).open('a+b');lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
    try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:
        lock.close()
        if args.open:webbrowser.open('http://127.0.0.1:'+str(args.port))
        return
    logpath=data/'forage.log'
    if logpath.exists() and logpath.stat().st_size>2*1024*1024:os.replace(logpath,data/'forage.previous.log')
    previous_streams=(sys.stdout,sys.stderr)
    with logpath.open('a',encoding='utf-8',buffering=1) as log:
        sys.stdout=sys.stderr=log
        tray=None
        try:
            deadline=time.monotonic()+(30 if args.wait_for_port else 0)
            while True:
                with socket.socket() as probe:
                    probe.settimeout(.3)
                    if probe.connect_ex(('127.0.0.1',args.port))!=0:break
                if time.monotonic()>=deadline:raise ValueError('The Forage port is already in use. Close the other launcher once, then start Forage again.')
                time.sleep(.2)
            tray=start_tray(ROOT,data,args.port,log)
            code=supervise(args,data,tray,log)
            if code not in [None,0,77]:raise ValueError('The Forage server exited unexpectedly. See forage.log for details.')
            if tray.poll() is not None and tray.returncode:raise ValueError('The tray process could not start. See forage.log for details.')
        except Exception:
            traceback.print_exc()
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,'Forage could not start. See '+str(logpath)+' for details.','Forage',16)
        finally:
            if tray and tray.poll() is None:tray.terminate();tray.wait(timeout=5)
            lock.close()
            sys.stdout,sys.stderr=previous_streams

if __name__=='__main__':main()
