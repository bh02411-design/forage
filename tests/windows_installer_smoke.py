"""Run on Windows CI: install, launch with bundled Python, reinstall, uninstall."""
import json, os, pathlib, subprocess, sys, tempfile, time, urllib.request

def main():
    assert os.name=='nt'
    setup=pathlib.Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix='Forage setup ') as folder:
        root=pathlib.Path(folder);app=root/'Installed app';data=root/'Personal data'
        data.mkdir();marker=data/'keep-me.txt';marker.write_text('Personal data must survive')
        (data/'update-config.json').write_text(json.dumps({'repository':'','check_on_start':False}))
        command=[str(setup),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',f'/DIR={app}']
        subprocess.run(command,check=True,timeout=120)
        python=app/'runtime'/'python.exe'
        assert python.is_file() and (app/'runtime'/'pythonw.exe').is_file()
        assert not (app/'data').exists()
        checks="import ssl,sqlite3,ctypes,server,updater,seed;assert not seed.initial_state()['collection'];assert updater.config('nonexistent')['repository']=='bh02411-design/forage';print('Bundled imports and clean starter verified')"
        subprocess.run([str(python),'-c',checks],cwd=root,check=True,timeout=30)
        process=subprocess.Popen([str(app/'runtime'/'pythonw.exe'),str(app/'launcher.py'),'--tray','--data-dir',str(data),'--port','18765'],cwd=root)
        base='http://127.0.0.1:18765'
        try:
            deadline=time.monotonic()+45
            while True:
                try:
                    with urllib.request.urlopen(base+'/api/state',timeout=2) as response:state=json.load(response)
                    break
                except OSError:
                    if process.poll() is not None or time.monotonic()>deadline:
                        raise RuntimeError((data/'forage.log').read_text() if (data/'forage.log').exists() else 'Tray failed to start')
                    time.sleep(.5)
            assert not state['state']['collection'] and not state['state']['decks'][0]['cards']
            with urllib.request.urlopen(base+'/api/desktop',timeout=3) as response:desktop=json.load(response)
            assert desktop['supported'] and desktop['tray_running']
            request=urllib.request.Request(base+'/api/desktop',data=b'{"action":"quit"}',headers={'Content-Type':'application/json','X-Forage-Token':state['token']})
            with urllib.request.urlopen(request,timeout=3):pass
            process.wait(timeout=20)
        finally:
            if process.poll() is None:subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True)
        subprocess.run(command,check=True,timeout=120)
        assert marker.read_text()=='Personal data must survive'
        subprocess.run([str(app/'unins000.exe'),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'],check=True,timeout=60)
        assert marker.read_text()=='Personal data must survive'
        print('Windows installer, bundled tray launch, clean workspace, reinstall and uninstall smoke checks passed.')

if __name__=='__main__':main()
