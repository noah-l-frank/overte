"""Phone original PCM-source counterexamples with an explicit native boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from overte_phone_audio_source import PhoneAudioSource,command,validate
from self_tests.test_recorded_preview_history import voice


class Boundary:
    def __init__(self):
        self.time=20.;self.sequence=0;self.calls=[];self.packet=None;self.fault=lambda value:None
        self.source=dict(inputVersion=1,armed=False,receipt={},pcmBytes=0,pcmSha256=hashlib.sha256(b'').hexdigest(),
            complete=True,cycle=0,callbacks=0,inputFrames=0,inputRate=0,inputChannels=0,firstInputEpochMs=0,lastInputEpochMs=0,
            packetEmits=0,silentEmits=0,encodedBytes=0,codec='',inputAvailable=True,lifecycleRunning=True,paused=False,muted=False,
            preview=voice([],cycle=0,started=0))
        self.native=SimpleNamespace(guard=lambda:None,pid=17,clock_ms=lambda:int(self.time*1000),send=self.send)
    def send(self,call):
        command(call);self.calls.append(deepcopy(call));self.sequence+=1
        if call['request']['operation']=='release':self.source.update(armed=False,pcmBytes=0,receipt={},pcmSha256=hashlib.sha256(b'').hexdigest())
        self.packet=dict(schemaVersion=1,requestId=call['commandId'],instance='a'*32,sequence=self.sequence,capturedEpochMs=int(self.time*1000),processId=17,
            pending=False,error='',receipt={},source=deepcopy(self.source),pendingBytes=0,revision=0)
        self.fault(self.packet)
    def reader(self,read_only=False):
        return PhoneAudioSource(self.native,lambda:json.dumps(self.packet),read_only=read_only,monotonic=lambda:self.time,sleep=lambda seconds:setattr(self,'time',self.time+seconds))


class AudioSourceTests(unittest.TestCase):
    def test_fresh_original_native_source_and_release_have_separate_read_only_absence_query(self):
        boundary=Boundary();reader=boundary.reader();self.assertFalse(reader.query()['source']['armed'])
        value=reader.release();self.assertEqual(3,value['sequence'])
        self.assertEqual(['observe','release','observe'],[row['request']['operation'] for row in boundary.calls])

    def test_actor_cannot_arm_or_release_the_input_source(self):
        boundary=Boundary();reader=boundary.reader(True)
        for action in ('arm','release'):
            with self.subTest(action=action),self.assertRaises(NativeUIError):reader.query(action)
        self.assertEqual([],boundary.calls);reader.query()

    def test_missing_native_source_foreign_process_stale_time_or_incomplete_original_history_stays_red(self):
        for fault in ('source','pid','time','history','boolean','overflow','hash'):
            with self.subTest(fault=fault):
                boundary=Boundary()
                def mutate(value):
                    if fault=='source':value['source']={}
                    elif fault=='pid':value['processId']=18
                    elif fault=='time':value['capturedEpochMs']-=1501
                    elif fault=='history':value['source']['preview']['historyComplete']=False
                    elif fault=='boolean':value['source']['callbacks']=True
                    elif fault=='overflow':value['source']['packetEmits']=4097
                    else:value['source']['pcmSha256']='0'*64
                boundary.fault=mutate
                with self.assertRaises((NativeUIError,KeyError)):boundary.reader().query()

    def test_old_or_replaced_native_instance_cannot_be_adopted_on_a_fresh_request(self):
        for fault in ('sequence','instance','clock','revision'):
            with self.subTest(fault=fault):
                boundary=Boundary();reader=boundary.reader();first=reader.query()
                def mutate(value):
                    if fault=='sequence':value['sequence']=first['sequence']
                    elif fault=='instance':value['instance']='b'*32
                    elif fault=='clock':value['capturedEpochMs']-=1
                    else:value['revision']=-1
                boundary.fault=mutate
                with self.assertRaises(NativeUIError):reader.query()

    def test_closed_command_rejects_effects_expected_values_foreign_path_redirect_and_boolean_versions(self):
        valid=dict(schemaVersion=1,commandId='a'*32,action='phone-audio-fixture',request=dict(schemaVersion=1,commandId='a'*32,operation='arm',runId='b'*32,ticket='c'*32,url='http://127.0.0.1:8000/feature-fixture/v1/runs/'+'b'*32+'/tickets/'+'c'*32+'/preview-input.v1.pcm16le'))
        command(valid)
        for fault in ('expected','version','request-version','path','operation','url'):
            value=deepcopy(valid)
            if fault=='expected':value['request']['expected']={'muted':False}
            elif fault=='version':value['schemaVersion']=True
            elif fault=='request-version':value['request']['schemaVersion']=True
            elif fault=='path':value['request']['url']=value['request']['url'].replace('/tickets/'+ 'c'*32,'/tickets/'+ 'd'*32)
            elif fault=='operation':value['request']['operation']='record-start'
            else:value['request']['url']+='?redirect=1'
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):command(value)


if __name__=='__main__':unittest.main()
