"""Three seconds of new independent original Chat reads, without product input.

The journal is retained even on success. Only the whole-run owner can release it
after restoring the original profile, peer, services and actual resources.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
import uuid

from adapters.chat_journey.samples import ChatSamples
from adapters.native_feature_observation import integer, need, number
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import identifier

VERSION = 2


def original(samples):
    """Retain an original source reference, never an ACK or expected ledger."""
    need(samples.frames)
    frame = samples.frames[-1]
    p, q = frame['primary']['source'], frame['peer']['source']
    return dict(ticket=frame['ticket'], index=len(samples.frames) - 1,
        epochs=[frame[key]['capturedEpochMs'] for key in ('primary', 'peer', 'view', 'lifecycle')],
        queries=[frame[key].get('commandId', frame[key].get('requestId')) for key in ('primary', 'peer', 'view', 'lifecycle')],
        mixer=p['mixerSha256'], selfIds=[p['selfSha256'], q['selfSha256']],
        cacheIds=[[frame[key]['instance'], frame[key]['source']['openedEpochMs']] for key in ('primary', 'peer')],
        eventSequences=[p['eventSequence'], q['eventSequence']],
        ui=deepcopy(frame['view']['source']['ui']), lifecycle=deepcopy(frame['lifecycle']['lifecycle']),
        storage=deepcopy(frame['view']['source']['storage']))


def recovered(samples):
    """Both original native nodes must have witnessed an actual outage."""
    need(samples.frames and samples.frames[-1]['primary']['source']['mixerPresent'])
    absent = next((frame for frame in reversed(samples.frames[:-1])
        if not frame['primary']['source']['mixerPresent'] and not frame['peer']['source']['mixerPresent']), None)
    need(absent is not None)
    before = next((frame for frame in reversed(samples.frames[:samples.frames.index(absent)])
        if frame['primary']['source']['mixerPresent']), None)
    need(before is not None and before['primary']['source']['mixerSha256']
        != samples.frames[-1]['primary']['source']['mixerSha256'])


class ChatNoReplay:
    """One durable attempt from two separately owned actual source roles.

    No reconstruction restarts an interrupted timer. The retained journal and
    both original role transcripts make that uncertainty visible to cleanup.
    """
    def __init__(self, primary, actor, store, *, monotonic=time.monotonic, sleep=time.sleep):
        need(isinstance(primary, ChatSamples) and isinstance(actor, ChatSamples)
            and primary is not actor and primary.role == 'primary' and actor.role == 'actor'
            and primary.run == actor.run and primary.binding == actor.binding
            and primary.peer_binding == actor.peer_binding and primary.vr == actor.vr
            and primary.store.path != actor.store.path and store.path not in (primary.store.path, actor.store.path)
            and callable(monotonic) and callable(sleep) and store.read() is None)
        self.primary, self.actor, self.store = primary, actor, store
        self.monotonic, self.sleep = monotonic, sleep
        self.previous = None

    def write(self, value):
        need(self.store.read() == self.previous)
        self.store.write(value, self.previous)
        need(self.store.read() == value)
        self.previous = deepcopy(value)

    def wait(self, ticket, after_epoch):
        try:
            identifier(ticket); need(integer(after_epoch, 1) and self.previous is None)
            started = previous = self.monotonic(); need(number(started, 0, 1e15))
            base = dict(chatNoReplayVersion=VERSION, runId=self.primary.run, ticket=ticket,
                binding=self.primary.binding, peerBinding=self.primary.peer_binding,
                primaryTranscript=self.primary.store.path.name, actorTranscript=self.actor.store.path.name,
                phase='reading', elapsedMs=0, originals=None, samples=[])
            self.write(base)
            first = None; baseline = None; last_epochs = None
            for _attempt in range(202):
                sample_started = self.monotonic()
                need(number(sample_started, previous, started + 20) and sample_started - previous <= 1.5)
                self.write({**self.previous, 'phase': 'reading'})
                observations = [samples.read(uuid.uuid4().hex, after_epoch) for samples in (self.primary, self.actor)]
                refs = [original(samples) for samples in (self.primary, self.actor)]
                now = self.monotonic(); need(number(now, sample_started, started + 20) and now - sample_started <= 1.5)
                need(observations[0]['state'] == observations[1]['state'] and observations[0]['state']['mixerConnected'])
                stable = ('mixer', 'selfIds', 'cacheIds', 'eventSequences', 'ui', 'lifecycle', 'storage')
                need(all(refs[0][key] == refs[1][key] for key in stable))
                epochs = [epoch for ref in refs for epoch in ref['epochs']]
                if first is None:
                    for samples in (self.primary, self.actor): recovered(samples)
                    first = epochs; baseline = deepcopy(refs)
                    state = deepcopy(observations[0]['state'])
                    # Timing starts after both original baseline transactions.
                    quiet_started = now
                else:
                    need(all(current > old for current, old in zip(epochs, last_epochs)))
                    need(observations[0]['state'] == state)
                    for ref, original_ref in zip(refs, baseline):
                        need(all(ref[key] == original_ref[key] for key in stable))
                        need(not set(ref['queries']) & {query for sample in self.previous['samples']
                            for role in sample for query in role['queries']})
                last_epochs = epochs
                elapsed = now - quiet_started
                complete = elapsed >= 3 and all(end - begin >= 3000 for end, begin in zip(epochs, first))
                self.write({**self.previous, 'phase': 'complete' if complete else 'waiting',
                    'elapsedMs': int(elapsed * 1000), 'originals': baseline,
                    'samples': self.previous['samples'] + [[{key:ref[key] for key in ('ticket','index','epochs','queries')} for ref in refs]]})
                if complete: return deepcopy(self.previous)
                need(now - started < 20)
                previous = now; self.sleep(.1)
            need(False)
        except Exception:
            raise NativeUIError('Chat no-replay window failed; original ownership journal is retained') from None
