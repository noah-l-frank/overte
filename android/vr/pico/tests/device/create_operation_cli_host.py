"""Existing Android operation CLI around original Create Native/SDK models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import uuid
ROOT=Path(__file__).resolve().parents[5]
sys.path[:0]=[str(ROOT/'tests/device'),str(Path(__file__).resolve().parent)]
from adapters.android import adapter as android
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.create_journey import PicoCreateJourney
from adapters.pico4.create_operation_owner import PicoCreateOperationOwner
from adapters.script_journey.lock import ScriptSourceLock
import test_create_journey as original
from test_create_peer_source import native_primary

fault=sys.argv[sys.argv.index('--model-fault')+1] if '--model-fault' in sys.argv else 'normal'
area=Path(sys.argv[sys.argv.index('--model-root')+1]);phase_store=PrivateFeatureState(area/'phase-publication.json')
class Retained(tempfile.TemporaryDirectory):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self._finalizer.detach()
    def cleanup(self):pass
tempfile.TemporaryDirectory=Retained;tempfile.tempdir=str(area)
args=SimpleNamespace(kind='pico',native_binding=True,action='operation-host',target='host-create-candidate',operation=None,arguments='{}')


class ModelOwner(PicoCreateOperationOwner):
    def __init__(self,adapter,target,run,url):
        super().__init__(adapter,target,run,url);self.fixture=adapter.fixture;self.world=None;self.world_previous=None
    def update(self):
        if self.world is None:return
        b=self.fixture.b;value=dict(clock=b.now(),rows=deepcopy(b.rows),births=deepcopy(b.domain_births),phase=self.fixture.journal.phase(original.RUN,uuid.uuid4().hex))
        with ScriptSourceLock(self.world.path.with_name('fixture-replica.lock')).held():self.world.write(value,self.world_previous);self.world_previous=deepcopy(value)
    def component(self,*arguments,**options):
        result=super().component(*arguments,**options);self.update()
        if fault=='lost-act' and arguments[0]=='act' and arguments[1]['verb']=='model-create':os._exit(2)
        return result
    def end(self,value):
        result=super().end(value)
        if fault=='lost-end':os._exit(2)
        return result
    def start_peer(self,spec,budget_value,*,entry=None):
        self.world=PrivateFeatureState(Path(spec['artifactRoot'])/'replica-model.json');self.update()
        return super().start_peer(spec,budget_value,entry=Path(__file__).with_name('create_operation_peer_host.py'))


class ModelAdapter(android.AndroidAdapter):
    def __init__(self):
        self.kind='pico';self.profile=android.PROFILES['pico'];self.factories=0
        fixture=self.fixture=original.CreateJourneyTests();fixture._before_prepare=lambda:native_primary(fixture)
        make=fixture.make
        def deferred():
            root=make();root.invoke=lambda operation,values=None:None if operation=='prepare' else PicoCreateJourney.invoke(root,operation,values);return root
        fixture.make=deferred;fixture.setUp();self.pico_configuration=fixture.adapter.pico_configuration
        journal=fixture.journal;produce=journal.phase
        def phase(run,nonce):
            publication=phase_store.read();row=journal.runs[run]
            journal.phase_instance=publication['instance'];row.update(phaseCreatedEpochMs=publication['createdEpochMs'],phaseActivations=deepcopy(publication['activations']))
            if publication['activations']:
                last=publication['activations'][-1];row.update(ticket=last['ticket'],activeEpochMs=last['activatedEpochMs'],stimulus=deepcopy(last['stimulus']))
            return produce(run,nonce)
        journal.phase=phase
        trace=PrivateFeatureState(area/'model-host.json');trace.write(dict(pid=os.getpid(),stateRoot=str(fixture.path),factoryCalls=0),None)
    def __getattr__(self,name):return getattr(self.fixture.adapter,name)
    def _create_journey(self,target,run):
        self.factories+=1;fixture=self.fixture;parent=PicoCreateJourney(self,target,run,fixture.source());fixture.root=fixture.b.root=parent
        trace=PrivateFeatureState(area/'model-host.json');trace.write(dict(pid=os.getpid(),stateRoot=str(fixture.path),factoryCalls=self.factories),trace.read());return parent
    def _create_operation_owner(self,target,run,url):return ModelOwner(self,target,run,url)
    def invoke(self,target,operation,values):
        if operation=='app.process':return dict(running=True,identity=str(os.getpid()))
        if operation=='app.foreground':return dict(foreground=True)
        raise AssertionError('No unsupported product operation in declared host model')


class Binding:
    @staticmethod
    def create_adapter(_args,_base):return ModelAdapter()


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
    (area/'host-loaded-sources.json').write_text(__import__('json').dumps(rows,sort_keys=True))
atexit.register(source_receipt)

if __name__=='__main__':
    android.cli=lambda argv=None:(args,Binding)
    try:raise SystemExit(android.main([]))
    except Exception:
        import traceback;traceback.print_exc();raise SystemExit(2)
