"""Pure original dependencies for the primary owner's incoming Chat read.

The existing independently owned sender, receiver cuts and immutable files are
reopened. This context owns no input, query, transport or additional journal.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from ios.adapters import chat_archive_round
from contextlib import contextmanager
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same
from ios.adapters.chat_receive_sources import IOSChatReceiveSources
from ios.adapters.chat_receive_runtime import binding_record
from ios.adapters.chat_send_receive import original_sent
from ios.adapters.graphics_history import follow_native

VERSION=1


class IOSChatPeerReceipts:
    def __init__(self,receive,sender_owner,*,recipient_role='primary',bounded_sender=False):
        need(isinstance(receive,IOSChatReceiveSources) and callable(sender_owner))
        need(type(recipient_role) is str and recipient_role in ('primary','peer') and type(bounded_sender) is bool
            and (recipient_role=='primary' or bounded_sender))
        self.recipient_role=recipient_role;self.sender_role='peer' if recipient_role=='primary' else 'primary'
        self.bounded_sender=bounded_sender;self.version=2 if bounded_sender else VERSION
        self.receive,self.sender_owner=receive,sender_owner
    def bound(self,primary):
        if primary.historical:self.history_bound()
        else:self.receive.bound()
        primary.lock.assert_held()
        binding=self.receive.primary_binding if self.recipient_role=='primary' else self.receive.binding
        lock=self.receive.primary_lock if self.recipient_role=='primary' else self.receive.lock
        need(same(primary.binding,binding) and primary.run==self.receive.run
            and str(primary.root)==self.receive.bound_record[self.recipient_role+'ArtifactRoot']['path']
            and primary.lock.path==lock.path)
    def history_bound(self):
        source=self.receive;source.lock.assert_held();source.primary_lock.assert_held()
        need(same(source.store.read(),source.previous))
        binding_record(source.bound_record,source.primary_binding,source.binding,source.run,
            source.bound_record['primaryArtifactRoot']['path'],source.root)
    def matches(self,source):
        self.history_bound()
        return (isinstance(source,IOSChatReceiveSources) and source.store.path==self.receive.store.path
            and source.lock is self.receive.lock and source.primary_lock is self.receive.primary_lock
            and same(source.previous,self.receive.previous) and same(source.state,self.receive.state)
            and same(source.bound_record,self.receive.bound_record))
    def original_source(self):
        self.history_bound();source=self.receive
        if source.historical:return source
        original=IOSChatReceiveSources.archive(source.store,source.primary_binding,source.binding,source.run,
            source.bound_record['primaryArtifactRoot']['path'],source.root,source.bound_record,source.primary_lock,source.lock)
        need(self.matches(original));return original
    @contextmanager
    def sender(self,ticket,through):
        from ios.adapters.chat_draft_owner import IOSChatDraftOwner
        self.history_bound()
        factory=self.sender_owner(ticket,through) if self.bounded_sender else self.sender_owner()
        binding=self.receive.binding if self.sender_role=='peer' else self.receive.primary_binding
        lock=self.receive.lock if self.sender_role=='peer' else self.receive.primary_lock
        with factory as sender:
            need(isinstance(sender,IOSChatDraftOwner) and sender.historical
                and sender.peer_actor==(self.sender_role=='peer')
                and sender.version in ((5,7) if self.sender_role=='peer' else (4,6))
                and same(sender.binding,binding) and sender.run==self.receive.run
                and str(sender.root)==self.receive.bound_record[self.sender_role+'ArtifactRoot']['path']
                and sender.lock.path==lock.path)
            if self.bounded_sender:need(sender.subgraph_only and sender.frontier_ticket==ticket and same(sender.frontier,through))
            else:need(sender.version==5 and not sender.subgraph_only)
            sender.bound();yield sender;sender.bound()
        self.history_bound()
    def link(self,fact):
        need(type(fact) is dict)
        source=self.original_source()
        with self.sender(fact['ticket'],fact['sendAfter']) as sender:
            actual=original_sent(sender,source,fact['ticket'],fact['receiveBefore'],fact['receiveAfter'],sender_role=self.sender_role)
        need(same(fact,actual))
        return self.pack(actual)
    def pack(self,actual):
        value=dict(iosChatPeerReceiptLinkVersion=self.version,runId=self.receive.run,ticket=actual['ticket'],
            peerBindingRecord=deepcopy(actual['peerBindingRecord']),
            **{key:deepcopy(actual[key]) for key in ('receiveBefore','receiveAfter','sendBefore','sendAfter')})
        if self.version==2:value['recipientRole']=self.recipient_role
        return value
    def shape(self,link):
        exact(link,{'iosChatPeerReceiptLinkVersion','runId','ticket','peerBindingRecord',
            'receiveBefore','receiveAfter','sendBefore','sendAfter'}|({'recipientRole'} if self.version==2 else set()))
        need(type(link['iosChatPeerReceiptLinkVersion']) is int and link['iosChatPeerReceiptLinkVersion']==self.version
            and link['runId']==self.receive.run and same(link['peerBindingRecord'],self.receive.bound_record))
        if self.version==2:need(link['recipientRole']==self.recipient_role)
        from feature_journeys.contract import identifier
        identifier(link['ticket'])
        for key in ('receiveBefore','receiveAfter'):self.receive.frames.expand(link[key])
        # Compact Draft/Receive references share this original envelope shape.
        # Expanding proves structure, not membership or any sender outcome.
        for key in ('sendBefore','sendAfter'):self.receive.frames.expand(link[key])
        need(link['receiveBefore']['index']<link['receiveAfter']['index']
            and link['sendBefore']['index']<link['sendAfter']['index'])
        return link
    def read(self,link):
        self.shape(link)
        source=self.original_source()
        with self.sender(link['ticket'],link['sendAfter']) as sender:
            actual=original_sent(sender,source,link['ticket'],link['receiveBefore'],link['receiveAfter'],sender_role=self.sender_role)
        need(same(link,self.pack(actual)))
        return actual,source.original(link['receiveBefore']),source.original(link['receiveAfter'])
    def before(self,primary,frame,link):
        self.bound(primary);actual,left,right=self.read(link)
        follow_native(frame['clockJoin']['nativeAfter'],left['joins'][self.recipient_role]['nativeBefore'])
        need(frame['clockJoin']['hostAfterEpochMs']<=left['joins']['primary']['hostBeforeEpochMs']
            and frame['clockJoin']['hostAfterMonotonic']<=left['joins']['primary']['hostBeforeMonotonic'])
        return actual,left,right
    def effect(self,primary,op,frame):
        need(op['verb']=='peer-receive' and op['inputs']=={} and op['intents']==[] and op['peerReceipt'] is not None)
        before=primary.original(op['before']);actual,left,right=self.before(primary,before,op['peerReceipt'])
        need(actual['ticket']==op['ticket'] and same(frame['peerReceipt'],op['peerReceipt']))
        follow_native(right['joins'][self.recipient_role]['nativeAfter'],frame['clockJoin']['nativeBefore'])
        need(right['joins']['peer']['hostAfterEpochMs']<=frame['clockJoin']['hostBeforeEpochMs']
            and right['joins']['peer']['hostAfterMonotonic']<=frame['clockJoin']['hostBeforeMonotonic'])
        old,new=before['originals']['view']['source']['storage'],frame['originals']['view']['source']['storage']
        need(len(new['events'])==len(old['events'])+1 and same(new['events'][:-1],old['events']))
        event=actual['events'][self.recipient_role];message=new['events'][-1]
        stimulus=(dict(verb='peer-send',inputs=dict(text=event['text'],channel=event['channel']))
            if self.sender_role=='peer' else dict(verb='send',inputs={}))
        need(all(phase['activations'][-1]['ticket']==op['ticket'] and same(phase['activations'][-1]['stimulus'],stimulus)
            for phase in (frame['phaseBefore'],frame['phaseAfter'])))
        need(message['text']==event['text'] and message['channel']==event['channel']
            and event['capturedEpochMs']<=message['timestamp']<=frame['originals']['view']['capturedEpochMs'])
        prior,current=primary.local(before),primary.local(frame)
        need(all(same(prior[key],current[key]) for key in ('open','channel','draft','focused','keyboard')))
        return current


chat_archive_round.register(__name__,globals())
