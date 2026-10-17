"""Opt-in GitHub release updates. Never install data or arbitrary ZIP paths."""
import datetime, hashlib, json, os, re, shutil, sqlite3, stat, threading, urllib.parse, urllib.request, zipfile
from pathlib import Path

UPDATE_LOCK=threading.RLock()
ROOT_FILES={'server.py','core.py','seed.py','advisor.py','updater.py','launcher.py','version.json','README.md','LOCAL-MODEL-CHECK.md','Start-Forage.bat','start.sh','build_release.py'}
STATIC_FILES={'static/index.html','static/app.js','static/style.css','static/render.js','static/card-view.js'}
PROGRAM_FILES=ROOT_FILES|STATIC_FILES
MAX_PACKAGE=20*1024*1024


def version(value):
    if not isinstance(value,str) or not re.fullmatch(r'v?\d+\.\d+\.\d+',value):raise ValueError('Use a stable version such as 0.2.0.')
    return tuple(map(int,value.lstrip('v').split('.')))

def current_version(root):return read_json(Path(root)/'version.json',{'version':'0.1.0'})['version']

def read_json(path,default=None):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:return default

def write_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,indent=2),encoding='utf-8');os.replace(tmp,path)

def repository(value):
    if not isinstance(value,str):raise ValueError('Enter owner/repository.')
    value=value.strip().removeprefix('https://github.com/').rstrip('/')
    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]{1,100}',value) or value.split('/')[1] in ['.','..']:raise ValueError('Enter a GitHub repository as owner/repository; no credentials or extra URL paths.')
    return value

def config(data):return read_json(Path(data)/'update-config.json',{'repository':'bh02411-design/forage','check_on_start':True})

def configure(data,repo,check_on_start=True):
    cfg={'repository':repository(repo) if repo.strip() else '', 'check_on_start':bool(check_on_start)}
    write_json(Path(data)/'update-config.json',cfg)
    # A change of source invalidates any previously advertised release.
    write_json(Path(data)/'updates'/'status.json',{'status':'not_checked' if cfg['repository'] else 'not_configured'})
    return cfg

def status(root,data):
    pending=read_json(Path(data)/'updates'/'pending.json')
    tx=read_json(Path(data)/'updates'/'transaction.json')
    return {'current_version':current_version(root),'config':config(data),'last_check':read_json(Path(data)/'updates'/'status.json',{'status':'not_checked'}),'pending':pending and {'version':pending['version']},'rollback_available':bool(tx and tx.get('status')=='installed'),'launcher_required':True}

class ReleaseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        u=urllib.parse.urlsplit(newurl)
        if u.scheme!='https' or u.username or u.password or u.port not in [None,443] or u.hostname not in ['github.com','release-assets.githubusercontent.com','objects.githubusercontent.com']:raise ValueError('Unexpected update download redirect.')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def fetch(url,limit):
    req=urllib.request.Request(url,headers={'User-Agent':'Forage-Updater','Accept':'application/vnd.github+json' if 'api.github.com/' in url else 'application/octet-stream','X-GitHub-Api-Version':'2022-11-28'})
    with urllib.request.build_opener(ReleaseRedirect()).open(req,timeout=30) as response:
        payload=response.read(limit+1)
        if len(payload)>limit:raise ValueError('Update exceeds the download size limit.')
        return payload

def check(root,data):
    repo=config(data)['repository']
    if not repo:return {'status':'not_configured','message':'Set a release repository in Updates.'}
    try:
        release=json.loads(fetch('https://api.github.com/repos/'+repository(repo)+'/releases/latest',1024*1024))
        tag=release['tag_name'];remote=version(tag);local=version(current_version(root))
        if release.get('draft') or release.get('prerelease'):raise ValueError('Only stable published releases are supported.')
        asset=next((a for a in release.get('assets',[]) if a.get('name')=='Forage-update.zip'),None)
        if not asset:raise ValueError('Release is missing Forage-update.zip.')
        digest=asset.get('digest','')
        if not re.fullmatch(r'sha256:[a-fA-F0-9]{64}',digest):raise ValueError('GitHub has not supplied a SHA-256 digest for the update asset.')
        url=asset.get('browser_download_url','');u=urllib.parse.urlsplit(url)
        expected='/'+repo+'/releases/download/'+tag+'/Forage-update.zip'
        if u.scheme!='https' or u.netloc!='github.com' or u.path!=expected or u.query or u.fragment:raise ValueError('Release asset does not belong to the configured repository and tag.')
        result={'status':'available' if remote>local else 'up_to_date','version':tag.lstrip('v'),'repository':repo,'url':url,'sha256':digest.split(':')[1].lower(),'notes':str(release.get('body') or '')[:4000]}
    except Exception as exc:result={'status':'error','message':str(exc)[:500]}
    result['checked_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    write_json(Path(data)/'updates'/'status.json',result)
    return result

def verify_package(archive,expected_version):
    """Validate all paths, hashes, sizes and metadata before extracting anything."""
    with zipfile.ZipFile(archive) as z:
        infos=z.infolist();names=[i.filename for i in infos]
        if len(names)!=len(set(n.casefold() for n in names)) or len(names)>100:raise ValueError('Duplicate or excessive update entries.')
        if 'release.json' not in names:raise ValueError('Missing release manifest.')
        for i in infos:
            if i.filename not in PROGRAM_FILES|{'release.json'} or i.is_dir() or '\\' in i.filename or stat.S_ISLNK(i.external_attr>>16):raise ValueError('Update contains an unapproved path: '+i.filename)
            if i.file_size>MAX_PACKAGE or i.flag_bits&1:raise ValueError('Invalid update entry.')
        if sum(i.file_size for i in infos)>MAX_PACKAGE:raise ValueError('Expanded update exceeds size limit.')
        manifest=json.loads(z.read('release.json'))
        if manifest.get('format')!=1 or version(manifest.get('version'))!=version(expected_version):raise ValueError('Release version or format mismatch.')
        files=manifest.get('files')
        if not isinstance(files,dict) or set(files)!=set(names)-{'release.json'} or not PROGRAM_FILES<=set(files):raise ValueError('Release must contain exactly the supported application files.')
        for name,digest in files.items():
            if not isinstance(digest,str) or hashlib.sha256(z.read(name)).hexdigest()!=digest:raise ValueError('Hash mismatch: '+name)
        metadata=json.loads(z.read('version.json'))
        if version(metadata['version'])!=version(expected_version) or metadata.get('update_format')!=1:raise ValueError('Application version metadata mismatch.')
        # Syntax checks do not execute downloaded code.
        for name in files:
            if name.endswith('.py'):compile(z.read(name),name,'exec')
        return manifest

def stage(root,data):
    with UPDATE_LOCK:
        found=check(root,data)
        if found.get('status')!='available':raise ValueError(found.get('message','No newer stable update is available.'))
        folder=Path(data)/'updates';folder.mkdir(parents=True,exist_ok=True)
        payload=fetch(found['url'],MAX_PACKAGE)
        if hashlib.sha256(payload).hexdigest()!=found['sha256']:raise ValueError('Downloaded update failed the GitHub SHA-256 check.')
        archive=folder/'candidate.zip';archive.write_bytes(payload)
        verify_package(archive,found['version'])
        os.replace(archive,folder/'pending.zip')
        write_json(folder/'pending.json',{'version':found['version'],'sha256':found['sha256'],'repository':found['repository']})
        return {'version':found['version'],'status':'ready'}

def replace_bytes(path,payload):
    path=Path(path)
    if path.is_symlink() or path.parent.is_symlink():raise ValueError('Refusing to replace an application symlink.')
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.update-tmp');tmp.write_bytes(payload);os.replace(tmp,path)

def recover(root,data):
    """Restore interrupted installations before launching a server."""
    tx=read_json(Path(data)/'updates'/'transaction.json')
    if tx and tx.get('status') in ['installing','rolling_back']:rollback(root,data,allow_interrupted=True)

def rollback(root,data,allow_interrupted=False):
    with UPDATE_LOCK:
        root=Path(root);data=Path(data);txfile=data/'updates'/'transaction.json';tx=read_json(txfile)
        if not tx or tx.get('status') not in (['installed','installing','rolling_back'] if allow_interrupted else ['installed']):raise ValueError('No application rollback is available.')
        folder=data/'updates'/'backups'/tx['backup']
        tx['status']='rolling_back';write_json(txfile,tx)
        for name,existed in tx['files'].items():
            if name not in PROGRAM_FILES:raise ValueError('Invalid rollback file.')
            target=root/name
            if existed:replace_bytes(target,(folder/'program'/name).read_bytes())
            elif target.exists():target.unlink()
        tx['status']='rolled_back';write_json(txfile,tx)
        (data/'updates'/'pending.json').unlink(missing_ok=True)
        return {'status':'rolled_back','version':current_version(root)}

def install_pending(root,data):
    with UPDATE_LOCK:
        root=Path(root);data=Path(data);folder=data/'updates';pending=read_json(folder/'pending.json')
        if not pending:raise ValueError('No staged update.')
        archive=folder/'pending.zip'
        if hashlib.sha256(archive.read_bytes()).hexdigest()!=pending['sha256']:raise ValueError('Staged update changed since verification.')
        if version(pending['version'])<=version(current_version(root)):raise ValueError('Staged update is not newer than this installation.')
        manifest=verify_package(archive,pending['version'])
        ident=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup=folder/'backups'/ident;backup.mkdir(parents=True)
        before={}
        for name in manifest['files']:
            source=root/name
            if source.is_symlink() or source.parent.is_symlink():raise ValueError('Application symlinks are not supported.')
            before[name]=source.exists()
            if source.exists():
                dest=backup/'program'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
        if (data/'forage.sqlite3').exists():
            with sqlite3.connect(data/'forage.sqlite3') as source,sqlite3.connect(backup/'workspace.sqlite3') as dest:source.backup(dest)
        tx={'status':'installing','backup':ident,'files':before,'from_version':current_version(root),'to_version':pending['version']}
        write_json(folder/'transaction.json',tx)
        try:
            with zipfile.ZipFile(archive) as z:
                for name in sorted(manifest['files'],key=lambda x:x=='version.json'):replace_bytes(root/name,z.read(name))
            tx['status']='installed';write_json(folder/'transaction.json',tx)
            (folder/'pending.json').unlink()
        except Exception:
            rollback(root,data,allow_interrupted=True);raise
        return {'status':'installed','version':current_version(root)}
