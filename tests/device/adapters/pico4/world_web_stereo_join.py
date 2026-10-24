"""Original World source frames bracket existing World two-eye ownership.

No normal input, scene construction, Mono relabel, expected state or resource
retirement shortcut is provided. Partial acquisitions remain explicitly owned.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import uuid

from adapters.chat_journey.source_chunks import json_digest,digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.observer_return import parent_node
from adapters.pico4.browser_actor_graph import original
from adapters.pico4.browser_stereo import PicoBrowserStereo,original_name
from adapters.pico4.graphics_journey import artifact_directory
from adapters.pico4.world_web_prefix import PicoWorldWebPrefix
from adapters.script_journey.history import same,canonical
from feature_journeys.stereo_browser_evidence import archive_sources

VERSION=1


def source_reference(frame):return dict(sequence=frame['sample']['sequence'],sha256=digest(frame))


def bracket(before,after,frame,facts):
    need(same(before['phaseBefore']['activations'],after['phaseAfter']['activations'])
        and same(before['sample']['state'],facts['state']) and same(after['sample']['state'],facts['state']))
    for family,cursor,nonce in (('native','sequence','commandId'),('runtime','sequence','commandId'),('diagnostic','sampleSequence','requestId')):
        key='browser' if family=='native' else 'scripts' if family=='diagnostic' else 'runtime'
        a,b=frame[key+'Before'],frame[key+'After'];left,right=before[family],after[family]
        need(left['instance']==a['instance']==b['instance']==right['instance']
            and left[cursor]<a[cursor]<b[cursor]<right[cursor])
        if nonce in a:need(len({left[nonce],a[nonce],b[nonce],right[nonce]})==4)
    need(before['nativeAfter']['sequence']<frame['nativeBefore']['sequence']<frame['nativeAfter']['sequence']<after['nativeBefore']['sequence']
        and before['nativeAfter']['instance']==frame['nativeBefore']['instance']==after['nativeBefore']['instance'])


class WorldStereoJoin:
    """Same owner/lock/role and exact phase, fresh before/after source reads."""
    def __init__(self,flow,artifacts):
        need(type(flow) is PicoWorldWebPrefix and flow._source_pass_export is None)
        self.flow,self.lock=flow,flow.lock;self.artifacts=artifact_directory(artifacts)
        self.store=PrivateFeatureState(flow.root/('pico-world-web-'+flow.role+'-stereo.json'))
        self.state=self.previous=None;self.owner=None;self.stamp=None
        self.scope=self.scope_sha=None;self.failed=False
        self.artifact_parent=parent_node(PrivateFeatureState(self.artifacts/'boundary.json'))
        with self.lock.held():
            flow.read();flow.control();need(flow.state is not None)
            self.scope=dict(prefixScope=deepcopy(flow.scope),binding=deepcopy(flow.state['binding']),ownerToken=flow.state['ownerToken'],
                role=flow.role,artifactRoot=str(self.artifacts),artifactParent=list(self.artifact_parent),sceneUrl=flow.adapter.scene_url)
            self.scope_sha=json_digest(self.scope);old=self.store.read();need(old is None)
            # This owner is warm-only. Historical admission belongs to the
            # independent original Source-Pass graph, never a resumed capture.
    def control(self):
        self.lock.assert_held();self.flow.control();need(not self.failed and json_digest(self.scope)==self.scope_sha
            and self.flow._source_pass_export is None and same(self.store.read(),self.previous)
            and same(self.state,None if self.previous is None else self.previous['payload'])
            and (self.stamp is None or original(self.store.path)[1]==self.stamp)
            and parent_node(PrivateFeatureState(self.artifacts/'boundary.json'))==self.artifact_parent)
    def save(self,value):
        self.control();json_digest(value)
        body=dict(picoWorldWebStereoJoinVersion=VERSION,scope=deepcopy(self.scope),payload=deepcopy(value))
        self.store.write(body,self.previous);raw,stamp=original(self.store.path);need(raw==canonical(body)+b'\n')
        self.previous=deepcopy(body);self.state=deepcopy(value);self.stamp=stamp
    def capture(self,before=None):
        need(self.lock._owner is None and not self.failed)
        observe=self.flow.publish if self.flow.role=='actor' else self.flow.observe
        if before is None:before=observe()
        try:
            with self.lock.held():
                self.flow.read();self.control();history=self.flow.history_reader();first=history.last
                need(self.flow.state['phase']=='ready' and same(first['sample'],before) and before['state']['open']
                    and (self.state is None or self.state['phase']=='ready' and len(self.state['images'])<64))
                phase=self.flow.exact_phase();need(same(phase['status']['activations'],first['phaseBefore']['activations']))
                journal=uuid.uuid4().hex
                active=dict(journalId=journal,ticket=phase['ticket'],phase=deepcopy(phase['status']),before=source_reference(first))
                self.save(dict(phase='acquiring',images=[] if self.state is None else self.state['images'],active=active))
                self.owner=self.flow.adapter.world_prefix_stereo(self.flow.target,self.flow,self.artifacts,journal)
                need(type(self.owner) is PicoBrowserStereo and self.owner.surface=='world' and self.owner.lock is self.lock)
                capture=self.owner.acquire(phase['ticket']);need(capture['phase']=='complete')
                metadata,stamp=original(self.owner.store.path);raw,png_stamp=original(self.artifacts/capture['image']['name'])
                body,state,facts=archive_sources(metadata,raw,self.flow.run,phase['ticket'],self.scope['sceneUrl'],role=self.flow.role,surface='world')
                need(body['binding']==self.scope['binding'] and body['scope']==dict(fixtureUrl=self.flow.url,foreignFixtureUrl=self.flow.foreign,
                    ownerToken=self.scope['ownerToken'],scriptUrl=self.flow.state['scriptUrl']) and same(facts['state'],first['sample']['state']))
                active=deepcopy(active);active['metadata']=dict(name=self.owner.store.path.name,stamp=stamp,sha256=hashlib.sha256(metadata).hexdigest())
                active['png']=dict(name=capture['image']['name'],stamp=png_stamp,sha256=hashlib.sha256(raw).hexdigest())
                value=deepcopy(self.state);value.update(phase='captured',active=active);self.save(value)
                self.flow.exact_phase()
            after=observe()
            with self.lock.held():
                self.flow.read();self.control();last=self.flow.history_reader().last
                need(same(last['sample'],after) and same(last['phaseBefore']['activations'],active['phase']['activations']))
                bracket(first,last,capture['frame'],facts)
                for row in (active['metadata'],active['png']):
                    data,physical=original(self.artifacts/row['name'],row['stamp']);need(hashlib.sha256(data).hexdigest()==row['sha256'])
                active=deepcopy(active);active['after']=source_reference(last)
                value=deepcopy(self.state);value.update(phase='ready',images=value['images']+[active],active=None);self.save(value)
                # Both actual capture and the post-capture source/copy/CAS are
                # bounded by the original first source's acquisition anchors.
                native=self.flow.adapter._native_feature_observer(self.flow.target,read_only=True)
                epochs=[first['nativeBefore']['capturedEpochMs'],facts['earliestEpochMs'],after['capturedEpochMs']]
                returned=deepcopy(active);seal=self.flow.seal(first['startedHost'],first['startedEpoch'],epochs,native)
            self.flow.finalize(seal)
            return returned
        except BaseException:self.failed=True;raise


def original_join(body,scope,history,read):
    """Cold complete original stereo sidecar; never restores a capture owner."""
    exact(body,{'picoWorldWebStereoJoinVersion','scope','payload'});json_digest(body)
    need(type(body['picoWorldWebStereoJoinVersion']) is int and body['picoWorldWebStereoJoinVersion']==VERSION and same(body['scope'],scope))
    value=body['payload'];exact(value,{'phase','images','active'})
    need(value['phase']=='ready' and value['active'] is None and type(value['images']) is list and 1<=len(value['images'])<=64)
    frames={row['original']['sample']['sequence']:row['original'] for row in history.rows if row['event']=='sample'}
    seen=set();result=[]
    for row in value['images']:
        exact(row,{'journalId','ticket','phase','before','after','metadata','png'})
        from feature_journeys.contract import identifier
        identifier(row['journalId']);identifier(row['ticket']);need(row['journalId'] not in seen);seen.add(row['journalId'])
        first,last=(frames[row[key]['sequence']] for key in ('before','after'))
        for key,frame in (('before',first),('after',last)):need(same(row[key],source_reference(frame)))
        from feature_journeys.phase_fixture import validate as original_phase
        original_phase(row['phase'],run=scope['prefixScope']['runId'],area='world-web',request=row['phase']['requestId'],
            epoch=row['phase']['capturedEpochMs'],previous=first['phaseAfter'])
        original_phase(last['phaseBefore'],run=scope['prefixScope']['runId'],area='world-web',request=last['phaseBefore']['requestId'],
            epoch=last['phaseBefore']['capturedEpochMs'],previous=row['phase'])
        need(same(row['phase']['activations'],first['phaseBefore']['activations'])
            and row['ticket']==row['phase']['activations'][-1]['ticket'])
        raw=[]
        for key in ('metadata','png'):
            record=row[key];exact(record,{'name','stamp','sha256'})
            from adapters.observer_return import physical
            physical(record['stamp']);data,stamp=read(record['name'])
            need(stamp==record['stamp'] and hashlib.sha256(data).hexdigest()==record['sha256']);raw.append(data)
        source,state,facts=archive_sources(raw[0],raw[1],scope['prefixScope']['runId'],row['ticket'],scope['sceneUrl'],role=scope['role'],surface='world')
        need(source['artifactRoot']==scope['artifactRoot'] and source['binding']==scope['binding'] and source['role']==scope['role']
            and source['journalId']==row['journalId'] and source['scope']==dict(fixtureUrl=scope['prefixScope']['fixtureUrl'],
                foreignFixtureUrl=scope['prefixScope']['foreignFixtureUrl'],ownerToken=scope['ownerToken'],scriptUrl=first['scriptUrl'])
            and row['metadata']['name']==original_name(scope['prefixScope']['runId'],scope['role'],row['journalId'],surface='world')
            and row['png']['name']==state['image']['name'])
        bracket(first,last,state['frame'],facts);result.append(dict(original=deepcopy(row),facts=facts))
    return result
