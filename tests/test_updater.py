import hashlib, io, json, os, shutil, sqlite3, sys, tempfile, unittest, zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import build_release, updater, server

class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.root=self.base/'app';self.source=self.base/'source';self.data=self.root/'data'
        self.root.mkdir();self.data.mkdir();self.source.mkdir()
        origin=Path(server.__file__).parent
        for name in updater.PROGRAM_FILES:
            for dest in [self.root,self.source]:
                (dest/name).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(origin/name,dest/name)
        updater.write_json(self.root/'version.json',{'version':'0.2.0','update_format':1})
        updater.write_json(self.source/'version.json',{'version':'0.2.1','update_format':1})
        (self.source/'README.md').write_text('Updated application')
        self.archive=self.base/'update.zip';build_release.build(self.source,self.archive)
        self.payload=self.archive.read_bytes();self.digest=hashlib.sha256(self.payload).hexdigest()
        self.release={'tag_name':'v0.2.1','body':'Fixes','assets':[{'name':'Forage-update.zip','browser_download_url':'https://github.com/example/forage/releases/download/v0.2.1/Forage-update.zip','digest':'sha256:'+self.digest}]}
        updater.configure(self.data,'example/forage')
    def tearDown(self):self.tmp.cleanup()
    def staged(self):
        with patch.object(updater,'fetch',side_effect=[json.dumps(self.release).encode(),self.payload]):updater.stage(self.root,self.data)
    def test_version_comparison(self):
        self.assertGreater(updater.version('0.10.0'),updater.version('0.9.9'))
        for x in ['v0.2.1-beta','../../bad','1.0','']:
            with self.assertRaises(ValueError):updater.version(x)
    def test_config_rejects_credentials_and_paths(self):
        for x in ['https://evil.test/x/y','x/y/../../z','token@github.com/x/y','x/..']:
            with self.assertRaises(ValueError):updater.repository(x)
    def test_no_repository_makes_no_request(self):
        updater.configure(self.data,'')
        with patch.object(updater,'fetch') as fetch:self.assertEqual(updater.check(self.root,self.data)['status'],'not_configured');fetch.assert_not_called()
    def test_release_is_available(self):
        with patch.object(updater,'fetch',return_value=json.dumps(self.release).encode()):
            self.assertEqual(updater.check(self.root,self.data)['status'],'available')
    def test_release_source_cannot_change_host(self):
        self.release['assets'][0]['browser_download_url']='https://evil.test/Forage-update.zip'
        with patch.object(updater,'fetch',return_value=json.dumps(self.release).encode()):
            self.assertEqual(updater.check(self.root,self.data)['status'],'error')
    def test_missing_digest_refuses_release(self):
        self.release['assets'][0].pop('digest')
        with patch.object(updater,'fetch',return_value=json.dumps(self.release).encode()):self.assertEqual(updater.check(self.root,self.data)['status'],'error')
    def test_network_error_is_visible(self):
        with patch.object(updater,'fetch',side_effect=OSError('offline')):self.assertIn('offline',updater.check(self.root,self.data)['message'])
    def test_staged_hash_mismatch(self):
        with patch.object(updater,'fetch',side_effect=[json.dumps(self.release).encode(),b'corrupt']):
            with self.assertRaisesRegex(ValueError,'SHA-256'):updater.stage(self.root,self.data)
        self.assertIsNone(updater.read_json(self.data/'updates'/'pending.json'))
    def test_rejects_arbitrary_zip_path(self):
        malicious=self.base/'bad.zip'
        with zipfile.ZipFile(self.archive) as z,zipfile.ZipFile(malicious,'w') as bad:
            for name in z.namelist():bad.writestr(name,z.read(name))
            bad.writestr('../data/forage.sqlite3','bad')
        with self.assertRaisesRegex(ValueError,'unapproved'):updater.verify_package(malicious,'0.2.1')
    def test_rejects_data_files(self):
        malicious=self.base/'bad.zip'
        with zipfile.ZipFile(self.archive) as z,zipfile.ZipFile(malicious,'w') as bad:
            for name in z.namelist():bad.writestr(name,z.read(name))
            bad.writestr('data/forage.sqlite3','bad')
        with self.assertRaises(ValueError):updater.verify_package(malicious,'0.2.1')
    def test_staged_tampering_detected(self):
        self.staged();(self.data/'updates'/'pending.zip').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'changed'):updater.install_pending(self.root,self.data)
        self.assertEqual(updater.current_version(self.root),'0.2.0')
    def test_install_and_rollback_preserve_live_workspace(self):
        with sqlite3.connect(self.data/'forage.sqlite3') as c:c.execute('create table test(value)');c.execute('insert into test values (42)')
        original=(self.root/'README.md').read_bytes();self.staged();updater.install_pending(self.root,self.data)
        self.assertEqual(updater.current_version(self.root),'0.2.1');self.assertTrue(updater.status(self.root,self.data)['rollback_available'])
        with sqlite3.connect(self.data/'forage.sqlite3') as c:c.execute('update test set value=99')
        updater.rollback(self.root,self.data)
        self.assertEqual(updater.current_version(self.root),'0.2.0');self.assertEqual((self.root/'README.md').read_bytes(),original)
        with sqlite3.connect(self.data/'forage.sqlite3') as c:self.assertEqual(c.execute('select value from test').fetchone()[0],99)
        self.assertEqual(len(list((self.data/'updates'/'backups').glob('*/workspace.sqlite3'))),1)
    def test_failed_install_restores_previous_files(self):
        self.staged();original=updater.replace_bytes;count=0
        def fail_once(path,payload):
            nonlocal count
            count+=1
            if count==3:raise OSError('write failed')
            return original(path,payload)
        with patch.object(updater,'replace_bytes',side_effect=fail_once):
            with self.assertRaisesRegex(OSError,'write failed'):updater.install_pending(self.root,self.data)
        self.assertEqual(updater.current_version(self.root),'0.2.0');self.assertEqual(updater.read_json(self.data/'updates'/'transaction.json')['status'],'rolled_back')
    def test_interrupted_install_recovers(self):
        self.staged();updater.install_pending(self.root,self.data)
        tx=updater.read_json(self.data/'updates'/'transaction.json');tx['status']='installing';updater.write_json(self.data/'updates'/'transaction.json',tx)
        updater.recover(self.root,self.data);self.assertEqual(updater.current_version(self.root),'0.2.0')
    def test_archive_never_contains_user_data(self):
        with zipfile.ZipFile(self.archive) as z:self.assertEqual(set(z.namelist()),updater.PROGRAM_FILES|{'release.json'})
    def test_mismatched_release_version_rejected(self):
        with self.assertRaises(ValueError):updater.verify_package(self.archive,'0.3.0')
    def test_symlink_target_not_overwritten(self):
        if os.name=='nt':self.skipTest('Symlink privileges vary on Windows')
        target=self.base/'outside';target.write_text('unchanged');(self.root/'README.md').unlink();(self.root/'README.md').symlink_to(target)
        self.staged()
        with self.assertRaisesRegex(ValueError,'symlink'):updater.install_pending(self.root,self.data)
        self.assertEqual(target.read_text(),'unchanged')

class VersionHistoryTests(unittest.TestCase):
    setUp=UpdateTests.setUp
    tearDown=UpdateTests.tearDown
    staged=UpdateTests.staged
    def write_workspace(self,number=1):
        with sqlite3.connect(self.data/'forage.sqlite3') as con:
            con.execute('CREATE TABLE IF NOT EXISTS workspace(id INTEGER PRIMARY KEY,payload TEXT)')
            con.execute('INSERT OR REPLACE INTO workspace VALUES(1,?)',(json.dumps({'version':number,'decks':[{'name':'Keep this deck'}]}),))
    def make_older_release(self):
        updater.write_json(self.root/'version.json',{'version':'0.2.2','update_format':1})
        self.write_workspace()
    def test_selected_downgrade_and_forward_preserve_data(self):
        self.make_older_release();before=(self.data/'forage.sqlite3').read_bytes()
        with patch.object(updater,'fetch',side_effect=[json.dumps(self.release).encode(),self.payload]):
            updater.stage(self.root,self.data,'0.2.1')
        updater.install_pending(self.root,self.data)
        self.assertEqual(updater.current_version(self.root),'0.2.1')
        with sqlite3.connect(self.data/'forage.sqlite3') as con:self.assertEqual(json.loads(con.execute('SELECT payload FROM workspace').fetchone()[0])['decks'][0]['name'],'Keep this deck')
        self.assertEqual((self.data/'forage.sqlite3').read_bytes(),before)
        self.assertEqual(len(list((self.data/'updates'/'backups').glob('*/workspace.sqlite3'))),1)
        updater.rollback(self.root,self.data);self.assertEqual(updater.current_version(self.root),'0.2.2')
        self.assertEqual(len(list((self.data/'updates'/'rollback-snapshots').glob('*/workspace.sqlite3'))),1)
    def test_undeclared_future_format_is_blocked(self):
        with self.assertRaisesRegex(ValueError,'declare'):updater.check_compatibility({'version':'0.3.0'},self.data)
    def test_declared_future_compatible_format_is_allowed(self):
        updater.check_compatibility({'version':'0.3.0','workspace_versions':[1]},self.data)
    def test_boolean_schema_is_not_an_integer_schema(self):
        with self.assertRaises(ValueError):updater.check_compatibility({'version':'0.3.0','workspace_versions':[True]},self.data)
    def test_incompatible_target_is_blocked_before_staging(self):
        self.make_older_release();self.write_workspace(2)
        with patch.object(updater,'fetch',side_effect=[json.dumps(self.release).encode(),self.payload]):
            with self.assertRaisesRegex(ValueError,'incompatible'):updater.stage(self.root,self.data,'0.2.1')
        self.assertIsNone(updater.read_json(self.data/'updates'/'pending.json'));self.assertEqual(updater.current_version(self.root),'0.2.2')
    def test_compatibility_rechecked_at_install(self):
        self.staged();self.write_workspace(2)
        with self.assertRaisesRegex(ValueError,'incompatible'):updater.install_pending(self.root,self.data)
        self.assertEqual(updater.current_version(self.root),'0.2.0')
    def test_rollback_rechecks_current_workspace_format(self):
        self.staged();updater.install_pending(self.root,self.data);self.write_workspace(2)
        with self.assertRaisesRegex(ValueError,'incompatible'):updater.preflight_rollback(self.data)
        with self.assertRaisesRegex(ValueError,'incompatible'):updater.rollback(self.root,self.data)
        self.assertEqual(updater.current_version(self.root),'0.2.1')
    def test_stale_selection_is_blocked(self):
        self.make_older_release()
        with patch.object(updater,'fetch',side_effect=[json.dumps(self.release).encode(),self.payload]):updater.stage(self.root,self.data,'0.2.1')
        updater.write_json(self.root/'version.json',{'version':'0.2.3','update_format':1})
        with self.assertRaisesRegex(ValueError,'changed after staging'):updater.install_pending(self.root,self.data)
    def test_history_sorts_and_marks_current_version(self):
        with patch.object(updater,'fetch',return_value=json.dumps([self.release]).encode()):history=updater.release_history(self.root,self.data)
        self.assertEqual([row['version'] for row in history['releases']],['0.2.1','0.2.0'])
        self.assertTrue(history['releases'][0]['available']);self.assertTrue(history['releases'][1]['installed'])
    def test_history_caches_for_offline_reading(self):
        with patch.object(updater,'fetch',return_value=json.dumps([self.release]).encode()):updater.release_history(self.root,self.data)
        with patch.object(updater,'fetch',side_effect=OSError('offline')):history=updater.release_history(self.root,self.data)
        self.assertIn('offline',history['offline_error']);self.assertEqual(history['releases'][0]['version'],'0.2.1')
    def test_history_does_not_reuse_different_repository_cache(self):
        with patch.object(updater,'fetch',return_value=json.dumps([self.release]).encode()):updater.release_history(self.root,self.data)
        updater.configure(self.data,'other/repo')
        with patch.object(updater,'fetch',side_effect=OSError('offline')):history=updater.release_history(self.root,self.data)
        self.assertEqual(len(history['releases']),1)
    def test_bundled_notes_readable_when_offline(self):
        updater.configure(self.data,updater.DEFAULT_REPOSITORY)
        with patch.object(updater,'fetch',side_effect=OSError('offline')):history=updater.release_history(self.root,self.data)
        release=next(row for row in history['releases'] if row['version']=='0.2.8')
        self.assertIn('On the table',release['changes'][1]);self.assertFalse(release['available'])
    def test_history_excludes_prerelease_and_bad_asset(self):
        invalid=dict(self.release,prerelease=True)
        with patch.object(updater,'fetch',return_value=json.dumps([invalid]).encode()):history=updater.release_history(self.root,self.data)
        self.assertEqual(len(history['releases']),1)

@unittest.skipUnless(os.name=='posix','Supervisor process-group tests run on POSIX CI; Windows launcher needs local verification.')
class SupervisorTests(unittest.TestCase):
    setUp=UpdateTests.setUp
    tearDown=UpdateTests.tearDown
    staged=UpdateTests.staged
    def lifecycle(self,broken=False,switch_back=False):
        import signal, socket, subprocess, time, urllib.request
        updater.configure(self.data,'example/forage',False)
        if broken:
            (self.source/'server.py').write_text("raise RuntimeError('deliberate startup failure')\n")
            build_release.build(self.source,self.archive);self.payload=self.archive.read_bytes();self.digest=hashlib.sha256(self.payload).hexdigest();self.release['assets'][0]['digest']='sha256:'+self.digest
        if switch_back:
            older_archive=self.base/'older.zip';build_release.build(self.root,older_archive);older_payload=older_archive.read_bytes()
        self.staged()
        with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
        base='http://127.0.0.1:'+str(port)
        def call(path,payload=None,token=''):
            req=urllib.request.Request(base+'/api/'+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json','X-Forage-Token':token})
            with urllib.request.urlopen(req,timeout=1) as r:return json.load(r)
        def wait_health(expected,previous=None):
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                try:
                    health=call('health')
                    if health['version']==expected and health['instance']!=previous:return health
                except Exception:pass
                time.sleep(.05)
            self.fail('Server did not reach expected version '+expected)
        with (self.base/'supervisor.log').open('w') as log:
            process=subprocess.Popen([sys.executable,str(self.root/'launcher.py'),'--port',str(port)],stdout=log,stderr=log,start_new_session=True)
            try:
                before=wait_health('0.2.0');state=call('state');token=state['token']
                # Ensure CSRF still guards update configuration.
                import urllib.error
                with self.assertRaises(urllib.error.HTTPError):call('updates',{'action':'configure','repository':'evil/repo'})
                self.assertTrue(call('updates/status')['supervised'])
                call('updates',{'action':'restart'},token)
                installed=wait_health('0.2.0' if broken else '0.2.1',before['instance'])
                self.assertEqual(call('state')['state']['decks'],state['state']['decks'])
                if switch_back:
                    self.assertTrue(call('updates/status')['version_switch_supported'])
                    older_release={'tag_name':'v0.2.0','assets':[{'name':'Forage-update.zip','browser_download_url':'https://github.com/example/forage/releases/download/v0.2.0/Forage-update.zip','digest':'sha256:'+hashlib.sha256(older_payload).hexdigest()}]}
                    with patch.object(updater,'fetch',side_effect=[json.dumps(older_release).encode(),older_payload]):updater.stage(self.root,self.data,'0.2.0')
                    token=call('state')['token'];call('updates',{'action':'restart'},token)
                    previous=wait_health('0.2.0',installed['instance'])
                    self.staged();token=call('state')['token'];call('updates',{'action':'restart'},token)
                    installed=wait_health('0.2.1',previous['instance'])
                    self.assertEqual(call('state')['state']['decks'],state['state']['decks'])
                if not broken:
                    token=call('state')['token'];call('updates',{'action':'rollback'},token)
                    wait_health('0.2.0',installed['instance'])
            finally:
                if process.poll() is None:
                    os.killpg(process.pid,signal.SIGINT)
                    try:process.wait(timeout=10)
                    except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
    def test_switch_backward_and_forward(self):self.lifecycle(switch_back=True)
    def test_full_update_restart_and_rollback(self):self.lifecycle()
    def test_failed_updated_server_restores_previous(self):self.lifecycle(broken=True)

