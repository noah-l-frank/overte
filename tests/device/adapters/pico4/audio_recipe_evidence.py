"""Existing normal recipe -> retained native PCM -> independent digital monitor.

No capture is armed here. The independently owned provider must already retain
the exact normal Start-ticket capture; absence cannot be replaced by a request,
native sink PCM or synthesized signal. Physical acoustic proof remains absent.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import wave

from adapters.native_feature_observation import exact, integer, need, number
from adapters.pico4.audio_capture_owner import read_original_file
from adapters.pico4.audio_peer import PicoAudioPeer, configuration
from adapters.script_journey.history import canonical, unpack
from feature_journeys.evidence import audio_observation


def completed(owner,state):
    need(state['cursor']>=8)
    row=state['steps'][7];need(row['actions'][-1]['name']=='capture3.retain')
    index=row['actions'][-1]['after'];frame=owner.frames[index]
    need(frame['action']=='capture3.retain' and frame['stage']=='after')
    root=frame['original'];child=unpack(root['payload'])[0]
    need(child['phase']=='retained' and child['original']['source']['cycle']==3
         and child['original']['source']['events'][-1]['phase']=='completed')
    start=state['steps'][6]['source'];original_start=child['start']
    need(start['activations']==original_start['activations'] and start['instance']==original_start['instance']
         and start['createdEpochMs']==original_start['createdEpochMs'])
    return start['activations'][-1]['ticket'],root,child


def wav(raw,rate,channels):
    # Shared frozen Phone file primitive: wrap ACTUAL PCM in a WAV header;
    # bytes are never generated from a challenge or requested waveform.
    need(type(raw) is bytes and integer(rate,8000,48000) and integer(channels,1,2)
         and len(raw)%(channels*2)==0 and 0<len(raw)<=32*1024*1024)
    output=io.BytesIO()
    with wave.open(output,'wb') as stream:
        stream.setparams((channels,2,rate,0,'NONE','not compressed'));stream.writeframes(raw)
    return output.getvalue()


def validate(owner,value,*,state):
    if value is None:return
    exact(value,{'phase','sourceTicket','cycle','nativeOriginalSha256','peerSessionHash','peerConfiguration','observations','original','file','metadata'})
    need(value['phase'] in ('issued','joined') and value['cycle']==3 and type(value['cycle']) is int)
    ticket,root,child=completed(owner,state)
    need(value['sourceTicket']==ticket and value['nativeOriginalSha256']==hashlib.sha256(canonical(root)).hexdigest()
         and type(value['peerSessionHash']) is str and len(value['peerSessionHash'])==64)
    configuration(value['peerConfiguration'])
    observations=value['observations'];need(type(observations) is list and len(observations)<=16)
    for row in observations:
        exact(row,{'action','reply'});need(row['action'] in ('status','domain-check','preview-files') and type(row['reply']) is dict)
    need(len(canonical(observations))<=1024*1024)
    if value['phase']=='issued':need(value['file'] is value['metadata'] is value['original'] is None);return
    packet=value['original'];exact(packet,{'schemaVersion','requestId','instance','captureId','capturedEpochMs','exists','retired','original'})
    need(type(packet['schemaVersion']) is int and packet['schemaVersion']==1 and packet['captureId']==ticket
         and packet['exists'] is True and packet['retired'] is False)
    source=packet['original'];need(type(source) is dict and source['captureId']==ticket and source['instance']==packet['instance']
         and source['source']=='private-pc-playout-monitor' and source['physicalAudioHardwareTested'] is False
         and source['startedEpochMs']<=child['original']['source']['startedEpochMs']+250
         and source['completedEpochMs']>=child['original']['source']['sinkLastEpochMs'])
    file=value['file'];exact(file,{'name','phase','file','bytes','sha256'})
    need(file['name']=='preview-'+ticket+'.wav' and file['phase']=='saved' and file['bytes']==source['bytes'] and file['sha256']==source['sha256'])
    read_original_file(Path(value['peerConfiguration']['peerState'])/'audio-owner.json',file)
    metadata=value['metadata'];exact(metadata,{'name','phase','file','bytes','sha256','raw'})
    need(metadata['name']=='preview-'+ticket+'.json' and metadata['phase']=='saved' and type(metadata['raw']) is str
         and len(metadata['raw'].encode())<=65536)
    record={k:v for k,v in metadata.items() if k!='raw'}
    raw=read_original_file(Path(value['peerConfiguration']['peerState'])/'audio-owner.json',record)
    from adapters.native_feature_observation import decode
    need(raw==metadata['raw'].encode() and canonical(decode(metadata['raw']))==canonical(source))


def join(owner,peer):
    need(type(peer) is PicoAudioPeer)
    with owner.lock.held():
        owner.load();need(owner.version==2 and owner.state['pending'] is None and owner.disk['phase'] in ('ready','partial-complete'))
        owner.resources();ticket,root,child=completed(owner,owner.state)
        anchor=owner.anchor();phase=deepcopy(owner.state['lastPhase'])
        previous=owner.state['digitalPreview'];session=peer.session()
        if previous is None:
            state=deepcopy(owner.state)
            state['digitalPreview']=dict(phase='issued',sourceTicket=ticket,cycle=3,
                nativeOriginalSha256=hashlib.sha256(canonical(root)).hexdigest(),peerSessionHash=session,
                peerConfiguration=deepcopy(peer.config),observations=[],original=None,file=None,metadata=None)
            owner.save(state)
        else:
            need(previous['peerSessionHash']==session and previous['peerConfiguration']==peer.config)
        peer.observations=[]
        owner.fence(anchor,phase,native=False)
        try:
            packet,raw=peer.original(owner.run,ticket)
            need(raw is not None and packet['exists'] and not packet['retired'])
            if previous is not None and previous['phase']=='joined':
                need(previous['original']['original']==packet['original'] and previous['file']==peer.last_file
                     and previous['metadata']==peer.last_metadata)
            original=child['original']['source'];rate,channels=original['sampleRate'],original['channels']
            pcm={kind:read_original_file(owner.store.path,child['artifacts'][kind]) for kind in ('input','sink')}
            # Run the existing shared analyzer on full actual input, accepted
            # sink and independent PC bytes. All use the NORMAL START ticket.
            analyses={kind:audio_observation(wav(pcm[kind],rate,channels),owner.run,ticket,profile='recorded-preview-v1')
                      for kind in ('input','sink')}
            analyses['digitalMonitor']=audio_observation(raw,owner.run,ticket,profile='recorded-preview-v1')
            need(peer.session()==session)
            state=deepcopy(owner.state);state['digitalPreview'].update(phase='joined',original=deepcopy(packet),
                file=deepcopy(peer.last_file),metadata=deepcopy(peer.last_metadata),observations=deepcopy(peer.observations))
            owner.save(state);owner.resources()
            result=dict(cycle=3,sourceTicket=ticket,analyses=analyses,independentDigitalMonitorObserved=True,
                        physicalAcousticObserved=False,independentWholePeerObserved=False,fullAudioQualified=False,
                        originalFilesRetained=True)
            expected_root=deepcopy(owner.disk)
            final_anchor=owner.fence(anchor,phase,native=False)
        except BaseException:
            # Persist actual unusable replies before refusing. The pending
            # parent blocks future normal input; a later retry only reads the
            # same owned capture and cannot arm or replay a receive operation.
            if owner.state['digitalPreview']['phase']=='issued':
                state=deepcopy(owner.state);state['digitalPreview']['observations']=deepcopy(peer.observations);owner.save(state)
            raise
    # Historical PCM never becomes a renewed input lease. Include actual outer
    # lock exit, all final file/process guards and copies in the SAME original
    # phase/query budget before publishing the independently decoded result.
    need(owner.lock._owner is None and owner.store.read()==expected_root)
    owner.resources();owner.status()
    started,requested,captured,epoch,finished=final_anchor
    current_epoch=owner.source.epoch_ms();now=owner.monotonic()
    need(number(current_epoch,epoch,1e15) and number(now,finished,1e15)
         and -250<=current_epoch-captured
         and max(current_epoch-captured,requested-captured+(now-started)*1000)<=1500)
    return result
