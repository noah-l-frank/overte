"""Real cold constructors, original Sources/Inputs, explicit SDK/Qt/Rig leaves.

The existing candidate fixtures and native producers are host models. Fixed
binary scripts really execute against separately retained private file roots.
No Android device, Qt renderer or native publisher executes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

from adapters.android.adapter import ANDROID_CONTROL_COMMAND,ANDROID_CONTROL_CONTRACT
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.emote_cold_factory import FILES,script,create_cold_common
from adapters.pico4.script_journey import PicoScriptJourney
from feature_journeys.phase_fixture import PhaseFixtureReader
from self_tests.pico_emote_stream_factory_fixture import FactoryModel,normal
from self_tests.pico_emote_capacity_publisher_model import NativePublisherModel


class ColdModel(FactoryModel):
    def __init__(self):
        super().__init__();self.primary_normal=normal.PicoNormalScriptsTests(methodName='runTest')
        self.primary_normal.setUp();temporary=self.primary_normal.fixture.fixture.fixture.temporary
        temporary._finalizer.detach();temporary.cleanup=lambda:None;self.roots.append(Path(temporary.name))
        # Both actual candidate admissions must see the SAME final unchanged
        # test environment. A second fixture's state-dir env cannot be swapped
        # underneath an earlier candidate seal and then treated as valid.
        with patch.object(normal.adapter,'AdbTransport',return_value=self.sdk):
            self.adapter=self.normal.fixture.instance()
        self.adapters={'primary':self.primary_normal.instance,'actor':self.adapter}
        self.sdks={'primary':self.primary_normal.native,'actor':self.sdk}
        self.cold_calls=[];self.getter_fault=None;self.leaves=None;self.runtimes=None
        self.clock_hook=None;self.process_hook=None
        self.cold_rows={}
        for role in ('primary','actor'):
            adapter=self.adapters[role];sdk=self.sdks[role];producer=self.streams[role]
            root=self.m.s.root if role=='primary' else self.actor_root
            sdk.target=role+'-model';sdk.identity='31:'+('original' if role=='primary' else 'actor-original')
            sdk.bridge_id=producer.self_id;sdk.require_process_identity=lambda identity,sdk=sdk: self.normal.assertEqual(sdk.identity,identity)
            adapter.pico_input_session=lambda target,sdk=sdk:sdk
            adapter.pico_configuration=(adapter.pico_configuration[0],root)
            adapter._script_paths=lambda target,root=root:(root/'normal-script-state-cold.json',root/'normal-script-ui-cold.json')
            adapter._emote_source_store=lambda target,r,root=root:PrivateFeatureState(root/('cold-emote-'+r+'.json'))
            adapter._avatar_parent_store=lambda target,run,root=root:PrivateFeatureState(root/('avatar-parent-owner-'+run+'.json'))
            journey=PicoScriptJourney(adapter);adapter._script_journey=lambda journey=journey:journey
            sdk.epoch_milliseconds=lambda target,producer=producer:producer.epoch()
            original_process=sdk.process_state
            def process(target,package,original=original_process):
                if self.process_hook is not None:self.process_hook()
                return original(target,package)
            sdk.process_state=process
            sdk.execute_bytes=lambda args,role=role,**kw:self.cold_binary(role,args,**kw)
            sdk.write_debug_app_file=lambda target,package,path,raw,role=role:self.cold_write(role,target,package,path,raw)
            sdk.read_debug_app_file=lambda target,package,path,role=role,**kw:self.cold_read(role,target,package,path,**kw)
            record=(self.primary_normal if role=='primary' else self.normal).fixture.fixture.record
            binding=dict(sourceRevision=record['sourceRevision'],artifactSha256=record['artifactSha256'],
                processIdentity=sdk.identity,sessionId=producer.self_id,generation=0,
                targetFingerprint=hashlib.sha256((sdk.target+'\0'+str(adapter.pico_configuration)).encode()).hexdigest())
            phase=self.m.s.phase if role=='primary' else PhaseFixtureReader(self.m.s.phase.client,self.m.s.phase.run,'emotes',
                epoch_ms=lambda:self.m.s.epoch,monotonic=lambda:self.m.s.clock)
            self.cold_rows[role]=dict(adapter=adapter,target=sdk.target,binding=binding,phase=phase,
                lock=self.m.s.lock if role=='primary' else self.actor_lock,subject=producer.subject_id)
        self.m.s.widget.instance=self.streams['primary'].self_id
        self.m.s.widget.tablet=False

    def cold_read(self,role,target,package,path,**options):
        assert path not in FILES.values(),'A cold source escaped raw admission'
        value=self.streams[role].root/path;assert value.is_file();return value.read_text()

    def publish_cold_runtime(self,role):
        producer=self.streams[role];root=producer.sample.parent
        values={'marker':dict(ANDROID_CONTROL_CONTRACT,processId=producer.pid),
            'probe':dict(sampleEpochMs=producer.epoch(),control=ANDROID_CONTROL_CONTRACT,application=dict(running=True)),
            'observation':dict(self.m.s.widgets(),featureControlsVersion=1)}
        if role=='actor':
            values['observation']=dict(schemaVersion=1,bridgeId=producer.self_id,generation=self.sdks[role].generation,
                processId=producer.pid,elapsedMs=100,updatedEpochMs=producer.epoch(),lastCommandSequence=0,
                open=False,ready=False,controls=[],featureControlsVersion=1)
        for kind,value in values.items():
            path=self.streams[role].root/FILES[kind];path.write_text(json.dumps(value));path.chmod(0o600)

    def cold_binary(self,role,arguments,*,target,timeout,check=False):
        assert check is False and target==role+'-model';argv=shlex.split(arguments[1])
        kinds=[kind for kind in FILES if argv[4]==script(kind)]
        if not kinds:return self.streams[role].execute_bytes(arguments,target=target,timeout=timeout)
        self.publish_cold_runtime(role)
        wire=subprocess.run(['sh','-c',argv[4],*argv[5:]],cwd=self.streams[role].root,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,check=False).stdout
        self.cold_calls.append(dict(role=role,kind=kinds[0],wire=wire))
        return self.getter_fault(wire) if self.getter_fault is not None else wire

    def cold_write(self,role,target,package,path,raw):
        assert target==role+'-model' and package=='org.overte.pico'
        command=json.loads(raw)
        if path!=ANDROID_CONTROL_COMMAND:
            assert role=='primary' and path.endswith('navigation-ui-command.json')
            original=self.m.input.owner;self.m.input.owner=self.parent.inputs
            try:
                # Actual NativeNavigationIO already checked the exact command
                # before entering this declared Qt delivery leaf. The older
                # fixture helper reconstructs a DIFFERENT command from a new
                # sample; do not pretend that reconstruction is the writer.
                self.m.input.original.navigation.io=SimpleNamespace(_before_send=lambda command:None)
                self.m.input.input(command['controlId'],command['action'],reference=__import__(
                    'adapters.pico4.normal_emote',fromlist=['project']).project(self.m.s.widgets()),
                    direction=command.get('direction'))
            finally:self.m.input.owner=original
            value=dict(schemaVersion=1,bridgeId=self.streams[role].self_id,commandId=command['commandId'],
                sequence=command['sequence'],performed=True,error='',processId=31,updatedEpochMs=self.m.s.epoch)
            output=self.streams[role].root/FILES['status'];output.write_text(json.dumps(value));output.chmod(0o600);return
        if command['action']=='feature-pico-remote-avatar-stream-control':
            producer=self.streams[role]
            if command['operation']=='arm':
                publisher=object.__new__(NativePublisherModel);self.publishers[role]=publisher;self.publisher_models.append(publisher)
                NativePublisherModel.__init__(publisher,producer.sample.parent,self.cycle.capacity.guard)
            elif command['operation']=='stop':self.publishers[role].stop()
            else:self.publishers[role].drain()
            producer.send(command);return
        assert role=='primary'
        if self.leaves is None:self.leaves=self.m.s.readers()
        selected={'feature-script-roots-observe':('roots',0),'feature-script-observe':('script',1),
            'feature-animation-inventory-observe':('inventory',2),'feature-native-observe':('native',3)}
        kind,index=selected[command['action']];leaf=self.leaves[index];leaf.send(command)
        output=self.streams[role].root/FILES[kind];output.write_text(leaf.original());output.chmod(0o600)

    def cold(self,*,canonical=False):
        if canonical:
            cycle,runtimes=self.adapters['primary']._emote_cold_common('primary-model',self.cold_rows,
                self.m.s.phase,self.m.s.root,self.m.s.lock)
        else:
            cycle,runtimes=create_cold_common(self.adapters['primary'],'primary-model',self.cold_rows,self.m.s.phase,
                self.m.s.root,self.m.s.lock,monotonic=self.now,sleep=self.m.sleep)
        self.cycle=cycle;self.parent=cycle.parent;self.runtimes=runtimes;self.capacity=cycle.capacity
        self.m.s.store=self.parent.source.store
        for role in self.streams:self.streams[role].native=runtimes[role].native
        self.m.input.owner=self.parent.inputs;self.m.input.store=self.parent.inputs.store
        self.adapters['primary'].pico_input_session=lambda target:self.m.input.controller_session
        return cycle

    def now(self):
        if self.clock_hook is not None:self.clock_hook()
        return self.m.s.clock

    def close(self):
        try:super().close()
        finally:self.primary_normal.doCleanups()
