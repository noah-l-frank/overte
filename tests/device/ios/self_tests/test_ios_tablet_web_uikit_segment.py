"""UIKit continuation through real private originals and modeled native input.

The bounded prefix builder is not a Journey or native timing qualification.
Actual inherited capture/recovery paths own every claimed passive query.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import tablet_web_uikit_segment as active,tablet_web_uikit_continuation as closed
from ios.adapters import tablet_web_child_rotation as parent
from ios.adapters.tablet_web_packets import TabletWebPackets
from ios.self_tests import test_ios_tablet_web_uikit_continuation as existing


class TabletUIKitSegmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):existing.TabletUIKitContinuationTests.setUpClass()

    def setUp(self):
        self.base=existing.TabletUIKitContinuationTests();self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.source=self.base.source;self.evidence=self.base.f;self.boundary=self.evidence.f.boundary
        self.allowed=[True];self.current_guard=lambda:self.allowed[0]

    def bound(self):
        self.base.build();prefix=self.base.complete();reference,_packet=self.base.model_row(129,129)
        prefix.bind_successor(reference);return prefix

    def arguments(self):
        s=self.source
        return s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,self.current_guard

    def clocks(self):
        return dict(monotonic=self.source.monotonic,epoch_ms=lambda:int(self.boundary.host+self.boundary.mono*1000))

    def open(self):return active.open_segment(*self.arguments(),**self.clocks())
    def reopen(self):return active.TabletUIKitSegment(*self.arguments(),**self.clocks())

    def test_actual_UIKit130_preserves_all_contacts_and_durable_before_send_then_historical_Source_tails(self):
        prefix=self.bound();old_body=deepcopy(prefix.body());old_raw=closed.decode(prefix.state,prefix.expected)[0]
        before=self.evidence.originals();counts=self.evidence.native_counts();owner=self.open()
        self.assertEqual(before,self.evidence.originals());self.assertEqual(counts,self.evidence.native_counts())
        self.assertEqual(old_body,owner.closed.body());self.assertEqual(old_raw,closed.decode(owner.closed.state,prefix.expected)[0])
        reader=self.boundary.reader('uikit');send=reader.send;seen=[]
        def actual(query):
            pending=owner.store.read()['active']['pending'];self.assertEqual(130,pending['index'])
            self.assertEqual('issued',pending['status']);self.assertEqual(query,pending['query'])
            self.assertFalse(pending['sendReturned']);seen.append(True);return send(query)
        reader.send=actual;value=owner.capture(reader)
        self.assertEqual([True],seen);self.assertEqual(130,value['sequence'])
        self.assertEqual([129,130],[row['index'] for row in owner.state['records']]);self.assertEqual(131,owner.state['nextRaw'])
        counts=self.evidence.native_counts();inventory=self.evidence.inventory();reopened=self.reopen();history=reopened.history()
        self.assertEqual(value,history[-1]);self.assertEqual(131,reopened._next_index())
        self.assertEqual(owner.state['records'][0],reopened.reference(129));self.assertEqual(owner.closed.old['records'][127],reopened.reference(128))
        for key in ('objects','targets','contacts','dispatches','pendingDispatches'):
            self.assertEqual(value[key],history[-1][key])
        s=self.source;historical=parent.restore(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)
        self.assertTrue(historical['historicalOnly']);self.assertEqual('rotating',historical['phase'])
        self.assertEqual(value,historical['children']['uikit']);self.assertEqual(130,historical['children']['dom']['sequence'])
        self.assertEqual(1,historical['frames'][0]['touches']['sequence']);self.assertEqual(1,historical['globalIndex'])
        with patch('ios.adapters.tablet_web_packets.OriginalFrameStore',side_effect=AssertionError('No lower frame factory')), \
             patch('ios.adapters.tablet_web_packets.TabletWebSourceSegments',side_effect=AssertionError('No lower raw factory')):
            with self.assertRaises(NativeUIError):TabletWebPackets(s.root,s.binding,s.run,s.role,s.fixture,s.pid,'uikit',lambda:True,historical=True)
        self.assertEqual(counts,self.evidence.native_counts());self.assertEqual(inventory,self.evidence.inventory())
        self.allowed[0]=False
        with self.assertRaises(NativeUIError):reopened.capture(self.boundary.reader('uikit'))
        self.assertEqual(counts,self.evidence.native_counts());self.assertEqual(inventory,self.evidence.inventory())
        self.allowed[0]=True;reopened._current_guard=lambda:True
        with self.assertRaises(NativeUIError):reopened.history()
        with self.assertRaises(NativeUIError):self.base.dom.history()

    def test_lost_open_and_issued_CAS_keep_query_responsibility_after_archiving_without_resend(self):
        self.bound();write=PrivateFeatureState.write;lost=[];counts=self.evidence.native_counts()
        def opened(store,value,previous):
            result=write(store,value,previous)
            if store.path==self.base.uikit.store.path and value.get('tabletWebUIKitContinuationVersion')==3:
                lost.append(True);raise OSError('Modeled lost successful UIKit segment-open CAS')
            return result
        with patch.object(PrivateFeatureState,'write',opened),self.assertRaises(OSError):self.open()
        self.assertEqual([True],lost);self.assertEqual(counts,self.evidence.native_counts());owner=self.reopen()
        with self.assertRaises(NativeUIError):self.open()
        self.assertEqual(130,owner._next_index());lost.clear()
        def issued(store,value,previous):
            result=write(store,value,previous);pending=value.get('active',{}).get('pending')
            if store.path==owner.store.path and pending is not None and pending['status']=='issued' and not lost:
                lost.append(deepcopy(pending));raise OSError('Modeled lost UIKit issued-journal CAS before send')
            return result
        with patch.object(PrivateFeatureState,'write',issued),self.assertRaises((OSError,NativeUIError)):
            owner.capture(self.boundary.reader('uikit'))
        self.assertEqual(1,len(lost));self.assertEqual(counts,self.evidence.native_counts());reopened=self.reopen()
        pending=deepcopy(reopened.state['pending']);self.assertEqual(lost[0]['query'],pending['query'])
        self.assertEqual(lost[0]['before'],pending['before']);self.assertFalse(pending['sendReturned'])
        with self.assertRaises(NativeUIError):reopened.capture(self.boundary.reader('uikit'))
        reference=reopened.archive_pending(abandon=True);row=reopened.originals.read(reopened.originals.expand(reference))
        self.assertEqual(pending['query'],row['query']);self.assertEqual(pending['before'],row['before'])
        self.assertEqual(pending['after'],row['after']);self.assertEqual('abandoned',row['status'])
        reopened.history();self.assertTrue(reopened.blocked);self.assertEqual(130,reopened.state['nextRaw'])
        with self.assertRaises(NativeUIError):reopened.capture(self.boundary.reader('uikit'))
        s=self.source
        with self.assertRaises(NativeUIError):parent.restore(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)
        self.assertEqual(counts,self.evidence.native_counts());self.assertEqual(3,reopened.closed.state['tabletWebUIKitContinuationVersion'])

    def test_complete_original130_after_lost_return_recovers_exact_file_without_query_or_raw_reset(self):
        self.bound();owner=self.open();intent=owner.originals.intent
        def lost(kind,value):
            intent(kind,value)
            if kind=='original' and value['phase']=='saved':raise OSError('Modeled lost complete UIKit130 original return')
        owner.originals.intent=lost
        with self.assertRaises(OSError):owner.capture(self.boundary.reader('uikit'))
        counts=self.evidence.native_counts();reopened=self.reopen();reference=deepcopy(reopened.state['recordIntent'])
        self.assertEqual(130,reference['index']);self.assertTrue(reopened.state['recordInspection']['complete']);before=self.evidence.originals()
        restored=reopened.recover_record();self.assertEqual(130,restored['index']);self.assertEqual(131,reopened._next_index())
        self.assertEqual(before,self.evidence.originals());self.assertEqual(counts,self.evidence.native_counts())
        self.assertIsNone(reopened.state['pending']);self.assertEqual(131,reopened.state['nextRaw'])
        self.assertEqual(130,reopened.history()[-1]['sequence'])


class TabletUIKitSegmentMetadataTests(unittest.TestCase):
    """Synthetic syntax only, never actual original/native authority."""
    def value(self):
        value,expected,raw=existing.TabletUIKitContinuationMetadataTests().value(2,2)
        value['tabletWebUIKitContinuationVersion']=3
        value['copyIntent']=dict(tabletWebClosedHeaderOriginalVersion=1,kind='sources',binding=deepcopy(expected['binding']),
            runId=expected['runId'],role=expected['role'],index=1,sha256='c'*64,bytes=2,phase='saved',file=dict(device=1,inode=1))
        value['manifests']=[dict(block=1,count=128,sha256='d'*64,bytes=2)]
        value['active']=dict(tabletWebUIKitActiveSegmentVersion=1,**deepcopy(expected),component='uikit',firstIndex=129,nextRaw=130,
            records=[deepcopy(value['successor'])],pending=None,recordIntent=None,recordInspection=None)
        return value,expected,raw

    def test_active3_keeps_literal_old_bytes_and_exact_cap_raw_binding_and_first_ref(self):
        value,expected,raw=self.value();actual,_old=closed.decode(value,expected);self.assertEqual(raw,actual)
        for kind in ('cap','raw','reset','gap','generation','reference'):
            with self.subTest(kind=kind):
                changed=deepcopy(value)
                if kind=='cap':changed['active']['records']*=129
                elif kind=='raw':changed['active']['nextRaw']=1026
                elif kind=='reset':changed['active']['firstIndex']=1
                elif kind=='gap':changed['active']['records'].append(deepcopy(changed['active']['records'][0]))
                elif kind=='generation':changed['active']['binding']['generation']+=1
                else:changed['active']['records'][0]['inode']+=1
                with self.assertRaises(NativeUIError):closed.decode(changed,expected)

    def test_bound2_cannot_adopt_active_fields_or_incomplete_closed_manifest(self):
        value,expected,_raw=self.value();changed=deepcopy(value);changed['tabletWebUIKitContinuationVersion']=2
        with self.assertRaises(NativeUIError):closed.decode(changed,expected)
        for kind in ('missing-copy','partial-manifest','manifest-intent'):
            with self.subTest(kind=kind):
                changed=deepcopy(value)
                if kind=='missing-copy':changed['copyIntent']=None
                elif kind=='partial-manifest':changed['manifests'][0]['count']=127
                else:changed['manifestIntent']=dict(tabletWebSourcePacketManifestVersion=1,reference=dict(changed['manifests'][0],count=129),phase='planned')
                with self.assertRaises(NativeUIError):closed.decode(changed,expected)


if __name__=='__main__':unittest.main()
