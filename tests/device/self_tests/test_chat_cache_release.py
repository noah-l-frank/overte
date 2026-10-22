"""Real ownership/phase/files/chunks; native/V8/IME and 26 input rows are seams.

This does not execute or qualify the preceding 25 target effects, product Agent,
network service, physical device, Qt object destruction or final archive.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from types import SimpleNamespace
import unittest

from adapters.chat_actor_files import ChatActorFiles,SOURCE,encode,node
from adapters.chat_peer_input import ChatPeerInput,COMMAND,RECEIPT
from adapters.chat_journey.cache_lifetime import ChatCacheLifetime
from adapters.chat_journey.cache_release import ChatCacheRelease
from adapters.chat_journey.compiled_samples import CompiledChatCacheAbsence
from adapters.chat_journey.peer_input_close import ChatPeerInputClose
from adapters.chat_journey.peer_retirement import ChatPeerRetirementFiles
from adapters.chat_journey.phase_fence import ChatPhaseFence
from adapters.chat_journey.script_source import ChatScriptSource
from adapters.native_chat_observation import ChatCaptureOwner,OwnedChatCapture,NativeChatObservation
from adapters.native_chat_profile import OwnedChatProfile
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from self_tests import test_chat_cleanup_admission as phase_seams
from self_tests.test_chat_actor_files import FileActor
from self_tests.test_chat_profile_owner import Boundary as ProfileBoundary
from self_tests.test_chat_script_source import CompiledBoundary
from self_tests.test_native_chat_observation import RUN


class CacheReleaseTests(unittest.TestCase):
    def setUp(self):
        self.phase=phase_seams.ChatCleanupAdmissionTests();self.phase.setUp();self.addCleanup(self.phase.doCleanups)
        self.h=self.phase.h.h;self.model=self.h.h;self.root=self.model.root;self.locks=self.h.roles[0].locks
        self.binding=self.h.roles[0].binding;self.peer_binding=self.h.roles[0].peer_binding
        self.epoch=lambda:self.h.native.epoch;self.now=lambda:self.h.native.host;self.sleep=self.h.sleep
        for boundary in (self.model.primary,self.model.peer):
            boundary.open_id='';boundary.retire_id='';original=boundary.mutate;send=boundary.send
            def mutate(value,boundary=boundary,original=original):
                original(value);value['source'].update(openedCommandId=boundary.open_id,retiredCommandId=boundary.retire_id)
            def owned(request,boundary=boundary,send=send):
                if request['operation']=='observe' and not boundary.open_id:boundary.open_id=request['commandId']
                if request['operation']=='retire' and not boundary.retire_id:boundary.retire_id=request['commandId']
                return send(request)
            boundary.mutate=mutate;boundary.send=owned
        self.actor_root=self.root/'native-actor';self.actor_root.mkdir(mode=0o700)
        path=self.actor_root/SOURCE;path.write_bytes(encode(dict(actorVersion=1,instance='e'*32,processId=456,
            configuredEpochMs=self.epoch()-100,scriptSha256='f'*64)));path.chmod(0o600)
        self.actor=FileActor(self.actor_root);self.actor.native=self.model.peer;self.addCleanup(self.actor.close_all)
        self.input_fd=-1;self.addCleanup(self.close_input);self.input_sequence=0
        def released(value):
            if self.input_fd>=0 and node(os.fstat(self.input_fd))==value:return False
            return self.actor.released(value)
        self.files=ChatActorFiles(self.actor_root,PrivateFeatureState(self.root/'peer'/'files.json'),self.peer_binding,
            'f'*64,lambda:True,released,clock_ms=self.epoch,monotonic=self.now,sleep=self.input_tick,require_original_fd=True)
        self.addCleanup(self.files.detach);self.fresh=None;self.addCleanup(lambda:self.fresh.detach() if self.fresh else None)
        self.input=ChatPeerInput(self.files,PrivateFeatureState(self.root/'peer'/'input.json'),RUN)
        self.caches=[]
        with self.phase.flow.session():
            for index,(boundary,binding,lock) in enumerate(zip((self.model.primary,self.model.peer),
                    (self.binding,self.peer_binding),self.locks)):
                reader=self.native_reader(index);owner=ChatCaptureOwner(PrivateFeatureState(lock.path.parent/'capture.json'),binding,reader.guard)
                owner.begin(RUN);owner.admit(reader.perform(RUN,'inspect'))
                cache=ChatCacheLifetime(OwnedChatCapture(reader,owner,RUN),PrivateFeatureState(lock.path.parent/'cache.json'),lock,monotonic=self.now)
                cache.activate();self.caches.append(cache)
            self.input.issue('release')
            self.actor.mutate=self.lifetime
            self.input_close=ChatPeerInputClose(self.input,self.native_reader(1),PrivateFeatureState(self.root/'peer'/'input-close.json'),
                self.locks[1],monotonic=self.now,sleep=self.sleep);self.input_close.run()
            self.fresh=ChatPeerRetirementFiles(self.files,self.input_close)
            owner=self.caches[1].capture.owner
            self.caches[1]=ChatCacheLifetime(OwnedChatCapture(self.native_reader(1,self.fresh),owner,RUN),
                self.caches[1].store,self.locks[1],monotonic=self.now)
            native=ProfileBoundary();native.hashes['cache']['ArmoredChat-Config']=self.model.view.source['storage']['configSha256']
            native.hashes['worker']['ArmoredChat-Config']=self.model.view.source['storage']['configSha256']
            send=native.send
            def profile_send(request):native.epoch=self.epoch();send(request)
            reader=native.reader();reader.send=profile_send;reader.clock_ms=self.epoch;reader.monotonic=self.now;reader.sleep=self.sleep
            self.profile=OwnedChatProfile(reader,PrivateFeatureState(self.root/'profile.json'),self.binding,RUN,self.locks[0])
            self.profile.perform('acquire');self.profile.perform('restore')
            self.phase.activate();self.phase.owner.admit();self.fence=ChatPhaseFence(self.phase.flow,cleanup=self.phase.owner)
            self.roles=tuple(self.sampler(role) for role in ('primary','actor'))
            self.store=PrivateFeatureState(self.root/'cache-release.json');self.owner=self.make()

    def close_input(self):
        if self.input_fd>=0:os.close(self.input_fd);self.input_fd=-1
    def input_tick(self,delay):
        self.sleep(delay);request=json.loads((self.actor_root/COMMAND).read_bytes());self.input_sequence+=1
        temporary=self.actor_root/'.input';descriptor=os.open(temporary,os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600)
        value=dict(actorFileVersion=1,commandNode=node((self.actor_root/COMMAND).stat()),resultNode=node(os.fstat(descriptor)),
            native=dict(peerInputVersion=3,commandId=request['commandId'],runId=RUN,operation=request['operation'],
                instance='7'*32,sequence=self.input_sequence,processId=456,capturedEpochMs=self.epoch(),
                avatarSha256=self.model.peer.value['source']['selfSha256'],avatarPosition=dict(x=2.,y=0.,z=2.),scriptPolls=1,releaseConsumed=True))
        os.write(descriptor,encode(value));os.fsync(descriptor);os.replace(temporary,self.actor_root/RECEIPT)
        self.close_input();self.input_fd=descriptor
    def lifetime(self,value):
        if not (self.actor_root/RECEIPT).exists():self.close_input()
        def present(name):
            path=self.actor_root/name;return dict(present=True,node=node(path.stat())) if path.exists() else dict(present=False,node={})
        value['inputLifetime']=dict(inputLifetimeVersion=1,commandId=value['native']['commandId'],runId=RUN,
            instance='7'*32,ownerRunId=RUN,sequence=1,scriptPolls=1,releaseConsumed=True,processId=456,capturedEpochMs=self.epoch(),
            command=present(COMMAND),receipt=present(RECEIPT),receiptHandle=dict(open=self.input_fd>=0,
                node=node(os.fstat(self.input_fd)) if self.input_fd>=0 else {}))
    def native_reader(self,index,files=None):
        boundary=(self.model.primary,self.model.peer)[index]
        if index==1:
            files=files or self.files
            def read():self.actor.tick();return files.read()
            reader=NativeChatObservation(files.send,read,self.epoch,lambda:True,456,monotonic=self.now,sleep=self.sleep)
            reader._chat_transport=files
        else:
            reader=boundary.reader();reader.clock_ms=self.epoch;reader.monotonic=self.now;reader.sleep=self.sleep
            reader._chat_transport=SimpleNamespace()
        return reader
    def sampler(self,role):
        code=CompiledBoundary();send=code.roots.send;full=code.full
        def root_send(request):code.roots.epoch=self.epoch();send(request);code.roots.value['processId']=123
        code.roots.send=root_send
        def script(value):full(value);value.update(processId=123,capturedEpochMs=self.epoch(),requestedEpochMs=self.epoch())
        code.script.mutate=script;roots,scripts=code.readers()
        for reader in (roots,scripts):reader.pid=123;reader.clock_ms=self.epoch;reader.monotonic=self.now;reader.sleep=self.sleep
        source=ChatScriptSource(RUN,role,self.binding,roots,scripts,PrivateFeatureState(self.root/(role+'-code.json')),
            self.locks[0],monotonic=self.now)
        view=self.model.view.reader(vr=True);native=self.model.native.reader()
        for reader in (view,native):reader.clock_ms=self.epoch;reader.monotonic=self.now;reader.sleep=self.sleep
        return CompiledChatCacheAbsence(RUN,role,self.binding,self.peer_binding,self.native_reader(0),self.native_reader(1),view,native,
            PrivateFeatureState(self.root/(role+'-final.json')),*self.locks,vr=True,script_source=source,monotonic=self.now)
    def make(self,*,defer_ipc=False):return ChatCacheRelease(tuple(self.caches),self.roles,self.profile,self.input_close,self.fresh,self.store,
        self.fence,defer_ipc=defer_ipc,monotonic=self.now,sleep=self.sleep)

    def test_deferred_original_retirements_keep_actual_peer_source_and_ipc_for_postrestart_queries(self):
        with self.phase.flow.session():
            self.owner=self.make(defer_ipc=True);result=self.owner.run(20000)
            self.assertEqual('caches-quiet',result['phase']);self.assertEqual(2,result['chatCacheReleaseVersion'])
            self.assertTrue(result['ipcDeferred']);self.assertNotIn('ipc',result)
            before=deepcopy(self.files.store.read());self.assertFalse(before['closing']);self.assertFalse(before['removed'])
            self.assertGreaterEqual(self.actor.fd,0);self.assertFalse(self.fresh.fd_owner.closed)
            request=dict(schemaVersion=1,commandId='f'*32,action='feature-chat-observe',operation='inspect',runId=RUN)
            self.fresh.send(request);self.actor.tick();packet=json.loads(self.fresh.read())
            self.assertTrue(packet['source']['retired']);self.assertFalse(packet['source']['scopePresent'])
            self.assertEqual(self.caches[1].base['retirement']['request']['commandId'],packet['source']['retiredCommandId'])
            self.assertFalse(self.files.released(node(os.fstat(self.actor.fd))));self.owner.authority()
        self.assertEqual(['observe','retire'],self.mutations(0));self.assertEqual(['observe','retire'],self.mutations(1))
        self.assertIsNotNone(self.input_close.store.read());self.assertIsNotNone(self.profile.store.read())

    def mutations(self,index):
        return [row['operation'] for row in (self.model.primary,self.model.peer)[index].commands if row['operation']!='inspect']

    def test_phase_change_after_parent_retirement_intent_prevents_native_mutation_and_retains_original(self):
        write=self.store.write
        def changed(value,previous):
            write(value,previous)
            if value['phase']=='primary-retirement-issued':self.phase.activate()
        self.store.write=changed
        with self.phase.flow.session():
            with self.assertRaises(NativeUIError):self.owner.run(20000)
            original=deepcopy(self.store.read())
            with self.assertRaises(NativeUIError):self.owner.run(20000)
            self.assertEqual(original,self.store.read())
        self.assertEqual(['observe'],self.mutations(0));self.assertEqual(['observe'],self.mutations(1))
        self.assertTrue((self.actor_root/'chat-actor-command.v1.json').exists())
        self.assertFalse(self.files.store.read()['closing'])

    def test_lost_original_parent_intent_never_overwrites_or_retires_peer_after_first_primary_release(self):
        write=self.store.write
        def lost(value,previous):
            write(value,previous)
            if value['phase']=='peer-retirement-issued':raise OSError('Original parent CAS landed; receipt lost')
        self.store.write=lost
        with self.phase.flow.session():
            with self.assertRaises(NativeUIError):self.owner.run(20000)
            original=deepcopy(self.store.read())
            with self.assertRaises(NativeUIError):self.owner.run(20000)
            self.assertEqual(original,self.store.read())
        self.assertEqual(['observe','retire'],self.mutations(0));self.assertEqual(['observe'],self.mutations(1))
        self.assertFalse(self.files.store.read()['closing']);self.assertIsNotNone(self.input_close.store.read())

    def test_frozen_host_cannot_hide_original_native_quiet_gap_or_allow_ipc_removal(self):
        self.owner.sleep=lambda delay:setattr(self.h.native,'epoch',self.h.native.epoch+600)
        with self.phase.flow.session(),self.assertRaises(NativeUIError):self.owner.run(20000)
        self.assertEqual(2,len(self.owner.frames));self.assertFalse(self.files.store.read()['closing'])
        self.assertTrue((self.actor_root/'chat-actor-command.v1.json').exists())
        self.assertEqual(['observe','retire'],self.mutations(0));self.assertEqual(['observe','retire'],self.mutations(1))
        self.assertIsNotNone(self.store.read());self.assertTrue(self.owner.failed)

    def test_late_keyboard_input_after_first_final_absence_refuses_ipc_close(self):
        def late(delay):
            self.sleep(delay);self.model.view.source['keyboard']['keys'][0]['pressed']=True
        self.owner.sleep=late
        with self.phase.flow.session(),self.assertRaises(NativeUIError):self.owner.run(20000)
        self.assertEqual(1,len(self.owner.frames));self.assertFalse(self.files.store.read()['closing'])
        self.assertEqual('reading',self.store.read()['phase']);self.assertTrue(self.owner.failed)

    def test_native_jump_after_final_ipc_cas_cannot_return_fresh_success_with_frozen_host(self):
        original=self.owner.authority;jumped=[False]
        def late():
            original()
            if self.owner.previous is not None and self.owner.previous['phase']=='ipc-closed' and not jumped[0]:
                self.h.native.epoch+=2000;jumped[0]=True
        self.owner.authority=late
        with self.phase.flow.session(),self.assertRaises(NativeUIError):self.owner.run(20000)
        self.assertTrue(jumped[0]);self.assertTrue(self.files.store.read()['removed']);self.assertTrue(self.fresh.fd_owner.closed)
        self.assertEqual('ipc-closed',self.store.read()['phase']);self.assertTrue(self.owner.failed)
        self.assertTrue(all(cache.store.read() is not None and cache.capture.owner.store.read() is not None for cache in self.caches))

    def test_original_two_retirements_independent_compiled_absence_quiet_and_retained_ipc_close(self):
        with self.phase.flow.session():result=self.owner.run(20000)
        self.assertEqual('ipc-closed',result['phase']);self.assertTrue(self.fresh.fd_owner.closed)
        self.assertTrue(self.files.store.read()['removed']);self.assertIsNotNone(self.profile.store.read())
        self.assertTrue(all(cache.base['phase']=='retired' and not cache.capture.owner.owned()['active'] for cache in self.caches))
        self.assertGreaterEqual(len(self.owner.frames),2)
        for boundary in (self.model.primary,self.model.peer):
            self.assertEqual(['observe','retire'],[row['operation'] for row in boundary.commands if row['operation']!='inspect'])
        self.assertFalse((self.actor_root/COMMAND).exists());self.assertFalse((self.actor_root/RECEIPT).exists())
        self.assertGreaterEqual(self.files.fd,0);self.files._check_source()
        with self.phase.flow.session(),self.assertRaises(NativeUIError):self.owner.run(20000)


# The existing 120-second per-selector budget is unchanged. Explicit groups
# remain lossless: a new/renamed test refuses selection until it is assigned.
_GROUPS=dict(
    positive=('test_original_two_retirements_independent_compiled_absence_quiet_and_retained_ipc_close',),
    deferred=('test_deferred_original_retirements_keep_actual_peer_source_and_ipc_for_postrestart_queries',),
    admission=('test_phase_change_after_parent_retirement_intent_prevents_native_mutation_and_retains_original',
        'test_lost_original_parent_intent_never_overwrites_or_retires_peer_after_first_primary_release'),
    quiet=('test_frozen_host_cannot_hide_original_native_quiet_gap_or_allow_ipc_removal',
        'test_late_keyboard_input_after_first_final_absence_refuses_ipc_close'),
    final_clock=('test_native_jump_after_final_ipc_cas_cannot_return_fresh_success_with_frozen_host',))


def _selection(group):
    names=[name for selection in _GROUPS.values() for name in selection]
    expected=unittest.defaultTestLoader.getTestCaseNames(CacheReleaseTests)
    if len(set(names))!=len(names) or sorted(names)!=expected:
        raise ValueError('Chat cache-release selectors must include every original case exactly once')
    return unittest.TestSuite(CacheReleaseTests(name) for name in _GROUPS[group])


def cache_release_positive_tests():return _selection('positive')
def cache_release_deferred_tests():return _selection('deferred')
def cache_release_admission_tests():return _selection('admission')
def cache_release_quiet_tests():return _selection('quiet')
def cache_release_final_clock_tests():return _selection('final_clock')


if __name__=='__main__':unittest.main()
