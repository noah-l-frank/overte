"""Independently acquired native peer ledger; never primary UI or send proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import time
from adapters.native_feature_observation import exact,integer,need,number
from adapters.native_chat_observation import NativeChatObservation,OwnedChatCapture,HEX,SHA
from adapters.normal_feature_state import context
from adapters.normal_ui import NativeUIError

VERSION=1


def source_identity(value):
    return dict(instance=value['instance'],processId=value['processId'],selfSha256=value['source']['selfSha256'],
                openedEpochMs=value['source']['openedEpochMs'])


def identity_shape(value):
    exact(value,{'instance','processId','selfSha256','openedEpochMs'})
    need(type(value['instance']) is str and re.fullmatch(HEX,value['instance']) and integer(value['processId'],1)
         and type(value['selfSha256']) is str and re.fullmatch(SHA,value['selfSha256']) and integer(value['openedEpochMs'],1))
    return value


def binding_pid(value):
    match=re.fullmatch(r'([1-9][0-9]{0,9})(?::[!-~]{1,150})?',value['processIdentity'])
    need(match is not None);return int(match[1])


class IndependentChatReceiver:
    """Runs in the separate actor with its own primary/peer transports.

    primary must independently inspect the real primary cache, never consume a
    primary-adapter JSON sample. peer owns its separate native receive cache.
    The caller still needs actual peer process/code association, normal primary
    UI/storage reads, send/mixer actors and a private publisher transport.
    """
    def __init__(self,primary,primary_binding,peer,store,*,component_only=False,monotonic=time.monotonic):
        need(isinstance(primary,NativeChatObservation) and isinstance(peer,OwnedChatCapture)
             and type(component_only) is bool and peer.owner.component_only==component_only and callable(monotonic))
        self.primary,self.peer,self.store,self.monotonic=primary,peer,store,monotonic
        self.binding=deepcopy(context(primary_binding,component_only=component_only))
        self.component_only=component_only;self.last_clock=None
        need(primary.pid==binding_pid(self.binding) and peer.reader.pid==binding_pid(peer.owner.binding)
             and self.binding['targetFingerprint']!=peer.owner.binding['targetFingerprint'])

    def owned(self):
        value=self.store.read()
        if value is None:return None
        exact(value,{'receiverVersion','runId','primaryBinding','peerBinding','primary','peer','mixerSha256','primaryAbsent','peerAbsent'})
        need(type(value['receiverVersion']) is int and value['receiverVersion']==VERSION and value['runId']==self.peer.run
             and context(value['primaryBinding'],component_only=self.component_only)==self.binding
             and context(value['peerBinding'],component_only=self.component_only)==self.peer.owner.binding
             and type(value['mixerSha256']) is str and re.fullmatch(SHA,value['mixerSha256'])
             and all(type(value[k]) is bool for k in ('primaryAbsent','peerAbsent')))
        identity_shape(value['primary']);identity_shape(value['peer'])
        need(value['primary']['processId']==binding_pid(value['primaryBinding']) and value['peer']['processId']==binding_pid(value['peerBinding']))
        need(value['primary']['instance']!=value['peer']['instance'] and value['primary']['selfSha256']!=value['peer']['selfSha256'])
        return value

    def now(self):
        value=self.monotonic();need(number(value,0,1e15) and (self.last_clock is None or value>=self.last_clock))
        self.last_clock=value;return value

    def sample(self):
        try:
            before=self.now();previous=self.owned()
            # Query fresh native originals on the actor's own transport. A
            # primary adapter response is not admitted as this inspect path.
            primary=self.primary.perform(self.peer.run,'inspect')
            need(primary['source']['scopePresent'] and not primary['source']['retired'] and primary['source']['droppedEvents']==0)
            peer=self.peer.observe()
            need(self.now()-before<=1.5 and self.primary.guard() is not False and self.peer.reader.guard() is not False)
            p,q=primary['source'],peer['source'];p_id,q_id=source_identity(primary),source_identity(peer)
            need(p_id['instance']!=q_id['instance'] and p_id['selfSha256']!=q_id['selfSha256'])
            if previous is None:
                need(p['mixerPresent'] and q['mixerPresent'] and p['mixerSha256']==q['mixerSha256'])
                value=dict(receiverVersion=VERSION,runId=self.peer.run,primaryBinding=self.binding,
                    peerBinding=deepcopy(self.peer.owner.binding),primary=p_id,peer=q_id,
                    mixerSha256=p['mixerSha256'],primaryAbsent=False,peerAbsent=False)
            else:
                need(previous['primary']==p_id and previous['peer']==q_id)
                value=deepcopy(previous)
                value['primaryAbsent'] |= not p['mixerPresent'];value['peerAbsent'] |= not q['mixerPresent']
                if p['mixerPresent'] and q['mixerPresent']:
                    need(p['mixerSha256']==q['mixerSha256'])
                    if p['mixerSha256']!=value['mixerSha256']:
                        need(value['primaryAbsent'] and value['peerAbsent'])
                        value.update(mixerSha256=p['mixerSha256'],primaryAbsent=False,peerAbsent=False)
            self.store.write(value,previous)
            # Both ordinary Local and Domain sends travel through MessagesMixer.
            # Keep original global reception order and multiplicity, filtering
            # self echoes, foreign senders and local-only native emissions.
            received=[event['text'] for event in q['events'] if event['senderSha256']==p['selfSha256'] and not event['localOnly']]
            return dict(receiverVersion=VERSION,runId=self.peer.run,peerMessages=received,
                primary=deepcopy(primary),peer=deepcopy(peer))
        except Exception:raise NativeUIError('Independent Chat receive binding or original evidence is unavailable') from None

    def retire(self):
        # Retire only the actor's cache. The primary adapter remains the owner
        # of its cache/UI. Failed peer retirement leaves both private journals.
        previous=self.owned();peer_owned=self.peer.owner.owned()
        self.peer.retire()
        if previous is not None or peer_owned is not None:
            original=self.peer.reader.perform(self.peer.run,'inspect');source=original['source']
            need(source['retired'] and not source['scopePresent'] and source['events']==[] and source['eventSequence']==0)
            if previous is not None:
                need(all(source_identity(original)[k]==previous['peer'][k] for k in ('instance','processId','selfSha256')))
        need(self.primary.guard() is not False and self.peer.reader.guard() is not False)
        self.store.discard(previous)
