"""Separate historical no-mixer self echo; never an online delivery receipt."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact, need
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from ios.adapters.chat_draft_owner import IOSChatDraftOwner
from ios.adapters.chat_receive_sources import IOSChatReceiveSources
from ios.adapters.graphics_history import follow_native


def echo_shape(value):
    exact(value, {'iosChatLocalEchoSendReceiveDerivedVersion', 'runId', 'ticket', 'sourceProfile',
                  'primaryBinding', 'peerBindingRecord', 'receiveBefore', 'receiveAfter',
                  'sendBefore', 'sendAfter', 'localEcho', 'peerEventsUnchanged',
                  'remoteDeliveryEstablished', 'domainContinuityEstablished'})
    need(type(value['iosChatLocalEchoSendReceiveDerivedVersion']) is int
         and value['iosChatLocalEchoSendReceiveDerivedVersion'] == 1)


def offline_sources(frame):
    for role in ('primary', 'peer'):
        source = frame['sample'][role]['source']
        need(source['scopePresent'] and not source['retired']
             and not source['mixerPresent'] and source['mixerSha256'] == '')


def original_local_echo(draft, receive, ticket, before, after):
    """Reopen actual normal Send and both independent original cache cuts.

    The old connected original_sent remains literal. Absence and localOnly
    do not identify a Domain or establish a complete common Chat state.
    """
    identifier(ticket)
    need(isinstance(draft, IOSChatDraftOwner) and isinstance(receive, IOSChatReceiveSources)
         and draft.source_bound and not draft.peer_actor and draft.version in (4, 6, 9))
    draft.bound(); receive.bound()
    need(draft.previous is not None and receive.previous is not None
         and same(draft.decode(draft.previous), draft.state)
         and same(receive.decode(receive.previous), receive.state)
         and draft.state['pending'] is None and draft.state['observation'] is None
         and receive.state['pending'] is None
         and same(draft.binding, receive.primary_binding) and draft.run == receive.run
         and str(draft.root) == receive.bound_record['primaryArtifactRoot']['path']
         and draft.lock.path == receive.primary_lock.path)
    if draft.version in (6, 9):
        need(draft.peer_receipts.matches(receive))
    sends = [op for op in draft.state['operations'] if op['ticket'] == ticket and op['verb'] == 'send']
    need(len(sends) == 1 and not any(op['ticket'] == ticket for op in draft.state['failures']))
    send = sends[0]
    need(len(send['intents']) == 1 and send['after'] is not None
         and before in receive.state['records'] and after in receive.state['records']
         and before['index'] < after['index'])
    left, right = receive.original(before), receive.original(after)
    first, last = draft.original(send['before']), draft.original(send['after'])
    draft.effect(send, last)
    a, b = left['joins']['peer'], first['clockJoin']
    c, d = last['clockJoin'], right['joins']['primary']
    need(a['hostAfterEpochMs'] <= b['hostBeforeEpochMs']
         and a['hostAfterMonotonic'] <= b['hostBeforeMonotonic']
         and c['hostAfterEpochMs'] <= d['hostBeforeEpochMs']
         and c['hostAfterMonotonic'] <= d['hostBeforeMonotonic'])
    follow_native(left['joins']['primary']['nativeAfter'], b['nativeBefore'])
    follow_native(c['nativeAfter'], right['joins']['primary']['nativeBefore'])
    for reference in draft.state['records']:
        frame = draft.original(reference); join = frame['clockJoin']
        if join['hostAfterEpochMs'] >= a['hostAfterEpochMs'] and join['hostBeforeEpochMs'] <= d['hostBeforeEpochMs']:
            need(frame['ticket'] == ticket and frame['verb'] == 'send')
    old, new = left['sample']['primary']['source'], right['sample']['primary']['source']
    before_peer, after_peer = left['sample']['peer']['source'], right['sample']['peer']['source']
    offline_sources(left); offline_sources(right)
    need(same(new['events'][:-1], old['events']) and len(new['events']) == len(old['events']) + 1
         and same(after_peer['events'], before_peer['events'])
         and same(left['sample']['peerMessages'], right['sample']['peerMessages']))
    event = new['events'][-1]
    prior = draft.local(first)
    stored = last['originals']['view']['source']['storage']['events'][-1]
    need(event['localOnly'] is True and event['senderSha256'] == old['selfSha256']
         and event['text'] == stored['text'] == prior['draft']
         and event['channel'] == stored['channel'] == prior['channel']
         and b['nativeAfter']['capturedEpochMs'] <= event['capturedEpochMs'] <= c['nativeAfter']['capturedEpochMs'])
    for reference in receive.state['records'][before['index'] - 1:after['index']]:
        frame = receive.original(reference); offline_sources(frame)
        need(same(frame['sample']['peer']['source']['events'], before_peer['events'])
             and same(frame['sample']['peerMessages'], left['sample']['peerMessages']))
        for role in ('primary', 'peer'):
            x, y = left['sample'][role], frame['sample'][role]
            need(x['instance'] == y['instance'] and x['processId'] == y['processId']
                 and x['source']['selfSha256'] == y['source']['selfSha256']
                 and x['source']['openedEpochMs'] == y['source']['openedEpochMs']
                 and same(left['joins'][role]['nativeBefore']['lifecycle'], frame['joins'][role]['nativeAfter']['lifecycle']))
    draft.bound(); receive.bound()
    return dict(iosChatLocalEchoSendReceiveDerivedVersion=1, runId=draft.run, ticket=ticket,
                sourceProfile=draft.version, primaryBinding=deepcopy(draft.binding),
                peerBindingRecord=deepcopy(receive.bound_record), receiveBefore=deepcopy(before),
                receiveAfter=deepcopy(after), sendBefore=deepcopy(send['before']), sendAfter=deepcopy(send['after']),
                localEcho=deepcopy(event), peerEventsUnchanged=True,
                remoteDeliveryEstablished=False, domainContinuityEstablished=False)


def restored_sources(frame):
    values = [frame['sample'][role]['source'] for role in ('primary', 'peer')]
    need(all(source['scopePresent'] and not source['retired'] and source['mixerPresent'] for source in values)
         and values[0]['mixerSha256'] == values[1]['mixerSha256'] != '')
    return values[0]['mixerSha256']


def original_no_replay(draft, receive, echo, references):
    """Three actual restored-mixer cuts; no new clock, query or UI fact."""
    echo_shape(echo)
    need(same(echo, original_local_echo(draft, receive, echo['ticket'], echo['receiveBefore'], echo['receiveAfter'])))
    need(isinstance(receive, IOSChatReceiveSources) and type(references) is list and len(references) == 3)
    need([ref['index'] for ref in references] == sorted({ref['index'] for ref in references})
         and all(ref in receive.state['records'] for ref in references)
         and references[0]['index'] > echo['receiveAfter']['index'])
    offline = receive.original(echo['receiveAfter'])
    frames = [receive.original(ref) for ref in references]
    mixer = restored_sources(frames[0])
    for reference in receive.state['records'][references[0]['index'] - 1:references[-1]['index']]:
        frame = receive.original(reference)
        need(restored_sources(frame) == mixer
             and same(frame['sample']['peerMessages'], offline['sample']['peerMessages']))
        for role in ('primary', 'peer'):
            left, right = offline['sample'][role], frame['sample'][role]
            need(left['instance'] == right['instance'] and left['processId'] == right['processId']
                 and left['source']['selfSha256'] == right['source']['selfSha256']
                 and left['source']['openedEpochMs'] == right['source']['openedEpochMs']
                 and same(left['source']['events'], right['source']['events'])
                 and same(offline['joins'][role]['nativeBefore']['lifecycle'], frame['joins'][role]['nativeAfter']['lifecycle']))
    for role in ('primary', 'peer'):
        first, last = frames[0]['joins'][role], frames[-1]['joins'][role]
        need(last['hostBeforeMonotonic'] - first['hostAfterMonotonic'] >= 3
             and last['hostBeforeEpochMs'] - first['hostAfterEpochMs'] >= 3000
             and last['nativeBefore']['capturedEpochMs'] - first['nativeAfter']['capturedEpochMs'] >= 3000)
    receive.bound()
    return dict(iosChatNoRemoteReplayDerivedVersion=1, runId=receive.run,
                offlineTicket=echo['ticket'], references=deepcopy(references), restoredMixerSha256=mixer,
                noRemoteReplayObserved=True, currentUIStateEstablished=False, wholeChatQualified=False)
