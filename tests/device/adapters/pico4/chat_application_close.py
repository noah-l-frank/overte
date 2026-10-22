"""Once-only Chat process retirement, original successor sources and final IPC.

A stop/launch receipt never proves release. Old process wrappers are discharged
only by the new process's actual ESRCH source. All originals remain retained.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import time
import uuid

from adapters.chat_actor_files import COMMAND,RESULT
from adapters.chat_journey.cache_release import ChatCacheRelease,epochs
from adapters.chat_journey.compiled_samples import CompiledChatCacheAbsence
from adapters.chat_journey.erase_restore import references
from adapters.chat_journey.flow_inputs import fresh_roles
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.native_feature_observation import fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.pico4.chat_restart_io import PicoChatRestartIO
from adapters.restart_inputs import RestartInputs,validate_native_restart
from adapters.script_journey.history import same

VERSION=1


def birth(packet):
    return dict(pid=packet['processId'],instance=packet['instance'],lifecycle=deepcopy(packet['lifecycle']))


class PicoChatApplicationClose:
    """One warm owner. Issued inputs and host publication are never replayed.

    The supplied successor factory may only construct new read-only sources in
    new private namespaces after the original binding transfer. It cannot open
    a capture or overwrite the old Script/UI journals. This component retains
    those journals and the complete original process proofs for final archival.
    """
    def __init__(self,release,io,parent_store,parent_value,store,inputs_store,successor,*,
                 monotonic=time.monotonic,sleep=time.sleep):
        need(type(release) is ChatCacheRelease and release.defer_ipc and release.previous['phase']=='caches-quiet'
            and type(io) is PicoChatRestartIO and callable(successor) and callable(monotonic) and callable(sleep)
            and isinstance(parent_store,PrivateFeatureState) and isinstance(store,PrivateFeatureState)
            and isinstance(inputs_store,PrivateFeatureState) and store.read() is None and inputs_store.read() is None)
        self.release,self.io,self.parent_store,self.parent_value=release,io,parent_store,deepcopy(parent_value)
        self.store,self.successor,self.monotonic,self.sleep=store,successor,monotonic,sleep
        self.locks=release.locks;self.run_id=release.run_id;self.fence=release.fence
        self.binding=deepcopy(release.profile.binding);self.previous=None;self.failed=False;self.last_clock=None
        self.roles=None;self.new_binding=None;self.sources=None;self.final_started=None;self.closed=None
        need(same(parent_store.read(),parent_value) and parent_value['phase']=='caches-retired'
            and same(parent_value['binding'],self.binding) and io.binding==self.binding
            and len({store.path,inputs_store.path,parent_store.path,release.store.path,release.profile.store.path})==5
            and all(value.path.parent==store.path.parent for value in (inputs_store,parent_store,release.store,release.profile.store)))
        self.inputs=RestartInputs(inputs_store,(parent_store,release.store,release.profile.store),monotonic=monotonic)
        self.scope=dict(picoChatApplicationCloseVersion=VERSION,runId=self.run_id,binding=self.binding,
            peerBinding=deepcopy(release.roles[0].peer_binding),parentJournal=parent_store.path.name,
            parentSha256=digest(parent_value),cacheReleaseJournal=release.store.path.name,
            cacheReleaseSha256=digest(release.previous),profileJournal=release.profile.store.path.name,
            profileSha256=digest(release.profile.previous),restartInputsJournal=inputs_store.path.name)
        self.chunks=ChatSourceChunks(store,self.scope);self.chunks.inventory(0)
        self.release_value=deepcopy(release.previous);self.profile=deepcopy(release.profile_original)
        self.final_peer=deepcopy(release.roles[0].frames[-1]['peer'])
        self.authority()

    def now(self):
        value=self.monotonic();need(number(value,0,1e15) and (self.last_clock is None or value>=self.last_clock))
        self.last_clock=value;return value

    def authority(self):
        for lock in self.locks:lock.assert_held()
        need(not self.failed and same(self.parent_store.read(),self.parent_value)
            and same(self.release.store.read(),self.release_value)
            and same(self.release.profile.store.read(),self.release.profile_disk)
            and same(self.release.profile.reader.last,self.profile))
        self.io.guard_candidate();self.release.files.authority();self.fence.original();self.chunks.verify()
        self.release.input_close.authority()
        for role in self.release.roles:
            role.history.verify();need(same(role.store.read(),role.previous))
        for cache in self.release.caches:
            # These validators are historical; their native guards belong to
            # the dead process and must never be called to fabricate a birth.
            need(same(cache.store.read(),cache.previous) and cache.base['phase']=='retired')
        if self.roles is not None:
            for role in self.roles:
                role.history.verify();role.script_source.history.verify()
                need(same(role.store.read(),role.previous) and same(role.script_source.store.read(),role.script_source.previous))

    def save(self,phase,**changes):
        self.authority();need(same(self.store.read(),self.previous))
        value={**(self.previous or self.scope),'phase':phase,**deepcopy(changes)}
        if 'chunks' not in value:value['chunks']=[]
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def append(self,kind,original):
        self.save('reading');manifest=self.chunks.append(dict(kind=kind,original=deepcopy(original)),self.previous['chunks'])
        self.save(kind,chunks=manifest)

    def issue(self,phase):
        self.fence.mark();self.save(phase);self.fence.check()

    def final_input(self):
        # This callback is immediately before the actual SDK command. The
        # RestartInputs CAS and transport guards have already completed.
        self.authority();self.fence.check()

    def freshness(self,started,packets):
        """Final copies, guards and original clocks share the initial budget."""
        self.authority();readers=(self.sources[1],self.sources[2],self.sources[3])
        oldest=min(min(value['capturedEpochMs'],*(value[key]['capturedEpochMs'] for key in ('settings','view')))
            if 'chatProfileCurrentVersion' in value else value['capturedEpochMs'] for value in packets)
        for reader in readers:need(reader.guard() is not False)
        measured=self.now();epoch=readers[0].clock_ms();ended=self.now()
        need(number(measured,started,started+1.5) and number(ended,measured,started+1.5))
        fresh(oldest,epoch);need(epoch-oldest+math.ceil((ended-measured)*1000)<=1500)

    def new_proofs(self):
        started=self.now();identity,native,presence,current=self.sources
        packet=native.read(native.sequence);validate_native_restart(self.inputs.read()['oldNative'],birth(packet))
        exited=presence.require_absent(self.io.pid);profile=current.read(self.run_id)
        final=native.read(native.sequence)
        need(packet['instance']==exited['instance']==final['instance'] and final['capturedEpochMs']>=exited['capturedEpochMs']
            and birth(final)['pid']==packet['processId'] and profile['processId']==packet['processId']
            and profile['instance']!=self.profile['instance'] and profile['view']['instance']!=self.profile['view']['instance']
            and all(profile['settings'][key]!=self.profile['settings'][key] for key in ('instance','writerInstance'))
            and same(profile['current'],self.profile['original']))
        result=deepcopy(dict(identity=identity,native=packet,absence=exited,profile=profile,nativeAfter=final))
        self.freshness(started,(packet,exited,profile,final));return result,started

    def transfer(self,proof,started):
        # Independent HTTP phase qualification occurs outside the native
        # session lock. Inside it there are ONLY original host CAS/age checks.
        self.fence.mark();self.fence.check();self.freshness(started,tuple(proof[key] for key in ('native','absence','profile','nativeAfter')))
        successor=dict(schemaVersion=1,processIdentity=proof['identity'],sessionNonce=uuid.uuid4().hex+uuid.uuid4().hex,nextSequence=1)
        def host_fresh():
            self.fence.host_fresh();need(number(self.now(),started,started+1.5))
        def intent(value):
            host_fresh();need(same(self.store.read(),self.previous))
            # No source, candidate, HTTP or SDK reentry while session is locked.
            result={**self.previous,'phase':'binding-transfer-issued','bindingTransferIntent':deepcopy(value)}
            self.store.write(result,self.previous);need(same(self.store.read(),result));self.previous=deepcopy(result);host_fresh()
        observed=self.io.transfer.replace(successor,intent=intent,before_publish=host_fresh)
        result=deepcopy(observed);self.freshness(started,tuple(proof[key] for key in ('native','absence','profile','nativeAfter')))
        self.append('binding-transferred',result)

    def qualify_roles(self,roles,binding):
        context(binding);need(type(roles) is tuple and len(roles)==2 and all(type(role) is CompiledChatCacheAbsence for role in roles)
            and roles[0].role=='primary' and roles[1].role=='actor'
            and all(role.binding==binding and role.peer_binding==self.scope['peerBinding'] and role.locks==self.locks
                and not role.component_only and role.vr and role.run==self.run_id and not role.frames for role in roles)
            and binding['processIdentity']==self.sources[0] and binding['sessionId']!=self.binding['sessionId']
            and all(binding[key]==self.binding[key] for key in ('sourceRevision','artifactSha256','targetFingerprint'))
            and len({role.store.path for role in roles}|{role.script_source.store.path for role in roles})==4
            and not {role.store.path for role in roles}&{role.store.path for role in self.release.roles})
        self.roles,self.new_binding=roles,deepcopy(binding)

    def sample(self,after_epoch):
        started=self.now();self.final_started=started;self.fence.mark();self.save('reading')
        observed=[role.read(uuid.uuid4().hex,after_epoch) for role in self.roles]
        need(observed[0]['state']==observed[1]['state'] and all(value['resources']==[] for value in observed))
        for role in self.roles:
            frame=role.frames[-1];p,q=frame['primary'],frame['peer'];source=p['source']
            need(p['chatVersion']==q['chatVersion']==3 and not source['retired'] and source['openedCommandId']==source['retiredCommandId']==''
                and p['instance']!=self.release.roles[0].frames[-1]['primary']['instance']
                and q['instance']==self.final_peer['instance'] and same(q['source'],self.final_peer['source'])
                and frame['lifecycle']['instance']==self.inputs.read()['newNative']['instance']
                and p['source']['session']['domainSha256']==self.final_peer['source']['session']['domainSha256']
                and p['source']['session']['connectionBirth']!=self.release.roles[0].frames[-1]['primary']['source']['session']['connectionBirth']
                and frame['view']['source']['storage']['configSha256']==self.profile['original']['cache']['ArmoredChat-Config'])
        current=self.sources[3].read(self.run_id);need(same(current['current'],self.profile['original'])
            and current['view']['instance']==self.roles[0].frames[-1]['view']['instance'])
        row=dict(roles=references(self.roles),sha256=[digest(role.frames[-1]) for role in self.roles],profile=current)
        self.append('postrestart-quiet',row);self.fence.check();fresh_roles(self.roles,started,self.now)
        self.freshness(started,(current,));return [value for role in self.roles for value in epochs(role.frames[-1])]+[current['capturedEpochMs']]

    def quiet(self,after_epoch):
        started=self.now();first=last=None;quiet_started=None
        for _attempt in range(202):
            current=self.sample(after_epoch);now=self.now();need(now-started<=20)
            if first is None:first=current;quiet_started=now
            else:need(all(0<new-old<=500 for new,old in zip(current,last)))
            last=current
            if now-quiet_started>=3 and all(new-old>=3000 for new,old in zip(current,first)):return
            self.sleep(.1)
        need(False)

    def ipc_absent(self):
        files=self.release.files;owned=files.store.read()
        need(self.closed is not None and same(owned,self.closed) and not files.original._exists(COMMAND)
            and not files.original._exists(RESULT) and owned['closing'] and owned['removed'] and owned['pending'] is None and owned['result']['retired']
            and files.fd_owner.closed and files.released({key:owned['result']['stamp'][key] for key in ('device','inode')}) is True)
        return deepcopy(owned)

    def after_ipc_quiet(self,after_epoch):
        # The peer observation channel is closed. Do not recreate it or retime
        # its final packet. Independent kernel FD absence replaces peer reads;
        # primary Chat/View/compiled code/native/profile remain actual NEW reads.
        started=self.now();first=last=None;quiet_started=None
        primary=self.roles[0]
        for _attempt in range(202):
            began=self.now();self.fence.mark();self.save('reading');ipc=self.ipc_absent()
            primary.script_source.capture(uuid.uuid4().hex,after_epoch)
            packet=primary.primary.perform(self.run_id,'inspect');view=primary.view.read(self.run_id)
            native=primary.lifecycle.read(primary.lifecycle.sequence);profile=self.sources[3].read(self.run_id)
            source=packet['source'];vs=view['source'];old=primary.frames[-1]
            need(same(source,old['primary']['source']) and same(vs['storage'],old['view']['source']['storage'])
                and not vs['ui']['present'] and not vs['editorFocused'] and not vs['editorHasDraft']
                and native['instance']==old['lifecycle']['instance'] and same(native['lifecycle'],old['lifecycle']['lifecycle'])
                and same(profile['current'],self.profile['original']))
            from adapters.native_chat_view import measured_keyboard
            need(not measured_keyboard(vs['keyboard']) and view['instance']==old['view']['instance'])
            code=primary.script_source.frames[-1]
            row=dict(primary=packet,view=view,native=native,profile=profile,compiledChat=deepcopy(code),ipc=ipc)
            self.append('ipc-quiet',row);self.ipc_absent();self.fence.check()
            # No copying or durable write occurs beyond these final guards.
            self.freshness(began,(packet,view,native,profile))
            for reader in (primary.primary,primary.view,primary.script_source.roots,primary.script_source.scripts):need(reader.guard() is not False)
            measured=self.now();epoch=primary.primary.clock_ms();ended=self.now()
            oldest=min(packet['capturedEpochMs'],view['capturedEpochMs'],native['capturedEpochMs'],profile['capturedEpochMs'],code['before']['requestedEpochMs'])
            need(number(ended,measured,began+1.5));fresh(oldest,epoch);need(epoch-oldest+math.ceil((ended-measured)*1000)<=1500)
            current=[row[key]['capturedEpochMs'] for key in ('primary','view','native','profile')]+[
                code['before']['requestedEpochMs'],code['scripts']['capturedEpochMs'],code['after']['capturedEpochMs']]
            now=self.now();need(now-started<=20)
            if first is None:first=current;quiet_started=now
            else:need(all(0<new-old<=500 for new,old in zip(current,last)))
            last=current
            if now-quiet_started>=3 and all(new-old>=3000 for new,old in zip(current,first)):return
            self.sleep(.1)
        need(False)

    def run(self,after_epoch):
        try:
            need(not self.failed and self.previous is None and integer(after_epoch,1))
            self.save('admitted',cursor=self.io.cursor)
            self.inputs.capture(self.binding,self.release.roles[0].lifecycle);self.old_birth=deepcopy(self.inputs.read()['oldNative'])
            self.append('old-native',self.inputs.read());self.issue('stop-issued')
            self.inputs.stop(lambda:self.io.stop(self.final_input))
            self.append('stop-receipt',dict(input=self.inputs.read(),os=self.io.stopped(),processQuery=self.io.last_process_query))
            self.issue('launch-issued');self.inputs.launch(self.io.stopped,lambda:self.io.launch(self.final_input))
            self.sources=self.io.unbound_sources();proof,started=self.new_proofs();self.append('new-process',proof)
            self.freshness(started,tuple(proof[key] for key in ('native','absence','profile','nativeAfter')))
            self.transfer(proof,started)
            binding,roles=self.successor(self.sources[0]);self.qualify_roles(roles,binding)
            self.inputs.observe(binding,self.sources[1]);self.append('new-native',self.inputs.read())
            self.quiet(after_epoch)
            self.issue('ipc-close-issued');closed=self.release.files.close(retain=True);self.closed=deepcopy(closed)
            self.append('ipc-closed',closed);self.ipc_absent();self.after_ipc_quiet(after_epoch)
            # Final old-process absence is a NEW original read, not a stop ACK.
            proof,started=self.new_proofs();self.append('released-final',proof)
            self.save('released');result=deepcopy(self.previous);self.ipc_absent();self.authority()
            self.freshness(started,tuple(proof[key] for key in ('native','absence','profile','nativeAfter')))
            return result
        except Exception:
            self.failed=True
            raise NativeUIError('Chat application retirement is unresolved; no input, transfer or journal is replayed or discarded') from None
