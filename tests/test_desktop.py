import contextlib, hashlib, shutil, json, os, sqlite3, subprocess, sys, tempfile, time, types, unittest, urllib.request, socket
from pathlib import Path
from unittest.mock import patch, Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import launcher, server, updater, build_release

class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'Forage with spaces';self.root.mkdir();self.data=self.root/'data'
    def tearDown(self):self.tmp.cleanup()
    def test_default_path_startup_command_avoids_unnecessary_arguments(self):
        args=launcher.desktop_args(self.root,self.data)
        self.assertEqual(args,[str(self.root/'launcher.py'),'--tray']);self.assertNotIn('--open',args)
    def test_bootstrap_keeps_tray_launcher_available_after_old_version_restore(self):
        for name in ['launcher.py','updater.py']:shutil.copy2(launcher.ROOT/name,self.root/name)
        bootstrap=launcher.install_tray_bootstrap(self.root,self.data)
        command=[sys.executable,str(bootstrap),'--help']
        self.assertEqual(subprocess.run(command,capture_output=True).returncode,0)
        (self.root/'launcher.py').write_text('raise RuntimeError("older launcher without tray")')
        result=subprocess.run(command,capture_output=True);self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(launcher.desktop_args(self.root,self.data)[0],str(bootstrap))
    def test_custom_data_port_are_preserved(self):
        custom=self.root/'custom data';args=launcher.desktop_args(self.root,custom,8766,True)
        self.assertIn(str(custom.resolve()),args);self.assertIn('8766',args);self.assertIn('--open',args)
    def test_background_process_has_no_console_and_keeps_data(self):
        fake_os=types.SimpleNamespace(name='nt',environ={})
        with patch.object(launcher,'os',fake_os),patch.object(launcher,'windowless_python',return_value=Path('/fake/pythonw.exe')),patch.object(launcher.subprocess,'Popen') as spawn:
            launcher.launch_background(self.root,self.data,8766,False,True)
        args=spawn.call_args.args[0];kwargs=spawn.call_args.kwargs
        self.assertEqual(args[0],'/fake/pythonw.exe');self.assertIn('--tray',args);self.assertIn('--wait-for-port',args);self.assertNotIn('--open',args)
        self.assertEqual(kwargs['env']['FORAGE_DATA_DIR'],str(self.data));self.assertEqual(kwargs['stdout'],subprocess.DEVNULL)
    def test_non_windows_does_not_write_startup(self):
        with patch.object(launcher,'os',types.SimpleNamespace(name='posix',environ={})),patch.object(launcher.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'Windows'):launcher.configure_desktop(self.root,self.data,8765,True)
            run.assert_not_called()
    def test_registry_startup_can_be_enabled_and_disabled(self):
        values={}
        def read(key,name):
            if name not in values:raise FileNotFoundError()
            return values[name],1
        def remove(key,name):
            if name not in values:raise FileNotFoundError()
            values.pop(name)
        reg=types.SimpleNamespace(HKEY_CURRENT_USER=1,REG_SZ=1,CreateKey=lambda *a:contextlib.nullcontext(1),OpenKey=lambda *a:contextlib.nullcontext(1),QueryValueEx=read,SetValueEx=lambda key,name,zero,typ,value:values.update({name:value}),DeleteValue=remove)
        env=types.SimpleNamespace(name='nt',environ={'APPDATA':str(self.root/'profile')})
        with patch.dict(sys.modules,{'winreg':reg}),patch.object(launcher,'os',env),patch.object(launcher,'windowless_python',return_value=Path('/fake/pythonw.exe')),patch.object(launcher,'powershell',return_value='powershell.exe'),patch.object(launcher.subprocess,'run',return_value=types.SimpleNamespace(returncode=0)) as run:
            result=launcher.configure_desktop(self.root,self.data,8765,True)
            self.assertTrue(result['startup_enabled']);self.assertNotIn('--open',values[launcher.RUN_NAME])
            payload=json.loads(run.call_args.kwargs['input']);self.assertIn('--open',payload['args']);self.assertTrue(payload['path'].endswith('Forage.lnk'))
            self.assertNotIn(str(self.root),run.call_args.args[0][-1]) # Paths are data, not interpolated script.
            self.assertFalse(launcher.configure_desktop(self.root,self.data,8765,False)['startup_enabled'])
    def test_stop_uses_csrf_and_graceful_quit(self):
        process=Mock();process.poll.return_value=None
        response=Mock();response.__enter__=lambda self:self;response.__exit__=lambda *a:None;response.read.return_value=b'{"token":"local-token"}'
        with patch.object(launcher.urllib.request,'urlopen',return_value=response) as call:launcher.stop_server(process,8765)
        request=call.call_args.args[0];self.assertEqual(request.get_header('X-forage-token'),'local-token');self.assertEqual(json.loads(request.data),{'action':'quit'});process.terminate.assert_not_called()
    def test_desktop_status_on_non_windows(self):
        with patch.object(launcher,'os',types.SimpleNamespace(name='posix',environ={})):self.assertFalse(launcher.desktop_status(self.root,self.data)['supported'])

@unittest.skipUnless(os.name=='posix','Local subprocess lifecycle test on CI; native tray needs Windows verification.')
class TrayLifecycleTests(unittest.TestCase):
    def test_tray_exit_stops_server_and_preserves_workspace(self):
        import signal
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'app';source=Path(tmp)/'source';root.mkdir();source.mkdir()
            for name in updater.PROGRAM_FILES:
                for target in [root,source]:
                    (target/name).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(launcher.ROOT/name,target/name)
            updater.write_json(root/'version.json',{'version':'0.2.11','update_format':1,'workspace_versions':[1]})
            updater.write_json(source/'version.json',{'version':'0.2.12','update_format':1,'workspace_versions':[1]})
            archive=Path(tmp)/'release.zip';build_release.build(source,archive);payload=archive.read_bytes()
            release={'tag_name':'v0.2.12','assets':[{'name':'Forage-update.zip','browser_download_url':'https://github.com/example/forage/releases/download/v0.2.12/Forage-update.zip','digest':'sha256:'+hashlib.sha256(payload).hexdigest()}]}
            data=Path(tmp)/'data';flag=Path(tmp)/'quit';log=Path(tmp)/'log'
            with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
            script="import launcher,types,pathlib; flag=pathlib.Path(__import__('sys').argv[1]); data=pathlib.Path(__import__('sys').argv[2]); port=int(__import__('sys').argv[3]); tray=types.SimpleNamespace(poll=lambda:0 if flag.exists() else None); log=open(__import__('sys').argv[4],'a'); launcher.updater.configure(data,'example/forage',False); launcher.supervise(types.SimpleNamespace(port=port,open=False),data,tray,log)"
            process=subprocess.Popen([sys.executable,'-c',script,str(flag),str(data),str(port),str(log)],cwd=root,start_new_session=True)
            try:
                deadline=time.monotonic()+10;before=None
                while time.monotonic()<deadline:
                    try:
                        with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/api/state',timeout=1) as response:initial=json.load(response);before=initial['state'];token=initial['token']
                        break
                    except OSError:time.sleep(.05)
                self.assertIsNotNone(before)
                with patch.object(updater,'fetch',side_effect=[json.dumps(release).encode(),payload]):updater.stage(root,data)
                request=urllib.request.Request('http://127.0.0.1:'+str(port)+'/api/updates',data=b'{"action":"restart"}',headers={'Content-Type':'application/json','X-Forage-Token':token})
                with urllib.request.urlopen(request,timeout=3) as response:self.assertTrue(json.load(response)['ok'])
                deadline=time.monotonic()+10;installed=False
                while time.monotonic()<deadline:
                    try:
                        with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/api/health',timeout=1) as response:installed=json.load(response)['version']=='0.2.12'
                        if installed:break
                    except OSError:pass
                    time.sleep(.1)
                self.assertTrue(installed)
                with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/api/desktop/status') as response:self.assertTrue(json.load(response)['tray_running'])
                flag.write_text('quit');process.wait(timeout=10);self.assertEqual(process.returncode,0)
                with sqlite3.connect(data/'forage.sqlite3') as con:after=json.loads(con.execute('SELECT payload FROM workspace WHERE id=1').fetchone()[0])
                self.assertEqual(after,before)
            finally:
                if process.poll() is None:os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=5)
