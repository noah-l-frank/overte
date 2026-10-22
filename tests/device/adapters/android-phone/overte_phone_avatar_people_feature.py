"""Public Phone Avatar/People owner over normal input and original sources.

No acknowledgment supplies state. The independently credentialed actor owns a
second Phone; primary observations never acquire that actor's control privilege.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import hashlib
import math
import re
import time
import uuid
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import arguments,identifier,result
from feature_journeys.fixtures import context as fixture_context
from feature_journeys.phase_fixture import PhasePending,PhaseRetired
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from feature_journeys.witness import projection
from overte_phone_avatar_people_fixture import AvatarPeopleFixtureReader
from overte_phone_avatar_people_native import validate as native_packet,ACTION,digest
from overte_phone_avatar_people_measurements import request,resources,measurement,wearable,social_replies
from overte_phone_avatar_people_pixels import measure as pixels
from overte_phone_script_ui import PhoneScriptUI
from overte_phone_script_lock import PhoneScriptSourceLock
from overte_phone_script_history import pack,unpack,canonical,same
from overte_phone_graphics_surface import PhoneGraphicsSurface,MODES
from overte_phone_navigation_marker import input_command,input_receipt,retired as marker_retired,camera_lease,VIEW,near,layout,rotation_equal,NULL_ID
from adapters.native_phone_web_runtime import active_marker,released as web_released
from overte_phone_graphics_images import PhoneGraphicsImages

VERSION=1
AREA='avatar-people'
PACKAGE='io.github.noah_be.overte.phone'
VISUAL={'baseline','avatar-url','avatar-scale','wearable-add','avatar-bookmark-choose','avatar-restore'}
QUIET={'connection-cancel','peer-reject','connection-remove','cleanup'}


def image_policy(value):
    """Reject incomplete image authority before any target input is possible."""
    from feature_journeys.evidence import rectangle
    exact(value,{'imageExtent','markerRoi','imagePolicy'})
    extent=value['imageExtent'];need(type(extent) is list and len(extent)==2 and all(integer(v,240,4096) for v in extent))
    outer=rectangle(value['markerRoi'],extent);policy=value['imagePolicy'];exact(policy,{'source','marker','subject'})
    need(policy['source']=='world-render-target');marker=rectangle(policy['marker'],extent);subject=rectangle(policy['subject'],extent)
    w,h=outer[2]-outer[0],outer[3]-outer[1]
    need(w>=160 and h>=40 and w*h<=.1*extent[0]*extent[1]
        and marker==tuple(round(v) for v in (outer[0]+w*4/160,outer[1]+h*4/40,outer[0]+w*132/160,outer[1]+h*36/40))
        and not (max(outer[0],subject[0])<min(outer[2],subject[2]) and max(outer[1],subject[1])<min(outer[3],subject[3])))
    return deepcopy(value)


def held_marker(packet,request):
    """Original fixture objects remain required while ordinary scale changes."""
    source=packet['source'];need(same(source['originalInput'],request) and source['phase']=='active'
        and source['retainedObjects']==1 and len(source['entities'])==1 and not source['absentIds'])
    camera_lease(source['cameraLease'],source['originalView'],packet['capturedEpochMs']);need(source['cameraLease']['phase']=='held')
    wanted=layout(source)
    for row in source['entities']:
        expected=wanted[row['role']]
        need(row['role']=='marker' and row['originalObject'] and row['hostType']=='local' and row['parentId']==NULL_ID
            and row['type']=='Web' and row['visible'] and not row['locked'] and row['collisionless'] and not row['canCastShadow']
            and row['name']=='e2e-'+source['runId']+'-navigation-marker' and row['dpi']==100
            and row['sourceUrl']==request['fixtureUrl']+'tickets/'+request['ticket']+'/graphics-marker.v1.html'
            and near(row['position'],expected['position'],.001) and near(row['dimensions'],expected['dimensions'],.001)
            and rotation_equal(row['rotation'],expected['rotation'],.0001))


def read_blob(root,run,reference):
    exact(reference,{'avatarPeopleBlobVersion','name','sha256'})
    need(type(reference['avatarPeopleBlobVersion']) is int and reference['avatarPeopleBlobVersion']==1 and type(reference['sha256']) is str and re.fullmatch('[0-9a-f]{64}',reference['sha256']))
    name='avatar-people-'+run+'-'+reference['sha256'][:32]+'.json';need(reference['name']==name)
    record=PrivateFeatureState(Path(root)/name).read();need(record is not None)
    exact(record,{'avatarPeopleBlobVersion','runId','payload'});need(type(record['avatarPeopleBlobVersion']) is int and record['avatarPeopleBlobVersion']==1 and record['runId']==run)
    rows=unpack(record['payload']);need(len(rows)==1 and hashlib.sha256(canonical(rows[0])).hexdigest()==reference['sha256']);return rows[0]


class AvatarPeopleImages(PhoneGraphicsImages):
    KIND='avatar-people'


class PhoneAvatarPeopleFeature:
    def __init__(self,adapter,selector,source,root,policy,*,role='primary',peer_selector=None,peer_policy=None,
                 monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(source,AvatarPeopleFixtureReader) and role in ('primary','actor') and callable(monotonic) and callable(sleep)
            and (role=='primary' and peer_selector is None and peer_policy is None or role=='actor' and type(peer_selector) is str and peer_selector!=selector))
        self.adapter,self.selector,self.source,self.role=adapter,selector,source,role
        self.subject=selector if role=='primary' else peer_selector
        self.run,self.fixture_url=source.run,source.fixture_url
        self.root,self.policy=Path(root),image_policy(policy if role=='primary' else peer_policy)
        self.monotonic,self.sleep=monotonic,sleep
        path=adapter.state_path(selector)
        self.store=PrivateFeatureState(path.with_name('phone-avatar-people-feature.json'))
        self.role_store=PrivateFeatureState(path.with_name('phone-avatar-people-'+role+'-feature.json'))
        self.retirement_store=PrivateFeatureState(path.with_name('phone-avatar-people-retirement.json'))
        self.lock=PhoneScriptSourceLock(path.with_name('phone-script-sources.lock'))
        self.peer_lock=None if role=='primary' else PhoneScriptSourceLock(adapter.state_path(self.subject).with_name('phone-script-sources.lock'))
        self.previous={};self.state=None;self.local=None;self.readers={};self.started=self.clock=None

    def bound(self):
        self.lock.assert_held();now=self.monotonic();need(number(now,0,1e15) and (self.clock is None or now>=self.clock)
            and (self.started is None or now-self.started<45));self.clock=now

    @contextmanager
    def scope(self):
        failure=None
        with self.lock.held():
            self.started=self.monotonic()
            try:
                if self.peer_lock is None:
                    try:yield
                    except Exception as error:failure=error
                else:
                    with self.peer_lock.held():
                        try:yield
                        except Exception as error:failure=error
                self.bound()
            finally:self.started=None
        # The shared lock deliberately sanitizes exceptions. Preserve the
        # feature's typed pending/retired state after both locks are released.
        if failure is not None:raise failure

    def read(self,store,kind):
        value=store.read();self.previous[store.path]=deepcopy(value)
        if value is None:return None
        exact(value,{'avatarPeopleFeatureVersion','kind','runId','fixtureUrl','artifactRoot','payload'})
        need(type(value['avatarPeopleFeatureVersion']) is int and value['avatarPeopleFeatureVersion']==VERSION and value['kind']==kind
            and value['runId']==self.run and value['fixtureUrl']==self.fixture_url and value['artifactRoot']==str(self.root))
        rows=unpack(value['payload']);need(len(rows)==1);return rows[0]

    def save(self,store,kind,value):
        self.bound();need(store.path in self.previous and same(store.read(),self.previous[store.path]))
        record=dict(avatarPeopleFeatureVersion=VERSION,kind=kind,runId=self.run,fixtureUrl=self.fixture_url,
            artifactRoot=str(self.root),payload=pack([value]));store.write(record,self.previous[store.path])
        need(same(store.read(),record));self.previous[store.path]=deepcopy(record)

    def blob(self,value=None,*,reference=None):
        self.bound()
        if reference is not None:
            return read_blob(self.root,self.run,reference)
        sha=hashlib.sha256(canonical(value)).hexdigest();name='avatar-people-'+self.run+'-'+sha[:32]+'.json'
        record=dict(avatarPeopleBlobVersion=1,runId=self.run,payload=pack([value]));store=PrivateFeatureState(self.root/name);old=store.read()
        if old is None:store.write(record,None)
        else:need(same(old,record))
        need(same(store.read(),record));return dict(avatarPeopleBlobVersion=1,name=name,sha256=sha)

    def load(self):
        self.state=self.read(self.store,'owner');self.local=self.read(self.role_store,self.role)
        if self.state is not None:
            exact(self.state,{'phase','binding','policy','original','ticket','call','phaseStatus','backend','bookmark','primaryReady','cleanup','final'})
            image_policy(self.state['policy'])
            if self.role=='primary':need(same(self.state['policy'],self.policy))
            context(self.state['binding']);need(self.state['phase'] in ('preparing','baseline','acting','active','cleaning','cleaned'))
            backend=self.state['backend']
            need(self.source.instance in (None,backend['instance']) and self.source.domain in (None,backend['domainId']))
            self.source.instance,self.source.domain=backend['instance'],backend['domainId']
            self.source.backend=deepcopy(backend)
        if self.local is not None:
            exact(self.local,{'phase','samplingPhase','binding','policy','original','baseline','leases','steps','marker','markerRetired','last','frames','images','sequence','quiet','retired'})
            context(self.local['binding']);need(same(self.local['policy'],self.policy));need(self.local['phase'] in ('preparing','ready','reading','cleaning','cleaned','retired')
                and integer(self.local['sequence'],0,1000000000) and type(self.local['steps']) is list and len(self.local['steps'])<=256
                and type(self.local['frames']) is list and len(self.local['frames'])<=128 and type(self.local['images']) is list and len(self.local['images'])<=128)
            need(self.local['samplingPhase'] in (None,'ready','cleaned','retired'))
            exact(self.local['leases'],{'tablet','address','menu'});need(all(type(v) is bool for v in self.local['leases'].values()))
            for row in self.local['steps']:
                exact(row,{'scope','stage','phase','original'});need(row['phase'] in ('issued','returned'))
        return self.state

    def owner_save(self):need(self.role=='primary');self.save(self.store,'owner',self.state)
    def role_save(self):self.save(self.role_store,self.role,self.local)

    def runtime(self,selector=None):
        selector=self.subject if selector is None else selector
        runtime=self.adapter.normal_feature_runtime(selector,read_only=True);context(runtime[2]);need(runtime[3]() is not False)
        binding=self.local['binding'] if selector==self.subject and self.local else self.state['binding'] if selector==self.selector and self.state else None
        if binding is not None:need(same(binding,runtime[2]))
        if self.role=='actor':
            primary=self.adapter.normal_feature_runtime(self.selector,read_only=True)[2];peer=self.adapter.normal_feature_runtime(self.subject,read_only=True)[2]
            need(primary['sourceRevision']==peer['sourceRevision'] and primary['artifactSha256']==peer['artifactSha256']
                and primary['sessionId']!=peer['sessionId'] and primary['targetFingerprint']!=peer['targetFingerprint'])
        self.bound();return runtime

    def native(self,selector=None):
        selector=self.subject if selector is None else selector;self.runtime(selector)
        if selector not in self.readers:
            reader=self.adapter._avatar_people_source(selector,read_only=True)
            if self.local and selector in self.local['last']:reader.restore([self.blob(reference=self.local['last'][selector])])
            self.readers[selector]=reader
        value=self.readers[selector].read(self.run);self.bound()
        if self.local is not None:
            self.local['last'][selector]=self.blob(value);self.role_save()
        return value

    def wait_native(self,predicate,timeout=12,selector=None):
        start=self.monotonic()
        for attempt in range(241):
            value=self.native(selector)
            if predicate(value):return value
            need(attempt<240 and self.monotonic()-start<timeout);self.sleep(.1)
        need(False)

    def step(self,scope,stage,original,action):
        rows=[r for r in self.local['steps'] if r['scope']==scope and r['stage']==stage];need(len(rows)<=1)
        if rows:need(rows[0]['phase']=='returned');return
        need(len(self.local['steps'])<256);row=dict(scope=scope,stage=stage,phase='issued',original=self.blob(original))
        self.local['steps'].append(row);first=len(self.local['steps'])-1;self.role_save();self.bound();action();self.bound()
        for returned in self.local['steps'][first:]:returned['phase']='returned'
        self.role_save()

    def intent(self,scope):
        def issued(stage,original,*details):
            # Helpers call this immediately before each possible ordinary input.
            # Text/passwords are never part of their original input metadata.
            name=stage+'-'+str(len(self.local['steps']))
            need(len(self.local['steps'])<256);self.local['steps'].append(dict(scope=scope,stage=name,phase='issued',original=self.blob(original)))
            self.role_save();return True
        return issued

    def lease(self,key,value):need(key in self.local['leases'] and type(value) is bool);self.local['leases'][key]=value;self.role_save()

    def normal_factory(self,method,*args):
        # Admission of an input transport pins only this role's own existing
        # SDK. Cross-Phone original reads happen outside that input scope; the
        # adapter's foreign-selector guard is never weakened or bypassed.
        with self.adapter.existing_input_session(self.subject):return method(self.subject,*args)

    def controls(self):return self.normal_factory(self.adapter._avatar_people_controls)

    def marker_input(self,request):
        with self.adapter.existing_input_session(self.subject):return self.adapter._navigation_marker_input(self.subject,request)

    def click(self,scope,stage,id,*,match=None):
        if self.done(scope,stage):return
        io=self.controls();value=io.capture();rows=[r for r in value['controls'] if r['id']==id]
        need(len(rows)==1 and rows[0]['enabled'] and rows[0]['inputReady'])
        if match is not None:need(all(same(rows[0].get(k),v) for k,v in match.items()))
        self.step(scope,stage,value,lambda:io.input(id,'activate',token=rows[0]['token']))

    def field(self,scope,stage,text):
        if self.done(scope,stage+'-replace'):return
        self.click(scope,stage+'-focus','avatar.dialog.input');io=self.controls();value=io.capture()
        rows=[r for r in value['controls'] if r['id']=='avatar.dialog.input'];need(len(rows)==1 and rows[0]['focused'])
        self.step(scope,stage+'-replace',value,lambda:io.input('avatar.dialog.input','replace',token=rows[0]['token'],text_value=text))

    def ui(self):return PhoneScriptUI(self.runtime()[0],PACKAGE)

    def close(self,scope):
        tablet=self.ui()
        if tablet.tablet_visible():
            need(self.local['leases']['tablet']);self.step(scope,'tablet-close',self.native(),lambda:tablet.native.click(tablet.resource('nav.close')))
        tablet.native.wait_absent(tablet.resource('nav.close'));self.lease('tablet',False)

    def open(self,scope,area):
        need(area in ('avatar','people'));tablet=self.ui()
        if not tablet.tablet_visible():
            self.lease('tablet',True);self.step(scope,'tablet-open',self.native(),tablet.open_tablet)
        else:need(self.local['leases']['tablet'])
        value=self.controls().capture()
        if any(r['id']==area+'.page' for r in value['controls']):return
        if not any(r['id']==area+'.entry' for r in value['controls']):
            if tablet.native.available(tablet.resource('nav.home')):self.step(scope,'tablet-home',value,lambda:tablet.native.click(tablet.resource('nav.home')))
            for page in range(1,9):
                value=self.controls().capture()
                if any(r['id']==area+'.entry' for r in value['controls']):break
                control=tablet.resource('tabletPage.'+str(page))
                if tablet.native.available(control):self.step(scope,'tablet-page-'+str(page),value,lambda control=control:tablet.native.click(control))
        self.click(scope,area+'-entry',area+'.entry');self.wait_native(lambda p:p['source']['view'][area]['present'])

    def url(self,scope,url):
        if self.done(scope,'avatar-url-submit'):
            self.wait_native(lambda p:p['source']['avatar']['requestedUrl']==url);return
        self.open(scope,'avatar');self.click(scope,'avatar-url-open','avatar.url');self.field(scope,'avatar-url',url)
        self.click(scope,'avatar-url-submit','avatar.dialog.confirm');self.wait_native(lambda p:p['source']['avatar']['requestedUrl']==url)

    def scale(self,scope,value):
        if self.done(scope,'settings-save'):
            self.wait_native(lambda p:abs(p['source']['avatar']['scale']-value)<.005);return
        self.open(scope,'avatar');self.click(scope,'settings-open','avatar.settings');io=self.controls();packet=io.capture()
        rows=[r for r in packet['controls'] if r['id']=='avatar.scale'];need(len(rows)==1)
        self.step(scope,'scale-set',packet,lambda:io.input('avatar.scale','set-value',token=rows[0]['token'],value=value*10))
        self.click(scope,'settings-save','avatar.dialog.confirm')
        self.wait_native(lambda p:abs(p['source']['avatar']['scale']-value)<.005 and abs(p['source']['avatar']['targetScale']-value)<.005)

    def bookmark_row(self,scope,name):
        for attempt in range(101):
            value=self.controls().capture();rows=[r for r in value['controls'] if r['id'].startswith('avatar.bookmark.row.') and r.get('bookmarkName')==name]
            if len(rows)==1:
                self.click(scope,'bookmark-row',rows[0]['id'],match={'bookmarkName':name});return
            need(not rows and attempt<100)
            next=[r for r in value['controls'] if r['id']=='avatar.bookmark.next' and r['enabled'] and r['inputReady']]
            need(len(next)==1);self.click(scope,'bookmark-next-'+str(attempt),next[0]['id'])
        need(False)

    def close_consent(self,scope):
        value=self.native()['source']['view']['people']
        if value['present'] and value['dialog']:
            need(value['consent']['phase'] in ('success','declined','cancelled','error'))
            self.click(scope,'consent-close','people.ConnectionCancel');self.wait_native(lambda p:not p['source']['view']['people']['dialog'])

    def view_surface(self,scope):
        ui=self.runtime()[0];subject=self.adapter._graphics_subject_observer(self.subject,read_only=True)
        graphics=self.normal_factory(self.adapter._graphics_controls,self.intent(scope))
        return PhoneGraphicsSurface(ui,subject,graphics,self.run,self.intent(scope),lambda key:self.local['leases'][key],self.lease,lambda _:False)

    def marker_prepare(self,scope,ticket):
        if self.local['marker'] is not None:
            if self.local['marker']['original'] is None:
                marker=self.adapter._navigation_marker(self.subject,read_only=True).read(self.run)
                held_marker(marker,self.local['marker']['request'])
                self.local['marker']['original']=self.blob(marker);self.role_save()
            return
        request=input_command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-navigation-marker-input',operation='prepare',runId=self.run,
            fixtureUrl=self.fixture_url,ticket=ticket,imageExtent=self.policy['imageExtent'],markerRoi=self.policy['markerRoi'],holdView=True))
        self.local['marker']=dict(request=request,original=None,release=None);self.role_save()
        receipt=self.marker_input(request);input_receipt(receipt,request)
        marker=self.adapter._navigation_marker(self.subject,read_only=True).read(self.run)
        need(same(marker['source']['originalInput'],request) and marker['source']['fixtureInstance']==receipt['fixtureInstance']
            and marker['source']['phase']=='active' and marker['source']['cameraLease']['phase']=='held')
        self.local['marker']['original']=self.blob(marker);self.role_save()

    def marker_release(self):
        owned=self.local['marker']
        if owned is None:return
        reader=self.adapter._navigation_marker(self.subject,read_only=True)
        if owned['original'] is not None:reader.restore([self.blob(reference=owned['original'])])
        actual=reader.read(self.run);need(same(actual['source']['originalInput'],owned['request']))
        if actual['source']['phase']!='drained':
            request=owned['release'] or input_command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-navigation-marker-input',operation='release',
                runId=self.run,fixtureInstance=actual['source']['fixtureInstance']))
            owned['release']=request;self.role_save();input_receipt(self.marker_input(request),request)
        for attempt in range(101):
            actual=reader.read(self.run)
            try:marker_retired(actual);break
            except NativeUIError:need(attempt<100);self.sleep(.1)
        web_reader=self.adapter._web_runtime_observer(self.subject,read_only=True)
        for attempt in range(101):
            web=web_reader.read(self.run,self.fixture_url)
            try:web_released(web);break
            except NativeUIError:need(attempt<100);self.sleep(.1)
        self.local['markerRetired']=self.blob(dict(marker=actual,web=web));self.local['marker']=None;self.role_save()

    def phase(self):
        value=self.source.read(self.state['phaseStatus'] if self.state else None);self.bound()
        if self.role=='primary' and self.state is not None:
            self.state.update(phaseStatus=value['status'],backend=deepcopy(value['backend']));self.owner_save()
        return value

    def original(self):return self.blob(reference=self.local['original'])

    def prepare(self):
        with self.scope():
            self.load()
            if self.role=='actor' and self.state is None:raise PhasePending('The primary Avatar owner has not reserved its run')
            if self.role=='actor' and self.state['phase'] in ('cleaning','cleaned') and self.local is None:
                raise PhasePending('An unstarted second Phone cannot acquire new input authority during cleanup')
            if self.local is not None and self.local['phase']!='preparing':return
            phase=self.source.read(self.state['phaseStatus'] if self.state else None)
            need(phase['verb']=='baseline' or self.state is not None and self.state['phase']=='cleaning')
            if self.local is None:
                ui,_native,binding,guard,_installed=self.runtime();original=self.native();source=original['source']
                viewer=self.adapter._avatar_render_observer(self.subject,read_only=True).read();auth=source['auth']['observation']
                need(source['connected'] and source['domainId']==self.source.domain and source['canRezAvatarEntities']
                    and not source['avatar']['replicated'] and source['avatar']['loaded'] and source['avatar']['geometry'] is not None
                    and source['avatar']['geometry']['texturesLoaded'] and abs(source['avatar']['scale']-1)<.005
                    and abs(source['avatar']['targetScale']-1)<.005 and source['preferredAvatarName']==''
                    and source['preferredAvatarUrl']==source['avatar']['requestedUrl'] and not source['attachments']
                    and not source['view']['tabletShown'] and not source['view']['avatar']['present'] and not source['view']['people']['present']
                    and not source['view']['avatar']['dialogs'] and source['bookmarks']['present']
                    and all(pref['present'] for pref in source['view']['preferences'].values())
                    and viewer['source']['cameraMode'] in MODES and not source['auth']['loggedIn']
                    and not any(auth[key] for key in ('tokenPresent','tokenValid','refreshPresent','loginPending','refreshPending'))
                    and source['accountOrigin'].rstrip('/')==self.source.origin
                    and not any(phase['backend']['relationships'].values()) and not phase['backend']['pending']
                    and not phase['backend']['inflightResponses'] and not phase['backend']['failedResponses'])
                for name in (fixture_context(self.run)['name'],fixture_context(self.run)['hidden']):need(name not in source['bookmarks']['bookmarks'])
                original_ref=self.blob(dict(native=original,viewer=viewer))
                self.local=dict(phase='preparing',samplingPhase=None,binding=deepcopy(binding),policy=deepcopy(self.policy),original=original_ref,baseline=None,
                    leases=dict(tablet=False,address=False,menu=False),steps=[],marker=None,markerRetired=None,last={},frames=[],images=[],sequence=0,quiet=None,retired=None)
                self.role_save()
                if self.role=='primary':
                    need(self.state is None)
                    self.state=dict(phase='preparing',binding=deepcopy(binding),policy=deepcopy(self.policy),original=original_ref,ticket=phase['ticket'],call=None,
                        phaseStatus=phase['status'],backend=phase['backend'],bookmark=None,primaryReady=False,cleanup=[],final=None);self.owner_save()
            auth_role='primary' if self.role=='primary' else 'peer';backend=self.source.status_backend()
            auth_run=backend['accounts'][auth_role]['runId'];login=self.normal_factory(self.adapter._login_controls,self.intent('prepare-login'),auth_run,self.source.origin)
            current=self.native();account=current['source']['auth']
            if not account['loggedIn']:
                def normal_login():
                    login.open();credentials=self.source.credentials(auth_role)
                    try:login.fill(credentials);login.submit()
                    finally:credentials=None
                self.step('prepare','login',current,normal_login)
            current=self.wait_native(lambda p:p['source']['auth']['loggedIn'] and p['source']['auth']['principalSha256']==digest(backend['principals'][auth_role])
                and p['source']['auth']['observation']['tokenValid'] and not p['source']['auth']['observation']['loginPending']
                and any(event['kind']=='profile-reply' and event['httpStatus']==200 and event['networkError']==0
                    and event['sequence']>self.original()['native']['source']['auth']['observation']['eventSequence']
                    for event in p['source']['auth']['observation']['events']))
            self.step('prepare','login-close',self.native(),login.cancel)
            self.step('prepare','camera',current,lambda:self.view_surface('prepare-camera').select_camera('selfie'))
            self.marker_prepare('prepare',phase['ticket'])
            if self.role=='actor':self.open('prepare-people','people')
            current=self.native();original=self.original()['native']['source']
            need(current['source']['avatar']['requestedUrl']==original['avatar']['requestedUrl']
                and current['source']['avatar']['geometry']['url']==original['avatar']['geometry']['url']
                and same(current['source']['bookmarks'],original['bookmarks']) and same(current['source']['view']['preferences'],original['view']['preferences']))
            self.local['baseline']=self.blob(current);self.local['phase']='ready';self.role_save()
            if self.role=='primary':self.state.update(phase='baseline',primaryReady=True);self.owner_save()

    def peer_state(self):
        store=PrivateFeatureState(self.store.path.with_name('phone-avatar-people-actor-feature.json'))
        state=self.read(store,'actor')
        if state is None or state['phase']=='preparing':raise PhasePending('The independently credentialed second Phone is not prepared')
        need(state['binding']['sessionId']!=self.state['binding']['sessionId'] and state['binding']['targetFingerprint']!=self.state['binding']['targetFingerprint'])
        return state

    def peer_session(self):
        state=self.peer_state();value=self.blob(reference=state['baseline'])
        return value['source']['avatar']['sessionId']

    def act(self,call):
        call=deepcopy(arguments('feature.'+AREA+'.act',call));need(self.role=='primary' and call['runId']==self.run and call['fixtureUrl']==self.fixture_url)
        self.prepare()
        with self.scope():
            self.load()
            if self.local['phase']=='reading':self.recover()
            phase=self.phase();need(phase['ticket']==call['ticket'] and phase['verb']==call['verb'] and same(phase['inputs'],call['inputs'])
                and self.state['phase'] in ('baseline','active','acting'))
            if self.state['phase']=='active' and same(self.state['call'],call):return {'performed':True}
            if self.state['phase']=='acting':need(same(self.state['call'],call))
            self.state.update(phase='acting',ticket=call['ticket'],call=call);self.owner_save()
            verb=call['verb'];scope=call['ticket'];inputs=call['inputs'];name=fixture_context(self.run)['name']
            if verb=='avatar-url':self.url(scope,self.fixture_url+'tickets/'+scope+'/'+inputs['resource'])
            elif verb=='avatar-scale':self.scale(scope,inputs['value'])
            elif verb=='wearable-add':
                self.open(scope,'avatar');self.click(scope,'wearables-open','avatar.wearables');self.click(scope,'wearable-add','avatar.wearable.add')
                self.field(scope,'wearable-url',self.fixture_url+'tickets/'+scope+'/'+inputs['resource']);self.click(scope,'wearable-submit','avatar.dialog.confirm')
                self.wait_native(lambda p:bool(p['source']['avatarEntityOrigins']['events']))
                self.click(scope,'wearables-save','avatar.dialog.confirm')
            elif verb=='avatar-bookmark-save':
                self.open(scope,'avatar');self.click(scope,'bookmark-add','avatar.bookmark.add');self.field(scope,'bookmark-name',name)
                self.click(scope,'bookmark-save','avatar.dialog.confirm');actual=self.wait_native(lambda p:name in p['source']['bookmarks']['bookmarks'])
                record=actual['source']['bookmarks']['bookmarks'][name]
                if self.state['bookmark'] is not None:need(same(record,self.state['bookmark']))
                self.state['bookmark']=deepcopy(record);self.owner_save()
            elif verb in ('avatar-bookmark-choose','avatar-bookmark-delete'):
                self.bookmark(scope,name,delete=verb.endswith('delete'))
            elif verb=='avatar-restore':self.url(scope,self.original()['native']['source']['avatar']['requestedUrl'])
            elif verb=='connection-request':
                self.open(scope,'people');self.click(scope,'nearby-tab','people.nearby');session=self.peer_session()
                value=self.controls().capture();rows=[r for r in value['controls'] if r['id'].startswith('people.row.') and r.get('peerSession')==session]
                need(len(rows)==1);self.click(scope,'select-peer',rows[0]['id'],match={'peerSession':session})
                self.click(scope,'request-connection','people.RequestConnection')
                self.wait_native(lambda p:p['source']['view']['people'].get('consent',{}).get('phase')=='outgoing')
            elif verb=='connection-cancel':
                self.click(scope,'cancel-connection','people.ConnectionCancel');self.wait_native(lambda p:not p['source']['view']['people']['dialog'])
            elif verb=='connection-remove':self.remove_connection(scope)
            elif verb not in ('peer-reject','peer-accept'):need(False)
        if call['verb'] in ('peer-reject','peer-accept'):self.finish_peer_action(call)
        with self.scope():
            self.load();need(same(self.state['call'],call));self.state['phase']='active';self.owner_save()
        return {'performed':True}

    def bookmark(self,scope,name,*,delete):
        self.open(scope,'avatar');current=self.native()
        if delete and name not in current['source']['bookmarks']['bookmarks']:
            need(any(row['scope']==scope and row['stage']=='bookmark-delete-confirm' for row in self.local['steps']))
            if current['source']['view']['avatar']['managing']:self.click(scope,'bookmark-mode-close','avatar.bookmark.manage')
            return
        need(self.state['bookmark'] is not None and same(current['source']['bookmarks']['bookmarks'].get(name),self.state['bookmark']))
        managing=current['source']['view']['avatar']['managing']
        if managing is not delete:self.click(scope,'bookmark-mode','avatar.bookmark.manage')
        self.bookmark_row(scope,name)
        if delete:
            self.click(scope,'bookmark-delete-confirm','avatar.dialog.confirm');self.wait_native(lambda p:name not in p['source']['bookmarks']['bookmarks'])
            self.click(scope,'bookmark-mode-close','avatar.bookmark.manage')
        else:
            url=self.state['bookmark']['avatarUrl'];self.wait_native(lambda p:p['source']['avatar']['requestedUrl']==url
                and abs(p['source']['avatar']['scale']-self.state['bookmark']['avatarScale'])<.005)

    def remove_connection(self,scope):
        self.open(scope,'people');self.click(scope,'connections-tab','people.connections');backend=self.source.status_backend();username=backend['principals']['peer']
        for attempt in range(81):
            value=self.controls().capture();rows=[r for r in value['controls'] if r['id'].startswith('people.row.') and r.get('userName')==username]
            if len(rows)==1:break
            need(not rows and attempt<80);self.sleep(.1)
        self.click(scope,'connected-peer-select',rows[0]['id'],match={'userName':username})
        self.click(scope,'connection-remove','people.remove.'+username,match={'userName':username})
        self.wait_native(lambda p:not any(row.get('userName')==username for row in p['source']['view']['models']['connectionsUserModel']['rows']))

    def finish_peer_action(self,call):
        # Waiting never holds either Phone's source lock: the independent actor
        # must be able to deliver its own real peer input and acquire originals.
        start=self.monotonic()
        for attempt in range(241):
            with self.scope():
                self.load();value=self.native();consent=value['source']['view']['people'].get('consent',{})
                if consent.get('phase') in ('success','declined'):
                    need(consent['phase']==('success' if call['verb']=='peer-accept' else 'declined'))
                    self.close_consent(call['ticket'])
                    if call['verb']=='peer-accept':self.click(call['ticket'],'accepted-connections-tab','people.connections')
                    return
            need(attempt<240 and self.monotonic()-start<24);self.sleep(.1)
        need(False)

    def done(self,scope,stage):
        rows=[row for row in self.local['steps'] if row['scope']==scope and row['stage']==stage];need(len(rows)<=1)
        if rows:need(rows[0]['phase']=='returned');return True
        return False

    def sync_peer(self):
        need(self.role=='actor')
        with self.scope():
            self.load()
            if self.local is not None and self.local['phase']=='reading':self.recover()
            phase=self.source.read(self.state['phaseStatus'])
            if self.state['phase'] in ('cleaning','cleaned'):
                self.clean_local(phase);return
            if not self.state['primaryReady']:raise PhasePending('Primary Avatar setup is incomplete')
            verb=phase['verb'];scope=phase['ticket']
            if verb in ('peer-accept','peer-reject'):
                completed=self.done(scope,'peer-respond')
                if self.state['ticket']!=scope or self.state['phase'] not in ('acting','active'):
                    raise PhasePending('Peer action has no owned primary input transaction')
                need(self.state['phase']=='acting' or completed)
                primary=self.native(self.selector);own=self.native();a=primary['source']['view']['people'];b=own['source']['view']['people']
                stage='peer-respond'
                if not completed:
                    need(a['present'] and b['present'] and a['consent']['phase']=='outgoing' and b['consent']['phase']=='incoming'
                        and a['consent']['requestId']==b['consent']['requestId'] and a['consent']['peer']==own['source']['avatar']['sessionId']
                        and b['consent']['peer']==primary['source']['avatar']['sessionId'])
                    self.click(scope,stage,'people.ConnectionAccept' if verb=='peer-accept' else 'people.ConnectionDecline')
                self.wait_native(lambda p:p['source']['view']['people'].get('consent',{}).get('phase') in
                    (('success','idle') if verb=='peer-accept' else ('declined','idle')))
                self.close_consent(scope)
                if verb=='peer-accept':self.click(scope,'peer-connections-tab','people.connections')
            elif verb=='connection-cancel':
                consent=self.native()['source']['view']['people']
                if consent['dialog'] and consent['consent']['phase'] not in ('success','declined','cancelled','error'):
                    raise PhasePending('The second Phone has not consumed the cancellation yet')
                self.close_consent(scope)
            elif verb=='connection-remove':
                self.close_consent(scope);self.click(scope,'peer-refresh-nearby','people.nearby');self.click(scope,'peer-refresh-connections','people.connections')

    def role_frame(self,phase,*,retired=False):
        """One original multi-source acquisition; every image is separately owned."""
        from overte_phone_avatar_people_measurements import restoration
        need(self.local['phase'] in ('ready','cleaned','retired'))
        self.local['samplingPhase']=self.local['phase'];self.local['phase']='reading';self.role_save()
        primary_before=self.native(self.selector)
        participant_before=primary_before if self.role=='primary' else self.native()
        original=self.blob(reference=self.state['original'])['native'];subject=original['source']['avatar']['sessionId']
        lifecycle_reader=self.adapter._native_feature_observer(self.subject,read_only=True)
        lifecycle=lifecycle_reader.read(0,require_account=True)
        last=self.blob(reference=self.local['frames'][-1]) if self.local['frames'] else None
        if last is not None:need(lifecycle['instance']==last['native']['instance'] and lifecycle['sequence']>last['native']['sequence']
            and all(lifecycle['lifecycle'][key]>=last['native']['lifecycle'][key] for key in lifecycle['lifecycle']))
        frame=dict(role=self.role,ticket=phase['ticket'],phase=phase['status'],backend=None,native=lifecycle,
            primaryBefore=primary_before,primaryAfter=None,participantBefore=participant_before,participantAfter=None,
            capture=None,draws=None,viewerBefore=None,viewerAfter=None,marker=None,web=None,image=None,pixels=None,release=None)
        if phase['verb']!='cleanup':
            owned=self.local['marker'];need(owned is not None and owned['original'] is not None)
            marker_reader=self.adapter._navigation_marker(self.subject,read_only=True);marker_reader.restore([self.blob(reference=owned['original'])])
            marker=marker_reader.read(self.run);held_marker(marker,owned['request'])
            web=self.adapter._web_runtime_observer(self.subject,read_only=True).read(self.run,self.fixture_url)
            active_marker(web,owned['request']['fixtureUrl']+'tickets/'+owned['request']['ticket']+'/graphics-marker.v1.html')
            viewer_before=self.adapter._avatar_render_observer(self.subject,read_only=True).read()
            capture=self.adapter._world_render_capture(self.subject,read_only=True,role=self.role,require_trace=True,require_frame_view=True)
            packet,raw=capture.read(0)
            if last is not None and last['capture'] is not None:
                old=last['capture'];need(packet['instance']==old['instance'] and packet['sequence']>old['sequence']
                    and packet['source']['acquisitionSequence']>old['source']['acquisitionSequence']
                    and packet['source']['renderTrace']['frameId']!=old['source']['renderTrace']['frameId'])
            recorded=packet['source']['renderTrace']['recordedView'];held=marker['source']['cameraLease']['heldView']
            need(recorded['position']==held['position'] and recorded['rotation']==held['rotation'] and recorded['projection']==held['projection'])
            draws=self.adapter._world_model_draws_observer(self.subject,read_only=True).read(packet)
            viewer_after=self.adapter._avatar_render_observer(self.subject,read_only=True).read()
            participant_after=self.native()
            primary_after=participant_after if self.role=='primary' else self.native(self.selector)
            def image_intent(value):
                if self.local['images'] and self.local['images'][-1]['capture']['requestId']==value['capture']['requestId']:self.local['images'][-1]=deepcopy(value)
                else:self.local['images'].append(deepcopy(value))
                self.role_save()
            images=AvatarPeopleImages(self.root,self.local['binding'],self.run,self.role,len(self.local['images'])+1,lifecycle_reader.guard,image_intent,monotonic=self.monotonic)
            image=images.write(phase['ticket'],packet,raw)
            ids=[row['entityId'] for row in primary_before['source']['avatarEntityOrigins']['events']
                if row['entityId'] in primary_before['source']['avatarEntities']['advertisedIds']]
            image_frame=dict(ticket=phase['ticket'],subjectSession=subject,wearableIds=ids,avatarBefore=participant_before,avatarAfter=participant_after,
                viewerBefore=viewer_before,viewerAfter=viewer_after,capture=packet,draws=draws)
            previous=None
            if phase['verb'] in ('avatar-scale','wearable-add','avatar-bookmark-choose'):
                prior=None
                for reference in reversed(self.local['frames']):
                    candidate=self.blob(reference=reference)
                    if candidate['ticket']!=phase['ticket'] and candidate['image'] is not None:prior=candidate;break
                if prior is None:raise PhasePending('No prior original Avatar image is available')
                previous=dict(frame=prior['pixels']['frame'],png=AvatarPeopleImages.archive(self.root,prior['image']))
            proof=pixels(self.run,image_frame,raw,self.policy['imagePolicy'],lifecycle_reader.pid,lifecycle_reader.clock_ms,lifecycle_reader.guard,
                previous=previous,monotonic=self.monotonic)
            need(proof['perspective']==('local' if self.role=='primary' else 'remote'))
            frame.update(capture=packet,draws=draws,viewerBefore=viewer_before,viewerAfter=viewer_after,marker=marker,web=web,image=image,
                pixels=dict(frame=image_frame,proof=proof),release=capture.release(),primaryAfter=primary_after,participantAfter=participant_after)
        else:
            frame['participantAfter']=self.native();frame['primaryAfter']=frame['participantAfter'] if self.role=='primary' else self.native(self.selector)
        backend=self.source.status_backend();frame['backend']=backend
        if retired:
            final=self.source.status(phase['status']);need(not final['active'] and same(final['activations'],phase['status']['activations']))
        else:
            final=self.source.read(phase['status']);need(final['ticket']==phase['ticket'])
        epoch=int(lifecycle_reader.clock_ms());baseline=self.blob(reference=self.state['original'])['native']
        if phase['verb']=='cleanup':
            actual=restoration(self.run,frame['primaryBefore'],frame['primaryAfter'],backend,baseline,self.fixture_url,self.source.instance,
                pid=frame['primaryAfter']['processId'],epoch=epoch,after_epoch=math.ceil(phase['afterEpochMs']))
            if self.role=='actor':
                restoration(self.run,frame['participantBefore'],frame['participantAfter'],backend,self.original()['native'],self.fixture_url,self.source.instance,
                    pid=frame['participantAfter']['processId'],epoch=epoch,after_epoch=math.ceil(phase['afterEpochMs']))
        else:
            actual=measurement(self.run,frame['primaryBefore'],frame['primaryAfter'],backend,phase['status'],baseline,self.fixture_url,self.source.instance,
                pid=frame['primaryAfter']['processId'],epoch=epoch,after_epoch=math.ceil(phase['afterEpochMs']))
            if self.role=='actor':self.remote_facts(frame,actual)
        return frame,actual

    def remote_facts(self,frame,actual):
        from overte_phone_avatar_people_measurements import model_resources,native_model_semantics
        backend=frame['backend'];primary=frame['primaryAfter']['source'];peer=frame['participantAfter']['source'];subject=primary['avatar']['sessionId']
        need(peer['connected'] and peer['domainId']==primary['domainId']==backend['domainId'] and peer['accountOrigin'].rstrip('/')==self.source.origin
            and peer['auth']['loggedIn'] and peer['auth']['principalSha256']==digest(backend['principals']['peer'])
            and peer['avatar']['sessionId']!=subject and not peer['avatar']['replicated'])
        rows=[row for row in peer['peers'] if row['sessionId']==subject];need(len(rows)==1);remote=rows[0]
        local=primary['avatar'];need(not remote['replicated'] and remote['requestedUrl']==local['requestedUrl'] and remote['loaded']==local['loaded']
            and abs(remote['scale']-local['scale'])<=.005 and abs(remote['targetScale']-local['targetScale'])<=.005)
        need(remote['geometry'] is not None and local['geometry'] is not None and remote['geometry']['url']==local['geometry']['url']
            and remote['geometry']['texturesLoaded'] and same(remote['geometry']['textures'],local['geometry']['textures']))
        urls=resources(self.run,frame['phase'],self.fixture_url);model_resources(self.run,remote,urls,peer['resourceReplies'],backend)
        receipts=social_replies(peer,backend,self.source.origin,'peer');view=peer['view']['people']
        if actual['connection']=='pending':
            consent=primary['view']['people']['consent'];need(view['present'] and view['dialog'] and view['consent']['phase']=='incoming'
                and view['consent']['requestId']==consent['requestId'] and view['consent']['peer']==subject and consent['peer']==peer['avatar']['sessionId'])
        elif actual['connection']=='connected':
            need(view['present'] and not view['dialog'] and backend['binding'] is not None
                and backend['binding']['primarySession']==subject and backend['binding']['peerSession']==peer['avatar']['sessionId'])
            for role in ('primary','peer'):
                events=[row for row in backend['responses'] if row['role']==role and row['method']=='POST' and row['status']==200
                    and row['ticket']==frame['ticket']]
                need(events and (role=='primary' or any(row['responseId'] in {r['responseId'] for r in receipts} for row in events)))
            need(sum(row.get('userName')==backend['principals']['primary'] and row.get('connection')=='connection'
                for row in peer['view']['models']['connectionsUserModel']['rows'])==1)
        else:need(not view['dialog'] and not backend['pending'] and not any(backend['relationships'].values()))

    def observe(self,call):
        arguments('feature.'+AREA+'.observe',call)
        self.prepare()
        started=self.monotonic()
        for attempt in range(81):
            try:return self.observe_once(call)
            except PhasePending:
                if self.role=='actor' and (self.local is None or self.local['phase']!='reading'):raise
                if attempt==80 or self.monotonic()-started>=8:raise
            except NativeUIError:
                if attempt==80 or self.monotonic()-started>=8:raise
            # Never hold either participant's source lock while waiting for
            # replication, genuine HTTP completion or the independent actor.
            self.sleep(.1)
        need(False)

    def observe_once(self,call):
        call=arguments('feature.'+AREA+'.observe',call);need(call['runId']==self.run)
        self.prepare()
        if self.role=='actor':self.sync_peer()
        with self.scope():
            self.load();need(self.local is not None and call['afterSequence']<=self.local['sequence'])
            if self.state['phase'] in ('preparing','acting','cleaning'):raise PhasePending('Avatar normal input or restoration is incomplete')
            self.recover();phase=self.phase()
            if phase['verb']=='cleanup':need(self.state['phase']=='cleaned' and self.local['phase'] in ('cleaned','retired'))
            elif phase['verb']!='baseline' and phase['ticket']!=self.state['ticket']:raise PhasePending('Avatar phase awaits its normal input')
            self.peer_state();frame,actual=self.role_frame(phase)
            need(len(self.local['frames'])<128);self.local['frames'].append(self.blob(frame));self.local['sequence']+=1
            resources=[]
            if self.local['marker'] is not None and phase['verb']!='baseline':resources.append('entity:avatar-marker')
            if actual['bookmarked']:resources.append('file:avatar-bookmark')
            if actual['wearable']:resources.append('entity:avatar-wearable')
            if actual['connection']!='none':resources.append('connection:owned-peer')
            if actual['dialog']:resources.append('panel:people-consent')
            if phase['verb'] in QUIET:
                now=frame['primaryAfter']['capturedEpochMs'];window=self.local['quiet']
                if window is None or window['ticket']!=phase['ticket']:window=dict(ticket=phase['ticket'],epoch=now,clock=self.monotonic(),samples=0,complete=False)
                window['samples']+=1;window['complete']=window['samples']>=3 and now-window['epoch']>=3000 and self.monotonic()-window['clock']>=3
                self.local['quiet']=window
                if not window['complete']:resources.append('input:avatar-quiet-window')
                if phase['verb']=='cleanup' and self.role=='primary':
                    peer=self.peer_state()
                    if peer['quiet'] is None or not peer['quiet']['complete']:resources.append('input:avatar-peer-retirement')
            self.local['phase']='cleaned' if phase['verb']=='cleanup' else 'ready';self.local['samplingPhase']=None;self.role_save()
            artifacts=[]
            if frame['image'] is not None:artifacts.append(dict(kind='image',source='world-render-target',name=frame['image']['name'],sequence=self.local['sequence'],
                capturedEpochMs=frame['capture']['capturedEpochMs'],ticket=phase['ticket']))
            return result('feature.'+AREA+'.observe',dict(schemaVersion=1,contractVersion=CONTRACT_VERSION,runId=self.run,sequence=self.local['sequence'],
                capturedEpochMs=frame['primaryAfter']['capturedEpochMs'],state=actual,artifacts=artifacts,resources=resources,lifecycle=frame['native']['lifecycle']))

    def publish(self):
        need(self.role=='actor')
        with self.scope():
            self.load()
            if self.read(self.retirement_store,'retirement') is not None:return None
            if self.state is None and self.local is None:raise PhaseRetired('The Avatar journals are retired')
            if self.state is not None:
                status=self.source.status(self.state['phaseStatus'])
                if not status['active']:
                    self.recover();self.retired_read(status);return None
        value=self.observe(dict(contractVersion=CONTRACT_VERSION,runId=self.run,afterSequence=0))
        with self.scope():
            self.load();frame=self.blob(reference=self.local['frames'][-1]);ticket=frame['ticket']
        self.source.client.request('/runs/'+self.run+'/samples',dict(ticket=ticket,actor='owned-observer',actorSequence=value['sequence'],
            capturedEpochMs=value['capturedEpochMs'],facts=projection(AREA,value['state'])))
        return value

    def retire_partial(self,image):
        AvatarPeopleImages.record(image);need(image['phase']!='saved')
        reader=AvatarPeopleImages(self.root,image['binding'],self.run,self.role,image['stage'],lambda:True,lambda _:False)
        path=reader._path(image);store=PrivateFeatureState(self.root/('avatar-people-partial-'+image['capture']['requestId']+'.json'))
        proof=dict(avatarPeoplePartialVersion=1,original=deepcopy(image));old=store.read();need(old is None or same(old,proof))
        if image['phase']=='planned':need(reader.absent(image))
        elif not reader.absent(image):
            import os
            descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
            try:reader._file(path,descriptor,image)
            finally:os.close(descriptor)
        else:need(old is not None)
        if old is None:store.write(proof,None)
        need(same(store.read(),proof))
        if not reader.absent(image):
            import os
            descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
            try:reader._file(path,descriptor,image);path.unlink()
            finally:os.close(descriptor)
            descriptor=os.open(path.parent,os.O_RDONLY|getattr(os,'O_DIRECTORY',0)|getattr(os,'O_NOFOLLOW',0))
            try:os.fsync(descriptor)
            finally:os.close(descriptor)
        need(reader.absent(image))

    def recover(self):
        for image in list(self.local['images']):
            if image['phase']=='saved':AvatarPeopleImages.archive(self.root,image)
            else:self.retire_partial(image);self.local['images'].remove(image);self.role_save()
        owned=self.adapter.world_render_store(self.subject,role=self.role)
        if owned.read() is not None:self.adapter._world_render_capture(self.subject,read_only=True,role=self.role).release()
        if self.local['phase']=='reading':
            # Discarding a partial acquisition creates no product input or old
            # observation. Saved originals remain in the audit until retirement.
            need(self.local['samplingPhase'] in ('ready','cleaned','retired'))
            self.local['phase']=self.local['samplingPhase'];self.local['samplingPhase']=None;self.role_save()

    def dismiss_owned_dialogs(self,scope):
        original=self.original()['native']['source'];urls=resources(self.run,self.state['phaseStatus'],self.fixture_url)
        allowed={'',fixture_context(self.run)['name'],original['avatar']['requestedUrl'],*urls['A'],*urls['missing'],*urls['wearable']}
        for attempt in range(5):
            native=self.native();view=native['source']['view'];controls=self.controls().capture()
            if not view['avatar']['dialogs']:break
            fields=[row for row in controls['controls'] if row['id']=='avatar.dialog.input']
            need(len(fields)<=1 and (not fields or fields[0].get('text') in allowed))
            self.click(scope,'dialog-cancel-'+str(attempt),'avatar.dialog.cancel')
        need(not self.native()['source']['view']['avatar']['dialogs'])
        people=self.native()['source']['view']['people']
        if people['present'] and people['dialog']:
            if people['consent']['phase'] not in ('success','declined','cancelled','error'):
                self.click(scope,'pending-consent-cancel','people.ConnectionCancel')
                self.wait_native(lambda p:p['source']['view']['people'].get('consent',{}).get('phase') in ('idle','cancelled','declined','error'))
            self.close_consent(scope)

    def retire_worn(self,scope):
        actual=self.native()['source'];owned=actual['avatarEntityOrigins']['events']
        present=[row for row in actual['avatarEntities']['entities'] if row['parentId']==actual['avatar']['sessionId']]
        if not present:return
        need(len(present)==1 and len(owned)==1 and present[0]['entityId']==owned[0]['entityId'] and present[0]['originalObject'])
        self.open(scope,'avatar');self.click(scope,'wearables-open','avatar.wearables')
        self.click(scope,'wearable-remove','avatar.wearable.remove',match={'wearableId':owned[0]['entityId'],'wearableUrlSha256':owned[0]['modelUrlSha256']})
        self.wait_native(lambda p:owned[0]['entityId'] in p['source']['avatarEntities']['absentIds']
            and owned[0]['entityId'] not in p['source']['avatarEntities']['advertisedIds'] and owned[0]['entityId'] not in p['source']['avatarEntities']['retainedIds'])
        self.click(scope,'wearables-save','avatar.dialog.confirm')

    def clean_local(self,phase):
        need(self.state['phase'] in ('cleaning','cleaned') and phase['verb']=='cleanup')
        if self.local is None:return
        self.recover();self.local['phase']='cleaning';self.role_save()
        original=self.original();baseline=original['native']['source'];scope=phase['ticket']+'-cleanup-'+self.role
        self.dismiss_owned_dialogs(scope)
        current=self.native()['source'];auth_role='primary' if self.role=='primary' else 'peer';backend=self.source.status_backend()
        if current['auth']['loggedIn']:need(current['auth']['principalSha256']==digest(backend['principals'][auth_role]))
        if self.role=='primary':
            if backend['relationships']['primary']:self.remove_connection(scope+'-remove')
            urls=resources(self.run,self.state['phaseStatus'],self.fixture_url)
            need(current['avatar']['requestedUrl'] in {baseline['avatar']['requestedUrl'],*urls['A'],*urls['missing']})
            owned={row['entityId'] for row in current['avatarEntityOrigins']['events']}
            local_ids={row['entityId'] for row in current['avatarEntities']['entities'] if row['parentId']==current['avatar']['sessionId']}
            need(local_ids<=owned and all(row['originalObject'] for row in current['avatarEntities']['entities'] if row['entityId'] in owned))
            if local_ids:self.retire_worn(scope+'-wearable-retire')
            if current['avatar']['requestedUrl']!=baseline['avatar']['requestedUrl'] or local_ids:self.url(scope+'-avatar-restore',baseline['avatar']['requestedUrl'])
            current=self.native()['source']
            if abs(current['avatar']['scale']-baseline['avatar']['scale'])>=.005:self.scale(scope+'-scale-restore',baseline['avatar']['scale'])
            name=fixture_context(self.run)['name']
            if name in current['bookmarks']['bookmarks']:
                if self.state['bookmark'] is None:
                    issued=any(row['stage']=='bookmark-save' and row['phase'] in ('issued','returned') for row in self.local['steps'])
                    need(issued and name not in baseline['bookmarks']['bookmarks'])
                    record=current['bookmarks']['bookmarks'][name]
                    need(record.get('version')==3 and record.get('avatarUrl') in urls['A'] and record.get('avatarScale')==1)
                    self.state['bookmark']=deepcopy(record);self.owner_save()
                self.bookmark(scope+'-bookmark-retire',name,delete=True)
        else:
            need(current['avatar']['requestedUrl']==baseline['avatar']['requestedUrl'] and not current['attachments']
                and same(current['bookmarks'],baseline['bookmarks']))
        self.close(scope+'-close')
        self.marker_release()
        current_viewer=self.adapter._avatar_render_observer(self.subject,read_only=True).read()
        if current_viewer['source']['cameraMode']!=original['viewer']['source']['cameraMode']:
            self.step(scope,'view-restore',current_viewer,lambda:self.view_surface(scope+'-view').select_camera(original['viewer']['source']['cameraMode']))
        self.close(scope+'-view-close')
        current=self.native()['source']
        if current['auth']['loggedIn']:
            auth_run=backend['accounts'][auth_role]['runId']
            self.lease('tablet',True) # The source-guarded normal logout menu opens this owned panel.
            self.step(scope,'logout',current,lambda:self.normal_factory(self.adapter._account_menu,self.intent(scope+'-logout'),auth_run,self.source.origin).logout())
        self.wait_native(lambda p:not p['source']['auth']['loggedIn'] and not p['source']['auth']['observation']['tokenPresent']
            and not p['source']['auth']['observation']['refreshPresent'] and not p['source']['auth']['observation']['loginPending']
            and not p['source']['auth']['observation']['refreshPending'])
        self.close(scope+'-logout-close');self.runtime()[0].release_actions()
        viewer=self.adapter._avatar_render_observer(self.subject,read_only=True).read();wanted=original['viewer']['source'];actual=viewer['source']
        need(actual['cameraMode']==wanted['cameraMode'] and near(actual['pose']['feetPosition'],wanted['pose']['feetPosition'],.005)
            and rotation_equal(actual['pose']['orientation'],wanted['pose']['orientation'],.001)
            and near(actual['view']['position'],wanted['view']['position'],.02)
            and rotation_equal(actual['view']['rotation'],wanted['view']['rotation'],.001)
            and near(actual['view']['projection'],wanted['view']['projection'],.0001))
        current=self.native()['source'];need(same(current['bookmarks'],baseline['bookmarks']) and same(current['view']['preferences'],baseline['view']['preferences']))
        self.local['phase']='cleaned';self.role_save()

    def cleanup(self,call):
        arguments('feature.'+AREA+'.cleanup',call);need(self.role=='primary' and call['runId']==self.run)
        with self.scope():
            self.load()
            if self.state is None:return {'performed':True}
            phase=self.phase();need(phase['verb']=='cleanup')
            if self.state['phase']=='cleaned':return {'performed':True}
            self.state.update(phase='cleaning',ticket=phase['ticket']);self.owner_save();self.clean_local(phase)
        # The primary never uses the actor's credentials or device input. Its
        # separately running peer participant performs and proves its own undo.
        start=self.monotonic()
        for attempt in range(301):
            with self.scope():
                self.load();store=PrivateFeatureState(self.store.path.with_name('phone-avatar-people-actor-feature.json'));peer=self.read(store,'actor')
                backend=self.source.status_backend()
                if (peer is None or peer['phase'] in ('cleaned','retired')) and not backend['pending'] and not any(backend['relationships'].values()) and not backend['inflightResponses']:
                    self.state['phase']='cleaned';self.state['cleanup'].append(self.blob(dict(native=self.native(),backend=backend)));self.owner_save();return {'performed':True}
            need(attempt<300 and self.monotonic()-start<30);self.sleep(.1)
        need(False)

    def retired_read(self,status):
        need(self.local is not None and self.local['phase'] in ('cleaned','retired') and self.state['phase']=='cleaned')
        need(not status['active'] and status['activations'] and status['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        phase=dict(ticket=status['activations'][-1]['ticket'],verb='cleanup',inputs={},status=status,afterEpochMs=status['retiredEpochMs'])
        frame,actual=self.role_frame(phase,retired=True)
        now=frame['primaryAfter']['capturedEpochMs'];retired=self.local['retired']
        if retired is None:retired=dict(firstEpochMs=now,firstMonotonic=self.monotonic(),samples=0,complete=False,last=None,status=status)
        need(same(retired['status']['activations'],status['activations']) and retired['status']['retiredEpochMs']==status['retiredEpochMs'])
        retired['samples']+=1;retired['complete']=retired['samples']>=3 and now-retired['firstEpochMs']>=3000 and self.monotonic()-retired['firstMonotonic']>=3
        retired['last']=self.blob(frame);retired['status']=deepcopy(status)
        self.local.update(phase='retired',samplingPhase=None,retired=retired);self.role_save();return retired['complete']

    def finalize(self):
        need(self.role=='primary')
        for attempt in range(151):
            if self.finalize_once() is not False:return
            need(attempt<150);self.sleep(.1)
        need(False)

    def finalize_once(self):
        need(self.role=='primary')
        with self.scope():
            self.load();retirement=self.read(self.retirement_store,'retirement')
            actor_store=PrivateFeatureState(self.store.path.with_name('phone-avatar-people-actor-feature.json'))
            actor=self.read(actor_store,'actor')
            if retirement is not None:
                exact(retirement,{'owner','primary','actor','status','backend','phase'})
                need(retirement['phase']=='retiring')
                # The durable intent freezes both participants. After it is
                # committed, no source is retimed and no deleted live journal
                # is recreated. Each remaining file must match its exact CAS.
                for actual,key in ((self.state,'owner'),(self.local,'primary'),(actor,'actor')):
                    need(actual is None or retirement[key] is not None and same(actual,self.blob(reference=retirement[key])))
                return self.retire_journals(retirement,actor_store)
            if self.state is None:
                need(self.local is None and actor is None);return True
            need(self.state['phase']=='cleaned' and self.local is not None and self.local['marker'] is None and not any(self.local['leases'].values()))
            status=self.source.status(self.state['phaseStatus']);need(not status['active'])
            backend=self.source.status_backend();need(not backend['active'] and not backend['pending'] and not any(backend['relationships'].values()) and not backend['inflightResponses'])
            for account in backend['accounts'].values():need(not account['accountExists'] and not account['grantsEnabled']
                and not any(account[key] for key in ('heldRequests','armedHold','inflightRequests','accessTokens','refreshTokens')))
            if not self.retired_read(status):return False
            if actor is not None:
                if actor['retired'] is None or not actor['retired']['complete']:return False
                frame=self.blob(reference=actor['retired']['last']);need(self.source.epoch_ms()-frame['participantAfter']['capturedEpochMs']<=1500)
            retirement=dict(owner=self.blob(self.state),primary=self.blob(self.local),actor=None if actor is None else self.blob(actor),
                status=self.blob(status),backend=self.blob(backend),phase='retiring')
            self.save(self.retirement_store,'retirement',retirement)
            return self.retire_journals(retirement,actor_store)

    def retire_journals(self,retirement,actor_store):
        self.bound()
        for role in ('primary','actor'):
            if retirement[role] is None:continue
            local=self.blob(reference=retirement[role])
            need(local['marker'] is None and not any(local['leases'].values()))
            if local['baseline'] is not None:
                need(local['markerRetired'] is not None);proof=self.blob(reference=local['markerRetired'])
                marker_retired(proof['marker']);web_released(proof['web'])
                need(proof['marker']['source']['runId']==self.run and proof['marker']['instance']==self.blob(reference=local['original'])['native']['instance'])
            for image in local['images']:
                need(image['phase']=='saved');AvatarPeopleImages.archive(self.root,image)
        # Immutable input/frame blobs and PNGs remain private audit artifacts.
        # Live authority journals are removed only after the immutable intent.
        archive=PrivateFeatureState(self.root/('avatar-people-retired-'+self.run+'.json'));old=archive.read()
        record=dict(avatarPeopleRetiredVersion=1,payload=pack([retirement]))
        if old is None:archive.write(record,None)
        else:need(same(old,record))
        for store in (actor_store,self.role_store,self.store,self.retirement_store):
            current=store.read();need(same(current,self.previous.get(store.path)))
            if current is not None:
                import os
                store.discard(current)
                descriptor=os.open(store.path.parent,os.O_RDONLY|getattr(os,'O_DIRECTORY',0)|getattr(os,'O_NOFOLLOW',0))
                try:os.fsync(descriptor)
                finally:os.close(descriptor)
            need(store.read() is None)
        return True
