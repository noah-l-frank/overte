"""Real segmented originals; native file-work and its clocks are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import json
import os
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import canonical
from ios.adapters import feature_observation,snapshot_file_work as source
from ios.adapters.snapshot_file_work_packet import SnapshotFileWorkPacket
from ios.self_tests.test_ios_snapshot_owned_packet import SnapshotOwnedPackets
from ios.self_tests.test_ios_snapshot_file_work import Jobs
from ios.self_tests.test_ios_snapshot_owned_files import RUN


class SnapshotFileWorkPackets(unittest.TestCase):
    def setUp(self):
        self.f=SnapshotOwnedPackets();self.f.setUp();self.addCleanup(self.f.doCleanups);self.jobs=Jobs();self.callbacks=[]
        self.f.model.now=self.jobs.now;self.raw=None;self.calls=[]
        self.f.transport.execute=self.execute
        actual=patch.object(feature_observation,'post_request',self.post);actual.start();self.addCleanup(actual.stop)
    def post(self,request,timeout):
        q=self.f.transport.fixture.set_client_command(json.loads(request.data));self.calls.append(q)
        self.f.transport.echo=json.dumps(q).encode();packet=self.jobs.read(q);self.f.model.now=self.jobs.now
        self.raw=json.dumps(packet,separators=(',',':'));return self.f.transport
    def execute(self,session,operation,arguments):
        self.assertEqual('mobile: pullFile',operation);self.assertTrue(arguments['remotePath'].endswith('/'+source.FILE))
        return base64.b64encode((self.raw or '').encode()).decode()
    def owner(self,index=1):
        f=self.f
        return SnapshotFileWorkPacket(PrivateFeatureState(f.root/('ios-snapshot-primary-native-filework-'+format(index,'04d')+'.json')),
            f.lock,f.binding,RUN,'primary',index,f.feature,f.native(),lambda:True,
            epoch_ms=lambda:f.model.now,monotonic=lambda:(f.model.now-10000)/1000)
    def history(self,index=1):
        return SnapshotFileWorkPacket.history(PrivateFeatureState(self.f.root/('ios-snapshot-primary-native-filework-'+format(index,'04d')+'.json')),
            self.f.lock,self.f.binding,RUN,'primary',index)
    def add_job(self,read=False):
        callback,q=self.jobs.queued()
        if read:q.update(operation='read',name=q['prefix']+'-snap_1700000000000_1.png',revision='c'*64,offset=0)
        callback();self.callbacks.append(callback);self.f.model.now=self.jobs.now;return q
    def captured(self,index=1):
        owner=self.owner(index);owner.reserve();owner.send();return owner,owner.retain()

    def test_actual_raw_parts_preserve_original_and_history_never_touches_sdk(self):
        q=self.add_job();self.callbacks.clear()
        with self.f.lock.held():
            owner,frame=self.captured();self.assertEqual(self.raw,frame['raw']);owner.qualified();source.drained(frame['packet'],[q])
            self.assertEqual(frame,self.history().historical());self.assertEqual(1,len(self.calls))
            self.assertEqual(1,len(owner.state['rawParts']['chunks']))
            def forbidden(*_a,**_k):raise AssertionError('Historical work source touched SDK')
            self.f.feature.guard=self.f.feature.original=self.f.native=forbidden
            self.assertEqual(frame,self.history().historical())

    def test_largest_actual_job_ledger_uses_multiple_bounded_files_without_frame_limit_raise(self):
        for _ in range(1024):self.add_job(read=True)
        self.callbacks.clear()
        with self.f.lock.held():
            owner,frame=self.captured();self.assertEqual(1024,len(frame['packet']['source']['jobs']))
            self.assertGreater(len(canonical(frame)),1024*1024)
            self.assertGreater(len(owner.state['rawParts']['chunks']),1)
            for ref in owner.state['rawParts']['chunks']:
                path=owner.parts().store.path(ref);self.assertLess(path.stat().st_size,1024*1024)
                self.assertEqual(0o600,path.stat().st_mode&0o777)
            self.assertLess(owner.store.path.stat().st_size,65536)
            body=owner.files().store.read(owner.state['storage']);self.assertNotIn('packet',body);self.assertNotIn('raw',body)
            self.assertEqual(frame,self.history().historical());self.assertEqual(1,len(self.calls))

    def test_partial_empty_opened_raw_is_frozen_and_cannot_be_rewritten_on_recovery(self):
        with self.f.lock.held():
            owner=self.owner();owner.reserve();owner.send();callback=owner.part_intent;lost=[False]
            def interrupted(parent):
                callback(parent)
                if parent['chunks'] and parent['chunks'][-1]['phase']=='opened' and not lost[0]:lost[0]=True;raise OSError('Lost raw opened return')
            owner.part_intent=interrupted
            with self.assertRaises(OSError):owner.retain()
            again=self.owner();parent=again.state['rawParts'];path=again.parts().store.path(parent['chunks'][0]);self.assertEqual(b'',path.read_bytes())
            self.assertEqual(0,again.state['snapshots'][0]['bytes']);before=path.stat()
            with self.assertRaises(NativeUIError):again.retain()
            self.assertEqual(before,path.stat());self.assertEqual(1,len(self.calls))
            with path.open('ab') as stream:stream.write(b'{')
            with self.assertRaises(NativeUIError):self.owner()

    def test_complete_raw_after_lost_flush_is_adopted_without_new_afc_or_file_write(self):
        with self.f.lock.held():
            owner=self.owner();owner.reserve();owner.send();fsync=os.fsync
            def lost(descriptor):
                if 'snapshot-primary-file-work-parts-frame-' in os.readlink('/proc/self/fd/'+str(descriptor)):raise OSError('Lost complete raw flush')
                return fsync(descriptor)
            with patch('os.fsync',side_effect=lost),self.assertRaises(OSError):owner.retain()
            again=self.owner();parent=again.state['rawParts'];path=again.parts().store.path(parent['chunks'][0]);before=path.stat();raw=path.read_bytes()
            def forbidden(*_a,**_k):raise AssertionError('Repeated original AFC read')
            again.feature.original=forbidden;frame=again.retain();self.assertEqual(self.raw,frame['raw'])
            self.assertEqual(before,path.stat());self.assertEqual(raw,path.read_bytes());self.assertEqual(1,len(self.calls))

    def test_owner_index_role_and_query_tag_cannot_relabel_existing_raw(self):
        with self.f.lock.held():
            owner,frame=self.captured();parent=deepcopy(owner.state['rawParts']);parent['tag']='f'*64
            with self.assertRaises(NativeUIError):owner.parent(parent,frame['query'])
            other=self.owner(2)
            with self.assertRaises(NativeUIError):other.parent(owner.state['rawParts'],frame['query'])
            path=owner.parts().store.path(owner.state['rawParts']['chunks'][0]);path.write_bytes(path.read_bytes()+b' ')
            with self.assertRaises(NativeUIError):self.history()


def load_tests(loader,tests,pattern):return loader.loadTestsFromTestCase(SnapshotFileWorkPackets)


if __name__=='__main__':unittest.main()
