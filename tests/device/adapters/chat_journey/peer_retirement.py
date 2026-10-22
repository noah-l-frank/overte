"""Fresh restricted transport over fully consumed original peer transactions."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib

from adapters.chat_actor_files import ChatActorFiles,RESULT,observation_envelope,stamp
from adapters.chat_peer_input import COMMAND,RECEIPT
from adapters.chat_journey.peer_input_close import ChatPeerInputClose
from adapters.native_chat_observation import command,validate
from adapters.native_feature_observation import need
from adapters.script_journey.history import same

VERSION=1


class ChatPeerRetirementFiles(ChatActorFiles):
    """Keep the original action writer/fence intact; never reopen peer input.

    Construction reads only an already consumed original native transaction.
    It cannot recover a pending/unprocessed command or adopt a lost result.
    A new callback owner can bind only to this new transport instance.
    """
    def __init__(self,original,input_close):
        need(type(original) is ChatActorFiles and type(input_close) is ChatPeerInputClose
            and input_close.files is original and input_close.input.files is original
            and getattr(original,'_chat_input_close_owner',None) is input_close
            and getattr(original,'_chat_retirement_transport',None) is None)
        self.original,self.input_close,self.lock=original,input_close,input_close.lock
        self.lock.assert_held();self.authority()
        before=original._owned()
        need(before['pending'] is None and not before['closing'] and not before['removed']
            and before['runId']==input_close.input.run and before['request'] is not None
            and before['request']['operation']=='inspect' and before['result'] is not None
            and before['result']['commandId']==before['request']['commandId'])
        # This is a historical handoff of an already consumed transaction,
        # never a fresh native sample. Verify its exact previously accepted
        # bytes/stamps and actual original held FD without retiming them.
        raw,info=original._read(RESULT,131072);envelope=observation_envelope(raw,info);packet=envelope['native']
        original._check_command(before)
        need(stamp(info)==before['result']['stamp'] and hashlib.sha256(raw).hexdigest()==before['result']['sha256']
            and envelope['commandNode']=={key:before['commandStamp'][key] for key in ('device','inode')}
            and original.released({key:stamp(info)[key] for key in ('device','inode')}) is False)
        validate(packet,before['request'],original.pid,packet.get('capturedEpochMs'))
        need(same(original.store.read(),before) and packet['commandId']==before['request']['commandId']
            and packet['runId']==before['runId'] and packet['instance']==original.source['instance']
            and packet['capturedEpochMs']>=original.source['configuredEpochMs'])
        self.run_id=before['runId'];self.initial=deepcopy(before)
        super().__init__(original.path,original.store,original.binding,original.source['scriptSha256'],
            original.guard,original.released,component_only=original.component_only,clock_ms=original.clock_ms,
            monotonic=original.monotonic,sleep=original.sleep,require_original_fd=True)
        try:
            need(same(self.store.read(),before) and self.source==original.source and self.root==original.root
                and self.source_stamp==original.source_stamp and self.source_sha==original.source_sha)
            self.authority();self._chat_input_close_owner=input_close
            original._chat_retirement_transport=self
        except BaseException:self.detach();raise

    def authority(self):
        self.lock.assert_held();closed=self.input_close
        need(not closed.failed and closed.previous is not None and closed.previous['phase']=='complete'
            and same(closed.store.read(),closed.previous))
        closed.chunks.verify();closed.authority()
        need(not self.original._exists(COMMAND) and not self.original._exists(RECEIPT)
            and self.original.released(node_from_stamp(closed.original_receipt)) is True)

    def send(self,request):
        self.lock.assert_held();command(request)
        need(request['runId']==self.run_id and request['operation'] in ('inspect','retire'))
        self.authority();super().send(request)

    def read(self):
        self.lock.assert_held();self.authority();return super().read()

    def close(self,*,retain=True):
        self.lock.assert_held();need(retain is True);self.authority()
        return super().close(retain=True)


def node_from_stamp(value):return {key:value[key] for key in ('device','inode')}
