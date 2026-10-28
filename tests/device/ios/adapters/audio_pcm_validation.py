"""Pure original native/PCM joins and independent tap absence qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_clock_join import validate_join
from adapters.native_feature_observation import exact,integer,need
from adapters.recorded_preview_evidence import INPUT,SINK,validate as preview_packet,validate_input_origin
from adapters.script_feature.history import same
from feature_journeys.phase_fixture import validate as phase_packet
from ios.adapters.graphics_history import follow_native


def phases(owner,value,*,active):
    first,last=value['phaseBefore'],value['phaseAfter']
    phase_packet(first,run=owner.run,area='audio',request=first['requestId'],epoch=first['capturedEpochMs'])
    phase_packet(last,run=owner.run,area='audio',request=last['requestId'],epoch=last['capturedEpochMs'],previous=first)
    need(same(first['activations'],last['activations']) and (not active or first['active'] and last['active']))


def clock(owner,value,name,others=None):
    packet=value['packet'];join=validate_join(value['clockJoin'],{name:packet}|({} if others is None else others))
    first,last=join['nativeBefore'],join['nativeAfter'];follow_native(first,last)
    # Close-only mode follows the already fully validated parent Close after
    # its original background bridge; it cannot require the pre-background
    # Start lifecycle counters to equal today's counters or retime that Start.
    reference=owner.closing['original'] if owner.version==3 else owner.recording['original']
    initial=owner.recorded.original(reference)['clockJoin']['nativeAfter'];follow_native(initial,first)
    need(first['processId']==last['processId']==int(owner.binding['processIdentity']) and first['lifecycle']==last['lifecycle']==initial['lifecycle'])
    for native in (first,last):
        need(native['audio']['recordedVoice']['cycle']==owner.recording['cycle'])
    need(packet['processId']==int(owner.binding['processIdentity']) and packet['instance']==first['instance']==last['instance']
        and packet['requestedEpochMs']>=first['capturedEpochMs'])
    return join


def snapshot(owner,value):
    exact(value,{'audioPCMKind','audioPCMSnapshotVersion','recording','packet','chunks','clockJoin','phaseBefore','phaseAfter','preflight','preflightQuery'})
    need(value['audioPCMKind']=='snapshot' and type(value['audioPCMSnapshotVersion']) is int and value['audioPCMSnapshotVersion']==1
        and same(value['recording'],owner.recording));phases(owner,value,active=True)
    join=clock(owner,value,'snapshot',dict(preflight=value['preflight']));packet=value['packet']
    preflight=files_packet(owner,value['preflight'],value['preflightQuery'])
    need(preflight['instance']==join['nativeBefore']['instance'] and preflight['requestedEpochMs']>=join['nativeBefore']['capturedEpochMs']
        and preflight['sequence']<packet['sequence']
        and owner.state['queries'].index(value['preflightQuery'])<owner.state['queries'].index(owner.state['allocation']))
    for row in preflight['files']:need(row['exists'] is False)
    preview_packet(packet,owner.state['allocation']['commandId'],int(owner.binding['processIdentity']),join['nativeAfter']['capturedEpochMs'])
    source=packet['source'];native=join['nativeAfter']['audio']['recordedVoice']
    # AudioClient samples the two original start timestamps sequentially.
    # Preserve both; the Preview observer begins after native cycle metadata
    # and before that cycle's first original published event.
    need(source['cycle']==owner.recording['cycle'] and native['events']
        and native['startedEpochMs']<=source['startedEpochMs']<=native['events'][0]['publishedEpochMs']
        and source['sampleRate']==native['captureSampleRate'] and source['channels']==native['captureChannels']
        and same(native['events'][:len(source['events'])],source['events']))
    exact(value['chunks'],{'input','sink'})
    for kind in ('input','sink'):
        raw=owner.originals.pcm(value,kind)
        if kind=='input':validate_input_origin(packet,raw,required=owner.version==2)
    return value


def files_packet(owner,packet,query):
    owner.command(query)
    need(query['action']=='feature-recorded-audio-files' and query in owner.state['queries'])
    exact(packet,{'schemaVersion','requestId','instance','sequence','requestedEpochMs','capturedEpochMs','processId','files','memoryEmpty'})
    need(type(packet['schemaVersion']) is int and packet['schemaVersion']==1 and packet['requestId']==query['commandId']
        and integer(packet['sequence'],1) and integer(packet['requestedEpochMs'],1)
        and integer(packet['capturedEpochMs'],packet['requestedEpochMs'])
        and packet['capturedEpochMs']-packet['requestedEpochMs']<1500
        and packet['processId']==int(owner.binding['processIdentity']) and type(packet['memoryEmpty']) is bool
        and type(packet['files']) is list and len(packet['files'])==2)
    for row,name in zip(packet['files'],(INPUT,SINK)):
        exact(row,{'name','exists'});need(row['name']==name and type(row['exists']) is bool)
    return packet


def absence(owner,value):
    exact(value,{'audioPCMKind','audioPCMAbsenceVersion','recording','packet','query','clockJoin','phaseBefore','phaseAfter'})
    need(value['audioPCMKind']=='absence' and type(value['audioPCMAbsenceVersion']) is int and value['audioPCMAbsenceVersion']==1
        and same(value['recording'],owner.recording));phases(owner,value,active=False)
    packet=files_packet(owner,value['packet'],value['query']);join=clock(owner,value,'absence')
    need(owner.state['release'] is not None and owner.state['queries'].index(value['query'])>owner.state['queries'].index(owner.state['release'])
        and packet['memoryEmpty'] is True and all(row['exists'] is False for row in packet['files']))
    if owner.state['snapshot'] is not None:
        previous=owner.originals.read(owner.state['snapshot'])['packet'];need(packet['sequence']>previous['sequence'])
    need(join['nativeAfter']['capturedEpochMs']>=packet['capturedEpochMs']);return value
