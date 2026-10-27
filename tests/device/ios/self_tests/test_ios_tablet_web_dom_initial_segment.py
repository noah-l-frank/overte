"""First actual DOM129 WAL over real files and modeled native producers.

The reused128-row builder is explicit prefix evidence, not128 Journey steps
or a physical Web/native timing qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import tablet_web_dom_segment as active,tablet_web_dom_continuation as closed
from ios.adapters import tablet_web_child_rotation as parent,tablet_web_dom_original_link as link
from ios.adapters.tablet_web_packets import TabletWebPackets
from ios.self_tests import test_ios_tablet_web_dom_segment as existing


class TabletDOMInitialSegmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):existing.TabletDOMSegmentTests.setUpClass()

    def setUp(self):
        self.flow=existing.TabletDOMSegmentTests();self.flow.setUp();self.addCleanup(self.flow.doCleanups)
        self.f=self.flow.f;self.s=self.f.source;self.boundary=self.f.f.boundary

    def closed(self):self.f.build();return self.f.complete()
    def open(self):return active.open_initial_segment(*self.flow.arguments(),**self.flow.clocks())
    def reopen(self):return self.flow.reopen()
    def read(self):
        s=self.s
        return link.read(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)

    def test_first_actual129_lost_open_complete_original_and_bind_CAS_recover_without_precreated_successor(self):
        prefix=self.closed();old_raw=closed.decode(prefix.state,prefix.expected)[0];body=deepcopy(prefix.body())
        originals=self.f.originals();counts=self.f.native_counts();write=PrivateFeatureState.write;lost=[]
        def opened(store,value,previous):
            result=write(store,value,previous)
            if store.path==prefix.store.path and value.get('tabletWebDOMContinuationVersion')==4:
                lost.append(True);raise OSError('Modeled lost successful initial DOM segment-open CAS return')
            return result
        with patch.object(PrivateFeatureState,'write',opened),self.assertRaises(OSError):self.open()
        self.assertEqual([True],lost);self.assertEqual(counts,self.f.native_counts());self.assertEqual(originals,self.f.originals())
        owner=self.reopen();self.assertEqual(4,owner.closed.state['tabletWebDOMContinuationVersion'])
        self.assertIsNone(owner.closed.state['successor']);self.assertEqual([],owner.state['records'])
        self.assertEqual((129,129),(owner._next_index(),owner.state['nextRaw']))
        self.assertEqual(128,self.read()['globalIndex'])
        with self.assertRaises(NativeUIError):self.open()
        reader=self.boundary.reader('dom');send=reader.send;seen=[]
        def actual(query):
            state=owner.store.read();pending=state['active']['pending']
            self.assertEqual(129,pending['index']);self.assertEqual('issued',pending['status'])
            self.assertEqual(query,pending['query']);self.assertFalse(pending['sendReturned'])
            self.assertIsNone(state['successor']);self.assertEqual([],state['active']['records'])
            self.assertFalse(list(self.s.root.glob('tabletweb-dom-packets-frame-*-0129-*.json')))
            seen.append(deepcopy(query));return send(query)
        reader.send=actual;intent=owner.originals.intent
        def lost_original(kind,value):
            intent(kind,value)
            if kind=='original' and value['phase']=='saved':raise OSError('Modeled lost complete first DOM129 original return')
        owner.originals.intent=lost_original
        with self.assertRaises(OSError):owner.capture(reader)
        self.assertEqual(1,len(seen));self.assertEqual(counts[0]+['dom'],self.f.native_counts()[0])
        counts=self.f.native_counts();before=self.f.originals();rebuilt=self.reopen()
        self.assertIsNone(rebuilt.closed.state['successor']);self.assertEqual([],rebuilt.state['records'])
        self.assertEqual(129,rebuilt.state['recordIntent']['index']);self.assertTrue(rebuilt.state['recordInspection']['complete'])
        bound=[]
        def bound_return(store,value,previous):
            result=write(store,value,previous)
            if store.path==rebuilt.store.path and value.get('tabletWebDOMContinuationVersion')==4 \
                    and value['successor'] is not None and previous['successor'] is None:
                bound.append(deepcopy(value['successor']));raise OSError('Modeled lost successful first DOM-original bind CAS return')
            return result
        with patch.object(PrivateFeatureState,'write',bound_return),self.assertRaises(OSError):rebuilt.recover_record()
        self.assertEqual(1,len(bound));rebuilt=self.reopen();reference=deepcopy(rebuilt.state['records'][0])
        self.assertEqual(bound[0],reference);self.assertEqual(reference,rebuilt.closed.state['successor'])
        self.assertEqual(130,rebuilt.state['nextRaw']);self.assertEqual(before,self.f.originals());self.assertEqual(counts,self.f.native_counts())
        packet129=rebuilt.history()[-1];self.assertEqual(129,packet129['sequence'])
        packet130=rebuilt.capture(self.boundary.reader('dom'));self.assertEqual(130,packet130['sequence'])
        self.assertNotEqual(seen[0]['commandId'],self.boundary.sent['dom']['commandId'])
        counts=self.f.native_counts();inventory=self.f.inventory();proof=self.read()
        self.assertEqual(packet130,proof['nativeFloor']);self.assertTrue(proof['subgraphOnly']);self.assertFalse(proof['peerAuthority'])
        s=self.s;result=parent.restore(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)
        self.assertEqual(packet130,result['children']['dom']);self.assertEqual(1,result['globalIndex'])
        self.assertEqual(1,result['frames'][0]['document']['sequence'])
        self.assertEqual(old_raw,closed.decode(rebuilt.closed.state,prefix.expected)[0]);self.assertEqual(body,rebuilt.closed.body())
        self.assertEqual(originals,{name:value for name,value in self.f.originals().items() if name in originals})
        self.assertEqual(counts,self.f.native_counts());self.assertEqual(inventory,self.f.inventory())

    def test_first_issued_CAS_loss_keeps_exact129_query_and_blocks_replay_after_archival(self):
        self.closed();owner=self.open();write=PrivateFeatureState.write;lost=[];counts=self.f.native_counts()
        def issued(store,value,previous):
            result=write(store,value,previous);pending=value.get('active',{}).get('pending')
            if store.path==owner.store.path and pending is not None and pending['status']=='issued' and not lost:
                lost.append(deepcopy(pending));raise OSError('Modeled lost first DOM129 issued CAS before send')
            return result
        with patch.object(PrivateFeatureState,'write',issued),self.assertRaises((OSError,NativeUIError)):
            owner.capture(self.boundary.reader('dom'))
        self.assertEqual(1,len(lost));self.assertEqual(counts,self.f.native_counts());rebuilt=self.reopen()
        self.assertIsNone(rebuilt.closed.state['successor']);self.assertEqual(lost[0]['query'],rebuilt.state['pending']['query'])
        with self.assertRaises(NativeUIError):rebuilt.capture(self.boundary.reader('dom'))
        reference=rebuilt.archive_pending(abandon=True);row=rebuilt.originals.read(rebuilt.originals.expand(reference))
        self.assertEqual('abandoned',row['status']);self.assertEqual(lost[0]['query'],row['query'])
        self.assertEqual(lost[0]['before'],row['before']);self.assertEqual(lost[0]['after'],row['after'])
        self.assertEqual(129,rebuilt.state['nextRaw']);self.assertEqual(reference,rebuilt.closed.state['successor'])
        rebuilt.history();self.assertTrue(rebuilt.blocked)
        with self.assertRaises(NativeUIError):rebuilt.capture(self.boundary.reader('dom'))
        with self.assertRaises(NativeUIError):self.read()
        s=self.s
        with self.assertRaises(NativeUIError):parent.restore(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)
        self.assertEqual(counts,self.f.native_counts())


class TabletDOMInitialSegmentMetadataTests(unittest.TestCase):
    """Typed syntax/fencing only; synthetic refs do not prove original files."""
    def value(self):
        value,expected,raw=existing.TabletDOMSegmentMetadataTests().value(3,2)
        value['tabletWebDOMContinuationVersion']=4;value['successor']=None
        value['active'].update(tabletWebDOMActiveSegmentVersion=2,nextRaw=129,records=[])
        return value,expected,raw

    def test_explicit_empty4_preserves_old_bytes_and_cannot_borrow_old_segment_or_reset_cursor(self):
        value,expected,raw=self.value();before=deepcopy(value);actual,_old=closed.decode(value,expected)
        self.assertEqual(raw,actual);self.assertEqual(before,value)
        for kind in ('old3','old-segment','bound-ref','foreign-subject','missing-active','overflow','reset'):
            with self.subTest(kind=kind):
                changed=deepcopy(value)
                if kind=='old3':changed['tabletWebDOMContinuationVersion']=3
                elif kind=='old-segment':changed['active']['tabletWebDOMActiveSegmentVersion']=1
                elif kind=='bound-ref':changed['successor']=dict(index=129,sha256='a'*64,bytes=2,device=1,inode=1)
                elif kind=='foreign-subject':changed['active']['component']='uikit'
                elif kind=='missing-active':del changed['active']
                elif kind=='overflow':changed['active']['nextRaw']=1026
                else:changed['active']['nextRaw']=1
                with self.assertRaises(NativeUIError):closed.decode(changed,expected)

    def test_first_reference_syntax_is_exact_and_old3_and_new4_segment_versions_stay_distinct(self):
        value,expected,_raw=existing.TabletDOMSegmentMetadataTests().value(3,2)
        value['tabletWebDOMContinuationVersion']=4;value['active']['tabletWebDOMActiveSegmentVersion']=2
        closed.decode(value,expected)
        for kind in ('no-first','foreign-first','gap','cap','old3','old-segment'):
            with self.subTest(kind=kind):
                changed=deepcopy(value)
                if kind=='no-first':changed['successor']=None
                elif kind=='foreign-first':changed['active']['records'][0]['inode']+=1
                elif kind=='gap':changed['active']['records'][0]['index']=130
                elif kind=='cap':changed['active']['records']*=129
                elif kind=='old3':changed['tabletWebDOMContinuationVersion']=3
                else:changed['active']['tabletWebDOMActiveSegmentVersion']=1
                with self.assertRaises(NativeUIError):closed.decode(changed,expected)

    def test_literal_packet_reader_refuses_new4_before_lower_factories_without_changing_head(self):
        value,expected,_raw=self.value()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);store=PrivateFeatureState(root/parent._name('dom',expected));store.write(value,None)
            before=(store.path.stat().st_dev,store.path.stat().st_ino,store.path.read_bytes())
            with patch('ios.adapters.tablet_web_packets.OriginalFrameStore',side_effect=AssertionError('No lower frame factory')), \
                 patch('ios.adapters.tablet_web_packets.TabletWebSourceSegments',side_effect=AssertionError('No lower raw factory')), \
                 self.assertRaises(NativeUIError):
                TabletWebPackets(root,expected['binding'],expected['runId'],expected['role'],expected['fixtureUrl'],
                    expected['processId'],'dom',lambda:False,historical=True)
            self.assertEqual(before,(store.path.stat().st_dev,store.path.stat().st_ino,store.path.read_bytes()))

    def test_private_own_link_expires_even_when_constructor_refuses_before_original_access(self):
        _value,expected,_raw=self.value();constructor=link._OriginalLinkPrefix.__init__;retained=[]
        def actual(scope,*args,**kwargs):
            try:return constructor(scope,*args,**kwargs)
            finally:retained.append(scope)
        with tempfile.TemporaryDirectory() as directory,patch.object(link._OriginalLinkPrefix,'__init__',actual),self.assertRaises(NativeUIError):
            link.read(Path(directory),expected['binding'],expected['runId'],expected['role'],expected['fixtureUrl'],expected['processId'],None)
        self.assertEqual(1,len(retained));self.assertFalse(retained[0].alive)
        with self.assertRaises(NativeUIError):retained[0].guard()
        with self.assertRaises(NativeUIError):retained[0].copy()


if __name__=='__main__':unittest.main()
