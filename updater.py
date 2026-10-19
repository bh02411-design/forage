"""Opt-in GitHub release updates. Never install data or arbitrary ZIP paths."""
import datetime, hashlib, json, os, re, shutil, sqlite3, stat, threading, urllib.parse, urllib.request, zipfile
from pathlib import Path

UPDATE_LOCK=threading.RLock()
ROOT_FILES={'server.py','core.py','seed.py','advisor.py','updater.py','launcher.py','version.json','README.md','LOCAL-MODEL-CHECK.md','Start-Forage.bat','start.sh','build_release.py'}
STATIC_FILES={'static/index.html','static/app.js','static/style.css','static/render.js','static/card-view.js'}
PROGRAM_FILES=ROOT_FILES|STATIC_FILES
MAX_PACKAGE=20*1024*1024


# Release notes stay in an existing updater file so older installers accept the package.
CHANGELOG={
 '0.2.35':['Add a Windows installer with a bundled Python runtime, Forage icon, shortcuts and a short getting-started guide.','Keep fresh installations empty and store personal data separately from installed application files.','Connect new installs to the existing public GitHub update channel; AI setup remains optional.'],
 '0.2.34':['Show full stored mana costs as colored pips in the physical deck checklist, including generic and repeated colored requirements.','Preserve hybrid, Phyrexian and variable symbols; distinguish lands and missing mana data.'],
 '0.2.33':['Fix deck export including Considering and swap staging cards that are outside board totals.','Preserve custom Archidekt categories and commander designation instead of replacing them with Mainboard.','Preview the exported list and included/excluded counts before downloading.'],
 '0.2.32':['Show total cards to sleeve, counting quantities, and marked entries in the physical deck checklist.','Refresh checklist totals after marking cards sleeved.'],
 '0.2.31':['Mark individual deck entries as Needs sleeving in card details; show markers in graphical and list views.','Filter the board to marked cards or open a physical-deck checklist and mark cards done after sleeving.','Keep markers saved per deck without changing roles, categories or board totals.'],
 '0.2.30':['Add an explicit Hide chat control in the conversation header and Show chat on the visual board.','Reuse the saved per-deck expanded view so collapsing chat gives the board full width and restores the latest conversation when reopened.'],
 '0.2.29':['Remove board-origin labels from shared swap cards and their category editor.','Present Swap In and Swap Out as a shared staging area excluded from board totals.'],
 '0.2.28':['Exclude shared Swap In and Swap Out categories from both board totals, including renamed categories.','Keep staging counts visible and align deck size, curve, roles and mana statistics with the unstaged mainboard.'],
 '0.2.27':['Add a collapsible desktop sidebar with accessible icon navigation and a remembered preference.','Keep the full horizontal navigation available on smaller screens.'],
 '0.2.26':['Show only commander-identity colors in mana comparison statistics, including combined partner identities.','Show colorless when relevant and let visible color cards fill the available width.'],
 '0.2.25':['Move Mana cost vs production above the mana curve and role panels.'],
 '0.2.24':['Add Forage’s branded green icon to the browser tab using a self-contained scalable favicon.'],
 '0.2.23':['Show mana cost versus potential production bars and per-color counts, with a mana-permanents toggle.','Add a reviewable basic-land mix optimizer using colored casting costs, early-spell weighting and fixed direct land sources.','Keep total basics, nonbasics, protected cards and Considering unchanged; respect confirmed collection availability.','Apply as one undoable edit, detect stale previews, and flag incomplete data and unmodeled mana conditions.'],
 '0.2.22':['Share the pinned Swap In and Swap Out categories across Mainboard and Considering.','Show each card’s board assignment and keep current-board counts separate.','Dropping existing cards into shared categories preserves board assignment; collection drops enter Considering.'],
 '0.2.21':['Use focused instructions for cut reviews instead of the full additions workflow.','Recover clearly labeled removal lists and alternate cut field names before checking mainboard membership, counts and protected cards.','Retain failed cut responses in Context used diagnostics instead of displaying an internal schema error.'],
 '0.2.20':['Open clicked cards in a larger detail dialog with artwork beside editing controls.','Pin real Swap In and Swap Out categories in a separate Mainboard column on the right.','Support normal category editing, drag-and-drop, selection, removal and undo; keep custom renamed swap categories pinned.','Hide empty ordinary category placeholders without deleting cards or category definitions.'],
 '0.2.19':['Route explicit cut requests to the current mainboard instead of collection additions.','Validate distinct cut names, requested counts and protection flags; display checked removal candidates with costs and reasons.','Keep cut failures in the removal workflow instead of substituting unrelated collection matches.'],
 '0.2.18':['Compact large deck and Considering rosters without dropping card names, quantities, roles, categories or protection flags.','Reduce oversized pending-plan and decision payloads before shortening conversation history.','Report context-packaging limits accurately and include roster coverage in context diagnostics.'],
 '0.2.17':['Treat manually assigned Uncategorized cards as eligible when Auto-categorize is clicked; preserve named custom categories.','Resolve missing card rules and types automatically before auto-categorizing, using saved metadata and cache first.','Show progress and connection failures, preserve custom categories and other boards, and keep the operation undoable.'],
 '0.2.16':['Add Select all with selection counts to Edit category.','Add bulk removal from the deck with one-step Undo; preserve collection ownership and protect locked cards and commanders.','Label category entries by board and show quantities.'],
 '0.2.15':['Add collection sorting by name, mana value, color identity, type, rarity, owned quantity and available quantity.','Remember ascending/descending preferences across visits; keep unresolved values last.'],
 '0.2.14':['Add common local Scryfall-style filters on deck and collection views.','Add clickable syntax keys, missing-data notices and explicit unsupported-query errors.'],
 '0.2.13':['Replace the generic Windows tray icon with Forage’s green eight-spoke mark on a dark background.'],
 '0.2.12':['Add Windows system tray mode with Open Forage, Start with Windows and Quit controls.','Add in-app setup and a Start-menu shortcut; run quietly without a persistent console window.'],
 '0.2.11':['Auto-categorize unassigned cards entering Mainboard or Considering using saved roles and card text.','Add an undoable Auto-categorize button on each board; preserve custom categories.'],
 '0.2.10':['Render prose-prefixed, fenced and nested AI JSON as readable chat.','Preserve embedded swap proposals for validation and graphical decisions instead of displaying internal fields.'],
 '0.2.9':['Add Update history with readable changes, installed-version labels and stable-release selection.','Check workspace compatibility and create a workspace snapshot before switching or rolling back.'],
 '0.2.8':['Move pending card choices, swaps and category plans into the chat header.','Remove the duplicate On the table section and bring analytics up.'],
 '0.2.7':['Display unranked collection-search fallbacks as graphical card options with decision controls.'],
 '0.2.6':['Display checked recommendations and proposed cuts as cards inside the conversation.','Add inspection, Considering, swap acceptance, different-cut requests and passing.'],
 '0.2.5':['Reduce repeated card metadata in AI prompts while preserving conversation context.','Honor explicit mana-value ranges in collection searches.'],
 '0.2.4':['Open conversations at the latest reply and preserve your position when reading older messages.'],
 '0.2.3':['Keep commanders at the top left across grouping and sorting modes.'],
 '0.2.2':['Move card quantities to the top left and widen the gap between deck and chat.'],
 '0.2.1':['Earlier updater release; see its GitHub release notes for details.'],
 '0.2.0':['Introduce supervised GitHub release installation, application backups and startup recovery.']
}
DEFAULT_REPOSITORY='bh02411-design/forage'

def workspace_version(data):
    path=Path(data)/'forage.sqlite3'
    if not path.exists():return 1
    with sqlite3.connect(path) as con:
        if not con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='workspace'").fetchone():return 1
        row=con.execute('SELECT payload FROM workspace WHERE id=1').fetchone()
    value=json.loads(row[0]).get('version') if row else 1
    if type(value) is not int:raise ValueError('Workspace format is unknown; version switching is blocked.')
    return value

def check_compatibility(metadata,data):
    supported=metadata.get('workspace_versions')
    # These released versions share the original workspace format. Future releases must declare support.
    if supported is None and (0,2,0)<=version(metadata.get('version',''))<=(0,2,8):supported=[1]
    if not isinstance(supported,list) or not supported or any(type(v) is not int or v<1 for v in supported):raise ValueError('This release does not declare a supported workspace format.')
    if workspace_version(data) not in supported:raise ValueError('This release is incompatible with your current workspace. No application files or deck data were changed.')

def snapshot_workspace(data,folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    if (Path(data)/'forage.sqlite3').exists():
        with sqlite3.connect(Path(data)/'forage.sqlite3') as source,sqlite3.connect(folder/'workspace.sqlite3') as dest:source.backup(dest)

def release_details(root,repo,release):
    tag=release['tag_name'];remote=version(tag);local=version(current_version(root))
    if release.get('draft') or release.get('prerelease'):raise ValueError('Only stable published releases are supported.')
    asset=next((a for a in release.get('assets',[]) if a.get('name')=='Forage-update.zip'),None)
    if not asset:raise ValueError('Release is missing Forage-update.zip.')
    digest=asset.get('digest','')
    if not re.fullmatch(r'sha256:[a-fA-F0-9]{64}',digest):raise ValueError('GitHub has not supplied a SHA-256 digest for the update asset.')
    url=asset.get('browser_download_url','');u=urllib.parse.urlsplit(url)
    if u.scheme!='https' or u.netloc!='github.com' or u.path!='/'+repo+'/releases/download/'+tag+'/Forage-update.zip' or u.query or u.fragment:raise ValueError('Release asset does not belong to the configured repository and tag.')
    return {'status':'available' if remote>local else 'up_to_date','version':tag.lstrip('v'),'repository':repo,'url':url,'sha256':digest.split(':')[1].lower(),'notes':str(release.get('body') or '')[:4000]}

def release_history(root,data):
    repo=config(data)['repository'];error=None;releases=[]
    cache=Path(data)/'updates'/'release-history.json'
    if repo:
        try:
            raw=json.loads(fetch('https://api.github.com/repos/'+repository(repo)+'/releases?per_page=100',2*1024*1024))
            if not isinstance(raw,list):raise ValueError('Unexpected release list.')
            for release in raw:
                try:releases.append(release_details(root,repo,release))
                except (ValueError,KeyError,TypeError):continue
            write_json(cache,{'repository':repo,'releases':releases})
        except Exception as exc:
            error=str(exc)[:300];cached=read_json(cache,{})
            if cached.get('repository')==repo:releases=cached.get('releases',[])
    by_version={row['version']:row for row in releases}
    if repo==DEFAULT_REPOSITORY:
        for number,notes in CHANGELOG.items():
            by_version.setdefault(number,{'version':number,'repository':repo,'notes':'','available':False})['changes']=notes
    installed=current_version(root);by_version.setdefault(installed,{'version':installed,'notes':'Installed locally.','available':False})
    for number,row in by_version.items():
        row['installed']=version(number)==version(installed)
        row['available']=bool(row.get('url') and row.get('sha256')) and not row['installed']
        row['direction']='older' if version(number)<version(installed) else 'newer'
    return {'current_version':installed,'releases':sorted(by_version.values(),key=lambda row:version(row['version']),reverse=True),'offline_error':error,'workspace_version':workspace_version(data)}

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
    return {'current_version':current_version(root),'config':config(data),'last_check':read_json(Path(data)/'updates'/'status.json',{'status':'not_checked'}),'pending':pending and {'version':pending['version']},'rollback_available':bool(tx and tx.get('status')=='installed'),'rollback_version':tx.get('from_version') if tx else None,'launcher_required':True}

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
        result=release_details(root,repo,release)
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

def stage(root,data,target=None):
    with UPDATE_LOCK:
        if target is not None:
            target='.'.join(map(str,version(target)));repo=repository(config(data)['repository'])
            if version(target)==version(current_version(root)):raise ValueError('This version is already installed.')
            release=json.loads(fetch('https://api.github.com/repos/'+repo+'/releases/tags/v'+target,1024*1024))
            found=release_details(root,repo,release)
            if version(found['version'])!=version(target):raise ValueError('Requested release tag mismatch.')
        else:found=check(root,data)
        if target is None and found.get('status')!='available':raise ValueError(found.get('message','No newer stable update is available.'))
        folder=Path(data)/'updates';folder.mkdir(parents=True,exist_ok=True)
        payload=fetch(found['url'],MAX_PACKAGE)
        if hashlib.sha256(payload).hexdigest()!=found['sha256']:raise ValueError('Downloaded update failed the GitHub SHA-256 check.')
        archive=folder/'candidate.zip';archive.write_bytes(payload)
        verify_package(archive,found['version'])
        with zipfile.ZipFile(archive) as z:check_compatibility(json.loads(z.read('version.json')),data)
        os.replace(archive,folder/'pending.zip')
        write_json(folder/'pending.json',{'version':found['version'],'sha256':found['sha256'],'repository':found['repository'],'operation':'switch' if target else 'update','from_version':current_version(root)})
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

def preflight_rollback(data):
    data=Path(data);tx=read_json(data/'updates'/'transaction.json')
    if not tx or tx.get('status')!='installed':raise ValueError('No application rollback is available.')
    check_compatibility(read_json(data/'updates'/'backups'/tx['backup']/'program'/'version.json',{}),data)

def rollback(root,data,allow_interrupted=False):
    with UPDATE_LOCK:
        root=Path(root);data=Path(data);txfile=data/'updates'/'transaction.json';tx=read_json(txfile)
        if not tx or tx.get('status') not in (['installed','installing','rolling_back'] if allow_interrupted else ['installed']):raise ValueError('No application rollback is available.')
        folder=data/'updates'/'backups'/tx['backup']
        check_compatibility(read_json(folder/'program'/'version.json',{}),data)
        snapshot_workspace(data,data/'updates'/'rollback-snapshots'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
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
        if pending.get('operation')=='switch':
            if pending.get('from_version')!=current_version(root):raise ValueError('Installed version changed after staging. Select the release again.')
        elif version(pending['version'])<=version(current_version(root)):raise ValueError('Staged update is not newer than this installation.')
        manifest=verify_package(archive,pending['version'])
        with zipfile.ZipFile(archive) as z:check_compatibility(json.loads(z.read('version.json')),data)
        ident=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup=folder/'backups'/ident;backup.mkdir(parents=True)
        before={}
        for name in manifest['files']:
            source=root/name
            if source.is_symlink() or source.parent.is_symlink():raise ValueError('Application symlinks are not supported.')
            before[name]=source.exists()
            if source.exists():
                dest=backup/'program'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
        snapshot_workspace(data,backup)
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
