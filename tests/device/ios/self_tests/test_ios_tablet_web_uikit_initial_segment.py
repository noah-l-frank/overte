"""Real first UIKit129 WAL, original files and modeled native transport.

The reused prefix builder owns128 independent replies; DOM's separate129
fixture bootstrap is not qualified by this UIKit-only packet.
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
from ios.adapters import tablet_web_uikit_segment as active,tablet_web_uikit_continuation as closed
from ios.adapters import tablet_web_child_rotation as parent,tablet_web_uikit_original_link as link
from ios.adapters.tablet_web_packets import TabletWebPackets
from ios.self_tests import test_ios_tablet_web_uikit_segment as existing


class TabletUIKitInitialSegmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):existing.TabletUIKitSegmentTests.setUpClass()

    def setUp(self):
        self.flow=existing.TabletUIKitSegmentTests();self.flow.setUp();self.addCleanup(self.flow.doCleanups)
        self.s=self.flow.source;self.evidence=self.flow.evidence

    def closed(self):self.flow.base.build();return self.flow.base.complete()
    def open(self):return active.open_initial_segment(*self.flow.arguments(),**self.flow.clocks())
    def reopen(self):return self.flow.reopen()
    def read(self):
        s=self.s
        return link.read(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)

    def test_first_real129_lost_open_and_complete_original_recover_without_precreated_successor(self):
        prefix=self.closed();old_raw=closed.decode(prefix.state,prefix.expected)[0];body=deepcopy(prefix.body())
        originals=self.evidence.originals();counts=self.evidence.native_counts();write=PrivateFeatureState.write;lost=[]
        def opened(store,value,previous):
            answer=write(store,value,previous)
            if store.path==prefix.store.path and value.get('tabletWebUIKitContinuationVersion')==closed.VERSION:
                lost.append(True);raise OSError('Modeled lost successful initial UIKit segment-open CAS')
            return answer
        with patch.object(PrivateFeatureState,'write',opened),self.assertRaises(OSError):self.open()
        self.assertEqual([True],lost);self.assertEqual(counts,self.evidence.native_counts())
        self.assertEqual(originals,self.evidence.originals());owner=self.reopen()
        self.assertEqual(closed.VERSION,owner.closed.state['tabletWebUIKitContinuationVersion'])
        self.assertIsNone(owner.closed.state['successor']);self.assertEqual([],owner.state['records'])
        self.assertEqual((129,129),(owner._next_index(),owner.state['nextRaw']))
        self.assertEqual(128,self.read()['globalIndex'])
        with self.assertRaises(NativeUIError):self.open()
        reader=self.flow.boundary.reader('uikit');send=reader.send;seen=[]
        def actual(query):
            state=owner.store.read();pending=state['active']['pending']
            self.assertEqual(129,pending['index']);self.assertEqual('issued',pending['status'])
            self.assertEqual(query,pending['query']);self.assertFalse(pending['sendReturned'])
            self.assertIsNone(state['successor']);self.assertEqual([],state['active']['records'])
            self.assertFalse(list(self.s.root.glob('tabletweb-uikit-packets-frame-*-0129-*.json')))
            seen.append(deepcopy(query));return send(query)
        reader.send=actual;intent=owner.originals.intent
        def lost_original(kind,value):
            intent(kind,value)
            if kind=='original' and value['phase']=='saved':raise OSError('Modeled lost complete first UIKit129 original return')
        owner.originals.intent=lost_original
        with self.assertRaises(OSError):owner.capture(reader)
        self.assertEqual(1,len(seen));self.assertEqual(counts[0]+['uikit'],self.evidence.native_counts()[0])
        counts=self.evidence.native_counts();before=self.evidence.originals();rebuilt=self.reopen()
        self.assertIsNone(rebuilt.closed.state['successor']);self.assertEqual([],rebuilt.state['records'])
        reference=deepcopy(rebuilt.state['recordIntent']);self.assertEqual(129,reference['index'])
        self.assertTrue(rebuilt.state['recordInspection']['complete'])
        bound=[]
        def bound_return(store,value,previous):
            answer=write(store,value,previous)
            if store.path==rebuilt.store.path and value.get('tabletWebUIKitContinuationVersion')==closed.VERSION \
                    and value['successor'] is not None and previous['successor'] is None:
                bound.append(deepcopy(value['successor']));raise OSError('Modeled lost successful first-original bind CAS return')
            return answer
        with patch.object(PrivateFeatureState,'write',bound_return),self.assertRaises(OSError):rebuilt.recover_record()
        self.assertEqual(1,len(bound));rebuilt=self.reopen();actual_reference=deepcopy(rebuilt.state['records'][0])
        self.assertEqual(bound[0],actual_reference);self.assertEqual(129,actual_reference['index'])
        self.assertEqual(actual_reference,rebuilt.closed.state['successor']);self.assertEqual(130,rebuilt.state['nextRaw'])
        self.assertEqual(before,self.evidence.originals());self.assertEqual(counts,self.evidence.native_counts())
        packet129=rebuilt.history()[-1];self.assertEqual(129,packet129['sequence'])
        packet130=rebuilt.capture(self.flow.boundary.reader('uikit'));self.assertEqual(130,packet130['sequence'])
        self.assertNotEqual(seen[0]['commandId'],self.flow.boundary.sent['uikit']['commandId'])
        counts=self.evidence.native_counts();inventory=self.evidence.inventory();actual=self.read()
        self.assertEqual(packet130,actual['nativeFloor']);self.assertEqual(130,actual['globalIndex'])
        self.assertFalse(actual['peerAuthority']);self.assertTrue(actual['subgraphOnly'])
        s=self.s;result=parent.restore(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)
        self.assertEqual(packet130,result['children']['uikit']);self.assertEqual(1,result['globalIndex'])
        self.assertEqual(1,result['frames'][0]['touches']['sequence'])
        self.assertEqual(old_raw,closed.decode(rebuilt.closed.state,prefix.expected)[0]);self.assertEqual(body,rebuilt.closed.body())
        self.assertEqual(originals,{name:value for name,value in self.evidence.originals().items() if name in originals})
        self.assertEqual(counts,self.evidence.native_counts());self.assertEqual(inventory,self.evidence.inventory())

    def test_lost_first_issued_CAS_keeps129_unresolved_after_archival_and_refuses_resend_or_parent_admission(self):
        self.closed();owner=self.open();write=PrivateFeatureState.write;lost=[];counts=self.evidence.native_counts()
        def issued(store,value,previous):
            answer=write(store,value,previous);pending=value.get('active',{}).get('pending')
            if store.path==owner.store.path and pending is not None and pending['status']=='issued' and not lost:
                lost.append(deepcopy(pending));raise OSError('Modeled lost first UIKit129 issued CAS before send')
            return answer
        with patch.object(PrivateFeatureState,'write',issued),self.assertRaises((OSError,NativeUIError)):
            owner.capture(self.flow.boundary.reader('uikit'))
        self.assertEqual(1,len(lost));self.assertEqual(counts,self.evidence.native_counts());rebuilt=self.reopen()
        self.assertIsNone(rebuilt.closed.state['successor']);self.assertEqual(lost[0]['query'],rebuilt.state['pending']['query'])
        with self.assertRaises(NativeUIError):rebuilt.capture(self.flow.boundary.reader('uikit'))
        reference=rebuilt.archive_pending(abandon=True);row=rebuilt.originals.read(rebuilt.originals.expand(reference))
        self.assertEqual('abandoned',row['status']);self.assertEqual(lost[0]['query'],row['query'])
        self.assertEqual(lost[0]['before'],row['before']);self.assertEqual(129,rebuilt.state['nextRaw'])
        self.assertEqual(reference,rebuilt.closed.state['successor']);rebuilt.history();self.assertTrue(rebuilt.blocked)
        with self.assertRaises(NativeUIError):rebuilt.capture(self.flow.boundary.reader('uikit'))
        with self.assertRaises(NativeUIError):self.read()
        s=self.s
        with self.assertRaises(NativeUIError):parent.restore(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)
        self.assertEqual(counts,self.evidence.native_counts())


class TabletUIKitInitialSegmentMetadataTests(unittest.TestCase):
    """Explicit wire syntax only; no original/native authority."""
    def value(self):
        value,expected,raw=existing.TabletUIKitSegmentMetadataTests().value()
        value['tabletWebUIKitContinuationVersion']=4;value['successor']=None
        value['active'].update(tabletWebUIKitActiveSegmentVersion=2,nextRaw=129,records=[])
        return value,expected,raw

    def test_empty_initial4_is_explicit_and_preserves_literal_predecessor(self):
        value,expected,raw=self.value();before=deepcopy(value);actual,_old=closed.decode(value,expected)
        self.assertEqual(raw,actual);self.assertEqual(before,value)
        self.assertEqual((1,2,3,4,5),closed.READS);self.assertEqual((1,2),active.READS)

    def test_literal_packet_constructor_refuses_initial4_before_any_lower_original_factory(self):
        value,expected,_raw=self.value()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700)
            store=PrivateFeatureState(root/parent._name('uikit',expected));store.write(value,None)
            before=(store.path.stat().st_dev,store.path.stat().st_ino,store.path.read_bytes())
            with patch('ios.adapters.tablet_web_packets.OriginalFrameStore',side_effect=AssertionError('No lower frame factory')), \
                 patch('ios.adapters.tablet_web_packets.TabletWebSourceSegments',side_effect=AssertionError('No lower raw factory')), \
                 self.assertRaises(NativeUIError):
                TabletWebPackets(root,expected['binding'],expected['runId'],expected['role'],expected['fixtureUrl'],
                    expected['processId'],'uikit',lambda:False,historical=True)
            self.assertEqual(before,(store.path.stat().st_dev,store.path.stat().st_ino,store.path.read_bytes()))

    def test_empty_initial_cannot_be_relabelled_as_old_bound2_active3_or_segment1(self):
        value,expected,_raw=self.value()
        for kind in ('bound2','active3','segment1','first-ref','wrong-segment','missing-active','raw-overflow','raw-reset'):
            with self.subTest(kind=kind):
                changed=deepcopy(value)
                if kind=='bound2':changed['tabletWebUIKitContinuationVersion']=2;del changed['active']
                elif kind=='active3':changed['tabletWebUIKitContinuationVersion']=3
                elif kind=='segment1':changed['active']['tabletWebUIKitActiveSegmentVersion']=1
                elif kind=='first-ref':changed['successor']=dict(index=129,sha256='a'*64,bytes=2,device=1,inode=1)
                elif kind=='wrong-segment':changed['active']['component']='dom'
                elif kind=='missing-active':del changed['active']
                elif kind=='raw-overflow':changed['active']['nextRaw']=1026
                else:changed['active']['nextRaw']=1
                with self.assertRaises(NativeUIError):closed.decode(changed,expected)

    def test_initial_first_reference_must_equal_actual_retained_first_global_record(self):
        value,expected,_raw=existing.TabletUIKitSegmentMetadataTests().value()
        value['tabletWebUIKitContinuationVersion']=4;value['active']['tabletWebUIKitActiveSegmentVersion']=2
        closed.decode(value,expected)
        for kind in ('missing-first','foreign-first','cap','gap','borrow-new-segment','borrow-old-segment'):
            with self.subTest(kind=kind):
                changed=deepcopy(value)
                if kind=='missing-first':changed['successor']=None
                elif kind=='foreign-first':changed['active']['records'][0]['inode']+=1
                elif kind=='cap':changed['active']['records']*=129
                elif kind=='gap':changed['active']['records'][0]['index']=130
                elif kind=='borrow-new-segment':changed['tabletWebUIKitContinuationVersion']=3
                else:changed['active']['tabletWebUIKitActiveSegmentVersion']=1
                with self.assertRaises(NativeUIError):closed.decode(changed,expected)


if __name__=='__main__':unittest.main()
