"""Existing common Journey -> OverteSession -> Pico router -> original SDKs.

Candidate/package/GUI/OS/GPU/fixture transport boundaries are synthetic. The
normal inputs, schemas, independent source readers, immutable files, common
engine, public router and final owner/actor retirement execute unchanged.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import copy,deepcopy
import importlib
import os
import secrets
import unittest
from unittest.mock import patch
import uuid

from adapters import owned_observer
from adapters.pico4 import feature_observer
from adapters.graphics_journey.fixture import GraphicsFixtureReader
from feature_journeys import engine
from feature_journeys.evidence import read_private_artifact
from feature_journeys.graphics_fixture import PICO_PROFILE
from feature_journeys.graphics_resources import GraphicsResources
from feature_journeys.stereo_graphics_evidence import SURFACE_PROFILE
from feature_journeys.witness import Journal
from self_tests.test_pico_graphics_public_binding import PublicFixture
from self_tests.test_pico_graphics_feature_stereo import RUN,TICKET


class PicoGraphicsCommonEngineTests(unittest.TestCase):
    def setUp(self):
        self.fixture=PublicFixture(self);self.model=self.fixture.model;m=self.model
        self.manifest=m.root/'synthetic-session-manifest.json'
        self.enterContext(patch.dict(os.environ,dict(OVERTE_DEVICE_ADAPTER_MANIFEST=str(self.manifest),
            OVERTE_DEVICE_TARGET_SELECTOR='owned',OVERTE_DEVICE_ARTIFACT_DIR=str(m.root/'artifacts'))))
        self.support=importlib.import_module('module_support');session_module=importlib.import_module('overte_session')
        self.enterContext(patch.object(self.support,'MANIFEST',self.manifest))
        self.enterContext(patch.object(self.support,'TARGET','owned'))
        self.enterContext(patch.object(self.support,'ARTIFACT_DIR',m.root/'artifacts'))
        self.enterContext(patch.object(self.support,'invoke',side_effect=self.adapter_rpc))
        self.session=session_module.OverteSession();self.calls=[]
        m.provider=GraphicsResources(m.client.url,clock_ms=lambda:m.native.epoch);m.provider.provision(RUN,profile=PICO_PROFILE)
        m.journal=Journal(clock=lambda:m.native.epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):m.journal.register('graphics')
        m.client.graphics_instance=m.provider.instance;m.client.graphics_previous=None
        m.source=GraphicsFixtureReader(m.client,RUN,epoch_ms=lambda:m.native.epoch)
        self.actor_client=copy(m.client);self.actor_client.token='c'*64;self.actor_client.graphics_previous=None
        def actor_status():
            value=m.provider.snapshot(RUN,uuid.uuid4().hex);self.actor_client.graphics_previous=deepcopy(value);return value
        self.actor_client.graphics_status=actor_status
    def adapter_rpc(self,manifest,target,operation,arguments):
        self.assertEqual(self.manifest,manifest);self.assertEqual('owned',target);self.calls.append(operation)
        return self.fixture.original.invoke(target,operation,arguments)
    def activate(self,ticket,verb='baseline',inputs=None):
        m=self.model;m.provider.activate(RUN,ticket);m.journal.activate(RUN,ticket,verb,inputs)
        m.deliver_codes(ticket)
    def invoke(self,operation,fields):
        _prefix,area,kind=operation.split('.')
        return self.session.feature_operation(area,kind,fields)
    def witness(self):
        self.fixture.original._graphics_journey()._graphics_feature('owned',RUN,role='actor',client=self.actor_client).publish()
        return self.model.journal.snapshot(RUN)
    def test_common_engine_all_checkpoints_and_actual_actor_loop_complete_final_retirement(self):
        m=self.model;reports=[];first=True;real_token=secrets.token_hex
        def token(size):
            nonlocal first
            if first:first=False;return TICKET
            return real_token(size)
        journey=engine.Journey('graphics',RUN,m.source.fixture_url,invoke=self.invoke,witness=self.witness,activate=self.activate,
            read_artifact=lambda name:read_private_artifact(m.root/'artifacts',name),image_policy=dict(screen=SURFACE_PROFILE),
            continuity=lambda *args:m.guard(),monotonic=lambda:m.native.clock,epoch_ms=lambda:m.native.epoch,
            sleep=m.native.sleep,report=reports.append)
        with patch.object(engine.secrets,'token_hex',side_effect=token),patch('adapters.android_process_query.subprocess.run',side_effect=m.query):
            journey.execute()
        self.assertTrue(reports[-1]['sequenceCompleted']);self.assertTrue(reports[-1]['cleanupSucceeded'])
        self.assertEqual(17,len(reports[-1]['phases']));self.assertEqual(32,m.pid)
        self.assertTrue(set(('feature.graphics.act','feature.graphics.observe','feature.graphics.cleanup'))<=set(self.calls))
        m.provider.retire(RUN);m.journal.close(RUN)
        facade=self.fixture.original._graphics_journey();primary=facade._graphics_cleanup_feature('owned',RUN)
        config=dict(picoFeatureObserverVersion=2,area='graphics',target='owned',candidateArguments=['synthetic-only'],
            fixtureUrl=m.client.url,actorToken='c'*64,durationSeconds=30,artifactRoot=str(m.root/'artifacts'))
        actor_done=False
        def progress(seconds):
            nonlocal actor_done
            if not actor_done:
                with patch.object(owned_observer,'Client',return_value=self.actor_client):
                    self.assertEqual(0,feature_observer.run(facade,config,monotonic=lambda:m.native.clock,sleep=m.native.sleep))
                actor_done=True
            m.native.sleep(seconds)
        primary.sleep=progress;self.assertEqual(dict(performed=True),primary.finalize())
        self.assertTrue(actor_done);self.assertTrue(all(store.read() is None for store in primary.child_stores().values()))
        self.assertIsNone(primary.store.read());self.assertIsNone(primary.retirement_store.read())
        self.assertFalse(primary.store.path.with_name('graphics-final-runtime.json').exists())
        self.assertEqual([],list(m.native_root.iterdir()))


if __name__=='__main__':unittest.main()
