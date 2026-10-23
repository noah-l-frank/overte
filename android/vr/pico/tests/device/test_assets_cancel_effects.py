"""Original normal Cancel/File/Home joined to one independent server query.

Two actual client processes query the same original server GetAll body. The
stdio broker/network/assignment/controller endpoints remain host boundaries;
no server service, oven, successful upload, model or stereo run is qualified.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_assets_native_ui import compile_ui
from test_assets_read_native import compile_source
import test_assets_page_home as pages_module
import test_assets_home_owner as home_module
import test_assets_mapping_pair as pair_module
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.assets_mapping_pair import IndependentAssetsMappings
from adapters.script_journey.history import pack,unpack,canonical,MAX_RAW,MAX_FRAMES
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from openxr_input.adapter_session import PicoOpenXrAdapterSession


class AssetsCancelEffectsTests(unittest.TestCase):
    make=pages_module.AssetsPageHomeTests.make
    cancel_phase=pages_module.AssetsPageHomeTests.cancel_phase
    home_owner=home_module.AssetsHomeOwnerTests.home_owner
    pointers=pages_module.AssetsPageHomeTests.pointers
    @classmethod
    def setUpClass(cls):
        cls.build=tempfile.TemporaryDirectory(prefix='pico-assets-effects-build-')
        cls.binary,cls.environment,cls.args=compile_ui(cls.build.name,persistent_tablet=True,original_server=True)
        independent=Path(cls.build.name)/'independent';independent.mkdir()
        cls.reader_binary,cls.reader_environment=compile_source(independent)
    @classmethod
    def tearDownClass(cls):cls.build.cleanup()
    def setUp(self):
        pages_module.AssetsPageHomeTests.setUp(self)
        self.lock=ScriptSourceLock(self.path/'script-sources.lock');independent=self.path/'independent';independent.mkdir(mode=0o700)
        self.actor=pair_module.Actor(self.reader_binary,self.reader_environment,independent,shared_server=self.host.request);self.addCleanup(self.actor.close)
        self.primary=self.host.mappings();self.pair=IndependentAssetsMappings(self.primary,self.actor.source,self.lock,self.actor.lock,
            PhaseFixtureReader(self.client,self.run,'assets'))
        self.addCleanup(self.preserve)
    def preserve(self):
        destination=os.environ.get('OVERTE_ASSETS_EFFECTS_EVIDENCE')
        if destination is None:return
        directory=Path(destination).resolve(strict=True);prefix=self._testMethodName
        values=dict(assetsCancelEffectsHostEvidenceVersion=1,primaryPid=self.host.process.pid,independentPid=self.actor.process.pid,
            primaryArtifactSha256=hashlib.sha256(Path(self.binary).read_bytes()).hexdigest(),independentArtifactSha256=hashlib.sha256(Path(self.reader_binary).read_bytes()).hexdigest(),
            pairedOriginals=pack(self.pair.history),primaryOriginals=pack(self.primary.history),independentOriginals=pack(self.actor.source.history),
            serverOriginals=pack(self.actor.server_originals),independentPipeOriginals=pack(self.actor.received),
            finalUploadOriginals=pack(self.final_uploads.history if hasattr(self,'final_uploads') else []),
            serverBodyOriginals=json.loads((Path(self.build.name)/'server-original-provenance.json').read_text()),pointers=self.pointers())
        PrivateFeatureState(directory/(prefix+'-effects.json')).write(values,None)
        for role,store in [('cancel',self.store),('files',self.file_store),*([('home',self.home_store)] if hasattr(self,'home_store') else [])]:
            if store.read() is not None:PrivateFeatureState(directory/(prefix+'-'+role+'.json')).write(store.read(),None)
    def mappings(self):
        frame=self.pair.capture();primary=json.loads(frame['primary']['raw']);independent=json.loads(frame['independent']['raw'])
        self.assertEqual(primary['source']['mappings'],independent['source']['mappings']);return primary['source']['mappings']
    def test_normal_cancel_file_home_and_continuous_independent_unchanged_mapping_effect(self):
        baseline=self.mappings();self.assertEqual(1,len(baseline));self.assertEqual('/foreign/original.bin',baseline[0]['path'])
        self.owner.open();self.assertEqual(baseline,self.mappings());self.cancel_phase();sample=self.owner.sample;quiet=[]
        def independently_observed_sample():
            value=sample();self.assertEqual(baseline,self.mappings());quiet.append(deepcopy(self.pair.history[-1]));return value
        with patch.object(self.owner,'sample',side_effect=independently_observed_sample):self.assertTrue(self.owner.cancel()['filesRetired'])
        self.assertGreaterEqual(len(quiet),2)
        first,last=(json.loads(frame['independent']['raw']) for frame in (quiet[0],quiet[-1]))
        self.assertGreaterEqual(last['capturedEpochMs']-first['capturedEpochMs'],3000)
        for before,after in zip(quiet,quiet[1:]):
            left,right=(json.loads(frame['independent']['raw']) for frame in (before,after))
            self.assertTrue(0<right['capturedEpochMs']-left['capturedEpochMs']<=500)
        self.cancel_before=deepcopy(self.store.read());self.files_before=deepcopy(self.file_store.read())
        self.journal.activate(self.run,'3'*32,'close',{})
        self.home_store=PrivateFeatureState(self.path/'normal-assets-home-stage1-host.json');self.transport=home_module.OriginalChannelTransport(self)
        self.session=PicoOpenXrAdapterSession(self.transport,'explicit-assets-effects-channel',self.path);self.session.begin(self.binding['processIdentity']);self.home_owner()
        result=self.home.close_page();self.assertTrue(result['homeObserved'] and result['pageRetired']);self.assertFalse(result['contextRetired'])
        self.assertEqual(baseline,self.mappings());self.assertEqual(self.cancel_before,self.store.read());self.assertEqual(self.files_before,self.file_store.read())
        self.assertEqual(1,len(self.transport.envelopes));self.final_uploads=self.host.uploads()
        self.assertEqual(0,self.final_uploads.read(self.run)['source']['totalCalls'])
        replies=[json.loads(frame['raw']) for frame in self.actor.server_originals];self.assertEqual(len(self.pair.history),len(replies))
        self.assertTrue(all(reply['processId']==self.host.process.pid for reply in replies))
        self.assertEqual(1,len({reply['serverInstance'] for reply in replies}));self.assertEqual(1,len({json.dumps(reply['serverFiles'],sort_keys=True) for reply in replies}))
        for reply in replies:
            self.assertEqual(1,len(reply['serverFiles']));blob=reply['serverFiles'][0]
            self.assertTrue(blob['exists']);self.assertEqual(baseline[0]['hash'],blob['hash']);self.assertEqual(blob['hash'],blob['sha256']);self.assertGreater(blob['bytes'],0)
        self.assertTrue(all(right['sourceSequence']>left['sourceSequence'] for left,right in zip(replies,replies[1:])))
        counts=4*len(self.pair.history)+len(self.primary.history)+len(self.actor.source.history)
        raw=len(canonical(self.pair.history))+len(canonical(self.primary.history))+len(canonical(self.actor.source.history))
        for originals in (self.actor.server_originals,self.actor.received):counts+=len(originals);raw+=len(canonical(originals))
        home=self.home_store.read();cancel=self.store.read();files=self.file_store.read()
        for original in (cancel['inputs'],cancel['uiOriginals'],cancel['originals'],files['originals'],home['pages'],home['files']):
            counts+=len(unpack(original));raw+=original['bytes']
        counts+=len(home['neutralReads'])+len(home['neutralFinal']);raw+=len(canonical([home['neutralReads'],home['neutralFinal']]))
        # Complete bound child snapshots in Home are retained separately too;
        # do not hide their original transcript cost behind compressed JSON.
        for child in unpack(home['children']):
            for key in ('inputs','uiOriginals','originals'):
                if key in child:counts+=len(unpack(child[key]));raw+=child[key]['bytes']
        raw+=2*len(canonical([cancel['baselineMappings'],cancel['baselineUploads'],cancel['unresolvedInputs']]))
        counts+=len(self.final_uploads.history);raw+=len(canonical(self.final_uploads.history))
        self.assertLessEqual(counts,MAX_FRAMES);self.assertLessEqual(raw,MAX_RAW);self.assertTrue(self.pointers()['contextAlive'])


if __name__=='__main__':unittest.main()
