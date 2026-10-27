"""Real small header fences, with explicit parent-decoder/own-proof models.

These unit cases do not validate128-row graphs, native sources or a complete
DOM/UIKit acquisition. Those retain their separate original-flow obligations.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import tablet_web_native_peer_admission as admission
from ios.adapters import tablet_web_native_child_continuation as native
from ios.adapters import tablet_web_dom_continuation as dom,tablet_web_uikit_continuation as uikit
from ios.adapters import tablet_web_dom_original_link as dom_own,tablet_web_uikit_original_link as uikit_own
from ios.self_tests import test_ios_tablet_web_dom_initial_segment as dom_fixture
from ios.self_tests import test_ios_tablet_web_uikit_initial_segment as uikit_fixture


class TabletNativePeerMetadataTests(unittest.TestCase):
    def test_both_literal4_and_explicit5_preserve_empty_and_bound_body2_without_old_cap_changes(self):
        for codec,fixture,field,segment_field in (
            (dom,dom_fixture.TabletDOMInitialSegmentMetadataTests(),'tabletWebDOMContinuationVersion','tabletWebDOMActiveSegmentVersion'),
            (uikit,uikit_fixture.TabletUIKitInitialSegmentMetadataTests(),'tabletWebUIKitContinuationVersion','tabletWebUIKitActiveSegmentVersion')):
            value,expected,raw=fixture.value()
            for version in (4,5):
                with self.subTest(component=codec.PROFILE,version=version):
                    value[field]=version;before=deepcopy(value)
                    self.assertEqual(raw,codec.decode(value,expected)[0]);self.assertEqual(before,value)
                    self.assertEqual(2,value['active'][segment_field])
                    for fault in ('old-body','reset','overflow','unknown'):
                        changed=deepcopy(value)
                        if fault=='old-body':changed['active'][segment_field]=1
                        elif fault=='reset':changed['active']['nextRaw']=1
                        elif fault=='overflow':changed['active']['nextRaw']=1026
                        else:changed[field]=6
                        with self.subTest(fault=fault),self.assertRaises(NativeUIError):codec.decode(changed,expected)
            value[field]=5
            reference=dict(index=129,sha256='a'*64,bytes=2,device=1,inode=129)
            value['successor']=deepcopy(reference);value['active']['records']=[reference];value['active']['nextRaw']=130
            codec.decode(value,expected)
            value['successor']=None
            with self.assertRaises(NativeUIError):codec.decode(value,expected)

    def test_old_live_profiles_and_both_private_own_links_never_invoke_native_admission(self):
        with patch.object(admission,'admit',side_effect=AssertionError('No admission from old metadata or own graph')):
            for codec,klass,field in ((dom,dom.TabletDOMClosedPrefix,'tabletWebDOMContinuationVersion'),
                    (uikit,uikit.TabletUIKitClosedPrefix,'tabletWebUIKitContinuationVersion')):
                for version in (1,2,3,4):
                    owner=object.__new__(klass);owner.state={field:version}
                    owner._admit_current_native()
            # Constructor-independent hooks do not even need a scope: they
            # supply no peer authority, including when the own metadata is5.
            object.__new__(dom_own._OriginalLinkPrefix)._admit_current_native()
            object.__new__(uikit_own._OriginalLinkPrefix)._admit_current_native()


class TabletNativePeerHeaderTests(unittest.TestCase):
    def setUp(self):
        directory=self.enterContext(tempfile.TemporaryDirectory())
        self.root=Path(directory);self.root.chmod(0o700)
        _value,self.expected,_raw=dom_fixture.TabletDOMInitialSegmentMetadataTests().value()
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        self.enterContext(self.lock.held())
        self.stores={};self.parent=dict(children=[])
        for name in ('sources','trace','buttons','state','closures','emissions','deferred'):
            store=PrivateFeatureState(self.root/admission.children._name(name,self.expected));store.write(dict(unitOnly=True,sequence=1),None)
            raw,identity=admission.children._raw(store.path);self.stores[name]=store
            self.parent['children'].append(dict(component=name,headerName=store.path.name,signature=identity,sha256=hashlib.sha256(raw).hexdigest()))
        self.parent_store=PrivateFeatureState(self.root/('tabletweb-source-owner-'+self.expected['runId']+'-'+self.expected['role']+'.json'))
        self.parent_store.write(self.parent,None)
        raw,identity=admission.children._raw(self.parent_store.path)
        self.parent_pin=dict(signature=identity,sha256=hashlib.sha256(raw).hexdigest())
        def decode(value,expected):
            self.assertEqual(self.parent,value);self.assertEqual(self.expected,expected)
        self.enterContext(patch.object(admission.children,'decode',side_effect=decode))
        self.calls=[];self.mutate=None;self.fault=None
        def prove(root,binding,run,role,fixture,pid,name,lock,*,monotonic):
            self.assertEqual((self.root,self.expected['binding'],self.expected['runId'],self.expected['role'],
                self.expected['fixtureUrl'],self.expected['processId'],self.lock),(root,binding,run,role,fixture,pid,lock))
            self.calls.append(name)
            if self.mutate:self.mutate(name)
            result=dict(component=name,historicalOnly=True,subgraphOnly=True,peerAuthority=False)
            if self.fault:self.fault(result)
            return result
        self.enterContext(patch.object(native,'read_own',side_effect=prove))

    def replace(self,name):
        store=self.stores[name];previous=store.read();store.write(previous,previous)

    def read(self):return admission.admit(self.root,self.expected,self.parent_pin,self.lock,monotonic=lambda:1)

    def originals(self):
        return {path.name:(admission.children._raw(path)) for path in self.root.iterdir() if path.suffix=='.json'}

    def test_only_changed_headers_require_separate_proofs_and_return_detached_pins(self):
        self.replace('sources');self.replace('trace');before=self.originals();pins=self.read()
        self.assertEqual(['sources','trace'],self.calls);self.assertEqual(set(native.KINDS),set(pins))
        self.assertEqual(before,self.originals())
        for name,pin in pins.items():
            raw,identity=admission.children._raw(self.stores[name].path)
            self.assertEqual(dict(signature=identity,sha256=hashlib.sha256(raw).hexdigest()),pin)
        with self.assertRaises(TypeError):pins['sources']['signature']['inode']+=1
        with self.assertRaises(TypeError):pins['sources']['sha256']='a'*64
        self.assertEqual(before,self.originals())

    def test_each_own_proof_must_be_historical_detached_and_without_peer_authority(self):
        self.replace('sources');before=self.originals()
        for field,foreign in (('component','trace'),('historicalOnly',False),('historicalOnly',1),
                ('subgraphOnly',False),('subgraphOnly',1),('peerAuthority',True),('peerAuthority',0)):
            self.calls.clear();self.fault=lambda value,field=field,foreign=foreign:value.update({field:foreign})
            with self.subTest(field=field,foreign=foreign),self.assertRaises(NativeUIError):self.read()
            self.assertEqual(['sources'],self.calls);self.assertEqual(before,self.originals())

    def test_same_bytes_new_inode_born_during_its_actual_proof_never_becomes_a_new_pin(self):
        self.replace('sources');before=admission.children._raw(self.stores['sources'].path)
        self.mutate=lambda _name:self.replace('sources')
        with self.assertRaises(NativeUIError):self.read()
        after=admission.children._raw(self.stores['sources'].path)
        self.assertEqual(['sources'],self.calls);self.assertEqual(before[0],after[0]);self.assertNotEqual(before[1]['inode'],after[1]['inode'])

    def test_later_proof_cannot_refresh_an_earlier_already_proved_header(self):
        self.replace('sources');self.replace('trace')
        before=admission.children._raw(self.stores['sources'].path)
        self.mutate=lambda name:self.replace('sources') if name=='trace' else None
        with self.assertRaises(NativeUIError):self.read()
        after=admission.children._raw(self.stores['sources'].path)
        self.assertEqual(['sources','trace'],self.calls);self.assertEqual(before[0],after[0]);self.assertNotEqual(before[1]['inode'],after[1]['inode'])

    def test_replaced_parent_is_refused_before_any_peer_proof(self):
        self.replace('sources');prior=self.parent_store.read();self.parent_store.write(prior,prior)
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual([],self.calls)

    def test_new_inventory_member_during_an_otherwise_valid_proof_keeps_admission_unavailable(self):
        self.replace('sources')
        def mutate(_name):PrivateFeatureState(self.root/'foreign-unit-file.json').write(dict(unitOnly=True),None)
        self.mutate=mutate
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(['sources'],self.calls);self.assertTrue((self.root/'foreign-unit-file.json').is_file())


if __name__=='__main__':unittest.main()
