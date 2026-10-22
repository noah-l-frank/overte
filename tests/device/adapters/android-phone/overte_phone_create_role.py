"""Independent role acquisition over concrete native Create/render sources."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import math

from adapters.native_feature_observation import exact,fresh,integer,need,validate as native_packet
from adapters.native_avatar_render import validate as avatar_packet
from adapters.native_world_model_draws import validate as draw_packet
from adapters.normal_feature_state import PrivateFeatureState
from adapters.world_render_evidence import original_pixels
from feature_journeys.contract import result
from feature_journeys.evidence import image_observation,rectangle,MarkerNotReady
from feature_journeys.phase_fixture import validate as phase_packet
from feature_journeys.scenarios import VERSION
from overte_phone_create_controls import validate as ui_packet
from overte_phone_create_source import validate as entity_packet
from overte_phone_create_marker import ready as marker_ready,retired as marker_retired
from adapters.normal_ui import NativeUIError
from adapters.native_phone_web_runtime import active_marker,released as web_released
from overte_phone_create_evidence import CreateOriginals,CreateImages
from overte_phone_create_measurements import facts,model,CreatePending
from overte_phone_graphics_effects import projected_box
from overte_phone_graphics_samples import restore_native,restore_ui,retirement
from overte_phone_script_history import pack,unpack,same


class PhoneCreateRole:
    def __init__(self,feature,role):
        need(role in ('primary','actor'));feature.lock.assert_held()
        self.feature,self.role=feature,role;self.store=PrivateFeatureState(feature.store.path.with_name('phone-create-'+role+'-originals.json'))
        self.previous=self.store.read();self.state=dict(phase='ready',sequence=0,manifests=[],pending=None,baselineVoxel=None)
        self.originals=CreateOriginals(feature.root,feature.binding,feature.run,role,self.bound,self.storage_intent,kind='create')
        if self.previous is not None:
            value=self.previous;exact(value,{'createRoleVersion','runId','binding','role','payload'})
            need(value['createRoleVersion']==1 and type(value['createRoleVersion']) is int and value['runId']==feature.run
                and same(value['binding'],feature.binding) and value['role']==role)
            rows=unpack(value['payload']);need(len(rows)==1);self.state=rows[0]
            exact(self.state,{'phase','sequence','manifests','pending','baselineVoxel'})
            need(self.state['phase'] in ('ready','reading','retired') and integer(self.state['sequence'],0,256))
        self.frames=self.originals.restore(self.state['manifests'],self.state['sequence'])
        self.native=feature.adapter._native_feature_observer(feature.selector,read_only=True)
        self.entities=feature.adapter._create_source(feature.selector,read_only=True)
        self.ui=feature.adapter._create_controls(feature.selector,lambda *_:need(False),read_only=True)
        self.avatar=feature.adapter._avatar_render_observer(feature.selector,read_only=True)
        self.draws=feature.adapter._world_model_draws_observer(feature.selector,read_only=True)
        if self.frames:
            for key,restore in (('nativeAfter',lambda value:restore_native(self.native,value)),
                    ('entitiesAfter',lambda value:setattr(self.entities,'last',deepcopy(value))),
                    ('uiOriginal',lambda value:restore_ui(self.ui.io,value,ui_packet)),
                    ('avatarAfter',lambda value:self.avatar.restore([value])),
                    ('draws',lambda value:setattr(self.draws,'last',deepcopy(value)))):
                value=next((frame[key] for frame in reversed(self.frames) if frame.get(key) is not None),None)
                if value is not None:restore(value)
        historical=list(self.frames)
        if self.state['pending'] is not None:historical.append(self.state['pending'].get('work',{}))
        baselines=[row for frame in historical for row in frame.get('entitiesAfter',{}).get('source',{}).get('entities',[]) if row['type']=='PolyVox' and row['voxel']['ready'] and row['voxel']['cells'] is not None]
        if self.state['baselineVoxel'] is not None:need(baselines and same(self.state['baselineVoxel'],baselines[0]))
        self.web=feature.adapter._web_runtime_observer(feature.selector,read_only=True)
        previous_web=next((frame['web'] for frame in reversed(self.frames) if frame.get('web') is not None),None)
        if previous_web is not None:self.web.last=deepcopy(previous_web)
        if self.previous is None:self.save()

    def bound(self):
        self.feature.bound();need(same(self.store.read(),self.previous));return True

    def save(self):
        self.bound();value=dict(createRoleVersion=1,runId=self.feature.run,binding=self.feature.binding,role=self.role,payload=pack([self.state]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def storage_intent(self,kind,value):
        self.bound();need(self.state['phase']=='reading' and kind in ('original','manifest'))
        old=self.state['pending'][kind]
        if old is not None:
            need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase']) if kind=='original' else value['phase']=='saved' and old['phase']=='planned')
        self.state['pending'][kind]=deepcopy(value);self.save();return True

    def image_intent(self,value):
        need(self.state['phase']=='reading');old=self.state['pending']['image']
        if old is None:need(value['phase']=='planned')
        else:need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase']) and same({key:item for key,item in old.items() if key not in ('phase','file')},{key:item for key,item in value.items() if key not in ('phase','file')}))
        self.state['pending']['image']=deepcopy(value);self.save();return True

    def release_capture(self,owned):
        memory=owned.storage.release(owned.owner.owned()['capture']['commandId']);owner=deepcopy(owned.owner.owned())
        owned.receipts.retire();proof=dict(memory=memory,files=deepcopy(owned.receipts.proof),owner=owner)
        retirement(proof,owner,self.feature.pid,self.feature.binding,self.role)
        self.state['pending']['retirement']=proof;self.save()
        need(same(owned.owner.owned(),owner));owned.owner.store.discard(owner);need(owned.owner.store.read() is None)
        return proof

    def pixels(self,frame,raw):
        f=self.feature;capture=frame['capture'];original_pixels(capture,raw)
        need(capture['source']['targetExtent']==f.config['imageExtent'])
        image_observation(raw,f.run,frame['ticket'],f.policy)
        draw_packet(frame['draws'],dict(schemaVersion=1,commandId=frame['draws']['requestId'],
            action='feature-world-model-draws-observe',captureRequestId=capture['requestId']),f.pid,frame['epochMs'],capture=capture)
        before,after=frame['entitiesBefore']['source'],frame['entitiesAfter']['source']
        for row in after['entities']:
            if row['type'] not in ('Model','PolyVox'):continue
            prior=[item for item in before['entities'] if item['id']==row['id']]
            if len(prior)!=1:return False
            a,b=deepcopy(prior[0]),deepcopy(row)
            for item in (a,b):
                if item['render'] is not None:item['render'].pop('recordedEpochMs')
            if not same(a,b):return False
            if row['type']=='Model' and (row['render'] is None or not row['render']['loaded']
                    or not row['render']['geometry']['textures']['complete']):return False
            geometry_row=row
            if row['type']=='Model':
                render,geometry=model(row);trace=frame['draws']['source']['modelTrace']
                matches=[item for item in trace['models'] if item['modelInstance']==render['modelInstance']
                    and item['geometryInstance']==geometry['instance'] and item['loadedSourcePresent']
                    and item['loadedSourceSha256']==geometry['sourceSha256'] and item['originalGeometryDrawCommands']>0]
                need(len(matches)==1 and render['recordedEpochMs']<=capture['source']['renderTrace']['recordedEpochMs'])
                draw=matches[0];center=[(a+b)/2 for a,b in zip(draw['minimum'],draw['maximum'])]
                # The two fixed normal model fixtures have centered registration.
                # A live draw of an old transform cannot satisfy new properties.
                need(all(abs(a-b)<=.005 for a,b in zip(center,row['position'])))
                geometry_row=dict(position=center,dimensions=[b-a for a,b in zip(draw['minimum'],draw['maximum'])],rotation=[0,0,0,1])
            box=projected_box(geometry_row,capture['source']['renderTrace']['recordedView'],capture['source']['targetExtent'])
            roi=[math.floor(box[0]),math.floor(box[1]),math.ceil(box[2]),math.ceil(box[3])]
            subject=rectangle(f.policy['subject'],capture['source']['targetExtent']);rectangle(roi,capture['source']['targetExtent'])
            need(roi[2]-roi[0]>=24 and roi[3]-roi[1]>=24 and subject[0]<=roi[0] and subject[1]<=roi[1] and subject[2]>=roi[2] and subject[3]>=roi[3]
                and (subject[2]-subject[0])*(subject[3]-subject[1])<=2*(roi[2]-roi[0])*(roi[3]-roi[1]))
        return True

    def checkpoint(self,**values):
        self.state['pending']['work'].update(deepcopy(values));self.save()

    def finish_archive(self,frame):
        pending=self.state['pending'];pending['frame']=deepcopy(frame);self.save()
        index=self.state['sequence']+1
        ref=(self.originals.write(index,frame) if pending['original'] is None else
             self.originals.resume_write(index,frame,pending['original']))
        manifests=(self.originals.append(self.state['manifests'],ref) if pending['manifest'] is None else
             self.originals.resume_manifest(self.state['manifests'],ref,pending['manifest']))
        self.state.update(phase='ready',sequence=index,manifests=manifests,pending=None);self.save();self.frames.append(deepcopy(frame))

    def recover(self):
        self.bound();need(self.state['phase']=='reading');pending=self.state['pending']
        owned=self.feature.adapter._world_render_capture(self.feature.selector,read_only=True,role=self.role,require_trace=True,require_frame_view=True)
        image=pending.get('image')
        if image is not None and image['phase']!='saved':
            engine=CreateImages(self.feature.root,self.feature.binding,self.feature.run,self.role,self.state['sequence']+1,self.bound,self.image_intent)
            if owned.owner.store.read() is not None:
                capture=pending['work']['capture'];need(owned.owner.owned()['capture']['commandId']==capture['requestId'])
                owned.storage.bind(capture);raw=owned.storage.read(capture['source']['image']['name']);engine.resume(image,raw)
            else:need(image['phase']=='planned' and engine.absent(image))
        if owned.owner.store.read() is not None:self.release_capture(owned)
        if pending.get('frame') is not None:frame=pending['frame']
        else:frame=dict(pending['work'],diagnostic=True,retirement=pending.get('retirement'),image=pending.get('image'))
        self.finish_archive(frame)

    def read(self,after_sequence):
        try:return self.acquire(after_sequence)
        except CreatePending:
            self.recover();raise

    def acquire(self,after_sequence):
        f=self.feature;self.bound();need(self.state['phase']=='ready' and integer(after_sequence,0,self.state['sequence']) and self.state['sequence']<256)
        self.state.update(phase='reading',pending=dict(original=None,manifest=None,image=None,retirement=None,frame=None,work={}));self.save()
        phase_before=f.phase.status();need(phase_before['active'] and phase_before['activations']);active=phase_before['activations'][-1];ticket=active['ticket']
        self.checkpoint(ticket=ticket,phaseBefore=phase_before)
        native_before=self.native.read(self.native.sequence);before=self.entities.read(f.run,sorted(row['id'] for row in f.state['objects']))
        avatar_before=self.avatar.read();ui=self.ui.capture();ui_original=deepcopy(self.ui.io.last_original)
        self.checkpoint(nativeBefore=native_before,entitiesBefore=before,avatarBefore=avatar_before,ui=ui,uiOriginal=ui_original)
        web=self.web.read(f.run,f.fixture_url);self.checkpoint(web=web)
        capture=draws=image=proof=marker=None;image_ready=False
        if f.state['marker'] is not None and f.state['marker']['operation']=='prepare':
            marker=f.adapter._create_fixture_observer(f.selector,read_only=True).read(f.run);marker_ready(marker,avatar_before)
            marker_rows=[row for row in marker['source']['entities'] if row['role']=='marker'];need(len(marker_rows)==1)
            active_marker(web,marker_rows[0]['sourceUrl']);self.checkpoint(marker=marker)
            owned=f.adapter._world_render_capture(f.selector,read_only=True,role=self.role,require_trace=True,require_frame_view=True)
            need(owned.owner.store.read() is None)
            captures=[frame['capture'] for frame in self.frames if frame.get('capture') is not None]
            if captures:
                last=captures[-1];reader=owned.capture
                reader.instance,reader.sequence=last['instance'],last['sequence']
                reader.acquisition,reader.captured=last['source']['acquisitionSequence'],last['source']['capturedEpochMs']
                reader.frames={packet['source']['renderTrace']['frameId'] for packet in captures}
            capture,raw=owned.read(owned.capture.sequence);self.checkpoint(capture=capture)
            self.state['pending']['capture']=deepcopy(owned.owner.owned());self.save()
            draws=self.draws.read(capture);self.checkpoint(draws=draws)
            image=CreateImages(f.root,f.binding,f.run,self.role,self.state['sequence']+1,self.bound,self.image_intent).write(ticket,capture,raw)
            proof=self.release_capture(owned)
        ui_before,ui_before_original=ui,ui_original
        ui=self.ui.capture();ui_original=deepcopy(self.ui.io.last_original)
        need(all(ui['scope'][key]==ui_before['scope'][key] for key in ('instance','generation','sequence','processId')))
        avatar_after=self.avatar.read();after=self.entities.read(f.run,sorted(row['id'] for row in f.state['objects']))
        native_after=self.native.read(self.native.sequence);phase_after=f.phase.status(phase_before)
        self.checkpoint(nativeAfter=native_after,entitiesAfter=after,avatarAfter=avatar_after,phaseAfter=phase_after)
        files=None
        if f.state['filesLease']:
            metadata=PrivateFeatureState(f.store.path.with_name('phone-create-files-owner.json')).read()
            need(metadata is not None and metadata['binding']==f.binding and metadata['runId']==f.run)
            files=f.adapter._create_files(f.selector,read_only=True).request('observe',f.run,metadata['ownerToken'])
        touch=world=None
        if f.state['phase']=='cleaned':
            touch=f.adapter._touch_state_observer(f.selector,read_only=True).read()
            world=f.adapter._graphics_subject_observer(f.selector,read_only=True).read(f.run,require_avatar=True)
        if f.state['marker'] is not None and f.state['marker']['operation']=='release':
            marker=f.adapter._create_fixture_observer(f.selector,read_only=True).read(f.run);marker_retired(marker);web_released(web)
        epoch=self.native.clock_ms();self.checkpoint(files=files,epochMs=epoch,touch=touch,world=world,marker=marker)
        need(same(phase_before['activations'],phase_after['activations']) and phase_before['active']==phase_after['active'])
        for packet in (before,after):
            entity_packet(packet,dict(schemaVersion=1,commandId=packet['requestId'],action='phone-create-observe',runId=f.run,
                trackedIds=sorted(row['id'] for row in f.state['objects'])),f.pid,epoch)
            need(packet['source']['connected'] and packet['source']['domainId']==f.state['domainId']
                and packet['source']['sessionId']==f.state['nativeSessionId'])
        for packet in (native_before,native_after):native_packet(packet,packet['requestId'],f.pid,epoch)
        for packet in (avatar_before,avatar_after):avatar_packet(packet,dict(schemaVersion=1,commandId=packet['requestId'],action='feature-avatar-render-observe'),f.pid,epoch)
        ui_packet(ui_original,ui_original['commandId'],f.pid,epoch)
        ui_packet(ui_before_original,ui_before_original['commandId'],f.pid,epoch)
        voxel=[row for row in after['source']['entities'] if row['type']=='PolyVox']
        if voxel and self.state['baselineVoxel'] is None:
            from overte_phone_create_fixture import voxel_cells
            if any(not row['voxel']['ready'] or row['voxel']['cells'] is None for row in voxel):raise CreatePending()
            need(len(voxel)==1 and voxel[0]['voxel']['cells']==dict(sha256=hashlib.sha256(voxel_cells()).hexdigest(),occupied=64))
            self.state['baselineVoxel']=deepcopy(voxel[0])
        measured=facts(f.run,f.fixture_url,after,ui,f.state['objects'],self.state['baselineVoxel'])
        frame=dict(ticket=ticket,phaseBefore=phase_before,phaseAfter=phase_after,nativeBefore=native_before,nativeAfter=native_after,
            entitiesBefore=before,entitiesAfter=after,ui=ui,uiOriginal=ui_original,uiBefore=ui_before,uiBeforeOriginal=ui_before_original,avatarBefore=avatar_before,avatarAfter=avatar_after,
            capture=capture,draws=draws,image=image,retirement=proof,files=files,web=web,touch=touch,world=world,marker=marker,epochMs=epoch,state=measured,ownership=deepcopy(f.state['objects']))
        if capture is not None:
            try:image_ready=self.pixels(frame,raw)
            except AssertionError:image_ready=False
        frame['imageReady']=image_ready
        self.finish_archive(frame)
        captured=min(native_after['capturedEpochMs'],after['capturedEpochMs'],ui_original['capturedEpochMs'],
                     capture['source']['capturedEpochMs'] if capture else native_after['capturedEpochMs'])
        fresh(captured,self.native.clock_ms());self.bound()
        artifacts=[]
        if image_ready:artifacts.append(dict(kind='image',source='world-render-target',name=image['name'],sequence=self.state['sequence'],capturedEpochMs=capture['source']['capturedEpochMs'],ticket=ticket))
        resources=['entity:'+row['id'] for row in after['source']['entities']]
        if measured['editor']:resources.append('panel:create')
        if files is not None and files['source']['exists']:resources.append('file:create-stage')
        return result('feature.create.observe',dict(schemaVersion=1,contractVersion=VERSION,runId=f.run,sequence=self.state['sequence'],
            capturedEpochMs=captured,state=measured,artifacts=artifacts,resources=sorted(resources),lifecycle=native_after['lifecycle']))
