"""Pure original browser sample grammar; no input or live owner reconstruction."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import math
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.script_journey.history import same
from adapters.pico4.browser_source import continuity,validate as validate_source
from adapters.pico4.browser_measurements import browser_status,measurement
from adapters.normal_feature_state import context
from feature_journeys.contract import arguments,identifier,result
from adapters.pico4.tablet_web_feature import re_script
AREA='tablet-web'
ACTION='pico-tablet-web'


def validate_sample(frame,previous,*,owner,run,fixture_url,foreign_url,vm,image,area="tablet-web"):
    """Replay complete historical source validation without any target query."""
    need(type(area) is str and area in ("tablet-web","world-web"))
    surface="tablet" if area=="tablet-web" else "world"
    action="pico-tablet-web" if surface=="tablet" else "pico-world-web"
    from adapters.native_feature_observation import validate as feature_packet
    from adapters.native_web_runtime import validate as runtime_packet,continuity as runtime_advance
    from adapters.normal_script_manager import diagnostic as service_packet
    from feature_journeys.phase_fixture import validate as phase_packet
    exact(frame,{'phaseBefore','phaseAfter','nativeBefore','nativeAfter','native','runtime','browser','diagnostic',
        'scriptUrl','vm','sample','startedHost','startedEpoch','finishedHost','finishedEpoch'})
    # During cold construction the callback precedes cache assignment.
    binding=owner['binding'];pid=int(binding['processIdentity'].split(':',1)[0])
    epoch=frame['finishedEpoch'];need(integer(epoch,1) and integer(frame['startedEpoch'],1,epoch)
        and number(frame['startedHost'],0,1e15) and number(frame['finishedHost'],frame['startedHost'],frame['startedHost']+10))
    for field in ('phaseBefore','phaseAfter'):
        packet=frame[field];phase_packet(packet,run=run,area=area,request=packet['requestId'],epoch=packet['capturedEpochMs'])
        need(packet['active']);fresh(packet['capturedEpochMs'],epoch)
    need(same(frame['phaseBefore']['activations'],frame['phaseAfter']['activations']))
    need(frame['scriptUrl'] is None or frame['scriptUrl']==owner['scriptUrl'])
    if previous is not None and previous['scriptUrl'] is not None:need(frame['scriptUrl']==previous['scriptUrl'])
    for field in ('nativeBefore','nativeAfter'):
        packet=frame[field];feature_packet(packet,packet['requestId'],pid,epoch)
    before,after=frame['nativeBefore'],frame['nativeAfter']
    need(before['instance']==after['instance'] and before['sequence']<after['sequence']
        and before['lifecycle']==after['lifecycle'] and before['capturedEpochMs']<=after['capturedEpochMs'])
    native=frame['native'];request=dict(schemaVersion=1,commandId=native['commandId'],action=action,runId=run,
        fixtureUrl=fixture_url,ownerToken=owner['ownerToken'],operation='observe')
    validate_source(native,request,pid,epoch)
    runtime=frame['runtime'];runtime_packet(runtime,dict(schemaVersion=1,commandId=runtime['commandId'],
        action='feature-web-runtime-observe',runId=run,fixtureUrl=fixture_url),pid,epoch,require_renderers=True)
    service_packet(frame['diagnostic'],epoch);browser_status(frame['browser'],None if previous is None else previous['browser'])
    if previous is not None:
        continuity(previous['native'],native);runtime_advance(previous['runtime'],runtime,pid,fixture_url)
        need(before['instance']==previous['nativeAfter']['instance'] and before['sequence']>previous['nativeAfter']['sequence']
            and all(after['lifecycle'][key]>=value for key,value in previous['nativeAfter']['lifecycle'].items())
            and frame['diagnostic']['instance']==previous['diagnostic']['instance']
            and frame['diagnostic']['sampleSequence']>previous['diagnostic']['sampleSequence']
            and frame['startedHost']>=previous['finishedHost'])
    measured,resources=measurement(run,fixture_url,foreign_url,native,frame['browser'],runtime,
        frame['diagnostic']['scripts'],frame['scriptUrl'],area=area)
    if frame['vm'] is not None:
        from adapters.chat_journey.source_chunks import digest
        exact(frame['vm'],{'scopeSha256','index','sha256'})
        need(frame['scriptUrl']==owner['scriptUrl'])
        vm.verify();reference=frame['vm'];index=reference['index']
        need(integer(index,0,vm.frame_count-1) and reference['scopeSha256']==digest(vm.scope)
            and reference['sha256']==vm.frame_hash(index))
        from adapters.pico4.browser_vm import join
        _origin,facts=join(vm.frame(index),frame['scriptUrl'],pid,origin=vm.origin,surface=surface)
        if not facts['retired'] and 'script:'+area+'-client' not in resources:resources.append('script:'+area+'-client')
    else:need(frame['scriptUrl'] is None)
    sample=result('feature.'+area+'.observe',frame['sample'])
    need(sample['runId']==run and sample['state']==measured and sample['resources']==resources
        and sample['lifecycle']==after['lifecycle'])
    if sample['artifacts']:
        need(len(sample['artifacts'])==2)
        artifacts={value['kind']:value for value in sample['artifacts']};need(set(artifacts)=={'image','file'})
        cached=image(artifacts['file']['name']);capture=cached['png']['capture'];facts=cached['facts']
        need(sample['state']==facts['state'] and sample['capturedEpochMs']==facts['earliestEpochMs']
            and sample['lifecycle']==cached['lifecycle'])
        for kind,name in (('image',cached['png']['name']),('file',artifacts['file']['name'])):
            need(artifacts[kind]==dict(kind=kind,name=name,sequence=sample['sequence'],
                capturedEpochMs=capture['capturedEpochMs'],ticket=cached['image']['ticket'],
                **(dict(source='world-render-target') if kind=='image' else {})))
    else:need(sample['capturedEpochMs']==after['capturedEpochMs'])
    clocks=[sample['capturedEpochMs'],before['capturedEpochMs'],after['capturedEpochMs'],native['capturedEpochMs'],
        runtime['capturedEpochMs'],frame['diagnostic']['sampleEpochMs'],frame['phaseAfter']['capturedEpochMs']]
    clocks.extend(runtime['source'][key]['capturedEpochMs'] for key in ('nativeBefore','java','nativeAfter'))
    if frame['vm'] is not None:
        original=vm.frame(frame['vm']['index'])
        clocks.extend((original['objectsBefore']['source']['capturedEpochMs'],original['scripts']['capturedEpochMs'],
            original['objectsAfter']['source']['capturedEpochMs']))
    need(min(before['capturedEpochMs'],native['capturedEpochMs'],runtime['source']['nativeBefore']['capturedEpochMs'])
        >=frame['phaseBefore']['activations'][-1]['activatedEpochMs'])
    for captured in clocks:
        fresh(captured,epoch)
        need(max(epoch-captured,frame['startedEpoch']-captured+math.ceil((frame['finishedHost']-frame['startedHost'])*1000))<=1500)


def validate_owner(value,run,fixture_url):
    exact(value,{'binding','ownerToken','phase','reserved','scriptUrl','call','tickets','phaseSource','cleanupProof','lifecycle','inputs','tabletOwned'})
    context(value['binding']);identifier(value['ownerToken'])
    need(value['phase'] in ('preparing','baseline','acting','active','cleaning','cleaned') and type(value['reserved']) is bool
        and type(value['tickets']) is list and len(value['tickets'])<=256 and len(set(value['tickets']))==len(value['tickets'])
        and (value['cleanupProof'] is None or type(value['cleanupProof']) is dict))
    for ticket in value['tickets']:identifier(ticket)
    if value['scriptUrl'] is not None:
        need(value['scriptUrl'].startswith(fixture_url+'tickets/') and re_script(value['scriptUrl'][len(fixture_url+'tickets/'):]))
    if value['call'] is not None:
        arguments('feature.'+AREA+'.act',value['call']);need(value['call']['runId']==run and value['call']['fixtureUrl']==fixture_url
            and value['call']['ticket']==value['tickets'][-1])
    need(type(value['inputs']) is list and len(value['inputs'])<=4096 and type(value['tabletOwned']) is bool)
    from feature_journeys.phase_fixture import validate as phase_packet
    for index,row in enumerate(value['inputs']):
        exact(row,{'ticket','original','anchor','complete','envelope'});identifier(row['ticket'])
        need(type(row['complete']) is bool and type(row['original']) is dict and row['original'].get('kind') in
            ('source-control','browser','normal-ui','home-ray','browser-app','lifecycle'))
        anchor=row['anchor'];exact(anchor,{'ticket','before','packet','hostMonotonic','epochMs'})
        need(anchor['ticket']==row['ticket'] and number(anchor['hostMonotonic'],0,1e15) and number(anchor['epochMs'],1,1e16))
        for field in ('before','packet'):
            packet=anchor[field];phase_packet(packet,run=run,area=AREA,request=packet['requestId'],epoch=packet['capturedEpochMs'])
            need(packet['activations'] and packet['activations'][-1]['ticket']==row['ticket'])
        need(anchor['before']['activations']==anchor['packet']['activations'])
        need(row['envelope'] is None or type(row['envelope']) is dict)
        if index:need(anchor['hostMonotonic']>=value['inputs'][index-1]['anchor']['hostMonotonic'])
    if value['cleanupProof'] is not None and 'browserQuietReferenceVersion' not in value['cleanupProof']:
        from adapters.pico4.browser_quiet import validate as quiet_packet
        quiet_packet(value['cleanupProof'],run,fixture_url,value['ownerToken'],
            int(value['binding']['processIdentity'].split(':',1)[0]),retired=False)
