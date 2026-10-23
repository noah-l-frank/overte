"""Real private coordinator/stereo/file owners at explicit GPU/SDK/DOM seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import secrets
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import pack,unpack
from adapters.pico4.tablet_web_feature import VERSION
from self_tests.test_pico_browser_stereo import Model,RUN,TICKET,OWNER,SCRIPT
from self_tests import test_pico_tablet_web_feature as feature_seams


class PicoTabletWebImageTests(unittest.TestCase):
    def setUp(self):
        self.fixture=feature_seams.PicoTabletWebFeatureTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.model=Model();self.addCleanup(self.model.close)
        self.fixture.original.binding=deepcopy(self.model.binding)
        self.model.lock=self.fixture.original.lock
        self.flow=self.fixture.binding.feature('owned',self.fixture.flow().source,self.model.artifacts,feature_seams.FOREIGN)
        with patch('adapters.pico4.tablet_web_feature.uuid.uuid4',return_value=SimpleNamespace(hex=OWNER)):
            self.flow.prepare()
        def stereo(target,path,root,run,scene,**kwargs):
            self.assertIs(kwargs['source_lock'],self.model.lock)
            self.assertEqual(self.model.artifacts,root);self.assertEqual(RUN,run)
            return self.model.browser_stereo(role=kwargs['role'],journal=kwargs['journal_id'])
        self.fixture.original._browser_stereo=stereo
        with self.flow.lock.held():
            self.owner=self.flow.owner();self.owner['scriptUrl']=SCRIPT;self.flow.save(self.owner)
            self.state=self.flow.role_state()

    def capture(self):
        with self.flow.lock.held():
            return self.flow.screenshot(self.owner,TICKET,1,'primary',self.state)

    def test_actual_parent_capture_uses_full_original_file_reference_and_cold_verifies_png_and_metadata(self):
        artifacts,facts=self.capture();self.assertEqual(2,len(artifacts));self.assertEqual('',facts['state']['text'])
        image=self.state['images'][0];self.assertNotIn('record',image)
        with self.flow.lock.held():
            restored=self.flow.role_state();self.assertEqual(self.state,restored)
        self.assertEqual(1,len(self.model.gpu.commands));self.assertIsNone(self.model.owner_store('primary').read())
        name=next(row['name'] for row in artifacts if row['kind']=='file');path=self.model.artifacts/name
        raw=path.read_bytes();replacement=path.with_name('replacement');replacement.write_bytes(raw);replacement.chmod(0o600);replacement.replace(path)
        with self.flow.lock.held(),self.assertRaises((ValueError,RuntimeError)):self.flow.role_state()
        self.assertEqual(1,len(self.model.gpu.commands))

    def test_v1_image_migration_requires_original_file_and_exact_embedded_body_before_v2_cas(self):
        self.capture();image=self.state['images'][0]
        from adapters.pico4.browser_stereo import original_name
        raw=self.flow.metadata(original_name(RUN,'primary',image['journalId']),image['metadata'])
        legacy=deepcopy(self.state);legacy['images'][0]['record']=json.loads(raw)
        disk=self.flow.role_store.read();old=deepcopy(disk);old[self.flow.version_field]=1;old['payload']=pack([legacy])
        self.flow.role_store.write(old,disk)
        with self.flow.lock.held():
            restored=self.flow.role_state();self.assertEqual(self.state,restored)
            self.assertEqual(1,self.flow.role_store.read()[self.flow.version_field])
            self.flow.write(self.flow.role_store,'primary',restored)
        self.assertEqual(VERSION,self.flow.role_store.read()[self.flow.version_field])
        changed=deepcopy(old);legacy['images'][0]['record']['binding']['sessionId']='foreign-session';changed['payload']=pack([legacy])
        self.flow.role_store.write(changed,self.flow.role_store.read())
        with self.flow.lock.held(),self.assertRaises((ValueError,RuntimeError)):self.flow.role_state()
        self.assertEqual(changed,self.flow.role_store.read());self.assertEqual(1,len(self.model.gpu.commands))

    def test_duplicate_original_journal_or_changed_saved_png_refuses_without_recapture(self):
        artifacts,_facts=self.capture();image=deepcopy(self.state['images'][0])
        with self.flow.lock.held():
            self.state['images'].append(image);self.flow.write(self.flow.role_store,'primary',self.state)
            with self.assertRaises((ValueError,RuntimeError)):self.flow.role_state()
            self.state['images'].pop();self.flow.write(self.flow.role_store,'primary',self.state)
            name=next(row['name'] for row in artifacts if row['kind']=='image');path=self.model.artifacts/name
            path.write_bytes(path.read_bytes()+b'foreign bytes')
            with self.assertRaises((ValueError,RuntimeError)):self.flow.role_state()
        self.assertEqual(1,len(self.model.gpu.commands));self.assertIsNotNone(self.flow.role_store.read())

    def test_references_fit_all_26_distinct_original_metadata_identities_under_unchanged_caps(self):
        # Capacity calculation only: these random metadata DTOs are not accepted
        # captures. The separate positive above verifies an actual full source
        # journal, PNG, source guards and original native resource retirement.
        self.capture();reference=self.state['images'][0];rows=[];legacy=[]
        for index in range(26):
            row=deepcopy(reference);row.update(journalId=secrets.token_hex(16),ticket=secrets.token_hex(16))
            row['metadata'].update(inode=100000+index,sha256=secrets.token_hex(32),mtimeNs=100000000+index,ctimeNs=200000000+index)
            rows.append(row)
            # A previously packed original body is incompressible to the outer
            # parent. Preserve its realistic maximum size without calling it
            # a product source or weakening the physical file's own cap.
            legacy.append(row|{'record':dict(originalPackedDto=secrets.token_hex(8192))})
        state=deepcopy(self.state);state['images']=rows
        packed=pack([state]);self.assertLess(len(json.dumps(packed).encode()),65536)
        self.assertEqual(26,len(unpack(packed)[0]['images']))
        state['images']=legacy
        with self.assertRaises((ValueError,RuntimeError)):pack([state])

    def test_warm_validation_reuses_only_original_semantics_and_cold_reads_revalidate_every_source(self):
        self.capture()
        from feature_journeys.stereo_browser_evidence import archive_sources
        with self.flow.lock.held(),patch('feature_journeys.stereo_browser_evidence.archive_sources',wraps=archive_sources) as validate:
            self.flow.role_state();self.assertEqual(1,validate.call_count)
            self.flow.role_state();self.assertEqual(1,validate.call_count)
            cold=self.fixture.binding.feature('owned',self.fixture.flow().source,self.model.artifacts,feature_seams.FOREIGN)
            cold.role_state();self.assertEqual(2,validate.call_count)
        self.assertEqual(1,len(self.model.gpu.commands))

    def test_warm_png_replacement_cached_value_or_missing_reference_cannot_renew_original_semantics(self):
        artifacts,_facts=self.capture()
        with self.flow.lock.held():self.flow.role_state()
        from adapters.script_journey.history import canonical
        key=next(iter(self.flow.image_cache));cached=self.flow.image_cache[key];sealed=self.flow._image_cache[key]
        copy=self.flow.image_cache;copy[key]['scope']['ownerToken']='f'*32
        with self.flow.lock.held():self.flow.role_state()
        self.assertEqual(cached,self.flow.image_cache[key])
        for fault in ('cached-scope','cached-png','cached-tuple','cached-subclass','cached-key-subclass','raw-type','reference'):
            with self.subTest(fault=fault),self.flow.lock.held():
                changed=deepcopy(cached)
                if fault=='cached-scope':changed['scope']['ownerToken']='f'*32
                elif fault=='cached-png':changed['png']['capture']['instance']='f'*32
                elif fault=='cached-tuple':changed['stamp']=tuple(changed['stamp'])
                elif fault=='cached-subclass':
                    class ForeignScope(dict):pass
                    changed['scope']=ForeignScope(changed['scope'])
                elif fault=='cached-key-subclass':
                    class ForeignKey(str):pass
                    value=changed['scope'].pop('ownerToken');changed['scope'][ForeignKey('ownerToken')]=value
                if fault in ('cached-tuple','cached-subclass','cached-key-subclass'):
                    with self.assertRaises((ValueError,RuntimeError)):self.flow.image_digest(changed)
                else:
                    if fault=='reference':
                        empty=deepcopy(self.state);empty['images']=[];self.flow.write(self.flow.role_store,'primary',empty)
                    elif fault=='raw-type':self.flow._image_cache[key]=bytearray(sealed)
                    else:self.flow._image_cache[key]=canonical(changed)
                    with self.assertRaises((ValueError,RuntimeError)):self.flow.role_state()
                self.flow._image_cache[key]=sealed;self.flow.write(self.flow.role_store,'primary',self.state)
        name=next(row['name'] for row in artifacts if row['kind']=='image');path=self.model.artifacts/name
        raw=path.read_bytes();path.write_bytes(raw)
        with self.flow.lock.held(),self.assertRaises((ValueError,RuntimeError)):self.flow.role_state()
        self.assertEqual(1,len(self.model.gpu.commands));self.assertEqual(raw,path.read_bytes())


if __name__=='__main__':unittest.main()
