"""Once-only original peer input removal, actual FD absence and native quiet."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import math
import os
import time

from adapters.chat_actor_files import encode,node,stamp
from adapters.chat_peer_input import ChatPeerInput,COMMAND,RECEIPT
from adapters.chat_journey.peer_distant import ChatPeerDistant
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.native_chat_observation import NativeChatObservation
from adapters.native_feature_observation import fresh,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import same,unpack
from adapters.script_journey.lock import ScriptSourceLock

VERSION=1


class ChatPeerInputClose:
    """Retain every original input/history and never replay an uncertain unlink.

    A held peer requires the completed original distance/restore/motion owner.
    No hold needs no position restoration authority. This owner closes only the
    two run-owned input files/receipt handle, never the enclosing actor fixture.
    """
    def __init__(self,input_owner,reader,store,source_lock,*,distant=None,
                 monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(input_owner,ChatPeerInput) and isinstance(reader,NativeChatObservation)
            and isinstance(store,PrivateFeatureState) and isinstance(source_lock,ScriptSourceLock)
            and callable(monotonic) and callable(sleep))
        files=input_owner.files
        transport=getattr(reader,'_chat_transport',getattr(reader.send,'__self__',None))
        need(transport is files and reader.pid==files.pid and not reader.ios
            and source_lock.path==files.store.path.with_name('script-sources.lock')
            and store.path.parent==files.store.path.parent and store.path not in (files.store.path,input_owner.store.path)
            and getattr(files,'_chat_input_close_owner',None) is None and store.read() is None)
        self.input,self.files,self.reader,self.store,self.lock=input_owner,files,reader,store,source_lock
        self.distant,self.monotonic,self.sleep=distant,monotonic,sleep
        self.previous=None;self.failed=False;self.frames=[];self.expected=None
        self.input_digest=digest(input_owner.disk);self.distant_digest=None if distant is None else digest(distant.previous)
        self.authority()
        receipt=input_owner.previous['receipt'];self.native=deepcopy(receipt['native'])
        self.original_command=deepcopy(input_owner.previous['commandStamp'])
        self.original_receipt=deepcopy(receipt['stamp']);self.receipt_sha=receipt['sha256']
        self.scope=dict(chatPeerInputCloseVersion=VERSION,runId=input_owner.run,binding=deepcopy(files.binding),
            sourceSha256=files.source_sha,inputJournal=input_owner.store.path.name,inputSha256=self.input_digest,
            distantSha256=self.distant_digest,commandStamp=self.original_command,receiptStamp=self.original_receipt,
            receiptSha256=self.receipt_sha)
        self.chunks=ChatSourceChunks(store,self.scope);self.chunks.inventory(0)
        files._chat_input_close_owner=self

    def authority(self):
        self.files._check_source();need(same(self.input.store.read(),self.input.disk)
            and digest(self.input.disk)==self.input_digest and self.input.previous is not None)
        intents=self.input.previous['intents'];need(intents and all(row['phase']=='consumed' for row in intents)
            and sum(row['command']['operation']=='release' for row in intents)==1)
        native=self.input.previous['receipt']['native']
        need(native['peerInputVersion']==3 and native['releaseConsumed'] is True)
        held=any(row['command']['operation']=='hold' for row in intents)
        if held or self.distant is not None:
            distant=self.distant
            need(isinstance(distant,ChatPeerDistant) and distant.sender.input is self.input
                and distant.previous is not None and distant.previous['phase']=='complete'
                and same(distant.store.read(),distant.previous) and digest(distant.previous)==self.distant_digest
                and distant.frames and same(distant.frames,unpack(distant.previous['transcript']))
                and all(role.locks[1] is self.lock for role in distant.sender.roles))
            avatars=distant.frames[-1]['avatars']
            need(len(avatars)==2 and all(value['releaseConsumed'] and value['instance']==native['instance']
                and value['scriptPolls']==native['scriptPolls'] for value in avatars)
                and avatars[-1]==native)

    def save(self,phase,**changes):
        self.lock.assert_held();self.authority();self.chunks.verify();need(same(self.store.read(),self.previous))
        value={**(self.previous or self.scope),**deepcopy(changes),'phase':phase}
        if 'chunks' not in value:value['chunks']=[]
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def fresh(self,frame,started):
        self.lock.assert_held();self.authority();self.chunks.verify()
        need(same(self.store.read(),self.previous) and self.reader.guard() is not False)
        measured=self.monotonic();need(number(measured,started,started+1.5));epoch=self.files.clock_ms()
        captured=min(frame['native']['capturedEpochMs'],frame['inputLifetime']['capturedEpochMs']);fresh(captured,epoch)
        ended=self.monotonic();need(number(ended,measured,started+1.5)
            and epoch-captured+math.ceil((ended-measured)*1000)<=1500)

    def sample(self,stage):
        self.save('reading',stage=stage);started=self.monotonic();need(number(started,0,1e15))
        native=self.reader.perform(self.input.run,'inspect');request=self.files._owned()['request']
        value=self.files.read_input_lifetime(request);raw=self.files.last_input_lifetime_raw
        from adapters.native_feature_observation import decode
        original=decode(raw.decode('utf-8'))
        need(original['native']==native and original['inputLifetime']==value and native['chatVersion']==3
            and value['instance']==self.native['instance'] and value['ownerRunId']==self.input.run
            and value['sequence']==self.native['sequence'] and value['scriptPolls']==self.native['scriptPolls']
            and value['releaseConsumed'] is True)
        if self.expected is None:self.expected=deepcopy(native['source'])
        else:need(same(native['source'],self.expected))
        if stage=='before':
            need(value['command']==dict(present=True,node={key:self.original_command[key] for key in ('device','inode')})
                and value['receipt']==dict(present=True,node={key:self.original_receipt[key] for key in ('device','inode')})
                and value['receiptHandle']==dict(open=True,node=value['receipt']['node']))
        else:
            need(value['command']==dict(present=False,node={}) and value['receipt']==dict(present=False,node={})
                and value['receiptHandle']==dict(open=False,node={}) and not self.files._exists(COMMAND)
                and not self.files._exists(RECEIPT) and self.files.released({key:self.original_receipt[key] for key in ('device','inode')}) is True)
        row=dict(base64=base64.b64encode(raw).decode('ascii'),sha256=hashlib.sha256(raw).hexdigest(),
            stamp=deepcopy(self.files.last_input_lifetime_stamp),stage=stage)
        manifest=self.chunks.append(row,self.previous['chunks']);self.frames.append(row)
        self.save('sampled',chunks=manifest);self.fresh(original,started)
        self.latest,self.sample_started=original,started
        return value

    def quiet(self,stage):
        started=previous=self.monotonic();need(number(started,0,1e15));first=last=None
        for _index in range(202):
            sample_started=self.monotonic();need(number(sample_started,previous,started+20) and sample_started-previous<=.5)
            value=self.sample(stage);epochs=(self.latest['native']['capturedEpochMs'],value['capturedEpochMs'])
            if first is None:first=epochs;quiet_started=self.monotonic()
            else:need(all(0<now-old<=500 for now,old in zip(epochs,last)))
            last=epochs;now=self.monotonic();need(number(now,previous,started+20));previous=now
            if now-quiet_started>=3 and all(now-old>=3000 for now,old in zip(epochs,first)):return
            self.sleep(.1)
        need(False)

    def unlink_original(self,name,original,phase):
        self.save(phase+'-issued')
        raw,info=self.files._read(name,4096);need(stamp(info)==original)
        if name==COMMAND:need(raw==encode(self.input.previous['intents'][-1]['command']))
        else:need(hashlib.sha256(raw).hexdigest()==self.receipt_sha and self.files.released(node(info)) is False)
        self.fresh(self.latest,self.sample_started)
        # Exactly one unlink after the original durable admission. Any exception
        # poisons this owner; a missing or surviving path is never retried here.
        os.unlink(name,dir_fd=self.files.fd);os.fsync(self.files.fd)
        need(not self.files._exists(name));self.save(phase+'-observed')

    def run(self):
        try:
            with self.lock.held():
                need(not self.failed and self.previous is None);self.save('admitted')
                self.quiet('before')
                self.unlink_original(COMMAND,self.original_command,'command-removal')
                self.unlink_original(RECEIPT,self.original_receipt,'receipt-removal')
                self.quiet('after');self.save('complete')
                result=deepcopy(self.previous);self.fresh(self.latest,self.sample_started);return result
        except Exception:
            self.failed=True
            raise NativeUIError('Peer input closure is unresolved; original journals and resources remain owned without replay') from None
