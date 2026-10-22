"""Independent role acquisition; original sources, bytes and current draws only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
from adapters.native_feature_observation import exact,fresh,integer,need,validate as native_packet
from adapters.native_avatar_render import validate as avatar_packet
from adapters.native_world_model_draws import validate as draw_packet
from adapters.normal_feature_state import PrivateFeatureState
from adapters.world_render_evidence import original_pixels
from adapters.native_phone_web_runtime import active_marker,released as web_released
from feature_journeys.contract import result
from feature_journeys.evidence import image_observation,rectangle
from feature_journeys.scenarios import VERSION
from overte_phone_create_role import PhoneCreateRole
from overte_phone_create_source import validate as entity_packet
from overte_phone_create_measurements import CreatePending
from overte_phone_create_marker import ready as marker_ready,retired as marker_retired
from overte_phone_assets_evidence import AssetsOriginals,AssetsImages,AssetsDownload
from overte_phone_assets_controls import validate as ui_packet
from overte_phone_assets_backend import inventory,owned_inventory,bytes_for,reader_chain,connection,responsibility,sha
from overte_phone_assets_measurements import facts,model
from overte_phone_graphics_effects import projected_box
from overte_phone_graphics_samples import restore_native,restore_ui
from overte_phone_script_history import pack,unpack,same

class PhoneAssetsRole(PhoneCreateRole):
    def __init__(self,feature,role):
        need(role in ('primary','actor'));feature.lock.assert_held();self.feature,self.role=feature,role
        self.store=PrivateFeatureState(feature.store.path.with_name('phone-assets-'+role+'-originals.json'));self.previous=self.store.read()
        self.state=dict(phase='ready',sequence=0,manifests=[],pending=None)
        self.originals=AssetsOriginals(feature.root,feature.binding,feature.run,role,self.bound,self.storage_intent,kind='assets')
        if self.previous is not None:
            value=self.previous;exact(value,{'assetsRoleVersion','runId','binding','role','payload'})
            need(type(value['assetsRoleVersion']) is int and value['assetsRoleVersion']==1 and value['runId']==feature.run and value['role']==role and same(value['binding'],feature.binding))
            rows=unpack(value['payload']);need(len(rows)==1);self.state=rows[0];exact(self.state,{'phase','sequence','manifests','pending'})
            need(self.state['phase'] in ('ready','reading','retired') and integer(self.state['sequence'],0,256))
        self.frames=self.originals.restore(self.state['manifests'],self.state['sequence'])
        self.native=feature.adapter._native_feature_observer(feature.selector,read_only=True)
        self.entities=feature.adapter._create_source(feature.selector,read_only=True)
        self.ui=feature.adapter._assets_controls(feature.selector,lambda *_:need(False),read_only=True)
        self.avatar=feature.adapter._avatar_render_observer(feature.selector,read_only=True)
        self.draws=feature.adapter._world_model_draws_observer(feature.selector,read_only=True)
        self.web=feature.adapter._web_runtime_observer(feature.selector,read_only=True)
        self.mapping=feature.adapter._assets_source(feature.selector,read_only=True)
        self.resolver=feature.adapter._assets_source(feature.selector,read_only=True,resolve=True)
        self.downloader=feature.adapter._assets_source(feature.selector,read_only=True,download=True)
        self.uploads=feature.adapter._assets_uploads(feature.selector,read_only=True);self.backend=feature.backend()
        self.backend.last=None # Actor/primary source cursors come from their own originals.
        restores=(('nativeAfter',lambda p:restore_native(self.native,p)),('entitiesAfter',lambda p:setattr(self.entities,'last',deepcopy(p))),
            ('uiOriginal',lambda p:restore_ui(self.ui.io,p,ui_packet)),('avatarAfter',lambda p:self.avatar.restore([p])),
            ('draws',lambda p:setattr(self.draws,'last',deepcopy(p))),('web',lambda p:setattr(self.web,'last',deepcopy(p))),
            ('mappingAfter',lambda p:setattr(self.mapping,'last',deepcopy(p))),('backendAfter',lambda p:setattr(self.backend,'last',deepcopy(p))),
            ('resolution',lambda p:setattr(self.resolver,'last',deepcopy(p))),('uploads',lambda p:setattr(self.uploads,'last',deepcopy(p))))
        for key,restore in restores:
            value=next((frame[key] for frame in reversed(self.frames) if frame.get(key) is not None),None)
            if value is not None:restore(value)
        last_download=next((list(frame['downloads'].values())[-1] for frame in reversed(self.frames) if frame.get('downloads')),None)
        if last_download is not None:self.downloader.last=deepcopy(last_download)
        if self.previous is None:self.save()
    def save(self):
        self.bound();value=dict(assetsRoleVersion=1,runId=self.feature.run,binding=self.feature.binding,role=self.role,payload=pack([self.state]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
    def storage_intent(self,kind,value):
        self.bound();need(self.state['phase']=='reading' and kind in ('original','manifest'))
        pending=self.state['pending'];old=pending[kind]
        if old is not None:need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase']) if kind=='original' else value['phase']=='saved' and old['phase']=='planned')
        pending[kind]=deepcopy(value)
        if kind=='original' and value['phase']=='saved':
            # The original file has already been fsynced and read back by the
            # existing immutable engine. Keep its exact receipt, not another
            # large FBX copy during the remaining manifest callbacks.
            pending['frame']=None;pending['work']={}
        self.save();return True
    def finish_archive(self,frame):
        # The final frame already contains every original in the acquisition
        # work map. Retain one complete copy while archiving, so a large actual
        # FBX is never duplicated across the bounded 48 KiB private header.
        # On a failed write the previous durable work remains recoverable.
        self.state['pending']['work']={}
        return super().finish_archive(frame)
    def download_intent(self,value):
        need(self.state['phase']=='reading');old=self.state['pending']['downloadFile']
        need(value['phase']=='planned' if old is None else value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase']))
        self.state['pending']['downloadFile']=deepcopy(value);self.save();return True
    def recover(self):
        self.bound();need(self.state['phase']=='reading');pending=self.state['pending'];f=self.feature
        owned=f.adapter._world_render_capture(f.selector,read_only=True,role=self.role,require_trace=True,require_frame_view=True)
        image=pending.get('image')
        if image is not None and image['phase']!='saved':
            engine=AssetsImages(f.root,f.binding,f.run,self.role,self.state['sequence']+1,self.bound,self.image_intent)
            if owned.owner.store.read() is not None:
                capture=pending['work']['capture'];need(owned.owner.owned()['capture']['commandId']==capture['requestId']);owned.storage.bind(capture)
                engine.resume(image,owned.storage.read(capture['source']['image']['name']))
            else:need(image['phase']=='planned' and engine.absent(image))
        if owned.owner.store.read() is not None:self.release_capture(owned)
        file=pending.get('downloadFile')
        if file is not None and file['phase']!='saved':
            raw=bytes_for(file['download'],file['download']['source']['hash'])
            AssetsDownload(f.root,f.binding,f.run,self.role,self.state['sequence']+1,self.bound,self.download_intent).resume(file,raw)
        if pending.get('frame') is not None:frame=pending['frame']
        elif pending['original'] is not None and pending['original']['phase']=='saved':frame=self.originals.read(pending['original'])
        else:frame=dict(pending['work'],diagnostic=True,retirement=pending.get('retirement'),image=pending.get('image'),downloadFile=pending.get('downloadFile'))
        self.finish_archive(frame)
    def pixels(self,frame,raw):
        f=self.feature;capture=frame['capture'];original_pixels(capture,raw);need(capture['source']['targetExtent']==f.config['imageExtent'])
        image_observation(raw,f.run,frame['ticket'],f.policy)
        draw_packet(frame['draws'],dict(schemaVersion=1,commandId=frame['draws']['requestId'],action='feature-world-model-draws-observe',captureRequestId=capture['requestId']),f.pid,frame['epochMs'],capture=capture)
        before,after=frame['entitiesBefore']['source'],frame['entitiesAfter']['source'];need(len(before['entities'])==len(after['entities']))
        for row in after['entities']:
            prior=next((item for item in before['entities'] if item['id']==row['id']),None);need(prior is not None)
            a,b=deepcopy(prior),deepcopy(row)
            for item in (a,b):
                if item['render'] is not None:item['render'].pop('recordedEpochMs')
            if not same(a,b):raise CreatePending()
            selected=frame['ui']['controls'];page=next(item for item in selected if item['id']=='assets.page');path=page['selectedPath']
            claim=next(claim for claim in frame['claims'] if any(item['hash']==inventory(frame['mappingAfter'])[path]['hash'] for item in claim['published'].values()))
            render,geometry,chain=model(row,path,frame['mappingAfter'],frame['resolution'],frame['downloads'],claim)
            matches=[item for item in frame['draws']['source']['modelTrace']['models'] if item['modelInstance']==render['modelInstance'] and item['geometryInstance']==geometry['instance']
                and item['loadedSourcePresent'] and item['loadedSourceSha256']==geometry['reader']['sourceSha256'] and item['originalGeometryDrawCommands']>0]
            need(len(matches)==1 and render['recordedEpochMs']<=capture['source']['renderTrace']['recordedEpochMs'])
            draw=matches[0];center=[(a+b)/2 for a,b in zip(draw['minimum'],draw['maximum'])];need(all(abs(a-b)<=.005 for a,b in zip(center,row['position'])))
            box=projected_box(dict(position=center,dimensions=[b-a for a,b in zip(draw['minimum'],draw['maximum'])],rotation=[0,0,0,1]),capture['source']['renderTrace']['recordedView'],capture['source']['targetExtent'])
            roi=[math.floor(box[0]),math.floor(box[1]),math.ceil(box[2]),math.ceil(box[3])];subject=rectangle(f.policy['subject'],capture['source']['targetExtent']);rectangle(roi,capture['source']['targetExtent'])
            need(roi[2]-roi[0]>=24 and roi[3]-roi[1]>=24 and subject[0]<=roi[0] and subject[1]<=roi[1] and subject[2]>=roi[2] and subject[3]>=roi[3]
                and (subject[2]-subject[0])*(subject[3]-subject[1])<=2*(roi[2]-roi[0])*(roi[3]-roi[1]))
        return True
    def acquire(self,after_sequence):
        f=self.feature;self.bound();need(self.state['phase']=='ready' and integer(after_sequence,0,self.state['sequence']) and self.state['sequence']<256)
        self.state.update(phase='reading',pending=dict(original=None,manifest=None,image=None,downloadFile=None,retirement=None,frame=None,work={}));self.save()
        phase_before=f.phase.status();need(phase_before['active'] and phase_before['activations']);ticket=phase_before['activations'][-1]['ticket'];self.checkpoint(ticket=ticket,phaseBefore=phase_before)
        native_before=self.native.read(self.native.sequence);before=self.entities.read(f.run,sorted(row['id'] for row in f.state['objects']));avatar_before=self.avatar.read()
        mapping_before=self.mapping.read(f.run);backend_before=self.backend.read();ui=self.ui.capture();ui_original=deepcopy(self.ui.io.last_original)
        self.checkpoint(nativeBefore=native_before,entitiesBefore=before,avatarBefore=avatar_before,mappingBefore=mapping_before,backendBefore=backend_before,ui=ui,uiOriginal=ui_original)
        web=self.web.read(f.run,f.fixture_url);self.checkpoint(web=web);uploads=self.uploads.request('observe',f.run);claims=[]
        for claim in f.state['claims']:
            if not uploads['source']['retired']:
                current=responsibility(uploads,claim['fileOriginal'],claim['resource'],f.run,f.state['backendOriginal']['connection']);need(current['complete']==claim['complete'])
                if 'currentPaths' in claim:current['currentPaths']=deepcopy(claim['currentPaths'])
                claims.append(current)
            else:claims.append(deepcopy(claim)) # Historical responsibility only; current effects are read independently below.
        files=None;stage_files={}
        for stage in f.state['stages']:
            metadata=PrivateFeatureState(f.store.path.with_name('phone-assets-files-owner-'+str(stage)+'.json')).read();need(metadata is not None and metadata['binding']==f.binding and metadata['runId']==f.run and metadata['stage']==stage)
            actual=f.adapter._assets_files(f.selector,read_only=True,stage=stage).request('observe',f.run,metadata['ownerToken']);stage_files[str(stage)]=actual
            if stage==f.state['stage']:files=actual
        self.checkpoint(uploads=uploads,claims=claims,files=files,stageFiles=stage_files)
        rows=inventory(mapping_before);page=self.ui.page(ui);selected='' if page is None else page['selectedPath'];resolution=None;downloads={}
        if selected:
            need(selected in rows);resolution=self.resolver.read(f.run,path=selected)
            hashes={row['hash'] for path,row in rows.items() if path.startswith('/e2e-'+f.run+'/') or path.startswith('/renamed-'+f.run+'/')
                or any(path.startswith('/.baked/'+item['returnedHash']+'/') for claim in claims for item in claim['uploads'].values())}
            for digest in sorted(hashes):downloads[digest]=self.downloader.read(f.run,digest)
        self.checkpoint(resolution=resolution,downloads=downloads)
        capture=draws=image=proof=marker=file=None;image_ready=False
        if f.state['marker'] is not None and f.state['marker']['operation']=='prepare':
            marker=f.adapter._create_fixture_observer(f.selector,read_only=True).read(f.run);marker_ready(marker,avatar_before)
            marker_rows=[row for row in marker['source']['entities'] if row['role']=='marker'];need(len(marker_rows)==1);active_marker(web,marker_rows[0]['sourceUrl']);self.checkpoint(marker=marker)
            owned=f.adapter._world_render_capture(f.selector,read_only=True,role=self.role,require_trace=True,require_frame_view=True);need(owned.owner.store.read() is None)
            captures=[frame['capture'] for frame in self.frames if frame.get('capture') is not None]
            if captures:
                last=captures[-1];reader=owned.capture;reader.instance,reader.sequence=last['instance'],last['sequence'];reader.acquisition,reader.captured=last['source']['acquisitionSequence'],last['source']['capturedEpochMs'];reader.frames={packet['source']['renderTrace']['frameId'] for packet in captures}
            capture,raw=owned.read(owned.capture.sequence);self.checkpoint(capture=capture);self.state['pending']['capture']=deepcopy(owned.owner.owned());self.save()
            draws=self.draws.read(capture);self.checkpoint(draws=draws)
            image=AssetsImages(f.root,f.binding,f.run,self.role,self.state['sequence']+1,self.bound,self.image_intent).write(ticket,capture,raw);proof=self.release_capture(owned)
        ui_before,ui_before_original=ui,ui_original;ui=self.ui.capture();ui_original=deepcopy(self.ui.io.last_original)
        need(all(ui['scope'][key]==ui_before['scope'][key] for key in ('instance','generation','sequence','processId')))
        avatar_after=self.avatar.read();after=self.entities.read(f.run,sorted(row['id'] for row in f.state['objects']));mapping_after=self.mapping.read(f.run);backend_after=self.backend.read()
        native_after=self.native.read(self.native.sequence);phase_after=f.phase.status(phase_before);epoch=self.native.clock_ms();touch=world=None
        if f.state['phase']=='cleaned':touch=f.adapter._touch_state_observer(f.selector,read_only=True).read();world=f.adapter._graphics_subject_observer(f.selector,read_only=True).read(f.run,require_avatar=True)
        if f.state['marker'] is not None and f.state['marker']['operation']=='release':marker=f.adapter._create_fixture_observer(f.selector,read_only=True).read(f.run);marker_retired(marker);web_released(web)
        self.checkpoint(nativeAfter=native_after,entitiesAfter=after,avatarAfter=avatar_after,mappingAfter=mapping_after,backendAfter=backend_after,phaseAfter=phase_after,epochMs=epoch,touch=touch,world=world,marker=marker)
        need(same(phase_before['activations'],phase_after['activations']) and phase_before['active']==phase_after['active'])
        for packet in (before,after):
            entity_packet(packet,dict(schemaVersion=1,commandId=packet['requestId'],action='phone-create-observe',runId=f.run,trackedIds=sorted(row['id'] for row in f.state['objects'])),f.pid,epoch)
            need(packet['source']['connected'] and packet['source']['domainId']==f.state['domainId'] and packet['source']['sessionId']==f.state['nativeSessionId'])
        for packet in (native_before,native_after):native_packet(packet,packet['requestId'],f.pid,epoch)
        for packet in (avatar_before,avatar_after):avatar_packet(packet,dict(schemaVersion=1,commandId=packet['requestId'],action='feature-avatar-render-observe'),f.pid,epoch)
        for packet in (ui_original,ui_before_original):ui_packet(packet,packet['commandId'],f.pid,epoch)
        if not same(mapping_before['source'],mapping_after['source']):raise CreatePending()
        measured=facts(f.run,ui,mapping_after,backend_after,f.state['backendOriginal'],claims,after,f.state['objects'],files,resolution,downloads,f.state['bakeBarrier'])
        if measured['sceneModel'] and selected.endswith('/main.gltf'):
            digest=rows[selected]['hash'];packet=downloads[digest];file=AssetsDownload(f.root,f.binding,f.run,self.role,self.state['sequence']+1,self.bound,self.download_intent).write(ticket,packet,bytes_for(packet,digest))
        frame=dict(ticket=ticket,phaseBefore=phase_before,phaseAfter=phase_after,nativeBefore=native_before,nativeAfter=native_after,entitiesBefore=before,entitiesAfter=after,
            mappingBefore=mapping_before,mappingAfter=mapping_after,backendBefore=backend_before,backendAfter=backend_after,ui=ui,uiOriginal=ui_original,uiBefore=ui_before,uiBeforeOriginal=ui_before_original,
            avatarBefore=avatar_before,avatarAfter=avatar_after,capture=capture,draws=draws,image=image,retirement=proof,files=files,stageFiles=stage_files,web=web,touch=touch,world=world,marker=marker,
            epochMs=epoch,state=measured,ownership=deepcopy(f.state['objects']),uploads=uploads,claims=claims,resolution=resolution,downloads=downloads,downloadFile=file)
        if capture is not None:image_ready=self.pixels(frame,raw)
        frame['imageReady']=image_ready;self.finish_archive(frame)
        captured=min(native_after['capturedEpochMs'],after['capturedEpochMs'],ui_original['capturedEpochMs'],mapping_after['capturedEpochMs'],backend_after['source']['capturedEpochMs'],capture['source']['capturedEpochMs'] if capture else native_after['capturedEpochMs'])
        fresh(captured,self.native.clock_ms());self.bound();artifacts=[]
        if image_ready:artifacts.append(dict(kind='image',source='world-render-target',name=image['name'],sequence=self.state['sequence'],capturedEpochMs=capture['source']['capturedEpochMs'],ticket=ticket))
        if file is not None:artifacts.append(dict(kind='file',name=file['name'],sequence=self.state['sequence'],capturedEpochMs=file['download']['capturedEpochMs'],ticket=ticket))
        resources=['entity:'+row['id'] for row in after['source']['entities']]+['file:assets-mapping-'+sha(path)[:32] for path in owned_inventory(mapping_after,backend_after,f.state['backendOriginal'],claims,f.run)]
        if measured['open']:resources.append('panel:assets')
        for stage,packet in stage_files.items():
            if packet['source']['exists']:resources.append('file:assets-stage-'+stage)
        if uploads['source']['activeBundles'] or uploads['source']['liveRequests'] or uploads['source']['retainedBundles']:resources.append('connection:assets-uploads')
        return result('feature.assets.observe',dict(schemaVersion=1,contractVersion=VERSION,runId=f.run,sequence=self.state['sequence'],capturedEpochMs=captured,state=measured,artifacts=artifacts,resources=sorted(resources),lifecycle=native_after['lifecycle']))
