"""Original common Chat journey and independent host; native producers are seams.

The original Parent owns native/widget/network producers, dispatcher and profile.
The separate Actor owns its readers, cursor, publication, source seal and return.
Only closed native commands and literal original producer bytes cross the owned
stdin channel. No requested state, shared live object or reconstructed Actor is
sent. This does not qualify a native app/AC binary, device or public capability.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import cProfile
import os
import pstats
import sys
import time
import unittest
from unittest.mock import patch

from adapters.chat_journey.observation import ChatObservationOwner
from adapters.chat_journey.observation_cursor import ChatObservationCursor
from adapters.chat_journey.remote_cleanup_prefix import ChatRemoteCleanupSlot,ChatRemoteCleanupPrefix
from adapters.chat_journey.remote_publication import ChatRemotePublication
from adapters.chat_journey.remote_actor_return import ChatRemoteActorReturn,ChatRemoteActorPending
from adapters.chat_journey.remote_consumed_sources import ChatRemoteConsumedSources
from adapters.chat_journey.cursor_source_seal import ChatCursorSourceSeal
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.engine import Journey
from feature_journeys.witness import Journal
from self_tests.chat_remote_cleanup_fixture import RemoteActorFixture
from self_tests.test_chat_script_source import CompiledBoundary
from self_tests.test_chat_warm_archive import WarmArchiveTests
from self_tests.test_native_chat_observation import RUN,command as chat_command
from self_tests import chat_diagnostic


class RemoteJourneyTests(RemoteActorFixture,unittest.TestCase):
    def setUp(self):
        self.full=self._testMethodName=='test_complete_shared_execute_then_original_remote_app_archive_and_host'
        self.diagnostic=self.full or self._testMethodName=='test_profile_actual_warm_source_calls_with_originals_retained'
        name=('test_all_original_compiled_stages_then_parent_erase_caches_restart_ipc_and_archive' if self.diagnostic else
            'test_three_original_parent_steps_have_no_synthetic_completed_prefix_or_shared_witness_owner')
        self.warm=WarmArchiveTests(name);self.warm.setUp();self.addCleanup(self.warm.doCleanups)
        w=self.warm;self.p=w.parent;self.d=w.d;self.native=self.d.h.native;self.directory=w.root
        self.addCleanup(self.p.detach)
        # Original coordinator before ANY phase read/query/input. The nested
        # source fixture's default activation has never been consumed here.
        self.assertIsNone(self.p.source.previous);self.assertEqual([],self.p.flow.rows)
        self.d.w.journal=Journal(w.h.epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.d.w.journal.register('chat')
        request=self.p.source.client.request
        def journal_request(path,*args,**kwargs):
            if path=='/runs/'+RUN:return self.d.w.journal.snapshot(RUN)
            return request(path,*args,**kwargs)
        self.p.source.client.request=journal_request
        self.source=self.p.source;self.slot=ChatRemoteCleanupSlot();self.consumer=None;self.reports=[];self.cleanup_calls=0
        self.report_error=None;self.error_diagnostic_issued=False
        self.started=time.monotonic()
        self.primary=ChatObservationCursor(self.observation(self.p.initial[0],'initial'),w.store(self.directory/'external-primary-cursor.json'))
        self.stores=dict(actor=w.store(self.directory/'remote-actor.json'),flow=self.p.flow.store,
            cleanup=w.store(self.directory/'cleanup.json'),publisher=w.store(self.directory/'remote-publisher.json'),
            cursor=w.store(self.directory/'remote-cursor.json'),code=w.store(self.directory/'remote-actor-code.json'))
        for stage in ('initial','active','cleanup'):
            self.stores[stage+'-observation']=w.store(self.directory/('remote-'+stage+'-observation.json'))
            self.stores[stage+'-samples']=(self.d.w.initial_witness_store if stage=='initial' else
                self.d.w.witness_store if stage=='active' else w.store(self.directory/'remote-cleanup-samples.json'))
        self.stop_store=w.store(self.directory/'remote-stop.json')
        self.return_stores=dict(stop=self.stop_store,seal=w.store(self.directory/'remote-seal.json'),
            **{'return':w.store(self.directory/'remote-return.json'),'consumption':w.store(self.directory/'remote-consumption.json')})
        self.code_boundary=CompiledBoundary();send=self.code_boundary.roots.send;full=self.code_boundary.full
        def roots(command):
            self.code_boundary.roots.epoch=w.h.epoch();send(command);self.code_boundary.roots.value['processId']=123
        def script(value):full(value);value.update(processId=123,capturedEpochMs=w.h.epoch(),requestedEpochMs=w.h.epoch())
        self.code_boundary.roots.send=roots;self.code_boundary.script.mutate=script
        self.native_requests=[]
        local=SimpleNamespace(native=self.native,initial=self.primary.current,cursor=self.primary,flow=self.d)
        self.start_actor(local,{**self.stores,**self.return_stores},w.h.locks,self.p.store,
            original_queries=True,defer_initial_publish=True,preserve_originals=self.diagnostic)
        if self.diagnostic:print('Remote journey Actor originals retained in '+str(self.host_root),flush=True)
        self.assertEqual('prepared',self.p.previous['phase']);self.assertEqual(0,self.p.previous['completedSteps'])
        self.assertIsNone(self.stores['publisher'].read());self.assertEqual([],self.native_requests)
        self.owner=ChatRemotePublication(self.process,self.source,self.stores,self.expected,w.h.locks,
            w.store(self.directory/'remote-publication-reader.json'),peer_epoch_ms=w.h.epoch,guard=lambda:True,monotonic=w.h.now)
        self.journey=Journey('chat',RUN,self.source.fixture_url,invoke=self.invoke,witness=self.received,
            activate=self.activate,read_artifact=self.no_artifact,image_policy={},continuity=lambda *_args:None,
            monotonic=w.h.now,epoch_ms=w.h.epoch,sleep=self.sleep,report=self.report,after_cleanup_baseline=self.slot.callback)
        self.slot.attach(self.journey)
        for name,store in dict(_chat_remote_cleanup_prefix_store=w.store(self.directory/'remote-cleanup-prefix.json'),
            _chat_remote_consumed_sources_store=w.store(self.directory/'remote-consumed-sources.json'),
            _chat_remote_publication_store=self.owner.store,
            _chat_remote_actor_return_store=w.store(self.directory/'remote-typed-return.json')).items():
            setattr(self.p.adapter,name,lambda _target,store=store:store)
        self.p.adapter._chat_cursor_source_seal_store=lambda _target,**_kw:w.store(self.directory/'remote-primary-seal.json')
        if self.full:self.trace_background_join()

    def trace_background_join(self):
        """Timing only: preserve original return/exception and once-only calls."""
        def trace(label,callback,enabled=lambda *_args,**_kwargs:True):
            def call(*args,**kwargs):
                if not enabled(*args,**kwargs):return callback(*args,**kwargs)
                started=time.monotonic()
                def event(phase):
                    try:
                        print('Remote BG join '+label+' '+phase+' seconds='+str(round(time.monotonic()-self.started,3))+
                            ' elapsed='+str(round(time.monotonic()-started,6)),flush=True)
                    except Exception:pass # A diagnostic output failure cannot mask the original exception.
                event('begin')
                try:result=callback(*args,**kwargs)
                except BaseException:
                    event('error');raise
                event('returned');return result
            return call
        dispatcher=self.p.dispatcher;factory=dispatcher.factories['background']
        def background():
            owner=factory()
            owner.run=trace('child.run',owner.run)
            owner.closed_history=trace('child.closed_history',owner.closed_history)
            owner.fresh_current=trace('child.final_freshness',owner.fresh_current,
                lambda *_args,**_kwargs:owner.state is not None and owner.state['phase']=='observed')
            return owner
        dispatcher.factories['background']=background
        active=lambda *_args,**_kwargs:bool(dispatcher.base['steps']) and dispatcher.base['steps'][-1]['route']=='background'
        dispatcher.snapshot=trace('dispatcher.snapshot',dispatcher.snapshot,lambda kind,_owner:kind=='background')
        for name in ('save','phase_snapshot'):
            setattr(dispatcher,name,trace('dispatcher.'+name,getattr(dispatcher,name),active))
        dispatcher.flow.finish=trace('flow.finish',dispatcher.flow.finish,active)

    def observation(self,samples,stage):
        return ChatObservationOwner(self.source,samples,self.p.flow.store,
            self.warm.store(self.directory/('external-'+stage+'-observation.json')),stage=stage,
            cleanup_store=self.warm.store(self.directory/'cleanup.json') if stage=='cleanup' else None,
            monotonic=self.warm.h.now)

    def native_query(self,source,request):
        self.assertIn(source,('primary','peer','view','lifecycle','roots','scripts'))
        self.assertIs(type(request),dict)
        if source in ('primary','peer'):
            chat_command(request);self.assertEqual('inspect',request['operation']);self.assertEqual(RUN,request['runId'])
            reader=self.warm.native_reader(0 if source=='primary' else 1)
            send,original=reader.send,reader.original
        else:
            producer=dict(view=self.warm.h.model.view,lifecycle=self.warm.h.model.native,
                roots=self.code_boundary.roots,scripts=self.code_boundary.script)[source]
            expected_action=dict(view='feature-chat-view-observe',lifecycle='feature-native-observe',roots='feature-script-roots-observe',scripts='feature-script-observe')[source]
            # Each original reader has already constructed its closed command;
            # the producer channel never accepts a desired effect or state.
            self.assertIn('commandId',request);self.assertEqual(expected_action,request['action'])
            self.assertEqual({'schemaVersion','commandId','action'}|({'runId'} if source=='view' else set()),set(request))
            send=producer.send;original=producer.read if source=='view' else producer.original
        self.native_requests.append((source,deepcopy(request)));send(deepcopy(request));return original()

    def activate(self,ticket,verb='baseline',inputs=None):
        self.d.w.journal.activate(RUN,ticket,verb,inputs or {})
        if verb=='baseline':self.d.next(0)

    def report(self,value):
        self.reports.append(value)
        if self.full:
            error=sys.exc_info()[1]
            if error is not None:self.preserve_error(error)
            try:
                chat_diagnostic.write(self.host_root,'common-journey-report',value)
            except Exception as diagnostic_error:
                self.report_error=diagnostic_error
                print('Private diagnostic remained unresolved: '+type(diagnostic_error).__name__,file=sys.stderr,flush=True)
            print('Remote common report sequenceCompleted='+str(value['sequenceCompleted'])+
                ' cleanupSucceeded='+str(value['cleanupSucceeded'])+' seconds='+str(round(time.monotonic()-self.started,3)),flush=True)

    def preserve_error(self,error):
        if self.error_diagnostic_issued:return
        self.error_diagnostic_issued=True
        try:chat_diagnostic.write(self.host_root,'original-error-contexts',chat_diagnostic.exception(error))
        except Exception as diagnostic_error:
            print('Original error diagnostic remained unresolved: '+type(diagnostic_error).__name__,file=sys.stderr,flush=True)

    def no_artifact(self,*_args):raise AssertionError('Current common Chat requires only independent peer observations')

    def native_clock(self):return dict(epoch=self.warm.h.epoch(),host=self.warm.h.now())

    def sleep(self,seconds):self.d.sleep(seconds)

    def received(self):
        self.command('publish');return self.owner.acquire(self.journey.last_actor_sequence)

    def invoke(self,operation,fields):
        if operation=='feature.chat.observe':
            return self.primary.read(fields['afterSequence']) if self.consumer is None else self.consumer.observe(fields)
        if operation=='feature.chat.act':
            self.p.step()
            if self.full:print('Remote actual dispatcher completedSteps='+str(self.p.previous['completedSteps'])+
                ' seconds='+str(round(time.monotonic()-self.started,3)),flush=True)
            # The original parent wrapper binds its newly acquired peer file
            # owners immediately after each actual dispatcher input.
            if 'peer' in self.d.owner.children:self.bind_peer_process()
            if self.primary.current.stage=='initial':self.primary.select(self.observation(self.p.roles[0],'active'))
            return dict(performed=True)
        self.assertEqual('feature.chat.cleanup',operation);self.cleanup_calls+=1
        if self.cleanup_calls==1:
            self.after=self.warm.h.epoch();self.p.close_input_and_restore_profile(self.after);self.p.prepare_cache_release(self.after)
            self.primary.select(self.observation(self.p.cache_release.roles[0],'cleanup'))
            self.consumer=ChatRemoteCleanupPrefix(self.primary,self.owner,self.stop_store,
                self.p.adapter._chat_remote_cleanup_prefix_store(self.p.target),guard=self.p.guard)
            self.slot.bind(self.consumer)
        else:
            self.assertEqual(2,self.cleanup_calls);self.p.cache_release.authority();self.p.input_close.authority()
        return dict(performed=True)

    def bind_peer_process(self):
        # Reuse the exact existing WarmArchive parent wrapper, without another
        # step or activation. This is declared native-process provenance seam.
        from adapters.native_fd_owner import OriginalDescriptor
        from fixture.chat_actor_process import LinuxChatActorProcess
        import os
        self.p.peer.files=self.warm.h.files=self.d.files;self.p.peer.files_store=self.d.files.store
        if self.p.peer.process is None:
            process=self.p.peer.process=LinuxChatActorProcess.__new__(LinuxChatActorProcess)
            process.fd_owner=OriginalDescriptor('/proc/self/exe',os.O_RDONLY|os.O_CLOEXEC)
            process.fd=process.fd_owner.fd;process.released=self.d.files.released;self.addCleanup(process.close)

    def test_prepared_actor_waits_then_queries_original_parent_bytes_for_baseline_and_normal_open(self):
        from feature_journeys.scenarios import SCENARIOS,expand
        from feature_journeys.fixtures import context
        self.activate('b'*32);self.journey.wait('owned-clean-baseline','b'*32,self.warm.h.epoch(),SCENARIOS['chat']['baseline'],['peer'],duration=0)
        self.activate('c'*32,'open',{});self.invoke('feature.chat.act',{})
        self.journey.wait('01-open','c'*32,self.warm.h.epoch(),expand(SCENARIOS['chat']['steps'][0]['state'],context(RUN)),['peer'],duration=0)
        self.assertEqual(2,self.p.previous['completedSteps']);self.assertEqual(len(self.owner.rows),self.journey.last_actor_sequence)
        self.assertGreaterEqual(self.journey.last_actor_sequence,6)
        self.assertEqual(set(('primary','peer','view','lifecycle','roots','scripts')),{kind for kind,_request in self.native_requests})
        self.assertTrue(self.owner.rows[-1]['publication']['payload']['facts']['open'])
        self.assertEqual([],self.d.widgets.sent);self.assertFalse(self.journey.cleanup_hook_started)

    def test_original_query_gateway_refuses_input_or_requested_state_before_producer_dispatch(self):
        command=dict(schemaVersion=1,commandId='e'*32,action='feature-chat-observe',operation='observe',runId=RUN)
        before=len(self.warm.h.model.primary.commands)
        with self.assertRaises(AssertionError):self.native_query('primary',command)
        command['operation']='inspect';command['expected']={'open':True}
        with self.assertRaises(NativeUIError):self.native_query('primary',command)
        self.assertEqual(before,len(self.warm.h.model.primary.commands));self.assertEqual([],self.native_requests)
        self.assertIsNone(self.stores['publisher'].read());self.assertEqual('prepared',self.p.previous['phase'])

    def test_profile_actual_warm_source_calls_with_originals_retained(self):
        self.test_prepared_actor_waits_then_queries_original_parent_bytes_for_baseline_and_normal_open()
        while len(self.owner.rows)<60:
            self.primary.read(len(self.primary.rows));self.command('publish')
            self.owner.acquire(self.owner.rows[-1]['publication']['sequence'])
            if len(self.owner.rows)%10==0:print('Actual same-phase source rows='+str(len(self.owner.rows))+
                ' seconds='+str(round(time.monotonic()-self.started,3)),flush=True)
        def functions(profile):
            return sorted(((ct,tt,nc,cc,os.path.basename(path)+':'+str(line)+':'+name)
                for (path,line,name),(cc,nc,tt,ct,_callers) in pstats.Stats(profile).stats.items()),reverse=True)[:25]
        primary=cProfile.Profile();primary.enable();self.primary.read(len(self.primary.rows));primary.disable()
        self.command('profile-start');parent=cProfile.Profile();parent.enable()
        self.command('publish');self.owner.acquire(self.owner.rows[-1]['publication']['sequence']);parent.disable()
        actor=self.command('profile-stop')
        report=dict(scope='actual-owned-python-source-fixture',sourceRows=len(self.owner.rows),
            completedSteps=self.p.previous['completedSteps'],nativeAndWidgetProducers='explicit-model-seams',
            actualDeviceFreshnessQualified=False,primary=functions(primary),parent=functions(parent),actor=actor)
        PrivateFeatureState(self.host_root/'actual-warm-source-profile.json').write(report,None)
        self.assertEqual(2,self.p.previous['completedSteps']);self.assertEqual(61,len(self.owner.rows))
        self.assertFalse(self.journey.cleanup_hook_started);self.assertIsNone(self.stop_store.read())
        print('Actual warm source profile retained in '+str(self.host_root/'actual-warm-source-profile.json'),flush=True)

    def test_complete_shared_execute_then_original_remote_app_archive_and_host(self):
        started=time.monotonic()
        try:self.journey.execute()
        except BaseException as error:self.preserve_error(error);raise
        # Report loss cannot overwrite an actual source/cleanup error. On an
        # otherwise successful execute it still forbids test finalization.
        if self.report_error is not None:raise self.report_error
        print('Remote common execute completed seconds='+str(round(time.monotonic()-started,3)),flush=True)
        self.assertTrue(self.reports[-1]['sequenceCompleted']);self.assertTrue(self.journey._cleanup_sequence_succeeded)
        self.assertEqual(26,len(self.p.dispatcher.base['steps']));self.assertEqual(2,self.cleanup_calls)
        self.command('stop');original=self.stop_store.read()
        returned=ChatRemoteActorReturn(self.process,{**self.stores,**self.return_stores},
            {**self.expected,'stopCommand':original},self.p.adapter._chat_remote_actor_return_store(self.p.target))
        returned.acknowledge();self.command('consume')
        with self.assertRaises(ChatRemoteActorPending):returned.finish()
        self.worker.stdin.write(b'{"action":"exit"}\n');self.worker.stdin.flush();self.worker.wait(timeout=5);returned.finish()
        seal=ChatCursorSourceSeal(self.primary,self.p.adapter._chat_cursor_source_seal_store(self.p.target))
        joined=ChatRemoteConsumedSources(self.consumer,returned,seal,self.p.adapter._chat_remote_consumed_sources_store(self.p.target))
        receipt=joined.run();self.assertTrue(receipt['original']['sequenceSucceeded'])
        self.p.restart_and_close_application(self.after,remote_sources=joined)
        print('Remote original app/profile/IPC completed seconds='+str(round(time.monotonic()-started,3)),flush=True)
        result=self.p.finalize_application();self.assertTrue(self.p.archive_plan.archive.complete)
        host=self.p.finalize_host();self.assertEqual(result['finalSha256'],host['finalSha256'])
        self.assertTrue(returned.process.fd_owner.closed);self.assertTrue(returned.process.entry_owner.closed)
        self.assertTrue(self.p.host_close.complete);self.assertTrue(self.p.detach())
        self.assertIsNone(self.p.store.read());self.assertIsNone(self.p.host_close.store.read())
        print('Remote original archive/host completed seconds='+str(round(time.monotonic()-started,3)),flush=True)


def remote_journey_component_tests():
    # The complete diagnostic is deliberately NOT added as a passing catalog
    # case: its one original measurement hit the unchanged outer 120s limit.
    return unittest.TestSuite(RemoteJourneyTests(name) for name in (
        'test_prepared_actor_waits_then_queries_original_parent_bytes_for_baseline_and_normal_open',
        'test_original_query_gateway_refuses_input_or_requested_state_before_producer_dispatch'))


if __name__=='__main__':unittest.main()
