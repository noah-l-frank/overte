"""Durable role/process Graphics samples from original sources and owned PNGs.

This internal producer performs no normal UI input or fixture activation. It
advertises no feature capability. A pending acquisition cannot become a fresh
success by recreating the producer or relabelling an archived image.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
from pathlib import Path
import math
import time

from adapters.native_feature_observation import exact,fresh,integer,need,number,validate as native_packet
from adapters.native_graphics_subject import validate as subject_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.owned_world_render import WorldRenderOwner
from adapters.world_render_evidence import validate as _capture_packet
from feature_journeys.contract import arguments,identifier
from feature_journeys.scenarios import VERSION as FEATURE_VERSION
from feature_journeys.graphics_resources import validate_status
from feature_journeys.witness import Client
from feature_journeys.evidence import MarkerNotReady
from adapters.pico4.graphics_source import validate as graphics_packet
from adapters.graphics_journey.originals import GraphicsOriginals,record as image_record,transition as image_transition
from adapters.graphics_journey.measurements import compose,metadata_bytes,frame_fields
from adapters.graphics_journey.source_history import restore_native,restore_ui
from feature_journeys.stereo_graphics_evidence import policy as stereo_policy,SURFACE_PROFILE,PROFILE
from adapters.script_journey.files import validate as tablet_packet
from adapters.script_journey.history import pack,unpack,same
from adapters.script_journey.lock import ScriptSourceLock

VERSION=5
CURSORS={'native','subject','graphics','tablet','capture','storage','inventory','provider'}
FIELDS={'binding','phase','sequence','cursors','seenFrames','images','pending','frame','retirements','readiness'}


class GraphicsMarkerPending(NativeUIError):
    """A retained original acquisition lacks current marker pixels; no facts."""


def capture_packet(packet,nonce,pid,epoch):
    return _capture_packet(packet,nonce,pid,epoch,stereo=True,require_cameras=True)


def retirement(proof,owner,pid,binding,role):
    """Validate retained original memory and complete file-absence proofs."""
    exact(proof,{'memory','files','owner'})
    exact(owner,{'ownershipVersion','binding','role','capture','receipts'})
    need(same(proof['owner'],owner) and type(owner['ownershipVersion']) is int and owner['ownershipVersion']==2
         and same(context(owner['binding']),context(binding)) and owner['role']==role and role in ('primary','actor')
         and WorldRenderOwner.acquisition(owner['capture']) and type(owner['receipts']) is list
         and 0<len(owner['receipts'])<=1024 and len(set(owner['receipts']))==len(owner['receipts']))
    for nonce in owner['receipts']:identifier(nonce)
    capture=owner['capture']['commandId'];ids=owner['receipts'];instance=proof['memory']['instance']
    memory=proof['memory']
    exact(memory,{'storageVersion','commandId','requestId','instance','sequence','processId','capturedEpochMs','present','callbacks','pngBytes'})
    need(type(memory['storageVersion']) is int and memory['storageVersion']==1 and memory['requestId']==capture
         and identifier(memory['commandId']) in ids and integer(memory['sequence'],1) and memory['processId']==pid
         and integer(memory['processId'],1) and integer(memory['capturedEpochMs'],1)
         and memory['present'] is False and type(memory['callbacks']) is int and memory['callbacks']==0
         and type(memory['pngBytes']) is int and memory['pngBytes']==0)
    identifier(instance)
    exact(proof['files'],{'removed','absent'})
    for key,operation in (('removed','remove'),('absent','inspect')):
        packet=proof['files'][key]
        exact(packet,{'receiptInventoryVersion','commandId','requestId','operation','instance','sequence','processId','capturedEpochMs','source'})
        identifier(packet['commandId'])
        need(type(packet['receiptInventoryVersion']) is int and packet['receiptInventoryVersion']==1
             and packet['requestId']==capture and packet['operation']==operation and packet['instance']==instance
             and integer(packet['sequence'],1) and integer(packet['processId'],1) and packet['processId']==pid
             and integer(packet['capturedEpochMs'],memory['capturedEpochMs']))
        source=packet['source'];exact(source,{'retired','present','callbacks','pngBytes','complete','receipts'}
            |({'performed'} if operation=='remove' else set()))
        need(source['retired'] is True and source['present'] is False and source['complete'] is True
             and type(source['callbacks']) is int and source['callbacks']==0
             and type(source['pngBytes']) is int and source['pngBytes']==0
             and (operation!='remove' or source['performed'] is True)
             and type(source['receipts']) is list and len(source['receipts'])==len(ids))
        seen=set()
        for row in source['receipts']:
            exact(row,{'receiptId','issued','exists','originalMatches'})
            need(row['receiptId'] in ids and row['receiptId'] not in seen
                 and all(type(row[field]) is bool for field in ('issued','exists','originalMatches'))
                 and row['exists'] is False and row['originalMatches'] is False)
            seen.add(row['receiptId'])
    removed,absent=proof['files']['removed'],proof['files']['absent']
    need(removed['commandId']!=absent['commandId'] and absent['sequence']>removed['sequence']
         and absent['capturedEpochMs']>=removed['capturedEpochMs']
         and {r['receiptId']:r['issued'] for r in removed['source']['receipts']}
             =={r['receiptId']:r['issued'] for r in absent['source']['receipts']})
    return proof


class GraphicsSamples:
    def __init__(self,adapter,selector,client,run,provider_instance,role,stage,lock,artifact_root,image_policy,
                 *,epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic):
        need(isinstance(client,Client) and client.run==run and client.area=='graphics'
             and client.graphics_instance==provider_instance and role in ('primary','actor')
             and type(stage) is int and stage in (0,1) and isinstance(lock,ScriptSourceLock)
             and callable(epoch_ms) and callable(monotonic) and type(image_policy) is dict)
        identifier(run);identifier(provider_instance);stereo_policy(image_policy)
        self.adapter,self.selector,self.client,self.run,self.provider_instance=adapter,selector,client,run,provider_instance
        self.role,self.stage,self.lock,self.artifact_root,self.image_policy=role,stage,lock,Path(artifact_root),deepcopy(image_policy)
        self.epoch_ms,self.monotonic=epoch_ms,monotonic
        path=adapter.state_path(selector);need(lock.path==path.with_name('script-sources.lock'));lock.assert_held()
        self.store=PrivateFeatureState(path.with_name('graphics-'+role+'-'+str(stage)+'-samples.json'))
        _ui,_service,binding,self.guard,_installed=adapter.normal_feature_runtime(selector,read_only=True)
        self.previous=self.store.read()
        self.state=dict(binding=deepcopy(context(binding)),phase='ready',sequence=0,cursors={key:None for key in CURSORS},
            seenFrames=[],images=[],pending=None,frame=None,retirements=[],readiness=[])
        self._marker_token=None
        if self.previous is not None:
            previous=self._decode(self.previous)
            need(same(previous['binding'],binding) and previous['phase']=='ready')
            self.state=previous
        self.images=GraphicsOriginals(self.artifact_root,binding,run,role,stage,self.guard,self._image_intent,monotonic=monotonic)
        if self.state['frame'] is not None:
            self._historical(self.state['frame'])
        if self.state['cursors']['provider'] is not None:
            previous=self.state['cursors']['provider'];current=getattr(self.client,'graphics_previous',None)
            if current is None:self.client.graphics_previous=deepcopy(previous)
            elif not same(current,previous):validate_status(current,instance=self.provider_instance,run=self.run,url=self.client.url,
                request=current['requestId'],previous=previous)

    def _decode(self,value):
        exact(value,{'graphicsSamplesVersion','runId','role','stage','providerInstance','fixtureUrl','artifactRoot','imagePolicy','payload'})
        need(type(value['graphicsSamplesVersion']) is int and value['graphicsSamplesVersion'] in (4,5)
             and (value['graphicsSamplesVersion']!=4 or self.image_policy==PROFILE)
             and value['runId']==self.run and value['role']==self.role and type(value['stage']) is int and value['stage']==self.stage
             and value['providerInstance']==self.provider_instance and value['fixtureUrl']==self.client.url
             and value['artifactRoot']==str(self.artifact_root) and same(value['imagePolicy'],self.image_policy))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0];exact(state,FIELDS);context(state['binding'])
        need(state['phase'] in ('ready','reading') and integer(state['sequence'],0,256)
             and type(state['seenFrames']) is list and len(state['seenFrames'])<=256
             and len(set(state['seenFrames']))==len(state['seenFrames'])
             and type(state['images']) is list and len(state['images'])<=512
             and type(state['retirements']) is list and len(state['retirements'])<=32
             and type(state['readiness']) is list and len(state['readiness'])<=64)
        for frame in state['seenFrames']:identifier(frame)
        pid=int(state['binding']['processIdentity'].split(':')[0]);need(pid>0)
        cursors=state['cursors']
        self._cursors(cursors,pid)
        names=set()
        for image in state['images']:
            image_record(image)
            need(same(image['binding'],state['binding']) and image['runId']==self.run and image['role']==self.role
                 and type(image['stage']) is int and image['stage']==self.stage and image['name'] not in names
                 and image['capture']['source']['renderTrace']['traceVersion']==4
                 and image['capture']['source']['renderTrace']['frameId'] in state['seenFrames'])
            names.add(image['name'])
        last_sequence=0
        event_sequences=set()
        for item in state['retirements']:
            exact(item,{'sequence','ticket','active','provider','cursors','measurement','abandonedImages','markerFrame'})
            need(integer(item['sequence'],last_sequence+1,state['sequence']));last_sequence=item['sequence']
            event_sequences.add(item['sequence'])
            identifier(item['ticket']);self._active(item['active']);need(item['ticket']!=item['active']['ticket'])
            packet=item['provider'];validate_status(packet,instance=self.provider_instance,run=self.run,
                url=self.client.url,request=packet['requestId'])
            need(packet['active'] is True and packet['ticket']==item['active']['ticket'])
            self._cursors(item['cursors'],pid);need(same(item['cursors']['provider'],packet))
            if item['measurement'] is not None:
                proof=item['measurement'];retirement(proof,proof['owner'],pid,state['binding'],self.role)
                need(same(item['cursors']['storage'],proof['memory'])
                     and same(item['cursors']['inventory'],proof['files']['absent']))
            self._abandoned(item['abandonedImages'],state['binding'],item['ticket'])
            if item['markerFrame'] is not None:
                need(item['markerFrame']['ticket']==item['ticket']
                    and all(any(same(item['markerFrame'][kind],image) for image in state['images']) for kind in ('image','metadata')));self._marker_history(item['markerFrame'])
        last_marker=0
        for item in state['readiness']:
            exact(item,{'sequence','ticket','active','provider','cursors','frame','marker'})
            need(integer(item['sequence'],last_marker+1,state['sequence']) and item['sequence'] not in event_sequences)
            last_marker=item['sequence'];event_sequences.add(last_marker);identifier(item['ticket']);self._active(item['active'])
            need(item['active']['ticket']==item['ticket'] and item['frame']['ticket']==item['ticket'])
            need(all(any(same(item['frame'][kind],image) for image in state['images']) for kind in ('image','metadata')))
            provider=item['provider'];validate_status(provider,instance=self.provider_instance,run=self.run,url=self.client.url,request=provider['requestId'])
            need(provider['active'] and provider['ticket']==item['ticket'])
            self._cursors(item['cursors'],pid);need(same(item['cursors']['provider'],provider))
            need(same(item['marker'],self._marker_history(item['frame'])))
            self._frame_cursors(item['frame'],item['cursors'],include_provider=False)
        if state['phase']=='ready':
            need(state['pending'] is None and all(image['phase']=='saved' for image in state['images']))
            if state['sequence']==0:need(state['frame'] is None and not state['images'] and not state['seenFrames']
                and all(packet is None for packet in cursors.values()) and not state['retirements'] and not state['readiness'])
            else:
                last_retired=max(last_sequence,last_marker)==state['sequence']
                frame=state['frame'];need(type(frame) is dict or last_retired)
                if frame is not None:
                    need(all(any(same(frame[kind],image) for image in state['images']) for kind in ('image','metadata')))
                    retirement(frame['retirement'],frame['retirement']['owner'],pid,state['binding'],self.role)
                    if not last_retired:
                        self._frame_cursors(frame,cursors)
                if last_retired:
                    last=state['retirements'][-1] if last_sequence>last_marker else state['readiness'][-1]
                    need(same(cursors,last['cursors']))
        else:
            pending=state['pending'];exact(pending,{'ticket','afterEpochMs','captureIntent','retirement','abandonedImages','markerFrame'})
            identifier(pending['ticket']);need(integer(pending['afterEpochMs'],1))
            if pending['captureIntent'] is not None:WorldRenderOwner.acquisition(pending['captureIntent'])
            if pending['retirement'] is not None:retirement(pending['retirement'],pending['retirement']['owner'],pid,state['binding'],self.role)
            self._abandoned(pending['abandonedImages'],state['binding'],pending['ticket'])
            if pending['markerFrame'] is not None:
                frame=pending['markerFrame'];need(type(frame) is dict and frame['ticket']==pending['ticket'])
                if frame['retirement'] is not None:self._marker_history(frame)
        return state

    @staticmethod
    def _frame_cursors(frame,cursors,*,include_provider=True):
        need(same(frame['nativeAfter'],cursors['native']) and same(frame['subjectAfter'],cursors['subject'])
             and same(frame.get('graphicsAfter',frame['graphics']),cursors['graphics']) and same(frame['tablet'],cursors['tablet'])
             and same(frame['capture'],cursors['capture']) and (not include_provider or same(frame['provider'],cursors['provider']))
             and same(cursors['storage'],frame['retirement']['memory']) and same(cursors['inventory'],frame['retirement']['files']['absent']))

    def _marker_history(self,frame):
        try:self._historical(frame)
        except MarkerNotReady as error:return deepcopy(error.observation)
        raise NativeUIError('Original Graphics readiness history unexpectedly contains a valid current frame')

    def _cursors(self,rows,pid):
        exact(rows,CURSORS)
        for key,validator,nonce in (('native',native_packet,'requestId'),('graphics',graphics_packet,'commandId'),
                                    ('tablet',tablet_packet,'commandId'),('capture',capture_packet,'requestId')):
            packet=rows[key]
            if packet is not None:validator(packet,identifier(packet.get(nonce)),pid,packet.get('capturedEpochMs'))
        if rows['subject'] is not None:
            packet=rows['subject'];subject_packet(packet,dict(schemaVersion=1,commandId=packet['requestId'],
                action='feature-graphics-subject-observe',runId=self.run),pid,packet['capturedEpochMs'],require_avatar=True,require_framework=True)
        if rows['provider'] is not None:
            packet=rows['provider'];validate_status(packet,instance=self.provider_instance,run=self.run,
                url=self.client.url,request=packet['requestId'])

    def _abandoned(self,rows,binding,ticket):
        need(type(rows) is list and len(rows)<=2)
        for absence in rows:
            exact(absence,{'image','absent','observedEpochMs'});image_record(absence['image'])
            need(absence['absent'] is True and integer(absence['observedEpochMs'],1)
                 and absence['image']['phase']=='planned' and absence['image']['ticket']==ticket
                 and absence['image']['runId']==self.run and absence['image']['role']==self.role
                 and type(absence['image']['stage']) is int and absence['image']['stage']==self.stage
                 and same(absence['image']['binding'],binding))

    def save(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))
        value=dict(graphicsSamplesVersion=VERSION,runId=self.run,role=self.role,stage=self.stage,providerInstance=self.provider_instance,
            fixtureUrl=self.client.url,artifactRoot=str(self.artifact_root),imagePolicy=self.image_policy,payload=pack([self.state]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def _image_intent(self,value):
        need(self.state['phase']=='reading' and self.state['pending']['ticket']==value['ticket'])
        rows=self.state['images'];found=[index for index,row in enumerate(rows) if row['name']==value['name']]
        if found:
            need(len(found)==1);image_transition(rows[found[0]],value);rows[found[0]]=deepcopy(value)
        else:
            need(len(rows)<512);image_transition(None,value);rows.append(deepcopy(value))
        self.save()

    def _active(self,value):
        exact(value,{'schemaVersion','runId','area','ticket','stimulus'})
        need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['runId']==self.run
             and value['area']=='graphics');identifier(value['ticket']);exact(value['stimulus'],{'verb','inputs'})
        if value['stimulus']['verb'] in ('baseline','cleanup'):need(value['stimulus']['inputs']=={})
        else:arguments('feature.graphics.act',dict(contractVersion=FEATURE_VERSION,runId=self.run,
            fixtureUrl=self.client.url+'/runs/'+self.run+'/',ticket=value['ticket'],**value['stimulus']))
        return value

    def _release_measurement(self,owned,pid,bound):
        need(same(owned.owner.owned()['capture'],self.state['pending']['captureIntent']))
        memory=owned.storage.release(owned.owner.owned()['capture']['commandId']);bound()
        self.state['cursors']['storage']=deepcopy(memory);self.save();bound()
        owner=deepcopy(owned.owner.owned())
        original=owned.receipts.cleanup.request
        def remember_inventory(operation):
            packet=original(operation)
            self.state['cursors']['inventory']=deepcopy(packet);self.save();bound()
            return packet
        owned.receipts.cleanup.request=remember_inventory
        owned.receipts.retire();bound()
        proof=dict(memory=memory,files=deepcopy(owned.receipts.proof),owner=owner)
        retirement(proof,owner,pid,self.state['binding'],self.role)
        self.state['pending']['retirement']=deepcopy(proof);self.save();bound()
        need(owned.owner.owned()==owner);owned.owner.store.discard(owner)
        need(owned.owner.store.read() is None);bound()
        return proof

    def _track_storage(self,owned,bound):
        original=owned.storage.request
        def remember(operation,request,offset=None):
            packet=original(operation,request,offset)
            cursor=deepcopy(packet)
            if 'data' in cursor:
                cursor['chunkSha256']=hashlib.sha256(base64.b64decode(cursor.pop('data'),validate=True)).hexdigest()
            self.state['cursors']['storage']=cursor;self.save();bound()
            return packet
        owned.storage.request=remember

    def retire_marker_not_ready(self):
        """Retire only this live, fully proved invalid-marker acquisition.

        No inputs, old-fact publication, context reset or recreated pending
        journal is admitted. The next measurement needs an entirely new frame.
        """
        self.lock.assert_held();pending=self.state['pending']
        need(self.state['phase']=='reading' and pending is not None and pending['markerFrame'] is not None
            and self._marker_token is not None and len(self.state['readiness'])<64 and self.state['sequence']<256)
        frame=pending['markerFrame'];need(frame['capture']['requestId']==self._marker_token
            and same(pending['captureIntent'],frame['retirement']['owner']['capture'])
            and same(pending['retirement'],frame['retirement']) and not pending['abandonedImages'])
        started=previous=self.monotonic();need(number(started,0,1e15))
        def bound():
            nonlocal previous
            self.lock.assert_held();need(self.guard() is not False)
            current=self.monotonic();need(number(current,previous,1e15) and current-started<20);previous=current
        self._frame_cursors(frame,self.state['cursors']);marker=self._marker_history(frame);bound()
        owned=self.adapter._world_render_capture(self.selector,read_only=True,role=self.role,require_frame_view=True,source_lock=self.lock)
        need(owned.owner.store.read() is None);bound()
        active=deepcopy(self._active(self.client.request('/runs/'+self.run+'/active')))
        need(active['ticket']==pending['ticket']);bound()
        provider=self.client.graphics_status();bound()
        validate_status(provider,instance=self.provider_instance,run=self.run,url=self.client.url,request=provider['requestId'],
            previous=self.state['cursors']['provider'])
        need(provider['active'] and provider['ticket']==pending['ticket']);fresh(provider['capturedEpochMs'],self.epoch_ms())
        confirmed=self._active(self.client.request('/runs/'+self.run+'/active'));need(same(confirmed,active));bound()
        cursors=deepcopy(self.state['cursors']);cursors['provider']=deepcopy(provider)
        item=dict(sequence=self.state['sequence']+1,ticket=pending['ticket'],active=active,provider=deepcopy(provider),
            cursors=deepcopy(cursors),frame=deepcopy(frame),marker=marker)
        self.state.update(phase='ready',sequence=item['sequence'],cursors=cursors,pending=None,readiness=self.state['readiness']+[item])
        self.save();bound();self._marker_token=None
        return deepcopy(item) # Rejected original image/history only, never feature state.

    def retire_changed_ticket(self):
        """Retire this live interrupted acquisition, without publishing facts.

        Recreation cannot enter this path: construction refuses reading journals.
        A missing original capture, partial PNG or unchanged phase stays red.
        """
        self.lock.assert_held()
        need(self.state['phase']=='reading' and self.state['pending'] is not None
             and len(self.state['retirements'])<32 and self.state['sequence']<256)
        started=previous=self.monotonic();need(number(started,0,1e15))
        def bound():
            nonlocal previous
            self.lock.assert_held();need(self.guard() is not False)
            current=self.monotonic();need(number(current,previous,1e15) and current-started<20);previous=current
        active=deepcopy(self._active(self.client.request('/runs/'+self.run+'/active')));bound()
        pending=self.state['pending'];need(active['ticket']!=pending['ticket'])
        owned=self.adapter._world_render_capture(self.selector,read_only=True,role=self.role,require_frame_view=True,source_lock=self.lock)
        capture=self.state['cursors']['capture']
        if pending['captureIntent'] is not None:
            need(capture is not None and capture['requestId']==pending['captureIntent']['commandId'])
        if owned.owner.store.read() is not None:
            need(pending['captureIntent'] is not None and same(owned.owner.owned()['capture'],pending['captureIntent']))
            stored=self.state['cursors']['storage'];inventory=self.state['cursors']['inventory']
            owned.storage.instance=capture['instance']
            if stored is not None:
                need(stored['instance']==capture['instance']);owned.storage.sequence=stored['sequence']
            if inventory is not None:
                need(inventory['instance']==capture['instance'])
                owned.receipts.cleanup.sequence,owned.receipts.cleanup.captured=inventory['sequence'],inventory['capturedEpochMs']
                owned.receipts.cleanup.histories[inventory['requestId']]={row['receiptId']:row['issued'] for row in inventory['source']['receipts']}
            self._track_storage(owned,bound)
            self._release_measurement(owned,int(self.state['binding']['processIdentity'].split(':')[0]),bound)
        if pending['captureIntent'] is not None:
            need(pending['retirement'] is not None and pending['retirement']['memory']['instance']==capture['instance'])
        need(owned.owner.store.read() is None)
        for absence in pending['abandonedImages']:need(self.images.absent(absence['image']) is True);bound()
        for image in list(self.state['images']):
            if image['ticket']!=pending['ticket']:continue
            if image['phase']=='planned':
                need(self.images.absent(image) is True);bound()
                pending['abandonedImages'].append(dict(image=deepcopy(image),absent=True,observedEpochMs=self.epoch_ms()))
                self.state['images'].remove(image);self.save();bound()
            else:
                self.images.read(image);bound()
                if image['phase']=='opened':
                    image=deepcopy(image);image['phase']='saved';self._image_intent(image);bound()
        provider=self.client.graphics_status();bound()
        validate_status(provider,instance=self.provider_instance,run=self.run,url=self.client.url,request=provider['requestId'],
            previous=self.state['cursors']['provider'])
        need(provider['active'] is True and provider['ticket']==active['ticket']);fresh(provider['capturedEpochMs'],self.epoch_ms())
        self.state['cursors']['provider']=deepcopy(provider);self.save();bound()
        confirmed=self._active(self.client.request('/runs/'+self.run+'/active'));need(same(confirmed,active));bound()
        item=dict(sequence=self.state['sequence']+1,ticket=pending['ticket'],active=active,provider=deepcopy(provider),
            cursors=deepcopy(self.state['cursors']),measurement=deepcopy(pending['retirement']),abandonedImages=deepcopy(pending['abandonedImages']),
            markerFrame=deepcopy(pending['markerFrame']))
        if item['markerFrame'] is not None:
            item['markerFrame']['retirement']=deepcopy(pending['retirement']);self._marker_history(item['markerFrame'])
        self.state.update(phase='ready',sequence=item['sequence'],pending=None,retirements=self.state['retirements']+[item])
        self.save();bound();self._marker_token=None
        return deepcopy(item) # Scope/history retirement only; no measured feature state.

    def _historical(self,frame):
        exact(frame,frame_fields(frame))
        raw=GraphicsOriginals.archive(self.artifact_root,frame['image'])
        need(same(frame['capture'],frame['image']['capture']) and frame['ticket']==frame['image']['ticket'])
        metadata=GraphicsOriginals.archive(self.artifact_root,frame['metadata'])
        need(frame['image']['kind']=='image' and frame['image']['phase']=='saved' and frame['metadata']['kind']=='file'
            and frame['metadata']['phase']=='saved' and frame['metadata']['ticket']==frame['ticket']
            and same(frame['metadata']['binding'],frame['image']['binding'])
            and metadata==metadata_bytes(frame,frame['image']['binding'],self.run,self.role,self.stage,self.client.url+'/runs/'+self.run+'/'))
        packet=frame['provider'];validate_status(packet,instance=self.provider_instance,run=self.run,url=self.client.url,request=packet['requestId'])
        retirement(frame['retirement'],frame['retirement']['owner'],frame['nativeAfter']['processId'],frame['image']['binding'],self.role)
        need(frame['retirement']['owner']['capture']['commandId']==frame['capture']['requestId']
             and frame['retirement']['memory']['instance']==frame['capture']['instance'])
        return compose(self.run,frame,raw,frame['image']['binding'],self.role,self.stage,self.client.url+'/runs/'+self.run+'/',self.image_policy)

    @classmethod
    def archive(cls,value,*,client,run,provider_instance,role,stage,binding,artifact_root,image_policy):
        """Pure historical validation. No SDK, input, repair or current result."""
        scope=object.__new__(cls);scope.client,scope.run,scope.provider_instance=client,run,provider_instance
        scope.role,scope.stage,scope.artifact_root,scope.image_policy=role,stage,Path(artifact_root),deepcopy(image_policy)
        state=scope._decode(value);need(state['phase']=='ready' and same(state['binding'],context(binding)))
        for image in state['images']:GraphicsOriginals.archive(scope.artifact_root,image)
        files=GraphicsOriginals(scope.artifact_root,binding,run,role,stage,lambda:True,lambda _:False)
        for item in state['retirements']:
            for absence in item['abandonedImages']:need(files.absent(absence['image']) is True)
        if state['frame'] is not None:scope._historical(state['frame'])
        return deepcopy(state)

    def read(self,ticket,after_epoch):
        identifier(ticket);need(integer(after_epoch,1));self.lock.assert_held()
        need(self.state['phase']=='ready' and self.state['sequence']<256 and len(self.state['seenFrames'])<256)
        self._marker_token=None
        self.state.update(phase='reading',pending=dict(ticket=ticket,afterEpochMs=after_epoch,captureIntent=None,retirement=None,abandonedImages=[],markerFrame=None));self.save()
        started=previous=self.monotonic();need(number(started,0,1e15))
        def bound():
            nonlocal previous
            self.lock.assert_held();need(self.guard() is not False)
            current=self.monotonic();need(number(current,0,1e15) and previous<=current and current-started<20);previous=current
        def remember(key,packet):
            old=self.state['cursors'][key]
            if old is not None:
                need(packet['capturedEpochMs']>=old['capturedEpochMs'])
            self.state['cursors'][key]=deepcopy(packet);self.save();bound()
        native=self.adapter._native_feature_observer(self.selector,read_only=True);restore_native(native,self.state['cursors']['native'])
        subject=self.adapter._graphics_subject_observer(self.selector,read_only=True)
        subject.last=deepcopy(self.state['cursors']['subject'])
        ui=self.adapter._graphics_ui_observer(self.selector,read_only=True)
        restore_ui(ui,self.state['cursors']['graphics'],graphics_packet)
        tablet=self.adapter._script_file_io(self.selector,read_only=True)
        restore_ui(tablet,self.state['cursors']['tablet'],tablet_packet)
        owned=self.adapter._world_render_capture(self.selector,read_only=True,role=self.role,require_frame_view=True,source_lock=self.lock)
        need(owned.owner.store.read() is None)
        original_send=owned.capture.send
        def send_capture(command):
            need(same(owned.owner.owned()['capture'],command) and self.state['pending']['captureIntent'] is None)
            self.state['pending']['captureIntent']=deepcopy(command);self.save();bound()
            original_send(command)
        owned.capture.send=send_capture
        previous_capture=self.state['cursors']['capture']
        if previous_capture is not None:
            source=previous_capture['source'];reader=owned.capture
            reader.instance,reader.sequence=previous_capture['instance'],previous_capture['sequence']
            reader.acquisition,reader.captured=source['acquisitionSequence'],source['capturedEpochMs']
            reader.trace_frame=source['renderTrace']['frameId']
            reader.frame,reader.execution,reader.submission=source['stereo']['frameIndex'],source['stereo']['executionSequence'],source['presentation']['submissionSequence']
            reader.camera_batch_sequence=source['renderTrace']['cameraBatches'][-1]['sequence']
        stored=self.state['cursors']['storage'];inventory=self.state['cursors']['inventory']
        if stored is not None:owned.storage.instance,owned.storage.sequence=stored['instance'],stored['sequence']
        if inventory is not None:owned.receipts.cleanup.sequence,owned.receipts.cleanup.captured=inventory['sequence'],inventory['capturedEpochMs']
        self._track_storage(owned,bound)
        bound()
        marker_error=None
        try:
            acquisition_started=self.monotonic();need(number(acquisition_started,previous,1e15));previous=acquisition_started
            before=native.read(native.sequence);remember('native',before)
            first=subject.read(self.run);remember('subject',first)
            graphics=ui.capture();remember('graphics',graphics)
            tabs=tablet.capture();remember('tablet',tabs)
            capture,raw=owned.read(owned.capture.sequence);remember('capture',capture)
            graphics_after=None
            if self.image_policy==SURFACE_PROFILE:
                graphics_after=ui.capture();remember('graphics',graphics_after)
            frame_id=capture['source']['renderTrace']['frameId'];need(frame_id not in self.state['seenFrames'])
            self.state['seenFrames'].append(frame_id);self.save();bound()
            last=subject.read(self.run);remember('subject',last)
            after=native.read(native.sequence);remember('native',after)
            provider=self.client.graphics_status();bound()
            validate_status(provider,instance=self.provider_instance,run=self.run,url=self.client.url,request=provider['requestId'],
                previous=self.state['cursors']['provider'])
            remember('provider',provider)
            sample_epoch=native.clock_ms();need(integer(sample_epoch,after['capturedEpochMs']))
            facts=dict(ticket=ticket,afterEpochMs=after_epoch,nativeBefore=before,subjectBefore=first,graphics=graphics,tablet=tabs,
                capture=capture,subjectAfter=last,nativeAfter=after,provider=provider)
            if graphics_after is not None:facts['graphicsAfter']=graphics_after
            try:actual=compose(self.run,facts,raw,self.state['binding'],self.role,self.stage,self.client.url+'/runs/'+self.run+'/',self.image_policy)
            except MarkerNotReady as error:marker_error=deepcopy(error.observation)
            image=self.images.write(ticket,capture,raw);bound()
            metadata=self.images.write(ticket,capture,metadata_bytes(facts,self.state['binding'],self.run,self.role,self.stage,
                self.client.url+'/runs/'+self.run+'/'),kind='file');bound()
            if marker_error is not None:
                self.state['pending']['markerFrame']=dict(facts,image=image,metadata=metadata,retirement=None)
                self.save();bound()
        finally:
            if owned.owner.store.read() is not None:
                # Capture/storage ownership is separately durable before every
                # dispatch, including a failed or undelivered acquisition.
                self._release_measurement(owned,native.pid,bound)
        need(self.state['pending']['retirement'] is not None and owned.owner.store.read() is None)
        captured=actual['capturedEpochMs'] if marker_error is None else min(before['capturedEpochMs'],provider['capturedEpochMs'])
        current_epoch=native.clock_ms();need(integer(current_epoch,sample_epoch));fresh(captured,current_epoch);bound()
        frame=dict(facts,image=image,metadata=metadata,retirement=self.state['pending']['retirement'])
        if marker_error is not None:
            self.state['pending']['markerFrame']=deepcopy(frame);self.save();bound()
            need(same(marker_error,self._marker_history(frame)))
            freshness_started=self.monotonic();need(number(freshness_started,previous,1e15))
            final_epoch=native.clock_ms();need(integer(final_epoch,current_epoch));fresh(captured,final_epoch);bound()
            need(max(final_epoch-captured+math.ceil((previous-freshness_started)*1000),
                before['capturedEpochMs']-captured+math.ceil((previous-acquisition_started)*1000))<=1500)
            self._marker_token=capture['requestId']
            raise GraphicsMarkerPending('Original Graphics pixels do not yet contain the current challenge')
        self.state.update(phase='ready',sequence=self.state['sequence']+1,pending=None,frame=frame)
        self.save();bound()
        freshness_started=self.monotonic();need(number(freshness_started,previous,1e15))
        final_epoch=native.clock_ms();need(integer(final_epoch,current_epoch));fresh(actual['capturedEpochMs'],final_epoch)
        bound()
        need(max(final_epoch-actual['capturedEpochMs']+math.ceil((previous-freshness_started)*1000),
            before['capturedEpochMs']-actual['capturedEpochMs']+math.ceil((previous-acquisition_started)*1000))<=1500)
        return deepcopy(dict(sequence=self.state['sequence'],imagePath=str(self.artifact_root/image['name']),metadataPath=str(self.artifact_root/metadata['name']),**actual))
