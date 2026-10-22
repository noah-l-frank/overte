"""Concrete ordinary Create composition with durable ownership and original reads.

No configurable producer supplies product facts. Inputs use the existing Qt or
SDK controls; files, Domain permissions, native objects and GPU PNGs retain their
separate original owners. Physical device qualification remains separate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import secrets
import stat
import time
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler,ProxyHandler,Request,build_opener
import uuid

from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.token_script_file_ui import file_url
from adapters.token_create_ui import snapshot,same_reference,tool_settings
from feature_journeys.contract import arguments,identifier,json_document
from feature_journeys.evidence import rectangle,read_private_artifact,file_observation
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.scenarios import VERSION
from fixture.create_permissions import standard,NoRedirect
from fixture.messages_mixer import start_identity
from overte_phone_create_evidence import CreateOriginals
from overte_phone_create_file_owner import OwnedCreateFiles
from overte_phone_create_measurements import DENIED,CreatePending
from adapters.native_phone_touch_state import released as touch_released
from adapters.native_phone_web_runtime import active_marker,released as web_released
from overte_phone_create_role import PhoneCreateRole
from overte_phone_graphics_effects import rotate,projected_box
from overte_phone_graphics_surface import MODES
from overte_phone_script_history import canonical,pack,unpack,same
from overte_phone_script_lock import PhoneScriptSourceLock
from overte_phone_script_ui import PhoneScriptUI


def configuration(value,*,actor=False):
    exact(value,{'createFeatureVersion','artifactRoot','imageExtent','markerRoi','imagePolicy','domainId',
        'permissionsControlUrl'}|({'permissionsTokenSha256'} if actor else {'permissionsControlToken'}))
    need(type(value['createFeatureVersion']) is int and value['createFeatureVersion']==1)
    root=Path(value['artifactRoot']);PrivateFeatureState(root/'create-evidence-boundary.json')._parent()
    extent=value['imageExtent'];need(type(extent) is list and len(extent)==2 and all(integer(v,240,4096) for v in extent))
    exact(value['imagePolicy'],{'source','marker','subject'});need(value['imagePolicy']['source']=='world-render-target')
    rectangle(value['markerRoi'],extent)
    for key in ('marker','subject'):rectangle(value['imagePolicy'][key],extent)
    x0,y0,x1,y1=value['markerRoi'];need(x1-x0>=160 and y1-y0>=40 and (x1-x0)*(y1-y0)<=.1*extent[0]*extent[1])
    marker,subject=value['imagePolicy']['marker'],value['imagePolicy']['subject']
    need(marker==[round(x0+(x1-x0)*4/160),round(y0+(y1-y0)*4/40),round(x0+(x1-x0)*132/160),round(y0+(y1-y0)*36/40)]
        and marker[2]-marker[0]>=128 and marker[3]-marker[1]>=32)
    need(x0<=marker[0]<marker[2]<=x1 and y0<=marker[1]<marker[3]<=y1
        and not(max(marker[0],subject[0])<min(marker[2],subject[2]) and max(marker[1],subject[1])<min(marker[3],subject[3])))
    need(str(uuid.UUID(value['domainId']))==value['domainId'])
    url=urlsplit(value['permissionsControlUrl'])
    need(url.scheme=='http' and url.hostname=='127.0.0.1' and integer(url.port,1,65535) and url.netloc=='127.0.0.1:'+str(url.port)
        and url.path=='/v1/create-permissions' and not url.query and not url.fragment
        )
    if actor:need(type(value['permissionsTokenSha256']) is str and len(value['permissionsTokenSha256'])==64 and all(ch in '0123456789abcdef' for ch in value['permissionsTokenSha256']))
    else:need(type(value['permissionsControlToken']) is str and 32<=len(value['permissionsControlToken'])<=128
        and all(33<=ord(ch)<=126 for ch in value['permissionsControlToken']))
    return deepcopy(value)


class PhoneCreateFeature:
    def __init__(self,adapter,selector,phase,config,*,role='primary',original_configuration=False,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(phase,PhaseFixtureReader) and phase.area=='create' and role in ('primary','actor'))
        need(type(original_configuration) is bool and (not original_configuration or role=='primary'))
        self.adapter,self.selector,self.phase,self.config,self.role=adapter,selector,phase,configuration(config,actor=role=='actor' or original_configuration),role
        self.run,self.fixture_url=phase.run,phase.fixture_url;self.root=Path(self.config['artifactRoot']);self.policy=deepcopy(self.config['imagePolicy'])
        self.monotonic,self.sleep=monotonic,sleep;path=adapter.state_path(selector)
        self.store=PrivateFeatureState(path.with_name('phone-create-feature.json'))
        self.lock=PhoneScriptSourceLock(path.with_name('phone-script-sources.lock'));self.previous=self.state=None
        _ui,_service,binding,self.guard,_installed=adapter.normal_feature_runtime(selector,read_only=True)
        self.binding=deepcopy(context(binding));self.pid=int(binding['processIdentity'].split(':')[0])
        self.inputs=CreateOriginals(self.root,self.binding,self.run,'primary',self.bound,self.storage_intent,kind='create-input')

    def load(self):
        self.lock.assert_held();self.previous=self.store.read();self.state=None
        if self.previous is None:return
        value=self.previous;exact(value,{'createFeatureVersion','runId','fixtureUrl','binding','configuration','payload'})
        public_config={key:item for key,item in self.config.items() if key!='permissionsControlToken'}
        public_config['permissionsTokenSha256']=self.config.get('permissionsTokenSha256') or hashlib.sha256(self.config['permissionsControlToken'].encode()).hexdigest()
        need(type(value['createFeatureVersion']) is int and value['createFeatureVersion']==1 and value['runId']==self.run
            and value['fixtureUrl']==self.fixture_url and same(value['binding'],self.binding) and same(value['configuration'],public_config))
        rows=unpack(value['payload']);need(len(rows)==1);self.state=rows[0]
        exact(self.state,{'phase','original','inputTicket','domainId','nativeSessionId','objects','creation','current','actions','leases',
            'hostProcess','marker','markerSource','tools','permissionOwner','permissionLease','filesLease','export','inputs','inputSequence','inputStorage','retained'})
        need(self.state['phase'] in ('baseline','active','acting','cleaning','cleaned','retiring')
            and type(self.state['objects']) is list and len(self.state['objects'])<=16 and type(self.state['actions']) is list
            and len(self.state['actions'])<=64 and integer(self.state['inputSequence'],0,1024))
        originals=self.inputs.restore(self.state['inputs'],self.state['inputSequence'])
        self.validate_ownership(originals);self.bound()

    def validate_ownership(self,originals):
        from overte_phone_create_source import validate as entity_packet
        seen=set()
        for owned in self.state['objects']:
            exact(owned,{'id','instance','role','created','ticket','sourceIndex'})
            need(integer(owned['sourceIndex'],1,len(originals)) and owned['id'] not in seen)
            receipt=originals[owned['sourceIndex']-1]['creationResponsibility'];exact(receipt,{'owned','before','actual','selection','trackedIds'})
            need(same(receipt['owned'],{key:item for key,item in owned.items() if key!='sourceIndex'}))
            need(receipt['trackedIds']==sorted(seen|{owned['id']}));snapshot(receipt['selection'])
            pages=[row for row in receipt['selection']['controls'] if row['id']=='create.page']
            need(len(pages)==1 and pages[0]['selectedIds']==[owned['id']] and receipt['selection']['scope']['processId']==self.pid)
            for packet,tracked in ((receipt['before'],sorted(seen)),(receipt['actual'],receipt['trackedIds'])):
                entity_packet(packet,dict(schemaVersion=1,commandId=packet['requestId'],action='phone-create-observe',runId=self.run,trackedIds=tracked),self.pid,packet['capturedEpochMs'])
                need(packet['source']['domainId']==self.state['domainId'] and packet['source']['sessionId']==self.state['nativeSessionId'])
            need(owned['id'] not in {row['id'] for row in receipt['before']['source']['scan']['inventory']})
            rows=[row for row in receipt['actual']['source']['entities'] if row['id']==owned['id']];need(len(rows)==1);row=rows[0]
            need(row['instance']==owned['instance'] and row['createdEpochUs']==owned['created'] and row['host']=='domain' and not row['locked']
                and row['parentId'] is None and row['lastEditedBy']==self.state['nativeSessionId']
                and row['createdEpochUs']>=receipt['before']['requestedEpochMs']*1000 and row['type']=={'model':'Model','voxel':'PolyVox','cube':'Box'}[owned['role']])
            seen.add(owned['id'])

    def bound(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous));return True

    def save(self):
        self.bound();public_config={key:item for key,item in self.config.items() if key!='permissionsControlToken'}
        public_config['permissionsTokenSha256']=self.config.get('permissionsTokenSha256') or hashlib.sha256(self.config['permissionsControlToken'].encode()).hexdigest()
        value=dict(createFeatureVersion=1,runId=self.run,fixtureUrl=self.fixture_url,binding=self.binding,
            configuration=public_config,payload=pack([self.state]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def storage_intent(self,kind,value):
        need(self.state is not None and self.state['current'] is not None and kind in ('original','manifest'))
        pending=self.state['inputStorage'];need(pending is not None)
        pending[kind]=deepcopy(value);self.save();return True

    def archive_input(self,frame):
        need(self.state['inputStorage'] is None)
        self.state['inputStorage']=dict(original=None,manifest=None,frame=deepcopy(frame));self.save()
        ref=self.inputs.write(self.state['inputSequence']+1,frame)
        refs=self.inputs.append(self.state['inputs'],ref)
        self.state.update(inputs=refs,inputSequence=self.state['inputSequence']+1,inputStorage=None);self.save();return self.state['inputSequence']

    def recover_archive(self):
        pending=self.state['inputStorage']
        if pending is None:return
        frame=pending['frame'];index=self.state['inputSequence']+1
        ref=(self.inputs.write(index,frame) if pending['original'] is None else self.inputs.resume_write(index,frame,pending['original']))
        refs=(self.inputs.append(self.state['inputs'],ref) if pending['manifest'] is None else
              self.inputs.resume_manifest(self.state['inputs'],ref,pending['manifest']))
        self.state.update(inputs=refs,inputSequence=index,inputStorage=None);self.save()

    def active(self):
        original=self.phase.status();need(original['active'] and original['activations'])
        current=self.state['current'];need(current is not None)
        last=original['activations'][-1];call=current['call']
        need(last['ticket']==call['ticket'] and same(last['stimulus'],dict(verb=call['verb'],inputs=call['inputs'])))
        return original

    def audit(self,kind,value):
        self.bound();current=self.state['current'];need(current is not None)
        if kind=='intent':
            need(current['pending'] is None);snapshot(value['original'])
            current['pending']=dict(kind='qt',intent=deepcopy(value),provider=self.active());self.save()
            if value['controlId'] in ('create.import-browse','create.export'):self.state['leases']['picker']=True;self.save()
        else:
            need(kind=='receipt' and current['pending'] is not None and same(current['pending']['intent'],value['intent']))
            before,after=value['intent']['original'],snapshot(value['after'])
            need(before['scope']['processId']==after['scope']['processId']==self.pid
                and before['scope']['instance']==after['scope']['instance'] and after['scope']['sequence']>before['scope']['sequence'])
            self.archive_input(dict(input=current['pending'],after=deepcopy(value['after']),providerAfter=self.active()))
            current['pending']=None;self.save()
        return True

    def controls(self):
        ui=self.adapter._create_controls(self.selector,lambda *_:self.bound(),read_only=False);ui.audit=self.audit;return ui

    def sdk(self,operation):
        need(operation in ('open','close','home'));current=self.state['current'];need(current is not None and current['pending'] is None)
        native,_observe,_binding,_check,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        tablet=PhoneScriptUI(native,'io.github.noah_be.overte.phone');before=self.adapter._create_controls(self.selector,lambda *_:need(False),read_only=True).capture()
        if operation=='open' and before['open'] or operation=='close' and not before['open']:return
        current['pending']=dict(kind='sdk',operation=operation,original=before,provider=self.active());self.save()
        if operation=='open':self.state['leases']['tablet']=True;self.save();tablet.open_tablet()
        elif operation=='close':need(self.state['leases']['tablet']);tablet.close_tablet();tablet.wait_tablet_absent()
        else:need(self.state['leases']['tablet']);native.click(tablet.resource('nav.home'))
        after=self.adapter._create_controls(self.selector,lambda *_:need(False),read_only=True).capture()
        if operation!='home':need(after['open']==(operation=='open'))
        else:need(not any(row['id']=='create.page' for row in after['controls']))
        self.archive_input(dict(input=current['pending'],after=after,providerAfter=self.active()))
        current['pending']=None
        if operation=='close':self.state['leases']['tablet']=False
        self.save()

    def surface(self):
        def intent(stage,subject,graphics,control):
            self.active();self.archive_input(dict(stage=stage,subject=subject,graphics=graphics,control=control));return True
        def lease(key,value):self.state['leases'][key]=value;self.save();return True
        return self.adapter._graphics_surface(self.selector,self.run,intent,lambda key:self.state['leases'][key],lease,
            lambda _url:False,lock=self.lock)

    def entities(self,extra=()):
        value=self.adapter._create_source(self.selector,read_only=True).read(self.run,sorted(set(extra)|{row['id'] for row in self.state['objects']}))
        need(value['source']['connected'] and value['source']['domainId']==self.state['domainId']
            and value['source']['sessionId']==self.state['nativeSessionId']);return value

    def files(self):
        return OwnedCreateFiles(self.adapter._create_files(self.selector,read_only=False),
            PrivateFeatureState(self.store.path.with_name('phone-create-files-owner.json')),self.binding,
            self.run,self.state['inputTicket'],self.fixture_url)

    def file_directory(self):
        owner=self.files()
        if owner.state['phase'] in ('reserved','stage-issuing','ready'):return owner.prepare()
        original=owner.read();need(original['source']['exists'] and not original['source']['retiring'])
        return original['source']['directory']

    def ensure_editor(self,ui):
        self.sdk('open');value=ui.capture()
        if not any(row['id']=='create.page' for row in value['controls']):ui.open_create()

    def permissions(self,operation,allowed=None):
        self.active();command=dict(schemaVersion=1,runId=self.run,ownerToken=self.state['permissionOwner'],operation=operation)
        if allowed is not None:command['allowed']=allowed
        self.state['permissionLease']=True;self.save()
        request=Request(self.config['permissionsControlUrl'],data=canonical(command),headers={
            'Content-Type':'application/json','X-Overte-E2E-Token':self.config['permissionsControlToken']})
        with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=5) as response:
            need(response.status==200 and response.geturl()==self.config['permissionsControlUrl']);raw=response.read(65537)
        need(len(raw)<=65536);value=json_document(raw)
        exact(value,{'createPermissionsVersion','domainId','sequence','capturedEpochMs','restored','standard'})
        need(type(value['createPermissionsVersion']) is int and value['createPermissionsVersion']==1
            and value['domainId']==self.state['domainId'] and type(value['restored']) is bool)
        standard(value['standard']);self.archive_input(dict(command={key:item for key,item in command.items() if key!='ownerToken'},original=value))
        if operation=='retire':need(value['restored']);self.state['permissionLease']=False;self.save()
        return value

    def initialize(self):
        need(self.role=='primary' and self.state is None)
        phase=self.phase.read();need(phase['verb']=='baseline')
        source=self.adapter._create_source(self.selector,read_only=True).read(self.run)
        ui=self.adapter._create_controls(self.selector,lambda *_:need(False),read_only=True).capture()
        avatar=self.adapter._avatar_render_observer(self.selector,read_only=True).read()
        need(not ui['open'] and not source['source']['entities'] and source['source']['connected']
            and source['source']['canRez'] and source['source']['domainId']==self.config['domainId']
            and source['source']['sessionId'] is not None and avatar['source']['cameraMode'] in MODES)
        touch=self.adapter._touch_state_observer(self.selector,read_only=True).read();touch_released(touch)
        world=self.adapter._graphics_subject_observer(self.selector,read_only=True).read(self.run,require_avatar=True)
        self.state=dict(phase='baseline',original=dict(entities=source,ui=ui,avatar=avatar,touch=touch,world=world),inputTicket=phase['ticket'],
            domainId=source['source']['domainId'],nativeSessionId=source['source']['sessionId'],objects=[],creation=None,current=None,
            actions=[],leases=dict(tablet=False,menu=False,address=False,picker=False),hostProcess=dict(pid=os.getpid(),start=start_identity(os.getpid())),marker=None,markerSource=None,tools=None,
            permissionOwner=secrets.token_hex(32),permissionLease=False,filesLease=False,export=None,inputs=[],inputSequence=0,inputStorage=None,retained=[])
        self.save()

    def begin_creation(self,role):
        need(self.state['creation'] is None);before=self.entities()
        self.state['creation']=dict(role=role,before=before,ticket=self.state['current']['call']['ticket']);self.save()

    def claim(self,ui):
        creation=self.state['creation'];need(creation is not None)
        value=ui.wait(lambda value:len(ui.page(value)['selectedIds'])==1);identifier_=ui.page(value)['selectedIds'][0]
        before=creation['before'];need(identifier_ not in {row['id'] for row in before['source']['scan']['inventory']})
        for attempt in range(51):
            observed=self.entities([identifier_]);rows=[row for row in observed['source']['entities'] if row['id']==identifier_]
            if rows:break
            need(attempt<50);self.sleep(.1)
        need(len(rows)==1);row=rows[0]
        need(row['host']=='domain' and row['parentId'] is None and not row['locked']
            and row['lastEditedBy']==self.state['nativeSessionId'] and row['createdEpochUs']>=before['requestedEpochMs']*1000
            and row['type']=={'model':'Model','voxel':'PolyVox','cube':'Box'}[creation['role']]
            and identifier_ not in {item['id'] for item in self.state['objects']})
        owned=dict(id=identifier_,instance=row['instance'],role=creation['role'],created=row['createdEpochUs'],ticket=creation['ticket'])
        source_index=self.archive_input(dict(creationResponsibility=dict(owned=deepcopy(owned),before=before,actual=observed,selection=deepcopy(value),
            trackedIds=sorted({item['id'] for item in self.state['objects']}|{identifier_}))))
        self.state['objects'].append(dict(owned,sourceIndex=source_index))
        self.state['creation']=None;self.save()
        ui.name_entity('e2e-'+self.run+'-'+creation['role'])
        avatar=self.adapter._avatar_render_observer(self.selector,read_only=True).read()['source']
        offset=rotate([0,0,-2],avatar['view']['rotation']);position=[a+b for a,b in zip(avatar['view']['position'],offset)]
        ui.edit_transform(position=dict(zip('xyz',position)),dimensions=dict(x=1.,y=1.,z=1.))
        for attempt in range(51):
            original=self.entities();actual=next(row for row in original['source']['entities'] if row['id']==identifier_)
            need(actual['instance']==row['instance'])
            if actual['name']=='e2e-'+self.run+'-'+creation['role'] and all(abs(a-b)<=.0001 for a,b in zip(actual['position'],position)) and all(abs(value-1)<=.0001 for value in actual['dimensions']):break
            need(attempt<50);self.sleep(.1)
        self.archive_input(dict(creationOriginal=original,avatarOriginal=avatar,owned=deepcopy(self.state['objects'][-1])))
        return identifier_

    def marker(self,operation):
        command=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-create-fixture-input',operation=operation,runId=self.run)
        if operation=='prepare':command.update(fixtureUrl=self.fixture_url,ticket=self.state['current']['call']['ticket'],
            imageExtent=self.config['imageExtent'],markerRoi=self.config['markerRoi'])
        else:command['fixtureInstance']=self.state['markerSource']['source']['fixtureInstance']
        self.state['marker']=deepcopy(command);self.save()
        self.adapter._create_fixture_input(self.selector,command,lock=self.lock,intent=lambda _command,binding:same(binding,self.binding))
        reader=self.adapter._create_fixture_observer(self.selector,read_only=True)
        for attempt in range(51):
            source=reader.read(self.run);self.state['markerSource']=source;self.save()
            if operation=='prepare' and source['source']['phase']=='active':return
            if operation=='release' and source['source']['phase']=='drained':
                web=self.adapter._web_runtime_observer(self.selector,read_only=True).read(self.run,self.fixture_url)
                try:web_released(web)
                except NativeUIError:need(attempt<50);self.sleep(.1);continue
                self.archive_input(dict(markerOriginal=source,webOriginal=web));return
            need(attempt<50);self.sleep(.1)

    def delete_objects(self,ui):
        ui.tab(3);ui.choose('create.edit-mode',0)
        observed=self.entities();rows={row['id']:row for row in observed['source']['entities']}
        for owned in self.state['objects']:
            if owned['id'] not in rows:continue
            row=rows[owned['id']];need(row['instance']==owned['instance'] and row['host']=='domain' and not row['locked'] and row['parentId'] is None)
            ui.select_entity(owned['id']);ui.delete_entity()
        for attempt in range(51):
            final=self.entities()
            if not final['source']['entities']:break
            need(attempt<50);self.sleep(.1)
        need(set(final['source']['absentIds'])=={row['id'] for row in self.state['objects']})

    def act(self,value):
        call=deepcopy(arguments('feature.create.act',value));need(self.role=='primary' and call['runId']==self.run and call['fixtureUrl']==self.fixture_url)
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            self.load();need(self.state is not None and self.state['phase'] not in ('cleaning','cleaned','retiring'))
            found=[row for row in self.state['actions'] if row['ticket']==call['ticket']]
            if found:need(len(found)==1 and found[0]['phase']=='acknowledged' and same(found[0]['call'],call));return {'performed':True}
            need(self.state['current'] is None)
            current=dict(call=call,pending=None,phase='issuing');self.state['actions'].append(dict(ticket=call['ticket'],call=call,phase='issuing'))
            self.state.update(phase='acting',current=current);self.save();self.active();ui=self.controls();verb=call['verb']
            if verb=='open':
                self.surface().select_camera('first person look at');self.marker('prepare')
                self.state['filesLease']=True;self.save();self.files().prepare()
                self.sdk('open');ui.open_create();tools=ui.actual_tools();self.state['tools']=tools;self.save()
            elif verb=='close':
                if self.state['tools'] is not None:ui.restore_tools(self.state['tools'])
                self.sdk('home');self.sdk('close');self.marker('release');self.surface().select_camera(self.state['original']['avatar']['source']['cameraMode'])
            elif verb=='import-picker-open':ui.open_import_picker()
            elif verb=='import-picker-cancel':ui.cancel_import_picker()
            elif verb in ('model-create','create-retry'):
                role='model' if verb=='model-create' else 'cube';self.begin_creation(role)
                ui.new_entity(role,resource=self.fixture_url+'tickets/'+call['ticket']+'/'+call['inputs']['resource'] if role=='model' else None)
                self.claim(ui)
            elif verb=='import-picker-accept':
                self.begin_creation('model');ui.accept_import_picker(file_url(self.file_directory())+'/entity-import.json');self.claim(ui)
            elif verb=='voxel-create':
                self.begin_creation('voxel');ui.open_import_picker();ui.accept_import_picker(file_url(self.file_directory())+'/voxel-import.json');self.claim(ui)
            elif verb=='apply-texture':ui.texture(self.fixture_url+'tickets/'+call['ticket']+'/checker.png')
            elif verb=='export-selection':
                owner=self.files();path=owner.begin_export();ui.export_selection(file_url(path));raw=owner.finish_export()
                name='create-export-'+self.run+'.json';path=self.root/name
                self.state['export']=dict(name=name,phase='planned',file=None,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw));self.save()
                descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                with os.fdopen(descriptor,'wb') as stream:
                    info=os.fstat(stream.fileno());self.state['export'].update(phase='opened',file=dict(device=info.st_dev,inode=info.st_ino));self.save()
                    need(stream.write(raw)==len(raw));stream.flush();os.fsync(stream.fileno())
                need(read_private_artifact(self.root,name)==raw);self.state['export']['phase']='saved';self.save()
            elif verb=='delete-owned':self.delete_objects(ui)
            elif verb=='set-rez-permission':self.permissions('set',call['inputs']['allowed'])
            elif verb=='create-denied':
                before=self.entities();need(not before['source']['canRez'] and not before['source']['canRezTmp'])
                ui.tab(0);ui.choose('create.host',0);ui.choose('create.shape',0);ui.reveal('create.new-shape');ui.input('create.new-shape')
                ui.wait(lambda value:ui.page(value)['statusError'] and ui.page(value)['statusText']==DENIED)
                after=self.entities();need(not after['source']['entities'] and same(before['source']['scan']['inventory'],after['source']['scan']['inventory']))
            elif verb=='voxel-edit':
                ui.configure_voxel_remove();self.sdk('close');self.world_click();self.ensure_editor(ui)
            else:need(False)
            if self.state['leases']['picker'] and ui.file_picker(ui.capture()) is None:self.state['leases']['picker']=False;self.save()
            need(current['pending'] is None);current['phase']='acknowledged';self.state['actions'][-1]['phase']='acknowledged'
            self.state.update(current=None,phase='active');self.save();return {'performed':True}

    def recover_export(self):
        original=self.state['export'];need(original is not None and original['phase'] in ('planned','opened','saved'))
        data=self.files().finish_export();need(hashlib.sha256(data).hexdigest()==original['sha256'] and len(data)==original['bytes'])
        path=self.root/original['name']
        if original['phase']=='planned':
            descriptor=os.open(path,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            info=os.fstat(descriptor);original.update(phase='opened',file=dict(device=info.st_dev,inode=info.st_ino));self.save()
        else:descriptor=os.open(path,os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(descriptor,'r+b') as stream:
            def owned():
                info,current=os.fstat(stream.fileno()),path.lstat()
                need(stat.S_ISREG(info.st_mode) and stat.S_ISREG(current.st_mode) and info.st_nlink==current.st_nlink==1
                    and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o600
                    and (info.st_dev,info.st_ino)==(current.st_dev,current.st_ino)==(original['file']['device'],original['file']['inode']))
            owned();prefix=stream.read(65537);owned();need(len(prefix)<=len(data) and data.startswith(prefix))
            need(stream.write(data[len(prefix):])==len(data)-len(prefix));stream.flush();os.fsync(stream.fileno());owned()
        need(read_private_artifact(self.root,original['name'])==data);original['phase']='saved';self.save()

    def world_click(self):
        source=self.entities();rows=[row for row in source['source']['entities'] if row['type']=='PolyVox'];need(len(rows)==1)
        avatar=self.adapter._avatar_render_observer(self.selector,read_only=True).read()['source'];native,_s,_b,_g,_i=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        rect=native._request('GET','/window/rect');extent=[int(rect['width']),int(rect['height'])]
        box=projected_box(rows[0],avatar['view'],extent);x,y=round((box[0]+box[2])/2),round((box[1]+box[3])/2)
        need(0<x<extent[0] and 0<y<extent[1] and not self.controls().capture()['open'])
        touch=self.adapter._touch_state_observer(self.selector,read_only=True);original_touch=touch.read();touch_released(original_touch)
        self.state['current']['pending']=dict(kind='world-click',original=source,avatar=avatar,touch=original_touch,x=x,y=y,provider=self.active());self.save()
        actions=[dict(type='pointerMove',duration=0,origin='viewport',x=x,y=y),dict(type='pointerDown',button=0),dict(type='pause',duration=100),dict(type='pointerUp',button=0)]
        try:native._request('POST','/actions',dict(actions=[dict(type='pointer',id='overte-create-primary',parameters=dict(pointerType='touch'),actions=actions)]))
        finally:native._request('DELETE','/actions')
        after_touch=touch.read();touch_released(after_touch)
        self.archive_input(dict(input=self.state['current']['pending'],after=self.entities(),touchAfter=after_touch,providerAfter=self.active()))
        self.state['current']['pending']=None;self.save()

    def observe(self,value):
        call=arguments('feature.create.observe',value);need(call['runId']==self.run)
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            self.load()
            if self.state is None:self.initialize()
            need(self.state['phase'] in ('baseline','active','cleaned'))
            for attempt in range(51):
                role=PhoneCreateRole(self,self.role)
                if role.state['phase']=='reading':role.recover()
                try:measured=role.read(call['afterSequence']);break
                except CreatePending:need(attempt<50);self.sleep(.1)
            if self.state['export'] is not None and self.state['export']['phase']=='saved' and self.state['phase']!='cleaned':
                original=role.frames[-1]['files'];need(original is not None)
                row=next(row for row in original['source']['files'] if row['name']=='selection.json')
                need(row['exists'] and row['sha256']==self.state['export']['sha256'])
                info=(self.root/self.state['export']['name']).lstat()
                need(dict(device=info.st_dev,inode=info.st_ino)==self.state['export']['file'])
                raw=read_private_artifact(self.root,self.state['export']['name']);need(hashlib.sha256(raw).hexdigest()==row['sha256'])
                measured['artifacts'].append(dict(kind='file',name=self.state['export']['name'],sequence=measured['sequence'],capturedEpochMs=original['capturedEpochMs'],ticket=self.phase.previous['activations'][-1]['ticket']))
            fresh(measured['capturedEpochMs'],self.adapter._native_feature_observer(self.selector,read_only=True).clock_ms());return measured

    def cleanup(self,value):
        call=arguments('feature.create.cleanup',value);need(self.role=='primary' and call['runId']==self.run)
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            self.load();need(self.state is not None)
            phase=self.phase.read();need(phase['verb']=='cleanup')
            self.recover_archive()
            for role_name in ('primary','actor'):
                role=PhoneCreateRole(self,role_name)
                if role.state['phase']=='reading':role.recover()
            if self.state['phase']=='cleaned':self.restored();return {'performed':True}
            # An uncertain earlier input is retained as evidence, never replayed.
            if self.state['current'] is not None:self.state['retained'].append(deepcopy(self.state['current']))
            self.state.update(phase='cleaning',current=dict(call=dict(contractVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,
                ticket=phase['ticket'],verb='cleanup',inputs={}),pending=None,phase='issuing'));self.save()
            ui=self.controls()
            if self.state['leases']['picker']:
                picker=ui.file_picker(ui.capture())
                if picker is not None:
                    ui.input('create-file.cancel');ui.wait(lambda value:ui.file_picker(value) is None)
                self.state['leases']['picker']=False;self.save()
            if self.state['permissionLease']:self.permissions('restore');self.permissions('retire')
            if self.state['creation'] is not None:
                original=self.state['creation']['before'];actual=self.entities()
                if same(original['source']['scan']['inventory'],actual['source']['scan']['inventory']):
                    self.state['retained'].append(dict(unissuedCreation=deepcopy(self.state['creation']),originalAfter=actual))
                    self.state['creation']=None;self.save()
                else:self.ensure_editor(ui);self.claim(ui)
            if self.entities()['source']['entities']:
                self.ensure_editor(ui);self.delete_objects(ui)
            if self.state['tools'] is not None:
                self.ensure_editor(ui);ui.restore_tools(self.state['tools'])
            if self.state['leases']['tablet']:self.sdk('home');self.sdk('close')
            if self.state['marker'] is not None and self.state['marker']['operation']=='prepare':
                if self.state['markerSource'] is None:
                    self.state['markerSource']=self.adapter._create_fixture_observer(self.selector,read_only=True).read(self.run);self.save()
                self.marker('release')
            if self.state['export'] is not None and self.state['export']['phase']!='saved':self.recover_export()
            if self.state['filesLease']:self.files().cleanup()
            self.surface().select_camera(self.state['original']['avatar']['source']['cameraMode'])
            final=self.entities();need(not final['source']['entities'] and not self.controls().capture()['open'])
            self.state.update(phase='cleaned',current=None);self.save();self.restored();return {'performed':True}


    def export_original(self):
        metadata=self.state['export']
        if metadata is None:return None
        need(metadata['phase']=='saved');path=self.root/metadata['name'];before=path.lstat()
        need(dict(device=before.st_dev,inode=before.st_ino)==metadata['file'])
        data=read_private_artifact(self.root,metadata['name']);after=path.lstat()
        need((before.st_dev,before.st_ino)==(after.st_dev,after.st_ino) and len(data)==metadata['bytes']
            and hashlib.sha256(data).hexdigest()==metadata['sha256'])
        return deepcopy(metadata)

    def restored(self,*,file_owner=None,snapshot=None):
        """Fresh actual absence/restoration, including world preservation."""
        need(self.state['phase']=='cleaned')
        if snapshot is not None:need(not snapshot.get('diagnostic') and snapshot['phaseAfter']['activations'][-1]['stimulus']['verb']=='cleanup')
        entities=self.entities() if snapshot is None else snapshot['entitiesAfter']
        ui=self.adapter._create_controls(self.selector,lambda *_:need(False),read_only=True).capture() if snapshot is None else snapshot['ui']
        need(not entities['source']['entities'] and not ui['open'])
        need(all(entities['source'][key]==self.state['original']['entities']['source'][key] for key in ('canRez','canRezTmp','canRezAvatarEntities')))
        avatar=self.adapter._avatar_render_observer(self.selector,read_only=True).read() if snapshot is None else snapshot['avatarAfter']
        need(avatar['source']['cameraMode']==self.state['original']['avatar']['source']['cameraMode'])
        touch=self.adapter._touch_state_observer(self.selector,read_only=True).read() if snapshot is None else snapshot['touch'];touch_released(touch)
        web=self.adapter._web_runtime_observer(self.selector,read_only=True).read(self.run,self.fixture_url) if snapshot is None else snapshot['web']
        if self.state['marker'] is not None:web_released(web)
        marker=None
        if self.state['marker'] is not None:
            marker=self.adapter._create_fixture_observer(self.selector,read_only=True).read(self.run) if snapshot is None else snapshot['marker']
            need(marker['source']['phase']=='drained' and not marker['source']['entities'] and marker['source']['retainedObjects']==0)
        files=None
        if self.state['filesLease']:
            if snapshot is not None:files=snapshot['files']
            elif file_owner is None:
                owner=self.files();files=owner.read()
            else:files=self.adapter._create_files(self.selector,read_only=True).request('observe',self.run,file_owner['ownerToken'])
            need(files['source']['retired'] and not files['source']['exists'])
        world=self.adapter._graphics_subject_observer(self.selector,read_only=True).read(self.run,require_avatar=True) if snapshot is None else snapshot['world']
        a={row['id']:row['sha256'] for row in self.state['original']['world']['source']['scan']['unowned']}
        b={row['id']:row['sha256'] for row in world['source']['scan']['unowned']};need(same(a,b))
        need(all(not self.state['leases'][key] for key in self.state['leases']) and not self.state['permissionLease'])
        return dict(entities=entities,ui=ui,avatar=avatar,touch=touch,web=web,marker=marker,files=files,world=world,exportOriginal=self.export_original())

    def finalize(self):
        from overte_phone_create_retirement import PhoneCreateRetirement
        return PhoneCreateRetirement(self).finalize()
