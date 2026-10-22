"""Fresh Snapshot historical JSON graphs retain every actual file boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from adapters.native_feature_observation import need
import overte_phone_assets_evidence as assets
from overte_phone_snapshots_evidence import SnapshotsOriginals
from overte_phone_script_history import canonical
from test_graphics_images import BINDING

RUN='d'*32


class SnapshotOriginalCloneTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='snapshot-original-clone-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.epoch=0.;self.allowed=True;self.guards=0
        self.owner=SnapshotsOriginals(self.root,BINDING,RUN,'primary',self.guard,lambda *_:True,kind='snapshots',monotonic=lambda:self.epoch)
        self.frame=dict(sourceEpochMs=20000,nested=[dict(original='actual',rows=[1,dict(value='original')])])

    def guard(self):self.guards+=1;need(self.allowed);return True

    def stored(self,index=1):return self.owner.expand(self.owner.write(index,self.frame))

    def evict(self,value):
        path=self.owner.path(value)
        with assets.AssetsOriginals._parsed_lock:
            for key in list(assets.AssetsOriginals._parsed):
                if key[0]==str(path):
                    _body,size=assets.AssetsOriginals._parsed.pop(key);assets.AssetsOriginals._parsed_bytes-=size

    def test_cold_and_cached_reads_parse_actual_raw_into_fresh_unshared_graphs(self):
        value=self.stored();self.evict(value);raw=self.owner.path(value).read_bytes();loads=json.loads;seen=[];self.guards=0
        def observed(content,*args,**kwargs):
            if content in (raw,raw.decode()):seen.append(type(content))
            return loads(content,*args,**kwargs)
        with patch.object(json,'loads',side_effect=observed),patch.object(assets,'deepcopy',wraps=deepcopy) as copied:
            first=self.owner.read(value);first['nested'][0]['rows'][1]['value']='caller mutation'
            second=self.owner.read(value);self.assertEqual(self.frame,second)
            second['nested'].append(dict(original='foreign'))
            self.assertEqual(self.frame,self.owner.read(value));self.assertEqual(0,copied.call_count)
        self.assertEqual([str,bytes,bytes,bytes],seen);self.assertEqual(6,self.guards)
        self.assertEqual(raw,self.owner.path(value).read_bytes())

    def test_shared_assets_default_clone_keeps_existing_deepcopy_behavior(self):
        owner=assets.AssetsOriginals(self.root,BINDING,RUN,'primary',self.guard,lambda *_:True,kind='assets')
        value=owner.expand(owner.write(1,self.frame))
        with patch.object(assets,'deepcopy',wraps=deepcopy) as copied:
            changed=owner.read(value);self.assertEqual(1,copied.call_count)
        changed['nested'][0]['original']='foreign';self.assertEqual(self.frame,owner.read(value))

    def test_cached_graph_never_substitutes_missing_changed_mode_link_or_replaced_actual_file(self):
        for index,mutation in enumerate(('missing','bytes','mode','link','inode'),1):
            with self.subTest(mutation=mutation):
                value=self.stored(index);self.owner.read(value);path=self.owner.path(value)
                if mutation=='missing':path.unlink()
                elif mutation=='bytes':path.write_bytes(path.read_bytes().replace(b'actual',b'forged'))
                elif mutation=='mode':path.chmod(0o644)
                elif mutation=='link':os.link(path,self.root/('alias-'+str(index)))
                else:
                    replacement=self.root/'replacement';replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);os.replace(replacement,path)
                with patch.object(self.owner,'clone_frame',wraps=self.owner.clone_frame) as clone:
                    with self.assertRaises((NativeUIError,FileNotFoundError)):self.owner.read(value)
                    self.assertEqual(0,clone.call_count)

    def test_actual_matching_hash_cannot_adopt_foreign_header_or_noncanonical_json(self):
        for index,mutation in enumerate(('role','binding','runId','index','frame','extra','whitespace','duplicate'),1):
            with self.subTest(mutation=mutation):
                value=self.stored(index);body=json.loads(self.owner.path(value).read_bytes())
                if mutation=='role':body['role']='actor'
                elif mutation=='binding':body['binding']['sessionId']='foreign'
                elif mutation=='runId':body['runId']='f'*32
                elif mutation=='index':body['index']+=1
                elif mutation=='frame':body['frame']=[]
                elif mutation=='extra':body['foreign']=True
                raw=canonical(body)
                if mutation=='whitespace':raw+=b'\n'
                elif mutation=='duplicate':raw=raw[:-1]+b',"frame":{}}'
                foreign=dict(value,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
                path=self.owner.path(foreign);path.write_bytes(raw);path.chmod(0o600);info=path.stat()
                foreign['file']=dict(device=info.st_dev,inode=info.st_ino)
                with patch.object(self.owner,'clone_frame',wraps=self.owner.clone_frame) as clone:
                    with self.assertRaises(NativeUIError):self.owner.read(foreign)
                    self.assertEqual(0,clone.call_count)

    def test_live_and_final_five_second_guards_precede_graph_cloning_on_cache_hit(self):
        value=self.stored();self.owner.read(value);self.allowed=False
        with self.assertRaises(NativeUIError):self.owner.read(value)
        self.allowed=True;original=self.owner.file;calls=[]
        def delayed(*args):
            original(*args);calls.append(True)
            if len(calls)==2:self.epoch+=5.001
        with patch.object(self.owner,'file',side_effect=delayed),patch.object(self.owner,'clone_frame',wraps=self.owner.clone_frame) as clone:
            with self.assertRaises(NativeUIError):self.owner.read(value)
            self.assertEqual(0,clone.call_count)

    def test_real_large_nested_original_keeps_fresh_graph_without_python_deepcopy(self):
        frame=dict(rows=[dict(sequence=i,events=[dict(kind='original',value=j) for j in range(20)]) for i in range(500)])
        value=self.owner.expand(self.owner.write(1,frame));raw=self.owner.path(value).read_bytes()
        with patch.object(assets,'deepcopy',wraps=deepcopy) as copied:
            started=time.monotonic()
            for _ in range(10):self.assertEqual(frame,self.owner.read(value))
            elapsed=time.monotonic()-started;self.assertEqual(0,copied.call_count)
        print('Actual Snapshot original bytes='+str(len(raw))+' fresh JSON reads=10 seconds='+str(round(elapsed,3)),flush=True)


if __name__=='__main__':unittest.main()
