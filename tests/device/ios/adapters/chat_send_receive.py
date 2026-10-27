"""Historical Send/receive join over the existing owners' actual originals.

This pure derived fact is not a new acquisition, rendered peer observation,
cleanup result or whole Chat capability. It sends no input or passive query.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from ios.adapters.chat_draft_owner import IOSChatDraftOwner
from ios.adapters.chat_receive_sources import IOSChatReceiveSources
from ios.adapters.graphics_history import follow_native

VERSION=1


def original_sent(draft,receive,ticket,before,after,*,sender_role='primary'):
    """Join one normal source-bound Send to independently stored receive cuts.

    Text/channel come from the original editor and actual saved message, never
    the caller's expected arguments. Both event prefixes and exact multiplicity
    are checked. Repeating this read cannot deliver or retry a message.
    """
    need(type(sender_role) is str and sender_role in ('primary','peer')
        and isinstance(draft,IOSChatDraftOwner) and isinstance(receive,IOSChatReceiveSources))
    sender_binding=receive.primary_binding if sender_role=='primary' else receive.binding
    sender_lock=receive.primary_lock if sender_role=='primary' else receive.lock
    need(draft.source_bound and draft.version==(4 if sender_role=='primary' else 5) and identifier(ticket)==ticket)
    draft.bound();receive.bound()
    need(draft.previous is not None and receive.previous is not None
        and same(draft.decode(draft.previous),draft.state)
        and same(receive.decode(receive.previous),receive.state)
        and draft.state['pending'] is None and draft.state['observation'] is None
        and receive.state['pending'] is None
        and same(draft.binding,sender_binding) and draft.run==receive.run
        and str(draft.root)==receive.bound_record[sender_role+'ArtifactRoot']['path']
        and draft.lock.path==sender_lock.path)
    sends=[op for op in draft.state['operations'] if op['ticket']==ticket and op['verb']=='send']
    need(len(sends)==1 and sends[0]['verb']=='send'
        and not any(op['ticket']==ticket for op in draft.state['failures']))
    send=sends[0];need(len(send['intents'])==1 and send['after'] is not None)
    need(before in receive.state['records'] and after in receive.state['records']
        and before['index']<after['index'])
    left,right=receive.original(before),receive.original(after)
    first,last=draft.original(send['before']),draft.original(send['after'])
    draft.effect(send,last)
    a,b=left['joins']['peer'],first['clockJoin']
    c,d=last['clockJoin'],right['joins']['primary']
    need(a['hostAfterEpochMs']<=b['hostBeforeEpochMs'] and a['hostAfterMonotonic']<=b['hostBeforeMonotonic']
        and c['hostAfterEpochMs']<=d['hostBeforeEpochMs'] and c['hostAfterMonotonic']<=d['hostBeforeMonotonic'])
    follow_native(left['joins'][sender_role]['nativeAfter'],b['nativeBefore'])
    follow_native(c['nativeAfter'],right['joins'][sender_role]['nativeBefore'])
    lifecycle=left['joins'][sender_role]['nativeBefore']['lifecycle']
    need(same(lifecycle,right['joins'][sender_role]['nativeAfter']['lifecycle']))
    # Every draft cut inside the outer window belongs to this Send. A second
    # normal action cannot be hidden by selecting only the desired after-cut.
    for reference in draft.state['records']:
        frame=draft.original(reference);join=frame['clockJoin']
        overlaps=(join['hostAfterEpochMs']>=a['hostAfterEpochMs']
            and join['hostBeforeEpochMs']<=d['hostBeforeEpochMs'])
        if overlaps:need(frame['ticket']==ticket and frame['verb']=='send')
    prior=draft.local(first);message=last['originals']['view']['source']['storage']['events'][-1]
    need(message['text']==prior['draft'] and message['channel']==prior['channel'])
    sender_sha=left['sample'][sender_role]['source']['selfSha256'];events={}
    mixer=None
    for role in ('primary','peer'):
        old,new=left['sample'][role],right['sample'][role];source,following=old['source'],new['source']
        need(old['instance']==new['instance'] and old['sequence']<new['sequence']
            and source['selfSha256']==following['selfSha256']
            and source['openedEpochMs']==following['openedEpochMs']
            and source['mixerPresent'] and following['mixerPresent']
            and source['mixerSha256']==following['mixerSha256']
            and same(following['events'][:len(source['events'])],source['events'])
            and len(following['events'])==len(source['events'])+1)
        if mixer is None:mixer=source['mixerSha256']
        else:need(mixer==source['mixerSha256'])
        event=following['events'][-1]
        need(event['senderSha256']==sender_sha and not event['localOnly']
            and event['text']==message['text'] and event['channel']==message['channel']
            and old['capturedEpochMs']<=event['capturedEpochMs']<=new['capturedEpochMs'])
        if role==sender_role:need(b['nativeAfter']['capturedEpochMs']<=event['capturedEpochMs']<=c['nativeAfter']['capturedEpochMs'])
        events[role]=deepcopy(event)
    for reference in receive.state['records'][before['index']:after['index']-1]:
        frame=receive.original(reference)
        for role in ('primary','peer'):
            source=frame['sample'][role]['source']
            need(source['mixerPresent'] and source['mixerSha256']==mixer)
        need(same(lifecycle,frame['joins'][sender_role]['nativeBefore']['lifecycle'])
            and same(lifecycle,frame['joins'][sender_role]['nativeAfter']['lifecycle']))
    draft.bound();receive.bound()
    profile=(dict(iosChatSendReceiveDerivedVersion=VERSION,primaryBinding=deepcopy(draft.binding))
        if sender_role=='primary' else dict(iosChatPeerSendReceiveDerivedVersion=VERSION,peerBinding=deepcopy(draft.binding)))
    return dict(profile,runId=draft.run,ticket=ticket,peerBindingRecord=deepcopy(receive.bound_record),
        receiveBefore=deepcopy(before),receiveAfter=deepcopy(after),
        sendBefore=deepcopy(send['before']),sendAfter=deepcopy(send['after']),events=events)
