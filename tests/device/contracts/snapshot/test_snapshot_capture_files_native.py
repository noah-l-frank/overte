#!/usr/bin/env python3
"""Original Snapshot save/FD/one-send retirement; no renderer or Android runtime.

Selected fixed Phone5527 test boundaries; actual Pico observer/getter bodies,
Qt PNG bytes, descriptors, inode checks and target retirement are real host IO.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import hashlib
import zipfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.pico4 import snapshot_capture_source as contract


def body(source,marker):
    start=source.index(marker);opening=source.index('{',start);depth=1;end=opening+1
    while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]+'\n'


environment=dict(os.environ);library=[];major=environment.get('OVERTE_NATIVE_QT_MAJOR','6')
if major not in ('5','6'):raise ValueError('Unsupported Qt major')
if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
    prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
    environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
        LD_LIBRARY_PATH=str(prefix/'usr/lib64'),QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'))
    library=['-L'+str(prefix/'usr/lib64')]
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',
    *('Qt'+major+name for name in ('Core','Gui'))],text=True,env=environment))
with tempfile.TemporaryDirectory(prefix='snapshot-capture-files-') as directory:
    stage=Path(directory);runtime=stage/'runtime';runtime.mkdir(mode=0o700)
    save=(ROOT/'interface/src/ui/Snapshot.cpp').read_text()
    tsi=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
    (stage/'original-snapshot-save.inc').write_text(body(save,'QString Snapshot::saveSnapshot(')+body(save,'QFile* Snapshot::savedFileForSnapshot(')+body(save,'void Snapshot::complete360('))
    (stage/'original-snapshot-files-getter.inc').write_text(body(tsi,'QVariantMap TestScriptingInterface::featurePicoSnapshotCaptureFiles('))
    source=Path(__file__).with_name('snapshot-capture-files-test.cpp')
    for profile,defines in (('pico',['OVERTE_E2E_FEATURE_TESTS','ANDROID_APP_PICO_INTERFACE']),
            ('production',[]),('other',['OVERTE_E2E_FEATURE_TESTS'])):
        executable=stage/profile
        subprocess.run(['c++','-std=c++17','-fPIC','-Wall','-Wextra','-Werror','-UNDEBUG','-I'+str(ROOT),'-I'+str(stage),
            *('-D'+value for value in defines),str(source),'-o',str(executable),*library,*flags],check=True,timeout=60,env=environment)
        modes=('success','360','cancelled','partial','pending','pending-close','foreign','changed-inode','changed-bytes',
            'fifo','early-missing','late-file','late-namespace','new-scope') if profile=='pico' else ('production',)
        for mode in modes:
            data=stage/(profile+'-'+mode);data.mkdir(mode=0o700)
            raw=subprocess.check_output(['unshare','--user','--map-root-user','--net',str(executable),mode,'--testScript'],text=True,
                timeout=15,env=environment|dict(XDG_DATA_HOME=str(data),QT_QPA_PLATFORM='offscreen',XDG_RUNTIME_DIR=str(runtime)))
            for line in raw.splitlines():
                value=json.loads(line);roots={row['path'].rsplit('/',1)[0] for row in value['source']['rows']}
                with patch.object(contract,'ROOTS',roots):contract.source(value['source'],value['capturedEpochMs'])
        if profile=='pico':
            data=stage/'disabled';data.mkdir(mode=0o700)
            subprocess.run(['unshare','--user','--map-root-user','--net',str(executable),'disabled'],check=True,timeout=15,
                env=environment|dict(XDG_DATA_HOME=str(data),QT_QPA_PLATFORM='offscreen',XDG_RUNTIME_DIR=str(runtime)))
    # Existing reviewed real public-domain GifCreator fixture; no dependency
    # installation, download, synthetic encoder or altered product worker.
    with zipfile.ZipFile(Path(__file__).parent/'fixtures/GifCreator.zip') as archive:
        header=archive.read('GifCreator.h')
    assert hashlib.sha256(header).hexdigest()=='275e4fd71a1d3bdc80279aee59d6abf530d628ea77aec01a2cd155220be2c8be'
    (stage/'GifCreator.h').write_bytes(header)
    animated=(ROOT/'interface/src/ui/SnapshotAnimated.cpp').read_text()
    (stage/'original-snapshot-gif.inc').write_text(body(animated,'bool SnapshotAnimated::processFrames('))
    for profile,defines in (('pico-gif',['OVERTE_E2E_FEATURE_TESTS','ANDROID_APP_PICO_INTERFACE']),('production-gif',[])):
        executable=stage/profile
        # The unchanged third-party real GifCreator header has its own warning
        # profile. The strict original-client/header check above remains on.
        subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-I'+str(ROOT),'-I'+str(stage),
            *('-D'+value for value in defines),str(Path(__file__).with_name('snapshot-capture-gif-test.cpp')),
            '-o',str(executable),*library,*flags],check=True,timeout=60,env=environment)
        for mode in ('success','failure','cancel'):
            data=stage/(profile+'-'+mode);data.mkdir(mode=0o700)
            raw=subprocess.check_output(['unshare','--user','--map-root-user','--net',str(executable),mode,'--testScript'],text=True,
                timeout=15,env=environment|dict(XDG_DATA_HOME=str(data),QT_QPA_PLATFORM='offscreen',XDG_RUNTIME_DIR=str(runtime)))
            for line in raw.splitlines():
                value=json.loads(line);roots={row['path'].rsplit('/',1)[0] for row in value['rows']}
                with patch.object(contract,'ROOTS',roots):contract.source(value,value['capturedEpochMs'])
print('PASS: original Pico QFile PNG/FD/close/plan/one-send retirement and non-Pico production profiles (Qt'+major+')')
