"""All21 normal Create actions on the same original CLI/Parent, model scope.

Actual fixture/Settings HTTP and process/file/lock ownership run; native/UI/
controller/render producers stay explicit models. No independent Actor/GPU or
successful product cleanup is inferred from the normal action sequence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import time
import unittest
import uuid

from test_create_operation_cli import CreateOperationCliTests
from test_create_journey import RUN,URL
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.scenarios import SCENARIOS
from self_tests.test_pico_create_permissions import PicoCreatePermissionTests


class CreateOperationFullPrefixTests(CreateOperationCliTests):
    def setUp(self):
        super().setUp()
        self.prefix[1]=str(Path(__file__).with_name('create_operation_full_cli_host.py'))
        actor=self.actor=PicoCreatePermissionTests();actor.setUp()
        self.addCleanup(lambda:(actor.tearDown(),actor.doCleanups()))
        provider,server,reader,_adapter=actor.fixture()
        self.provider,self.server,self.remote_reader=provider,server,reader
        server.journal=self.authority.journal
        domain='11111111-1111-1111-1111-111111111111'
        actor.controller.domain=actor.server.domain=domain;provider.config['domainId']=domain
        clock=PrivateFeatureState(self.area/'permission-source-clock.json');clock.write(dict(epochMs=self.authority.epoch),None)
        actor.controller.epoch_ms=provider.epoch_ms=lambda:clock.read()['epochMs']
        provider.provision(RUN)
        reader.run=RUN;reader.area='create';reader.closed=False
        def activate(path,value=None,method=None,**options):
            assert path=='/runs/'+RUN+'/active' and method is None and not options
            result=reader.request(path,value,method)
            phase=self.authority.journal.phase(RUN,uuid.uuid4().hex)
            publication={key:phase[key] for key in ('instance','createdEpochMs','activations')}
            self.authority.path.write(publication,self.authority.previous);self.authority.previous=publication
            return result
        self.authority.request=activate
        PrivateFeatureState(self.area/'permission-model.json').write(dict(
            settingsUrl=actor.controller.url,fixtureUrl=reader.url,
            originalStandard=deepcopy(actor.original['standard_permissions'])),None)

    def test_all_twenty_one_normal_actions_share_original_cli_and_permission_sources(self):
        started=time.monotonic();deadline=started+120
        self.component('prepare')
        for step in SCENARIOS['create']['steps']:
            self.assertLess(time.monotonic(),deadline)
            self.act(step['verb'],step['inputs'])
        metadata=PrivateFeatureState(self.area/'model-host.json').read();self.assertEqual(1,metadata['factoryCalls'])
        root=Path(metadata['stateRoot'])
        parent=PrivateFeatureState(next(root.glob('create-feature-owner-*.json'))).read()
        self.assertEqual(21,len(parent['calls']));self.assertIsNone(parent['pending']);self.assertIsNone(parent['subject'])
        self.assertEqual('edited',parent['voxelEdit']['outcome']);self.assertTrue(parent['voxelEdit']['settingsRestored'])
        self.assertEqual(2,len(self.actor.server.posts))
        sample=self.component('sample');self.authority.epoch=sample['sampleAnchor']['nativeEpochMs']
        with self.assertRaisesRegex(RuntimeError,'unresolved'):
            with self.host.create_input_context(RUN,URL,'cleanup',None):
                self.authority.activate(uuid.uuid4().hex,'cleanup',{})
                self.component('cleanup')
        self.assertTrue(self.host.failed)
        self.assertEqual(self.actor.original,self.actor.server.security)
        self.assertEqual(3,len(self.actor.server.posts))
        errors=b''.join(path.read_bytes() for path in sorted(self.artifacts.glob('stderr-*.bin')))
        self.assertIn(b'Original Create Qt context, listener or delivery remains retained',errors)
        self.assertLess(time.monotonic(),deadline)
        (self.area/'twenty-one-action-prefix-result.json').write_text(json.dumps(dict(
            componentOnly=True,completeCommonObservation=False,actions=21,cleanupSucceeded=False,
            retainedQtContext=True,independentActorObserved=False,gpuPixelsObserved=False,host=metadata,
            permissionSettingsRestored=True,parent=parent,hostElapsedSeconds=time.monotonic()-started),sort_keys=True))

    def test_ignored_actual_permission_post_blocks_sixteenth_input_and_never_replays(self):
        started=time.monotonic();self.component('prepare')
        for step in SCENARIOS['create']['steps'][:15]:self.act(step['verb'],step['inputs'])
        metadata=PrivateFeatureState(self.area/'model-host.json').read();root=Path(metadata['stateRoot'])
        store=PrivateFeatureState(next(root.glob('create-feature-owner-*.json')));before=store.read()
        self.actor.server.ignore=True
        with self.assertRaisesRegex(ValueError,'Owned feature fixture transport failed'):
            self.act('set-rez-permission',dict(allowed=False))
        self.assertTrue(self.host.failed)
        after=store.read();self.assertEqual(15,len(after['calls']))
        self.assertEqual(before['inputCount'],after['inputCount'])
        self.assertEqual(self.actor.original,self.actor.server.security)
        self.assertEqual(1,len(self.actor.server.posts));self.assertIsNotNone(self.provider.state()['pending'])
        originals={path.name:path.read_bytes() for path in self.artifacts.iterdir() if path.is_file()}
        with self.assertRaises(RuntimeError):self.component('sample')
        self.assertEqual(originals,{path.name:path.read_bytes() for path in self.artifacts.iterdir() if path.is_file()})
        self.assertEqual(1,len(self.actor.server.posts));self.assertLess(time.monotonic()-started,120)


def load_tests(loader,tests,pattern):
    return loader.loadTestsFromNames([
        'CreateOperationFullPrefixTests.test_all_twenty_one_normal_actions_share_original_cli_and_permission_sources',
        'CreateOperationFullPrefixTests.test_ignored_actual_permission_post_blocks_sixteenth_input_and_never_replays'],module=__import__(__name__))


if __name__=='__main__':unittest.main()
