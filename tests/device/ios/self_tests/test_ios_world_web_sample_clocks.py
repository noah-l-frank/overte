"""Every actual GPU-clock delivery is retained before send and on reconstruction."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import time
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.world_web_sample_clocks import WorldWebSampleClocks
from ios.self_tests.world_web_sources_fixture import SDK


class WorldWebSampleClockTests(unittest.TestCase):
    @contextmanager
    def owners(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);sdk=SDK();lock=ScriptSourceLock(root/'script-feature-sources.lock');caught=None
            with lock.held():
                try:
                    source=sdk.owner(PrivateFeatureState(root/'ios-world-web-primary-sources.json'),lock)
                    make=lambda:WorldWebSampleClocks(PrivateFeatureState(root/'ios-world-web-primary-gpu-clocks.json'),root,source.binding,source.run,
                        'ios-'+'9'*32,lock,lambda:True,native=source.native,monotonic=lambda:sdk.time)
                    yield sdk,source,make
                except BaseException as error:caught=error
            if caught is not None:raise caught

    def test_actual_query_is_durable_before_send_and_raw_native_pid_nonce_clocks_survive_reconstruction(self):
        with self.owners() as (sdk,source,make):
            clocks=make();sent=[];original_send=source.native.send
            def send(query):
                packet=clocks.store.read();state=clocks.decode(packet)
                self.assertEqual(query,state['entries'][-1]['query']);self.assertEqual([],state['entries'][-1]['raws']);sent.append(query)
                original_send(query)
            source.native.send=send
            with clocks.owned():first=source.native.read(source.native.sequence)
            self.assertEqual(1,len(sent));self.assertEqual(first,clocks.validate_original(clocks.previous));self.assertEqual(first,make().last())
            returned=clocks.last();returned['processId']=333
            self.assertEqual(sdk.pid,clocks.last()['processId'])

    def test_lost_clock_raw_remains_unknown_and_later_observation_has_a_distinct_nonce_without_replay(self):
        with self.owners() as (sdk,source,make):
            clocks=make();original=source.native.original
            source.native.original=lambda:(_ for _ in ()).throw(OSError('lost passive raw'))
            with self.assertRaises(NativeUIError):
                with clocks.owned():source.native.read(source.native.sequence)
            unknown=clocks.state['entries'][0]['query'];self.assertEqual([],clocks.state['entries'][0]['raws'])
            source.native.original=original;fresh=make()
            with fresh.owned():actual=source.native.read(source.native.sequence)
            self.assertEqual(2,len(sdk.native.commands));self.assertEqual(unknown,sdk.native.commands[0])
            self.assertNotEqual(unknown['commandId'],actual['requestId']);self.assertEqual(unknown,fresh.state['entries'][0]['query'])
            self.assertEqual(actual,make().last())

    def test_identical_raw_bytes_with_replaced_actual_carrier_inode_never_hit_a_warm_cache(self):
        with self.owners() as (_sdk,source,make):
            clocks=make()
            with clocks.owned():source.native.read(source.native.sequence)
            clocks.last();reference=clocks.state['entries'][0]['raws'][0];path=clocks.frames.path(clocks.frames.expand(reference))
            replacement=path.with_suffix('.replacement');replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);os.replace(replacement,path)
            with self.assertRaises(NativeUIError):clocks.last()
            with self.assertRaises(NativeUIError):make()

    def test_matching_foreign_pid_raw_is_durably_retained_but_never_validated_or_relabelled(self):
        with self.owners() as (sdk,source,make):
            clocks=make();actual=sdk.native.mutate
            def mutate(value):actual(value);value['processId']+=1
            sdk.native.mutate=mutate
            with self.assertRaises(NativeUIError):
                with clocks.owned():source.native.read(source.native.sequence)
            self.assertEqual(1,len(clocks.state['entries']));self.assertTrue(clocks.state['entries'][0]['raws'])
            entry=clocks.state['entries'][0];raw=clocks.raw(entry['raws'][0],1,1,entry['query'])
            self.assertEqual(sdk.pid+1,json.loads(raw)['processId'])
            with self.assertRaises(NativeUIError):clocks.validate_original(clocks.previous)

    @staticmethod
    def history_producer(sdk):
        history=[];clock=sdk.native.mutate
        def produced(value):
            animation=deepcopy(value['animation']);clock(value);sequence=value['sequence'];epoch=value['capturedEpochMs']
            animation.update(capturedEpochMs=epoch,evaluationSequence=100+sequence,overrideActive=False);animation.pop('clip',None)
            history.append(dict(frameSequence=sequence,overrideSequence=0,evaluationSequence=100+sequence,capturedEpochMs=epoch,
                overrideActive=False,joints=[dict(index=0,pose=deepcopy(animation['joints'][0]))]))
            animation['history']=dict(historyVersion=2,instance='e'*32,available=True,callSequence=0,overrideSequence=0,
                frameSequence=sequence,droppedEvents=0,droppedFrames=0,events=[],frames=deepcopy(history))
            value['animation']=animation;value['animationFence']=dict(rigId=animation['rigId'],sequence=99+sequence,requestedEpochMs=value['requestedEpochMs'])
        sdk.native.mutate=produced;return history

    def test_interval_validates_each_actual_before_after_current_prefix_once_with_exit_guards(self):
        with self.owners() as (sdk,source,make):
            # Install this declared history producer before its first native
            # query. No previously captured packet is changed or retimed.
            history=self.history_producer(sdk);clocks=make()
            with clocks.owned():
                for _ in range(12):source.native.read(source.native.sequence)
            before=clocks.snapshot()
            with clocks.owned():
                first=source.native.read(source.native.sequence);last=source.native.read(source.native.sequence)
            after=clocks.snapshot()
            with clocks.owned():source.native.read(source.native.sequence)
            sent=len(sdk.native.commands);started=time.perf_counter()
            with patch.object(clocks,'accepted_rows',wraps=clocks.accepted_rows) as decoded:
                self.assertEqual((first,last),clocks.interval(before,after));self.assertEqual(1,decoded.call_count)
            elapsed=time.perf_counter()-started
            self.assertEqual(sent,len(sdk.native.commands));self.assertEqual(15,len(history))
            self.interval_seconds=elapsed
            # Local results cannot become an outward mutable decoder cache.
            result=clocks.retained(before);result[0]['sequence']=0
            self.assertGreater(clocks.retained(before)[0]['sequence'],0)

    def test_interval_rechecks_current_journal_and_carrier_inodes_on_exit(self):
        for mode in ('journal','carrier'):
            with self.subTest(mode=mode),self.owners() as (sdk,source,make):
                clocks=make()
                with clocks.owned():source.native.read(source.native.sequence)
                before=clocks.snapshot()
                with clocks.owned():source.native.read(source.native.sequence)
                after=clocks.snapshot();tail=clocks.rows
                def changed(state,**kwargs):
                    value=tail(state,**kwargs)
                    # All current rows have been read; replacement at return is still refused.
                    changed.calls+=1
                    if changed.calls==1:
                        reference=clocks.state['entries'][0]['raws'][0]
                        path=clocks.store.path if mode=='journal' else clocks.frames.path(clocks.frames.expand(reference))
                        raw=path.read_bytes();other=path.with_suffix('.replacement');other.write_bytes(raw);other.chmod(0o600);other.replace(path)
                    return value
                changed.calls=0;sent=len(sdk.native.commands)
                with patch.object(clocks,'rows',side_effect=changed),self.assertRaises(NativeUIError):clocks.interval(before,after)
                self.assertEqual(sent,len(sdk.native.commands))

    def test_retirement_interval_requires_new_retained_actual_queries_after_the_exact_old_prefix(self):
        with self.owners() as (_sdk,source,make):
            clocks=make()
            with clocks.owned():old=source.native.read(source.native.sequence)
            before=clocks.snapshot()
            with clocks.owned():
                first=source.native.read(source.native.sequence);last=source.native.read(source.native.sequence)
            after=clocks.snapshot();self.assertEqual((first,last),clocks.interval(before,after))
            self.assertGreater(first['sequence'],old['sequence'])
            for a,b in ((before,before),(after,before),(after,after)):
                with self.subTest(before=a['requestId'],after=b['requestId']),self.assertRaises(NativeUIError):clocks.interval(a,b)
            poisoned=deepcopy(before)
            from adapters.script_feature.history import pack,unpack
            state=unpack(poisoned['payload'])[0];state['entries'][0]['query']['commandId']='ios-'+'2'*32;poisoned['payload']=pack([state])
            with self.assertRaises(NativeUIError):clocks.interval(poisoned,after)
            returned=clocks.interval(before,after);returned[0]['sequence']=0
            self.assertEqual((first,last),clocks.interval(before,after))


if __name__=='__main__':unittest.main()
