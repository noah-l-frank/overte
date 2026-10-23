"""Real closed dispatcher/owners on explicit native, widget and HTTP seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import math
import os
from copy import deepcopy
import unittest
import uuid

from adapters.chat_journey.dispatcher import ChatDispatcher,KINDS,route
from adapters.chat_journey.flow_inputs import ChatFlowInputs,recipe
from adapters.chat_journey.cache_lifetime import ChatCacheLifetime
from adapters.chat_journey.normal_input import ChatNormalInput
from adapters.chat_journey.peer_send import ChatPeerSend
from adapters.chat_journey.peer_distant import ChatPeerDistant
from adapters.chat_journey.background import ChatBackground
from adapters.chat_journey.mixer import ChatMixerOwner
from adapters.chat_journey.mixer_control import FixtureMixerControl
from adapters.chat_journey.no_replay import ChatNoReplay
from adapters.chat_actor_files import ChatActorFiles,SOURCE,encode,node
from adapters.chat_peer_input import ChatPeerInput,COMMAND,RECEIPT
from adapters.chat_journey.samples import ChatCacheAbsence
from adapters.native_chat_observation import ChatCaptureOwner,OwnedChatCapture,identity
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.token_chat_ui import TokenChatUI
from feature_journeys.fixtures import context
from self_tests import test_chat_witness as witness_seams
from self_tests import test_chat_actor_files as actor_seams
from self_tests import test_chat_peer_position as position_seams
from self_tests import test_chat_mixer_owner as mixer_seams
from self_tests.test_token_chat_ui import Widgets
from self_tests.test_native_chat_observation import RUN,SELF,PEER


class DispatcherTests(unittest.TestCase):
    def setUp(self):
        self.w=witness_seams.WitnessTests();self.w.setUp();self.addCleanup(self.w.doCleanups)
        self.h=self.w.h;self.root=self.h.h.root;self.widgets=Widgets();self.cache_calls=0;self.factory_calls=[]
        self.h.binding['sessionId']=self.widgets.instance;self.h.peer_binding['sessionId']='f'*32
        self.roles=tuple(self.h.samples(role,store) for role,store in zip(('primary','actor'),(self.h.roles[0].store,self.h.roles[1].store)))
        initial=tuple(self.h.samples(role,sample.store,kind=ChatCacheAbsence) for role,sample in zip(('primary','actor'),self.w.initial_roles))
        self.flow=ChatFlowInputs(self.w.parent_source,self.roles,self.w.flow_store,self.w.witness_store,
            initial_roles=initial,initial_witness_store=self.w.initial_witness_store,monotonic=lambda:self.h.native.host)
        self.native_mixer='d'*64
        for boundary in (self.h.h.primary,self.h.h.peer):
            boundary.open_id='';boundary.retire_id='';previous=boundary.mutate
            def mutate(value,previous=previous,boundary=boundary):
                previous(value);value['source'].update(openedCommandId=boundary.open_id,retiredCommandId=boundary.retire_id)
                value['source']['mixerSha256']=self.native_mixer if value['source']['mixerPresent'] else ''
                value['source']['session']['domainSha256']=identity(RUN,mixer_seams.DOMAIN)
            boundary.mutate=mutate;send=boundary.send
            def send_owned(request,send=send,boundary=boundary):
                if request['operation']=='observe' and not boundary.open_id:
                    boundary.open_id=request['commandId'];boundary.opened=self.h.native.epoch
                if request['operation']=='retire' and not boundary.retire_id:boundary.retire_id=request['commandId']
                return send(request)
            boundary.send=send_owned
        ordinary=self.widgets.input
        self.widgets.bind_input_fence=lambda fence:setattr(self.widgets,'phase_fence',fence)
        def widget_input(identifier,action,reference,value=None):
            before=len(self.widgets.sent)
            if getattr(self.widgets,'phase_fence',None) is not None:self.widgets.phase_fence.check()
            try:return ordinary(identifier,action,reference,value)
            finally:
                if len(self.widgets.sent)>before:
                    channel,text=self.widgets.sent[-1];self.h.h.accept(text,sender=SELF,channel=channel,local=not self.h.h.primary.mixer)
                    self.h.h.primary.events[-1]['capturedEpochMs']=self.h.native.epoch
                    self.h.h.view.source['storage']['events'][-1]['timestamp']=self.h.native.epoch
                    if self.h.h.peer.mixer:
                        self.h.h.peer.event(text=text,sender=SELF,channel=channel)
                        self.h.h.peer.events[-1]['capturedEpochMs']=self.h.native.epoch
                    for key in ('local','domain'):
                        setattr(self.widgets,key,[row['text'] for row in self.h.h.view.source['storage']['events'] if row['channel']==key])
                self.sync()
        self.widgets.input=widget_input
        self.normal_store=PrivateFeatureState(self.root/'dispatch-normal.json');self.store=PrivateFeatureState(self.root/'dispatcher.json')
        self.factories={kind:lambda kind=kind:self.unused(kind) for kind in KINDS};self.factories['normal']=self.normal
        self.factories.update(peer=self.peer,distant=self.distant,background=self.background,mixer=self.mixer,
            **{'no-replay':lambda:ChatNoReplay(*self.roles,PrivateFeatureState(self.root/'dispatch-no-replay.json'),
                monotonic=lambda:self.h.native.host,sleep=self.sleep)})
        self.owner=self.create()

    def unused(self,kind):self.factory_calls.append(kind);raise AssertionError('Unrequested child factory')
    def create(self):return ChatDispatcher(self.flow,self.caches,self.factories,self.store)
    def sleep(self,seconds):self.h.sleep(seconds);self.widgets.elapsed+=round(seconds*1000)
    def sync(self):
        if self.widgets.panel:self.h.h.open(self.widgets.channel,self.widgets.draft)
        else:self.h.h.close()
        from self_tests.test_pico_chat_keyboard import keyboard
        self.h.h.view.source.update(tabletShown=self.widgets.tablet,editorFocused=self.widgets.focus,
            editorHasDraft=bool(self.widgets.draft),keyboard=keyboard(self.widgets.keyboard_request))
    def normal(self):
        self.factory_calls.append('normal')
        return ChatNormalInput(self.roles,lambda intent:TokenChatUI(self.widgets,intent,RUN,
            monotonic=lambda:self.h.native.host,sleep=self.sleep),self.normal_store,
            monotonic=lambda:self.h.native.host,sleep=self.sleep)
    def peer(self):
        self.factory_calls.append('peer');root=self.peer_directory();sha='f'*64
        source=root/SOURCE;source.write_bytes(encode(dict(actorVersion=1,instance='e'*32,processId=456,
            configuredEpochMs=self.h.native.epoch,scriptSha256=sha)));source.chmod(0o600)
        actor=self.make_peer_actor(root);self.actor=actor;self.addCleanup(actor.close_all);self.peer_fd=-1;self.peer_sequence=0
        self.peer_commands=[];self.peer_operations=[];self.point=dict(x=2.,y=0.,z=2.)
        self.peer_original=None;self.peer_mode='normal';self.release_time=None;self.polls=0
        def close():
            if self.peer_fd>=0:os.close(self.peer_fd);self.peer_fd=-1
        self.addCleanup(close)
        def released(identity):
            if self.peer_fd>=0 and node(os.fstat(self.peer_fd))==identity:return False
            return actor.released(identity)
        def tick(seconds):
            self.sleep(seconds);request=json.loads((root/COMMAND).read_bytes())
            if request['commandId'] in self.peer_commands:return
            self.peer_commands.append(request['commandId']);self.peer_sequence+=1
            operation=request['operation'];self.peer_operations.append(operation)
            if self.peer_mode!='moving':self.polls+=1
            temporary=root/'.input-receipt';fd=os.open(temporary,os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600)
            value=dict(actorFileVersion=1,commandNode=node((root/COMMAND).stat()),resultNode=node(os.fstat(fd)),
                native=dict(peerInputVersion=3,commandId=request['commandId'],runId=RUN,operation=operation,
                    instance='8'*32,sequence=self.peer_sequence,processId=456,capturedEpochMs=self.h.native.epoch,
                    avatarSha256=PEER,avatarPosition=self.actual(),scriptPolls=self.polls,
                    releaseConsumed=self.peer_mode=='moving' or operation=='release'))
            os.write(fd,encode(value));os.fsync(fd);os.replace(temporary,root/RECEIPT);close();self.peer_fd=fd
            if operation=='hold':self.peer_original=self.actual();self.point=deepcopy(request['position']);self.peer_mode='held'
            elif operation=='restore':self.point=deepcopy(self.peer_original);self.peer_mode='restored'
            elif operation=='release':self.peer_mode='moving';self.release_time=self.h.native.host
            elif operation=='send':
                if self.peer_mode=='held':
                    self.h.h.primary.event(text=context(RUN)[request['textKey']],channel=request['channel'])
                else:
                    self.h.h.accept(context(RUN)[request['textKey']],channel=request['channel'])
                    self.h.h.view.source['storage']['events'][-1]['timestamp']=self.h.native.epoch
                    for key in ('local','domain'):
                        setattr(self.widgets,key,[row['text'] for row in self.h.h.view.source['storage']['events'] if row['channel']==key])
                    self.sync()
                self.h.h.primary.events[-1]['capturedEpochMs']=self.h.native.epoch
        files=ChatActorFiles(root,PrivateFeatureState(self.root/'dispatch-peer-files.json'),self.roles[0].peer_binding,sha,
            lambda:True,released,clock_ms=lambda:self.h.native.epoch,monotonic=lambda:self.h.native.host,sleep=tick,
            require_original_fd=getattr(self,'strict_peer_files',False))
        self.files=files
        self.addCleanup(files.detach)
        owner=ChatPeerInput(files,PrivateFeatureState(self.root/'dispatch-peer-input.json'),RUN)
        return ChatPeerSend(owner,*self.roles,PrivateFeatureState(self.root/'dispatch-peer-send.json'),
            monotonic=lambda:self.h.native.host,sleep=self.sleep)
    def peer_directory(self):return self.root/'peer'
    def make_peer_actor(self,root):return actor_seams.FileActor(root)
    def actual(self):
        if self.peer_mode=='moving':return dict(x=2+.75*math.sin(self.h.native.host-self.release_time),y=0.,z=2.)
        return deepcopy(self.point)
    def distant(self):
        self.factory_calls.append('distant');pose=position_seams.Boundary()
        def mutate(value):value['capturedEpochMs']=self.h.native.epoch;value['source']['peerPosition']=self.actual()
        pose.mutate=mutate;sources=(pose.reader(),pose.reader())
        for source in sources:
            source.clock_ms=lambda:self.h.native.epoch;source.monotonic=lambda:self.h.native.host;source.sleep=self.sleep
        return ChatPeerDistant(self.owner.child('peer'),sources,PrivateFeatureState(self.root/'dispatch-distant.json'),
            monotonic=lambda:self.h.native.host,sleep=self.sleep)
    def background(self):
        self.factory_calls.append('background')
        self.h.next_timer=self.h.native.host+.25
        return ChatBackground(self.roles,self.h.source,self.h.os,self.h.target,self.h.store,
            monotonic=lambda:self.h.native.host,sleep=self.sleep)
    def mixer(self):
        self.factory_calls.append('mixer');controller=mixer_seams.Controller(lambda:self.h.native.epoch)
        store=PrivateFeatureState(self.root/'dispatch-mixer.json');self.mixer_controller=controller
        def apply(command):
            self.assertEqual(command,store.read()['commands'][-1]);controller.apply(command)
            self.h.h.primary.mixer=self.h.h.peer.mixer=command['action']=='online'
            if command['action']=='online':self.native_mixer='f'*64
        controller.effect=apply
        sources=tuple(FixtureMixerControl(mixer_seams.URL,mixer_seams.TOKEN,lambda:True,readonly=readonly,
            clock_ms=lambda:self.h.native.epoch,monotonic=lambda:self.h.native.host,opener=controller) for readonly in (False,True))
        return ChatMixerOwner(sources,self.roles,store,monotonic=lambda:self.h.native.host,sleep=self.sleep)
    def caches(self):
        self.cache_calls+=1;owners=[]
        for index,boundary in enumerate((self.h.h.primary,self.h.h.peer)):
            lock=self.roles[0].locks[index];binding=self.roles[0].binding if index==0 else self.roles[0].peer_binding
            owner=ChatCaptureOwner(PrivateFeatureState(lock.path.parent/'dispatch-capture.json'),binding,boundary.guard)
            owner.begin(RUN);reader=boundary.reader();reader.pid=123 if index==0 else 456
            reader.clock_ms=lambda:self.h.native.epoch;reader.monotonic=lambda:self.h.native.host;reader.sleep=self.sleep
            owner.admit(reader.perform(RUN,'inspect'))
            reader=boundary.reader();reader.pid=123 if index==0 else 456
            reader.clock_ms=lambda:self.h.native.epoch;reader.monotonic=lambda:self.h.native.host;reader.sleep=self.sleep
            owners.append(ChatCacheLifetime(OwnedChatCapture(reader,owner,RUN),PrivateFeatureState(lock.path.parent/'dispatch-cache.json'),
                lock,monotonic=lambda:self.h.native.host))
        return tuple(owners)
    def next(self,index):
        if index:
            self.sleep(.01);fixed=recipe(RUN)[index]
            self.w.journal.activate(RUN,uuid.uuid4().hex,fixed['verb'],fixed['inputs'])
        return self.owner.step()
    def through(self,end):
        for index in range(end+1):
            try:result=self.next(index)
            except Exception as error:
                while error.__context__ is not None:error=error.__context__
                import traceback
                self.fail('Original dispatcher step '+str(index)+' failed:\n'+''.join(traceback.format_exception(error)))
        return result
    def mutations(self):return [row for boundary in (self.h.h.primary,self.h.h.peer) for row in boundary.commands if row['operation']!='inspect']

    def test_fixed_normal_prefix_owns_real_cache_birth_cancel_reopen_and_independent_send(self):
        observed=self.through(7)
        self.assertEqual([context(RUN)['unicode']],observed[0]['state']['peerMessages'])
        self.assertEqual(1,self.cache_calls);self.assertEqual(['observe','observe'],[row['operation'] for row in self.mutations()])
        self.assertEqual(1,len(self.widgets.sent));self.assertEqual(['normal'],self.factory_calls)
        self.assertEqual(['completed']*8,[row['phase'] for row in self.store.read()['steps']])
        proofs=self.owner.history();self.assertEqual(['cache-primary','cache-peer','normal'],[row['kind'] for row in proofs[:3]])
        self.assertEqual('observed',self.owner.children['normal'].base['attempts'][-1]['phase'])
        self.assertFalse(any('facts' in row or 'state' in row for row in proofs))

    def test_parent_intent_is_durable_before_first_native_or_ui_input(self):
        self.next(0);original=self.h.h.primary.send
        def send(request):
            if request['operation']=='observe':
                self.assertEqual('issued',self.store.read()['steps'][-1]['phase'])
                self.assertEqual('issued',self.flow.store.read() and self.flow.rows[-1]['phase'])
            return original(request)
        self.h.h.primary.send=send
        before=self.widgets.input
        def widget(*args,**kwargs):
            self.assertEqual('issued',self.store.read()['steps'][-1]['phase']);return before(*args,**kwargs)
        self.widgets.input=widget;self.next(1)
        self.assertEqual(1,len(self.widgets.calls))

    def test_same_original_roles_join_normal_send_and_three_distinct_peer_inputs(self):
        observed=self.through(11)
        self.assertEqual(['normal','peer'],self.factory_calls);self.assertEqual(3,len(self.peer_commands))
        self.assertEqual([context(RUN)['reply']],observed[0]['state']['localMessages'])
        self.assertEqual([context(RUN)['unicode'],context(RUN)['reply'],context(RUN)['hidden']],observed[0]['state']['domainMessages'])
        self.assertEqual([context(RUN)['unicode']],observed[0]['state']['peerMessages'])
        self.assertEqual(1,len(self.widgets.sent));self.assertEqual('completed',self.store.read()['steps'][-1]['phase'])
        self.assertEqual(['received']*3,[row['phase'] for row in self.owner.children['peer'].store.read()['attempts']])

    def test_all_25_real_child_steps_share_original_native_ui_storage_and_peer_histories(self):
        self.complete_positive()

    def complete_positive(self,*,check_exhausted=True):
        from adapters.chat_journey.witness import ChatWitness
        from feature_journeys.scenarios import SCENARIOS,expand
        witness_samples=self.h.samples('actor',self.w.witness_store)
        witness_initial=self.h.samples('actor',self.w.initial_witness_store,kind=ChatCacheAbsence)
        publisher=ChatWitness(self.w.actor_source,witness_samples,self.w.flow_store,self.w.publisher_store,
            initial_samples=witness_initial,monotonic=lambda:self.h.native.host)
        for index in range(26):
            try:
                observed=self.next(index);self.assertEqual(index+1,publisher.publish())
                expected=expand(SCENARIOS['chat']['baseline'] if index==0 else SCENARIOS['chat']['steps'][index-1]['state'],context(RUN))
                for actual in (observed[0]['state'],self.w.journal.snapshot(RUN)['entries'][-1]['facts']):
                    for key,value in expected.items():
                        if type(value) is dict and 'oneOf' in value:self.assertIn(actual[key],value['oneOf'])
                        else:self.assertEqual(value,actual[key],str(index)+':'+key)
            except Exception as error:
                while error.__context__ is not None:error=error.__context__
                import traceback
                self.fail('Original dispatcher/witness step '+str(index)+' failed:\n'+''.join(traceback.format_exception(error)))
        self.assertFalse(observed[0]['state']['open']);self.assertEqual(26,len(self.flow.rows))
        self.assertEqual(['completed']*26,[row['phase'] for row in self.store.read()['steps']])
        self.assertEqual(['normal','peer','distant','background','mixer'],self.factory_calls)
        self.assertEqual(3,len(self.widgets.sent));self.assertEqual(['offline','online'],[row['action'] for row in self.mixer_controller.posts])
        self.assertEqual(1,self.peer_operations.count('hold'));self.assertEqual(1,self.peer_operations.count('restore'))
        self.assertEqual(1,self.peer_operations.count('release'));self.assertEqual(4,self.peer_operations.count('send'))
        self.assertEqual([context(RUN)['unicode'],context(RUN)['retry']],observed[0]['state']['peerMessages'])
        self.assertEqual([context(RUN)['unicode'],context(RUN)['reply'],context(RUN)['hidden'],context(RUN)['retry'],context(RUN)['retry']],observed[0]['state']['domainMessages'])
        self.assertEqual([context(RUN)['reply']],observed[0]['state']['localMessages'])
        self.assertTrue(self.h.native.released);self.assertFalse(self.h.native.active)
        self.assertEqual(26,len(self.w.posted));self.assertEqual(1,len(witness_initial.frames))
        self.assertEqual('complete',self.owner.children['no-replay'].previous['phase'])
        if check_exhausted:
            before=len(self.widgets.calls)
            with self.assertRaises(NativeUIError):self.owner.step()
            self.assertEqual(before,len(self.widgets.calls));self.assertIsNotNone(self.store.read())

    def test_late_final_native_clock_and_changed_fixture_ticket_cannot_seal_or_repeat_input(self):
        self.next(0);write=self.store.write
        def late(value,previous):
            write(value,previous)
            if len(value['steps'])==2 and value['steps'][-1]['phase']=='completed':self.h.native.epoch+=2000
        self.store.write=late
        with self.assertRaises(NativeUIError):self.next(1)
        self.assertEqual(1,len(self.widgets.calls));self.assertEqual('completed',self.store.read()['steps'][-1]['phase'])
        with self.assertRaises(NativeUIError):self.owner.step()
        with self.assertRaises(NativeUIError):self.create().step()
        self.assertEqual(1,len(self.widgets.calls))
        self.setUp();self.next(0)
        def changed():self.w.journal.activate(RUN,uuid.uuid4().hex,'type',recipe(RUN)[2]['inputs'])
        self.widgets.before=changed
        with self.assertRaises(NativeUIError):self.next(1)
        self.assertEqual('issued',self.store.read()['steps'][-1]['phase']);self.assertEqual(1,len(self.widgets.calls))
        with self.assertRaises(NativeUIError):self.owner.step()
        self.assertEqual(1,len(self.widgets.calls));self.assertEqual('',self.widgets.draft)

    def test_original_snapshot_lost_ack_retains_orphan_and_never_reconstructs_or_replays(self):
        self.next(0);append=self.owner.chunks.append
        def lost(frame,manifest):
            value=append(frame,manifest)
            if frame['kind']=='normal':raise OSError('Original snapshot landed; manifest receipt lost')
            return value
        self.owner.chunks.append=lost
        with self.assertRaises(NativeUIError):self.next(1)
        self.assertEqual(1,len(self.widgets.calls));self.assertEqual('reading',self.store.read()['phase'])
        original=self.store.path.read_bytes()
        with self.assertRaises(NativeUIError):self.owner.step()
        with self.assertRaises(NativeUIError):self.owner.history()
        with self.assertRaises(NativeUIError):self.create()
        self.assertEqual(original,self.store.path.read_bytes());self.assertEqual(1,len(self.widgets.calls))

    def test_normal_intent_cas_phase_change_or_native_jump_prevents_actual_transport(self):
        from adapters.script_journey.history import unpack
        for native in (False,True):
            with self.subTest(native=native):
                self.setUp();self.next(0);factory=self.factories['normal']
                def create():
                    owner=factory();write=owner.store.write
                    def changed(value,previous):
                        write(value,previous);attempt=unpack(value['attempts'])[-1]
                        if attempt['phase']=='issuing' and attempt['inputIntents']:
                            if native:self.h.native.epoch+=2000
                            else:self.w.journal.activate(RUN,uuid.uuid4().hex,'type',recipe(RUN)[2]['inputs'])
                    owner.store.write=changed;return owner
                self.factories['normal']=create
                with self.assertRaises(NativeUIError):self.next(1)
                self.assertEqual([],self.widgets.calls);self.assertEqual(2,len(self.mutations()))
                self.assertEqual('issued',self.store.read()['steps'][-1]['phase'])
                with self.assertRaises(NativeUIError):self.owner.step()
                self.assertEqual([],self.widgets.calls)

    def test_type_second_part_rechecks_phase_after_its_own_durable_cas(self):
        from adapters.script_journey.history import unpack
        self.through(1);owner=self.owner.children['normal'];write=owner.store.write
        def changed(value,previous):
            write(value,previous);attempt=unpack(value['attempts'])[-1]
            if attempt['verb']=='type' and len(attempt['inputIntents'])==2:
                self.w.journal.activate(RUN,uuid.uuid4().hex,'close',{})
        owner.store.write=changed
        with self.assertRaises(NativeUIError):self.next(2)
        self.assertEqual(['chat.entry','chat.input'],[row[0] for row in self.widgets.calls])
        self.assertEqual('',self.widgets.draft);self.assertTrue(self.widgets.focus)

    def test_peer_intent_cas_does_not_publish_command_for_a_retired_original_ticket(self):
        self.through(7);factory=self.factories['peer']
        def create():
            owner=factory();write=owner.input.store.write
            def changed(value,previous):
                write(value,previous)
                from adapters.script_journey.history import unpack
                if unpack(value['intents']):
                    current=self.w.journal.runs.pop(RUN);current['retiredEpochMs']=self.h.native.epoch
                    self.w.journal.retired_phases[RUN]=current
            owner.input.store.write=changed;return owner
        self.factories['peer']=create
        with self.assertRaises(NativeUIError):self.next(8)
        self.assertEqual([],self.peer_commands);self.assertFalse((self.root/'peer'/COMMAND).exists())
        self.assertEqual('issued',self.store.read()['steps'][-1]['phase'])

    def test_lost_input_ack_and_lost_completed_parent_write_never_replay_warm_or_cold(self):
        self.through(6);self.widgets.lose_ack=True
        with self.assertRaises(NativeUIError):self.next(7)
        self.assertEqual(1,len(self.widgets.sent));original=self.store.path.read_bytes();calls=len(self.widgets.calls)
        with self.assertRaises(NativeUIError):self.owner.step()
        with self.assertRaises(NativeUIError):self.create().step()
        self.assertEqual(original,self.store.path.read_bytes());self.assertEqual(calls,len(self.widgets.calls))
        self.setUp();self.next(0);write=self.store.write
        def lost(value,previous):
            write(value,previous)
            if value['steps'][-1]['phase']=='completed':raise OSError('Original write landed; receipt lost')
        self.store.write=lost
        with self.assertRaises(NativeUIError):self.next(1)
        self.assertEqual('completed',self.store.read()['steps'][-1]['phase']);self.assertEqual(1,len(self.widgets.calls))
        with self.assertRaises(NativeUIError):self.owner.step()
        with self.assertRaises(NativeUIError):self.create().step()
        self.assertEqual(1,len(self.widgets.calls));self.assertEqual(2,len(self.mutations()))

    def test_ack_only_ui_effect_cannot_complete_parent_or_acquire_next_child(self):
        self.next(0);self.widgets.ignore_effect=True
        with self.assertRaises(NativeUIError):self.next(1)
        self.assertEqual('issued',self.store.read()['steps'][-1]['phase']);self.assertEqual(1,len(self.widgets.calls))
        self.assertEqual(['normal'],self.factory_calls)

    def test_skip_and_failed_parent_intent_prevent_any_cache_or_control_input(self):
        self.next(0);self.w.journal.activate(RUN,uuid.uuid4().hex,'send',{})
        with self.assertRaises(NativeUIError):self.owner.step()
        self.assertEqual([],self.widgets.calls);self.assertEqual([],self.mutations());self.assertEqual(0,self.cache_calls)
        self.setUp();self.next(0);write=self.store.write
        def failed(value,previous):
            if len(value['steps'])==2:raise OSError('Original write failed')
            return write(value,previous)
        self.store.write=failed
        with self.assertRaises(NativeUIError):self.next(1)
        self.assertEqual([],self.widgets.calls);self.assertEqual([],self.mutations());self.assertEqual(0,self.cache_calls)

    def test_cold_history_and_immutable_snapshot_corruption_never_issue_input(self):
        self.through(2);before=len(self.widgets.calls);queries=len(self.h.h.primary.commands)
        rebuilt=self.create();self.assertEqual(6,len(rebuilt.history()))
        self.assertEqual(queries,len(self.h.h.primary.commands));self.assertEqual(before,len(self.widgets.calls))
        child=self.owner.chunks.store(0);old=child.read();child.write({**old,'scopeSha256':'f'*64},old)
        with self.assertRaises(NativeUIError):self.owner.history()
        with self.assertRaises(NativeUIError):self.create()
        self.assertEqual(before,len(self.widgets.calls))

    def test_all_fixed_verbs_have_closed_routes_without_checkpoint_state(self):
        rows=recipe(RUN);self.assertEqual(26,len(rows));self.assertEqual(17,sum(route(row['verb'])=='normal' for row in rows))
        self.assertEqual(set(KINDS)|{'baseline'},set(route(row['verb']) for row in rows))
        self.assertEqual(['distant','background','mixer','mixer','no-replay'],[route(rows[index]['verb']) for index in (12,17,18,21,22)])


if __name__=='__main__':unittest.main()
