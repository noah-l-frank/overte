#!/usr/bin/env python3
"""Reproduce fixed executable-source admission pins without contacting a client."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parents[2]
BASE='3c8e85c69f007b6a3702bcc7aa5f412218b84668'
DEST=ROOT/'tests/device/feature_journeys/phone-emote-admission-pins.v1.json'
BOUND='(function(id) { return Script.require(Script.require.resolve(id, this.filename)); })'
JSON_MODULE='module.exports = JSON.parse(__json)'
MANAGERS=['defaultScripts.js','system/create/edit.js','system/snapshot.js',
    'communityScripts/armored-chat/armored_chat.js','communityScripts/chatBubbles/chatBubbles.js',
    'communityScripts/notificationCore/notificationCore.js']


def pin(code):
    raw=code.encode('utf-16-le',errors='surrogatepass')
    return dict(encoding='utf-16le-code-units',codeUnits=len(raw)//2,sha256=hashlib.sha256(raw).hexdigest())


def generate():
    def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args])
    base=git('rev-parse',BASE+'^{commit}').decode().strip()
    paths=git('ls-tree','-r','--name-only',base,'--','scripts').decode().splitlines()
    files=[]
    for path in paths:
        if not path.endswith(('.js','.json')):continue
        code=git('show',base+':'+path).decode('utf-8')
        runtime=path[len('scripts/'):]
        if runtime=='defaultScripts.js':continue # Qt selects the Phone bootstrap.
        files.append(dict(path=path,runtimePath=runtime,kind='json-module' if path.endswith('.json') else 'script',
            **pin(JSON_MODULE if path.endswith('.json') else code)))
        if runtime=='+android_phoneInterface/defaultScripts.js':
            files.append(dict(path=path,runtimePath='defaultScripts.js',kind='script',**pin(code)))
    probe='tests/device/probe/overte_e2e_probe.js'
    return dict(phoneEmoteAdmissionCatalogVersion=1,sourceBase=base,managers=MANAGERS,
        files=sorted(files,key=lambda row:row['runtimePath']),probe=dict(path=probe,**pin(git('show',base+':'+probe).decode('utf-8'))),
        native=[dict(resourceName='(boundRequire)',**pin(BOUND))])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true');args=parser.parse_args()
    value=generate()
    if args.write:DEST.write_text(json.dumps(value,indent=2)+'\n')
    else:
        if json.loads(DEST.read_text())!=value:raise SystemExit('Phone Emote admission catalog differs from its fixed source commit')
        print('PASS: fixed Phone executable admission pins reproduce exactly')
