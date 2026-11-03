"""Actual BoundAdapter/runtime constructors over explicit host producers.

No Native/Qt/device service executes. Candidate ZIP/tools, SDK process/session,
fresh app-file publication, render and virtual clocks are declared models.
Existing normal constructors/decoders and Emote resource owners execute.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'android/vr/pico/tests/device'))
import test_normal_scripts as normal

from adapters.android.adapter import ANDROID_CONTROL_COMMAND,ANDROID_CONTROL_CONTRACT
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.emote_stream_factory import FILES,script
from adapters.pico4.script_journey import PicoScriptJourney
from adapters.world_render_storage import receipt_file
from self_tests.pico_emote_stream_capacity_cycle_fixture import CapacityCycleModel
from self_tests.test_pico_emote_sources import BINDING


class FactoryModel(CapacityCycleModel):
    def __init__(self):
        self.normal=normal.PicoNormalScriptsTests(methodName='runTest');self.normal.setUp()
        temporary=self.normal.fixture.fixture.fixture.temporary
        temporary._finalizer.detach();temporary.cleanup=lambda:None
        self.normal_root=Path(temporary.name)
        super().__init__();self.roots.append(self.normal_root)
        self.adapter=self.normal.instance;self.sdk=self.normal.native;self.factories=[]
        self.runtime_calls=[];self.runtime_after_wire=self.runtime_corrupt=self.first_clock=self.first_guard=None
        self.before_runtime_process=None
        self.process_calls=0
        self.builder_calls=[];self.native_commands=[];self.normal_inputs=self.sdk.inputs
        self.sdk.target='actor-model';self.sdk.identity='31:actor-original'
        self.sdk.bridge_id=self.streams['actor'].self_id
        self.sdk.require_process_identity=lambda identity:self.normal.assertEqual(self.sdk.identity,identity)
        self.adapter.pico_configuration=(self.adapter.pico_configuration[0],self.actor_root)
        self.adapter._avatar_parent_store=lambda target,run:PrivateFeatureState(self.actor_root/('avatar-parent-owner-'+run+'.json'))
        self.adapter._script_paths=lambda target:(self.actor_root/'normal-script-state-cold.json',self.actor_root/'normal-script-ui-cold.json')
        self.adapter._emote_source_store=lambda target,role:PrivateFeatureState(self.actor_root/('emote-'+role+'.json'))
        journey=PicoScriptJourney(self.adapter)
        journey.state_path=lambda target:self.actor_root/'normal-script-state-cold.json'
        self.adapter._script_journey=lambda:journey
        self.sdk.epoch_milliseconds=lambda target:self.streams['actor'].epoch()
        process=self.sdk.process_state
        def current_process(target,package):
            self.process_calls+=1
            self.publish_runtime()
            if self.before_runtime_process is not None:
                callback,self.before_runtime_process=self.before_runtime_process,None;callback()
            return process(target,package)
        self.sdk.process_state=current_process
        self.sdk.execute_bytes=self.binary
        self.sdk.write_debug_app_file=self.write
        self.sdk.read_debug_app_file=self.read
        self._clock_patch=patch('adapters.common.time',SimpleNamespace(time=lambda:self.streams['actor'].epoch()/1000))
        self._clock_patch.start()
        owner=self.m.s.owner
        candidate=self.normal.fixture.fixture.record
        def source(role='primary',binding=None):
            base=dict(binding or BINDING)
            base.update(sourceRevision=candidate['sourceRevision'],artifactSha256=candidate['artifactSha256'])
            value=owner(role,binding=base);clock=value.monotonic;guard=value.guard
            def monotonic():
                if self.first_clock is not None:
                    callback,self.first_clock=self.first_clock,None;callback()
                return clock()
            def guarded():
                if self.first_guard is not None:
                    callback,self.first_guard=self.first_guard,None;callback()
                return guard()
            value.monotonic=monotonic;value.guard=guarded;return value
        self.m.s.owner=source

    def configure_capacity_native(self):
        super().configure_capacity_native()
        self.roles['actor']['adapter']=self.adapter
        self.roles['actor']['binding']['targetFingerprint']=hashlib.sha256(
            ('actor-model'+'\0'+str(self.adapter.pico_configuration)).encode()).hexdigest()
        self.publish_runtime()

    def publish_runtime(self):
        producer=self.streams['actor'];root=producer.sample.parent
        marker=dict(ANDROID_CONTROL_CONTRACT,processId=producer.pid)
        probe=dict(sampleEpochMs=producer.epoch(),control=ANDROID_CONTROL_CONTRACT,application=dict(running=True))
        ui=dict(schemaVersion=1,bridgeId=producer.self_id,generation=self.sdk.generation,
            processId=producer.pid,elapsedMs=100,updatedEpochMs=producer.epoch(),lastCommandSequence=0,
            open=False,ready=False,controls=[],featureControlsVersion=1)
        values={'control-marker':marker,'probe':probe,'ui-observation':ui,'ui-status':{}}
        for kind,value in values.items():
            path=root/Path(FILES[kind]).name;raw=json.dumps(value).encode()
            if self.runtime_corrupt is not None:raw=self.runtime_corrupt(kind,raw)
            path.write_bytes(raw);path.chmod(0o600)

    def binary(self,arguments,*,target,timeout):
        argv=shlex.split(arguments[1]);kinds=[kind for kind in FILES if argv[4]==script(kind)]
        if not kinds:return self.streams['actor'].execute_bytes(arguments,target=target,timeout=timeout)
        assert target=='actor-model' and argv[:4]==['run-as','org.overte.pico','sh','-c']
        self.publish_runtime()
        wire=subprocess.run(['sh','-c',argv[4],*argv[5:]],cwd=self.streams['actor'].root,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,check=False).stdout
        self.runtime_calls.append(dict(kind=kinds[0],wire=wire,timeout=timeout))
        return self.runtime_after_wire(wire) if self.runtime_after_wire is not None else wire

    def read(self,target,package,path,**options):
        # Cold controlled/UI bytes MUST use the actual fixed binary hook.
        assert path not in FILES.values(),'Unarchived cold runtime getter'
        actual=self.streams['actor'].root/path
        assert actual.is_file();return actual.read_text()

    def write(self,target,package,path,raw):
        assert target=='actor-model' and package=='org.overte.pico' and path==ANDROID_CONTROL_COMMAND
        command=json.loads(raw);self.native_commands.append(deepcopy(command));action=command['action']
        owner=self.adapter._emote_world_render_store(target,'actor').read()
        if action=='feature-world-render-observe':
            assert owner['capture']==command
            self.renderer.intents.append(deepcopy(command));self.renderer.send(command);self.storage.present=True
        elif action=='feature-world-render-storage':
            self.storage.send(command);receipt=self.scope_root/receipt_file(command['commandId'])
            self.inventory.issued[command['commandId']]=(command['requestId'],hashlib.sha256(receipt.read_bytes()).hexdigest())
        elif action=='feature-world-render-receipts':
            self.inventory.owner=deepcopy(owner);self.inventory.retired=not self.storage.present
            self.inventory.present=self.storage.present;self.inventory.callbacks=self.storage.callbacks
            self.inventory.png_bytes=len(self.renderer.raw) if self.storage.present else 0
            self.inventory.send(command)
        elif action=='feature-pico-world-model-draws-observe':self.models().send(command)
        else:raise AssertionError('Unselected modeled native action')

    def factory_capture(self,cycle,index=1):
        value=self.adapter._emote_stream_capture('primary-model','actor-model',cycle,index)
        self.captures.append(value)
        from adapters.pico4.emote_stream_factory import OWNED
        owner=[owner for owner in OWNED if owner.capture is value];assert len(owner)==1
        self.factories.append(owner[0]);return value,owner[0]

    def close(self):
        try:super().close()
        finally:
            self._clock_patch.stop();self.normal.doCleanups()
