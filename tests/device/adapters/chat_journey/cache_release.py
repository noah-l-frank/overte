"""Original cache tombstones, independent absence quiet and retained peer IPC."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
import uuid

from adapters.chat_journey.cache_lifetime import ChatCacheLifetime
from adapters.chat_journey.compiled_samples import CompiledChatCacheAbsence
from adapters.chat_journey.erase_restore import references
from adapters.chat_journey.flow_inputs import fresh_roles
from adapters.chat_journey.peer_input_close import ChatPeerInputClose
from adapters.chat_journey.peer_retirement import ChatPeerRetirementFiles
from adapters.chat_journey.phase_fence import ChatPhaseFence,bind_phase_fence
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.native_chat_profile import OwnedChatProfile
from adapters.native_feature_observation import integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import same

VERSION=2


class ChatCacheRelease:
    """One warm owner; every uncertain native/file mutation remains retained.

    Qt/global process destruction and post-restart profile verification belong
    to the enclosing parent. This component cannot grant feature capability.
    """
    def __init__(self,caches,roles,profile,input_close,files,store,fence,*,defer_ipc=False,monotonic=time.monotonic,sleep=time.sleep):
        need(type(caches) is tuple and len(caches)==2 and all(type(cache) is ChatCacheLifetime for cache in caches)
            and type(roles) is tuple and len(roles)==2 and all(type(role) is CompiledChatCacheAbsence for role in roles)
            and type(profile) is OwnedChatProfile and type(input_close) is ChatPeerInputClose
            and type(files) is ChatPeerRetirementFiles and files.input_close is input_close
            and type(fence) is ChatPhaseFence and fence.cleanup is not None
            and type(defer_ipc) is bool and callable(monotonic) and callable(sleep) and store.read() is None)
        self.caches,self.roles,self.profile,self.input_close,self.files,self.store,self.fence=caches,roles,profile,input_close,files,store,fence
        self.defer_ipc=defer_ipc
        self.monotonic,self.sleep=monotonic,sleep;self.last_clock=None;self.previous=None;self.failed=False;self.frames=[]
        self.locks=roles[0].locks;self.run_id=profile.run
        for lock in self.locks:lock.assert_held()
        need(roles[0].role=='primary' and roles[1].role=='actor' and self.locks[1] is input_close.lock is files.lock
            and all(role.locks==self.locks and not role.frames and not role.component_only and role.vr
                and role.run==self.run_id and role.binding==profile.binding and role.peer_binding==roles[0].peer_binding for role in roles)
            and profile.lock is self.locks[0] and fence.flow.roles[0].locks==self.locks
            and fence.flow.scope['binding']==profile.binding and fence.flow.scope['peerBinding']==roles[0].peer_binding
            and fence.flow.source.run==self.run_id and files.run_id==self.run_id)
        need(all(cache.lock is lock and cache.capture.run==self.run_id and cache.capture.owner.binding==binding
            and cache.base['phase']=='active' and same(cache.store.read(),cache.previous)
            for cache,lock,binding in zip(caches,self.locks,(profile.binding,roles[0].peer_binding))))
        need(getattr(caches[1].reader,'_chat_transport',None) is files
            and len({store.path,profile.store.path,*[role.store.path for role in roles],*[cache.store.path for cache in caches]})==6
            and store.path.parent==roles[0].store.path.parent==roles[1].store.path.parent)
        self.profile_original=deepcopy(profile.reader.last);need(self.profile_original is not None and self.profile_original['restored']
            and self.profile_original['restoreAttempted'] and self.profile_original['current']==self.profile_original['original'])
        self.profile_disk=deepcopy(profile.previous);need(same(profile.store.read(),self.profile_disk))
        self.scope=dict(chatCacheReleaseVersion=VERSION if defer_ipc else 1,runId=self.run_id,binding=deepcopy(profile.binding),
            peerBinding=deepcopy(roles[0].peer_binding),cacheJournals=[cache.store.path.name for cache in caches],
            absenceJournals=[role.store.path.name for role in roles],profileJournal=profile.store.path.name,
            profileSha256=digest(self.profile_disk),inputCloseJournal=input_close.store.path.name,
            inputCloseSha256=digest(input_close.previous))
        if defer_ipc:self.scope['ipcDeferred']=True
        self.chunks=ChatSourceChunks(store,self.scope);self.chunks.inventory(0)
        for cache in caches:
            bind_phase_fence(cache,fence);bind_phase_fence(cache.reader._chat_transport,fence)
        bind_phase_fence(files,fence);self.authority()

    def now(self):
        value=self.monotonic();need(number(value,0,1e15) and (self.last_clock is None or value>=self.last_clock))
        self.last_clock=value;return value

    def authority(self):
        for lock in self.locks:lock.assert_held()
        self.files.authority();self.fence.original();self.chunks.verify()
        need(same(self.profile.store.read(),self.profile_disk) and same(self.profile.reader.last,self.profile_original)
            and same(self.input_close.store.read(),self.input_close.previous)
            and digest(self.input_close.previous)==self.scope['inputCloseSha256'])
        for cache in self.caches:
            need(same(cache.store.read(),cache.previous));cache.validate();cache.owner()
        for role in self.roles:role.history.verify();need(same(role.store.read(),role.previous))

    def save(self,phase,**changes):
        self.authority();need(same(self.store.read(),self.previous))
        value={**(self.previous or self.scope),'phase':phase,**deepcopy(changes)}
        if 'chunks' not in value:value['chunks']=[]
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def issue(self,phase):
        self.fence.mark();self.save(phase);self.fence.check()

    def tombstones(self):
        for role in self.roles:
            frame=role.frames[-1]
            for key,cache in zip(('primary','peer'),self.caches):
                packet=frame[key];source=packet['source'];owned=cache.capture.owner.owned()
                need(cache.base['phase']=='retired' and owned['ownershipVersion']==2 and not owned['active']
                    and owned['retirement'] is not None and packet['chatVersion']==3
                    and packet['instance']==cache.scope['sourceInstance'] and source['selfSha256']==cache.scope['selfSha256']
                    and source['openedCommandId']==cache.base['activation']['request']['commandId']
                    and source['retiredCommandId']==cache.base['retirement']['request']['commandId']
                    and source['retired'] and not source['scopePresent'] and source['events']==[]
                    and source['eventSequence']==source['openedEpochMs']==0 and source['droppedEvents']==0
                    and same(source,cache.base['frames'][-1]['packet']['source']))
            need(frame['view']['source']['storage']['configSha256']==self.profile_original['original']['cache']['ArmoredChat-Config'])

    def sample(self,after_epoch):
        started=self.now();self.final_started=started;self.fence.mark();self.save('reading')
        observed=[role.read(uuid.uuid4().hex,after_epoch) for role in self.roles]
        need(observed[0]==observed[1] or all(same(observed[0][key],observed[1][key]) for key in ('state','lifecycle','resources')))
        need(all(value['resources']==[] for value in observed));self.tombstones()
        if self.frames:
            for role,old in zip(self.roles,self.original_frames):
                frame=role.frames[-1]
                need(same(frame['view']['source']['storage'],old['view']['source']['storage'])
                    and same(frame['lifecycle']['lifecycle'],old['lifecycle']['lifecycle'])
                    and frame['view']['instance']==old['view']['instance'] and frame['lifecycle']['instance']==old['lifecycle']['instance'])
        else:self.original_frames=[deepcopy(role.frames[-1]) for role in self.roles]
        row=dict(roles=references(self.roles),sha256=[digest(role.frames[-1]) for role in self.roles])
        chunks=self.chunks.append(row,self.previous['chunks']);self.save('quiet',chunks=chunks);self.frames.append(row)
        self.authority();self.fence.check();fresh_roles(self.roles,started,self.now)
        return [epoch for role in self.roles for epoch in epochs(role.frames[-1])]

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

    def run(self,after_epoch):
        try:
            need(not self.failed and self.previous is None and integer(after_epoch,1))
            self.save('admitted')
            for index,cache in enumerate(self.caches):
                label='primary' if index==0 else 'peer';self.issue(label+'-retirement-issued')
                cache.retire();self.save(label+'-retired')
            self.quiet(max(after_epoch,self.profile_original['capturedEpochMs']))
            if self.defer_ipc:
                self.save('caches-quiet');result=deepcopy(self.previous);self.authority()
                fresh_roles(self.roles,self.final_started,self.now);return result
            self.issue('ipc-close-issued');closed=self.files.close(retain=True)
            need(closed['closing'] and closed['removed'] and closed['result']['retired']);self.save('ipc-closed',ipc=closed)
            result=deepcopy(self.previous);self.authority();fresh_roles(self.roles,self.final_started,self.now)
            return result
        except Exception:
            self.failed=True
            raise NativeUIError('Chat cache/IPC closure is unresolved; original journals remain without replay') from None


def epochs(frame):
    code=frame['compiledChat']
    return [frame[key]['capturedEpochMs'] for key in ('primary','peer','view','lifecycle')]+[
        code['before']['requestedEpochMs'],code['scripts']['capturedEpochMs'],code['after']['capturedEpochMs']]
