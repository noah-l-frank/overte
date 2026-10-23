"""Actual separate host actor and credentialed loopback journal, no device."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import multiprocessing
import hashlib
import uuid
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(Path(__file__).parent)]
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from feature_journeys.phase_fixture import PhaseFixtureReader
from fixture.messages_mixer import start_identity
from overte_phone_script_history import unpack,pack,canonical
from overte_phone_snapshots_actor import PhoneSnapshotsActor
from overte_phone_snapshots_role import PhoneSnapshotsRole
from test_snapshots_role import SnapshotRolesBoundary,RUN,TICKET


def actor_once(boundary,url,token,queue):
    try:
        f=boundary.feature;f.role='actor';f.load=lambda:setattr(f,'previous',f.store.read())
        phase=PhaseFixtureReader(Client(url,token),RUN,'snapshots',epoch_ms=lambda:boundary.epoch)
        f.phase.client=phase.client;f.phase.status=phase.status
        result=PhoneSnapshotsActor(f).step();queue.put(dict(result=result,pid=os.getpid(),start=start_identity(os.getpid())))
    except Exception as error:queue.put(dict(error=type(error).__name__,message=str(error)))


def actor_until_closed(boundary,url,queue,command,report_progress=False):
    try:
        f=boundary.feature;f.role='actor';f.load=lambda:setattr(f,'previous',f.store.read())
        phase=PhaseFixtureReader(Client(url,'a'*64),RUN,'snapshots',epoch_ms=lambda:boundary.epoch)
        f.phase.client=phase.client;f.phase.status=phase.status
        f.phase.provider=lambda:dict(boundary.provider,active=phase.status()['active'])
        # Exercise the production quiet window with real elapsed host time.
        f.monotonic,f.sleep=time.monotonic,time.sleep
        actor=PhoneSnapshotsActor(f)
        handed=[False]
        def sleep(seconds):
            if report_progress and not handed[0] and f.lock._owner is None:
                handed[0]=True;queue.put(dict(progress=True,quiet=deepcopy(actor.state['quiet'])))
                if not command.poll(5):raise RuntimeError('Quiet progress handoff missing')
                instruction=command.recv()
                if instruction=='foreign-binding':f.binding['processIdentity']='32:foreign-start'
                elif instruction in ('feature-load','actor-load'):
                    store=f.store if instruction=='feature-load' else actor.store;read=store.read;changed=[False]
                    def switched_read():
                        original=read()
                        if not changed[0]:
                            changed[0]=True
                            if instruction=='feature-load':foreign=dict(foreignFeatureDuringLoad=True)
                            else:
                                state=unpack(original['payload'])[0];state['dropped'].append(dict(foreignLoad=True))
                                foreign=dict(original,payload=pack([state]))
                            PrivateFeatureState(store.path).write(foreign,original)
                        return original
                    store.read=switched_read
                elif instruction!='continue':raise RuntimeError('Quiet progress handoff missing')
            time.sleep(seconds)
        f.sleep=sleep
        deadline=time.monotonic()+15
        for _attempt in range(100):
            if time.monotonic()>=deadline:raise RuntimeError('Independent quiet deadline exceeded')
            result=actor.step()
            if actor.state['quiet'] is not None and actor.state['quiet']['complete']:break
            time.sleep(.1)
        else:raise RuntimeError('Independent original actor quiet never completed')
        queue.put(dict(ready=True,pid=os.getpid(),start=start_identity(os.getpid()),quiet=deepcopy(actor.state['quiet'])))
        if not command.poll(10):raise RuntimeError('Explicit host close seam timed out')
        assert command.recv()=='closed'
        result=actor.step();queue.put(dict(result=result,phase=actor.state['phase'],closure=deepcopy(actor.state['closure'])))
        if not command.poll(10):raise RuntimeError('Explicit post-close seam timed out')
        next_command=command.recv()
        if next_command=='late':actor.step();raise AssertionError('Late original unexpectedly passed retired actor')
        assert next_command=='exit'

    except Exception as error:queue.put(dict(error=type(error).__name__,message=str(error)))


def cleanup_frontier_actor(boundary,url,queue,command):
    """Drive the real cleanup actor from another process; IPC carries no facts.

    SDK/native producers are the existing explicit component seams. Original
    files, reader continuity, the HTTP journal and three-second quiet windows
    execute unchanged. Wrappers only count calls or lose an actual POST reply.
    """
    import overte_phone_snapshots_actor as module
    f=boundary.feature;f.role='actor'
    def load():
        f.previous=f.store.read()
        if f.previous is not None:f.state=unpack(f.previous['payload'])[0]
    f.load=load
    phase=PhaseFixtureReader(Client(url,'a'*64),RUN,'snapshots',epoch_ms=lambda:boundary.epoch)
    f.phase.client=phase.client;f.phase.status=phase.status
    f.phase.provider=lambda:dict(boundary.provider,active=phase.status()['active'])
    f.monotonic,f.sleep=time.monotonic,time.sleep
    actor=PhoneSnapshotsActor(f);counts=dict(reads=0,posts=0);points=[];lose_reply=[False];lost_replies=[0]
    pause_warm=[False];memory_mutated=[False];read_fault=[None];cached_read=[None]
    actual_reads=[0];ignored_reads=[0];foreign_sources=[0];quiet_stops=[0]
    native_source=boundary.native_source.mutate
    def native(value):
        native_source(value)
        if read_fault[0]=='foreign-native':value['processId']=999;foreign_sources[0]+=1
    boundary.native_source.mutate=native
    original_read=PhoneSnapshotsRole.read;original_quiet=module.quiet_window;request=actor.client.request
    def read(role,*args,**kwargs):
        counts['reads']+=1
        if read_fault[0]=='ignored':
            assert cached_read[0] is not None
            ignored_reads[0]+=1;return deepcopy(cached_read[0])
        actual_reads[0]+=1
        value=original_read(role,*args,**kwargs);cached_read[0]=deepcopy(value);return value
    def quiet(previous,now,sequence):
        result=original_quiet(previous,now,sequence)
        points.append(dict(previousLast=None if previous is None else previous['last'],
            started=result['started'],last=result['last'],sequence=sequence,complete=result['complete']))
        return result
    def transport(path,*args,**kwargs):
        is_post=path=='/runs/'+RUN+'/samples' and bool(args)
        if is_post:counts['posts']+=1
        result=request(path,*args,**kwargs)
        if is_post and lose_reply[0]:
            lose_reply[0]=False;lost_replies[0]+=1
            raise RuntimeError('Actual accepted POST reply deliberately lost')
        return result
    actor.client.request=transport
    def sleep(seconds):
        if (pause_warm[0] and f.lock._owner is None and actor.state is not None
                and actor.state['quiet'] is not None and actor.state['quiet']['complete']):
            pause_warm[0]=False
            queue.put(dict(event='warm-gap',pid=os.getpid(),counts=deepcopy(counts),lockReleased=True))
            if not command.poll(15):raise RuntimeError('Warm cleanup gap IPC expired')
            action=command.recv()
            if action=='pid':
                f.binding=deepcopy(f.binding);f.binding['processIdentity']='32:foreign-start'
            elif action=='sdk':f.adapter._existing_input_scope=dict(foreignScope=True)
            elif action in ('last-native-memory','last-save-memory'):
                original=f.bound;callbacks=[0]
                def after_native():
                    result=original()
                    caller=sys._getframe(1).f_code.co_name
                    if caller=='validate_primary_cue':callbacks[0]+=1
                    mutate=(action=='last-native-memory' and caller=='validate_primary_cue' and callbacks[0]==2
                        or action=='last-save-memory' and caller=='save' and actor.state['pending'] is not None)
                    if mutate and not memory_mutated[0]:
                        actor._cleanup_reader[0].frames[0]['lateNativeGraphChange']=True
                        memory_mutated[0]=True
                    return result
                f.bound=after_native
            elif action!='continue':raise RuntimeError('Unknown warm cleanup gap instruction')
        time.sleep(seconds)
    f.sleep=sleep
    try:
        with patch.object(PhoneSnapshotsRole,'read',read),patch.object(module,'quiet_window',quiet):
            while command.poll(25):
                instruction=command.recv()
                if instruction=='exit':return
                if instruction.get('cold'):
                    actor=PhoneSnapshotsActor(f)
                    # The same actual Client retains only its transport wrapper.
                lose_reply[0]=instruction.get('loseReply',False);pause_warm[0]=instruction.get('pauseWarm',False)
                read_fault[0]=instruction.get('readFault');save=actor.save
                def saved_quiet():
                    save()
                    if (instruction.get('stopAfterQuiet') and actor.state['quiet'] is not None
                            and actor.state['quiet']['complete'] and actor.state['last'] is actor.state['pending'] is None):
                        quiet_stops[0]+=1
                        raise NativeUIError('Controlled interruption after actual durable quiet, before any publication')
                first=len(points);error=None;result=None
                try:
                    with patch.object(actor,'save',saved_quiet):result=actor.step()
                except Exception as caught:error=dict(error=type(caught).__name__,message=str(caught))
                header=PrivateFeatureState(boundary.root/'phone-snapshots-actor-originals.json').read()
                queue.put(dict(error=error,result=result,pid=os.getpid(),counts=deepcopy(counts),
                    points=deepcopy(points[first:]),state=deepcopy(actor.state),roleHeader=header,lostReplies=lost_replies[0],memoryMutated=memory_mutated[0],
                    actorHeader=PrivateFeatureState(boundary.root/'phone-snapshots-actor-lifecycle.json').read(),
                    actualReads=actual_reads[0],ignoredReads=ignored_reads[0],foreignSources=foreign_sources[0],quietStops=quiet_stops[0]))
        raise RuntimeError('Cleanup frontier IPC command expired')
    except Exception as error:
        queue.put(dict(fatal=type(error).__name__,message=str(error)))


class SnapshotsActorTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='snapshot-actor-');self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.boundary=SnapshotRolesBoundary(self.root);f=self.boundary.feature;f.state['hostProcess']=dict(pid=os.getpid(),start=start_identity(os.getpid()))
        f.state['actions']=[dict(ticket=TICKET,phase='acknowledged')]
        self.server=make_server('r'*64,'a'*64,adapter_token='b'*64);self.server.journal.clock=lambda:self.boundary.epoch
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        def stop():self.server.shutdown();self.server.server_close();self.thread.join(3)
        self.addCleanup(stop);self.url='http://127.0.0.1:'+str(self.server.server_port)+'/feature-fixture/v1';self.reader=Client(self.url,'r'*64)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.reader.register('snapshots')
        self.reader.activate(TICKET,'capture',dict(mode='still',format='png'))
        # The ordinary actor's scheduling prerequisite is a genuinely ready
        # Primary original, never an assumed sequence or a primary fact copy.
        phase=PhaseFixtureReader(self.reader,RUN,'snapshots',epoch_ms=lambda:self.boundary.epoch)
        f.role='primary';f.phase.client=phase.client;f.phase.status=phase.status
        with f.lock.held():
            primary=PhoneSnapshotsRole(f,'primary');primary.read(primary.state['sequence'])
            self.capture_primary_header=deepcopy(primary.previous)
    def advance_cleanup_primary(self):
        """Create a genuinely new Primary original through the normal reader."""
        f=self.boundary.feature
        with f.lock.held():
            primary=PhoneSnapshotsRole(f,'primary')
            measured=primary.read(primary.state['sequence'])
            self.assertEqual([],measured['resources'])
            self.assertEqual('d'*32,primary.frames[-1]['ticket'])
            self.assertEqual(primary.previous,primary.store.read())
            return deepcopy(primary.previous)

    def cleanup_frontier(self,*,ready=True,slot_mode=False):
        b=self.boundary;b.clean();self.reader.activate('d'*32,'cleanup',{})
        # Align the explicit synthetic boundary with the real loaded Feature.
        b.feature.state['current']=None;b.feature.guard=b.feature.bound
        b.feature.state['actions']=[dict(ticket='d'*32,phase='acknowledged')]
        b.provider.update(ticket='d'*32,activations=[dict(ticket=TICKET,verb='capture',capturedEpochMs=19000),
            dict(ticket='d'*32,verb='cleanup',capturedEpochMs=20000)])
        if ready:self.advance_cleanup_primary()
        from overte_phone_snapshots_feature import PhoneSnapshotsFeature
        with b.feature.lock.held():
            b.feature.previous=b.feature.store.read();PhoneSnapshotsFeature.save(b.feature)
            self.assertEqual(b.feature.previous,b.feature.store.read())
        self.server.shutdown();self.thread.join(3);self.assertFalse(self.thread.is_alive())
        ctx=multiprocessing.get_context('fork');queue=ctx.Queue();parent,child=ctx.Pipe()
        process=ctx.Process(target=cleanup_frontier_actor,args=(b,self.url,queue,child));process.start();child.close()
        if slot_mode:
            self.slot_process=dict(pid=process.pid,start=start_identity(process.pid))
            b.feature.state.setdefault('cleanupStages',{})['readReadyMode']=dict(snapshotCleanupReadReadyVersion=1,actorProcess=deepcopy(self.slot_process))
            with b.feature.lock.held():PhoneSnapshotsFeature.save(b.feature)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        def stop():
            if process.is_alive():
                try:parent.send('exit')
                except (BrokenPipeError,EOFError,OSError):pass
                process.join(3)
            if process.is_alive():process.terminate();process.join(3)
            parent.close();queue.close();queue.join_thread()
            self.assertFalse(process.is_alive(),'Owned cleanup Actor did not stop')
            self.assertEqual(0,process.exitcode,'Owned cleanup Actor did not exit normally')
        self.addCleanup(stop)
        def step(*,at_gap=None,**instruction):
            self.assertTrue(process.is_alive())
            if at_gap is not None:instruction['pauseWarm']=True
            parent.send(instruction);value=queue.get(timeout=20);self.assertNotIn('fatal',value,value)
            if at_gap is not None:
                self.assertEqual('warm-gap',value.get('event'),value);self.assertTrue(value['lockReleased'])
                self.assertNotEqual(os.getpid(),value['pid'])
                action=at_gap(value);parent.send('continue' if action is None else action)
                value=queue.get(timeout=20);self.assertNotIn('fatal',value,value)
            self.assertNotEqual(os.getpid(),value['pid']);return value
        return step

    def append_cleanup_slot(self,*,mutate=None,diagnostic_only=False):
        """Produce pure metadata through the actual Role archive pipeline.

        Native/SDK signals remain the explicit component producers. The public
        ConstructorPass authorization and wait are covered by the separate
        public-slot composition tests; this producer never supplies effect facts.
        """
        f=self.boundary.feature
        with f.lock.held():
            role=PhoneSnapshotsRole(f,'primary');old=deepcopy(role.previous)
            before=f.phase.status();after=f.phase.status(before)
            frame=dict(ticket=before['activations'][-1]['ticket'],phaseBefore=before,phaseAfter=after,
                diagnostic=True,image=None,binaries=[],retirement=None)
            if not diagnostic_only:
                frame['readReadySlot']=dict(snapshotCleanupReadReadyVersion=1,slotId=uuid.uuid4().hex,
                    preparedRoleSequence=role.state['sequence'],preparedRoleHeader=old,
                    preparedRoleOwnerSha256=hashlib.sha256(canonical(old)).hexdigest(),
                    featureOwnerSha256=hashlib.sha256(canonical(f.previous)).hexdigest(),actorProcess=deepcopy(self.slot_process))
            if mutate is not None:mutate(frame)
            role.state.update(phase='reading',pending=dict(original=None,manifest=None,image=None,binaries=[],retirement=None,frame=None,work=deepcopy(frame)))
            role.save();role.finish_archive(frame)
            self.assertEqual(role.previous,role.store.read())
            return deepcopy(role.previous),deepcopy(frame)

    def enroll_complete_without_post(self,step):
        deadline=time.monotonic()+15;previous_reads=previous_sequence=None
        while True:
            value=step();self.assertIsNone(value['error'],value)
            self.assertLessEqual(time.monotonic(),deadline,'Bounded genuine cleanup interval did not complete')
            quiet=value['state']['quiet'];self.assertIsNotNone(quiet)
            self.assertEqual(0,value['counts']['posts']);self.assertIsNone(value['state']['primaryCue'])
            self.assertIsNone(value['state']['pending']);self.assertTrue(quiet['sequences'])
            if previous_reads is not None:
                self.assertEqual(previous_reads+1,value['counts']['reads'])
                self.assertGreater(quiet['sequences'][-1],previous_sequence)
            previous_reads=value['counts']['reads'];previous_sequence=quiet['sequences'][-1]
            if quiet['complete']:break
            self.assertLess(time.monotonic()+.1,deadline,'Bounded genuine cleanup interval did not complete')
            time.sleep(.1)
        self.assertGreaterEqual(value['counts']['reads'],3)
        self.assertGreaterEqual(quiet['last']-quiet['started'],3);self.assertGreaterEqual(len(quiet['sequences']),3)
        return value

    def completed_frontier(self,step,**instruction):
        value=step(**instruction);self.assertIsNone(value['error'],value)
        quiet=value['state']['quiet'];self.assertIsNotNone(quiet)
        self.assertTrue(quiet['complete']);self.assertGreaterEqual(quiet['last']-quiet['started'],3)
        self.assertGreaterEqual(len(quiet['sequences']),3)
        self.assertEqual(1,value['counts']['posts']);self.assertIsNone(value['state']['pending'])
        self.assertEqual(1,len(self.reader.request('/runs/'+RUN)['entries']))
        return value

    def assert_no_further_acquisition(self,before,after):
        self.assertEqual(before['counts'],after['counts'])
        self.assertEqual(before['roleHeader'],after['roleHeader'])

    def test_enrolled_cleanup_ignores_normal_and_unrelated_diagnostic_then_reads_for_slot(self):
        step=self.cleanup_frontier(slot_mode=True);first=self.enroll_complete_without_post(step)
        self.advance_cleanup_primary();normal=step();self.assertIsNone(normal['error'],normal)
        self.assert_no_further_acquisition(first,normal)
        self.append_cleanup_slot(diagnostic_only=True);unrelated=step();self.assertIsNone(unrelated['error'],unrelated)
        self.assert_no_further_acquisition(normal,unrelated)
        header,frame=self.append_cleanup_slot();fresh=step();self.assertIsNone(fresh['error'],fresh)
        self.assertGreater(fresh['counts']['reads'],first['counts']['reads']);self.assertEqual(1,fresh['counts']['posts'])
        self.assertEqual(header,fresh['state']['primaryCue']['header'])
        self.assertEqual(self.slot_process,frame['readReadySlot']['actorProcess'])
        self.assertEqual(fresh['state']['quiet']['sequences'][-1],fresh['state']['last']['original']['sample']['actorSequence'])
        again=step();self.assertIsNone(again['error'],again);self.assert_no_further_acquisition(fresh,again)
        self.assertEqual(1,len(self.reader.request('/runs/'+RUN)['entries']))

    def slot_rejection(self,mutation):
        step=self.cleanup_frontier(slot_mode=True);before=self.enroll_complete_without_post(step)
        header,frame=self.append_cleanup_slot(mutate=mutation)
        original_paths=list(self.root.glob('emote-*-snapshots-'+RUN+'-primary-*.json'))
        original_bytes={str(path):path.read_bytes() for path in original_paths}
        rejected=step();self.assertEqual('NativeUIError',rejected['error']['error'],rejected)
        self.assert_no_further_acquisition(before,rejected)
        self.assertEqual(header,PrivateFeatureState(self.root/'phone-snapshots-primary-originals.json').read())
        self.assertEqual(original_bytes,{str(path):path.read_bytes() for path in original_paths})
        self.assertFalse(self.reader.request('/runs/'+RUN)['entries'])

    def test_enrolled_cleanup_rejects_unknown_slot_version(self):
        self.slot_rejection(lambda frame:frame['readReadySlot'].update(snapshotCleanupReadReadyVersion=2))

    def test_enrolled_cleanup_rejects_foreign_slot_process(self):
        self.slot_rejection(lambda frame:frame['readReadySlot']['actorProcess'].update(start='999999999'))

    def test_enrolled_cleanup_rejects_unjoined_prepared_header(self):
        self.slot_rejection(lambda frame:frame['readReadySlot']['preparedRoleHeader'].update(role='actor'))

    def test_enrolled_cleanup_rejects_foreign_feature_digest(self):
        self.slot_rejection(lambda frame:frame['readReadySlot'].update(featureOwnerSha256='0'*64))

    def mode_rejection(self,mutation):
        step=self.cleanup_frontier(slot_mode=True);f=self.boundary.feature
        mutation(f.state['cleanupStages']['readReadyMode'])
        from overte_phone_snapshots_feature import PhoneSnapshotsFeature
        with f.lock.held():PhoneSnapshotsFeature.save(f)
        rejected=step();self.assertEqual('NativeUIError',rejected['error']['error'],rejected)
        self.assertEqual(dict(reads=0,posts=0),rejected['counts'])
        self.assertFalse(self.reader.request('/runs/'+RUN)['entries'])

    def test_enrolled_cleanup_rejects_unknown_mode_version_before_read(self):
        self.mode_rejection(lambda mode:mode.update(snapshotCleanupReadReadyVersion=2))

    def test_enrolled_cleanup_rejects_present_null_mode_before_read(self):
        step=self.cleanup_frontier(slot_mode=True);f=self.boundary.feature
        f.state['cleanupStages']['readReadyMode']=None
        from overte_phone_snapshots_feature import PhoneSnapshotsFeature
        with f.lock.held():PhoneSnapshotsFeature.save(f)
        rejected=step();self.assertEqual('NativeUIError',rejected['error']['error'],rejected)
        self.assertEqual(dict(reads=0,posts=0),rejected['counts'])
        self.assertFalse(self.reader.request('/runs/'+RUN)['entries'])

    def test_enrolled_cleanup_rejects_foreign_enrolled_process_before_read(self):
        self.mode_rejection(lambda mode:mode['actorProcess'].update(start='999999999'))

    def test_enrolled_cleanup_lost_post_recovers_exact_original_slot_once(self):
        step=self.cleanup_frontier(slot_mode=True);before=self.enroll_complete_without_post(step)
        header,_frame=self.append_cleanup_slot();uncertain=step(loseReply=True)
        self.assertEqual('NativeUIError',uncertain['error']['error'],uncertain)
        self.assertEqual(1,uncertain['counts']['posts']);self.assertEqual(1,uncertain['lostReplies'])
        self.assertGreater(uncertain['counts']['reads'],before['counts']['reads'])
        self.assertEqual(header,uncertain['state']['primaryCue']['header'])
        sample=deepcopy(uncertain['state']['pending']['sample']);accepted=self.reader.request('/runs/'+RUN)['entries']
        self.assertEqual(1,len(accepted));self.assertEqual(sample,{key:accepted[0][key] for key in sample})
        recovered=step(cold=True);self.assertIsNone(recovered['error'],recovered)
        self.assert_no_further_acquisition(uncertain,recovered)
        self.assertIsNone(recovered['state']['pending']);self.assertEqual(sample,recovered['state']['last']['original']['sample'])
        self.assertEqual(header,recovered['state']['primaryCue']['header'])
        self.assertEqual(1,len(self.reader.request('/runs/'+RUN)['entries']))

    def test_cleanup_frontier_publishes_once_then_requires_new_own_read(self):
        step=self.cleanup_frontier();first=self.completed_frontier(step)
        held=step();self.assertIsNone(held['error'],held);self.assert_no_further_acquisition(first,held)
        self.assertEqual(first['state']['primaryCue'],held['state']['primaryCue'])
        primary=self.advance_cleanup_primary();fresh=step();self.assertIsNone(fresh['error'],fresh)
        self.assertGreater(fresh['counts']['reads'],held['counts']['reads']);self.assertEqual(2,fresh['counts']['posts'])
        self.assertEqual(primary,fresh['state']['primaryCue']['header'])
        previous=unpack(first['roleHeader']['payload'])[0];current=unpack(fresh['roleHeader']['payload'])[0]
        self.assertGreater(current['sequence'],previous['sequence'])
        self.assertEqual(current['sequence'],fresh['state']['last']['original']['sample']['actorSequence'])
        entries=self.reader.request('/runs/'+RUN)['entries'];self.assertEqual(2,len(entries))
        self.assertGreater(entries[-1]['actorSequence'],entries[0]['actorSequence'])

    def test_cleanup_frontier_real_gap_restarts_the_complete_quiet_interval(self):
        step=self.cleanup_frontier();first=self.completed_frontier(step)
        time.sleep(1.6);self.advance_cleanup_primary();fresh=step();self.assertIsNone(fresh['error'],fresh)
        self.assertTrue(fresh['points']);point=fresh['points'][0]
        self.assertGreater(point['last']-point['previousLast'],1.5)
        self.assertEqual(point['last'],point['started']);self.assertFalse(point['complete'])
        quiet=fresh['state']['quiet'];self.assertTrue(quiet['complete'])
        self.assertGreaterEqual(quiet['last']-quiet['started'],3);self.assertGreaterEqual(len(quiet['sequences']),3)
        self.assertGreater(quiet['started'],first['state']['quiet']['last'])
        self.assertEqual(2,fresh['counts']['posts'])
        self.assertEqual(quiet['sequences'][-1],fresh['state']['last']['original']['sample']['actorSequence'])

    def cleanup_frontier_header_counter(self,mutation):
        step=self.cleanup_frontier();first=self.completed_frontier(step)
        store=PrivateFeatureState(self.root/'phone-snapshots-primary-originals.json');previous=store.read()
        if mutation=='missing':store.discard(previous);foreign=None
        elif mutation=='regressed':foreign=deepcopy(self.capture_primary_header);store.write(foreign,previous)
        else:
            self.assertEqual('foreign',mutation);foreign=deepcopy(previous)
            foreign['binding']['targetFingerprint']='f'*64;store.write(foreign,previous)
        rejected=step();self.assertEqual('NativeUIError',rejected['error']['error'],rejected)
        self.assert_no_further_acquisition(first,rejected);self.assertEqual(foreign,store.read())
        self.assertEqual(1,len(self.reader.request('/runs/'+RUN)['entries']))
        self.assertTrue(list(self.root.glob('emote-frame-snapshots-'+RUN+'-primary-*.json')))

    def test_cleanup_frontier_rejects_a_foreign_primary_owner(self):self.cleanup_frontier_header_counter('foreign')
    def test_cleanup_frontier_rejects_a_missing_known_primary_owner(self):self.cleanup_frontier_header_counter('missing')
    def test_cleanup_frontier_rejects_an_actual_earlier_primary_header(self):self.cleanup_frontier_header_counter('regressed')

    def test_cleanup_without_ready_frontier_publishes_first_actual_quiet_then_waits(self):
        step=self.cleanup_frontier(ready=False);waiting=self.completed_frontier(step)
        self.assertGreaterEqual(waiting['actualReads'],3)
        quiet=waiting['state']['quiet'];self.assertTrue(quiet['complete'])
        self.assertGreaterEqual(quiet['last']-quiet['started'],3);self.assertGreaterEqual(len(quiet['sequences']),3)
        self.assertIsNone(waiting['state']['primaryCue'])
        self.assertEqual(self.capture_primary_header,PrivateFeatureState(self.root/'phone-snapshots-primary-originals.json').read())
        held=step();self.assertIsNone(held['error'],held);self.assert_no_further_acquisition(waiting,held)
        self.assertEqual(waiting['actorHeader'],held['actorHeader']);self.assertEqual(waiting['state'],held['state'])
        self.advance_cleanup_primary();fresh=step();self.assertIsNone(fresh['error'],fresh)
        self.assertGreater(fresh['actualReads'],waiting['actualReads']);self.assertEqual(2,fresh['counts']['posts'])
        self.assertEqual(fresh['state']['quiet']['sequences'][-1],fresh['state']['last']['original']['sample']['actorSequence'])

    def interrupted_uncued_quiet(self):
        step=self.cleanup_frontier(ready=False);value=step(stopAfterQuiet=True)
        self.assertEqual('NativeUIError',value['error']['error'],value);self.assertEqual(1,value['quietStops'])
        quiet=value['state']['quiet'];self.assertTrue(quiet['complete'])
        self.assertGreaterEqual(quiet['last']-quiet['started'],3);self.assertGreaterEqual(len(quiet['sequences']),3)
        self.assertGreaterEqual(value['actualReads'],3);self.assertEqual(0,value['counts']['posts'])
        self.assertIsNone(value['state']['pending']);self.assertIsNone(value['state']['last'])
        self.assertIsNone(value['state']['primaryCue']);self.assertFalse(self.reader.request('/runs/'+RUN)['entries'])
        self.assertEqual(quiet,unpack(value['actorHeader']['payload'])[0]['quiet'])
        return step,value

    def test_legacy_saved_complete_quiet_requires_new_read_and_real_gap_reset_before_first_receipt(self):
        step,first=self.interrupted_uncued_quiet();time.sleep(1.6)
        fresh=step(cold=True);self.assertIsNone(fresh['error'],fresh)
        self.assertGreater(fresh['actualReads'],first['actualReads']);self.assertGreaterEqual(len(fresh['points']),3)
        point=fresh['points'][0];self.assertGreater(point['last']-point['previousLast'],1.5)
        self.assertEqual(point['started'],point['last']);self.assertFalse(point['complete'])
        quiet=fresh['state']['quiet'];self.assertTrue(quiet['complete'])
        self.assertGreaterEqual(quiet['last']-quiet['started'],3);self.assertGreaterEqual(len(quiet['sequences']),3)
        self.assertEqual(1,fresh['counts']['posts']);self.assertIsNone(fresh['state']['primaryCue'])
        self.assertEqual(quiet['sequences'][-1],fresh['state']['last']['original']['sample']['actorSequence'])
        held=step();self.assertIsNone(held['error'],held);self.assert_no_further_acquisition(fresh,held)
        self.assertEqual(fresh['actorHeader'],held['actorHeader']);self.assertEqual(fresh['state'],held['state'])

    def test_legacy_saved_complete_quiet_cannot_publish_an_ignored_read_returning_old_facts(self):
        step,first=self.interrupted_uncued_quiet()
        rejected=step(cold=True,readFault='ignored');self.assertEqual('NativeUIError',rejected['error']['error'],rejected)
        self.assertEqual(first['actualReads'],rejected['actualReads']);self.assertEqual(1,rejected['ignoredReads'])
        self.assertEqual(first['counts']['reads']+1,rejected['counts']['reads']);self.assertEqual(0,rejected['counts']['posts'])
        self.assertEqual(first['actorHeader'],rejected['actorHeader']);self.assertEqual(first['roleHeader'],rejected['roleHeader'])
        self.assertEqual([],rejected['points']);self.assertFalse(self.reader.request('/runs/'+RUN)['entries'])

    def test_legacy_saved_complete_quiet_cannot_publish_a_foreign_actual_native_source(self):
        step,first=self.interrupted_uncued_quiet()
        rejected=step(cold=True,readFault='foreign-native');self.assertEqual('NativeUIError',rejected['error']['error'],rejected)
        self.assertGreater(rejected['actualReads'],first['actualReads']);self.assertGreater(rejected['foreignSources'],0)
        self.assertEqual(0,rejected['counts']['posts']);self.assertEqual(first['actorHeader'],rejected['actorHeader'])
        self.assertEqual([],rejected['points']);self.assertFalse(self.reader.request('/runs/'+RUN)['entries'])

    def test_cleanup_uncertain_post_recovers_receipt_without_reacquiring_or_reposting(self):
        step=self.cleanup_frontier();uncertain=step(loseReply=True)
        self.assertEqual('NativeUIError',uncertain['error']['error'],uncertain)
        self.assertEqual(1,uncertain['lostReplies'])
        self.assertEqual(1,uncertain['counts']['posts']);self.assertTrue(uncertain['state']['pending']['issued'])
        self.assertIsNotNone(uncertain['state']['primaryCue']);self.assertIsNone(uncertain['state']['last'])
        accepted=self.reader.request('/runs/'+RUN)['entries'];self.assertEqual(1,len(accepted))
        recovered=step(cold=True);self.assertIsNone(recovered['error'],recovered)
        self.assert_no_further_acquisition(uncertain,recovered);self.assertIsNone(recovered['state']['pending'])
        self.assertEqual(uncertain['state']['primaryCue'],recovered['state']['primaryCue'])
        self.assertEqual(accepted[0],recovered['state']['last']['receipt'])
        held=step();self.assertIsNone(held['error'],held);self.assert_no_further_acquisition(recovered,held)
        self.assertEqual(accepted,self.reader.request('/runs/'+RUN)['entries'])

    def test_cleanup_warm_gap_requalifies_a_genuine_newer_primary_prefix(self):
        step=self.cleanup_frontier();first=self.completed_frontier(step);self.advance_cleanup_primary();advanced=[]
        def gap(value):
            self.assertEqual(first['counts'],value['counts'])
            advanced.append(self.advance_cleanup_primary()) # Acquires the actual source lock while Actor waits.
        fresh=step(at_gap=gap);self.assertIsNone(fresh['error'],fresh)
        self.assertGreater(fresh['counts']['reads'],first['counts']['reads']);self.assertEqual(2,fresh['counts']['posts'])
        self.assertEqual(advanced[0],fresh['state']['primaryCue']['header'])

    def cleanup_warm_gap_counter(self,mutation):
        step=self.cleanup_frontier();first=self.completed_frontier(step);self.advance_cleanup_primary();changed={}
        def gap(value):
            self.assertEqual(first['counts'],value['counts'])
            # All mutations occur after genuine first-stage admission and
            # source-lock release, before any second-stage current acquisition.
            if mutation in ('feature','actor','role'):
                name={'feature':'feature.json','actor':'phone-snapshots-actor-lifecycle.json',
                    'role':'phone-snapshots-actor-originals.json'}[mutation]
                store=PrivateFeatureState(self.root/name);previous=store.read()
                if mutation=='actor':
                    state=unpack(previous['payload'])[0];state['dropped'].append(dict(foreignWarmOwner=True))
                    foreign=dict(previous,payload=pack([state]))
                elif mutation=='role':
                    foreign=deepcopy(previous);foreign['binding']['targetFingerprint']='f'*64
                else:
                    state=unpack(previous['payload'])[0];state['phase']='active'
                    foreign=dict(previous,payload=pack([state]))
                store.write(foreign,previous);changed.update(store=store,foreign=foreign)
            elif mutation=='candidate-rollback':
                store=PrivateFeatureState(self.root/'phone-snapshots-primary-originals.json')
                foreign=deepcopy(first['state']['primaryCue']['header']);store.write(foreign,store.read())
                changed.update(store=store,foreign=foreign)
            elif mutation=='phase':self.reader.activate('e'*32,'cleanup',{})
            elif mutation=='old-file':
                path=next(self.root.glob('emote-frame-snapshots-'+RUN+'-actor-*.json'))
                raw=path.read_bytes()+b' ';path.write_bytes(raw);changed.update(path=path,raw=raw)
            else:
                self.assertIn(mutation,('pid','sdk','last-native-memory'));return mutation
        rejected=step(at_gap=gap);self.assertEqual('NativeUIError',rejected['error']['error'],rejected)
        self.assertEqual(first['counts'],rejected['counts'])
        self.assertEqual(first['state']['primaryCue'],rejected['state']['primaryCue'])
        self.assertEqual(1,len(self.reader.request('/runs/'+RUN)['entries']))
        if 'store' in changed:self.assertEqual(changed['foreign'],changed['store'].read())
        if 'path' in changed:self.assertEqual(changed['raw'],changed['path'].read_bytes())
        if mutation=='last-native-memory':self.assertTrue(rejected['memoryMutated'])
        else:self.assertFalse(rejected['memoryMutated'])

    def test_cleanup_warm_gap_rejects_changed_feature_owner(self):self.cleanup_warm_gap_counter('feature')
    def test_cleanup_warm_gap_rejects_changed_actor_owner(self):self.cleanup_warm_gap_counter('actor')
    def test_cleanup_warm_gap_rejects_changed_role_owner(self):self.cleanup_warm_gap_counter('role')
    def test_cleanup_warm_gap_rejects_changed_process_binding(self):self.cleanup_warm_gap_counter('pid')
    def test_cleanup_warm_gap_rejects_changed_sdk_scope(self):self.cleanup_warm_gap_counter('sdk')
    def test_cleanup_warm_gap_rejects_new_actual_cleanup_activation(self):self.cleanup_warm_gap_counter('phase')
    def test_cleanup_warm_gap_rejects_candidate_rollback_to_consumed_floor(self):self.cleanup_warm_gap_counter('candidate-rollback')
    def test_cleanup_warm_gap_reopens_and_rejects_changed_old_original(self):self.cleanup_warm_gap_counter('old-file')
    def test_cleanup_warm_gap_rechecks_memory_after_last_native_callback(self):self.cleanup_warm_gap_counter('last-native-memory')

    def test_cleanup_warm_publication_rechecks_old_graph_after_last_save_native_guard(self):
        step=self.cleanup_frontier();first=self.completed_frontier(step);self.advance_cleanup_primary()
        old_files={path:path.read_bytes() for pattern in ('emote-frame-snapshots-'+RUN+'-actor-*.json',
            'emote-index-snapshots-'+RUN+'-actor-*.json','snapshots-file-'+RUN+'-actor-*.bin')
            for path in self.root.glob(pattern)}
        self.assertTrue(old_files)
        rejected=step(at_gap=lambda _value:'last-save-memory')
        self.assertEqual('NativeUIError',rejected['error']['error'],rejected);self.assertTrue(rejected['memoryMutated'])
        self.assertGreater(rejected['counts']['reads'],first['counts']['reads'])
        self.assertEqual(first['counts']['posts'],rejected['counts']['posts'])
        durable=unpack(rejected['actorHeader']['payload'])[0]
        self.assertIsNone(durable['pending']);self.assertEqual(first['state']['primaryCue'],durable['primaryCue'])
        self.assertEqual(1,len(self.reader.request('/runs/'+RUN)['entries']))
        for path,raw in old_files.items():self.assertEqual(raw,path.read_bytes())

    def run_actor(self,token='a'*64):
        # Ordinary preparation pins an actual Feature owner across its lock
        # gap. Write it through the real owner save before the separate child;
        # the component boundary's loader remains an explicit host seam.
        from overte_phone_snapshots_feature import PhoneSnapshotsFeature
        f=self.boundary.feature
        with f.lock.held():
            f.previous=f.store.read();PhoneSnapshotsFeature.save(f)
            self.assertEqual(f.previous,f.store.read())
        # Fork only after stopping the loopback server thread; restart that
        # same listener immediately in the parent before any actor I/O.
        self.server.shutdown();self.thread.join(3);self.assertFalse(self.thread.is_alive())
        ctx=multiprocessing.get_context('fork');queue=ctx.Queue();process=ctx.Process(target=actor_once,args=(self.boundary,self.url,token,queue));process.start()
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();process.join(15)
        if process.is_alive():process.terminate();process.join(3);self.fail('Explicit host actor seam exceeded its bounded completion')
        self.assertEqual(0,process.exitcode);return queue.get(timeout=2)
    def test_actual_separate_process_publishes_own_originals_with_actor_credentials(self):
        result=self.run_actor();self.assertNotIn('error',result);self.assertIs(result['result'],False);self.assertNotEqual(os.getpid(),result['pid'])
        value=self.reader.request('/runs/'+RUN);self.assertEqual(1,len(value['entries']));self.assertEqual(1,value['entries'][0]['facts']['files'])
        header=PrivateFeatureState(self.root/'phone-snapshots-actor-lifecycle.json').read();state=unpack(header['payload'])[0]
        self.assertEqual(dict(pid=result['pid'],start=result['start']),state['process']);self.assertIsNone(state['pending']);self.assertEqual('watching',state['phase'])
        primary=PrivateFeatureState(self.root/'phone-snapshots-primary-originals.json').read()
        self.assertIsNotNone(primary);self.assertEqual(primary,state['primaryCue']['header'])
        self.assertTrue(list(self.root.glob('snapshots-file-'+RUN+'-actor-*.bin')))
    def test_reader_credentials_cannot_publish_even_after_actual_independent_measurement(self):
        result=self.run_actor('r'*64);self.assertIn('error',result);self.assertFalse(self.reader.request('/runs/'+RUN)['entries'])
        state=unpack(PrivateFeatureState(self.root/'phone-snapshots-actor-lifecycle.json').read()['payload'])[0]
        self.assertTrue(state['pending']['issued']);self.assertIsNone(state['last']);self.assertEqual('watching',state['phase'])
    def test_own_original_quiet_and_actual_closed_phase_precede_actor_retirement(self):
        b=self.boundary;b.clean();self.reader.activate('d'*32,'cleanup',{});b.feature.state['actions']=[dict(ticket='d'*32,phase='acknowledged')]
        b.provider.update(ticket='d'*32,activations=[dict(ticket=TICKET,verb='capture',capturedEpochMs=19000),dict(ticket='d'*32,verb='cleanup',capturedEpochMs=20000)])
        self.advance_cleanup_primary()
        self.server.shutdown();self.thread.join(3)
        ctx=multiprocessing.get_context('fork');queue=ctx.Queue();receive,send=ctx.Pipe(duplex=False)
        process=ctx.Process(target=actor_until_closed,args=(b,self.url,queue,receive));process.start()
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        try:
            ready=queue.get(timeout=25);self.assertNotIn('error',ready);self.assertGreaterEqual(ready['quiet']['last']-ready['quiet']['started'],3)
            self.assertGreaterEqual(len(ready['quiet']['sequences']),3);self.reader.close();send.send('closed')
            final=queue.get(timeout=15);self.assertNotIn('error',final);self.assertIs(final['result'],True);self.assertEqual('retired',final['phase']);self.assertFalse(final['closure']['active'])
            # A stored retired plan must not hide actual late target work.
            late=b.producer.directory/('e2e-'+RUN+'-late.png');late.write_bytes(b.raw);send.send('late')
            rejected=queue.get(timeout=10);self.assertEqual('NativeUIError',rejected.get('error'));self.assertEqual(b.raw,late.read_bytes())
            process.join(3);self.assertEqual(0,process.exitcode)
        finally:
            if process.is_alive():process.terminate();process.join(3)
        state=unpack(PrivateFeatureState(self.root/'phone-snapshots-actor-lifecycle.json').read()['payload'])[0]
        self.assertEqual('retired',state['phase']);self.assertIsNone(state['partialClosure']);self.assertIsNone(state['pending'])
    def test_incomplete_actual_quiet_sample_releases_lock_before_another_role_read(self):
        from overte_phone_script_lock import PhoneScriptSourceLock
        b=self.boundary;b.clean();self.reader.activate('d'*32,'cleanup',{});b.feature.state['actions']=[dict(ticket='d'*32,phase='acknowledged')]
        b.provider.update(ticket='d'*32,activations=[dict(ticket=TICKET,verb='capture',capturedEpochMs=19000),dict(ticket='d'*32,verb='cleanup',capturedEpochMs=20000)])
        self.advance_cleanup_primary()
        self.server.shutdown();self.thread.join(3)
        ctx=multiprocessing.get_context('fork');queue=ctx.Queue();receive,send=ctx.Pipe(duplex=False)
        process=ctx.Process(target=actor_until_closed,args=(b,self.url,queue,receive,True));process.start()
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        try:
            progress=queue.get(timeout=15);self.assertNotIn('error',progress);self.assertTrue(progress['progress'])
            self.assertIsNone(progress['quiet'])
            self.assertFalse(self.reader.request('/runs/'+RUN)['entries'])
            # A genuinely separate process remains alive with unfinished quiet
            # work while the primary can acquire the original OS source lock.
            self.assertTrue(process.is_alive())
            with PhoneScriptSourceLock(b.feature.lock.path,timeout=.1).held():pass
            send.send('continue');ready=queue.get(timeout=25);self.assertNotIn('error',ready)
            self.assertGreaterEqual(ready['quiet']['last']-ready['quiet']['started'],3)
            self.assertGreaterEqual(len(ready['quiet']['sequences']),3)
            self.reader.close();send.send('closed');final=queue.get(timeout=15);self.assertNotIn('error',final)
            self.assertTrue(final['result']);send.send('exit');process.join(3);self.assertEqual(0,process.exitcode)
        finally:
            if process.is_alive():process.terminate();process.join(3)

    def between_lock_counter(self,mutation):
        b=self.boundary;b.clean();self.reader.activate('d'*32,'cleanup',{});b.feature.state['actions']=[dict(ticket='d'*32,phase='acknowledged')]
        b.provider.update(ticket='d'*32,activations=[dict(ticket=TICKET,verb='capture',capturedEpochMs=19000),dict(ticket='d'*32,verb='cleanup',capturedEpochMs=20000)])
        self.advance_cleanup_primary()
        self.server.shutdown();self.thread.join(3)
        ctx=multiprocessing.get_context('fork');queue=ctx.Queue();receive,send=ctx.Pipe(duplex=False)
        process=ctx.Process(target=actor_until_closed,args=(b,self.url,queue,receive,True));process.start()
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        foreign_store=None;foreign=None
        try:
            progress=queue.get(timeout=15);self.assertNotIn('error',progress);self.assertIsNone(progress['quiet'])
            if mutation=='closed':self.reader.close()
            elif mutation=='ticket':self.reader.activate('e'*32,'cleanup',{})
            elif mutation=='late-file':
                late=b.producer.directory/('e2e-'+RUN+'-late-between-locks.png');late.write_bytes(b.raw)
            elif mutation in ('feature','role'):
                foreign_store=b.feature.store if mutation=='feature' else PrivateFeatureState(b.root/'phone-snapshots-actor-originals.json')
                previous=foreign_store.read();foreign=dict(foreignActualHeader=True);foreign_store.write(foreign,previous)
            elif mutation=='actor':
                foreign_store=PrivateFeatureState(b.root/'phone-snapshots-actor-lifecycle.json');previous=foreign_store.read()
                state=unpack(previous['payload'])[0];state['dropped'].append(dict(foreign=True));foreign=dict(previous,payload=pack([state]))
                foreign_store.write(foreign,previous)
            elif mutation in ('feature-load','actor-load'):
                # The first second-stage comparison sees the original owner;
                # replace the actual file after that read returns, so only
                # the post-load exact previous pin can reject its adoption.
                foreign_store=b.feature.store if mutation=='feature-load' else PrivateFeatureState(b.root/'phone-snapshots-actor-lifecycle.json')
            else:self.assertEqual('pid',mutation)
            send.send('foreign-binding' if mutation=='pid' else mutation if mutation in ('feature-load','actor-load') else 'continue')
            rejected=queue.get(timeout=15);self.assertEqual('NativeUIError',rejected.get('error'),rejected)
            process.join(3);self.assertEqual(0,process.exitcode)
            if mutation!='closed':self.assertFalse(self.reader.request('/runs/'+RUN)['entries'])
            if mutation=='feature-load':self.assertEqual(dict(foreignFeatureDuringLoad=True),foreign_store.read())
            elif mutation=='actor-load':self.assertEqual([dict(foreignLoad=True)],unpack(foreign_store.read()['payload'])[0]['dropped'])
            elif foreign_store is not None:self.assertEqual(foreign,foreign_store.read())
            if mutation=='late-file':self.assertEqual(b.raw,late.read_bytes())
        finally:
            if process.is_alive():process.terminate();process.join(3)

    def test_actual_closed_phase_between_preparation_and_quiet_is_red(self):self.between_lock_counter('closed')
    def test_new_actual_cleanup_ticket_between_preparation_and_quiet_is_red(self):self.between_lock_counter('ticket')
    def test_changed_feature_owner_between_preparation_and_quiet_is_red(self):self.between_lock_counter('feature')
    def test_changed_actor_journal_cannot_be_loaded_as_the_prepared_owner(self):self.between_lock_counter('actor')
    def test_changed_role_journal_cannot_be_loaded_as_the_prepared_floor(self):self.between_lock_counter('role')
    def test_changed_original_process_binding_between_locks_is_red(self):self.between_lock_counter('pid')
    def test_late_actual_owned_file_between_preparation_and_quiet_is_red(self):self.between_lock_counter('late-file')
    def test_feature_load_cannot_adopt_changed_owner_after_first_comparison(self):self.between_lock_counter('feature-load')
    def test_actor_load_cannot_adopt_valid_changed_journal_after_first_comparison(self):self.between_lock_counter('actor-load')

    def test_partial_cleanup_records_only_the_owner_proof_after_actual_close(self):
        b=self.boundary;f=b.feature;f.role='actor';f.load=lambda:None;f.previous=f.store.read();f.state.update(phase='partial-cleaned',partial=True)
        f.state['hostProcess']=dict(pid=os.getpid()+100,start='explicit-host-identity-seam')
        phase=PhaseFixtureReader(Client(self.url,'a'*64),RUN,'snapshots',epoch_ms=lambda:b.epoch);f.phase.client=phase.client;f.phase.status=phase.status
        proof=dict(originalScope='zero-issued',kernelBinding=deepcopy(f.binding));calls=[]
        f.partial_restored=lambda:calls.append('original-proof') or deepcopy(proof)
        actor=PhoneSnapshotsActor(f);self.assertIs(actor.step(),False);self.assertFalse(calls);self.reader.close()
        def refused():raise NativeUIError('Original owner still has an unresolved partial obligation')
        f.partial_restored=refused
        with self.assertRaises(NativeUIError):actor.step()
        self.assertEqual('watching',actor.state['phase']);self.assertIsNone(actor.state['partialClosure'])
        f.partial_restored=lambda:calls.append('original-proof') or deepcopy(proof)
        self.assertIs(actor.step(),True);self.assertEqual(['original-proof'],calls);self.assertEqual(proof,actor.state['partialClosure'])
        self.assertIsNone(actor.state['last']);self.assertIsNone(actor.state['quiet']);self.assertIsNone(actor.state['pending'])
        self.assertFalse(list(self.root.glob('snapshots-file-'+RUN+'-actor-*')))
    def test_primary_process_cannot_claim_separate_actor_identity(self):
        b=self.boundary;f=b.feature;f.role='actor';f.load=lambda:None;f.phase.client=Client(self.url,'a'*64)
        with self.assertRaises(NativeUIError):PhoneSnapshotsActor(f).step()
        self.assertIsNone(PrivateFeatureState(self.root/'phone-snapshots-actor-lifecycle.json').read())

if __name__=='__main__':unittest.main()
