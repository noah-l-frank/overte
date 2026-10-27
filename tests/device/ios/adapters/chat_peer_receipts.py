"""Pure original dependencies for the primary owner's incoming Chat read.

The existing independently owned sender, receiver cuts and immutable files are
reopened. This context owns no input, query, transport or additional journal.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same
from ios.adapters.chat_receive_sources import IOSChatReceiveSources
from ios.adapters.chat_send_receive import original_sent
from ios.adapters.graphics_history import follow_native

VERSION=1


class IOSChatPeerReceipts:
    def __init__(self,receive,sender_owner):
        need(isinstance(receive,IOSChatReceiveSources) and callable(sender_owner))
        self.receive,self.sender_owner=receive,sender_owner
    def bound(self,primary):
        self.receive.bound();primary.lock.assert_held()
        need(same(primary.binding,self.receive.primary_binding) and primary.run==self.receive.run
            and str(primary.root)==self.receive.bound_record['primaryArtifactRoot']['path']
            and primary.lock.path==self.receive.primary_lock.path)
    @contextmanager
    def sender(self):
        from ios.adapters.chat_draft_owner import IOSChatDraftOwner
        self.receive.bound()
        with self.sender_owner() as sender:
            need(isinstance(sender,IOSChatDraftOwner) and sender.historical and sender.peer_actor and sender.version==5
                and same(sender.binding,self.receive.binding) and sender.run==self.receive.run
                and str(sender.root)==self.receive.bound_record['peerArtifactRoot']['path']
                and sender.lock.path==self.receive.lock.path)
            sender.bound();yield sender;sender.bound()
        self.receive.bound()
    def link(self,fact):
        need(type(fact) is dict)
        with self.sender() as sender:
            actual=original_sent(sender,self.receive,fact['ticket'],fact['receiveBefore'],fact['receiveAfter'],sender_role='peer')
        need(same(fact,actual))
        return self.pack(actual)
    def pack(self,actual):
        return dict(iosChatPeerReceiptLinkVersion=VERSION,runId=self.receive.run,ticket=actual['ticket'],
            peerBindingRecord=deepcopy(actual['peerBindingRecord']),
            **{key:deepcopy(actual[key]) for key in ('receiveBefore','receiveAfter','sendBefore','sendAfter')})
    def read(self,link):
        exact(link,{'iosChatPeerReceiptLinkVersion','runId','ticket','peerBindingRecord',
            'receiveBefore','receiveAfter','sendBefore','sendAfter'})
        need(type(link['iosChatPeerReceiptLinkVersion']) is int and link['iosChatPeerReceiptLinkVersion']==VERSION
            and link['runId']==self.receive.run and same(link['peerBindingRecord'],self.receive.bound_record))
        with self.sender() as sender:
            actual=original_sent(sender,self.receive,link['ticket'],link['receiveBefore'],link['receiveAfter'],sender_role='peer')
        need(same(link,self.pack(actual)))
        return actual,self.receive.original(link['receiveBefore']),self.receive.original(link['receiveAfter'])
    def before(self,primary,frame,link):
        self.bound(primary);actual,left,right=self.read(link)
        follow_native(frame['clockJoin']['nativeAfter'],left['joins']['primary']['nativeBefore'])
        need(frame['clockJoin']['hostAfterEpochMs']<=left['joins']['primary']['hostBeforeEpochMs']
            and frame['clockJoin']['hostAfterMonotonic']<=left['joins']['primary']['hostBeforeMonotonic'])
        return actual,left,right
    def effect(self,primary,op,frame):
        need(op['verb']=='peer-receive' and op['inputs']=={} and op['intents']==[] and op['peerReceipt'] is not None)
        before=primary.original(op['before']);actual,left,right=self.before(primary,before,op['peerReceipt'])
        need(actual['ticket']==op['ticket'] and same(frame['peerReceipt'],op['peerReceipt']))
        follow_native(right['joins']['primary']['nativeAfter'],frame['clockJoin']['nativeBefore'])
        need(right['joins']['peer']['hostAfterEpochMs']<=frame['clockJoin']['hostBeforeEpochMs']
            and right['joins']['peer']['hostAfterMonotonic']<=frame['clockJoin']['hostBeforeMonotonic'])
        old,new=before['originals']['view']['source']['storage'],frame['originals']['view']['source']['storage']
        need(len(new['events'])==len(old['events'])+1 and same(new['events'][:-1],old['events']))
        event=actual['events']['primary'];message=new['events'][-1]
        stimulus=dict(verb='peer-send',inputs=dict(text=event['text'],channel=event['channel']))
        need(all(phase['activations'][-1]['ticket']==op['ticket'] and same(phase['activations'][-1]['stimulus'],stimulus)
            for phase in (frame['phaseBefore'],frame['phaseAfter'])))
        need(message['text']==event['text'] and message['channel']==event['channel']
            and event['capturedEpochMs']<=message['timestamp']<=frame['originals']['view']['capturedEpochMs'])
        prior,current=primary.local(before),primary.local(frame)
        need(all(same(prior[key],current[key]) for key in ('open','channel','draft','focused','keyboard')))
        return current
