"""Existing Lifecycle normal graph and unchanged Common peer waits together.

Only the explicit target/native/Qt/domain models are supplied by the fixture.
The original World/Restore/Source3/operations/session/journey code executes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_world import PicoLifecycleWorld
from adapters.pico4.lifecycle_back import PicoLifecycleBack
from adapters.pico4.lifecycle_join import PicoLifecycleXJoin
from adapters.pico4.lifecycle_process import PicoLifecycleProcessRetirement
from adapters.pico4.lifecycle_restore import PicoLifecycleRestore
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.engine import Journey
from self_tests import test_pico_lifecycle_process as process_models
from self_tests.test_pico_lifecycle_restore import disconnected


class CanonicalLifecycleOperationGraph:
    def __init__(self,case,stage):
        self.case,self.stage,self.target=case,stage,stage.editor
        target=self.target;adapter,native,lock,root=target.adapter,target.native,target.lock,target.root
        observer=adapter._native_feature_observer(target.target)
        self.world=PicoLifecycleWorld(adapter._lifecycle_ui_source(target.target,source_lock=lock),
            adapter._lifecycle_gesture_source(target.target,source_lock=lock),
            adapter._lifecycle_drive_source(target.target,source_lock=lock),target.session,
            root/'lifecycle-world-owner.json',target.run,target.binding,observer.guard,lock,
            monotonic=lambda:native.clock,sleep=native.sleep)
        back=PicoLifecycleBack(adapter._lifecycle_ui_source(target.target,source_lock=lock),target.session,
            root/'lifecycle-x-back-owner.json',target.run,target.binding,observer.guard,
            monotonic=lambda:native.clock,sleep=native.sleep,source_lock=lock)
        self.joined=PicoLifecycleXJoin(self.world,back,root/'lifecycle-x-join.json')
        self.process=PicoLifecycleProcessRetirement(root/'lifecycle-process-owner.json',target.run,
            target.session.profile,observer.guard,lock,monotonic=lambda:native.clock,sleep=native.sleep)
        holder=SimpleNamespace(native=native,process=self.process,sleep=native.sleep)
        boundary,domain=process_models.LifecycleProcessTests.domains(holder,native,123,'9'*32,'1'*32,'2'*32,19000)
        disconnected(boundary)
        def unavailable(*_args,**_kwargs):raise NativeUIError('No restore surface is exercised by this two-action prefix')
        self.restore=PicoLifecycleRestore(self.process,self.joined,observer,domain,root/'lifecycle-restore-owner.json',unavailable)
        self.restore.begin()
        self.source=adapter._lifecycle_observation_readonly_begin(target.target,target.run,restore=self.restore,editor=target.owner)
        phases=PhaseFixtureReader(stage.client,target.run,'lifecycle-input',epoch_ms=native.epoch,monotonic=lambda:native.clock)
        self.operations=adapter._lifecycle_primary_operations(target.target,target.run,source=self.source,phases=phases)
        self.session_module=self.load_session(case,root)
        self.session=self.session_module.OverteSession()
        self.calls=[];self.actor_samples=[]
        def operation(name,fields):
            self.calls.append((name,deepcopy(fields)));return self.operations.invoke(name,fields)
        active=patch.object(self.session_module,'operation',operation);active.start();case.addCleanup(active.stop)
        def invoke(name,fields):
            _prefix,area,kind=name.split('.');return self.session.feature_operation(area,kind,fields)
        def witness():
            stage.sample();value=stage.client.observe()
            # Retain the complete actual journal response before Common can
            # accept or reject it. No desired/Primary fact crosses to Actor.
            with self.operations.lock.held():self.operations.archive(dict(independentJournal=deepcopy(value)))
            self.actor_samples.append(deepcopy(value['entries'][-1]));return value
        def activate(*_args,**_kwargs):raise AssertionError('This prefix activates the actual fixture explicitly')
        def forbidden(*_args,**_kwargs):raise AssertionError('No artifact/public completion is supplied by this source prefix')
        def continuity(*_args):
            observer.guard()
            if stage.process is not None:stage.process.guard()
        self.journey=Journey('lifecycle-input',target.run,phases.fixture_url,invoke=invoke,witness=witness,
            activate=activate,read_artifact=forbidden,image_policy={},continuity=continuity,
            monotonic=lambda:native.clock,epoch_ms=native.epoch,sleep=native.sleep,report=forbidden)

    @staticmethod
    def load_session(case,root):
        path=Path(__file__).resolve().parents[1]/'overte_session.py'
        environment=dict(OVERTE_DEVICE_ADAPTER_MANIFEST=str(root/'unused-adapter.json'),
            OVERTE_DEVICE_TARGET_SELECTOR='unit-lifecycle-canonical-common-peer',OVERTE_DEVICE_ARTIFACT_DIR=str(root))
        saved=sys.modules.pop('module_support',None)
        try:
            with patch.dict('os.environ',environment):
                spec=importlib.util.spec_from_file_location('canonical_lifecycle_common_session',path)
                module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        finally:
            sys.modules.pop('module_support',None)
            if saved is not None:sys.modules['module_support']=saved
        return module
