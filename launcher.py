#!/usr/bin/env python3
"""Supervise Forage so application files change only while its server is stopped."""
import argparse, json, os, subprocess, sys, time, urllib.request
from pathlib import Path
import updater

ROOT=Path(__file__).resolve().parent

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

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);parser.add_argument('--open',action='store_true');args=parser.parse_args()
    data=Path(os.environ.get('FORAGE_DATA_DIR',str(ROOT/'data'))).resolve()
    updater.recover(ROOT,data)
    first=True;verify_start=False
    while True:
        cmd=[sys.executable,str(ROOT/'server.py'),'--port',str(args.port)]
        if args.open and first:cmd.append('--open')
        env=dict(os.environ,FORAGE_LAUNCHER='1',FORAGE_VERSION_SWITCH='1')
        process=subprocess.Popen(cmd,cwd=ROOT,env=env);first=False
        try:
            if verify_start and not healthy(process,args.port,updater.current_version(ROOT)):
                if process.poll() is None:process.terminate();process.wait(timeout=10)
                updater.rollback(ROOT,data);print('Update failed its startup check. Previous application restored.',flush=True)
                verify_start=False;continue
            verify_start=False
            code=process.wait()
        except KeyboardInterrupt:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()
            return
        if code not in [75,76]:return
        try:
            if code==75:updater.install_pending(ROOT,data);verify_start=True
            else:updater.rollback(ROOT,data)
        except Exception as exc:
            print('Update was not applied: '+str(exc),flush=True)
            try:updater.recover(ROOT,data)
            except Exception as recovery:
                print('Recovery needs attention: '+str(recovery)+'. Application was not restarted.',flush=True);return
            print('Restarting the existing application.',flush=True)

if __name__=='__main__':main()
