"""Private Pico Chat composition of original sources and once-only child owners.

No public feature capability is granted until enclosing process/final journal
retirement and independent whole-feature cleanup are implemented and verified.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack,contextmanager
from copy import deepcopy
import stat
import os
import math

from adapters.chat_journey.dispatcher import ChatDispatcher
from adapters.chat_journey.owned_peer import OwnedChatPeer
from adapters.chat_journey.owned_mixer import OwnedChatMixer
from adapters.chat_journey.flow_inputs import fresh_roles
from adapters.feature_fixture_access import AdapterFixtureClient
from adapters.native_feature_observation import need,integer,exact
from adapters.normal_feature_state import context
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import same
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader

VERSION=6


PHASES=('admitted','bound','profile-acquire-issued','profile-acquired','prepared','step-issued','step-completed',
    'cleanup-admission-issued','cleanup-admitted','input-close-issued','input-closed','erase-restore-issued','profile-restored','cache-release-issued','caches-ipc-released','caches-retired')


def record(value):
    import re
    exact(value,{'picoChatCompositionVersion','runId','binding','fixtureUrl','phase','peerBinding','peerOriginBasis','completedSteps'})
    need(type(value['picoChatCompositionVersion']) is int and value['picoChatCompositionVersion'] in (1,2,3,4,5,VERSION)
        and type(value['runId']) is str and re.fullmatch('[0-9a-f]{32}',value['runId'])
        and type(value['fixtureUrl']) is str and len(value['fixtureUrl'])<=512
        and value['fixtureUrl'].endswith('/runs/'+value['runId']+'/') and value['phase'] in PHASES
        and integer(value['completedSteps'],0,26))
    context(value['binding'])
    if value['picoChatCompositionVersion']<3:need(value['phase'] not in ('cleanup-admission-issued','cleanup-admitted'))
    if value['picoChatCompositionVersion']<4:need(value['phase'] not in ('cache-release-issued','caches-ipc-released','caches-retired'))
    if value['picoChatCompositionVersion']<5:need(value['phase']!='caches-retired')
    if value['phase']=='admitted':need(value['peerBinding'] is None and value['peerOriginBasis']=='unavailable')
    else:context(value['peerBinding']);need(value['peerOriginBasis']=='native-configured-metadata-only')
    if value['phase'] in PHASES[:5]:need(value['completedSteps']==0)
    if value['phase'] in PHASES[7:]:need(value['completedSteps']==26)
    if value['phase']=='step-completed':need(value['completedSteps']>=1)
    if value['phase']=='step-issued':need(value['completedSteps']<26)
    return value


def peer_directory(adapter,target,*,create=False):
    state,_=adapter._script_paths(target);directory=state.with_name(state.stem.replace('normal-script-state-','chat-peer-state-'))
    if create:
        try:directory.mkdir(mode=0o700)
        except FileExistsError:pass
    try:info=directory.lstat()
    except FileNotFoundError:
        need(not create);return None
    need(stat.S_ISDIR(info.st_mode) and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o700
        and directory.resolve(strict=True)==directory)
    return directory


def peer_retained(adapter,target):
    directory=peer_directory(adapter,target)
    if directory is None:return False
    retained=False
    for path in directory.iterdir():
        if path.name!='script-sources.lock':retained=True;continue
        info=path.lstat();need(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid()
            and stat.S_IMODE(info.st_mode)==0o600 and info.st_nlink==1 and info.st_size==0)
    return retained


class PicoChatComposition:
    """One warm parent; a partial/unknown child is retained, never reconstructed.

    Static peer provenance is its actual native configured source metadata plus
    original kernel/executable/script ownership. It is not a hermetic AC receipt.
    """
    def __init__(self,adapter,target,source,peer_config,domain_ready):
        need(isinstance(source,PhaseFixtureReader) and source.area=='chat' and isinstance(source.client,AdapterFixtureClient)
            and isinstance(peer_config,PrivateFeatureState) and isinstance(domain_ready,PrivateFeatureState))
        self.adapter,self.target,self.source=adapter,target,source
        self.native=adapter._native_feature_observer(target);self.binding=deepcopy(adapter._scripts(target).binding)
        self.native.guard();need(self.native.pid==int(self.binding['processIdentity'].split(':')[0]))
        self.store=adapter._chat_composition_store(target);need(self.store.read() is None)
        self.lock=ScriptSourceLock(self.store.path.with_name('script-sources.lock'))
        self.peer=self.mixer=self.profile=self.dispatcher=None;self.previous=None;self.failed=False
        self.after=None;self.erase=self.input_close=self.cleanup_admission=self.cleanup_fence=self.cache_release=None
        with self.lock.held():
            self.save('admitted',peerBinding=None,peerOriginBasis='unavailable',completedSteps=0)
            try:
                need(not peer_retained(adapter,target))
                directory=peer_directory(adapter,target,create=True)
                peer_lock=ScriptSourceLock(directory/'script-sources.lock')
                self.peer=OwnedChatPeer(peer_config,PrivateFeatureState(directory/'actor-files.json'),source_lock=peer_lock)
                need(self.peer.lock.path!=self.lock.path)
                self.mixer=OwnedChatMixer(self.peer,domain_ready)
                self.save('bound',peerBinding=deepcopy(self.peer.binding),peerOriginBasis='native-configured-metadata-only')
            except Exception:
                self.failed=True
                if self.peer is not None:self.peer.close_host()
                raise NativeUIError('Pico Chat original sources are unavailable; parent intent remains retained') from None

    def guard(self):
        need(same(self.adapter._scripts(self.target).binding,self.binding) and self.native.guard() is not False)
        if self.peer is not None:need(self.peer.guard() is True)
        if self.mixer is not None:need(self.mixer.guard() is True)

    def save(self,phase,**changes):
        self.lock.assert_held();self.guard();need(same(self.store.read(),self.previous))
        base=self.previous or dict(picoChatCompositionVersion=VERSION,runId=self.source.run,binding=self.binding,
            fixtureUrl=self.source.fixture_url)
        value=record({**base,**deepcopy(changes),'phase':phase});self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    @contextmanager
    def held(self):
        with ExitStack() as held:
            for lock in sorted((self.lock,self.peer.lock),key=lambda lock:str(lock.path)):held.enter_context(lock.held())
            yield

    def prepare(self):
        try:
            need(not self.failed and self.previous['phase']=='bound' and self.dispatcher is None)
            with self.held():
                self.code_sources=tuple(self.adapter._chat_script_source(self.target,self.source.run,role=role,
                    source_lock=self.lock) for role in ('primary','actor'))
                self.save('profile-acquire-issued')
                self.profile=self.adapter._chat_profile(self.target,self.source.run,self.lock)
                original=self.profile.perform('acquire');need(original['owned'] and not original['restoreAttempted'])
                self.save('profile-acquired')
                self.adapter._chat_admit_capture(self.target,self.source.run,source_lock=self.lock)
                self.peer.admit_capture(self.source.run)
                self.initial=tuple(self.adapter._chat_cache_absence(self.target,self.source.run,self.peer.reader(),self.peer.binding,
                    role=role,stage='initial',source_lock=self.lock,peer_lock=self.peer.lock,script_source=code)
                    for role,code in zip(('primary','actor'),self.code_sources))
                self.roles=tuple(self.adapter._chat_samples(self.target,self.source.run,self.peer.reader(),self.peer.binding,
                    role=role,source_lock=self.lock,peer_lock=self.peer.lock,pending_capture=True,script_source=code)
                    for role,code in zip(('primary','actor'),self.code_sources))
                self.flow=self.adapter._chat_flow_inputs(self.target,self.source,*self.roles,*self.initial)
                factories=dict(normal=lambda:self.adapter._chat_normal_input(self.target,*self.roles),
                    peer=self.peer_sender,distant=lambda:self.adapter._chat_peer_distant(self.target,self.dispatcher.child('peer')),
                    background=lambda:self.adapter._chat_background(self.target,*self.roles),
                    mixer=lambda:self.adapter._chat_mixer(self.target,self.mixer.controls,*self.roles),
                    **{'no-replay':lambda:self.adapter._chat_no_replay(self.target,*self.roles)})
                self.dispatcher=ChatDispatcher(self.flow,self.caches,factories,self.adapter._chat_dispatcher_store(self.target))
                need(not self.dispatcher.cold);self.save('prepared')
            return self.dispatcher
        except Exception:
            self.failed=True
            raise NativeUIError('Pico Chat preparation is unresolved; original profile/source intents remain without replay') from None

    def caches(self):
        self.lock.assert_held();self.peer.lock.assert_held()
        return (self.adapter._chat_cache_lifetime(self.target,self.source.run,source_lock=self.lock),
            self.peer.cache_lifetime(self.source.run))

    def peer_sender(self):
        self.peer.lock.assert_held()
        input_owner=self.adapter._chat_peer_input(self.target,self.peer.files,self.source.run)
        return self.adapter._chat_peer_send(self.target,input_owner,*self.roles)

    def step(self):
        try:
            need(not self.failed and self.dispatcher is not None and self.previous['phase'] in ('prepared','step-completed'))
            with self.held():
                self.save('step-issued')
                observed=self.dispatcher.step();started=self.flow.now()
                self.save('step-completed',completedSteps=len(self.dispatcher.base['steps']))
                result=deepcopy(observed);self.guard()
                fresh_roles(self.initial if len(self.dispatcher.base['steps'])==1 else self.roles,started,self.flow.now)
                return result
        except Exception:
            self.failed=True
            raise NativeUIError('Pico Chat parent is unresolved; no child input is repeated') from None

    def admit_cleanup(self,after_epoch):
        from adapters.chat_journey.cleanup_admission import ChatCleanupAdmission
        from adapters.chat_journey.phase_fence import ChatPhaseFence
        try:
            need(not self.failed and integer(after_epoch,1) and self.previous['phase']=='step-completed'
                and self.previous['completedSteps']==26 and self.cleanup_admission is None
                and self.dispatcher.base['phase']=='ready' and len(self.dispatcher.base['steps'])==26
                and all(row['phase']=='completed' for row in self.dispatcher.base['steps']))
            with self.held():
                self.dispatcher.chunks.verify();self.dispatcher.audit()
                need(same(self.dispatcher.store.read(),self.dispatcher.previous))
                self.save('cleanup-admission-issued')
                self.cleanup_admission=ChatCleanupAdmission(self.flow,self.adapter._chat_cleanup_admission_store(self.target))
                original=self.cleanup_admission.admit()
                need(after_epoch>=math.ceil(original['activations'][-1]['activatedEpochMs']))
                self.cleanup_fence=ChatPhaseFence(self.flow,cleanup=self.cleanup_admission)
                from adapters.chat_journey.phase_fence import bind_phase_fence
                bind_phase_fence(self.profile,self.cleanup_fence)
                bind_phase_fence(self.profile.reader._chat_transport,self.cleanup_fence)
                self.save('cleanup-admitted');return deepcopy(original)
        except Exception:
            self.failed=True
            raise NativeUIError('Original Chat cleanup admission is unresolved; no cleanup input is authorized') from None

    def close_input_and_restore_profile(self,after_epoch):
        try:
            need(not self.failed and integer(after_epoch,1) and self.previous['phase'] in ('step-completed','cleanup-admitted')
                and self.previous['completedSteps']==26 and all(row['phase']=='completed' for row in self.dispatcher.base['steps']))
            if self.previous['phase']=='step-completed':self.admit_cleanup(after_epoch)
            from adapters.chat_journey.phase_fence import bind_phase_fence
            with self.held():
                self.save('input-close-issued')
                distant=self.dispatcher.children.get('distant');need(distant is not None)
                self.input_close=self.peer.input_close(distant.sender.input,distant=distant)
                bind_phase_fence(self.input_close,self.cleanup_fence);self.input_close.run()
                self.save('input-closed')
                self.erase_code_sources=tuple(self.adapter._chat_script_source(self.target,self.source.run,role=role,
                    source_lock=self.lock,stage='erase',predecessor=code)
                    for role,code in zip(('primary','actor'),self.code_sources))
                self.after=tuple(self.adapter._chat_samples(self.target,self.source.run,self.peer.reader(),self.peer.binding,
                    role=role,source_lock=self.lock,peer_lock=self.peer.lock,erased=True,script_source=code)
                    for role,code in zip(('primary','actor'),self.erase_code_sources))
                self.erase=self.adapter._chat_erase_restore(self.target,self.profile,self.roles,self.after)
                original_intent=self.erase.ui.intent
                def intent(value):
                    self.cleanup_fence.mark();original_intent(value)
                self.cleanup_fence.stream_intent=self.erase.controller_intent
                self.erase.ui.intent=intent;self.erase.ui.io.bind_input_fence(self.cleanup_fence)
                self.cleanup_fence.mark();self.save('erase-restore-issued');result=self.erase.run(after_epoch)
                need(result['phase']=='complete');self.save('profile-restored')
                return deepcopy(self.previous)
        except Exception:
            self.failed=True
            raise NativeUIError('Pico Chat release/profile work is unresolved; original owners remain without replay') from None

    def close_caches_and_ipc(self,after_epoch):
        """Immediate legacy component close; this cannot enter the app restart stage."""
        return self._release_caches(after_epoch,defer_ipc=False)

    def prepare_cache_release(self,after_epoch):
        """Retire original caches while keeping peer queries owned through restart."""
        return self._release_caches(after_epoch,defer_ipc=True)

    def _release_caches(self,after_epoch,*,defer_ipc):
        from adapters.chat_journey.cache_release import ChatCacheRelease
        try:
            need(not self.failed and integer(after_epoch,1) and self.previous['phase']=='profile-restored'
                and self.cache_release is None and self.erase.previous['phase']=='complete'
                and same(self.erase.store.read(),self.erase.previous))
            with self.held():
                self.save('cache-release-issued')
                caches=(self.adapter._chat_cache_lifetime(self.target,self.source.run,source_lock=self.lock),
                    self.peer.retirement_cache(self.source.run,self.input_close))
                self.final_code_sources=tuple(self.adapter._chat_script_source(self.target,self.source.run,role=role,
                    source_lock=self.lock,stage='final',predecessor=code)
                    for role,code in zip(('primary','actor'),self.erase_code_sources))
                final=tuple(self.adapter._chat_cache_absence(self.target,self.source.run,self.peer.reader(),self.peer.binding,
                    role=role,stage='final',source_lock=self.lock,peer_lock=self.peer.lock,script_source=code)
                    for role,code in zip(('primary','actor'),self.final_code_sources))
                self.cache_release=ChatCacheRelease(caches,final,self.profile,self.input_close,self.peer.retirement_files,
                    self.adapter._chat_cache_release_store(self.target),self.cleanup_fence,
                    defer_ipc=defer_ipc,monotonic=self.native.monotonic,sleep=self.native.sleep)
                result=self.cache_release.run(after_epoch);need(result['phase']==('caches-quiet' if defer_ipc else 'ipc-closed'))
                self.save('caches-retired' if defer_ipc else 'caches-ipc-released');result=deepcopy(self.previous);self.guard()
                self.cache_release.authority()
                owned=self.peer.files._owned()
                need(owned['pending'] is None and owned['result']['commandId']==owned['request']['commandId'])
                node={key:owned['result']['stamp'][key] for key in ('device','inode')}
                need(self.peer.process.released(node) is (not defer_ipc))
                fresh_roles(final,self.cache_release.final_started,self.cache_release.now);return result
        except Exception:
            self.failed=True
            raise NativeUIError('Pico Chat cache/IPC release is unresolved; original journals remain without replay') from None

    def restart_and_close_application(self,after_epoch):
        """Actual once-only restart, independent new originals and final IPC."""
        from adapters.pico4.chat_application_close import PicoChatApplicationClose
        try:
            need(not self.failed and integer(after_epoch,1) and self.previous['phase']=='caches-retired'
                and self.cache_release is not None and self.cache_release.defer_ipc
                and getattr(self,'application_close',None) is None)
            with self.held():
                self.guard();io=self.adapter._chat_restart_io(self.target,self.binding)
                self.restart_io=io
                from adapters.pico4.chat_archive import PicoChatArchivePlan
                self.archive_plan=PicoChatArchivePlan(self)
                def successor(identity):
                    return self.adapter._chat_postrestart_sources(self.target,self.source.run,identity,
                        self.peer.retirement_reader(),self.peer.binding,source_lock=self.lock,peer_lock=self.peer.lock)
                self.application_close=PicoChatApplicationClose(self.cache_release,io,self.store,self.previous,
                    self.adapter._chat_application_store(self.target),self.adapter._chat_restart_inputs_store(self.target),
                    successor,monotonic=self.native.monotonic,sleep=self.native.sleep)
                return self.application_close.run(after_epoch)
        except Exception:
            self.failed=True
            raise NativeUIError('Pico Chat application close is unresolved; original process and source journals remain') from None

    def finalize_application(self):
        """Archive exact original sources before retiring consumed journals."""
        try:
            need(not self.failed and getattr(self,'application_close',None) is not None
                and self.application_close.previous['phase']=='released' and getattr(self,'archive_plan',None) is not None)
            with self.held():return self.archive_plan.finish(self.application_close)
        except Exception:
            self.failed=True
            raise NativeUIError('Pico Chat final archive is unresolved; all unknown originals and retirement intents remain') from None

    def detach(self):
        """Host handles only; never a native, journal or feature cleanup claim."""
        okay=True
        for owner in (self.peer,getattr(self,'restart_io',None),getattr(self,'archive_plan',None)):
            if owner is not None:
                try:okay=owner.close_host() is True and okay
                except Exception:okay=False
        return okay


class PicoChatWitness:
    """Independent publisher credentials, original native sources and OS locks.

    The parent manifest supplies only admission/control identity. Every target
    fact is acquired anew by the existing original ChatWitness publisher.
    """
    def __init__(self,adapter,target,source,peer_config):
        need(isinstance(source,PhaseFixtureReader) and source.area=='chat' and not isinstance(source.client,AdapterFixtureClient)
            and isinstance(peer_config,PrivateFeatureState))
        self.adapter,self.target=adapter,target;self.peer=None
        self.native=adapter._native_feature_observer(target);self.binding=deepcopy(adapter._scripts(target).binding)
        self.native.guard();self.lock=ScriptSourceLock(adapter._chat_composition_store(target).path.with_name('script-sources.lock'))
        self.parent=adapter._chat_composition_store(target);original=record(self.parent.read())
        need(type(original) is dict and type(original.get('picoChatCompositionVersion')) is int
            and original['picoChatCompositionVersion'] in (3,4,VERSION) and same(original.get('binding'),self.binding)
            and original.get('runId')==source.run and original.get('fixtureUrl')==source.fixture_url
            and original.get('phase') in ('prepared','step-issued','step-completed'))
        try:
            directory=peer_directory(adapter,target);need(directory is not None)
            self.peer=OwnedChatPeer(peer_config,PrivateFeatureState(directory/'actor-files.json'),
                source_lock=ScriptSourceLock(directory/'script-sources.lock'))
            need(same(self.peer.binding,original['peerBinding']) and self.peer.lock.path!=self.lock.path)
            with ExitStack() as held:
                for lock in sorted((self.lock,self.peer.lock),key=lambda lock:str(lock.path)):held.enter_context(lock.held())
                code=adapter._chat_script_source(target,source.run,role='actor',source_lock=self.lock,witness=True)
                initial=adapter._chat_cache_absence(target,source.run,self.peer.reader(),self.peer.binding,
                    role='actor',stage='initial',source_lock=self.lock,peer_lock=self.peer.lock,witness=True,script_source=code)
                samples=adapter._chat_samples(target,source.run,self.peer.reader(),self.peer.binding,
                    role='actor',source_lock=self.lock,peer_lock=self.peer.lock,witness=True,pending_capture=True,script_source=code)
                self.publisher=adapter._chat_witness(target,source,samples,initial)
        except Exception:
            self.detach();raise NativeUIError('Independent Pico Chat witness originals are unavailable') from None

    def publish(self):
        need(same(self.adapter._scripts(self.target).binding,self.binding) and self.native.guard() is not False
            and self.peer.guard() is True)
        return self.publisher.publish()

    def detach(self):
        if self.peer is not None:self.peer.close_host()
