"""Stage a clean Windows installation with a pinned, bundled Python runtime."""
import argparse, hashlib, json, math, shutil, struct, urllib.request, zipfile
from pathlib import Path
import updater

PYTHON_VERSION='3.13.16'
PYTHON_URL=f'https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip'
PYTHON_SHA256='97dae5274cc54867065e8d5a3226e48c35017ed332a0fdb0e27d5b5821961297'

GUIDE=r'''Welcome to Forage

1. Open Forage from your desktop or Start menu. It opens in your browser.
2. Click Import to add a deck, then open Collection to import your collection.
3. Use Resolve card data to load card text, costs and artwork.
4. Optional AI: install LM Studio from https://lmstudio.ai/, load a chat model,
   and start its local server. In Forage, open Local AI & settings, select
   http://127.0.0.1:1234/v1, list models, choose your model and save.
5. New versions appear under Local AI & settings > Application updates.
   Click Update and restart when you are ready. Your data stays on your PC.

Deck editing, collection tools and the physical checklist work without AI.
Python is included. You do not need to install it or run commands.
Closing the browser leaves Forage in the system tray. Right-click its icon
to reopen or quit. Start with Windows is optional in Local AI & settings.

Your decks, collection, chats and backups are stored separately in:
%LOCALAPPDATA%\Forage\data
Use Backup in Forage to save a copy. Uninstalling preserves this data.
The download includes no other user's decks, collection or conversations.
Scryfall card lookups and GitHub update checks need internet access.
AI chat runs through your own local model; no paid AI account is required.

Before running this installer again, quit Forage from its tray menu.
This installer is for 64-bit Intel/AMD Windows 10/11 computers.
'''

def write_icon(path):
    size=64;pixels=bytearray()
    for y in reversed(range(size)):
        for x in range(size):
            dx,dy=x-31.5,y-31.5;r=math.hypot(dx,dy)
            spoke=(abs(dx)<2.5 or abs(dy)<2.5 or abs(dx-dy)<3.5 or abs(dx+dy)<3.5) and r<22
            red,green,blue,alpha=(197,232,165,255) if spoke else (12,20,15,255) if r<30 else (0,0,0,0)
            pixels.extend((blue,green,red,alpha))
    image=struct.pack('<IIIHHIIIIII',40,size,size*2,1,32,0,len(pixels),0,0,0,0)+pixels+bytes(size*size//8)
    Path(path).write_bytes(struct.pack('<HHH',0,1,1)+struct.pack('<BBBBHHII',size,size,0,0,1,32,len(image),22)+image)

def stage(root,output,runtime_archive=None):
    root=Path(root);output=Path(output)
    if output.exists() and any(output.iterdir()):raise ValueError('Use an empty output directory for installation staging.')
    output.mkdir(parents=True,exist_ok=True)
    payload=Path(runtime_archive).read_bytes() if runtime_archive else urllib.request.urlopen(PYTHON_URL,timeout=90).read()
    if hashlib.sha256(payload).hexdigest()!=PYTHON_SHA256:raise ValueError('Bundled Python checksum mismatch.')
    import io
    runtime=output/'runtime';runtime.mkdir()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for entry in archive.infolist():
            target=(runtime/entry.filename).resolve()
            if not target.is_relative_to(runtime.resolve()):raise ValueError('Invalid runtime archive path.')
        archive.extractall(runtime)
    (runtime/'python313._pth').write_text('python313.zip\n.\n..\nimport site\n',encoding='utf-8')
    for name in sorted(updater.PROGRAM_FILES):
        destination=output/name;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(root/name,destination)
    (output/'Getting-started.txt').write_text(GUIDE,encoding='utf-8')
    write_icon(output/'Forage.ico')
    (output/'bundled-runtime.json').write_text(json.dumps({'version':PYTHON_VERSION,'url':PYTHON_URL,'sha256':PYTHON_SHA256},indent=2))
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--runtime-archive');args=parser.parse_args()
    print(stage(Path(__file__).resolve().parent,args.output,args.runtime_archive))
