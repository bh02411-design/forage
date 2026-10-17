#!/usr/bin/env python3
"""Build an update ZIP containing code only, never the local workspace."""
import hashlib, json, zipfile
from pathlib import Path
import updater

def build(root,output):
    root=Path(root);output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    files={name:(root/name).read_bytes() for name in sorted(updater.PROGRAM_FILES)}
    manifest={'format':1,'version':updater.current_version(root),'files':{name:hashlib.sha256(payload).hexdigest() for name,payload in files.items()}}
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for name,payload in files.items():z.writestr(name,payload)
        z.writestr('release.json',json.dumps(manifest,indent=2))
    updater.verify_package(output,manifest['version'])
    return manifest

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',default='dist/Forage-update.zip');args=p.parse_args()
    m=build(Path(__file__).resolve().parent,args.output);print('Built Forage '+m['version']+' update at '+args.output)
