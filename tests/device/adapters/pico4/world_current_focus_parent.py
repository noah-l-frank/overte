"""Current ray/focus substage of the existing World acting owner.

The original v16 focus/type action stays acting: focus is not text consumption.
No second owner, journey, replay, Keyboard trace or shared version is added.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import exact,need,number
from adapters.pico4.world_current_input import decode,validate
from adapters.pico4.world_current_document import semantic,strict
from adapters.pico4.browser_source import geometry_original
from adapters.android.input_geometry import observed_grip_pose
from feature_journeys.contract import arguments
from feature_journeys.scenarios import SCENARIOS,expand
from feature_journeys.fixtures import context

VERSION=1
FIELD='picoWorldCurrentFocusParentVersion'
LIMIT=40


def original(value,owner,run,url,control,operation):
    exact(value,{'raw','request','documentOriginal'})
    packet=decode(value['raw']);call=value['request'];identity=owner['binding']['processIdentity']
    need(type(identity) is str and re.fullmatch('[1-9][0-9]*:[0-9]+',identity))
    validate(packet,call,int(identity.split(':')[0]),packet['capturedEpochMs'],value['documentOriginal'])
    need(packet['status']=='ready' and call['runId']==run and call['fixtureUrl']==url
         and call['ownerToken']==owner['ownerToken'] and call['control']==control and call['operation']==operation)
    return packet


def focus_matches(calibration,focus):
    old,new=decode(calibration['raw'])['source'],decode(focus['raw'])['source']
    old_dom=decode(calibration['documentOriginal']['raw'])['source']['dom']
    new_dom=decode(focus['documentOriginal']['raw'])['source']['dom']
    need(json_digest(semantic(old['authorityBefore']['native']))==json_digest(semantic(new['authorityAfter']['native']))
         and json_digest(old['originalFinish'])==json_digest(new['originalFinish'])
         and old_dom['instance']==new_dom['instance'] and json_digest(old_dom['document'])==json_digest(new_dom['document']))
    packet=decode(focus['raw'])
    geometry=geometry_original(decode(new['focusRaw'])['geometryRaw'],focus['request'],new['authorityBefore']['native']['url'],packet['capturedEpochMs'])
    return geometry['editor']['focused'] is True and new['nativeEditor']['focused'] is True and new['nativeEditor']['enabled'] is True


def validate_carrier(value,row,owner,run,url):
    strict(value)
    exact(value,{FIELD,'ticket','control','phase','calibrationOriginal','deliveryIntent','publication','focusOriginals'})
    need(type(value[FIELD]) is int and value[FIELD]==VERSION and value['ticket']==row['ticket']
         and value['control']=='text' and value['phase'] in ('planned','calibrated','published','focused')
         and type(value['focusOriginals']) is list and len(value['focusOriginals'])<=LIMIT)
    activation=row['anchor']['packet']['activations'][-1]
    need(activation['ticket']==value['ticket'] and activation['stimulus']['verb'] in ('focus-type','clear-text'))
    if value['phase']=='planned':
        need(value['calibrationOriginal'] is None and value['deliveryIntent'] is None and value['publication'] is None
             and value['focusOriginals']==[] and row['envelope'] is None and row['complete'] is False)
        return
    calibration=value['calibrationOriginal'];packet=original(calibration,owner,run,url,'text','measure-current-ray')
    ray=packet['source']['worldRay'];pose=observed_grip_pose(ray['sensorToWorld'],ray['headPosition'],ray['worldPoint'])
    intent=value['deliveryIntent']
    if intent is not None:
        exact(intent,{'operation','calibrationOriginal','pose'})
        need(intent['operation']=='world-current-trigger' and json_digest(intent['calibrationOriginal'])==json_digest(calibration)
             and json_digest(intent['pose'])==json_digest(pose))
    envelope=row['envelope']
    if envelope is not None:
        need(intent is not None);exact(envelope,{'schemaVersion','sessionNonce','sequence','commands'})
        need(type(envelope['schemaVersion']) is int and envelope['schemaVersion']==1
             and type(envelope['sessionNonce']) is str and re.fullmatch('[0-9a-f]{64}',envelope['sessionNonce'])
             and type(envelope['sequence']) is int and envelope['sequence']>=1
             and type(envelope['commands']) is list and len(envelope['commands'])==1)
        command=envelope['commands'][0];exact(command,{'id','operation','arguments'})
        need(command['operation']=='input.primary' and command['id']=='input-primary-'+str(envelope['sequence'])
             and json_digest(command['arguments'])==json_digest(pose))
    publication=value['publication']
    if publication is not None:
        exact(publication,{'calibrationOriginal','streamEnvelope','publication'})
        need(intent is not None and envelope is not None and json_digest(publication['calibrationOriginal'])==json_digest(calibration)
             and json_digest(publication['streamEnvelope'])==json_digest(envelope))
    need((value['phase'] in ('published','focused'))==(publication is not None)
         and (value['phase']!='calibrated' or not value['focusOriginals'])
         and (row['complete'] is False or value['phase']=='focused'))
    for focus in value['focusOriginals']:original(focus,owner,run,url,'text','observe-current-focus')
    if value['phase']=='focused':
        need(bool(value['focusOriginals']) and focus_matches(calibration,value['focusOriginals'][-1]))


def epochs(value):
    packet=decode(value['raw']);doc=decode(value['documentOriginal']['raw'])
    field='geometryRaw' if value['request']['operation']=='measure-current-ray' else 'focusRaw'
    geometry=decode(decode(packet['source'][field])['geometryRaw'])
    if type(geometry) is str:geometry=decode(geometry)
    clocks=[geometry['capturedEpochMs'],doc['source']['dom']['capturedEpochMs']]
    for current in (doc,packet):
        clocks.extend([current['requestedEpochMs'],current['capturedEpochMs']])
        clocks.extend(current['source'][side][kind]['capturedEpochMs'] for side in ('authorityBefore','authorityAfter') for kind in ('native','java'))
    if field=='geometryRaw':clocks.append(packet['source']['worldRay']['capturedEpochMs'])
    return clocks


def begin(parent,value):
    """Issue one normal ray from the actual next focus/type phase, then read focus.

    No completed-step append occurs here. A cold/second call refuses before
    any new source query or input; read() can inspect every original substage.
    """
    call=deepcopy(arguments('feature.world-web.act',value))
    need(parent.role=='primary' and parent.lock._owner is None)
    with parent.lock.held(),parent.adapter.existing_input_session(parent.target):
        parent.read();parent.control();need(parent.state is not None and parent.state['phase']=='ready')
        index=len(parent.state['completed']);need(0<index<len(SCENARIOS[parent.area]['steps']))
        step=SCENARIOS[parent.area]['steps'][index]
        need(call['runId']==parent.run and call['fixtureUrl']==parent.url and call['verb'] in ('focus-type','clear-text')
             and json_digest(dict(verb=call['verb'],inputs=call['inputs']))==json_digest(dict(verb=step['verb'],inputs=expand(step['inputs'],context(parent.run)))))
        parent.observation_admission();phase=parent.source.read(parent.state['fixture'])
        need(phase['ticket']==call['ticket'] and phase['verb']==call['verb'] and phase['inputs']==call['inputs']
             and len(phase['status']['activations'])==index+2)
        started=parent.source.monotonic();native=parent.adapter._native_feature_observer(parent.target,read_only=True);requested=native.clock_ms()
        state=deepcopy(parent.state);state.update(phase='acting',active=call,fixture=deepcopy(phase['status']));parent.save(state)
        carrier={FIELD:VERSION,'ticket':call['ticket'],'control':'text','phase':'planned','calibrationOriginal':None,
                 'deliveryIntent':None,'publication':None,'focusOriginals':[]}
        parent.input_begin(carrier);seal=parent.seal(started,requested,[],native)
    parent.finalize(seal) # Real outer exit, before even one CurrentDoc query.
    expected=[deepcopy(seal['body']),deepcopy(seal['pins'])]
    def host_control():
        parent.lock.assert_held();parent.control()
        need(json_digest(parent.store.read())==json_digest(expected[0]) and json_digest(parent.pins())==json_digest(expected[1])
             and parent.state['phase']=='acting' and json_digest(parent.state['active'])==json_digest(call))
    def remember():
        expected[:]=[deepcopy(parent.disk),parent.pins()]
    source=parent.adapter.world_prefix_current_source(parent.target,parent)
    base_guard=source.guard
    def guard():
        need(base_guard() is not False)
        if parent.lock._owner is not None:
            host_control();parent.runtime();parent.exact_phase();host_control()
        else:
            with parent.lock.held():
                host_control();parent.runtime();parent.exact_phase()
                current=parent.seal(parent.source.monotonic(),native.clock_ms(),[],native)
            parent.finalize(current)
        return True
    source.guard=source.documents.guard=guard
    source.read(parent.run,parent.url,parent.state['ownerToken'],'measure-current-ray','text')
    calibration=source.original()

    def save(update,*,current=None):
        need(parent.lock._owner is None)
        if current is not None:
            source.require_warm(current);start,request,_=source._warm_anchor;clocks=epochs(current)
        else:start,request,clocks=parent.source.monotonic(),native.clock_ms(),[]
        with parent.lock.held():
            host_control();parent.runtime();parent.exact_phase()
            need(parent.state['phase']=='acting' and json_digest(parent.state['active'])==json_digest(call))
            state=deepcopy(parent.state);row=state['inputs'][-1]
            need(row['ticket']==call['ticket'] and FIELD in row['original']);update(row)
            parent.save(state);seal=parent.seal(start,request,clocks,native)
            result=deepcopy(row['original'])
        parent.finalize(seal);expected[:]=[deepcopy(seal['body']),deepcopy(seal['pins'])];return result

    save(lambda row:row['original'].update(phase='calibrated',calibrationOriginal=deepcopy(calibration)),current=calibration)
    def intent(value):
        host_control();parent.runtime();parent.exact_phase()
        state=deepcopy(parent.state);carrier=state['inputs'][-1]['original']
        need(parent.state['phase']=='acting' and json_digest(parent.state['active'])==json_digest(call)
             and carrier['phase']=='calibrated' and carrier['deliveryIntent'] is None)
        carrier['deliveryIntent']=deepcopy(value);parent.save(state);remember();parent.input_fence().check()
    def stream(envelope):
        host_control();parent.input_fence().stage_intent(envelope);remember()
    def publish(envelope):
        host_control();parent.input_fence().before_publish(envelope);host_control()
    def admission():
        host_control();parent.runtime();parent.exact_phase();parent.input_fence().check()
    ray=parent.adapter.world_prefix_current_ray(parent.target,parent,source,intent,
        stream_intent=stream,before_publish=publish,admission=admission)
    publication=ray.publish()
    save(lambda row:row['original'].update(phase='published',publication=deepcopy(publication)),current=calibration)
    started=parent.source.monotonic();previous=started
    for attempt in range(LIMIT):
        # Independent exact phase/read admission, outside the source's lock.
        with parent.lock.held():
            host_control();parent.runtime();parent.exact_phase()
            need(parent.state['phase']=='acting' and json_digest(parent.state['active'])==json_digest(call))
            before=parent.seal(parent.source.monotonic(),native.clock_ms(),[],native)
        parent.finalize(before)
        source.read(parent.run,parent.url,parent.state['ownerToken'],'observe-current-focus','text');focus=source.original()
        # Retain a well-formed but foreign-current-grant original before its
        # semantic refusal. Publication never supplies a replacement focus.
        save(lambda row:row['original']['focusOriginals'].append(deepcopy(focus)),current=focus)
        if focus_matches(calibration,focus):
            ray.check_focus(publication,focus)
            def complete(row):row['original']['phase']='focused';row['complete']=True
            return save(complete,current=focus)
        now=parent.source.monotonic();need(number(now,previous,started+5) and attempt<LIMIT-1);previous=now
        source.sleep(.1)
    need(False)
