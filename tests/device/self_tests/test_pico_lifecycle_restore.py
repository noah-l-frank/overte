"""One existing Lifecycle prefix through normal restore and process owners.

Python owners/storage/session/navigation are real. Native Qt/physics/domain/
OS observations remain explicit model seams, never device qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch

from adapters.pico4.lifecycle_close import run_close
from adapters.pico4.lifecycle_process import PicoLifecycleProcessRetirement,run_lifecycle_restart
from adapters.pico4.lifecycle_restore import PicoLifecycleRestore,PicoLifecycleRestoreSurface
from adapters.pico4.navigation import PicoNavigation
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.pico4.tablet_home import PicoTabletHome
from adapters.token_script_ui import TokenScriptUI
from adapters.normal_feature_state import PrivateFeatureState
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.chat_journey.source_bundles import prepare as bundle_parts
from adapters.script_journey.history import canonical
import hashlib
from self_tests import test_pico_lifecycle_close as close_fixture
from self_tests import test_pico_lifecycle_editor as editor_fixture
from self_tests import test_pico_lifecycle_process as process_fixture
from self_tests import test_pico_graphics_surface as surface_fixture
from self_tests.test_vr_graphics_subject import Boundary as SubjectBoundary
from self_tests.test_pico_openxr_adapter_session import FakeTransport
from feature_journeys.graphics_fixture import subject_ids


def disconnected(boundary):
    original=boundary.mutate
    def mutate(value):
        original(value);value['chatVersion']=3
        value['source'].update(openedCommandId='',retiredCommandId='')
        value['source']['session'].update(connected=False,domainSha256='',connectionBirth='',connectedEpochMs=0,mixerActive=False)
    boundary.mutate=mutate


class LifecycleRestoreJoinTests(unittest.TestCase):
    def setUp(self):
        self.inputs=[];self.destinations=[];self.baseline_before_inputs=None
        self.configured_scene='http://controlled.invalid/scene.json'
        original=editor_fixture.LifecycleEditorTests.joined
        original_make=editor_fixture.LifecycleEditorTests.make
        def initial_bridge(editor):
            if getattr(editor,'owner',None) is None:
                # Configure the fixture's original normal bridge before any
                # owner/journal exists, using the native navigation UUID form.
                self.assertFalse(editor.path.exists())
                bridge=str(uuid.UUID(editor.binding['sessionId']))
                editor.binding=editor.binding|dict(sessionId=bridge);editor.controls.instance=bridge;editor.field.instance=bridge
            return original_make(editor)
        def before_first_input(editor):
            joined=original(editor);self.joined,self.world,self.native,self.root=joined,joined.world,editor.native,editor.root
            # Configure this serverless model before its first original World
            # observation, using the existing normal-navigation fixture scope.
            self.native.drive.source['sceneUrl']=self.configured_scene
            self.helper=object.__new__(process_fixture.LifecycleProcessTests)
            self.helper.native=self.native;self.helper.new_native=None
            self.process=PicoLifecycleProcessRetirement(self.root/'lifecycle-process-owner.json',self.world.run,
                self.world.session.profile,lambda:True,self.world.lock,
                monotonic=lambda:self.native.clock,sleep=self.helper.sleep)
            self.helper.process=self.process
            save=self.process.save
            def preserve_failed_save(state):
                try:return save(state)
                except Exception as error:
                    # Diagnostic copies cannot qualify/replace the original
                    # process journal or provide another World observation.
                    scope=dict(role='lifecycle-process-failed-save',runId=self.world.run,binding=self.world.binding)
                    root=PrivateFeatureState(self.root/'restore-process-failed-originals.json')
                    reference,parts=bundle_parts(state,0,[])
                    value=dict(scope=scope,phase='reading',chunks=[],reference=reference,
                        exceptionType=type(error).__name__,exceptionMessage=str(error),
                        stateSha256=hashlib.sha256(canonical(state)).hexdigest())
                    root.write(value,None);history=ChatSourceChunks(root,scope)
                    for part in parts:
                        chunks=history.append(part,value['chunks']);updated=deepcopy(value);updated['chunks']=chunks
                        root.write(updated,value);value=updated
                    raise
            self.process.save=preserve_failed_save
            _feature,self.source=self.helper.features(self.native,123,'a'*32,1)
            boundary,self.domain=self.helper.domains(self.native,123,'9'*32,'1'*32,'2'*32,19000)
            disconnected(boundary)
            self.restore=PicoLifecycleRestore(self.process,joined,self.source,self.domain,
                self.root/'lifecycle-restore-owner.json',self.surface)
            self.restore.begin();self.baseline_before_inputs=deepcopy(self.process.state)
            self.assertFalse(self.world.state['attempts']);self.assertFalse(editor.transport.envelopes)
            return joined
        with patch.object(editor_fixture.LifecycleEditorTests,'make',initial_bridge),patch.object(editor_fixture.LifecycleEditorTests,'joined',before_first_input):
            self.fixture=close_fixture.LifecycleCloseTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def surface(self,intent,owns,lease,allow):
        outer=self
        class Native(surface_fixture.Boundary):
            def __init__(self):
                super().__init__();self.pid=123;self.bridge=outer.world.binding['sessionId']
                self.clock=outer.native.clock;self.before_send=None;self.before_controller=self.stream_intent=self.stream_publish=None
            @property
            def epoch(self):return outer.native.epoch()
            def snapshot(self):
                self.clock=outer.native.clock
                return super().snapshot()
            def bind_before_send(self,callback):
                assert self.before_send is None;self.before_send=callback
            def bind_controller_admission(self,callback,*,intent,before_publish):
                assert self.before_controller is None
                self.before_controller,self.stream_intent,self.stream_publish=callback,intent,before_publish
            def sleep(self,value):outer.native.sleep(value);self.clock=outer.native.clock
            def controller(self,operation):
                self.before_controller(operation)
                outer.world.session.stage(outer.world.identity,operation,dict(holdMilliseconds=1000),
                    intent=self.stream_intent,before_publish=self.stream_publish)
                self.opened=operation=='tablet.open';self.revision+=1
                outer.native.ui.shown=self.opened;outer.native.ui.home=True
            def send(self,command):
                self.before_send(deepcopy(command));self.intents.append(dict(control=command['controlId']))
                result=super().send(command);outer.inputs.append(deepcopy(command))
                if command['controlId']=='navigation.address':
                    outer.native.ui.raised=self.focused
                    if command['action']=='submit':
                        # Model the existing AddressManager path parser's actual
                        # normal-field input, not an expected pose in a receipt.
                        path=self.entered[-1];point,rotation=path[1:].split('/')
                        point=[float(value) for value in point.split(',')]
                        rotation=[float(value) for value in rotation.split(',')]
                        outer.native.drive.source['feetPosition']=point
                        outer.native.drive.source['bodyPosition']=[point[0],point[1]+1,point[2]]
                        outer.native.drive.source['orientation']=rotation
                        outer.native.ui.shown=False;outer.native.ui.home=True;outer.destinations.append(path)
                return result
        native=Native();self.navigation_native=native
        transport=outer.world.session.transport;previous=transport.stage
        def stage(envelope,profile,*,before_publish=None):
            if envelope['commands'][0]['operation'] in ('tablet.open','tablet.close'):
                return FakeTransport.stage(transport,envelope,profile,before_publish=before_publish)
            return previous(envelope,profile,before_publish=before_publish)
        transport.stage=stage
        identity=dict(schemaVersion=1,sourceRevision=self.world.binding['sourceRevision'],
            artifactSha256=self.world.binding['artifactSha256'],installedCandidateVerified=True)
        navigation=PicoNavigation(native,self.root/'restore-navigation.json',identity,self.world.identity,
            self.native.drive.source['sceneUrl'],monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        route=TokenScriptUI(PicoScriptIO(navigation),monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        subject=SubjectBoundary();subject.source['sceneUrl']=self.native.drive.source['sceneUrl']
        subject.source['absentIds']=list(subject_ids(self.world.run).values())
        original=subject.send
        def send(request):
            subject.epoch=self.native.epoch()
            actual=self.native.drive.source
            subject.source['avatarPose']=dict(feetPosition=deepcopy(actual['feetPosition']),
                orientation=deepcopy(actual['orientation']),modelScale=actual['modelScale'])
            original(request);subject.sample.update(processId=123)
        reader=subject.reader(require_framework=True);reader.pid=123;reader.send=send
        reader.clock_ms=self.native.epoch;reader.monotonic=lambda:self.native.clock;reader.sleep=self.native.sleep
        home=surface_fixture.HomeSource(native)
        return PicoLifecycleRestoreSurface(route,reader,PicoTabletHome(home,home.stage),self.world.run,intent,owns,lease,allow)

    def test_original_begin_existing_editor_pending_close_prefix_location_restore_and_process_restart(self):
        run_close(self.fixture.owner);self.world.world_input();self.world.release()
        result=self.restore.restore(self.fixture.owner)
        self.assertEqual(0.,result['worldDisplacement']);self.assertEqual(2,result['worldAttempts'])
        self.assertTrue(result['processShutdownPrepared']);self.assertFalse(result['completeLifecycle'])
        self.assertEqual([self.restore.state['restorePath']],self.destinations)
        self.assertEqual(self.baseline_before_inputs['originalWorld'],self.process.state['originalWorld'])
        before=len(self.world.state['frames']);self.assertLessEqual(before,128)
        def launch():
            self.helper.new_process(inputs=False);disconnected(self.helper.new_domain_boundary)
            self.helper.new_native.drive.source['sceneUrl']=self.configured_scene
            return dict(launched=True)
        result=run_lifecycle_restart(self.process,lambda:self.process.require_stop_ready(self.source),lambda:self.source,
            lambda:(setattr(self.native,'alive',False) or dict(stopped=True)),
            lambda:dict(running=self.native.alive,identity=self.world.identity if self.native.alive else None),
            launch,lambda:deepcopy(process_fixture.NEW_BINDING),lambda:self.helper.observe())
        self.assertTrue(result['processOwnedScopesRetired']);self.assertEqual(before,len(self.world.state['frames']))
        self.assertEqual(2,result['worldAttempts']);self.assertTrue(result['journalsRetained'])


if __name__=='__main__':unittest.main()
