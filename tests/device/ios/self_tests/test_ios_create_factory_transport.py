"""All normal recipes through real runtime/UI/token/HTTP/AFC factories.

Qt/native/product/renderer are modeled SDK boundaries. No parts/ensure/action
or IOSCreateUI method is replaced. Separate whole tests qualify images/peers.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.witness import Client
from feature_journeys.scenarios import SCENARIOS
from feature_journeys.phase_fixture import PhaseFixtureReader
from fixture.create_rez_authority import CreateRezControl
from ios.adapters.create_product_state import project
from ios.adapters.create_runtime import IOSCreateRuntime
from ios.adapters.create_world_input import CreateWorldInput
from ios.self_tests.create_product_controls_fixture import ProductControls
from ios.self_tests.create_whole_fixture import ComposedCreate
from ios.self_tests import test_ios_create_controls as transport
from ios.self_tests import test_ios_create_rez_client as authority
from ios.self_tests import test_ios_installed_code as installed
from ios.self_tests.test_ios_create_files import BINDING,URL
from ios.self_tests.test_ios_create_state import RUN


class CreateFactoryTransportTests(unittest.TestCase):
    def setUp(self):
        buffers={}
        getter=None if self._testMethodName=='test_original_legacy_state3_cannot_start_setup_or_deliver_any_input' else lambda root:buffers.get('create.property-search','')
        self.f=ComposedCreate(self,property_search=getter);f=self.f
        phase_clock=patch('ios.adapters.create_runtime.PhaseFixtureReader',side_effect=lambda client,run,area:PhaseFixtureReader(
            client,run,area,epoch_ms=f.clock.epoch,monotonic=lambda:f.clock.clock))
        phase_clock.start();self.addCleanup(phase_clock.stop)
        world_clock=patch('ios.adapters.create_runtime.CreateWorldInput',side_effect=lambda *args,**kwargs:CreateWorldInput(
            *args,**kwargs,epoch_ms=f.clock.epoch,monotonic=lambda:f.clock.clock))
        world_clock.start();self.addCleanup(world_clock.stop)
        web=f.scope.web.read;painted=[False]
        def rendered(*args):
            if f.domain.running and not painted[0]:f.domain.paint();painted[0]=True
            return web(*args)
        f.scope.web.read=rendered
        self.t=transport.IOSCreateControlsTests();self.t.setUp();self.addCleanup(self.t.doCleanups);t=self.t
        self.controls=ProductControls(f,t.native.instance,texts=buffers);t.widget=self.controls;t.marker=2
        t.native.epoch=f.clock.epoch;native=t.flow.io.original.native;native.native_epoch_ms=f.clock.epoch
        observed=t.native.observed
        def actual():t.native.qt.opened=f.product.value['source']['tabletShown'];return observed()
        t.native.observed=actual
        self.authority=authority.CreateRezClientTests();self.authority.setUp();self.addCleanup(self.authority.doCleanups);a=self.authority
        a.harness.binding['domainId']=f.product.value['source']['domainId'];a.config['domainId']=a.harness.binding['domainId']
        a.control=CreateRezControl(a.harness.owner(),PrivateFeatureState(a.path/'factory-control.json'))
        handle=a.control.handle
        def transition(query):
            result=handle(query)
            # Replication is derived from the genuine normal settings API rows,
            # independently of the requested value or HTTP acknowledgment.
            row=next(row for row in result['standardPermissions'] if row['permissions_id']=='anonymous')
            f.product.value['source'].update(canRez=row['id_can_rez'],canRezTmp=row['id_can_rez_tmp']);return result
        a.control.handle=transition
        f.h.ah.file_boundary.clock=f.h.h.sdk.tick
        observer=SimpleNamespace(create_files=lambda _clock:f.h.ah.file_boundary.native(),pointer_state=lambda _clock:f.pointer)
        f.ui.click=f.h.ah.normal.click
        sources=dict(binding=BINDING,check=lambda:True,roots=SimpleNamespace(read=lambda _after:{'source':{'defaultScriptsUrl':f.source.scripts_root}}),
            observer=observer,clock_source=None,native_bound=f.scope.native,create=f.source.readers['create'],work=f.source.readers['work'],
            script_work=f.source.readers['worker'],domain=f.source.readers['domain'],geometry=f.geometry,native=native,ui=f.ui)
        prepared=installed.InstalledCodeTests();prepared.setUp();self.addCleanup(prepared.doCleanups)
        prepared.scope=dict(sourceRevision=BINDING['sourceRevision'],artifactSha256=BINDING['artifactSha256'],sessionId='actual-peer',generation=1,targetFingerprint='a'*64)
        prepared.binding=prepared.make();prepared.active()
        class Runtime(IOSCreateRuntime):
            def state_path(_self,_selector):return f.root/'session.json'
            def _create_sources(_self,_selector,_lock):return sources
            def _create_source_owner(_self,_selector,_run,_role,_phase,_roots,_lock):return f.source
            def _create_marker(_self,*_args,**_kwargs):return f.scope
            def _create_sample(_self,_selector,_run,_role,request,_root,_lock):return f.sample(request)
            def _existing(_self,_selector):return None,prepared.scope['sessionId'],{}, {},deepcopy(prepared.scope)
            @contextmanager
            def existing_input_session(_self,_selector):yield
        self.runtime=Runtime(SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda *_args:prepared.make()))
        self.client=Client(URL.split('/runs/')[0],'r'*64);self.client.request=lambda path,**kwargs:f.journal.phase(RUN,kwargs['phase_nonce']);f.source.phase.client=self.client
        self.flow=self.runtime._create_feature('primary',RUN,role='primary',client=self.client,settings=dict(artifactRoot=str(f.root),
            imagePolicy=dict(source='world-render-target',marker=[85,87,245,127],subject=[0,170,640,400]),actorTarget='actor',rezAuthority=a.config))
        self.flow.lock=self.flow.primary_lock=f.lock;self.flow.phase=f.source.phase
        self.flow.epoch_ms=f.clock.epoch;self.flow.monotonic=lambda:f.clock.clock;self.flow.sleep=f.domain.sleep
        held=self.flow.held
        @contextmanager
        def diagnostic():
            error=None
            with held():
                try:yield
                except Exception as caught:error=caught
            if error is not None:raise error
        self.flow.held=diagnostic
    def test_original_legacy_state3_cannot_start_setup_or_deliver_any_input(self):
        # This is a genuine older native SDK shape, not a changed observation
        # floor. Its original empty tree, PNG and clocks remain independently
        # validated; only the hidden draft proof is unavailable.
        del self.f.product.search_original
        with self.flow.held():
            parts,_status=self.flow.ensure()
            self.assertEqual(3,parts['source'].frames[-1]['originals']['createAfter']['iosCreateStateVersion'])
            with self.assertRaises(NativeUIError):self.flow.prepare_inputs(parts)
        self.assertEqual([],self.controls.inputs);self.assertFalse(self.f.domain.running)

    def test_entire_21_step_controller_uses_runtime_factories_durable_native_tokens_and_actual_original_effects(self):
        f=self.f;flow=self.flow
        with flow.held():flow.ensure()
        sequence=0
        for index,step in enumerate(SCENARIOS['create']['steps']):
            query=f.h.ah.query(index);f.journal.activate(RUN,query['ticket'],query['verb'],query['inputs'])
            flow.act(query)
            if set(step['evidence']) & {'image','changed'}:f.render(query['ticket'])
            observed=flow.observe(dict(contractVersion=16,runId=RUN,afterSequence=sequence));sequence=observed['sequence']
            self.assertEqual(step['state'],observed['state'],step['verb'])
            with flow.held():
                flow.load();parts=flow.parts();actions=parts['actions'];packet=actions.read()
                actual=project(packet,RUN,[row['id'] for row in actions.state['owned']],voxel_baseline=actions.state['voxelBaseline'])
                self.assertEqual(step['state'],actual,step['verb'])
        self.assertGreater(len(self.controls.inputs),100)
        with flow.held():
            actions=flow.parts()['actions'];self.assertEqual(21,len(actions.state['calls']));self.assertEqual(5,len(actions.state['owned']))
            originals=actions.inputs.state['calls'];self.assertEqual(21,len(originals))
            self.assertTrue(all(event['phase']=='observed' for call in originals for event in call['events']))
        self.assertTrue(any(command.get('operation')=='edit' for command in self.t.native.commands))
        from ios.adapters.create_api_clock import scope
        f.journal.activate(RUN,'2'*32,'cleanup',{})
        with scope(lambda:f.clock.clock),flow.held():
            parts=flow.parts();original=flow.clean_local(parts,flow.phase.read())
            measured=parts['retirement'].validate_original(original)
            self.assertEqual([],measured['public']['resources']);self.assertEqual(5,len(parts['actions'].state['owned']))
            self.assertEqual(14,len(parts['retirement'].all_samples()))
            self.assertTrue(all(owner.frame_owner.store.read()['phase']=='released' for owner in parts['retirement'].all_samples()))
        self.assertFalse(f.domain.running);self.assertFalse(f.items)



if __name__=='__main__':unittest.main()
