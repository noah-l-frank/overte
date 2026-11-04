"""Normal offline Send plus one durable passive restored-mixer quiet window.

There is no second Send journal. The existing draft WAL owns every input;
the additive window journal owns only phase/cut selection and passive recovery.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from adapters.native_feature_observation import exact, need, integer
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import validate as phase_validate
from ios.adapters import chat_archive_round
from ios.adapters.chat_draft_clock import operation
from ios.adapters.chat_send_operation import IOSChatSendOperation
from ios.adapters.chat_offline_send_receive import (echo_shape, offline_sources, original_local_echo,
                                                  original_no_replay, restored_sources)


def phase_original(value, run, ticket, previous=None):
    exact(value, {'ticket', 'afterEpochMs', 'verb', 'inputs', 'status'})
    status = value['status']; need(type(status) is dict)
    phase_validate(status, run=run, area='chat', request=status.get('requestId'),
                   epoch=status.get('capturedEpochMs'), previous=None if previous is None else previous['status'])
    need(status['active'] and status['activations'])
    last = status['activations'][-1]
    need(same(value, dict(ticket=last['ticket'], afterEpochMs=last['activatedEpochMs'],
                          **last['stimulus'], status=status))
         and value['ticket'] == ticket and value['verb'] == 'await-no-replay' and value['inputs'] == {})


class IOSChatOfflineSendOperation(IOSChatSendOperation):
    def __init__(self, receive, draft_owner, *, sleep=time.sleep):
        super().__init__(receive, draft_owner, sender_role='primary')
        need(callable(sleep)); self.sleep = sleep
        self.store = PrivateFeatureState(receive.primary_lock.path.with_name('ios-chat-offline-no-replay.json'))

    def offline_after(self, draft, send, before):
        last = draft.original(send['after'])['clockJoin']
        baseline = self.receive.original(before)['sample']
        for reference in self.receive.state['records'][before['index']:]:
            frame = self.receive.original(reference); join = frame['joins']['primary']
            if (last['hostAfterEpochMs'] <= join['hostBeforeEpochMs']
                    and last['hostAfterMonotonic'] <= join['hostBeforeMonotonic']):
                offline_sources(frame)
                primary = frame['sample']['primary']['source']['events']
                old = baseline['primary']['source']['events']
                need(same(primary[:len(old)], old)
                     and same(frame['sample']['peer']['source']['events'], baseline['peer']['source']['events'])
                     and same(frame['sample']['peerMessages'], baseline['peerMessages']))
                # Empty native cache cuts remain actual evidence, never a
                # local-acceptance substitute. Choose the FIRST append only;
                # it cannot be skipped to hide a false flag or foreign event.
                if len(primary) > len(old):
                    return deepcopy(reference)
        return None

    @operation
    def send(self, ticket):
        identifier(ticket); self.receive.bound(); self.receive.recover()
        with self.owner() as draft:
            draft.recover_observation(); send = self.retained(draft, ticket)
            before = None if send is None else self.before(draft, send)
        if before is None:
            before = self.receive.capture()
        offline_sources(self.receive.original(before))
        with self.owner() as draft:
            send = self.retained(draft, ticket)
            if send is None or send['after'] is None:
                draft.act(ticket, 'send', {})
                send = self.retained(draft, ticket)
            need(send is not None and send['after'] is not None)
            after = self.offline_after(draft, send, before)
        if after is None:
            after = self.receive.capture()
        with self.owner() as draft:
            return original_local_echo(draft, self.receive, ticket, before, after)

    def envelope(self, state):
        return dict(iosChatOfflineNoReplayVersion=1, runId=self.receive.run,
                    primaryBinding=deepcopy(self.receive.primary_binding),
                    peerBinding=deepcopy(self.receive.binding),
                    peerBindingRecord=deepcopy(self.receive.bound_record), payload=state)

    def decode(self, value, draft):
        exact(value, {'iosChatOfflineNoReplayVersion', 'runId', 'primaryBinding', 'peerBinding',
                      'peerBindingRecord', 'payload'})
        state = value['payload']
        need(type(state) is dict and same(value, self.envelope(state))
             and type(value['iosChatOfflineNoReplayVersion']) is int and value['iosChatOfflineNoReplayVersion'] == 1)
        exact(state, {'ticket', 'fixtureUrl', 'echo', 'startPhase', 'cursor', 'records', 'pending', 'complete'})
        identifier(state['ticket']); need(state['fixtureUrl'] == draft.fixture_url)
        phase_original(state['startPhase'], self.receive.run, state['ticket'])
        echo = state['echo']; echo_shape(echo)
        need(same(echo, original_local_echo(draft, self.receive, echo['ticket'],
                                                                 echo['receiveBefore'], echo['receiveAfter'])))
        need(integer(state['cursor'], echo['receiveAfter']['index'])
             and type(state['records']) is list and len(state['records']) <= 3
             and type(state['complete']) is bool)
        previous_phase = state['startPhase']
        previous_index = state['cursor'] - len(state['records'])
        need(previous_index >= echo['receiveAfter']['index'])
        for index, row in enumerate(state['records']):
            exact(row, {'reference', 'phaseBefore', 'phaseAfter'})
            reference = row['reference']
            need(reference in self.receive.state['records'] and reference['index'] == previous_index + 1)
            phase_original(row['phaseBefore'], self.receive.run, state['ticket'],
                           None if index == 0 and same(row['phaseBefore'], previous_phase) else previous_phase)
            phase_original(row['phaseAfter'], self.receive.run, state['ticket'], row['phaseBefore'])
            frame = self.receive.original(reference); restored_sources(frame)
            need(row['phaseBefore']['status']['capturedEpochMs'] <= frame['joins']['primary']['hostBeforeEpochMs']
                 and frame['joins']['peer']['hostAfterEpochMs'] <= row['phaseAfter']['status']['capturedEpochMs'])
            previous_phase = row['phaseAfter']; previous_index = reference['index']
        need(previous_index == state['cursor'] and state['cursor'] <= len(self.receive.state['records']))
        pending = state['pending']
        if pending is not None:
            exact(pending, {'phaseBefore', 'cursor'})
            need(pending['cursor'] == state['cursor'] and len(state['records']) < 3)
            phase_original(pending['phaseBefore'], self.receive.run, state['ticket'], previous_phase)
        if state['complete']:
            need(len(state['records']) == 3 and pending is None)
            original_no_replay(draft, self.receive, echo, [row['reference'] for row in state['records']])
        return deepcopy(state)

    def save(self, state, previous):
        chat_archive_round.mutation()
        self.receive.bound(); need(same(self.store.read(), previous))
        value = self.envelope(deepcopy(state)); self.store.write(value, previous)
        need(same(self.store.read(), value)); return value

    @operation
    def no_replay(self, ticket, offline_ticket):
        """The real await-no-replay phase authorizes reads and waits only.

        Fresh-cut intent is owned by existing receive.pending before any query.
        The saved cursor adopts its first actual saved cut after a lost return.
        It cannot rebase the quiet origin or dispatch any product/peer input.
        """
        identifier(ticket); identifier(offline_ticket)
        self.receive.bound(); self.receive.recover()
        previous = self.store.read()
        with self.owner() as draft:
            if previous is None:
                send = self.retained(draft, offline_ticket)
                need(send is not None and send['after'] is not None)
                before = self.before(draft, send); after = self.offline_after(draft, send, before)
                need(after is not None)
                echo = original_local_echo(draft, self.receive, offline_ticket, before, after)
                start = draft.phase.read(); phase_original(start, self.receive.run, ticket)
                state = dict(ticket=ticket, fixtureUrl=draft.fixture_url, echo=echo, startPhase=deepcopy(start),
                             cursor=len(self.receive.state['records']), records=[], pending=None, complete=False)
                previous = self.save(state, None)
            else:
                state = self.decode(previous, draft)
                need(state['ticket'] == ticket and state['echo']['ticket'] == offline_ticket)
            if state['complete']:
                return self.result(state, draft)
        while len(state['records']) < 3:
            if state['pending'] is None:
                if state['records'] and len(self.receive.state['records']) == state['cursor']:
                    chat_archive_round.mutation()
                    self.sleep(1.6)
                with self.owner() as draft:
                    prior_phase = state['records'][-1]['phaseAfter'] if state['records'] else state['startPhase']
                    before_phase = draft.phase.read()
                    phase_original(before_phase, self.receive.run, ticket, prior_phase)
                    state['pending'] = dict(phaseBefore=deepcopy(before_phase), cursor=state['cursor'])
                    self.decode(self.envelope(state), draft)
                    previous = self.save(state, previous)
            before_phase = state['pending']['phaseBefore']
            # A fresh phase read is a current ticket guard only. It never
            # replaces the actual saved before-phase of an uncertain capture.
            with self.owner() as draft:
                current_phase = draft.phase.read()
                phase_original(current_phase, self.receive.run, ticket, before_phase)
            if len(self.receive.state['records']) == state['cursor']:
                reference = self.receive.capture()
            else:
                reference = self.receive.state['records'][state['cursor']]
            need(reference['index'] == state['cursor'] + 1)
            with self.owner() as draft:
                after_phase = draft.phase.read()
                phase_original(after_phase, self.receive.run, ticket, current_phase)
                row = dict(reference=deepcopy(reference), phaseBefore=deepcopy(before_phase),
                           phaseAfter=deepcopy(after_phase))
                state['records'].append(row); state['cursor'] = reference['index']; state['pending'] = None
                self.decode(self.envelope(state), draft)
                previous = self.save(state, previous)
        with self.owner() as draft:
            result = self.result(state, draft)
            state['complete'] = True; self.decode(self.envelope(state), draft)
            self.save(state, previous); return result

    def result(self, state, draft):
        result = original_no_replay(draft, self.receive, state['echo'],
                                    [row['reference'] for row in state['records']])
        return dict(result, ticket=state['ticket'], historicalWindow=True)

    @classmethod
    def archived_no_replay(cls, draft, receive, store):
        need(draft.historical and receive.historical and type(store) is PrivateFeatureState
             and store.path == receive.primary_lock.path.with_name('ios-chat-offline-no-replay.json'))
        owner = object.__new__(cls); owner.receive, owner.store = receive, store
        value = store.read(); need(value is not None)
        state = owner.decode(value, draft); need(state['complete'])
        return owner.result(state, draft)
