"""Normal fixture peer Send joined to two independent original receive reads."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
import uuid

from adapters.chat_journey.samples import ChatSamples
from adapters.chat_peer_input import ChatPeerInput
from adapters.native_feature_observation import integer, need, number
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import context

VERSION = 1


class ChatPeerSend:
    """Own one actual peer and independent primary/actor reception sources.

    Input consumption and actual reception remain distinct durable phases.
    Receipt loss or source failure cannot trigger another Send.
    """
    def __init__(self, input_owner, primary, actor, store, *, monotonic=time.monotonic, sleep=time.sleep):
        need(isinstance(input_owner, ChatPeerInput) and isinstance(primary, ChatSamples)
            and isinstance(actor, ChatSamples) and primary is not actor
            and primary.role == 'primary' and actor.role == 'actor'
            and primary.run == actor.run == input_owner.run
            and primary.binding == actor.binding and primary.peer_binding == actor.peer_binding == input_owner.files.binding
            and primary.store.path != actor.store.path and store.path not in
                (primary.store.path, actor.store.path, input_owner.store.path, input_owner.files.store.path)
            and callable(monotonic) and callable(sleep) and store.read() is None)
        self.input, self.roles, self.store = input_owner, (primary, actor), store
        self.monotonic, self.sleep = monotonic, sleep; self.previous = None

    def write(self, value):
        need(self.store.read() == self.previous)
        self.store.write(value, self.previous); need(self.store.read() == value)
        self.previous = deepcopy(value)

    def pair(self, after_epoch):
        before = self.monotonic(); need(number(before, 0, 1e15))
        observed = [role.read(uuid.uuid4().hex, after_epoch) for role in self.roles]
        after = self.monotonic(); need(number(after, before, before + 1.5))
        self.input.files._check_source()
        for role in self.roles:
            peer = role.frames[-1]['peer']
            need(peer['instance'] == self.input.files.source['instance'] and peer['processId'] == self.input.files.pid)
        need(observed[0]['state'] == observed[1]['state'])
        return observed

    def references(self):
        return [dict(index=len(role.frames)-1, ticket=role.frames[-1]['ticket'],
            queries=[role.frames[-1][key].get('commandId', role.frames[-1][key].get('requestId'))
                for key in ('primary', 'peer', 'view', 'lifecycle')]) for role in self.roles]

    def send(self, channel, text_key, after_epoch):
        try:
            need(channel in ('local', 'domain') and text_key in ('reply', 'hidden') and integer(after_epoch, 1))
            need(self.previous is None or self.previous['attempts'][-1]['phase'] == 'received')
            attempts = [] if self.previous is None else self.previous['attempts']
            need(not any(row['channel'] == channel and row['textKey'] == text_key for row in attempts))
            attempt = dict(channel=channel, textKey=text_key, phase='sampling', before=None, after=None)
            base = dict(chatPeerSendVersion=VERSION, runId=self.input.run, binding=self.roles[0].binding,
                peerBinding=self.input.files.binding, inputJournal=self.input.store.path.name, attempts=attempts+[attempt])
            self.write(base)
            before = self.pair(after_epoch)
            starts = [deepcopy(role.frames[-1]) for role in self.roles]
            for role in self.roles:
                source = role.frames[-1]['primary']['source']
                need(source['mixerPresent'] and role.frames[-1]['peer']['source']['mixerPresent'])
            attempt.update(phase='issuing', before=self.references())
            self.write({**base, 'attempts': attempts+[deepcopy(attempt)]})
            self.input.issue('send', channel=channel, textKey=text_key)
            attempt['phase'] = 'observing'; self.write({**base, 'attempts': attempts+[deepcopy(attempt)]})
            started = previous = self.monotonic(); need(number(started, 0, 1e15))
            for _index in range(202):
                observed = self.pair(after_epoch); delivered = []
                for role, initial, state in zip(self.roles, starts, observed):
                    frame = role.frames[-1]; p = frame['primary']['source']; q = frame['peer']['source']
                    need(p['mixerPresent'] and q['mixerPresent']
                        and p['mixerSha256'] == initial['primary']['source']['mixerSha256'])
                    delta = p['events'][len(initial['primary']['source']['events']):]
                    need(len(delta) <= 1)
                    if delta:
                        event = delta[0]
                        need(event['senderSha256'] == q['selfSha256'] and not event['localOnly']
                            and event['channel'] == channel and event['text'] == context(self.input.run)[text_key])
                        stored = frame['view']['source']['storage']['events']
                        old = initial['view']['source']['storage']['events']
                        # Ordinary near Local/Domain must actually be accepted,
                        # reconstructed and shown through the original sources.
                        need(stored[:len(old)] == old and len(stored) <= len(old)+1)
                        delivered.append(len(stored) == len(old)+1 and stored[-1]['channel'] == channel
                            and stored[-1]['text'] == event['text'])
                    else: delivered.append(False)
                now = self.monotonic(); need(number(now, previous, started+20)); previous = now
                if all(delivered):
                    attempt.update(phase='received', after=self.references())
                    self.write({**base, 'attempts': attempts+[deepcopy(attempt)]}); return deepcopy(observed)
                self.sleep(.1)
            need(False)
        except Exception:
            raise NativeUIError('Chat peer Send lacks independent reception; original intent remains without replay') from None
