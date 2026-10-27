"""Seven whitelisted native channels: syntax, real originals and modeled IO."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zlib

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from adapters.original_file_reads import scope as actual_reads
from adapters.script_feature.lock import ScriptSourceLock
from adapters.script_feature.history import canonical
from ios.adapters import tablet_web_native_child_continuation as closed,tablet_web_child_rotation as parent
from ios.adapters.tablet_web_packets import TabletWebPackets
from ios.adapters.tablet_web_source_owner import FRAME_KEYS
from ios.adapters import tablet_web_native_semantics as semantics,tablet_web_record_cache as record_cache
from ios.adapters.tablet_web_segments import TabletWebSourceSegments,CHUNK_BYTES,sha
from ios.self_tests import test_ios_tablet_web_child_rotation as existing
from ios.self_tests.test_ios_emote_sources import BINDING
from ios.self_tests.test_ios_tablet_web_sources import RUN,ROOT


class TabletNativeChildMetadataTests(unittest.TestCase):
    """Synthetic refs prove only exact compatibility/fence syntax."""
    def value(self,component='sources',*,legacy=2,active=False):
        expected=closed.base.scope(BINDING,RUN,'actor',ROOT,31)
        def reference(index):return dict(index=index,sha256='a'*64,bytes=2,device=1,inode=index)
        old=dict(tabletWebPacketsVersion=legacy,**deepcopy(expected),component=component,nextRaw=129,
            records=[reference(index) for index in range(1,129)],pending=None,recordIntent=None,recordInspection=None)
        raw=(json.dumps(old,indent=1)+'\n').encode()
        def signature(size):return dict(device=1,inode=1,mode=0o100600,uid=0,gid=0,nlink=1,bytes=size,mtimeNs=1,ctimeNs=1)
        value=dict(tabletWebPacketsVersion=3,tabletWebNativeChildContinuationVersion=1,profile=closed.PROFILE,phase='rotating',scope=expected,
            component=component,parent=dict(signature=signature(2),sha256='b'*64),previousHeader=dict(signature=signature(len(raw)),
                sha256=hashlib.sha256(raw).hexdigest(),data=base64.b64encode(zlib.compress(raw)).decode(),bytes=len(raw)),
            copyIntent=None,manifests=[],manifestIntent=None,firstRecord=None,active=None)
        if active:
            value['copyIntent']=dict(tabletWebClosedHeaderOriginalVersion=1,kind='sources',binding=deepcopy(BINDING),runId=RUN,role='actor',
                index=1,sha256='c'*64,bytes=2,phase='saved',file=dict(device=1,inode=1))
            value['manifests']=[dict(block=1,count=128,sha256='d'*64,bytes=2)]
            value['active']=dict(tabletWebNativeChildActiveSegmentVersion=1,**deepcopy(expected),component=component,firstIndex=129,nextRaw=129,
                records=[],pending=None,recordIntent=None,recordInspection=None)
        return value,expected,raw

    def test_seven_literal_Packet1_and2_predecessors_keep_exact_bytes_and_explicit_empty129(self):
        for component in sorted(closed.KINDS):
            for legacy in (1,2):
                for active in (False,True):
                    with self.subTest(component=component,legacy=legacy,active=active):
                        value,expected,raw=self.value(component,legacy=legacy,active=active);before=deepcopy(value)
                        actual,old=closed.decode(value,expected,component)
                        self.assertEqual(raw,actual);self.assertEqual(component,old['component']);self.assertEqual(before,value)

    def test_unknown_component_wrong_root_kind_raw_reset_cap_and_first_reference_mismatch_fail(self):
        value,expected,_raw=self.value(active=True)
        for component in ('dom','uikit','../sources',True,[],None):
            with self.subTest(component=component),self.assertRaises(NativeUIError):closed.decode(value,expected,component)
        for kind in ('foreign-component','foreign-binding','raw-reset','raw-overflow','index-reset','unbound-first','copy-missing','partial-manifest'):
            with self.subTest(kind=kind):
                changed=deepcopy(value)
                if kind=='foreign-component':changed['component']='trace'
                elif kind=='foreign-binding':changed['scope']['binding']['generation']+=1
                elif kind=='raw-reset':changed['active']['nextRaw']=1
                elif kind=='raw-overflow':changed['active']['nextRaw']=1026
                elif kind=='index-reset':changed['active']['firstIndex']=1
                elif kind=='unbound-first':changed['firstRecord']=dict(index=129,sha256='a'*64,bytes=2,device=1,inode=129)
                elif kind=='copy-missing':changed['copyIntent']=None
                else:changed['manifests'][0]['count']=127
                with self.assertRaises(NativeUIError):closed.decode(changed,expected,'sources')
        first=dict(index=129,sha256='a'*64,bytes=2,device=1,inode=129)
        value['firstRecord']=deepcopy(first);value['active']['records']=[deepcopy(first)];value['active']['nextRaw']=130
        closed.decode(value,expected,'sources')
        for kind in ('foreign-ref','gap','cap','missing-first'):
            with self.subTest(kind=kind):
                changed=deepcopy(value)
                if kind=='foreign-ref':changed['active']['records'][0]['inode']+=1
                elif kind=='gap':changed['active']['records'][0]['index']=130
                elif kind=='cap':changed['active']['records']*=129
                else:changed['firstRecord']=None
                with self.assertRaises(NativeUIError):closed.decode(changed,expected,'sources')

    def test_all_seven_default_constructors_refuse_before_lower_original_factories(self):
        for component in sorted(closed.KINDS):
            with self.subTest(component=component),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);root.chmod(0o700);value,expected,_raw=self.value(component,active=True)
                store=PrivateFeatureState(root/parent._name(component,expected));store.write(value,None)
                before=(store.path.stat().st_dev,store.path.stat().st_ino,store.path.read_bytes())
                with patch('ios.adapters.tablet_web_packets.OriginalFrameStore',side_effect=AssertionError('No lower frame factory')), \
                     patch('ios.adapters.tablet_web_packets.TabletWebSourceSegments',side_effect=AssertionError('No lower raw factory')), \
                     self.assertRaises(NativeUIError):
                    TabletWebPackets(root,expected['binding'],RUN,'actor',ROOT,31,component,lambda:False,historical=True)
                self.assertEqual(before,(store.path.stat().st_dev,store.path.stat().st_ino,store.path.read_bytes()))

    def test_failed_own_graph_constructor_cannot_leave_a_live_reader_or_mutation_method(self):
        constructor=closed._OwnPrefix.__init__;retained=[]
        def actual(owner,*args,**kwargs):
            try:return constructor(owner,*args,**kwargs)
            finally:retained.append(owner)
        with tempfile.TemporaryDirectory() as directory,patch.object(closed._OwnPrefix,'__init__',actual),self.assertRaises(NativeUIError):
            closed.read_own(Path(directory),BINDING,RUN,'actor',ROOT,31,'sources',None)
        self.assertEqual(1,len(retained));self.assertFalse(retained[0].alive)
        for operation in (retained[0].guard,retained[0].copy,retained[0].index,retained[0].recover_copy,
                retained[0].recover_index,lambda:retained[0].save({})):
            with self.assertRaises(NativeUIError):operation()


class TabletNativeChildContinuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):existing.TabletChildRotationTests.setUpClass()

    def setUp(self):
        self.fixture=existing.TabletChildRotationTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.s=self.fixture.source;self.boundary=self.fixture.f.boundary;self.current_guard=lambda:True
        self.intent_store=PrivateFeatureState(self.s.root/'native-child-boundary-fixture.json');self.intent_state=None

    def intent(self,value):self.intent_store.write(value,self.intent_state);self.intent_state=deepcopy(value)

    def build(self,components):
        for component in components:
            child=self.s.children[component];refs=deepcopy(child.state['records']);cursor=child.state['nextRaw']
            parts=TabletWebSourceSegments(self.s.root,self.s.binding,self.s.run,self.s.role,component,lambda:True,self.intent,monotonic=self.s.monotonic)
            originals=OriginalFrameStore(self.s.root,self.s.binding,self.s.run,self.s.role,lambda:True,
                lambda kind,value:self.intent(dict(kind=kind,value=value)),namespace='tabletweb-'+component+'-packets',
                schema_prefix='tabletWebSourcePacket',monotonic=self.s.monotonic)
            for index in range(2,129):
                before=child.stamp();self.intent(dict(component=component,phase='modeled-query',index=index))
                packet=self.boundary.reader(component).read(self.s.run,self.s.fixture);query=deepcopy(self.boundary.sent[component])
                raw=self.boundary.raw[component].encode();parent_parts=parts.write(component,sha(canonical(query)),raw,cursor)
                after=child.stamp();row=dict(tabletWebSourcePacketVersion=2,index=index,before=before,after=after,query=query,
                    sendReturned=True,status='returned',raws=[dict(before=before,after=after,segments=parent_parts,
                        inspection=parts.inspect(parent_parts),outcome='accepted')],unsafe=[],resultSha256=sha(canonical(packet)),readbacks=[])
                refs.append(originals.write(index,row));cursor+=max(1,(len(raw)+CHUNK_BYTES-1)//CHUNK_BYTES)
            previous=deepcopy(child.state);child.state.update(records=refs,nextRaw=cursor)
            child.store.write(child.state,previous);child.saved=deepcopy(child.state);child.history()
        self.fixture.freeze()

    def prefix(self,component):
        s=self.s
        return closed.TabletNativeChildClosedPrefix(s.root,s.binding,s.run,s.role,s.fixture,s.pid,component,s.lock,monotonic=s.monotonic)

    def complete(self,component):
        value=closed.prepare(self.s,component);closed.install(self.s,component,value)
        owner=self.prefix(component);owner.copy();owner.index();return owner

    def arguments(self,component):
        s=self.s
        return s.root,s.binding,s.run,s.role,s.fixture,s.pid,component,s.lock,self.current_guard

    def clocks(self):return dict(monotonic=self.s.monotonic,epoch_ms=lambda:int(self.boundary.host+self.boundary.mono*1000))
    def open(self,component):return closed.open_initial_segment(*self.arguments(component),**self.clocks())
    def reopen(self,component):return closed.TabletNativeChildSegment(*self.arguments(component),**self.clocks())

    def full_actual129(self,component):
        self.build([component]);prefix=self.complete(component)
        raw=closed.decode(prefix.state,prefix.expected,component)[0];body=deepcopy(prefix.body())
        originals=self.fixture.originals();counts=self.fixture.native_counts();owner=self.open(component)
        self.assertEqual(originals,self.fixture.originals());self.assertEqual(counts,self.fixture.native_counts())
        reader=self.boundary.reader(component);send=reader.send;seen=[]
        def actual(query):
            state=owner.store.read();pending=state['active']['pending'];self.assertEqual(129,pending['index'])
            self.assertEqual('issued',pending['status']);self.assertEqual(query,pending['query'])
            self.assertFalse(pending['sendReturned']);self.assertIsNone(state['firstRecord'])
            self.assertFalse(list(self.s.root.glob('tabletweb-'+component+'-packets-frame-*-0129-*.json')))
            seen.append(True);return send(query)
        reader.send=actual;packet=owner.capture(reader);self.assertEqual([True],seen);self.assertEqual(129,packet['sequence'])
        self.assertEqual(129,owner.state['records'][0]['index']);self.assertEqual(owner.state['records'][0],owner.closed.state['firstRecord'])
        consumed=max(1,(len(self.boundary.raw[component].encode())+CHUNK_BYTES-1)//CHUNK_BYTES)
        self.assertEqual(prefix.old['nextRaw']+consumed,owner.state['nextRaw'])
        counts=self.fixture.native_counts();before=self.fixture.originals();reopened=self.reopen(component)
        self.assertEqual(originals,{name:value for name,value in before.items() if name in originals})
        self.assertEqual(packet,reopened.history()[-1]);self.assertEqual(before,self.fixture.originals())
        s=self.s;own=closed.read_own(s.root,s.binding,s.run,s.role,s.fixture,s.pid,component,s.lock,monotonic=s.monotonic)
        self.assertEqual(packet,own['nativeFloor']);self.assertFalse(own['peerAuthority']);self.assertTrue(own['subgraphOnly'])
        result=parent.restore(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)
        self.assertEqual(packet,result['children'][component]);self.assertEqual(1,result['globalIndex'])
        self.assertEqual(1,result['frames'][0][FRAME_KEYS.get(component,component)]['sequence'])
        self.assertEqual(raw,closed.decode(reopened.closed.state,prefix.expected,component)[0]);self.assertEqual(body,reopened.closed.body())
        self.assertEqual(before,self.fixture.originals());self.assertEqual(counts,self.fixture.native_counts())
        # A changed peer header invalidates live scope. An own-only archive
        # still proves its exact original tail without granting peer authority.
        peer=s.children['trace' if component=='sources' else 'sources'];old=peer.store.read()
        peer.store.write(old,old)
        with self.assertRaises(NativeUIError):reopened.history()
        with self.assertRaises(NativeUIError):self.reopen(component)
        with self.assertRaises(NativeUIError):parent.restore(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)
        own=closed.read_own(s.root,s.binding,s.run,s.role,s.fixture,s.pid,component,s.lock,monotonic=s.monotonic)
        self.assertEqual(packet,own['nativeFloor']);self.assertFalse(own['peerAuthority']);self.assertTrue(own['subgraphOnly'])
        self.assertEqual(before,self.fixture.originals());self.assertEqual(counts,self.fixture.native_counts())

    def test_actual_sources129_owns_first_query_before_send_and_preserves_historical_parent1(self):
        self.full_actual129('sources')

    def test_actual_trace129_owns_original_WAL_and_independent_tail_without_parent_retiming(self):
        self.full_actual129('trace')

    def test_actual_buttons129_owns_original_WAL_and_independent_tail_without_parent_retiming(self):
        self.full_actual129('buttons')

    def test_actual_state129_owns_original_WAL_and_independent_tail_without_parent_retiming(self):
        self.full_actual129('state')

    def test_actual_closures129_owns_original_WAL_and_independent_tail_without_parent_retiming(self):
        self.full_actual129('closures')

    def test_actual_emissions129_owns_original_WAL_and_independent_tail_without_parent_retiming(self):
        self.full_actual129('emissions')

    def test_actual_deferred129_owns_original_WAL_and_independent_tail_without_parent_retiming(self):
        self.full_actual129('deferred')

    def test_sources_first129_lost_open_and_original_bind_recover_exact_file_without_query_repeat(self):
        component='sources';self.build([component]);prefix=self.complete(component);write=PrivateFeatureState.write;lost=[]
        counts=self.fixture.native_counts();before=self.fixture.originals()
        def opened(store,value,previous):
            answer=write(store,value,previous)
            if store.path==prefix.store.path and value.get('tabletWebNativeChildContinuationVersion')==1 and value['active'] is not None:
                lost.append(True);raise OSError('Modeled lost successful native-child segment-open CAS return')
            return answer
        with patch.object(PrivateFeatureState,'write',opened),self.assertRaises(OSError):self.open(component)
        self.assertEqual([True],lost);owner=self.reopen(component)
        self.assertEqual(counts,self.fixture.native_counts());self.assertEqual(before,self.fixture.originals())
        with self.assertRaises(NativeUIError):self.open(component)
        intent=owner.originals.intent
        def lost_original(kind,value):
            intent(kind,value)
            if kind=='original' and value['phase']=='saved':raise OSError('Modeled lost complete native-child129 original return')
        owner.originals.intent=lost_original
        with self.assertRaises(OSError):owner.capture(self.boundary.reader(component))
        counts=self.fixture.native_counts();before=self.fixture.originals();rebuilt=self.reopen(component)
        self.assertEqual(129,rebuilt.state['recordIntent']['index']);self.assertTrue(rebuilt.state['recordInspection']['complete'])
        bound=[]
        def bound_return(store,value,previous):
            answer=write(store,value,previous)
            if store.path==rebuilt.store.path and value.get('tabletWebNativeChildContinuationVersion')==1 \
                    and previous['firstRecord'] is None and value['firstRecord'] is not None:
                bound.append(deepcopy(value['firstRecord']));raise OSError('Modeled lost successful native-child first-original bind CAS return')
            return answer
        with patch.object(PrivateFeatureState,'write',bound_return),self.assertRaises(OSError):rebuilt.recover_record()
        self.assertEqual(1,len(bound));rebuilt=self.reopen(component)
        self.assertEqual(bound[0],rebuilt.state['records'][0]);self.assertEqual(bound[0],rebuilt.closed.state['firstRecord'])
        self.assertEqual(129,rebuilt.history()[-1]['sequence']);self.assertEqual(130,rebuilt.state['nextRaw'])
        self.assertEqual(before,self.fixture.originals());self.assertEqual(counts,self.fixture.native_counts())

    def own(self,component='sources'):
        s=self.s
        return closed.read_own(s.root,s.binding,s.run,s.role,s.fixture,s.pid,component,s.lock,monotonic=s.monotonic)

    def test_sources_pure_own_batch_reads_literal_bytes_without_ambient_memos_and_expires_every_reader(self):
        self.build(['sources']);self.complete('sources');owner=self.open('sources');packet=owner.capture(self.boundary.reader('sources'))
        originals=self.fixture.originals();counts=self.fixture.native_counts();retained=[];seen=set();read=OriginalFrameStore.read
        attach=closed._OwnReadBatch.reader;attempts=[]
        def keep(batch,reader):attach(batch,reader);retained.append(reader)
        def actual(store,value):
            result=read(store,value)
            if store.namespace in ('tabletweb-sources-packets','tabletweb-sources-source-parts'):
                seen.add(store.path(value))
                if not attempts:
                    attempts.append(True);reader=retained[0]
                    for operation in (lambda:reader.capture(self.boundary.reader('sources')),reader.save,
                            lambda:reader.reconcile(self.boundary.reader('sources')),reader.archive_pending,reader.recover_record,
                            lambda:reader.originals.write(130,{}),lambda:reader.segments.write('sources','a'*64,b'{}',130),
                            lambda:self.own()):
                        with self.assertRaises(NativeUIError):operation()
            return result
        module=closed.COMPONENTS['sources'];memo=semantics.TabletNativeSemantics();records=record_cache.TabletRecordCache()
        with patch.object(module,'validate',wraps=module.validate) as validator,semantics.scope(memo),record_cache.scope(records):
            owner.history();native_before=(len(memo.entries),memo.bytes);records_before=(len(records.originals.rows),records.bytes)
            calls=validator.call_count
            with patch.object(closed._OwnReadBatch,'reader',keep),patch.object(OriginalFrameStore,'read',actual),actual_reads(fresh=True) as reads:
                proof=self.own()
            self.assertGreater(validator.call_count,calls)
            self.assertIs(memo,semantics._ACTIVE.get());self.assertIs(records,record_cache._ACTIVE.get())
            self.assertEqual(native_before,(len(memo.entries),memo.bytes));self.assertEqual(records_before,(len(records.originals.rows),records.bytes))
        expected={self.s.root/name for name in originals if name.startswith(('tabletweb-sources-packets-frame-','tabletweb-sources-source-parts-frame-'))}
        self.assertEqual(expected,seen);self.assertTrue(expected<=reads);self.assertEqual([True],attempts)
        self.assertEqual(packet,proof['nativeFloor']);self.assertTrue(proof['subgraphOnly']);self.assertFalse(proof['peerAuthority'])
        proof['nativeFloor']['sequence']=0
        self.assertEqual(packet,self.own()['nativeFloor']);self.assertIsNone(closed._OWN_READ.get())
        self.assertTrue(retained)
        for reader in retained:
            ref=reader.state['records'][0];row=owner.originals.read(owner.originals.expand(ref));raw=row['raws'][0]['segments']
            with patch('os.open',side_effect=AssertionError('Expired own reader attempted file I/O')):
                for operation in (reader.history,lambda:reader.reference(ref['index']),
                        lambda:reader.originals.read(reader.originals.expand(ref)),lambda:reader.segments.inspect(raw),
                        lambda:reader.segments.read(raw),reader.original_guard):
                    with self.assertRaises(NativeUIError):operation()
        self.assertEqual(originals,self.fixture.originals());self.assertEqual(counts,self.fixture.native_counts())

    def test_sources_pure_own_batch_rejects_census_scope_and_read_dependency_changes_even_on_exception(self):
        self.build(['sources']);self.complete('sources');owner=self.open('sources');owner.capture(self.boundary.reader('sources'))
        originals=self.fixture.originals();counts=self.fixture.native_counts();read=OriginalFrameStore.read
        foreign_tmp=tempfile.TemporaryDirectory();self.addCleanup(foreign_tmp.cleanup);foreign_root=Path(foreign_tmp.name);foreign_root.chmod(0o700)
        foreign_intent=PrivateFeatureState(foreign_root/'guard-intent.json');foreign_previous=None
        def foreign_write(kind,value):
            nonlocal foreign_previous
            state=dict(kind=kind,value=deepcopy(value));foreign_intent.write(state,foreign_previous);foreign_previous=state
        foreign=OriginalFrameStore(foreign_root,self.s.binding,self.s.run,self.s.role,lambda:True,foreign_write,
            namespace='own-foreign',schema_prefix='ownForeign',monotonic=self.s.monotonic)
        foreign_ref=foreign.write(1,dict(purpose='Unrelated actual dependency, not native evidence'))
        for kind in ('ctime','new-inode','new-entry','missing-entry','foreign-dependency','candidate','root','lock','exception','pure-exception'):
            with self.subTest(kind=kind):
                probe=PrivateFeatureState(self.s.root/('own-batch-probe-'+kind+'.json'));state=dict(probe=kind);probe.write(state,None)
                before=probe.path.stat();raw=probe.path.read_bytes();touched=[]
                def changed(store,value):
                    answer=read(store,value)
                    if store.namespace=='tabletweb-sources-packets' and not touched:
                        touched.append(True);batch=closed._OWN_READ.get();self.assertIsNotNone(batch)
                        if kind=='ctime':
                            # Timestamp tampering belongs only to this synthetic
                            # guard probe, never a native/packet original.
                            probe.path.write_bytes(raw);os.utime(probe.path,ns=(before.st_atime_ns,before.st_mtime_ns))
                            self.assertEqual(before.st_mtime_ns,probe.path.stat().st_mtime_ns)
                            self.assertNotEqual(before.st_ctime_ns,probe.path.stat().st_ctime_ns)
                        elif kind=='new-inode':probe.write(state,state)
                        elif kind=='new-entry':PrivateFeatureState(self.s.root/'own-batch-injected-new.json').write(dict(unexpected=True),None)
                        elif kind=='missing-entry':probe.path.unlink()
                        elif kind=='foreign-dependency':foreign.read(foreign.expand(foreign_ref))
                        elif kind=='candidate':batch.prefix.expected['binding']['generation']+=1
                        elif kind=='root':batch.prefix.root=foreign_root
                        elif kind=='lock':batch.prefix.lock=ScriptSourceLock(self.s.root/'own-batch-foreign-lock.json')
                        elif kind=='exception':
                            probe.path.write_bytes(raw);raise OSError('Modeled decoder interruption with changed census')
                        else:raise OSError('Modeled decoder interruption with unchanged originals')
                    return answer
                error=OSError if kind=='pure-exception' else NativeUIError
                with patch.object(OriginalFrameStore,'read',changed),self.assertRaises(error):self.own()
                self.assertEqual([True],touched);self.assertIsNone(closed._OWN_READ.get())
                self.assertEqual(originals,self.fixture.originals());self.assertEqual(counts,self.fixture.native_counts())
        # Suppressing an actual frame's read membership cannot turn a decoded
        # body into an owned dependency, even though all original bytes exist.
        dropped=[]
        with patch('adapters.original_frame_store.record_original_read',lambda path:dropped.append(path)),self.assertRaises(NativeUIError):self.own()
        self.assertTrue(dropped)  # Hook runs only after a complete literal frame read.
        self.assertIsNone(closed._OWN_READ.get());self.assertEqual(originals,self.fixture.originals());self.assertEqual(counts,self.fixture.native_counts())

    def interrupted_raw(self,*,partial):
        component='sources';self.build([component]);self.complete(component);owner=self.open(component);losses=[]
        if partial:
            intent=owner.segments.store.intent
            def lost(kind,value):
                intent(kind,value)
                if kind=='original' and value['phase']=='opened':
                    losses.append(deepcopy(value))
                    raise OSError('Modeled lost opened-empty native-child raw129 return')
            owner.segments.store.intent=lost
        else:
            write=owner.segments.write
            def lost(*args,**kwargs):
                saved=write(*args,**kwargs);losses.append(deepcopy(saved))
                raise OSError('Modeled lost complete native-child raw129 return')
            owner.segments.write=lost
        with self.assertRaisesRegex(NativeUIError,'^Original iOS world Web transcript is unavailable or invalid$'):
            owner.capture(self.boundary.reader(component))
        self.assertEqual(1,len(losses))
        failed=deepcopy(owner.state['pending']);counts=self.fixture.native_counts();before=self.fixture.originals()
        self.assertEqual('failed',failed['status']);self.assertEqual(129,failed['index'])
        self.assertTrue(failed['sendReturned']);self.assertIsNone(owner.closed.state['firstRecord'])
        self.assertEqual([],owner.state['records']);self.assertEqual(130,owner.state['nextRaw'])
        self.assertEqual(1,len(failed['raws']));self.assertEqual(129,failed['raws'][0]['segments']['first'])
        self.assertEqual(not partial,failed['raws'][0]['inspection'][0]['complete'])
        self.assertEqual(losses[0],failed['raws'][0]['segments']['chunks'][0] if partial else failed['raws'][0]['segments'])
        reopened=self.reopen(component);self.assertEqual(failed,reopened.state['pending'])
        with self.assertRaises(NativeUIError):reopened.capture(self.boundary.reader(component))
        with self.assertRaises(NativeUIError):reopened.reconcile(self.boundary.reader(component))
        self.assertEqual(failed,reopened.state['pending']);self.assertEqual(counts,self.fixture.native_counts())
        ref=reopened.archive_pending();row=reopened.originals.read(reopened.originals.expand(ref))
        self.assertEqual(failed,row);self.assertEqual(ref,reopened.closed.state['firstRecord'])
        reopened.history();self.assertTrue(reopened.blocked)
        with self.assertRaises(NativeUIError):reopened.capture(self.boundary.reader(component))
        s=self.s
        with self.assertRaises(NativeUIError):closed.read_own(s.root,s.binding,s.run,s.role,s.fixture,s.pid,component,s.lock,monotonic=s.monotonic)
        with self.assertRaises(NativeUIError):parent.restore(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)
        self.assertEqual(130,reopened.state['nextRaw']);self.assertEqual(counts,self.fixture.native_counts())
        self.assertEqual(before,{name:value for name,value in self.fixture.originals().items() if name in before})

    def test_sources_first129_complete_raw_lost_return_retains_original_failed_ownership_without_repeat(self):
        self.interrupted_raw(partial=False)

    def test_sources_first129_opened_empty_raw_lost_return_retains_partial_inode_without_recreate(self):
        self.interrupted_raw(partial=True)

    def test_sources_unknown_first_issued129_stays_blocked_after_original_archival(self):
        component='sources';self.build([component]);self.complete(component);owner=self.open(component)
        counts=self.fixture.native_counts();write=PrivateFeatureState.write;lost=[]
        def issued(store,value,previous):
            answer=write(store,value,previous);pending=value.get('active',{}).get('pending') if value.get('active') is not None else None
            if store.path==owner.store.path and pending is not None and pending['status']=='issued' and not lost:
                lost.append(deepcopy(pending));raise OSError('Modeled lost native-child first129 issued CAS return before send')
            return answer
        with patch.object(PrivateFeatureState,'write',issued),self.assertRaises((OSError,NativeUIError)):
            owner.capture(self.boundary.reader(component))
        self.assertEqual(1,len(lost));rebuilt=self.reopen(component)
        self.assertEqual(lost[0]['query'],rebuilt.state['pending']['query']);self.assertEqual(counts,self.fixture.native_counts())
        with self.assertRaises(NativeUIError):rebuilt.capture(self.boundary.reader(component))
        pending=deepcopy(rebuilt.state['pending'])
        ref=rebuilt.archive_pending(abandon=True);row=rebuilt.originals.read(rebuilt.originals.expand(ref))
        self.assertEqual('abandoned',row['status']);self.assertEqual(lost[0]['query'],row['query'])
        self.assertEqual(lost[0]['before'],row['before']);self.assertEqual(pending['after'],row['after'])
        self.assertEqual(129,rebuilt.state['nextRaw']);self.assertEqual(ref,rebuilt.closed.state['firstRecord'])
        rebuilt.history();self.assertTrue(rebuilt.blocked)
        with self.assertRaises(NativeUIError):rebuilt.capture(self.boundary.reader(component))
        s=self.s
        with self.assertRaises(NativeUIError):closed.read_own(s.root,s.binding,s.run,s.role,s.fixture,s.pid,component,s.lock,monotonic=s.monotonic)
        with self.assertRaises(NativeUIError):parent.restore(s.root,s.binding,s.run,s.role,s.fixture,s.pid,s.lock,monotonic=s.monotonic)
        self.assertEqual(counts,self.fixture.native_counts())



if __name__=='__main__':unittest.main()
