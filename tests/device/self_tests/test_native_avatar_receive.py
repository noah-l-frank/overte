"""Received source originals at a synthetic transport boundary; no network/device."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from adapters.native_avatar_receive import NativeAvatarReceive,ACTION,validate,motion
from adapters.normal_ui import NativeUIError


def record(sequence,position):
    return dict(receiveSequence=sequence,capturedEpochMs=19000+sequence,avatarSha256='b'*64,mixerSha256='c'*64,
        recordSha256=str(sequence)*64,recordBytes=123,carriesJoints=True,jointCount=1,
        joints=[dict(index=0,rotation=[0.,0.,0.,1.],translation=[position,0.,0.])],
        advertisedModelUrl='https://fixture.test/avatar.fst',targetScale=1.)


class Boundary:
    def __init__(self):self.sequence=0;self.current=None;self.commands=[];self.clock=0.;self.records=[];self.mutate=lambda v:None
    def send(self,request):
        self.commands.append(deepcopy(request));self.sequence+=1
        self.current=dict(avatarReceiveObservationVersion=1,commandId=request['commandId'],instance='a'*32,
            sequence=self.sequence,processId=31,requestedEpochMs=20000,capturedEpochMs=20000,
            source=dict(avatarReceiveVersion=1,instance='d'*32,processId=31,selfSha256='a'*64,complete=True,
                receiveSequence=len(self.records),droppedRecords=0,records=deepcopy(self.records)))
        self.mutate(self.current)
    def sleep(self,n):self.clock+=n
    def reader(self):return NativeAvatarReceive(self.send,lambda:json.dumps(self.current),lambda:20000,lambda:True,31,
        ios=True,monotonic=lambda:self.clock,sleep=self.sleep)


class NativeAvatarReceiveTests(unittest.TestCase):
    def test_actual_received_pose_changes_are_separate_from_requested_or_outgoing_values(self):
        boundary=Boundary();reader=boundary.reader();first=reader.read(0)
        boundary.records=[record(1,.1),record(2,.2)];second=reader.read(1)
        rows=motion(first['source'],second['source'],'b'*64)
        self.assertEqual(2,len(rows));self.assertNotIn('animation',str(rows));self.assertNotIn('pose',str(boundary.commands))
    def test_foreign_sender_self_echo_or_missing_joint_packet_cannot_supply_peer_effect(self):
        for fault in ('foreign','self','no-joints'):
            boundary=Boundary();reader=boundary.reader();first=reader.read(0);boundary.records=[record(1,.1),record(2,.2)]
            if fault=='self':boundary.records[0]['avatarSha256']='a'*64
            if fault=='no-joints':boundary.records[1]['carriesJoints']=False
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                second=reader.read(1);motion(first['source'],second['source'],'f'*64 if fault=='foreign' else 'b'*64)
    def test_retimed_or_changed_accepted_record_and_source_birth_are_rejected(self):
        for fault in ('time','pose','birth','root','pid'):
            boundary=Boundary();boundary.records=[record(1,.1)];reader=boundary.reader();reader.read(0)
            if fault=='time':boundary.records[0]['capturedEpochMs']+=1
            if fault=='pose':boundary.records[0]['joints'][0]['translation'][0]+=.1
            if fault=='birth':boundary.mutate=lambda v:v['source'].update(instance='e'*32)
            if fault=='root':boundary.mutate=lambda v:v.update(instance='e'*32)
            if fault=='pid':boundary.mutate=lambda v:v['source'].update(processId=99)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(1)
    def test_antipodal_quaternion_and_frozen_translation_are_not_motion(self):
        boundary=Boundary();reader=boundary.reader();first=reader.read(0);boundary.records=[record(1,.1),record(2,.1)]
        boundary.records[1]['joints'][0]['rotation']=[0.,0.,0.,-1.];second=reader.read(1)
        with self.assertRaises(NativeUIError):motion(first['source'],second['source'],'b'*64)
    def test_default_pose_nulls_cannot_be_filled_with_expected_joints(self):
        boundary=Boundary();reader=boundary.reader();first=reader.read(0);boundary.records=[record(1,.1),record(2,.2)]
        for row in boundary.records:row['joints'][0].update(rotation=None,translation=None)
        second=reader.read(1)
        with self.assertRaises(NativeUIError):motion(first['source'],second['source'],'b'*64)
    def test_reconstruction_restores_only_original_cursor_without_query(self):
        boundary=Boundary();boundary.records=[record(1,.1)];first=boundary.reader().read(0)
        reader=boundary.reader();reader.restore(first);self.assertEqual(1,len(boundary.commands));reader.read(1)
        self.assertEqual(2,len(boundary.commands))

if __name__=='__main__':unittest.main()
