"""Bound active DOM component with real original files, modeled native transport.

The fixture's explicit prefix/large-tail builder is not a full Journey or a
native timing qualification. Actual inherited capture/recovery paths are used
where this class claims query behavior.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
import unittest
from unittest.mock import patch
import zlib

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import tablet_web_dom_segment as active,tablet_web_child_rotation as parent,tablet_web_dom_continuation as codec
from ios.adapters.tablet_web_packets import TabletWebPackets
from ios.self_tests import test_ios_tablet_web_dom_continuation as existing
from ios.self_tests.test_ios_emote_sources import BINDING
from ios.self_tests.test_ios_tablet_web_sources import RUN,ROOT


class TabletDOMSegmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):existing.TabletDOMContinuationTests.setUpClass()

    def setUp(self):
        self.f=existing.TabletDOMContinuationTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.allowed=[True]
        self.current_guard=lambda:self.allowed[0]

    def bound(self):
        f=self.f.build();closed=f.complete();ref,_packet=f.model_row(129,129);closed.bind_successor(ref)
        return f

    def arguments(self):
        s=self.f.source
        return (s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,self.current_guard)

    def clocks(self):
        s=self.f.source
        return dict(monotonic=s.monotonic,epoch_ms=lambda:int(self.f.f.boundary.host+self.f.f.boundary.mono*1000))

    def open(self):return active.open_segment(*self.arguments(),**self.clocks())
    def reopen(self):return active.TabletDOMSegment(*self.arguments(),**self.clocks())

    def test_actual_row130_query_uses_bound129_and_existing_durable_before_send_path(self):
        f=self.bound();before=f.originals();counts=f.native_counts();owner=self.open()
        self.assertEqual(before,f.originals());self.assertEqual(counts,f.native_counts());reader=f.f.boundary.reader('dom');send=reader.send
        seen=[]
        def actual(query):
            pending=owner.store.read()['active']['pending']
            self.assertEqual(130,pending['index']);self.assertEqual('issued',pending['status'])
            self.assertEqual(query,pending['query']);self.assertFalse(pending['sendReturned']);seen.append(True)
            return send(query)
        reader.send=actual;value=owner.capture(reader)
        self.assertEqual([True],seen);self.assertEqual(130,value['sequence'])
        self.assertEqual([129,130],[row['index'] for row in owner.state['records']]);self.assertEqual(131,owner.state['nextRaw'])
        counts=f.native_counts();reopened=self.reopen();self.assertEqual(value,reopened.history()[-1]);self.assertEqual(counts,f.native_counts())
        self.assertEqual(131,reopened._next_index());s=f.source
        with self.assertRaises(NativeUIError):parent.restore(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock)
        with self.assertRaises(NativeUIError):TabletWebPackets(s.root,s.binding,s.run,s.role,s.fixture,s.pid,'dom',lambda:True,historical=True)
        inventory=f.inventory();self.allowed[0]=False
        with self.assertRaises(NativeUIError):reopened.capture(f.f.boundary.reader('dom'))
        self.assertEqual(inventory,f.inventory());self.assertEqual(counts,f.native_counts())
        self.allowed[0]=True;reopened._current_guard=lambda:True
        with self.assertRaises(NativeUIError):reopened.history()

    def test_active128_capacity_stops_before_row257_without_native_or_raw_reset(self):
        f=self.bound();owner=self.open();value=deepcopy(owner.closed.state);refs=value['active']['records'];cursor=value['active']['nextRaw']
        for index in range(130,257):
            reference,packet=f.model_row(index,cursor);refs.append(reference);cursor+=1
        value['active']['nextRaw']=cursor;owner.store.write(value,owner.closed.state)
        owner=self.reopen();self.assertEqual(128,len(owner.state['records']));self.assertEqual(256,owner.history()[-1]['sequence'])
        self.assertEqual((257,257),(owner._next_index(),owner.state['nextRaw']));counts=f.native_counts();inventory=f.inventory()
        with self.assertRaises(NativeUIError):owner.capture(f.f.boundary.reader('dom'))
        self.assertEqual(counts,f.native_counts());self.assertEqual(inventory,f.inventory());self.assertIsNone(owner.state['pending'])

    def test_lost_open_and_issued_CAS_returns_do_not_reopen_lower_head_or_send_unknown_query(self):
        f=self.bound();write=PrivateFeatureState.write;lost=[];counts=f.native_counts()
        def opened(store,value,previous):
            result=write(store,value,previous)
            if store.path==f.dom.store.path and value.get('tabletWebDOMContinuationVersion')==3:
                lost.append(True);raise OSError('Modeled lost successful segment-open CAS')
            return result
        with patch.object(PrivateFeatureState,'write',opened),self.assertRaises(OSError):self.open()
        self.assertEqual([True],lost);self.assertEqual(counts,f.native_counts());owner=self.reopen()
        with self.assertRaises(NativeUIError):self.open()
        self.assertEqual(130,owner._next_index());lost.clear()
        def issued(store,value,previous):
            result=write(store,value,previous);pending=value.get('active',{}).get('pending')
            if store.path==f.dom.store.path and pending is not None and pending['status']=='issued' and not lost:
                lost.append(deepcopy(pending));raise OSError('Modeled lost issued-journal CAS before send')
            return result
        with patch.object(PrivateFeatureState,'write',issued),self.assertRaises((OSError,NativeUIError)):
            owner.capture(f.f.boundary.reader('dom'))
        self.assertEqual(1,len(lost));self.assertEqual(counts,f.native_counts());reopened=self.reopen()
        self.assertEqual(lost[0],reopened.state['pending']);self.assertEqual(130,reopened.state['pending']['index'])
        with self.assertRaises(NativeUIError):reopened.capture(f.f.boundary.reader('dom'))
        self.assertEqual(counts,f.native_counts());self.assertEqual(3,reopened.closed.state['tabletWebDOMContinuationVersion'])

    def test_complete_global130_original_after_lost_write_return_recovers_without_query(self):
        f=self.bound();owner=self.open();intent=owner.originals.intent
        def lost(kind,value):
            intent(kind,value)
            if kind=='original' and value['phase']=='saved':raise OSError('Modeled lost complete frame return')
        owner.originals.intent=lost
        with self.assertRaises(OSError):owner.capture(f.f.boundary.reader('dom'))
        counts=f.native_counts();reopened=self.reopen();reference=deepcopy(reopened.state['recordIntent'])
        self.assertEqual(130,reference['index']);self.assertTrue(reopened.state['recordInspection']['complete']);before=f.originals()
        restored=reopened.recover_record();self.assertEqual(130,restored['index']);self.assertEqual(131,reopened._next_index())
        self.assertEqual(before,f.originals());self.assertEqual(counts,f.native_counts());self.assertIsNone(reopened.state['pending'])
        self.assertEqual(130,reopened.history()[-1]['sequence'])

    def test_lost_send_return_stays_owned_after_archiving_and_never_admits_new_query(self):
        f=self.bound();owner=self.open();f.f.boundary.lost='dom'
        with self.assertRaises(NativeUIError):owner.capture(f.f.boundary.reader('dom'))
        counts=f.native_counts();owner=self.reopen();pending=deepcopy(owner.state['pending'])
        self.assertEqual('failed',pending['status']);self.assertEqual(130,pending['index']);self.assertFalse(pending['sendReturned'])
        with self.assertRaises(NativeUIError):owner.capture(f.f.boundary.reader('dom'))
        ref=owner.archive_pending(abandon=True);row=owner.originals.read(owner.originals.expand(ref))
        self.assertEqual(pending['query'],row['query']);self.assertEqual(pending['before'],row['before']);self.assertEqual(pending['after'],row['after'])
        self.assertEqual('abandoned',row['status']);owner.history();self.assertTrue(owner.blocked)
        with self.assertRaises(NativeUIError):owner.capture(f.f.boundary.reader('dom'))
        self.assertEqual(counts,f.native_counts());self.assertEqual(130,owner.state['nextRaw']);self.assertEqual(129,owner.history()[-1]['sequence'])


class TabletDOMSegmentMetadataTests(unittest.TestCase):
    """Metadata syntax only: synthetic refs provide no native/file authority."""
    def value(self,version,legacy):
        expected=codec.base.scope(BINDING,RUN,'actor',ROOT,31)
        def reference(index):return dict(index=index,sha256='a'*64,bytes=2,device=1,inode=index)
        old=dict(tabletWebPacketsVersion=legacy,**expected,component='dom',nextRaw=129,
            records=[reference(index) for index in range(1,129)],pending=None,recordIntent=None,recordInspection=None)
        raw=(json.dumps(old,indent=1)+'\n').encode()
        def signature(size):return dict(device=1,inode=1,mode=0o100600,uid=0,gid=0,nlink=1,bytes=size,mtimeNs=1,ctimeNs=1)
        value=dict(tabletWebPacketsVersion=3,tabletWebDOMContinuationVersion=version,profile=codec.PROFILE,phase='rotating',scope=expected,
            parent=dict(signature=signature(1),sha256='b'*64),previousHeader=dict(signature=signature(len(raw)),bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest(),data=base64.b64encode(zlib.compress(raw)).decode()),
            copyIntent=None,manifests=[],manifestIntent=None)
        if version>=2:value['successor']=None
        if version>=3:
            value['successor']=reference(129)
            value['copyIntent']=dict(tabletWebClosedHeaderOriginalVersion=1,kind='sources',binding=BINDING,runId=RUN,role='actor',
                index=1,sha256='c'*64,bytes=2,phase='saved',file=dict(device=1,inode=1))
            value['manifests']=[dict(block=1,count=128,sha256='d'*64,bytes=2)]
            value['active']=dict(tabletWebDOMActiveSegmentVersion=1,**expected,component='dom',firstIndex=129,nextRaw=130,
                records=[reference(129)],pending=None,recordIntent=None,recordInspection=None)
        return value,expected,raw

    def test_literal_metadata1_and2_keep_old_header_bytes_without_file_or_native_authority(self):
        for version in (1,2):
            with self.subTest(version=version):
                value,expected,raw=self.value(version,version);before=deepcopy(value)
                with patch('adapters.original_frame_store.OriginalFrameStore.__init__',side_effect=AssertionError('No store from syntax')):
                    actual,_old=codec.decode(value,expected)
                self.assertEqual(raw,actual);self.assertEqual(before,value)

    def test_active_segment_metadata_refuses_cap_growth_raw_overflow_and_index_reset(self):
        value,expected,_raw=self.value(3,2);codec.decode(value,expected)
        for kind in ('cap','raw','reset','gap','generation'):
            with self.subTest(kind=kind):
                changed=deepcopy(value)
                if kind=='cap':changed['active']['records']*=129
                elif kind=='raw':changed['active']['nextRaw']=1026
                elif kind=='reset':changed['active']['firstIndex']=1
                elif kind=='gap':changed['active']['records'].append(deepcopy(changed['active']['records'][0]))
                else:
                    changed['active']['binding']=deepcopy(changed['active']['binding'])
                    changed['active']['binding']['generation']+=1
                with self.assertRaises(NativeUIError):codec.decode(changed,expected)


if __name__=='__main__':unittest.main()
