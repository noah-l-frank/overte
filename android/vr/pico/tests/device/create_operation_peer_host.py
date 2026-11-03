"""Existing Create worker fixture with retained early admission diagnostics."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import traceback
ROOT=Path(__file__).resolve().parents[5]
sys.path[:0]=[str(ROOT/'tests/device'),str(Path(__file__).resolve().parent)]
import create_peer_cli_host as original_host
from adapters.normal_feature_state import PrivateFeatureState
config=PrivateFeatureState(Path(sys.argv[2])).read();artifact_root=Path(config['artifactRoot'])
original_inputs=original_host.model_inputs
def model_inputs(value,_directory):
    return original_inputs(dict(value,worldPath=str(artifact_root/'replica-model.json')),artifact_root)
original_host.model_inputs=model_inputs
def private_state(path):
    path=Path(path)
    return PrivateFeatureState(artifact_root/path.name if path.name=='replica-model.json' else path)
original_host.PrivateFeatureState=private_state
main=original_host.main
from adapters.pico4 import create_peer_actor
original=create_peer_actor.CreatePeerAdmission.__init__
def admission(self,*args,**kwargs):
    try:return original(self,*args,**kwargs)
    except Exception:traceback.print_exc();raise
create_peer_actor.CreatePeerAdmission.__init__=admission

import atexit
import hashlib
def source_receipt():
    rows={}
    for module in list(sys.modules.values()):
        name=getattr(module,'__file__',None)
        if not name:continue
        path=Path(name).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():continue
        info=path.lstat();rows[str(path)]=dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),physical=[info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_nlink,info.st_size,info.st_mtime_ns,info.st_ctime_ns])
    (artifact_root/'peer-loaded-sources.json').write_text(__import__('json').dumps(rows,sort_keys=True))
atexit.register(source_receipt)

if __name__=='__main__':raise SystemExit(main())
