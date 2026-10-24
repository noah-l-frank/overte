"""Final v2 replay of original role readiness and actual own native ordering."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters.emote_scene_gate import IOSEmoteSceneGate
from ios.adapters.emote_retirement import Frozen
from ios.adapters.emote_native_prefix import follow


def before(gate,stage,ticket,packet):
    own=[gate.replayed[ref['sha256']] for ref in gate.state['own']];peer=[gate.replayed[ref['sha256']] for ref in gate.state['peer']]
    candidates=[]
    for item,actual in peer:
        if item['stage']!=stage or item['ticket']!=ticket:continue
        endpoint=actual['ownEndpoint']
        if endpoint['sequence']>=packet['sequence']:continue
        left=[row for row in own if row[0]['stage']==stage and row[0]['ticket']==ticket
            and row[1]['nativeEndpoint']['sequence']<endpoint['sequence']]
        if not left:continue
        source=left[-1][1]['nativeEndpoint'];follow(source,endpoint);follow(endpoint,packet)
        need(endpoint['animation']['overrideActive'] is False)
        if 'history' in source['animation']:
            need(endpoint['animation']['history']['callSequence']==source['animation']['history']['callSequence'])
        candidates.append(endpoint)
    need(candidates);return candidates[-1]


def validate(final,copies,scope,frames,*,validate_original=None):
    f=final.flow;path=final.path('ios-emote-'+f.role+'-scene-gate.json');value=copies[str(path.path)];need(value is not None)
    from adapters.normal_feature_state import PrivateFeatureState
    peer_path=Path(value['peerStatePath']);need(peer_path!=path.path and peer_path.is_absolute() and peer_path.resolve()==peer_path)
    options={} if validate_original is None else dict(validate_original=validate_original)
    gate=IOSEmoteSceneGate.archive(value,store=Frozen(path.path,value),root=f.root,binding=f.state['binding'],run=f.run,role=f.role,
        instance=f.state['phaseInstance'],admission=value['peerAdmission'],peer_store=PrivateFeatureState(peer_path),lock=f.lock,primary_lock=f.primary_lock,**options)
    need(gate.state['pending'] is None and gate.state['own'] and gate.state['peer'])
    if f.role=='primary':need(same(gate.admission,f.state['actorAdmission']))
    else:need(same(gate.peer_binding,f.state['primaryBinding']))
    baseline=scope.frames[scope.state['baseline']-1]['clockJoin']['nativeBefore']
    before(gate,'initial',f.state['initialTicket'],baseline)
    # Every actual cleanup fence, including retained failed-image candidates,
    # must have been scheduled only after both actual scene-end originals.
    cleanup=[ref for ref in frames.state['records'] if frames.original(ref)['phase']=='captured' and frames.original(ref)['kind']=='cleanup']
    need(cleanup)
    for ref in cleanup:
        frame,_raw=frames.frame(ref)
        # Original cleanup activations may repeat within one run. The precise
        # retained role-ready ticket is admitted by its original phase packet.
        peer=[gate.replayed[row['sha256']] for row in gate.state['peer']]
        tickets={item['ticket'] for item,_actual in peer if item['stage']=='scene-retired'}
        endpoints=[]
        for ticket in tickets:
            eligible=[actual['ownEndpoint'] for item,actual in peer
                if item['stage']=='scene-retired' and item['ticket']==ticket
                and actual['ownEndpoint']['sequence']<frame['clockJoin']['nativeBefore']['sequence']]
            if eligible:endpoints.append(before(gate,'scene-retired',ticket,frame['clockJoin']['nativeBefore']))
        need(endpoints)

    gate.replay_lease.guard()
    for lease in gate.foreign_leases:lease.guard()
