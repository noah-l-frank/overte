"""Pico source serialization, no input replay and final acquisition bounds."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.pico4.browser_source import PicoBrowserIO,command
from adapters.pico4.tablet_browser_source import PicoTabletBrowserIO
from adapters.script_journey.lock import ScriptSourceLock
from adapters.normal_ui import NativeUIError

RUN='a'*32;OWNER='b'*32;URL='http://127.0.0.1/feature-fixture/v1/runs/'+RUN+'/'
class Boundary:
    def __init__(self):self.epoch=20000;self.elapsed=1.;self.calls=[];self.packet=None;self.guards=0
    def guard(self):self.guards+=1;return True
    def send(self,call):
        self.calls.append(deepcopy(call));self.packet=dict(picoBrowserVersion=1,commandId=call['commandId'],runId=RUN,ownerToken=OWNER,
            instance='c'*32,sequence=len(self.calls),processId=123,capturedEpochMs=self.epoch,status='ready',source={'reserved':True})
    def reader(self,lock,**options):return PicoTabletBrowserIO(self.send,lambda:json.dumps(self.packet),lambda:self.epoch,self.guard,123,
        source_lock=lock,monotonic=lambda:self.elapsed,sleep=lambda _:None,**options)
class PicoBrowserIOTests(unittest.TestCase):
    def lock(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);return ScriptSourceLock(Path(temp.name)/'script-sources.lock')
    def test_exact_shared_os_lock_and_read_only_role_refuse_before_publication(self):
        lock=self.lock();boundary=Boundary();reader=boundary.reader(lock)
        with self.assertRaises(NativeUIError):reader.request(RUN,URL,OWNER,'reserve')
        self.assertEqual([],boundary.calls)
        with lock.held():
            with self.assertRaises(NativeUIError):boundary.reader(lock,read_only=True).request(RUN,URL,OWNER,'reserve')
            packet=reader.request(RUN,URL,OWNER,'reserve')
        self.assertEqual(1,len(boundary.calls));packet['source']['reserved']=False
        self.assertTrue(reader.last['source']['reserved'])
    def test_late_copy_and_last_guard_fail_without_committing_cursor(self):
        for stage in ('copy','guard'):
            with self.subTest(stage=stage):
                lock=self.lock();boundary=Boundary();reader=boundary.reader(lock);copies=0
                def copy(value):
                    nonlocal copies
                    result=deepcopy(value);copies+=1
                    if stage=='copy' and copies==2:boundary.elapsed+=1.6
                    return result
                def guard():
                    if stage=='guard' and copies>=2:boundary.epoch+=1501
                    return True
                reader.guard=guard
                with lock.held(),patch('adapters.pico4.browser_source.deepcopy',side_effect=copy):
                    with self.assertRaises(NativeUIError):reader.request(RUN,URL,OWNER,'reserve')
                self.assertIsNone(reader.last);self.assertEqual(1,len(boundary.calls))
    def test_final_native_and_host_clock_regression_refuse_without_cursor(self):
        for clock in ('host','native'):
            with self.subTest(clock=clock):
                lock=self.lock();boundary=Boundary();reader=boundary.reader(lock)
                if clock=='host':
                    times=iter((1.,1.,1.6,1.5));reader.monotonic=lambda:next(times)
                else:
                    times=iter((20000,20000,20100,20050));reader.clock_ms=lambda:next(times)
                with lock.held(),self.assertRaises(NativeUIError):reader.request(RUN,URL,OWNER,'reserve')
                self.assertIsNone(reader.last);self.assertEqual(1,len(boundary.calls))
    def test_closed_pico_protocol_never_accepts_phone_actions_host_coordinates_or_desired_outcomes(self):
        call=dict(schemaVersion=1,commandId='d'*32,action='pico-tablet-web',runId=RUN,fixtureUrl=URL,operation='reserve',ownerToken=OWNER)
        command(call)
        for bad in (call|{'action':'phone-tablet-web'},call|{'x':12},call|{'expected':'success'},call|{'schemaVersion':True}):
            with self.subTest(bad=bad),self.assertRaises((ValueError,RuntimeError)):command(bad)
if __name__=='__main__':unittest.main()
