#!/usr/bin/env python3
"""Actual private history/loopback/process counterexamples for cleanup continuity."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import multiprocessing
import os
from pathlib import Path
import sys
import threading
import time
import traceback
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshots_actor as base
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from overte_phone_script_history import unpack,pack
import overte_phone_snapshots_actor as source
from overte_phone_snapshots_feature import PhoneSnapshotsFeature


def retained_child(boundary,url,queue,command,first_mismatch=False):
    try:
        f=boundary.feature;f.role='actor';f.load=lambda:setattr(f,'previous',f.store.read())
        phase=PhaseFixtureReader(Client(url,'a'*64),base.RUN,'snapshots',epoch_ms=lambda:boundary.epoch)
        f.phase.client=phase.client;f.phase.status=phase.status
        f.phase.provider=lambda:dict(boundary.provider,active=phase.status()['active'])
        f.monotonic,f.sleep=time.monotonic,time.sleep
        constructors=[];original=source.PhoneSnapshotsRole;delete_before_construct=[False]
        def construct(*args,**kwargs):
            if delete_before_construct[0]:
                delete_before_construct[0]=False;(boundary.root/'phone-snapshots-actor-originals.json').unlink()
                assert kwargs['expected_previous'] is not None
            role=original(*args,**kwargs);constructors.append(role);return role
        with patch.object(source,'PhoneSnapshotsRole',construct):
            actor=source.PhoneSnapshotsActor(f)
            if first_mismatch:
                retain=actor.retain_cleanup;foreign=[]
                def replaced(role,status):
                    previous=actor.store.read();state=unpack(previous['payload'])[0];state['dropped'].append(dict(foreignFirstRetain=True))
                    value=dict(previous,payload=pack([state]));PrivateFeatureState(actor.store.path).write(value,previous);foreign.append(value)
                    return retain(role,status)
                actor.retain_cleanup=replaced;errors=[]
                for _ in range(2):
                    try:actor.step()
                    except NativeUIError:errors.append(True)
                queue.put(dict(firstMismatch=True,errors=len(errors),constructors=len(constructors),poisoned=actor._cleanup_failed,
                    retained=actor._cleanup_reader is not None,preserved=actor.store.read()==foreign[0]));return
            # Warmup may yield between actual current acquisitions. Wait for
            # the original completed interval and its own receipt, rather than
            # treating a single scheduler turn as a completed measurement.
            deadline=time.monotonic()+15
            while True:
                assert time.monotonic()<deadline,'Original resident warmup deadline exceeded'
                actor.step()
                if (actor._cleanup_reader is not None and actor.state['quiet'] is not None
                        and actor.state['quiet']['complete'] and actor.state['last'] is not None):break
                time.sleep(actor.poll_delay())
            role=actor._cleanup_reader[0];restores=[];restore=role.restore_originals
            def read_old():restores.append(True);return restore()
            role.restore_originals=read_old
            queue.put(dict(ready=True,sequence=role.state['sequence'],quiet=deepcopy(actor.state['quiet']),
                oldFile=str(next(boundary.root.glob('emote-frame-snapshots-'+base.RUN+'-actor-*.json')))))
            instruction=command.recv();before=actor.store.read()
            original_read=role.read
            if instruction in ('pending','pending-foreign','pending-disappear','busy-foreign','source-error'):
                def refused(_):
                    if instruction in ('pending','pending-foreign','pending-disappear'):raise source.SnapshotPending()
                    if instruction=='busy-foreign':raise source.PhoneScriptSourceBusy('Controlled current source lock unavailable')
                    raise NativeUIError('Actual source unavailable')
                role.read=refused
            elif instruction in ('feature-load','actor-load'):
                store=f.store if instruction=='feature-load' else actor.store;read=store.read;switched=[False]
                def late_read():
                    value=read()
                    if not switched[0]:
                        switched[0]=True
                        if instruction=='feature-load':foreign=dict(foreignFeature=True)
                        else:
                            state=unpack(value['payload'])[0];state['dropped'].append(dict(foreign=True));foreign=dict(value,payload=pack([state]))
                        PrivateFeatureState(store.path).write(foreign,value)
                    return value
                store.read=late_read
            elif instruction=='binding':f.binding['processIdentity']='32:foreign-start'
            elif instruction not in ('continue','closed','changed'):raise RuntimeError('Unknown controlled test command')
            started=time.monotonic()
            try:
                result=actor.step();error=None
            except Exception as failure:
                result=None;error=type(failure).__name__;current=failure
                while current is not None:
                    traceback.print_exception(type(current),current,current.__traceback__,chain=False)
                    current=current.__context__
            elapsed=time.monotonic()-started
            pending_anchor=actor._cleanup_anchor is not None;resumed=False
            if instruction in ('pending-foreign','busy-foreign'):
                role.read=original_read;previous=actor.store.read();state=unpack(previous['payload'])[0]
                state['dropped'].append(dict(foreignAfterUnavailable=True));foreign=dict(previous,payload=pack([state]))
                PrivateFeatureState(actor.store.path).write(foreign,previous)
                try:actor.step();error=None
                except Exception as failure:error=type(failure).__name__
                assert actor.store.read()==foreign
            elif instruction=='pending-disappear':
                role.read=original_read;delete_before_construct[0]=True
                try:actor.step();error=None
                except Exception as failure:error=type(failure).__name__
                assert not (boundary.root/'phone-snapshots-actor-originals.json').exists()
            elif instruction=='pending':
                role.read=original_read;actor.step();resumed=actor._cleanup_reader is not None
            poisoned=False
            if actor._cleanup_failed:
                try:actor.step()
                except NativeUIError:poisoned=True
            queue.put(dict(result=result,error=error,elapsed=elapsed,constructors=len(constructors),restores=len(restores),
                retained=actor._cleanup_reader is not None,poisoned=poisoned,phase=actor.state['phase'],
                quiet=deepcopy(actor.state['quiet']),pendingAnchor=pending_anchor,resumed=resumed,
                unchangedJournal=before==actor.store.read()))
    except Exception as failure:
        # Keep suppressed lock/guard context in this host test's private log;
        # the queue still carries the same error verdict to the parent.
        current=failure
        while current is not None:
            traceback.print_exception(type(current),current,current.__traceback__,chain=False)
            current=current.__context__
        queue.put(dict(error=type(failure).__name__,message=str(failure)))


class SnapshotResidentActorTests(unittest.TestCase):
    def setUp(self):
        self.rig=base.SnapshotsActorTests('test_own_original_quiet_and_actual_closed_phase_precede_actor_retirement')
        self.rig.setUp();self.addCleanup(self.rig.doCleanups)

    def probe(self,mutation):
        r=self.rig;b=r.boundary;b.clean();r.reader.activate('d'*32,'cleanup',{})
        b.feature.state['current']=None;b.feature.guard=b.feature.bound
        b.feature.state['actions']=[dict(ticket='d'*32,phase='acknowledged')]
        b.provider.update(ticket='d'*32,activations=[dict(ticket=base.TICKET,verb='capture',capturedEpochMs=19000),dict(ticket='d'*32,verb='cleanup',capturedEpochMs=20000)])
        r.advance_cleanup_primary()
        # Warm reuse pins an actual durable Feature owner as well as the Role
        # and Actor journals. Use the same original save path as the separate
        # cleanup-frontier fixture; an absent owner is not reusable authority.
        with b.feature.lock.held():
            b.feature.previous=b.feature.store.read();PhoneSnapshotsFeature.save(b.feature)
            self.assertEqual(b.feature.previous,b.feature.store.read())
        r.server.shutdown();r.thread.join(3)
        ctx=multiprocessing.get_context('fork');queue=ctx.Queue();receive,send=ctx.Pipe(duplex=False)
        process=ctx.Process(target=retained_child,args=(b,r.url,queue,receive,mutation=='first-retain'));process.start()
        r.thread=threading.Thread(target=r.server.serve_forever,daemon=True);r.thread.start()
        foreign_store=foreign=None
        try:
            ready=queue.get(timeout=15)
            if mutation=='first-retain':
                process.join(3);self.assertEqual(0,process.exitcode);self.assertTrue(ready.get('firstMismatch'),ready)
                self.assertEqual(2,ready['errors']);self.assertEqual(1,ready['constructors']);self.assertTrue(ready['poisoned'])
                self.assertFalse(ready['retained']);self.assertTrue(ready['preserved']);return ready
            self.assertTrue(ready.get('ready'),ready)
            entries=r.reader.request('/runs/'+base.RUN)['entries'];self.assertEqual(1,len(entries))
            # The next Actor turn needs a genuinely newer Primary original.
            # Produce it before the controlled mutation; neither an ACK nor a
            # synthetic sequence can authorize the requested independent read.
            r.advance_cleanup_primary()
            if mutation=='closed':r.reader.close()
            elif mutation=='ticket':r.reader.activate('e'*32,'cleanup',{})
            elif mutation in ('feature','actor','role'):
                foreign_store=b.feature.store if mutation=='feature' else PrivateFeatureState(b.root/('phone-snapshots-actor-'+('lifecycle' if mutation=='actor' else 'originals')+'.json'))
                previous=foreign_store.read()
                if mutation=='actor':
                    state=unpack(previous['payload'])[0];state['dropped'].append(dict(foreign=True));foreign=dict(previous,payload=pack([state]))
                else:foreign=dict(foreignHeader=True)
                foreign_store.write(foreign,previous)
            elif mutation=='old-file':Path(ready['oldFile']).unlink()
            elif mutation=='late-file':(b.producer.directory/('e2e-'+base.RUN+'-late.png')).write_bytes(b.raw)
            send.send(mutation if mutation in ('continue','closed','binding','pending','pending-foreign','pending-disappear','busy-foreign','source-error','feature-load','actor-load') else 'changed')
            final=queue.get(timeout=15);process.join(3);self.assertEqual(0,process.exitcode)
            if mutation=='continue':
                self.assertIsNone(final['error']);self.assertFalse(final['result']);self.assertEqual(1,final['constructors'])
                self.assertGreaterEqual(final['restores'],1);self.assertTrue(final['retained'])
                self.assertEqual(ready['quiet']['started'],final['quiet']['started']);self.assertTrue(final['quiet']['complete'])
                self.assertGreater(final['quiet']['sequences'][-1],ready['sequence'])
                self.assertEqual(2,len(r.reader.request('/runs/'+base.RUN)['entries']))
            elif mutation=='closed':
                self.assertIsNone(final['error']);self.assertTrue(final['result']);self.assertEqual(2,final['constructors'])
                self.assertEqual('retired',final['phase']);self.assertFalse(final['retained'])
            elif mutation=='pending':
                self.assertIsNone(final['error']);self.assertTrue(final['pendingAnchor']);self.assertTrue(final['resumed'])
                self.assertTrue(final['retained']);self.assertEqual(2,final['constructors'])
            else:
                self.assertEqual('NativeUIError',final.get('error'),final);self.assertFalse(final['retained']);self.assertTrue(final['poisoned'])
                self.assertEqual(1,final['constructors']);self.assertEqual(1,len(r.reader.request('/runs/'+base.RUN)['entries']))
            if foreign_store is not None:self.assertEqual(foreign,foreign_store.read())
            return final
        finally:
            if process.is_alive():process.terminate();process.join(3)

    def test_first_retention_cannot_adopt_valid_foreign_actor_owner_after_caller_catches_error(self):self.probe('first-retain')
    def test_same_process_reuses_reader_but_reopens_all_old_originals_and_reads_new_current_sources(self):self.probe('continue')
    def test_real_close_discards_reader_and_obtains_new_full_closed_proof_before_retirement(self):self.probe('closed')
    def test_foreign_feature_header_cannot_turn_a_warm_mismatch_into_a_cold_adoption(self):self.probe('feature')
    def test_valid_foreign_actor_header_cannot_be_adopted(self):self.probe('actor')
    def test_foreign_role_header_is_red_before_load(self):self.probe('role')
    def test_valid_actor_header_replaced_after_comparison_is_red_after_load(self):self.probe('actor-load')
    def test_changed_feature_header_after_comparison_is_red_after_load(self):self.probe('feature-load')
    def test_changed_cleanup_activation_cannot_reuse_reader(self):self.probe('ticket')
    def test_changed_original_pid_binding_cannot_reuse_reader(self):self.probe('binding')
    def test_missing_old_original_is_not_hidden_by_resident_reader(self):self.probe('old-file')
    def test_actual_late_owned_file_prevents_new_peer_publication(self):self.probe('late-file')
    def test_pending_current_source_discards_reader_but_preserves_trusted_anchors_for_genuine_resume(self):self.probe('pending')
    def test_pending_source_cannot_allow_valid_foreign_actor_header_before_cold_resume(self):self.probe('pending-foreign')
    def test_disappeared_known_role_header_at_constructor_first_read_cannot_create_a_new_owner(self):self.probe('pending-disappear')
    def test_busy_inside_acquisition_cannot_allow_valid_foreign_actor_header_on_retry(self):self.probe('busy-foreign')
    def test_failed_current_source_discards_reader_preserving_original_journals(self):self.probe('source-error')


if __name__=='__main__':unittest.main()
