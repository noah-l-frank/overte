"""Warm Pico parent/compiled originals through archival; product producers are seams.

The actual child owners, parent methods, phase HTTP protocol, FS/OFD histories,
restart cursor and final catalog run. Source clocks and native/widget/network/
SDK/process identity production are synthetic: no app, AC, hardware or hermetic
peer build is run. Progress timings use the actual host monotonic clock; they
do not qualify live target freshness under this filesystem load.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import os
import math
import time
import unittest
import uuid
from unittest.mock import patch

from adapters.chat_journey.script_source import ChatScriptSource
from adapters.chat_journey.erase_restore import ChatEraseRestore
from adapters.chat_journey.peer_input_close import ChatPeerInputClose
from adapters.chat_journey.peer_retirement import ChatPeerRetirementFiles
from adapters.chat_journey.cache_lifetime import ChatCacheLifetime
from adapters.chat_journey.owned_peer import OwnedChatPeer
from adapters.native_fd_owner import OriginalDescriptor
from adapters.native_chat_observation import NativeChatObservation,OwnedChatCapture
from adapters.native_chat_profile import OwnedChatProfile
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.chat_composition import PicoChatComposition
from adapters.pico4.chat_restart_io import PicoChatRestartIO
from adapters.token_chat_ui import TokenChatUI
from adapters.chat_actor_files import node
from fixture.chat_actor_process import LinuxChatActorProcess
from self_tests import test_chat_compiled_dispatcher as compiled_seams
from self_tests import test_chat_dispatcher as dispatcher_seams
from self_tests import test_chat_witness as witness_seams
from self_tests import test_chat_background as background_seams
from self_tests import test_chat_journey_samples as model_seams
from self_tests import test_chat_script_source as source_seams
from self_tests import test_pico_chat_application_close as application_seams
from self_tests.test_chat_erase_controls import CleanupWidgets
from self_tests.test_chat_profile_owner import Boundary as ProfileBoundary
from self_tests.test_pico_chat_restart_io import RestartBoundary
from self_tests.test_native_chat_observation import RUN

KEY='a1'*16


class WarmArchiveTests(unittest.TestCase):
    def store(self,path):
        path=Path(path)
        if path.stem in ('dispatch-peer-files','dispatch-peer-input'):path=path.parent/'peer'/path.name
        if path.parent.name!='peer' and path.suffix=='.json' and not path.name.startswith('normal-script-'):
            path=path.with_name('chat-fixture-'+path.stem+'-'+KEY+'.json')
        return PrivateFeatureState(path)

    def setUp(self):
        # Choose the actual private paths and numeric original process binding
        # before any owner/input; completed journals are never renamed/copied.
        for module in (compiled_seams,dispatcher_seams,witness_seams,background_seams,model_seams,application_seams):
            p=patch.object(module,'PrivateFeatureState',self.store);p.start();self.addCleanup(p.stop)
        p=patch.object(dispatcher_seams,'Widgets',CleanupWidgets);p.start();self.addCleanup(p.stop)
        # Match the original TSI getter's fixed whole-process nonce capacity;
        # role readers share one native birth, never independent request budgets.
        self.root_requests={};send_root=source_seams.RootBoundary.send
        def bounded_root(boundary,request):
            requests=self.root_requests.setdefault(boundary.instance,set())
            if request['commandId'] in requests or len(requests)>=4096:
                from adapters.normal_ui import NativeUIError
                raise NativeUIError('Original native ScriptRoots nonce budget exhausted: '+str(len(requests)))
            requests.add(request['commandId']);result=send_root(boundary,request)
            boundary.sequence=len(requests);boundary.value['sequence']=len(requests)
            return result
        p=patch.object(source_seams.RootBoundary,'send',bounded_root);p.start();self.addCleanup(p.stop)
        self.c=compiled_seams.CompiledDispatcherTests()
        with patch.object(model_seams,'BINDING',model_seams.BINDING|dict(processIdentity='123:456')):self.c.setUp()
        self.addCleanup(self.c.doCleanups);d=self.d=self.c.h;model=d.h.h;self.root=d.root
        if self._testMethodName=='test_all_original_compiled_stages_then_parent_erase_caches_restart_ipc_and_archive':
            # This one manual measurement retains its private originals on
            # success or failure. Only its already-registered tempfile cleanup
            # is removed; actual descriptor-owner cleanup still runs normally.
            temporary=model.temp
            cleanups=[row for row in model._cleanups if getattr(row[0],'__self__',None) is temporary
                and getattr(row[0],'__func__',None) is type(temporary).cleanup]
            self.assertEqual(1,len(cleanups));model._cleanups.remove(cleanups[0]);temporary._finalizer.detach()
            print('Warm measurement originals retained in '+str(self.root),flush=True)
        d.h.original.identity='123:456';d.strict_peer_files=True
        original_sync=d.sync
        def sync():
            original_sync()
            if d.widgets.panel:
                source=model.view.source;source['ui'].update(generation=f'{d.widgets.page_life:032x}',historySha256=d.widgets.digest())
                if d.widgets.channel=='settings':source['ui'].update(visibleMessages=[],visibleRowCount=0)
        d.sync=sync
        ordinary=d.widgets.input
        def ordinary_input(identifier,action,reference,value=None):
            try:return ordinary(identifier,action,reference,value)
            finally:
                if identifier=='chat.erase' and d.widgets.erased:model.view.source['storage'].update(kind='null',count=0,events=[])
                d.sync()
        d.widgets.input=ordinary_input
        actor_directory=self.root/'actor-originals';actor_directory.mkdir(mode=0o700)
        d.peer_directory=lambda:actor_directory
        def actor_factory(root):
            actor=dispatcher_seams.actor_seams.FileActor(root);actor.native=model.peer;actor.mutate=self.lifetime
            return actor
        d.make_peer_actor=actor_factory
        self.h=SimpleNamespace(model=model,binding=d.h.binding,peer_binding=d.h.peer_binding,locks=d.roles[0].locks,
            now=lambda:d.h.native.host,epoch=lambda:d.h.native.epoch,sleep=d.sleep,native_reader=self.native_reader)
        self.roles=None;self.new_mutate=None
        native=ProfileBoundary();self.profile_native=native
        for where in ('cache','worker'):native.hashes[where]['ArmoredChat-Config']=model.view.source['storage']['configSha256']
        send=native.send
        def profile_send(request):
            transport=getattr(reader,'_chat_transport',None);fence=getattr(transport,'phase_fence',None)
            if fence is not None and request['operation']=='restore':fence.check()
            native.epoch=self.h.epoch();send(request)
            if request['operation']=='restore':model.view.source['storage'].update(kind='unset',count=0,events=[])
        reader=native.reader();reader.send=profile_send;reader.clock_ms=self.h.epoch;reader.monotonic=self.h.now;reader.sleep=self.h.sleep
        reader._chat_transport=SimpleNamespace()
        native.mutate=lambda value:value['settings'].update(mutationSequence=2 if value['restoreAttempted'] else 0)
        profile=OwnedChatProfile(reader,self.store(self.root/'profile.json'),self.h.binding,RUN,self.h.locks[0]);profile.perform('acquire')
        state=self.root/('normal-script-state-'+KEY+'.json');ui=self.root/('normal-script-ui-'+KEY+'.json')
        manager=SimpleNamespace(binding=self.h.binding,store=PrivateFeatureState(state))
        manager.store.write(dict(binding=self.h.binding,sourceKind='scripts',source=None,loadAttempted=False,managerOwned=False,dialogOwned=False),None)
        self.manager=manager;self.old_manager=state.read_bytes()
        adapter=SimpleNamespace(_scripts=lambda target:manager,_script_paths=lambda target:(state,ui),
            _chat_cleanup_admission_store=lambda target:self.store(self.root/'cleanup.json'),
            _chat_cache_release_store=lambda target:self.store(self.root/'cache-release.json'),
            _chat_application_store=lambda target:self.store(self.root/'application.json'),
            _chat_restart_inputs_store=lambda target:self.store(self.root/'restart.json'),
            _chat_archive_retirement_store=lambda target:self.store(self.root/'archive-retirement.json'),
            _chat_host_close_store=lambda target:self.store(self.root/'host-close.json'),
            _chat_witness_store=lambda target:d.w.publisher_store,
            _chat_postrestart_store=lambda target,kind:self.store(self.root/('post-'+kind+'.json')))
        def code_source(target,run,*,role,source_lock,witness=False,stage='active',predecessor=None):
            self.assertIs(source_lock,self.h.locks[0])
            if stage=='active':return self.c.code(role,d.w.witness_store if witness else d.roles[0 if role=='primary' else 1].store)
            return ChatScriptSource(run,role,self.h.binding,predecessor.roots,predecessor.scripts,
                self.store(self.root/(stage+'-'+role+'-code.json')),source_lock,predecessor=predecessor,monotonic=self.h.now)
        adapter._chat_script_source=code_source
        def samples(target,run,peer,binding,*,role,source_lock,peer_lock,**kw):
            self.assertIs(source_lock,self.h.locks[0]);self.assertIs(peer_lock,self.h.locks[1])
            witness=kw.get('witness',False);kind=kw.get('stage');erased=kw.get('erased',False)
            store=(d.w.initial_witness_store if kind=='initial' else d.w.witness_store) if witness else self.store(self.root/(('final-' if kind else 'erased-')+role+'.json'))
            result=self.c.samples(role,store,kind=dispatcher_seams.ChatCacheAbsence if kind else None,script_source=kw.get('script_source'))
            if not witness:result.peer=peer
            return result
        adapter._chat_samples=samples;adapter._chat_cache_absence=samples
        adapter._chat_erase_restore=lambda target,profile,before,after:ChatEraseRestore(profile,before,after,
            lambda intent:TokenChatUI(d.widgets,intent,RUN,monotonic=self.h.now,sleep=self.h.sleep),
            self.store(self.root/'erase.json'),monotonic=self.h.now,sleep=self.h.sleep)
        def primary_cache(target,run,**kw):
            old=d.owner.caches[0];reader=self.native_reader(0);reader._chat_transport=SimpleNamespace()
            return ChatCacheLifetime(OwnedChatCapture(reader,old.capture.owner,run),old.store,self.h.locks[0],monotonic=self.h.now)
        adapter._chat_cache_lifetime=primary_cache
        adapter._chat_restart_io=lambda target,binding:self.restart_io()
        adapter._chat_postrestart_sources=lambda target,run,identity,peer,binding,**kw:application_seams.ApplicationCloseTests.successor(self,identity)
        p=self.parent=PicoChatComposition.__new__(PicoChatComposition)
        p.adapter,p.target,p.source,p.binding,p.native=adapter,d.h.target,d.w.parent_source,self.h.binding,d.roles[0].lifecycle
        p.store=self.store(self.root/'parent.json');p.lock=self.h.locks[0];p.previous=None;p.failed=False
        p.peer=OwnedChatPeer.__new__(OwnedChatPeer)
        p.peer.binding=self.h.peer_binding;p.peer.lock=self.h.locks[1];p.peer.guard=lambda:True
        p.peer.reader=lambda:self.native_reader(1);p.peer.input_close=self.input_close;p.peer.retirement_cache=self.retirement_cache
        p.peer.retirement_reader=self.retirement_peer_reader;p.peer.files=p.peer.process=p.peer.retirement_files=None
        p.mixer=SimpleNamespace(guard=lambda:True);p.profile=profile;p.roles=d.roles;p.initial=d.flow.initial_roles
        p.code_sources=tuple(role.script_source for role in p.roles);p.flow=d.flow;p.dispatcher=d.owner
        p.after=None;p.erase=p.input_close=p.cleanup_admission=p.cleanup_fence=p.cache_release=None
        with p.held():p.save('prepared',peerBinding=self.h.peer_binding,peerOriginBasis='native-configured-metadata-only',completedSteps=0)
        def next_parent(index):
            if index:
                d.sleep(.01);fixed=dispatcher_seams.recipe(RUN)[index];d.w.journal.activate(RUN,uuid.uuid4().hex,fixed['verb'],fixed['inputs'])
            result=p.step()
            if 'peer' in d.owner.children:
                p.peer.files=self.h.files=d.files;p.peer.files_store=d.files.store
                if p.peer.process is None:
                    # Process/executable provenance remains a declared producer
                    # seam. This actual host pair exercises the real closing
                    # implementation; it does not qualify a native AC binary.
                    process=p.peer.process=LinuxChatActorProcess.__new__(LinuxChatActorProcess)
                    process.fd_owner=OriginalDescriptor('/proc/self/exe',os.O_RDONLY|os.O_CLOEXEC)
                    process.fd=process.fd_owner.fd;process.released=d.files.released;self.addCleanup(process.close)
            return result
        d.next=next_parent

    def native_reader(self,index,files=None):
        if files is None and (index==0 or not hasattr(self.d,'files')):
            result=(self.h.model.primary,self.h.model.peer)[index].reader();result.pid=123 if index==0 else 456
            result.clock_ms=self.h.epoch;result.monotonic=self.h.now;result.sleep=self.h.sleep;return result
        files=files or self.d.files
        def original():self.d.actor.tick();return files.read()
        result=NativeChatObservation(files.send,original,self.h.epoch,lambda:True,456,monotonic=self.h.now,sleep=self.h.sleep)
        result._chat_transport=files;return result

    def lifetime(self,value):
        from adapters.chat_peer_input import COMMAND,RECEIPT
        d=self.d;root=d.actor.root
        if not (root/RECEIPT).exists() and d.peer_fd>=0:os.close(d.peer_fd);d.peer_fd=-1
        def present(name):
            path=root/name;return dict(present=True,node=node(path.stat())) if path.exists() else dict(present=False,node={})
        native=d.owner.children['peer'].input.previous['receipt']['native']
        value['inputLifetime']={key:deepcopy(native[key]) for key in ('commandId','runId','instance','sequence','scriptPolls','releaseConsumed','processId')}
        value['inputLifetime'].update(inputLifetimeVersion=1,commandId=value['native']['commandId'],ownerRunId=RUN,capturedEpochMs=self.h.epoch(),
            command=present(COMMAND),receipt=present(RECEIPT),receiptHandle=dict(open=d.peer_fd>=0,node=node(os.fstat(d.peer_fd)) if d.peer_fd>=0 else {}))

    def input_close(self,owner,*,distant):
        return ChatPeerInputClose(owner,self.native_reader(1),PrivateFeatureState(self.d.files.store.path.with_name('input-close.json')),
            self.h.locks[1],distant=distant,monotonic=self.h.now,sleep=self.h.sleep)

    def retirement_cache(self,run,input_close):
        self.h.fresh=ChatPeerRetirementFiles(self.d.files,input_close);self.parent.peer.retirement_files=self.h.fresh
        old=self.d.owner.caches[1]
        return ChatCacheLifetime(OwnedChatCapture(self.native_reader(1,self.h.fresh),old.capture.owner,run),old.store,self.h.locks[1],monotonic=self.h.now)

    def retirement_peer_reader(self):
        return application_seams.ApplicationCloseTests.retirement_peer_reader(self)

    def restart_io(self):
        self.os=RestartBoundary(self.root);self.os.pico_configuration=self.d.h.original.pico_configuration
        self.os.session.state_path.unlink();self.os.session.begin('123:456')
        self.io=PicoChatRestartIO(self.os,self.os.target,self.h.binding,monotonic=self.h.now,sleep=self.h.sleep)
        self.addCleanup(self.io.close_host);send=self.os.write_control_command
        def control(*args):self.os.epoch=self.h.epoch();return send(*args)
        self.os.write_control_command=control;self.os.epoch_milliseconds=lambda target:self.h.epoch()
        self.os.presence.epoch_ms=self.h.epoch;self.os.presence.edit=lambda value:value.update(instance='f'*32)
        native=self.os.native.mutate
        def new(value):native(value);value['instance']='f'*32;value['lifecycle'].update(activations=self.d.h.activations+1,backgrounds=self.d.h.backgrounds)
        self.os.native.mutate=new;self.os.current.hashes=deepcopy(self.parent.cache_release.profile_original['original'])
        self.os.current.edit=lambda value:(value.update(processId=789,instance='9'*32),value['settings'].update(instance='8'*32,writerInstance='7'*32),value['view'].update(instance='6'*32))
        p=patch('adapters.android_process_query.subprocess.run',side_effect=self.os.ps);p.start();self.addCleanup(p.stop)
        self.h.actor=self.d.actor
        return self.io

    def test_three_original_parent_steps_have_no_synthetic_completed_prefix_or_shared_witness_owner(self):
        for index in range(3):self.d.next(index)
        self.assertEqual(3,self.parent.previous['completedSteps']);self.assertEqual('step-completed',self.parent.previous['phase'])
        self.assertEqual(['completed']*3,[row['phase'] for row in self.parent.flow.rows]);self.assertEqual(['acquire'],[row['operation'] for row in self.profile_native.requests])
        self.assertEqual(self.old_manager,self.manager.store.path.read_bytes())

    def test_original_peer_files_join_the_same_native_cache_without_fabricated_process_identity(self):
        for index in range(10):self.d.next(index)
        self.assertIs(self.d.actor.native,self.h.model.peer)
        self.assertEqual(self.h.locks[1].path,self.d.files.store.path.with_name('script-sources.lock'))
        with self.parent.held():
            observed=self.native_reader(1).perform(RUN,'inspect')
            self.assertEqual(self.d.owner.caches[1].base['activation']['request']['commandId'],observed['source']['openedCommandId'])
        self.assertEqual(1,len(self.d.widgets.sent));self.assertEqual(1,self.d.peer_operations.count('send'))

    def test_all_original_compiled_stages_then_parent_erase_caches_restart_ipc_and_archive(self):
        from adapters.chat_journey.evidence_archive import completed_archive
        self.addCleanup(self.parent.detach)
        self.d.complete_positive(check_exhausted=False)
        self.d.w.journal.activate(RUN,uuid.uuid4().hex,'cleanup',{});after=self.h.epoch()
        try:
            self.parent.close_input_and_restore_profile(after);self.parent.prepare_cache_release(after)
            self.parent.restart_and_close_application(after)
        except Exception as error:
            while error.__context__ is not None:error=error.__context__
            import traceback
            self.fail('Warm original cleanup failed:\n'+''.join(traceback.format_exception(error)))
        self.assertEqual(self.old_manager,self.manager.store.path.read_bytes())
        self.assertEqual('released',self.parent.application_close.previous['phase'])
        from adapters.chat_journey.evidence_archive import ChatEvidenceArchive
        retire=ChatEvidenceArchive.retire
        def measured_retire(archive):
            # Real nonce acquisition remains bounded in bounded_root. This
            # preflight rejects even a mathematically impossible best case
            # before original copying/unlinks; it grants no native capacity.
            current=archive.guard.role.script_source.roots.last['sequence']
            minimum=current+2*(math.ceil(len(archive.catalog.rows)/16)+3)
            print('Original warm archive: files='+str(len(archive.catalog.rows))+', nativeRootSequence='+str(current)+', minimumRootRequests='+str(minimum)+', nativeLimit=4096',flush=True)
            self.assertLessEqual(minimum,4096,'Original native whole-process Root budget cannot admit this archive plan')
            started=time.monotonic();original=ChatEvidenceArchive.original;write=ChatEvidenceArchive.write
            def copied(owner,name,raw):
                result=original(owner,name,raw)
                if name.startswith('original-') and (int(name[9:13])+1)%256==0:
                    print('Warm archive copied='+str(int(name[9:13])+1)+' elapsedSeconds='+str(round(time.monotonic()-started,3)),flush=True)
                return result
            def recorded(owner,phase,**changes):
                result=write(owner,phase,**changes)
                if phase in ('archiving','archived','complete') or phase=='retiring' and len(owner.deleted)%256==0:
                    print('Warm archive phase='+phase+' deleted='+str(len(owner.deleted))+' elapsedSeconds='+str(round(time.monotonic()-started,3)),flush=True)
                return result
            with patch.object(ChatEvidenceArchive,'original',copied),patch.object(ChatEvidenceArchive,'write',recorded):return retire(archive)
        try:
            with patch.object(ChatEvidenceArchive,'retire',measured_retire):result=self.parent.finalize_application()
        except Exception as error:
            while error.__context__ is not None:error=error.__context__
            import traceback
            self.fail('Warm original archive failed:\n'+''.join(traceback.format_exception(error)))
        directory=self.parent.archive_plan.archive.directory
        original=completed_archive(directory)
        self.assertEqual(result['finalSha256'],original['finalSha256']);self.assertEqual('ESRCH',original['original']['absence']['errorSymbol'])
        self.assertIsNone(self.parent.store.read());self.assertIsNone(self.parent.profile.store.read())
        self.assertIsNone(self.parent.application_close.inputs.store.read());self.assertTrue(self.h.fresh.fd_owner.closed)
        self.assertEqual(1,self.d.widgets.erased);self.assertEqual(3,len(self.d.widgets.sent));self.assertEqual(26,len(self.d.w.posted))
        self.assertEqual(2,len([row for row in self.os.trace if type(row) is tuple and row[0]=='shell']))
        self.assertFalse(self.manager.store.path.exists())
        self.assertTrue(all(len(requests)<=4096 for requests in self.root_requests.values()))
        host=self.parent.finalize_host();self.assertEqual('original-host-chat-handles',host['sourceScope'])
        self.assertTrue(self.parent.host_close.complete);self.assertTrue(self.parent.detach())
        self.assertEqual(result['finalSha256'],host['finalSha256']);self.assertIsNone(self.parent.host_close.store.read())


def warm_archive_component_tests():
    # The full manual diagnostic intentionally exceeds the unchanged catalog
    # budget. These two short assertions are its disjoint registered prefix.
    return unittest.TestSuite(WarmArchiveTests(name) for name in (
        'test_three_original_parent_steps_have_no_synthetic_completed_prefix_or_shared_witness_owner',
        'test_original_peer_files_join_the_same_native_cache_without_fabricated_process_identity'))


if __name__=='__main__':unittest.main()
