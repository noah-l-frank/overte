"""Ordinary Assets composition over independent native, file and server owners."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import secrets
import time
from urllib.parse import urlsplit,unquote,quote
from urllib.request import ProxyHandler,Request,build_opener

from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.token_assets_ui import snapshot as assets_snapshot
from adapters.token_create_ui import snapshot as create_snapshot
from adapters.native_phone_touch_state import released as touch_released
from adapters.native_phone_web_runtime import released as web_released
from feature_journeys.contract import arguments,json_document
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.scenarios import VERSION
from feature_journeys.asset_fixture import BUNDLES
from fixture.assets_permissions import asset_standard
from fixture.create_permissions import NoRedirect
from fixture.messages_mixer import start_identity
from overte_phone_create_feature import PhoneCreateFeature,configuration as create_configuration
from overte_phone_assets_backend import PhoneAssetsBackend,baseline,connection,inventory,owned_inventory,responsibility,sha
from overte_phone_assets_evidence import AssetsOriginals
from overte_phone_assets_file_owner import OwnedAssetsFiles
from overte_phone_assets_fixture import PREFIX
from overte_phone_script_history import pack,unpack,same,canonical
from overte_phone_script_lock import PhoneScriptSourceLock


def configuration(value,*,actor=False,original_configuration=False):
    need(type(actor) is bool and type(original_configuration) is bool and not(actor and original_configuration))
    common={'assetsFeatureVersion','artifactRoot','imageExtent','markerRoi','imagePolicy','domainId','permissionsControlUrl',
        'originalsControlUrl','originalsReadToken','originalsPrimaryTokenSha256','originalsActorTokenSha256'}
    exact(value,common|({'permissionsTokenSha256'} if actor or original_configuration else {'permissionsControlToken'}))
    need(urlsplit(value['permissionsControlUrl']).path=='/v1/assets-permissions')
    base={key:deepcopy(item) for key,item in value.items() if key in {'artifactRoot','imageExtent','markerRoi','imagePolicy','domainId','permissionsControlUrl','permissionsControlToken','permissionsTokenSha256'}}
    base.update(createFeatureVersion=value['assetsFeatureVersion'],permissionsControlUrl=value['permissionsControlUrl'].replace('/v1/assets-permissions','/v1/create-permissions'))
    create_configuration(base,actor=actor or original_configuration) # Same private-image/domain policy, no product source conversion.
    token=value['originalsReadToken'];need(type(token) is str and 32<=len(token)<=128 and all(33<=ord(ch)<=126 for ch in token))
    for key in ('originalsPrimaryTokenSha256','originalsActorTokenSha256'):
        need(type(value[key]) is str and len(value[key])==64 and all(ch in '0123456789abcdef' for ch in value[key]))
    need(value['originalsPrimaryTokenSha256']!=value['originalsActorTokenSha256'] and sha(token)==value['originalsActorTokenSha256' if actor else 'originalsPrimaryTokenSha256'])
    permission=value.get('permissionsTokenSha256') or sha(value['permissionsControlToken'])
    need(permission not in (value['originalsPrimaryTokenSha256'],value['originalsActorTokenSha256']))
    PhoneAssetsBackend(value['originalsControlUrl'],token,'a'*32,value['domainId'],lambda:True,lambda:1)
    return deepcopy(value)


class PhoneAssetsFeature(PhoneCreateFeature):
    # Existing original input archive, camera/UI lease, actual entity claim and
    # normal Properties/delete engines are reused without replacing their facts.
    def __init__(self,adapter,selector,phase,config,*,role='primary',original_configuration=False,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(phase,PhaseFixtureReader) and phase.area=='assets' and role in ('primary','actor'))
        self.adapter,self.selector,self.phase,self.role,self.config=adapter,selector,phase,role,configuration(config,actor=role=='actor',original_configuration=original_configuration)
        self.run,self.fixture_url=phase.run,phase.fixture_url;self.root=Path(config['artifactRoot']);self.policy=deepcopy(config['imagePolicy'])
        self.monotonic,self.sleep=monotonic,sleep;path=adapter.state_path(selector)
        self.store=PrivateFeatureState(path.with_name('phone-assets-feature.json'));self.lock=PhoneScriptSourceLock(path.with_name('phone-script-sources.lock'))
        self.previous=self.state=None
        _ui,_service,binding,self.guard,_installed=adapter.normal_feature_runtime(selector,read_only=True)
        self.binding=deepcopy(context(binding));self.pid=int(binding['processIdentity'].split(':')[0])
        self.inputs=AssetsOriginals(self.root,self.binding,self.run,'primary',self.bound,self.storage_intent,kind='assets-input')

    def public_configuration(self):
        value={key:deepcopy(item) for key,item in self.config.items() if key not in ('permissionsControlToken','originalsReadToken')}
        value['permissionsTokenSha256']=self.config.get('permissionsTokenSha256') or sha(self.config['permissionsControlToken']);return value

    def load(self):
        self.lock.assert_held();self.previous=self.store.read();self.state=None
        if self.previous is None:return
        value=self.previous;exact(value,{'assetsFeatureVersion','runId','fixtureUrl','binding','configuration','payload'})
        need(type(value['assetsFeatureVersion']) is int and value['assetsFeatureVersion']==1 and value['runId']==self.run
            and value['fixtureUrl']==self.fixture_url and same(value['binding'],self.binding) and same(value['configuration'],self.public_configuration()))
        rows=unpack(value['payload']);need(len(rows)==1);self.state=rows[0]
        exact(self.state,{'phase','original','inputTicket','domainId','nativeSessionId','objects','creation','current','actions','leases','hostProcess',
            'marker','markerSource','tools','permissionOwner','permissionLease','inputs','inputSequence','inputStorage','retained',
            'stages','stage','stageTickets','claims','backendOriginal','backendHistory','uploadsOriginal','bakeBarrier','downloadFile'})
        need(self.state['phase'] in ('baseline','active','acting','cleaning','cleaned','retiring') and type(self.state['objects']) is list and len(self.state['objects'])<=3
            and type(self.state['actions']) is list and len(self.state['actions'])<=64 and integer(self.state['inputSequence'],0,1024)
            and self.state['stages']==list(range(1,len(self.state['stages'])+1)) and len(self.state['stages'])<=6
            and (self.state['stage'] is None or self.state['stage'] in self.state['stages']))
        originals=self.inputs.restore(self.state['inputs'],self.state['inputSequence'])
        if self.state['inputStorage'] is not None:
            pending=self.state['inputStorage'];frame=pending['frame']
            # Verify authority against the exact pending original before the
            # existing prefix/inode engine completes any interrupted archive.
            self.validate_ownership(originals);self.validate_assets_ownership(originals+[frame]);self.recover_archive()
            originals=self.inputs.restore(self.state['inputs'],self.state['inputSequence'])
        self.validate_ownership(originals);self.validate_assets_ownership(originals)
        if self.state['phase']=='baseline' and self.state['current'] is not None:
            need(self.state['current']['call']['verb']=='baseline' and not self.state['actions']);self.state['current']=None;self.save()
        self.bound()

    def validate_assets_ownership(self,originals):
        # Destructive authority is reconstructed from immutable original input
        # files, never from mutable claim/current-path fields in the journal.
        need(originals and 'assetsBaseline' in originals[0])
        base=originals[0]['assetsBaseline'];need(same(base['backend'],self.state['backendOriginal']) and same(base['original'],self.state['original']))
        need(same(baseline(base['backend']['mappings'],base['backend']['backend'],self.run),base['backend']))
        claims={};stages={};barrier=None;transitions=[]
        for frame in originals:
            authority=any(key in frame for key in ('uploadIntent','bakingResponsibility','uploadResponsibility','renameResponsibility','deletionAfter'))
            prior=dict(claims=deepcopy(list(claims.values())),barrier=deepcopy(barrier)) if authority else None;verb=None
            if 'stageReservation' in frame:
                row=frame['stageReservation'];exact(row,{'stage','ticket'});need(row['stage']==len(stages)+1 and integer(row['stage'],1,6))
                stages[str(row['stage'])]=row['ticket']
            if 'uploadIntent' in frame and frame['uploadIntent']['resource']=='asset-stand.fbx':
                original=frame['uploadIntent']['backend']['source'];barrier=self.bake_barrier(original);verb='upload'
            if 'bakingResponsibility' in frame:barrier=deepcopy(frame['bakingResponsibility']);verb='set-baking'
            if 'uploadResponsibility' in frame:
                row=frame['uploadResponsibility'];actual=responsibility(row['source'],row['fileOriginal'],row['resource'],self.run,base['backend']['connection'])
                actual['currentPaths']={item['path']:item['hash'] for item in actual['published'].values()};need(same(actual,row));claims[row['bundleId']]=actual;verb='upload'
            if 'renameResponsibility' in frame:
                verb='rename-folder'
                row=frame['renameResponsibility'];before=inventory(row['before']);after=inventory(row['after'])
                paths={path:digest for claim in claims.values() for path,digest in claim['currentPaths'].items()}
                renamed={path.replace('/e2e-'+self.run+'/','/renamed-'+self.run+'/',1):digest for path,digest in paths.items()}
                need(same(renamed,row['paths']) and all(before.get(path,{}).get('hash')==digest and path not in after for path,digest in paths.items())
                    and all(after.get(path,{}).get('hash')==digest for path,digest in renamed.items()))
                for claim in claims.values():claim['currentPaths']={path.replace('/e2e-'+self.run+'/','/renamed-'+self.run+'/',1):digest for path,digest in claim['currentPaths'].items()}
            if 'deletionAfter' in frame:
                verb='delete-owned'
                after=inventory(frame['deletionAfter']);need(not any(path.startswith(('/e2e-'+self.run+'/','/renamed-'+self.run+'/')) for path in after))
                for claim in claims.values():claim['currentPaths']={}
            if verb is not None:transitions.append(dict(before=prior,after=dict(claims=deepcopy(list(claims.values())),barrier=deepcopy(barrier)),verb=verb))
        if not(same(list(claims.values()),self.state['claims']) and same(barrier,self.state['bakeBarrier'])):
            current=self.state['current'];need(current is not None and current['phase']=='issuing' and transitions)
            transition=transitions[-1]
            need((current['call']['verb']==transition['verb'] or self.state['phase']=='cleaning' and current['call']['verb']=='cleanup') and same(transition['before'],dict(claims=self.state['claims'],barrier=self.state['bakeBarrier']))
                and same(transition['after'],dict(claims=list(claims.values()),barrier=barrier)))
            self.state['claims']=deepcopy(list(claims.values()));self.state['bakeBarrier']=deepcopy(barrier);self.save()
        # A reservation may have been durably written immediately before its
        # archive; no native staging is issued until that archive completes.
        expected=deepcopy(self.state['stageTickets'])
        if stages!=expected:
            need(self.state['current'] is not None and len(expected)==len(stages)+1 and self.state['stage']==len(expected)
                and expected.pop(str(self.state['stage']))==self.state['current']['call']['ticket'] and expected==stages)
        need(set(self.state['stageTickets'])=={str(stage) for stage in self.state['stages']})
        for stage in range(1,7):
            header=PrivateFeatureState(self.store.path.with_name('phone-assets-files-owner-'+str(stage)+'.json')).read()
            if header is not None:
                need(stage in self.state['stages'] and header['stage']==stage and header['runId']==self.run and same(header['binding'],self.binding)
                    and header['inputTicket']==self.state['stageTickets'][str(stage)] and header['fixtureUrl']==self.fixture_url)

    @staticmethod
    def bake_barrier(source):
        # Worker times use the original server clock, not the phone clock.
        return dict(instance=source['instance'],sequence=source['sequence'],jobs=[row['instance'] for row in source['jobs']],epochMs=source['capturedEpochMs'])

    def save(self):
        self.bound();value=dict(assetsFeatureVersion=1,runId=self.run,fixtureUrl=self.fixture_url,binding=self.binding,configuration=self.public_configuration(),payload=pack([self.state]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def audit(self,kind,value):
        self.bound();current=self.state['current'];need(current is not None)
        if kind=='intent':
            need(current['pending'] is None);original=value['original']
            (assets_snapshot if 'assetsControlsVersion' in original else create_snapshot)(original)
            current['pending']=dict(kind='qt',intent=deepcopy(value),provider=self.active());self.save()
            if value['controlId']=='assets.upload':self.state['leases']['picker']=True;self.save()
        else:
            need(kind=='receipt' and current['pending'] is not None and same(current['pending']['intent'],value['intent']))
            before,after=value['intent']['original'],value['after'];(assets_snapshot if 'assetsControlsVersion' in after else create_snapshot)(after)
            need(before['scope']['processId']==after['scope']['processId']==self.pid and before['scope']['instance']==after['scope']['instance'] and after['scope']['sequence']>before['scope']['sequence'])
            self.archive_input(dict(input=current['pending'],after=deepcopy(after),providerAfter=self.active()));current['pending']=None;self.save()
        return True

    def controls(self):
        ui=self.adapter._assets_controls(self.selector,lambda *_:self.bound(),read_only=False);ui.audit=self.audit;return ui
    def create_controls(self):
        ui=self.adapter._create_controls(self.selector,lambda *_:self.bound(),read_only=False);ui.audit=self.audit;return ui
    def backend(self):
        clock=self.adapter._native_feature_observer(self.selector,read_only=True).clock_ms
        reader=PhoneAssetsBackend(self.config['originalsControlUrl'],self.config['originalsReadToken'],self.run,self.config['domainId'],self.bound,clock,monotonic=self.monotonic)
        if self.state is not None and self.state['backendHistory']:reader.last=deepcopy(self.state['backendHistory'][-1])
        return reader
    def backend_pair(self):
        reader=self.adapter._assets_source(self.selector,read_only=True);source=self.backend();started=self.monotonic()
        for attempt in range(51):
            packet=reader.read(self.run);backend=source.read()
            need(connection(packet['source'])==self.state['backendOriginal']['connection'] and self.monotonic()-started<5)
            if {row['path']:row['hash'] for row in packet['source']['mappings']}=={row['path']:row['hash'] for row in backend['source']['mappings']}:break
            need(attempt<50);self.sleep(.1)
        self.state['backendHistory'].append(backend);need(len(self.state['backendHistory'])<=256);self.save();return packet,backend
    def files(self,stage=None):
        stage=self.state['stage'] if stage is None else stage;need(stage in self.state['stages'])
        return OwnedAssetsFiles(self.adapter._assets_files(self.selector,read_only=False,stage=stage),
            PrivateFeatureState(self.store.path.with_name('phone-assets-files-owner-'+str(stage)+'.json')),self.binding,self.run,self.state['stageTickets'][str(stage)],self.fixture_url)
    def stage(self):
        need(self.state['stage'] is None and len(self.state['stages'])<6)
        stage=len(self.state['stages'])+1;self.state['stages'].append(stage);self.state['stageTickets'][str(stage)]=self.state['current']['call']['ticket'];self.state['stage']=stage;self.save();self.archive_input(dict(stageReservation=dict(stage=stage,ticket=self.state['current']['call']['ticket'])));return self.files().prepare()
    def retire_stage(self):
        if self.state['stage'] is None:return
        self.files().cleanup();self.state['stage']=None;self.save()
    def open_browser(self):
        ui=self.controls();self.sdk('open')
        if ui.page(ui.capture()) is None:
            create=self.create_controls();self.ensure_editor(create)
            if self.state['tools'] is None:self.state['tools']=create.actual_tools();self.save()
            ui.open_assets(create)
        return ui
    def close_browser(self):
        ui=self.controls()
        if ui.page(ui.capture()) is not None:ui.close_assets()

    def permissions(self,operation,allowed=None):
        need(self.role=='primary');self.active();command=dict(schemaVersion=1,runId=self.run,ownerToken=self.state['permissionOwner'],operation=operation)
        if allowed is not None:command['allowed']=allowed
        self.state['permissionLease']=True;self.save()
        request=Request(self.config['permissionsControlUrl'],data=canonical(command),headers={'Content-Type':'application/json','X-Overte-E2E-Token':self.config['permissionsControlToken']})
        with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=5) as response:
            need(response.status==200 and response.geturl()==self.config['permissionsControlUrl']);raw=response.read(65537)
        need(len(raw)<=65536);value=json_document(raw);exact(value,{'assetsPermissionsVersion','domainId','sequence','capturedEpochMs','restored','standard'})
        need(type(value['assetsPermissionsVersion']) is int and value['assetsPermissionsVersion']==1 and value['domainId']==self.state['domainId'] and type(value['restored']) is bool)
        asset_standard(value['standard']);self.archive_input(dict(command={key:item for key,item in command.items() if key!='ownerToken'},original=value))
        if operation=='retire':need(value['restored']);self.state['permissionLease']=False;self.save()
        return value

    def initialize(self):
        need(self.role=='primary' and self.state is None);phase=self.phase.read();need(phase['verb']=='baseline')
        source=self.adapter._create_source(self.selector,read_only=True).read(self.run)
        ui=self.adapter._create_controls(self.selector,lambda *_:need(False),read_only=True).capture()
        assets=self.adapter._assets_controls(self.selector,lambda *_:need(False),read_only=True).capture()
        avatar=self.adapter._avatar_render_observer(self.selector,read_only=True).read();touch=self.adapter._touch_state_observer(self.selector,read_only=True).read();touch_released(touch)
        world=self.adapter._graphics_subject_observer(self.selector,read_only=True).read(self.run,require_avatar=True)
        native=self.adapter._assets_source(self.selector,read_only=True).read(self.run)
        # The baseline source has no feature owner yet; its guard still pins the
        # existing process and empty journal through the held lock.
        backend=self.backend().read();original=baseline(native,backend,self.run)
        need(not ui['open'] and not any(row['id']=='assets.page' for row in assets['controls']) and not source['source']['entities']
            and source['source']['connected'] and source['source']['canRez'] and source['source']['domainId']==self.config['domainId'] and native['source']['canWrite'])
        uploads=self.adapter._assets_uploads(self.selector,read_only=True).request('observe',self.run);need(not uploads['source']['bundles'] and not uploads['source']['retired'])
        self.state=dict(phase='baseline',original=dict(entities=source,ui=ui,assets=assets,avatar=avatar,touch=touch,world=world),inputTicket=phase['ticket'],
            domainId=source['source']['domainId'],nativeSessionId=source['source']['sessionId'],objects=[],creation=None,current=None,actions=[],
            leases=dict(tablet=False,menu=False,address=False,picker=False),hostProcess=dict(pid=os.getpid(),start=start_identity(os.getpid())),marker=None,markerSource=None,tools=None,
            permissionOwner=secrets.token_hex(32),permissionLease=False,inputs=[],inputSequence=0,inputStorage=None,retained=[],stages=[],stage=None,stageTickets={},claims=[],
            backendOriginal=original,backendHistory=[backend],uploadsOriginal=uploads,bakeBarrier=None,downloadFile=None);self.save()
        self.state['current']=dict(call=dict(contractVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,ticket=phase['ticket'],verb='baseline',inputs={}),pending=None,phase='issuing');self.save()
        self.archive_input(dict(assetsBaseline=dict(backend=deepcopy(original),original=deepcopy(self.state['original']))));self.state['current']=None;self.save()

    def reconcile_upload(self,resource):
        original=self.files().read();reader=self.adapter._assets_uploads(self.selector,read_only=True);reader.last=deepcopy(self.state['uploadsOriginal'])
        started=self.monotonic()
        for attempt in range(51):
            actual=reader.request('observe',self.run);need(self.monotonic()-started<5)
            if not actual['source']['activeBundles'] and not actual['source']['liveRequests']:break
            need(attempt<50);self.sleep(.1)
        claim=responsibility(actual,original,resource,self.run,self.state['backendOriginal']['connection'])
        claim['currentPaths']={row['path']:row['hash'] for row in claim['published'].values()}
        prior=[row for row in self.state['claims'] if row['bundleId']==claim['bundleId']]
        if prior:
            need(len(prior)==1);self.state['claims'][self.state['claims'].index(prior[0])]=claim
        else:need(len(self.state['claims'])<6);self.state['claims'].append(claim)
        self.archive_input(dict(uploadResponsibility=deepcopy(claim)));self.state['uploadsOriginal']=actual;self.save();return claim

    def checked_inventory(self):
        packet,backend=self.backend_pair();owned=owned_inventory(packet,backend,self.state['backendOriginal'],self.state['claims'],self.run);return packet,backend,owned

    def claim_asset_model(self,ui):
        before=self.state['creation']['before'];known={row['id'] for row in before['source']['scan']['inventory']}
        for attempt in range(51):
            actual=self.entities();added=[row for row in actual['source']['scan']['inventory'] if row['id'] not in known]
            if added:break
            need(attempt<50);self.sleep(.1)
        need(len(added)==1 and added[0]['type']=='Model' and added[0]['host']=='domain')
        self.ensure_editor(ui);ui.select_entity(added[0]['id']);return self.claim(ui)

    def act(self,value):
        call=deepcopy(arguments('feature.assets.act',value));need(self.role=='primary' and call['runId']==self.run and call['fixtureUrl']==self.fixture_url)
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            self.load();need(self.state is not None and self.state['phase'] not in ('cleaning','cleaned','retiring'))
            found=[row for row in self.state['actions'] if row['ticket']==call['ticket']]
            if found:need(len(found)==1 and found[0]['phase']=='acknowledged' and same(found[0]['call'],call));return {'performed':True}
            need(self.state['current'] is None);current=dict(call=call,pending=None,phase='issuing');self.state['actions'].append(dict(ticket=call['ticket'],call=call,phase='issuing'))
            self.state.update(phase='acting',current=current);self.save();self.active();ui=self.controls();verb=call['verb'];inputs=call['inputs']
            if verb=='open':
                self.surface().select_camera('first person look at');self.marker('prepare');self.open_browser()
            elif verb=='close':
                self.close_browser();create=self.create_controls();self.ensure_editor(create)
                if self.state['tools'] is not None:create.restore_tools(self.state['tools'])
                self.sdk('home');self.sdk('close');self.marker('release');self.surface().select_camera(self.state['original']['avatar']['source']['cameraMode'])
            elif verb=='upload-picker-open':
                directory=self.stage();ui.open_picker();ui.navigate_files(unquote(urlsplit(directory).path)+'/gltf-bundle')
            elif verb=='upload-picker-cancel':
                ui.cancel_picker();self.state['leases']['picker']=False;self.save();self.retire_stage()
            elif verb=='upload':
                self.checked_inventory();directory=self.stage();resource=inputs['resource']
                self.archive_input(dict(uploadIntent=dict(resource=resource,files=self.files().read(),backend=self.state['backendHistory'][-1],uploads=self.state['uploadsOriginal'])))
                if resource=='asset-stand.fbx':self.state['bakeBarrier']=self.bake_barrier(self.state['backendHistory'][-1]['source']);self.save()
                ui.upload_bundle(unquote(urlsplit(directory).path),resource,'/e2e-'+self.run+'/')
                claim=self.reconcile_upload(resource);need(claim['terminal'] and claim['complete'])
                self.checked_inventory();ui.input('assets.refresh');ui.select_mapping('/e2e-'+self.run+'/'+BUNDLES[resource][0]);self.state['leases']['picker']=False;self.save();self.retire_stage()
            elif verb=='browse':self.checked_inventory();ui.select_mapping('/'+inputs['name'])
            elif verb=='rename-folder':
                _packet,_backend,owned=self.checked_inventory();need(owned and all(path.startswith('/e2e-'+self.run+'/') for path in owned))
                selected=ui.page(ui.capture())['selectedPath'];need(selected in owned);ui.select_mapping('/e2e-'+self.run+'/');ui.rename_folder('/'+inputs['name']+'/')
                # Reconcile only the exact original path/hash bijection after
                # this archived normal rename input. No unknown row is adopted.
                packet,backend=self.backend_pair();rows=inventory(packet);renamed={path.replace('/e2e-'+self.run+'/','/renamed-'+self.run+'/',1):row['hash'] for path,row in owned.items()}
                need(all(path not in rows for path in owned) and {path:row['hash'] for path,row in rows.items() if path.startswith('/renamed-'+self.run+'/')}==renamed)
                self.archive_input(dict(renameResponsibility=dict(before=_packet,after=packet,backend=backend,paths=renamed)))
                for claim in self.state['claims']:claim['currentPaths']={row['path'].replace('/e2e-'+self.run+'/','/renamed-'+self.run+'/',1):row['hash'] for row in claim['published'].values()}
                self.save();self.checked_inventory();ui.input('assets.refresh');ui.select_mapping(selected.replace('/e2e-'+self.run+'/','/renamed-'+self.run+'/',1))
            elif verb=='inspect-baking-unavailable':need(not ui.row(ui.capture(),'assets.baking',enabled=False)['enabled'])
            elif verb=='import-selected':
                self.checked_inventory();self.begin_creation('model');ui.import_selected();self.close_browser();self.claim_asset_model(self.create_controls());self.open_browser()
                # Reselect the actual model URL, not an action expectation.
                entity=next(row for row in self.entities()['source']['entities'] if row['id']==self.state['objects'][-1]['id']);need(entity['modelUrl'].startswith('atp:/'))
                self.controls().select_mapping(entity['modelUrl'][4:])
            elif verb=='remove-owned-model':
                selected=ui.page(ui.capture())['selectedPath'];self.close_browser();create=self.create_controls();self.ensure_editor(create);self.delete_objects(create);self.open_browser();self.controls().select_mapping(selected)
            elif verb=='set-write-permission':self.permissions('set',inputs['allowed'])
            elif verb=='delete-denied':
                packet,backend,owned=self.checked_inventory();need(not packet['source']['canWrite'] and not ui.row(ui.capture(),'assets.delete',enabled=False)['enabled'])
                ui.input('assets.delete','probe-disabled');after,after_backend,actual=self.checked_inventory();need(same(owned,actual));self.archive_input(dict(deniedBefore=packet,deniedAfter=after,backendBefore=backend,backendAfter=after_backend))
            elif verb=='delete-owned':self.delete_mappings(ui)
            elif verb=='set-baking':
                packet,backend,owned=self.checked_inventory();selected=ui.page(ui.capture())['selectedPath'];need(selected in owned and owned[selected]['bakeStatus'] in (1,4))
                if inputs['enabled']:
                    self.state['bakeBarrier']=self.bake_barrier(backend['source']);self.archive_input(dict(bakingResponsibility=deepcopy(self.state['bakeBarrier'])));self.save()
                ui.baking(inputs['enabled'])
            elif verb=='upload-picker-select':
                directory=self.files().read()['source']['directory'];ui.select_file(directory+'/gltf-bundle/main.gltf')
            elif verb=='retire-staged-primary':self.files().retire_primary()
            elif verb=='upload-picker-accept-unavailable':
                need(self.files().read()['source']['primaryRetired']);ui.input('assets-file.accept')
                ui.wait(lambda value:ui.file_picker(value) is not None and ui.file_picker(value)['error']=='A selected file is no longer available.')
            else:need(False)
            need(current['pending'] is None);current['phase']='acknowledged';self.state['actions'][-1]['phase']='acknowledged';self.state.update(current=None,phase='active');self.save();return {'performed':True}

    def delete_mappings(self,ui):
        packet,backend,owned=self.checked_inventory()
        roots=sorted({'/'+path.split('/')[1]+'/' for path in owned})
        for root in roots:ui.select_mapping(root);ui.delete_selected();ui.input('assets.refresh')
        for attempt in range(51):
            final,actual,remaining=self.checked_inventory()
            hashes={row['returnedHash'] for claim in self.state['claims'] for row in claim['uploads'].values()}
            if not remaining and not any(row['hash'] in hashes or any(row['path'].startswith('/.baked/'+digest+'/') for digest in hashes) for row in actual['source']['mappings']) and not any(row['hash'] in hashes for row in actual['source']['blobs']):break
            need(attempt<50);self.sleep(.1)
        self.archive_input(dict(deletionBefore=packet,deletionAfter=final,backendAfter=actual))
        for claim in self.state['claims']:claim['currentPaths']={}
        self.save()

    def observe(self,value):
        from overte_phone_assets_role import PhoneAssetsRole
        from overte_phone_create_measurements import CreatePending
        call=arguments('feature.assets.observe',value);need(call['runId']==self.run)
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            self.load()
            if self.state is None:self.initialize()
            need(self.state['phase'] in ('baseline','active','cleaned'))
            for attempt in range(51):
                role=PhoneAssetsRole(self,self.role)
                if role.state['phase']=='reading':role.recover()
                try:measured=role.read(call['afterSequence']);break
                except CreatePending:need(attempt<50);self.sleep(.1)
            fresh(measured['capturedEpochMs'],self.adapter._native_feature_observer(self.selector,read_only=True).clock_ms());return measured

    def cleanup(self,value):
        from overte_phone_assets_role import PhoneAssetsRole
        call=arguments('feature.assets.cleanup',value);need(self.role=='primary' and call['runId']==self.run)
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            self.load();need(self.state is not None);phase=self.phase.read();need(phase['verb']=='cleanup');self.recover_archive()
            for role_name in ('primary','actor'):
                role=PhoneAssetsRole(self,role_name)
                if role.state['phase']=='reading':role.recover()
            if self.state['phase']=='cleaned':self.restored();return {'performed':True}
            uncertain=deepcopy(self.state['current'])
            if uncertain is not None:self.state['retained'].append(uncertain)
            self.state.update(phase='cleaning',current=dict(call=dict(contractVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,ticket=phase['ticket'],verb='cleanup',inputs={}),pending=None,phase='issuing'));self.save()
            ui=self.controls()
            # Close only observed owned normal dialogs, through their real
            # Cancel controls. Never replay an uncertain acceptance or upload.
            for dialog in ('model','destination','rename','delete'):
                if ui.row(ui.capture(),'assets.'+dialog+'.cancel') is not None:ui.input('assets.'+dialog+'.cancel')
            if ui.file_picker(ui.capture()) is not None:ui.cancel_picker()
            self.state['leases']['picker']=False;self.save()
            uploads=self.adapter._assets_uploads(self.selector,read_only=True)
            if uncertain is not None and uncertain['call']['verb']=='upload' and self.state['stage'] is not None:
                resource=uncertain['call']['inputs']['resource'];actual=uploads.request('observe',self.run)
                directory=self.files().read()['source']['directory'];expected=sha(unquote(urlsplit(directory).path)+'/'+PREFIX[resource])
                if any(row['directorySha256']==expected for row in actual['source']['bundles']):
                    # Normal close cancels a still-active bundle through the
                    # product page's existing lifetime handler.
                    if actual['source']['activeBundles']:self.close_browser()
                    for attempt in range(51):
                        actual=uploads.request('observe',self.run)
                        if not actual['source']['activeBundles'] and not actual['source']['liveRequests']:break
                        need(attempt<50);self.sleep(.1)
                    self.reconcile_upload(resource)
            if self.state['permissionLease']:self.permissions('restore');self.permissions('retire')
            if self.state['creation'] is not None:
                before=self.state['creation']['before'];actual=self.entities()
                if same(before['source']['scan']['inventory'],actual['source']['scan']['inventory']):
                    self.archive_input(dict(unissuedCreation=deepcopy(self.state['creation']),originalAfter=actual));self.state['creation']=None;self.save()
                else:self.close_browser();self.claim_asset_model(self.create_controls())
            if self.entities()['source']['entities']:
                self.close_browser();create=self.create_controls();self.ensure_editor(create);self.delete_objects(create)
            # Original responsibility is checked before opening/destructively
            # selecting any path. Partial published bundles remain included.
            packet,backend,owned=self.checked_inventory()
            hashes={row['returnedHash'] for claim in self.state['claims'] for row in claim['uploads'].values()}
            if owned:self.delete_mappings(self.open_browser())
            elif any(row['hash'] in hashes for row in backend['source']['blobs']):
                # A fully uploaded but unpublished canceled bundle can leave
                # unreferenced blobs. Use a NEW ordinary cleanup upload intent,
                # then normal folder Delete invokes actual server collection.
                # This is never replay of an uncertain original command.
                need(uncertain is not None and uncertain['call']['verb']=='upload')
                if self.state['stage'] is None:directory=self.stage()
                else:directory=self.files().read()['source']['directory']
                resource=uncertain['call']['inputs']['resource'];ui=self.open_browser()
                self.archive_input(dict(cleanupUploadIntent=dict(files=self.files().read(),backend=backend,resource=resource)))
                ui.upload_bundle(unquote(urlsplit(directory).path),resource,'/e2e-'+self.run+'/');claim=self.reconcile_upload(resource);need(claim['complete']);self.delete_mappings(ui)
            for stage in self.state['stages']:self.files(stage).cleanup()
            self.state['stage']=None;self.save();self.close_browser()
            if self.state['tools'] is not None:
                create=self.create_controls();self.ensure_editor(create);create.restore_tools(self.state['tools'])
            if self.state['leases']['tablet']:self.sdk('home');self.sdk('close')
            if self.state['marker'] is not None and self.state['marker']['operation']=='prepare':self.marker('release')
            self.surface().select_camera(self.state['original']['avatar']['source']['cameraMode'])
            current=uploads.request('observe',self.run);need(not current['source']['activeBundles'] and not current['source']['liveRequests'])
            ids=[row['id'] for row in current['source']['bundles']]
            if not current['source']['retired']:
                self.archive_input(dict(uploadReleaseIntent=current));released=uploads.request('release',self.run,current['source']['instance'],ids)
                self.archive_input(dict(uploadReleaseOriginal=released))
            else:released=current
            need(released['source']['retired'] and not released['source']['bundles']);self.state['uploadsOriginal']=released
            self.state.update(phase='cleaned',current=None);self.save();self.restored();return {'performed':True}

    def restored(self,*,file_owners=None,snapshot=None):
        need(self.state['phase']=='cleaned');f=self.state
        if snapshot is not None:need(not snapshot.get('diagnostic') and snapshot['phaseAfter']['activations'][-1]['stimulus']['verb']=='cleanup')
        entities=self.entities() if snapshot is None else snapshot['entitiesAfter'];need(not entities['source']['entities'])
        create=self.adapter._create_controls(self.selector,lambda *_:need(False),read_only=True).capture();need(not create['open'])
        ui=self.adapter._assets_controls(self.selector,lambda *_:need(False),read_only=True).capture() if snapshot is None else snapshot['ui']
        need(not any(row['id'].startswith(('assets.','assets-file.')) for row in ui['controls']))
        avatar=self.adapter._avatar_render_observer(self.selector,read_only=True).read() if snapshot is None else snapshot['avatarAfter']
        need(avatar['source']['cameraMode']==f['original']['avatar']['source']['cameraMode'])
        touch=self.adapter._touch_state_observer(self.selector,read_only=True).read() if snapshot is None else snapshot['touch'];touch_released(touch)
        web=self.adapter._web_runtime_observer(self.selector,read_only=True).read(self.run,self.fixture_url) if snapshot is None else snapshot['web']
        marker=None
        if f['marker'] is not None:
            from overte_phone_create_marker import retired
            web_released(web);marker=self.adapter._create_fixture_observer(self.selector,read_only=True).read(self.run) if snapshot is None else snapshot['marker'];retired(marker)
        if snapshot is None:
            packet=self.adapter._assets_source(self.selector,read_only=True).read(self.run);backend=self.backend().read()
            owned=owned_inventory(packet,backend,f['backendOriginal'],f['claims'],self.run)
        else:
            packet,backend=snapshot['mappingAfter'],snapshot['backendAfter'];owned=owned_inventory(packet,backend,f['backendOriginal'],f['claims'],self.run)
        need(not owned and packet['source']['canWrite']==f['backendOriginal']['mappings']['source']['canWrite'])
        need({row['path']:row['hash'] for row in backend['source']['mappings']}=={row['path']:row['hash'] for row in f['backendOriginal']['backend']['source']['mappings']}
            and {row['hash']:row for row in backend['source']['blobs']}=={row['hash']:row for row in f['backendOriginal']['backend']['source']['blobs']}
            and backend['source']['pending']==0 and all(row['terminalEpochMs'] is not None and row['runExitedEpochMs'] is not None and row['destroyedEpochMs'] is not None for row in backend['source']['jobs']))
        uploads=self.adapter._assets_uploads(self.selector,read_only=True).request('observe',self.run) if snapshot is None else snapshot['uploads']
        need(uploads['source']['retired'] and not uploads['source']['bundles'] and uploads['source']['instance']==f['uploadsOriginal']['source']['instance'])
        files={}
        for stage in f['stages']:
            metadata=(PrivateFeatureState(self.store.path.with_name('phone-assets-files-owner-'+str(stage)+'.json')).read() if file_owners is None else file_owners[str(stage)])
            need(metadata is not None and metadata['runId']==self.run and metadata['binding']==self.binding and metadata['phase']=='retired')
            actual=self.adapter._assets_files(self.selector,read_only=True,stage=stage).request('observe',self.run,metadata['ownerToken']) if snapshot is None else snapshot['stageFiles'][str(stage)]
            need(actual['source']['retired'] and not actual['source']['exists']);files[str(stage)]=actual
        world=self.adapter._graphics_subject_observer(self.selector,read_only=True).read(self.run,require_avatar=True) if snapshot is None else snapshot['world']
        need({row['id']:row['sha256'] for row in world['source']['scan']['unowned']}=={row['id']:row['sha256'] for row in f['original']['world']['source']['scan']['unowned']}
            and all(not flag for flag in f['leases'].values()) and not f['permissionLease'])
        return dict(entities=entities,create=create,ui=ui,avatar=avatar,touch=touch,web=web,marker=marker,mappings=packet,backend=backend,uploads=uploads,files=files,world=world)

    def finalize(self):
        from overte_phone_assets_retirement import PhoneAssetsRetirement
        return PhoneAssetsRetirement(self).finalize()
