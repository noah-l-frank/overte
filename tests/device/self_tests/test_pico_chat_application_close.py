"""Real host owners/phase/IPC/OFD/session, explicit native/SDK/V8 seams.

No application, Assignment Client, device, network or Qt destruction is run.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.chat_journey.compiled_samples import CompiledChatCacheAbsence
from adapters.chat_journey.script_source import ChatScriptSource
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.chat_application_close import PicoChatApplicationClose
from adapters.pico4.chat_restart_io import PicoChatRestartIO
from self_tests import test_chat_journey_samples as initial_seams
from self_tests import test_chat_cache_release as cache_seams
from self_tests.test_chat_script_source import CompiledBoundary
from self_tests.test_native_chat_observation import RUN
from self_tests.test_pico_chat_restart_io import RestartBoundary


class ApplicationCloseTests(unittest.TestCase):
    def setUp(self):
        self.h=cache_seams.CacheReleaseTests()
        with patch.object(initial_seams,'BINDING',initial_seams.BINDING|dict(processIdentity='123:456')):self.h.setUp()
        self.addCleanup(self.h.doCleanups);self.root=self.h.root
        self.os=RestartBoundary(self.root);self.os.pico_configuration=('explicit-layer',self.root)
        self.os.session.state_path.unlink();self.os.session.begin('123:456')
        self.io=PicoChatRestartIO(self.os,self.os.target,self.h.binding,monotonic=self.h.now,sleep=self.h.sleep)
        self.addCleanup(self.io.close_host)
        original_send=self.os.write_control_command
        def send(target,identity,operation,command):
            self.os.epoch=self.h.epoch();original_send(target,identity,operation,command)
        self.os.write_control_command=send
        self.os.epoch_milliseconds=lambda _target:self.h.epoch()
        self.os.presence.epoch_ms=self.h.epoch
        self.os.presence.edit=lambda value:value.update(instance='f'*32)
        native=self.os.native.mutate
        def new_native(value):
            native(value);value['instance']='f'*32
        self.os.native.mutate=new_native
        self.os.current.hashes=deepcopy(self.h.owner.profile_original['original'])
        def current(value):
            value.update(processId=789,instance='9'*32)
            value['settings'].update(instance='8'*32,writerInstance='7'*32)
            value['view'].update(instance='6'*32)
        self.os.current.edit=current
        patcher=patch('adapters.android_process_query.subprocess.run',side_effect=self.os.ps);patcher.start();self.addCleanup(patcher.stop)
        self.parent=PrivateFeatureState(self.root/'parent.json')
        self.parent_value=dict(phase='caches-retired',binding=self.h.binding)
        self.parent.write(self.parent_value,None)
        self.store=PrivateFeatureState(self.root/'app-close.json');self.inputs_store=PrivateFeatureState(self.root/'restart-inputs.json')
        self.roles=None;self.new_mutate=None

    def make(self):
        return PicoChatApplicationClose(self.h.owner,self.io,self.parent,self.parent_value,self.store,self.inputs_store,self.successor,
            monotonic=self.h.now,sleep=self.h.sleep)

    def successor(self,identity):
        self.assertEqual('789:999',identity);self.os.session.require_process_identity(identity)
        self.h.model.primary.retired=False;self.h.model.primary.open_id=self.h.model.primary.retire_id=''
        primary_old=self.h.model.primary.mutate
        def primary(value):
            primary_old(value);value.update(processId=789,instance='5'*32)
            value['source']['session'].update(instance='4'*32,connectionBirth='6'*32)
            if self.new_mutate:self.new_mutate(value)
        self.h.model.primary.mutate=primary
        view_old=self.h.model.view.mutate
        def view(value):
            view_old(value);value.update(processId=789,instance='6'*32)
        self.h.model.view.mutate=view
        binding=self.h.binding|dict(processIdentity=identity,sessionId='new-real-bridge')
        roles=[]
        for role in ('primary','actor'):
            code=CompiledBoundary();code.roots.instance='f'*32;root_send=code.roots.send;full=code.full
            def roots_send(request,code=code,send=root_send):
                code.roots.epoch=self.h.epoch();send(request);code.roots.value['processId']=789
            code.roots.send=roots_send
            def scripts(value,full=full):full(value);value.update(processId=789,capturedEpochMs=self.h.epoch(),requestedEpochMs=self.h.epoch())
            code.script.mutate=scripts;roots,scripts=code.readers()
            for reader in (roots,scripts):reader.pid=789;reader.clock_ms=self.h.epoch;reader.monotonic=self.h.now;reader.sleep=self.h.sleep
            source=ChatScriptSource(RUN,role,binding,roots,scripts,PrivateFeatureState(self.root/('post-'+role+'-code.json')),
                self.h.locks[0],monotonic=self.h.now)
            primary=self.h.native_reader(0);primary.pid=789;view=self.h.model.view.reader(vr=True);view.pid=789
            from adapters.native_feature_observation import NativeFeatureObservation
            native=NativeFeatureObservation(self.os.native.send,self.os.native.original,self.h.epoch,lambda:True,789,
                monotonic=self.h.now,sleep=self.h.sleep)
            send=native.send
            def native_send(request,send=send):self.os.epoch=self.h.epoch();send(request)
            native.send=native_send
            for reader in (view,native):reader.clock_ms=self.h.epoch;reader.monotonic=self.h.now;reader.sleep=self.h.sleep
            roles.append(CompiledChatCacheAbsence(RUN,role,binding,self.h.peer_binding,primary,self.retirement_peer_reader(),view,native,
                PrivateFeatureState(self.root/('post-'+role+'.json')),*self.h.locks,vr=True,script_source=source,monotonic=self.h.now))
        self.roles=tuple(roles);return binding,self.roles

    def retirement_peer_reader(self):
        from adapters.chat_journey.owned_peer import OwnedChatPeer
        if not hasattr(self,'peer_owner'):
            # Only process/source identity is a producer seam. The original
            # restricted files/input-close owners and new method actually run.
            peer=OwnedChatPeer.__new__(OwnedChatPeer);peer.guard=lambda:True
            peer.lock=self.h.locks[1];peer.files=self.h.files;peer.retirement_files=self.h.fresh
            peer.process_guard=self.h.fresh.guard
            peer.process=SimpleNamespace(pid=456,released=self.h.fresh.released)
            peer.clock_ms=self.h.epoch;peer.monotonic=self.h.now;peer.sleep=self.h.sleep
            read=self.h.fresh.read
            def original():self.h.actor.tick();return read()
            self.h.fresh.read=original;self.peer_owner=peer
        return self.peer_owner.retirement_reader()

    def prepare(self):
        self.h.owner=self.h.make(defer_ipc=True);self.h.owner.run(20000);self.owner=self.make()
    def shells(self):return [row for row in self.os.trace if type(row) is tuple and row[0]=='shell']

    def test_original_restart_birth_profile_new_roles_both_quiet_windows_and_kernel_ipc_release(self):
        with self.h.phase.flow.session():
            self.prepare();old=[role.store.path.read_bytes() for role in self.h.owner.roles]
            result=self.owner.run(20000)
            self.assertEqual('released',result['phase']);self.assertEqual(2,len(self.shells()))
            self.assertEqual('789:999',self.os.session._load()['processIdentity'])
            self.assertEqual(old,[role.store.path.read_bytes() for role in self.h.owner.roles])
            self.assertEqual('observed',self.owner.inputs.read()['phase']);self.assertEqual('ESRCH',self.os.presence.value['errorSymbol'])
            self.assertTrue(self.h.files.store.read()['removed']);self.assertEqual(-1,self.h.actor.fd)
            self.assertTrue(all(len(role.frames)>=31 for role in self.roles));self.assertTrue(self.h.fresh.fd_owner.closed)
            rows=self.owner.chunks.load(result['chunks']);self.assertGreaterEqual(sum(row['kind']=='ipc-quiet' for row in rows),31)
            self.assertTrue(self.parent.path.exists());self.assertTrue(self.h.profile.store.path.exists())
            self.archive_complete()
            self.assertIsNone(self.parent.read());self.assertIsNone(self.h.profile.store.read())
            before=self.store.read()
            with self.assertRaises(NativeUIError):self.owner.run(20000)
            self.assertEqual(before,self.store.read());self.assertEqual(2,len(self.shells()))


    def test_changed_physical_profile_refuses_cursor_transfer_and_cannot_replay_restart(self):
        with self.h.phase.flow.session():
            self.prepare();original=self.os.session.state_path.read_bytes()
            self.os.current.hashes['physical']['ArmoredChat-Config']['sha256']='0'*64
            with self.assertRaises(NativeUIError):self.owner.run(20000)
            self.assertEqual(original,self.os.session.state_path.read_bytes());self.assertEqual(2,len(self.shells()))
            self.assertIsNone(self.roles);self.assertEqual('launch-issued',self.owner.inputs.read()['phase'])
            before=self.store.read()
            with self.assertRaises(NativeUIError):self.owner.run(20000)
            self.assertEqual(before,self.store.read());self.assertEqual(2,len(self.shells()));self.assertFalse(self.h.files.store.read()['removed'])

    def test_permission_unknown_cannot_replace_actual_esrch_or_retire_old_contexts(self):
        with self.h.phase.flow.session():
            self.prepare();original=self.os.session.state_path.read_bytes();self.os.presence.presence='unknown'
            with self.assertRaises(NativeUIError):self.owner.run(20000)
            self.assertEqual(original,self.os.session.state_path.read_bytes());self.assertEqual(2,len(self.shells()))
            self.assertEqual('EPERM',self.os.presence.value['errorSymbol']);self.assertIsNone(self.roles)
            self.assertIsNotNone(self.parent.read());self.assertIsNotNone(self.h.profile.store.read())

    def test_cleanup_phase_changes_after_parent_cas_prevent_actual_sdk_input(self):
        with self.h.phase.flow.session():
            self.prepare();write=self.store.write
            def changed(value,previous):
                write(value,previous)
                if value['phase']=='stop-issued':self.h.phase.activate()
            self.store.write=changed
            with self.assertRaises(NativeUIError):self.owner.run(20000)
            self.assertEqual([],self.shells());self.assertEqual('prepared',self.owner.inputs.read()['phase'])
            self.assertEqual('stop-issued',self.store.read()['phase']);self.assertTrue(self.os.running)

    def test_frozen_host_native_clock_jump_in_restart_input_cas_prevents_actual_sdk_stop(self):
        with self.h.phase.flow.session():
            self.prepare();write=self.inputs_store.write
            def slow(value,previous):
                write(value,previous)
                if value['phase']=='stop-issued':self.h.h.native.epoch+=2000
            self.inputs_store.write=slow
            with self.assertRaises(NativeUIError):self.owner.run(20000)
            self.assertEqual([],self.shells());self.assertEqual('stop-issued',self.owner.inputs.read()['phase'])
            self.assertEqual('stop-issued',self.store.read()['phase']);self.assertTrue(self.os.running)

    def test_lost_once_only_stop_reply_keeps_original_intent_without_launch_or_second_stop(self):
        with self.h.phase.flow.session():
            self.prepare();self.os.lost='stop'
            with self.assertRaises(NativeUIError):self.owner.run(20000)
            self.assertEqual(1,len(self.shells()));self.assertEqual('stop-issued',self.owner.inputs.read()['phase'])
            before=self.store.read()
            with self.assertRaises(NativeUIError):self.owner.run(20000)
            self.assertEqual(before,self.store.read());self.assertEqual(1,len(self.shells()));self.assertIsNotNone(self.parent.read())

    def test_keyboard_raised_after_actual_ipc_release_prevents_released_or_archive_success(self):
        with self.h.phase.flow.session():
            self.prepare();append=self.owner.append
            def late(kind,original):
                append(kind,original)
                if kind=='ipc-closed':
                    from self_tests.test_pico_chat_keyboard import keyboard
                    self.h.model.view.source['keyboard']=keyboard(True)
            self.owner.append=late
            with self.assertRaises(NativeUIError):self.owner.run(20000)
            self.assertEqual(2,len(self.shells()));self.assertTrue(self.h.files.store.read()['removed'])
            self.assertTrue(self.h.fresh.fd_owner.closed);self.assertNotEqual('released',self.store.read()['phase'])
            self.assertIsNotNone(self.parent.read());self.assertIsNotNone(self.h.profile.store.read())

    def archive_complete(self):
        from adapters.chat_journey.evidence_archive import ChatArchiveCatalog,ChatEvidenceArchive,completed_archive
        from adapters.pico4.chat_archive import ChatArchiveReleaseSource,ChatArchiveUnlinkFence
        catalog=ChatArchiveCatalog(hold_files=False);self.addCleanup(catalog.close_host)
        # These explicit component roots are fully consumed. A real parent
        # additionally requires all 26 independent Witness stages and the full
        # typed catalog; this component fixture makes no such journey claim.
        def add(store,value):catalog.add('primary/'+store.path.name,store,value)
        for store in (self.parent,self.h.owner.store,self.h.profile.store):add(store,store.read())
        owners=(self.owner,*self.roles,*(role.script_source for role in self.roles))
        for owner in owners:
            add(owner.store,owner.previous);history=getattr(owner,'history',None) or owner.chunks
            for index in range(len(history.identities)):
                store=history.store(index);add(store,store.read())
        add(self.inputs_store,self.owner.inputs.read())
        catalog.rows['primary/'+self.inputs_store.path.name]['retire']=lambda check:self.owner.inputs.retire(self.owner.new_binding,self.owner.sources[1],before_discard=check)
        admitted={row['store'].path for row in catalog.rows.values()}
        def inventory(expected):self.assertEqual(expected,{path for path in admitted if path.exists()})
        ledger=PrivateFeatureState(self.root/'archive-retirement.json');directory=self.root/'archive'
        guard=ChatArchiveReleaseSource(self.owner,fresh_phase_final=True)
        archive=ChatEvidenceArchive(catalog,directory,ledger,dict(runId=RUN),guard,inventory,unlink_fence=ChatArchiveUnlinkFence(guard));self.addCleanup(archive.close_host)
        self.addCleanup(lambda:directory.chmod(0o700) if directory.exists() else None)
        result=archive.retire();self.assertTrue(archive.complete);self.assertIsNone(ledger.read());self.assertEqual(3,result['chatEvidenceArchiveVersion'])
        evidence=completed_archive(directory);self.assertEqual(result['finalSha256'],evidence['finalSha256'])
        self.assertEqual('ESRCH',evidence['original']['absence']['errorSymbol']);self.assertEqual(789,evidence['original']['native']['processId'])
        self.assertIsNone(self.inputs_store.read());self.assertTrue(self.h.fresh.fd_owner.closed)


_APPLICATION_GROUPS={
    'journey':('test_original_restart_birth_profile_new_roles_both_quiet_windows_and_kernel_ipc_release',),
    'recovery':('test_changed_physical_profile_refuses_cursor_transfer_and_cannot_replay_restart',
        'test_permission_unknown_cannot_replace_actual_esrch_or_retire_old_contexts'),
    'admission':('test_cleanup_phase_changes_after_parent_cas_prevent_actual_sdk_input',
        'test_frozen_host_native_clock_jump_in_restart_input_cas_prevents_actual_sdk_stop'),
    'delivery':('test_lost_once_only_stop_reply_keeps_original_intent_without_launch_or_second_stop',),
    'post-ipc':('test_keyboard_raised_after_actual_ipc_release_prevents_released_or_archive_success',)}


def _application_tests(group):
    names=[name for group_names in _APPLICATION_GROUPS.values() for name in group_names]
    if len(names)!=len(set(names)) or set(names)!=set(unittest.defaultTestLoader.getTestCaseNames(ApplicationCloseTests)):
        raise RuntimeError('Chat application owning selections must remain disjoint and lossless')
    return unittest.TestSuite(ApplicationCloseTests(name) for name in _APPLICATION_GROUPS[group])


def application_close_journey_tests():return _application_tests('journey')
def application_close_recovery_tests():return _application_tests('recovery')
def application_close_admission_tests():return _application_tests('admission')
def application_close_delivery_tests():return _application_tests('delivery')
def application_close_post_ipc_tests():return _application_tests('post-ipc')


if __name__=='__main__':unittest.main()
