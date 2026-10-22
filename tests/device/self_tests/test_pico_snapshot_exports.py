"""Original export/lease/readback boundaries; synthetic transport only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.pico4.snapshot_exports import PicoSnapshotExports,PicoSnapshotExportIO,validate,components,continuity,lease
from adapters.pico4.snapshot_export_readbacks import command
from adapters.pico4.snapshot_export_controls import metadata
from adapters.script_journey.lock import ScriptSourceLock

RUN='a'*32


def packet(request,sequence=1,epoch=20000):
    events=dict(snapshotExportObservationVersion=2,instance='b'*32,complete=True,capturedEpochMs=epoch,elapsedMs=0,sequence=0,activeRequest='',pendingIo=[],events=[])
    copies=dict(accepted=False,source=dict(snapshotExportReadbacksVersion=1,initialized=False,complete=True))
    return dict(picoSnapshotExportsVersion=1,requestId=request['commandId'],runId=request['runId'],instance='c'*32,sequence=sequence,processId=123,
        requestedEpochMs=epoch,capturedEpochMs=epoch,lease=dict(present=False),exportsRaw=json.dumps(events),readbacksRaw=json.dumps(copies))


class IO(PicoSnapshotExportIO):
    def __init__(self):
        self.sent=[];self.latest=None;self.checks=0;self.late=lambda:None;self._before_send=None;self.reply=packet
    def guard(self):
        self.checks+=1
        if self.checks==2:self.late()
    def bind_input(self):pass
    def send(self,request):
        if self._before_send:self._before_send(deepcopy(request))
        self.sent.append(deepcopy(request));self.latest=self.reply(request,len(self.sent))
    def raw(self):return self.latest if type(self.latest) is str else json.dumps(self.latest)


class PicoSnapshotExportsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='pico-export-source-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700);self.clock=[20000,1.];self.io=IO()
        self.owner=PicoSnapshotExports(self.io,lambda:self.clock[0],123,ScriptSourceLock(self.root/'script-sources.lock'),
            monotonic=lambda:self.clock[1],sleep=lambda _:None)
        self.io._before_send=self.owner.before_publish
    def test_original_empty_java_history_is_not_a_saved_destination_or_retired_scope(self):
        value=self.owner.request(RUN);events,copies=components(value)
        self.assertEqual([],events['events']);self.assertFalse(copies['accepted']);self.assertFalse(copies['source']['initialized'])
        self.assertNotIn('workersTerminated',copies['source']);self.assertFalse(value['lease']['present'])
        self.assertEqual(1,len(self.io.sent));self.assertEqual(json.loads(self.owner.original()['raw']),value)
    def test_readonly_source_cannot_send_acquire_delete_revoke_or_retirement(self):
        for operation,request,id in (('read','b'*32,'c'*32),('remove-destination','b'*32,'c'*32),('revoke-share','b'*32,'c'*32),('retire-copies','','')):
            with self.subTest(operation=operation),self.assertRaises(NativeUIError):self.owner.request(RUN,operation,export_request=request,resource_id=id)
        self.assertEqual([],self.io.sent)
    def test_actual_last_guard_and_final_copy_cannot_refresh_old_sources_under_frozen_other_clock(self):
        for native,host in ((2000,0),(0,2)):
            self.io.checks=0;self.clock[:]=[20000,1.]
            self.io.late=lambda:setattr(self,'clock',[20000+native,1.+host])
            with self.subTest(native=native,host=host),self.assertRaises(NativeUIError):self.owner.request(RUN)
        self.assertIsNone(self.owner.last)
    def test_raw_bound_and_malformed_non_null_sources_never_fall_back_to_old_empty_history(self):
        self.owner.request(RUN);original=deepcopy(self.owner.last)
        for raw in ('x'*262145,'{bad json',json.dumps(dict(requestId='a'*32,available=False))):
            self.io.latest=raw
            def reply(request,sequence):
                if raw.startswith('{"requestId"'):return json.dumps(dict(requestId=request['commandId'],available=False))
                return raw
            self.io.reply=reply;self.io.checks=0
            with self.subTest(raw=raw[:20]),self.assertRaises((NativeUIError,ValueError)):self.owner.request(RUN)
            self.assertEqual(original,self.owner.last)
    def test_native_process_original_handles_and_closed_commands_cannot_be_replaced_by_requested_states(self):
        request=PicoSnapshotExports.envelope(RUN);value=packet(request)
        for key,bad in (('processId',True),('instance','foreign'),('sequence',True),('expectedSaved',True)):
            changed=deepcopy(value);changed[key]=bad
            with self.subTest(key=key),self.assertRaises(NativeUIError):validate(changed,request,123,20000)
        for extra in ('expectedSaved','path','uri','sha256'):
            with self.subTest(extra=extra),self.assertRaises(NativeUIError):command(dict(request,**{extra:'requested'}))
        native=dict(snapshotExportLeaseVersion=1,handle='1',ticket='2',busy=True)
        lease(dict(present=True,componentUrl='file:///packaged/system/snapshot/NativeSnapshotReview.qml',native=native))
        with self.assertRaises(NativeUIError):lease(dict(present=True,componentUrl='file:///packaged/system/snapshot/NativeSnapshotReview.qml',native=dict(native,busy=False)))
    def test_parent_publication_deadline_is_pure_host_and_prevents_slow_sdk_writer(self):
        self.owner.io._before_send=lambda request:(setattr(self,'clock',[20000,3.]),self.owner.before_publish(request))
        with self.assertRaises(NativeUIError):self.owner.request(RUN)
        self.assertEqual([],self.io.sent)
    def test_old_native_observer_or_java_history_cannot_restart_at_a_new_identity(self):
        request=PicoSnapshotExports.envelope(RUN);first=packet(request);new=packet(PicoSnapshotExports.envelope(RUN),2)
        continuity(first,new);events=json.loads(new['exportsRaw']);events['instance']='d'*32;new['exportsRaw']=json.dumps(events)
        with self.assertRaises(NativeUIError):continuity(first,new)


class PicoSnapshotExportControlTests(unittest.TestCase):
    def test_actual_path_hash_source_profile_and_dynamic_ticket_are_closed(self):
        path='/data/user/0/org.overte.pico/files/Snapshots/parity-aaaaaaaaaaaaaaaa-still-png-snap_1.png'
        row=dict(id='snapshot.save.'+hashlib.sha256(path.encode()).hexdigest(),path=path,token='a3bb8dd4-6561-4306-b01a-bd9809f3c6f2',
            enabled=True,focused=False,profile='native-pico-snapshot-export-v1',componentUrl='file:///packaged/system/snapshot/NativeSnapshotReview.qml',inputReady=True)
        metadata(row)
        for key,bad in (('path',path+'-foreign'),('id','snapshot.save.'+'f'*64),('componentUrl','file:///foreign.qml'),('expectedSaved',True)):
            changed=deepcopy(row);changed[key]=bad
            with self.subTest(key=key),self.assertRaises(NativeUIError):metadata(changed)
        cancel={key:value for key,value in row.items() if key!='path'};cancel.update(id='snapshot.cancel-export',exportTicket='2');metadata(cancel)
        cancel['exportTicket']=''
        with self.assertRaises(NativeUIError):metadata(cancel)


if __name__=='__main__':unittest.main()
