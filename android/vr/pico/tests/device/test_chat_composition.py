"""Actual Pico factory/Linux peer identity with explicit SDK/native SOURCE seams.

Only owned stdin workers run. No product Agent, service, device or OpenXR run.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
import select
from unittest.mock import patch
import unittest

import test_normal_scripts as pico_seams
from self_tests import test_chat_owned_peer as peer_seams
from adapters.chat_actor_files import SOURCE
from adapters.feature_fixture_access import AdapterFixtureClient
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.chat_composition import peer_directory
from feature_journeys.phase_fixture import PhaseFixtureReader

RUN='d'*32

# Original Python protocol seam, actual native-process file descriptors/identity.
WORKER=peer_seams.WORKER.replace("print('ready',flush=True);sys.stdin.readline();os.close(fd)",r"""
from adapters.chat_actor_files import encode,node
from self_tests.test_chat_cache_lifetime import NativeBoundary
from adapters.native_chat_observation import identity
native=NativeBoundary();result_fd=-1;last=None
print('ready',flush=True)
for line in sys.stdin:
    if line.strip()=='close':break
    assert line.strip()=='tick'
    path=root/'chat-actor-command.v1.json'
    if path.exists():
        request=json.loads(path.read_bytes())
        if request['commandId']!=last:
            last=request['commandId'];native.epoch=int(time.time()*1000);native.send(request)
            native.value.update(instance=value['instance'],processId=os.getpid())
            native.value['source']['selfSha256']=identity(request['runId'],'22222222-2222-4222-8222-222222222222')
            temporary=root/'.original-result';new=os.open(temporary,os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600)
            envelope=dict(actorFileVersion=1,commandNode=node(path.stat()),resultNode=node(os.fstat(new)),native=native.value)
            os.write(new,encode(envelope));os.fsync(new);os.replace(temporary,root/'feature-chat-observation.json')
            if result_fd>=0:os.close(result_fd)
            result_fd=new
    print('tick',flush=True)
if result_fd>=0:os.close(result_fd)
os.close(fd)
""")


def ready():
    base='http://127.0.0.1:48308/v1/'
    return dict(schemaVersion=1,domainUrl='hifi://127.0.0.1:48302/parity',domainHost='127.0.0.1',
        domainId='33333333-3333-4333-8333-333333333333',requiredMarkers=[],expectedEntityCount=1,
        bootstrapScriptUrl='http://127.0.0.1:48309/domain.js',peerScriptUrl='http://127.0.0.1:48309/peer.js',
        peerDisplayName='owned-component-peer',controlUrl=base+'domain-state',controlToken='test_only_'+'a'*48,
        collaborationEditUrl=base+'collaboration-edit',collaborationStateUrl=base+'collaboration-state',
        messagesMixerControlUrl=base+'messages-mixer-state')


class PicoChatCompositionTests(unittest.TestCase):
    def setUp(self):
        self.pico=pico_seams.PicoNormalScriptsTests();self.pico.setUp();self.addCleanup(self.pico.doCleanups)
        self.instance,self.native=self.pico.instance,self.pico.native
        self.peer=peer_seams.OwnedPeerTests()
        with patch.object(peer_seams,'WORKER',WORKER):self.peer.setUp()
        self.addCleanup(self.peer.doCleanups)
        self.ready=PrivateFeatureState(self.peer.root/'ready.json');self.ready.write(ready(),None)
        self.source=PhaseFixtureReader(AdapterFixtureClient('http://127.0.0.1:48300/feature-fixture/v1','a'*48),RUN,'chat')
        self.owners=[];self.addCleanup(lambda:[owner.detach() for owner in self.owners])
    def compose(self):
        owner=self.instance._chat_composition(self.native.target,self.source,self.peer.config,self.ready)
        self.owners.append(owner);return owner

    def test_owned_mixer_accepts_same_original_controller_permissions_extension_and_pins_its_stamp(self):
        from adapters.chat_journey.owned_mixer import OwnedChatMixer
        owner=self.compose();value=ready();value['createPermissionsControlUrl']='http://127.0.0.1:48308/v1/create-permissions'
        store=PrivateFeatureState(self.peer.root/'permissions-ready.json');store.write(value,None)
        mixer=OwnedChatMixer(owner.peer,store);self.assertTrue(mixer.guard())
        store.write(value,value)
        with self.assertRaises(NativeUIError):mixer.guard()

    def test_owned_mixer_refuses_permissions_extension_from_foreign_controller_or_path(self):
        from adapters.chat_journey.owned_mixer import OwnedChatMixer
        owner=self.compose()
        for index,url in enumerate(('http://127.0.0.1:48310/v1/create-permissions',
            'http://127.0.0.1:48308/v1/foreign-permissions')):
            value=ready();value['createPermissionsControlUrl']=url
            store=PrivateFeatureState(self.peer.root/f'foreign-permissions-ready-{index}.json');store.write(value,None)
            with self.subTest(url=url),self.assertRaises(NativeUIError):OwnedChatMixer(owner.peer,store)

    def prepare_sources(self,owner):
        profile=pico_seams.ProfileBoundary()
        from self_tests.test_chat_cache_lifetime import NativeBoundary
        chat=NativeBoundary()
        original_write=self.native.write_debug_app_file;original_read=self.native.read_debug_app_file
        def captured(value):
            epoch=self.native.epoch_milliseconds(self.native.target)
            value['capturedEpochMs']=value['settings']['capturedEpochMs']=value['view']['capturedEpochMs']=epoch
            value['runId']=RUN
        profile.mutate=captured
        def write(target,package,path,raw):
            request=json.loads(raw)
            if request['action']=='feature-chat-profile':profile.send(request)
            elif request['action']=='feature-chat-observe':
                chat.epoch=self.native.epoch_milliseconds(target);chat.send(request)
            else:return original_write(target,package,path,raw)
        def read(target,package,path,**kwargs):
            if path.endswith('/feature-chat-profile.json'):return profile.raw
            if path.endswith('/feature-chat-observation.json'):return chat.read()
            return original_read(target,package,path,**kwargs)
        actual_read=owner.peer.files.read
        def peer_read():
            self.peer.worker.stdin.write('tick\n');self.peer.worker.stdin.flush()
            self.assertTrue(select.select([self.peer.worker.stdout],[],[],2)[0])
            self.assertEqual('tick',self.peer.worker.stdout.readline().strip());return actual_read()
        for boundary in (patch.object(self.native,'write_debug_app_file',side_effect=write),
                         patch.object(self.native,'read_debug_app_file',side_effect=read),
                         patch.object(owner.peer.files,'read',side_effect=peer_read)):
            boundary.start();self.addCleanup(boundary.stop)
        self.prepare_chat=chat
        return profile,chat

    def test_actual_prepare_owns_profile_and_both_absent_caches_then_builds_all_exact_parent_locks(self):
        owner=self.compose();profile,chat=self.prepare_sources(owner);dispatcher=owner.prepare()
        self.assertEqual('prepared',owner.previous['phase']);self.assertIs(dispatcher,owner.dispatcher)
        self.assertEqual(['acquire'],[request['operation'] for request in profile.requests])
        self.assertEqual(['inspect'],[request['operation'] for request in chat.commands])
        self.assertEqual('inspect',owner.peer.files.store.read()['request']['operation'])
        self.assertEqual({},dispatcher.children);self.assertIsNone(dispatcher.caches)
        for role in owner.roles+owner.initial:
            self.assertIs(role.locks[0],owner.lock);self.assertIs(role.locks[1],owner.peer.lock)
            self.assertEqual(owner.binding,role.binding);self.assertEqual(owner.peer.binding,role.peer_binding)
        for index in range(2):
            self.assertIs(owner.roles[index].script_source,owner.code_sources[index])
            self.assertIs(owner.initial[index].script_source,owner.code_sources[index])
            self.assertIs(owner.code_sources[index].lock,owner.lock)
        self.assertEqual(5,owner.previous['picoChatCompositionVersion'])
        self.assertEqual([],self.native.inputs)
        with self.assertRaises(NativeUIError):owner.prepare()
        self.assertEqual(['acquire'],[request['operation'] for request in profile.requests])

    def test_actual_parent_builds_all_six_lazy_children_and_both_cache_owners_without_input(self):
        from adapters.chat_journey.dispatcher import KINDS
        owner=self.compose();self.prepare_sources(owner);owner.prepare()
        with owner.held():
            for kind,expected in KINDS.items():
                child=owner.dispatcher.child(kind);self.assertIs(type(child),expected)
                self.assertIs(child.phase_fence,owner.dispatcher.fence)
            primary,peer=owner.caches()
            self.assertIs(primary.lock,owner.lock);self.assertIs(peer.lock,owner.peer.lock)
            self.assertEqual(owner.binding,primary.capture.owner.binding)
            self.assertEqual(owner.peer.binding,peer.capture.owner.binding)
            self.assertEqual('ready',primary.base['phase']);self.assertEqual('ready',peer.base['phase'])
            normal=owner.dispatcher.children['normal'];background=owner.dispatcher.children['background']
            native=normal.ui.io.original.navigation.io
            self.assertIs(native._before_send.__self__,owner.dispatcher.fence)
            self.assertIs(native._controller_intent.__self__,owner.dispatcher.fence)
            self.assertIs(native._controller_publish.__self__,owner.dispatcher.fence)
            self.assertIs(background.source.source_lock,owner.lock)
            self.assertIs(owner.dispatcher.children['distant'].sender,owner.dispatcher.children['peer'])
            self.assertIs(owner.dispatcher.children['peer'].input.files,owner.peer.files)
        self.assertEqual([],self.native.inputs)
        self.assertEqual(['inspect'],[request['operation'] for request in self.prepare_chat.commands])
        self.assertFalse((self.peer.actor/'chat-peer-input.v1.json').exists())

    def test_independent_witness_factory_uses_own_credential_readers_and_same_original_os_lock_paths(self):
        from feature_journeys.witness import Client
        owner=self.compose();self.prepare_sources(owner);owner.prepare()
        source=PhaseFixtureReader(Client(self.source.client.url,'w'*48),RUN,'chat')
        witness=self.instance._chat_witness_composition(self.native.target,source,self.peer.config)
        self.addCleanup(witness.detach)
        self.assertIs(source,witness.publisher.source);self.assertIsNot(source.client,self.source.client)
        self.assertIsNot(owner.peer,witness.peer);self.assertEqual(owner.peer.binding,witness.peer.binding)
        self.assertIsNot(owner.lock,witness.lock);self.assertEqual(owner.lock.path,witness.lock.path)
        self.assertIsNot(owner.peer.lock,witness.peer.lock);self.assertEqual(owner.peer.lock.path,witness.peer.lock.path)
        self.assertIs(witness.publisher.samples.locks[0],witness.lock)
        self.assertIs(witness.publisher.samples.locks[1],witness.peer.lock)
        self.assertIsNot(witness.publisher.samples.peer,owner.roles[1].peer)
        self.assertIsNot(witness.publisher.samples.store,owner.roles[1].store)
        code=witness.publisher.samples.script_source
        self.assertIs(code,witness.publisher.initial_samples.script_source);self.assertIs(code.lock,witness.lock)
        self.assertIsNot(code,owner.code_sources[1]);self.assertIsNot(code.roots,owner.code_sources[1].roots)
        self.assertIsNot(code.scripts,owner.code_sources[1].scripts)
        self.assertNotEqual(code.store.path,owner.code_sources[1].store.path)
        self.assertEqual([],witness.publisher.samples.frames);self.assertEqual([],self.native.inputs)

    def test_legacy_parent_manifest_is_retained_but_cannot_qualify_compiled_source_witness(self):
        from feature_journeys.witness import Client
        owner=self.compose();self.prepare_sources(owner);owner.prepare()
        original=owner.store.read()
        source=PhaseFixtureReader(Client(self.source.client.url,'w'*48),RUN,'chat')
        for version in (1,2):
            legacy=dict(original,picoChatCompositionVersion=version);owner.store.write(legacy,owner.store.read())
            with self.subTest(version=version),self.assertRaises(ValueError):self.instance._chat_witness_composition(self.native.target,source,self.peer.config)
            self.assertEqual(legacy,owner.store.read());self.assertEqual([],self.native.inputs)

    def test_premature_parent_cleanup_never_admits_phase_or_creates_peer_release_input(self):
        owner=self.compose();self.prepare_sources(owner);owner.prepare()
        with self.assertRaises(NativeUIError):owner.admit_cleanup(self.native.epoch_milliseconds(self.native.target))
        self.assertIsNone(self.instance._chat_cleanup_admission_store(self.native.target).read())
        self.assertEqual('prepared',owner.store.read()['phase']);self.assertEqual([],self.native.inputs)
        self.assertIs(owner.profile.reader.send,owner.profile.reader._chat_transport.send)
        self.assertFalse((self.peer.actor/'chat-peer-input.v1.json').exists())

    def test_original_cleanup_admission_without_parent_root_still_prevents_generic_cleanup_success(self):
        store=self.instance._chat_cleanup_admission_store(self.native.target)
        original={'original':'unresolved-final-cleanup-phase'};store.write(original,None)
        with self.assertRaises(ValueError):self.pico.cleanup_instance().cleanup(self.native.target)
        self.assertEqual(original,store.read());self.assertFalse(self.native.running)

    def test_cache_release_orphan_without_parent_root_still_refuses_generic_cleanup(self):
        store=self.instance._chat_cache_release_store(self.native.target)
        orphan=PrivateFeatureState(store.path.with_name(store.path.name+'.frame-000.json'))
        original={'original':'unresolved-cache-release-frame'};orphan.write(original,None)
        with self.assertRaises(ValueError):self.pico.cleanup_instance().cleanup(self.native.target)
        self.assertEqual(original,orphan.read());self.assertFalse(self.native.running);self.assertIsNone(store.read())

    def test_parent_cannot_retire_cache_or_construct_final_sources_before_original_erase_restore(self):
        owner=self.compose();before=owner.store.read()
        with self.assertRaises(NativeUIError):owner.close_caches_and_ipc(20000)
        self.assertEqual(before,owner.store.read());self.assertIsNone(owner.cache_release)
        self.assertIsNone(owner.peer.retirement_files);self.assertEqual([],self.native.inputs)

    def test_lost_parent_profile_receipt_keeps_original_native_acquire_without_replay(self):
        owner=self.compose();profile,chat=self.prepare_sources(owner);original=owner.store.write
        def lost(value,previous):
            if value['phase']=='profile-acquired':raise OSError('Original profile acquired, parent receipt lost')
            return original(value,previous)
        owner.store.write=lost
        with self.assertRaises(NativeUIError):owner.prepare()
        self.assertEqual('profile-acquire-issued',owner.store.read()['phase'])
        with self.assertRaises(NativeUIError):owner.prepare()
        self.assertEqual(['acquire'],[request['operation'] for request in profile.requests])
        self.assertEqual([],chat.commands);self.assertEqual([],self.native.inputs)

    def test_actual_pico_parent_pins_independent_peer_origin_and_owns_separate_source_locks(self):
        owner=self.compose();self.assertEqual('bound',owner.previous['phase'])
        self.assertEqual('c'*40,owner.peer.binding['sourceRevision'])
        self.assertEqual('native-configured-metadata-only',owner.previous['peerOriginBasis'])
        self.assertNotEqual(owner.binding['sourceRevision'],owner.peer.binding['sourceRevision'])
        self.assertNotEqual(owner.lock.path,owner.peer.lock.path);self.assertEqual(owner.peer.files.store.path.parent,owner.peer.lock.path.parent)
        self.assertEqual({SOURCE},set(path.name for path in self.peer.actor.iterdir()))
        self.assertIsNone(owner.peer.files.store.read()['request']);self.assertIsNone(owner.profile)
        self.assertFalse(owner.mixer.controls[0].readonly);self.assertTrue(owner.mixer.controls[1].readonly)
        self.assertIsNot(owner.mixer.controls[0],owner.mixer.controls[1])
        self.assertIs(owner.mixer.controls[0].guard,owner.mixer.controls[1].guard)
        self.assertEqual([],self.native.inputs)
        self.assertFalse(any(value.startswith('feature.chat.') for value in self.instance.capabilities(self.native.target)))
        with self.assertRaises(ValueError):self.compose()
        self.assertEqual('bound',self.instance._chat_composition_store(self.native.target).read()['phase'])

    def test_actual_control_parser_requires_original_ready_domain_on_first_independent_get(self):
        from self_tests.test_chat_mixer_owner import Controller,Response
        owner=self.compose();first,second=owner.mixer.controls
        boundary=Controller(first.clock_ms);boundary.value['domainId']=self.ready.read()['domainId']
        class Opener:
            def open(inner,request,timeout):return Response(boundary.open(request,timeout).value,first.url)
        first._opener=second._opener=Opener()
        self.assertEqual(self.ready.read()['domainId'],first.state()['domainId'])
        boundary.value['domainId']='11111111-2222-4333-8444-555555555555'
        with self.assertRaises(NativeUIError):second.state()
        self.assertIsNone(second.previous);self.assertEqual([],boundary.posts)
        self.assertEqual([],self.native.inputs);self.assertIsNone(owner.peer.files.store.read()['request'])

    def test_existing_fixture_ready_file_may_use_its_separate_original_private_directory(self):
        directory=self.peer.root/'separate-ready-output';directory.mkdir(mode=0o700)
        self.ready=PrivateFeatureState(directory/'ready.json');self.ready.write(ready(),None)
        owner=self.compose();self.assertTrue(owner.mixer.guard())
        self.assertNotEqual(owner.mixer.store.path.parent,owner.peer.config_store.path.parent)
        self.assertIsNone(owner.peer.files.store.read()['request']);self.assertEqual([],self.native.inputs)

    def test_original_ready_replacement_and_changed_primary_candidate_are_refused_before_inputs(self):
        owner=self.compose();path=self.ready.path;other=path.with_name('replacement.json')
        other.write_bytes(path.read_bytes());other.chmod(0o600);os.replace(other,path)
        with self.assertRaises(NativeUIError):owner.mixer.guard()
        self.assertIsNone(owner.peer.files.store.read()['request']);self.assertEqual([],self.native.inputs)
        self.native.digest='f'*64
        with self.assertRaises((ValueError,RuntimeError)):owner.guard()

    def test_missing_parent_root_does_not_hide_original_peer_state_or_source_chunk_orphans(self):
        owner=self.compose();self.instance._chat_composition_store(self.native.target).path.unlink()
        self.assertTrue(self.instance._chat_peer_state_retained(self.native.target))
        directory=peer_directory(self.instance,self.native.target)
        owner.peer.files.store.path.unlink()
        chunk=PrivateFeatureState(directory/'chat-peer-input-close.json.frame-000.json');chunk.write({'original':'retained'},None)
        self.assertTrue(self.instance._chat_peer_state_retained(self.native.target))
        self.assertTrue(chunk.path.exists());self.assertEqual([],self.native.inputs)
        with self.assertRaises(ValueError):self.compose()
        self.assertTrue(chunk.path.exists())

    def test_adapter_credential_cannot_attach_independent_witness_and_bad_ready_keeps_admission(self):
        with self.assertRaises(ValueError):self.instance._chat_witness_composition(self.native.target,self.source,self.peer.config)
        changed=ready();changed['controlUrl']='http://127.0.0.1:48310/v1/domain-state'
        self.ready.write(changed,self.ready.read())
        with self.assertRaises(ValueError):self.compose()
        original=self.instance._chat_composition_store(self.native.target).read()
        self.assertEqual('admitted',original['phase']);self.assertEqual([],self.native.inputs)
        self.assertEqual({SOURCE},set(path.name for path in self.peer.actor.iterdir()))


if __name__=='__main__':unittest.main()
