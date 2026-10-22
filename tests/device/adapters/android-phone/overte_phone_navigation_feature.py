"""Public Phone navigation owner over ordinary input and independent originals.

Input acknowledgments never supply state. Every role acquires its own current
native/UI/HTTP/probe/PNG facts under the existing candidate/session guards.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit
import hashlib
import math
import os
import time
import uuid

from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import Locator,NativeUIError
from adapters.native_phone_web_runtime import active_marker,released as web_released
from adapters.restart_inputs import validate_native_restart
from feature_journeys.contract import arguments,result,identifier
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from feature_journeys.fixtures import context as fixture_context
from feature_journeys.witness import projection
from feature_journeys.phase_fixture import PhasePending,PhaseRetired
from feature_journeys.evidence import image_observation
from navigation_observation import project_probe,arrived,viewpoint_urls,FreshNavigation
from overte_phone_navigation_fixture import NavigationFixtureReader
from overte_phone_navigation_measurements import measurement
from overte_phone_navigation_marker import input_command,input_receipt,ready as marker_ready,retired as marker_retired
from overte_phone_graphics_images import PhoneGraphicsImages
from overte_phone_script_ui import PhoneScriptUI
from overte_phone_script_history import pack,unpack,same,canonical
from overte_phone_script_lock import PhoneScriptSourceLock

VERSION=1
AREA='world-navigation'


class NavigationImages(PhoneGraphicsImages):
    KIND='navigation'

    @classmethod
    def retire_partial(cls,root,value):
        """Retire only the exact inode persisted before an interrupted write."""
        cls.record(value);need(value['phase']!='saved')
        reader=cls(root,value['binding'],value['runId'],value['role'],value['stage'],lambda:True,lambda _:False)
        path=reader._path(value)
        archive=PrivateFeatureState(Path(root)/('navigation-partial-'+value['capture']['requestId']+'.json'))
        record=dict(navigationPartialVersion=1,original=deepcopy(value))
        old=archive.read();need(old is None or same(old,record))
        if value['phase']=='planned':
            need(reader.absent(value)) # An unrecorded inode can never be adopted.
        elif not reader.absent(value):
            descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
            try:reader._file(path,descriptor,value)
            finally:os.close(descriptor)
        else:need(old is not None) # Absence after the persisted retirement intent.
        if old is None:archive.write(record,None)
        need(same(archive.read(),record))
        if not reader.absent(value):
            descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
            try:reader._file(path,descriptor,value);path.unlink()
            finally:os.close(descriptor)
        descriptor=os.open(path.parent,os.O_RDONLY|getattr(os,'O_DIRECTORY',0)|getattr(os,'O_NOFOLLOW',0))
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
        need(reader.absent(value))


class PhoneNavigationFeature:
    def __init__(self,adapter,selector,source,root,policy,*,role='primary',monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(source,NavigationFixtureReader) and role in ('primary','actor') and callable(monotonic) and callable(sleep))
        self.adapter,self.selector,self.source,self.role=adapter,selector,source,role
        self.run,self.fixture_url=source.run,source.fixture_url
        self.root,self.policy=Path(root),deepcopy(policy)
        self.monotonic,self.sleep=monotonic,sleep
        path=adapter.state_path(selector)
        self.store=PrivateFeatureState(path.with_name('phone-navigation-feature.json'))
        self.role_store=PrivateFeatureState(path.with_name('phone-navigation-'+role+'-feature.json'))
        self.retirement_store=PrivateFeatureState(path.with_name('phone-navigation-retirement.json'))
        self.lock=PhoneScriptSourceLock(path.with_name('phone-script-sources.lock'))
        self.previous={};self.frame_cache={};self.state=None;self.started=None;self.clock=None

    def bound(self):
        self.lock.assert_held();now=self.monotonic();need(number(now,0,1e15) and (self.clock is None or now>=self.clock)
            and (self.started is None or now-self.started<45));self.clock=now

    def read(self,store,kind):
        value=store.read();self.previous[store.path]=deepcopy(value)
        if value is None:return None
        exact(value,{'navigationFeatureVersion','kind','runId','fixtureUrl','artifactRoot','imagePolicy','payload'})
        need(type(value['navigationFeatureVersion']) is int and value['navigationFeatureVersion']==VERSION and value['kind']==kind
            and value['runId']==self.run and value['fixtureUrl']==self.fixture_url and value['artifactRoot']==str(self.root)
            and same(value['imagePolicy'],self.policy))
        rows=unpack(value['payload']);need(len(rows)==1);return self.frames(rows[0],loading=True)

    def save(self,store,kind,value):
        self.bound();need(store.path in self.previous and same(store.read(),self.previous[store.path]))
        metadata=dict(navigationFeatureVersion=VERSION,kind=kind,runId=self.run,fixtureUrl=self.fixture_url,
            artifactRoot=str(self.root),imagePolicy=self.policy,payload=pack([self.frames(value,loading=False)]))
        store.write(metadata,self.previous[store.path]);need(same(store.read(),metadata));self.previous[store.path]=deepcopy(metadata)

    def frames(self,value,*,loading):
        """Immutable original files keep the existing 64 KiB journal bound."""
        if type(value) is dict:
            if 'navigationOwnerRefVersion' in value:
                need(loading);exact(value,{'navigationOwnerRefVersion','kind','name','sha256'})
                need(type(value['navigationOwnerRefVersion']) is int and value['navigationOwnerRefVersion']==1 and value['kind'] in ('owner','primary','actor'))
                digest=value['sha256'];need(type(digest) is str and len(digest)==64)
                name='navigation-owner-'+self.run+'-'+value['kind']+'-'+digest[:32]+'.json';need(value['name']==name)
                original=PrivateFeatureState(self.root/name).read();need(original is not None and hashlib.sha256(canonical(original)).hexdigest()==digest)
                need(original.get('navigationFeatureVersion')==1 and original.get('runId')==self.run and original.get('kind')==value['kind'])
                return original
            if 'navigationFeatureVersion' in value and value.get('kind') in ('owner','primary','actor'):
                need(not loading and value['runId']==self.run)
                digest=hashlib.sha256(canonical(value)).hexdigest();name='navigation-owner-'+self.run+'-'+value['kind']+'-'+digest[:32]+'.json'
                store=PrivateFeatureState(self.root/name);old=store.read()
                if old is None:store.write(value,None)
                else:need(same(old,value))
                need(same(store.read(),value))
                return dict(navigationOwnerRefVersion=1,kind=value['kind'],name=name,sha256=digest)
            if 'navigationFrameRefVersion' in value:
                need(loading);exact(value,{'navigationFrameRefVersion','role','name','sha256','originalId'})
                need(type(value['navigationFrameRefVersion']) is int and value['navigationFrameRefVersion']==1
                    and value['role'] in ('primary','actor'))
                identifier(value['originalId']);name='navigation-frame-'+self.run+'-'+value['role']+'-'+value['originalId']+'.json'
                need(value['name']==name);original=PrivateFeatureState(self.root/name).read()
                need(original is not None and hashlib.sha256(canonical(original)).hexdigest()==value['sha256'])
                exact(original,{'navigationFrameVersion','runId','role','originalId','payload'})
                need(type(original['navigationFrameVersion']) is int and original['navigationFrameVersion']==1
                    and original['runId']==self.run and original['role']==value['role'] and original['originalId']==value['originalId'])
                rows=unpack(original['payload']);need(len(rows)==1);frame=rows[0]
                need(frame['role']==value['role'] and frame['before']['commandId']==value['originalId'])
                self.frame_cache[(frame['role'],frame['before']['commandId'])]=(hashlib.sha256(canonical(frame)).hexdigest(),deepcopy(value))
                return frame
            if {'role','ticket','phase','providerInstance','navigation','before','probe','native','after','missing','image','capture','release','marker','web'}==set(value):
                need(not loading and value['role'] in ('primary','actor'));key=identifier(value['before']['commandId'])
                name='navigation-frame-'+self.run+'-'+value['role']+'-'+key+'.json'
                cache=self.frame_cache.get((value['role'],key));digest=hashlib.sha256(canonical(value)).hexdigest()
                if cache is not None:need(digest==cache[0]);return deepcopy(cache[1])
                record=dict(navigationFrameVersion=1,runId=self.run,role=value['role'],originalId=key,payload=pack([value]))
                store=PrivateFeatureState(self.root/name);old=store.read()
                if old is None:store.write(record,None)
                else:need(same(old,record))
                need(same(store.read(),record))
                reference=dict(navigationFrameRefVersion=1,role=value['role'],name=name,originalId=key,sha256=hashlib.sha256(canonical(record)).hexdigest())
                self.frame_cache[(value['role'],key)]=(digest,deepcopy(reference));return reference
            return {key:self.frames(item,loading=loading) for key,item in value.items()}
        if type(value) is list:return [self.frames(item,loading=loading) for item in value]
        return value

    def load(self):
        state=self.read(self.store,'owner')
        if state is not None:
            exact(state,{'phase','binding','originalUrl','baseline','phaseStatus','navigationStatus','ticket','call','steps','leases','marker','markerHistory','restarts','cleanup'})
            need(state['phase'] in ('preparing','baseline','acting','active','cleaning','cleaned','restoring')
                and type(state['steps']) is list and len(state['steps'])<=256 and type(state['markerHistory']) is list and len(state['markerHistory'])<=4
                and type(state['restarts']) is list and len(state['restarts'])<=1 and type(state['cleanup']) is list and len(state['cleanup'])<=64)
            context(state['binding']);exact(state['leases'],{'tablet','address'})
            need(all(type(v) is bool for v in state['leases'].values()))
            if state['call'] is not None:arguments('feature.'+AREA+'.act',state['call'])
            for row in state['steps']:
                exact(row,{'scope','stage','phase','original','receipt'})
                need(type(row['scope']) is str and type(row['stage']) is str and row['phase'] in ('issued','acknowledged'))
        self.state=state;return state

    def owner_save(self):self.save(self.store,'owner',self.state)

    def runtime(self,*,read_only=False):
        runtime=self.adapter.normal_feature_runtime(self.selector,read_only=read_only)
        context(runtime[2]);need(self.state is None or same(runtime[2],self.state['binding']))
        need(runtime[3]() is not False);return runtime

    def phase(self):
        value=self.source.read(self.state['phaseStatus'] if self.state else None);self.bound()
        if self.state is not None:
            old=self.state['navigationStatus']
            self.source.navigation(old)
            self.state.update(phaseStatus=value['status'],navigationStatus=deepcopy(self.source.backend));self.owner_save()
        return value

    def step(self,scope,stage,original,action):
        rows=[row for row in self.state['steps'] if row['scope']==scope and row['stage']==stage];need(len(rows)<=1)
        if rows:
            row=rows[0]
            need(row['phase']=='acknowledged') # Unknown input is never redelivered.
            return deepcopy(row['receipt'])
        need(len(self.state['steps'])<256)
        row=dict(scope=scope,stage=stage,phase='issued',original=deepcopy(original),receipt=None)
        self.state['steps'].append(row);self.owner_save();self.bound()
        receipt=action();self.bound();row.update(phase='acknowledged',receipt=deepcopy(receipt));self.owner_save()
        return receipt

    def lease(self,key,value):
        need(key in self.state['leases'] and type(value) is bool)
        self.state['leases'][key]=value;self.owner_save()

    def ui(self):
        native,_,binding,guard,_=self.runtime();return native,PhoneScriptUI(native,'io.github.noah_be.overte.phone')

    def click(self,scope,stage,identifier,*,match=None):
        io=self.adapter._navigation_controls(self.selector,read_only=False)
        value=io.capture();rows=[r for r in value['controls'] if r['id']==identifier]
        need(len(rows)==1 and rows[0]['enabled'] and rows[0]['inputReady'])
        if match is not None:need(all(same(rows[0].get(k),v) for k,v in match.items()))
        row=rows[0]
        self.step(scope,stage,value,lambda:io.input(identifier,'activate',token=row['token']))

    def choose(self,scope,stage,prefix,match):
        value=self.adapter._navigation_controls(self.selector).capture()
        rows=[r for r in value['controls'] if r['id'].startswith(prefix) and all(same(r.get(k),v) for k,v in match.items())]
        need(len(rows)==1);self.click(scope,stage,rows[0]['id'],match=match)

    def field(self,scope,stage,identifier,value):
        self.click(scope,stage+'-focus',identifier)
        io=self.adapter._navigation_controls(self.selector);packet=io.capture();rows=[r for r in packet['controls'] if r['id']==identifier]
        need(len(rows)==1 and rows[0]['focused']);token=rows[0]['token']
        self.step(scope,stage+'-replace',packet,lambda:io.input(identifier,'replace',token=token,text_value=value))
        self.wait_ui(lambda source:any(r['id']==identifier and r.get('text')==value for r in source['controls']))

    def wait_ui(self,predicate):
        deadline=self.monotonic()+10
        for attempt in range(101):
            value=self.adapter._navigation_controls(self.selector,read_only=True).capture();self.bound()
            if predicate(value):return value
            need(attempt<100 and self.monotonic()<deadline);self.sleep(.1)
        need(False)

    def close_address(self,scope):
        ui,tablet=self.ui();field=tablet.resource('PhoneAddressField')
        if ui.available(field,require_enabled=False):
            need(self.state['leases']['address'])
            self.step(scope,'address-cancel',self.adapter._navigation_view(self.selector).read(self.run),lambda:ui.click(tablet.resource('PhoneAddressCancelButton')))
        ui.wait_absent(field);self.lease('address',False)

    def close(self,scope):
        self.close_address(scope);ui,tablet=self.ui()
        if tablet.tablet_visible():
            need(self.state['leases']['tablet'])
            self.step(scope,'tablet-close',self.adapter._navigation_view(self.selector).read(self.run),lambda:ui.click(tablet.resource('nav.close')))
        ui.wait_absent(tablet.resource('nav.close'));self.lease('tablet',False)

    def open(self,scope):
        self.close_address(scope);ui,tablet=self.ui()
        if not tablet.tablet_visible():
            self.lease('tablet',True)
            self.step(scope,'tablet-open',self.adapter._navigation_view(self.selector).read(self.run),lambda:tablet.open_tablet())
        else:need(self.state['leases']['tablet'])
        current=self.adapter._navigation_controls(self.selector).capture()
        if not any(row['id']=='navigation.page' for row in current['controls']):
            if ui.available(tablet.resource('nav.home')):
                self.step(scope,'tablet-home',current,lambda:ui.click(tablet.resource('nav.home')))
            for page in range(1,9):
                current=self.adapter._navigation_controls(self.selector).capture()
                if any(row['id']=='navigation.entry' for row in current['controls']):break
                button=tablet.resource('tabletPage.'+str(page))
                if ui.available(button):self.step(scope,'tablet-page-'+str(page),current,lambda button=button:ui.click(button))
            self.click(scope,'places-entry','navigation.entry')
        self.wait_ui(lambda value:any(r['id']=='navigation.page' for r in value['controls']))
        self.click(scope,'places-tab','navigation.placesTab')
        self.wait_ui(lambda value:any(r['id']=='navigation.refreshPlaces' and r['enabled'] for r in value['controls']))
        self.click(scope,'directory-refresh','navigation.refreshPlaces')
        # Respect the original queued UI/200 ms command guard without dispatch.
        self.wait_view(lambda value:value['source']['ui']['present'] and not value['source']['ui']['loading']
            and value['source']['ui']['pendingCommands']==0 and value['source']['ui']['activeTimers']==0)

    def goto(self,scope,url):
        self.close(scope+'-preclose');ui,tablet=self.ui();field=tablet.resource('PhoneAddressField')
        self.lease('address',True)
        self.step(scope,'goto-open',self.adapter._navigation_view(self.selector).read(self.run),lambda:ui.click(Locator('accessibility id','Go to destination')))
        ui.wait_control(field)
        self.step(scope,'goto-text',{'url':url},lambda:ui.replace_text(field,url));need(ui.text(field)==url)
        self.step(scope,'goto-submit',self.adapter._navigation_view(self.selector).read(self.run),lambda:ui.click(tablet.resource('PhoneAddressGoButton')))
        # The actual not-found path may leave its owned address page visible.
        if not url.startswith('hifi://hidden-'):
            ui.wait_absent(field);self.lease('address',False)

    def probe(self,after=0):
        return self.adapter._navigation_probe(self.selector,after)

    def wait_arrival(self,label):
        urls=viewpoint_urls(self.source.inputs['sceneUrl']);deadline=self.monotonic()+20;fresh_probe=FreshNavigation()
        count=0;start=None
        for attempt in range(81):
            value=self.probe(fresh_probe.previous['sampleSequence'] if fresh_probe.previous else 0);_,advanced=fresh_probe.accept(value);self.bound()
            if arrived(value,urls[label],label) and advanced:
                if start is None:start=self.monotonic()
                count+=1
                if count>=3 and self.monotonic()-start>=.5:return value
            else:count=0;start=None
            need(attempt<80 and self.monotonic()<deadline);self.sleep(.25)
        need(False)

    def wait_view(self,predicate):
        reader=self.adapter._navigation_view(self.selector,read_only=True);deadline=self.monotonic()+10
        for attempt in range(101):
            value=reader.read(self.run);self.bound()
            if predicate(value):return value
            need(attempt<100 and self.monotonic()<deadline);self.sleep(.1)
        need(False)

    def prepare(self):
        need(self.role=='primary')
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            self.started=self.monotonic();state=self.load()
            if state is None:
                need(self.retirement_store.read() is None)
                for role in ('primary','actor'):
                    need(PrivateFeatureState(self.store.path.with_name('phone-navigation-'+role+'-feature.json')).read() is None
                        and self.adapter.world_render_store(self.selector,role=role).read() is None)
                phase=self.source.read();need(phase['verb']=='baseline')
                ui,_,binding,guard,_=self.adapter.normal_feature_runtime(self.selector)
                need(binding['sourceRevision']==self.source.inputs['sourceRevision'])
                baseline=self.adapter._navigation_view(self.selector).read(self.run);actual=baseline['source'];ctx=fixture_context(self.run)
                need(not actual['tabletShown'] and not actual['ui']['present'] and not actual['ui']['addressDialog'] and not actual['ui']['notFoundModal'] and not actual['ui']['bookmarkDialog']
                    and not actual['ui']['pendingCommands'] and not actual['ui']['activeTimers'] and not actual['keyboard']['visible'] and not any(name in actual['storage']['bookmarks'] for name in (ctx['name'],ctx['renamed'])))
                parsed=urlsplit(self.source.client.url);origin=parsed.scheme+'://'+parsed.netloc
                need(actual['endpoint'].rstrip('/')==origin and actual['protocolSignature']==self.source.inputs['protocolSignature'])
                initial=self.probe();need(initial['sceneUrl'].split('?')[0]==self.source.inputs['sceneUrl'] and not initial['inAir'] and not initial['flying']
                    and math.dist(list(initial['feetPosition'].values()),[0,0,4])<=.75)
                self.state=dict(phase='preparing',binding=deepcopy(binding),originalUrl=initial['sceneUrl'],baseline=baseline,
                    phaseStatus=phase['status'],navigationStatus=phase['navigation'],ticket=phase['ticket'],call=None,steps=[],
                    leases=dict(tablet=False,address=False),marker=None,markerHistory=[],restarts=[],cleanup=[])
                self.owner_save()
            if self.state['phase']=='preparing':
                self.goto('prepare',viewpoint_urls(self.source.inputs['sceneUrl'])['A']);self.wait_arrival('A')
                self.state['phase']='baseline';self.owner_save()
            self.started=None;return deepcopy(self.state)

    def marker_release(self,scope):
        owned=self.state['marker']
        if owned is None:return
        reader=self.adapter._navigation_marker(self.selector,read_only=True)
        if owned['original'] is not None:reader.restore([owned['original']])
        actual=reader.read(self.run);need(same(actual['source']['originalInput'],owned['request']))
        request=input_command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-navigation-marker-input',operation='release',
            runId=self.run,fixtureInstance=actual['source']['fixtureInstance']))
        # Releasing this exact E2E fixture is idempotent. Every retry still
        # requires actual same-object absence and original Browser drainage.
        if actual['source']['phase']!='drained':
            self.state['marker']['release']=request;self.owner_save()
            receipt=self.adapter._navigation_marker_input(self.selector,request);input_receipt(receipt,request)
        for attempt in range(101):
            actual=reader.read(self.run);self.bound()
            try:marker_retired(actual);break
            except NativeUIError:need(attempt<100);self.sleep(.1)
        web_reader=self.adapter._web_runtime_observer(self.selector,read_only=True)
        for attempt in range(101):
            web=web_reader.read(self.run,self.fixture_url);self.bound()
            try:web_released(web);break
            except NativeUIError:need(attempt<100);self.sleep(.1)
        self.state['markerHistory'].append(dict(owner=deepcopy(owned),retired=actual,web=web))
        need(len(self.state['markerHistory'])<=4);self.state['marker']=None;self.owner_save()

    def marker_prepare(self,scope,ticket):
        self.marker_release(scope+'-old')
        request=input_command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-navigation-marker-input',operation='prepare',runId=self.run,
            fixtureUrl=self.fixture_url,ticket=ticket,imageExtent=self.policy['imageExtent'],markerRoi=self.policy['markerRoi']))
        self.state['marker']=dict(request=request,release=None,original=None);self.owner_save()
        receipt=self.adapter._navigation_marker_input(self.selector,request);input_receipt(receipt,request)
        reader=self.adapter._navigation_marker(self.selector,read_only=True)
        for attempt in range(81):
            marker=reader.read(self.run);avatar=self.adapter._avatar_render_observer(self.selector,read_only=True).read();self.bound()
            try:marker_ready(marker,avatar);break
            except NativeUIError:need(attempt<80);self.sleep(.1)
        need(same(marker['source']['originalInput'],request) and marker['source']['fixtureInstance']==receipt['fixtureInstance'])
        self.state['marker']['original']=marker;self.owner_save()

    def act(self,call):
        call=deepcopy(arguments('feature.'+AREA+'.act',call));need(self.role=='primary' and call['runId']==self.run and call['fixtureUrl']==self.fixture_url)
        self.prepare()
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            self.started=self.monotonic();self.load();need(self.state['phase'] in ('baseline','active','acting'))
            phase=self.phase();need(phase['ticket']==call['ticket'] and phase['verb']==call['verb'] and same(phase['inputs'],call['inputs']))
            if self.state['ticket']==call['ticket'] and self.state['phase']=='active':need(same(self.state['call'],call));return {'performed':True}
            if self.state['phase']=='acting':need(same(self.state['call'],call))
            else:self.state.update(phase='acting',ticket=call['ticket'],call=call);self.owner_save()
            scope=call['ticket'];verb=call['verb'];ctx=fixture_context(self.run);inputs=call['inputs']
            if verb=='open':self.open(scope)
            elif verb.startswith('bookmark-add') or verb.startswith('bookmark-rename'):
                self.click(scope,'bookmarks-tab','navigation.bookmarksTab')
                if verb.startswith('bookmark-add'):self.click(scope,'bookmark-dialog','navigation.addBookmark')
                else:self.choose(scope,'bookmark-dialog','navigation.renameBookmark.',{'bookmarkName':ctx['name']})
                dialog=self.wait_ui(lambda packet:any(r['id']=='navigation.bookmarkName' for r in packet['controls']))
                name_rows=[r for r in dialog['controls'] if r['id']=='navigation.bookmarkName']
                need(len(name_rows)==1 and name_rows[0].get('dialogOriginalName')==('' if verb.startswith('bookmark-add') else ctx['name'])
                    and name_rows[0].get('dialogAddress')==viewpoint_urls(self.source.inputs['sceneUrl'])['A'])
                self.field(scope,'bookmark-name','navigation.bookmarkName',inputs['name'])
                self.click(scope,'bookmark-submit','navigation.bookmark.cancel' if verb.endswith('cancel') else 'navigation.bookmark.save')
                self.wait_ui(lambda packet:not any(r['id'] in ('navigation.bookmarkName','navigation.bookmark.save','navigation.bookmark.cancel') for r in packet['controls']))
            elif verb=='directory-search':
                self.click(scope,'places-tab','navigation.placesTab');self.field(scope,'directory-query','navigation.placesSearch',inputs['query'])
            elif verb=='directory-select':
                self.choose(scope,'directory-select','navigation.visitPlace.',{'placeId':inputs['destination']})
                self.wait_arrival('B');self.close(scope);self.marker_prepare(scope,call['ticket'])
            elif verb=='navigate-missing':self.goto(scope,'hifi://'+ctx['hidden'])
            elif verb=='dismiss-error':self.click(scope,'error-dismiss','navigation.error.ok');self.close_address(scope)
            elif verb=='bookmark-visit':
                self.marker_release(scope);self.open(scope);self.click(scope,'bookmarks-tab','navigation.bookmarksTab')
                self.choose(scope,'bookmark-visit','navigation.visitBookmark.',{'bookmarkName':inputs['name']})
                self.wait_arrival('A');self.close(scope);self.marker_prepare(scope,call['ticket'])
            elif verb=='bookmark-delete':
                self.click(scope,'bookmarks-tab','navigation.bookmarksTab');self.choose(scope,'bookmark-delete','navigation.deleteBookmark.',{'bookmarkName':inputs['name']})
            elif verb=='close':self.close(scope)
            elif verb=='restart-app':self.restart(scope)
            else:need(False)
            self.state['phase']='active';self.owner_save();self.started=None;return {'performed':True}

    def restart(self,scope):
        self.marker_release(scope)
        if not self.state['restarts']:
            before=self.adapter._native_feature_observer(self.selector,read_only=True).read(0)
            view=self.adapter._navigation_view(self.selector,read_only=True).read(self.run)
            need(not view['source']['tabletShown'] and not any(view['source']['ui'][key] for key in ('present','addressDialog','notFoundModal','bookmarkDialog','pendingCommands','activeTimers')))
            self.state['restarts'].append(dict(binding=deepcopy(self.state['binding']),native=before,view=view,stop='planned',launch='planned',proof=None));self.owner_save()
        plan=self.state['restarts'][0];need(plan['proof'] is None)
        old=plan['binding'];status=self.adapter._graphics_lifecycle_status(self.selector,old)
        if plan['stop']=='planned':
            need(status['process']['running'] and status['process']['identity']==old['processIdentity'])
            plan['stop']='issued';self.owner_save();self.adapter.invoke(self.selector,'app.stop',{});plan['stop']='returned';self.owner_save()
        status=self.adapter._graphics_lifecycle_status(self.selector,old)
        if plan['launch']=='planned':
            need(not status['process']['running']);plan['launch']='issued';self.owner_save()
            self.adapter.invoke(self.selector,'app.launch',{});plan['launch']='returned';self.owner_save()
        _,_,binding,guard,_=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        need(all(same(binding[key],old[key]) for key in old if key!='processIdentity') and binding['processIdentity']!=old['processIdentity'])
        after=self.adapter._native_feature_observer(self.selector,read_only=True).read(0)
        validate_native_restart(dict(pid=plan['native']['processId'],instance=plan['native']['instance'],lifecycle=plan['native']['lifecycle']),
            dict(pid=after['processId'],instance=after['instance'],lifecycle=after['lifecycle']))
        exit=self.adapter._process_presence(self.selector,read_only=True).require_absent(plan['native']['processId'])
        view=self.adapter._navigation_view(self.selector,read_only=True).read(self.run)
        need(same(view['source']['storage'],plan['view']['source']['storage']) and same(view['source']['preferences'],plan['view']['source']['preferences']))
        plan['proof']=dict(binding=deepcopy(binding),native=after,view=view,exit=exit)
        self.state['binding']=deepcopy(binding);self.owner_save()

    def role_state(self):
        state=self.read(self.role_store,self.role)
        if state is None:return dict(phase='ready',binding=deepcopy(self.state['binding']),sequence=0,frames=[],pending=None,images=[],cleanupWindow=None,retired=None)
        exact(state,{'phase','binding','sequence','frames','pending','images','cleanupWindow','retired'})
        need(state['phase'] in ('ready','reading','retired') and integer(state['sequence'],0,1000000000)
            and type(state['frames']) is list and len(state['frames'])<=256 and type(state['images']) is list and len(state['images'])<=256)
        context(state['binding'])
        for image in state['images']:
            NavigationImages.record(image)
            if image['phase']=='saved':NavigationImages.archive(self.root,image)
        return state

    def role_save(self,state):self.save(self.role_store,self.role,state)

    def retire_images(self,state,store=None,role=None):
        for image in list(state['images']):
            NavigationImages.record(image)
            if image['phase']=='saved':NavigationImages.archive(self.root,image)
            else:
                NavigationImages.retire_partial(self.root,image)
                state['images'].remove(image)
                self.save(store or self.role_store,role or self.role,state)

    def recover(self,state):
        self.retire_images(state)
        if state['phase']!='reading':return
        owner=self.adapter.world_render_store(self.selector,role=self.role)
        if owner.read() is not None:self.adapter._world_render_capture(self.selector,read_only=True,role=self.role).release()
        # Preserve every original partial record and uncertain file intent.
        # Recovery publishes no old sample and creates no new application input.
        need(state['pending'] is not None)
        state['pending']['abandoned']=True;self.state['cleanup'].append(deepcopy(state['pending']));need(len(self.state['cleanup'])<=64);self.owner_save()
        state.update(phase='ready',pending=None);self.role_save(state)

    def frame(self,state,phase,*,retired=False):
        view=self.adapter._navigation_view(self.selector,read_only=True)
        native=self.adapter._native_feature_observer(self.selector,read_only=True)
        last=state['frames'][-1] if state['frames'] and state['frames'][-1]['before']['processId']==int(self.state['binding']['processIdentity'].split(':')[0]) else None
        if last is not None:view.last=deepcopy(last['after'])
        before=view.read(self.run)
        for attempt in range(101):
            current=before['source']['ui'];settled=not current['pendingCommands'] and not current['activeTimers'] and (not current['present'] or not current['loading'])
            state['pending']['before']=before;self.role_save(state)
            if settled:break
            need(attempt<100);self.sleep(.1);before=view.read(self.run);self.bound()
        probe=self.probe(last['probe']['sampleSequence'] if last else 0)
        for attempt in range(16):
            if probe['sampleEpochMs']>=before['capturedEpochMs']:break
            need(attempt<15);self.sleep(.05);probe=self.probe(probe['sampleSequence'])
        lifecycle=native.read(last['native']['sequence'] if last else 0)
        if last is not None:need(lifecycle['instance']==last['native']['instance'] and lifecycle['sequence']>last['native']['sequence']
            and all(lifecycle['lifecycle'][key]>=last['native']['lifecycle'][key] for key in last['native']['lifecycle']))
        backend=self.source.navigation(self.state['navigationStatus'])
        frame=dict(role=self.role,ticket=phase['ticket'],phase=phase['status'],providerInstance=self.source.instance,navigation=backend,before=before,probe=probe,
            native=lifecycle,after=None,missing=None,image=None,capture=None,release=None,marker=None,web=None)
        if before['source']['ui']['notFoundModal']:
            parsed=urlsplit(self.source.client.url)
            frame['missing']=self.adapter._navigation_replies(self.selector,read_only=True).owned_missing(self.run,owned_origin=parsed.scheme+'://'+parsed.netloc,
                ticket=phase['ticket'],after_epoch=math.ceil(phase['afterEpochMs']),provider_status=backend,
                provider_instance=self.source.instance,provider_inputs=self.source.inputs)
        if phase['verb'] in ('directory-select','bookmark-visit'):
            need(self.state['marker'] is not None)
            marker_reader=self.adapter._navigation_marker(self.selector,read_only=True)
            originals=[f['marker'] for f in state['frames'] if f['marker'] is not None and f['marker']['processId']==marker_reader.pid and same(f['marker']['source']['originalInput'],self.state['marker']['request'])]
            marker_reader.restore([originals[-1]] if originals else [self.state['marker']['original']])
            marker=marker_reader.read(self.run)
            need(same(marker['source']['originalInput'],self.state['marker']['request']))
            avatar=self.adapter._avatar_render_observer(self.selector,read_only=True).read();marker_ready(marker,avatar)
            web_reader=self.adapter._web_runtime_observer(self.selector,read_only=True)
            webs=[f['web'] for f in state['frames'] if f['web'] is not None and f['web']['processId']==web_reader.pid]
            if webs:web_reader.last=deepcopy(webs[-1])
            web=web_reader.read(self.run,self.fixture_url)
            active_marker(web,self.state['marker']['request']['fixtureUrl']+'tickets/'+self.state['marker']['request']['ticket']+'/graphics-marker.v1.html')
            capture=self.adapter._world_render_capture(self.selector,read_only=True,role=self.role,require_trace=True,require_frame_view=True)
            packet,raw=capture.read(0);frame.update(capture=packet,marker=marker,web=web)
            from overte_phone_navigation_marker import near,rotation_equal,VIEW
            recorded=packet['source']['renderTrace']['recordedView'];wanted=marker['source']['originalView']
            need(all(near(recorded[key],wanted[key],.0001) for key in VIEW if key!='rotation') and rotation_equal(recorded['rotation'],wanted['rotation'],.0001))
            earlier=[f['capture'] for f in state['frames'] if f['capture'] is not None and f['capture']['processId']==packet['processId']]
            if earlier:need(packet['instance']==earlier[-1]['instance'] and packet['sequence']>earlier[-1]['sequence']
                and packet['source']['acquisitionSequence']>earlier[-1]['source']['acquisitionSequence']
                and packet['source']['renderTrace']['frameId'] not in {v['source']['renderTrace']['frameId'] for v in earlier})
            index=len(state['images'])+1;need(index<=256)
            def intent(value):
                if state['images'] and state['images'][-1]['capture']['requestId']==value['capture']['requestId']:state['images'][-1]=deepcopy(value)
                else:state['images'].append(deepcopy(value))
                self.role_save(state)
            images=NavigationImages(self.root,self.state['binding'],self.run,self.role,index,view.guard,intent,monotonic=self.monotonic)
            image=images.write(phase['ticket'],packet,raw)
            image_observation(raw,self.run,phase['ticket'],self.policy['imagePolicy'])
            frame.update(image=image,release=capture.release())
        frame['after']=view.read(self.run)
        state['pending']['frame']=deepcopy(frame);self.role_save(state)
        if retired:
            final_status=self.source.status(phase['status']);need(not final_status['active'] and same(final_status['activations'],phase['status']['activations']))
        else:
            final_phase=self.source.read(phase['status']);need(final_phase['ticket']==phase['ticket'])
        parsed=urlsplit(self.source.client.url);origin=parsed.scheme+'://'+parsed.netloc
        actual=measurement(self.run,frame,self.state['baseline'],self.source.inputs,origin,pid=frame['before']['processId'],
            epoch=int(native.clock_ms()),after_epoch=math.ceil(phase['afterEpochMs']),previous=last,retired=retired)
        need(frame['after']['capturedEpochMs']>=frame['native']['capturedEpochMs'])
        return frame,actual

    def retired_sample(self,state,status):
        need(self.state['phase']=='cleaned' and not status['active'] and status['activations'])
        latest=status['activations'][-1];need(latest['stimulus']==dict(verb='cleanup',inputs={}))
        self.recover(state);self.runtime(read_only=True)
        phase=dict(ticket=latest['ticket'],afterEpochMs=status['retiredEpochMs'],status=status,verb='cleanup')
        state.update(phase='reading',pending=dict(ticket=phase['ticket'],binding=deepcopy(state['binding']),before=None,frame=None,abandoned=False));self.role_save(state)
        frame,actual=self.frame(state,phase,retired=True)
        need(actual==dict(location='A',bookmark=False,bookmarkName='',searchQuery='',searchResults=[],error='none',panel=False,addressDialog=False))
        state['frames'].append(frame);state['sequence']+=1;need(len(state['frames'])<=256)
        now=frame['after']['capturedEpochMs'];window=state['cleanupWindow']
        if window is None:window=dict(ticket=phase['ticket'],firstEpochMs=now,firstMonotonic=self.monotonic(),samples=0,complete=False)
        window['samples']+=1;window['complete']=window['samples']>=3 and now-window['firstEpochMs']>=3000 and self.monotonic()-window['firstMonotonic']>=3
        state.update(phase='ready',pending=None,cleanupWindow=window);self.role_save(state)
        return window['complete']

    def observe(self,call):
        call=arguments('feature.'+AREA+'.observe',call);need(call['runId']==self.run)
        if self.role=='primary':self.prepare()
        pending=None
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            self.started=self.monotonic();self.load()
            try:
                if self.state is None or self.state['phase'] in ('preparing','acting','cleaning','restoring'):raise PhasePending('Navigation normal input or restoration is incomplete')
                state=self.role_state();need(call['afterSequence']<=state['sequence']);self.recover(state)
                phase=self.phase()
                if phase['verb']=='cleanup':
                    if self.state['phase']!='cleaned':raise PhasePending('Navigation cleanup has not restored its ordinary controls')
                elif phase['verb']!='baseline' and phase['ticket']!=self.state['ticket']:raise PhasePending('Navigation phase awaits its ordinary input')
                if not same(state['binding'],self.state['binding']):
                    need(len(self.state['restarts'])==1 and self.state['restarts'][0]['proof'] is not None
                        and same(state['binding'],self.state['restarts'][0]['binding'])
                        and same(self.state['binding'],self.state['restarts'][0]['proof']['binding']))
                    state['binding']=deepcopy(self.state['binding'])
                self.runtime(read_only=True)
                state.update(phase='reading',pending=dict(ticket=phase['ticket'],binding=deepcopy(state['binding']),before=None,frame=None,abandoned=False));self.role_save(state)
                for attempt in range(41):
                    try:frame,actual=self.frame(state,phase);break
                    except PhasePending:
                        need(attempt<40);self.recover(state);self.sleep(.1)
                        state.update(phase='reading',pending=dict(ticket=phase['ticket'],binding=deepcopy(state['binding']),before=None,frame=None,abandoned=False));self.role_save(state)
                need(len(state['frames'])<256)
                state['frames'].append(frame);state['sequence']+=1
                resources=[]
                if actual['panel'] or actual['addressDialog'] or actual['error']!='none':resources.append('panel:navigation')
                if actual['bookmark']:resources.append('file:navigation-bookmark')
                if self.state['marker'] is not None:resources.append('entity:navigation-marker')
                if phase['verb']=='cleanup':
                    need(not resources and actual==dict(location='A',bookmark=False,bookmarkName='',searchQuery='',searchResults=[],error='none',panel=False,addressDialog=False))
                    now=frame['after']['capturedEpochMs'];window=state['cleanupWindow']
                    if window is None or window['ticket']!=phase['ticket']:window=dict(ticket=phase['ticket'],firstEpochMs=now,firstMonotonic=self.monotonic(),samples=0,complete=False)
                    window['samples']+=1;window['complete']=window['samples']>=3 and now-window['firstEpochMs']>=3000 and self.monotonic()-window['firstMonotonic']>=3
                    state['cleanupWindow']=window
                    if self.role=='primary':
                        actor_store=PrivateFeatureState(self.store.path.with_name('phone-navigation-actor-feature.json'))
                        actor=self.read(actor_store,'actor')
                        if not window['complete'] or actor is None or actor['cleanupWindow'] is None or not actor['cleanupWindow']['complete']:
                            resources.append('input:navigation-retirement')
                state.update(phase='ready',pending=None);self.role_save(state)
                artifacts=[]
                if frame['image'] is not None:artifacts.append(dict(kind='image',source='world-render-target',name=frame['image']['name'],sequence=state['sequence'],
                    capturedEpochMs=frame['capture']['capturedEpochMs'],ticket=phase['ticket']))
                value=dict(schemaVersion=1,contractVersion=CONTRACT_VERSION,runId=self.run,sequence=state['sequence'],capturedEpochMs=frame['after']['capturedEpochMs'],
                    state=actual,artifacts=artifacts,resources=resources,lifecycle=frame['native']['lifecycle'])
                self.started=None;return result('feature.'+AREA+'.observe',value)
            except PhaseRetired as error:
                need(self.role=='actor' and self.state['phase']=='cleaned')
                state=self.role_state()
                if state['cleanupWindow'] is None or not state['cleanupWindow']['complete']:
                    if not self.retired_sample(state,error.status):
                        pending=PhasePending('Navigation retired cleanup quiet window is incomplete')
                    else:
                        state.update(phase='retired',retired=error.status);self.role_save(state);pending=error
                else:
                    state.update(phase='retired',retired=error.status);self.role_save(state);pending=error
            except PhasePending as error:pending=error
        self.started=None;raise pending

    def publish(self):
        need(self.role=='actor')
        value=self.observe(dict(contractVersion=CONTRACT_VERSION,runId=self.run,afterSequence=0))
        with self.lock.held():
            self.load();state=self.role_state();need(state['phase']=='ready' and state['sequence']==value['sequence'])
            ticket=state['frames'][-1]['ticket']
        payload=dict(ticket=ticket,actor='owned-observer',actorSequence=value['sequence'],capturedEpochMs=value['capturedEpochMs'],facts=projection(AREA,value['state']))
        try:self.source.client.request('/runs/'+self.run+'/samples',payload)
        except ValueError:
            if self.source.read()['ticket']!=ticket:raise PhasePending('Navigation publication crossed its original phase') from None
            raise
        return value

    def cleanup(self,call):
        arguments('feature.'+AREA+'.cleanup',call);need(self.role=='primary' and call['runId']==self.run)
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            self.started=self.monotonic();self.load()
            if self.state is None:return {'performed':True}
            phase=self.phase();need(phase['verb']=='cleanup');scope=phase['ticket']
            if self.state['phase']=='cleaned':need(self.state['ticket']==scope);return {'performed':True}
            self.state.update(phase='cleaning',ticket=scope);self.owner_save()
            for role in ('primary','actor'):
                store=PrivateFeatureState(self.store.path.with_name('phone-navigation-'+role+'-feature.json'))
                retained=self.read(store,role)
                if retained is not None:self.retire_images(retained,store,role)
                owner=self.adapter.world_render_store(self.selector,role=role)
                if owner.read() is not None:self.adapter._world_render_capture(self.selector,read_only=True,role=role).release()
            self.marker_release(scope)
            current=self.adapter._navigation_view(self.selector).read(self.run)
            if current['source']['ui']['notFoundModal']:self.click(scope,'cleanup-error-dismiss','navigation.error.ok')
            if current['source']['ui']['bookmarkDialog'] and any(r['id']=='navigation.bookmark.cancel' for r in self.adapter._navigation_controls(self.selector).capture()['controls']):
                self.click(scope,'cleanup-bookmark-cancel','navigation.bookmark.cancel')
            ctx=fixture_context(self.run)
            names=[name for name in (ctx['name'],ctx['renamed']) if name in current['source']['storage']['bookmarks']]
            for name in names:
                self.open(scope+'-'+name);self.click(scope,'cleanup-bookmarks-'+name,'navigation.bookmarksTab')
                self.choose(scope,'cleanup-delete-'+name,'navigation.deleteBookmark.',{'bookmarkName':name})
                self.wait_view(lambda value:name not in value['source']['storage']['bookmarks'])
            self.goto(scope+'-restore-A',viewpoint_urls(self.source.inputs['sceneUrl'])['A']);self.wait_arrival('A');self.close(scope+'-final')
            ui,_=self.ui();ui.release_actions()
            actual=self.wait_view(lambda value:not value['source']['keyboard']['visible'] and not value['source']['tabletShown'] and not any(value['source']['ui'][k] for k in ('present','addressDialog','notFoundModal','bookmarkDialog','pendingCommands','activeTimers')))
            need(same(actual['source']['storage']['bookmarks'],self.state['baseline']['source']['storage']['bookmarks'])
                and same(actual['source']['preferences'],self.state['baseline']['source']['preferences']))
            self.state['cleanup'].append(actual);self.state['phase']='cleaned';self.owner_save();self.started=None;return {'performed':True}

    def finalize(self):
        need(self.role=='primary')
        for attempt in range(101):
            if self.finalize_once() is not False:return
            need(attempt<100);self.sleep(.1)

    def finalize_once(self):
        need(self.role=='primary')
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            self.started=self.monotonic();self.load();retirement=self.read(self.retirement_store,'retirement')
            if retirement is None:
                if self.state is None:return
                need(self.state['phase']=='cleaned' and self.state['marker'] is None and not any(self.state['leases'].values()))
                status=self.source.status(self.state['phaseStatus']);need(not status['active'])
                backend=self.source.navigation(self.state['navigationStatus']);need(not backend['active'])
                state=self.role_state()
                if state['cleanupWindow'] is None or not state['cleanupWindow']['complete']:
                    if not self.retired_sample(state,status):return False
                actor_store=PrivateFeatureState(self.store.path.with_name('phone-navigation-actor-feature.json'))
                actor=self.read(actor_store,'actor')
                if actor is None or actor['phase']!='retired':return False
                roles={}
                for role in ('primary','actor'):
                    store=PrivateFeatureState(self.store.path.with_name('phone-navigation-'+role+'-feature.json'))
                    value=self.read(store,role);need(value is not None and value['cleanupWindow'] is not None and value['cleanupWindow']['complete']
                        and value['phase'] in (('ready',) if role=='primary' else ('retired',)) and value['pending'] is None)
                    self.retire_images(value,store,role)
                    need(all(image['phase']=='saved' for image in value['images']))
                    roles[role]=deepcopy(self.previous[store.path])
                retirement=dict(owner=deepcopy(self.previous[self.store.path]),roles=roles,status=status,backend=backend,restored=False,proof=None)
                self.save(self.retirement_store,'retirement',retirement)
            else:
                original=self.frames(unpack(retirement['owner']['payload'])[0],loading=True)
                if self.state is not None and not same(self.previous[self.store.path],retirement['owner']):
                    current=self.state;need(current['phase']=='restoring')
                    need(all(same(current[key],original[key]) for key in original if key not in ('phase','steps','leases'))
                        and same(current['steps'][:len(original['steps'])],original['steps'])
                        and all(row['scope'] in ('finalize-original','finalize-original-preclose','finalize-close') for row in current['steps'][len(original['steps']):]))
                else:self.state=original
            if not retirement['restored']:
                # Only the exact controlled original scene admitted at setup is
                # restored, using ordinary Go To. No product state is assigned.
                self.state['phase']='restoring';self.owner_save()
                current=self.adapter._navigation_view(self.selector,read_only=True).read(self.run);probe=self.probe()
                neutral=not current['source']['keyboard']['visible'] and not current['source']['tabletShown'] and not any(current['source']['ui'][k] for k in ('present','addressDialog','notFoundModal','bookmarkDialog','pendingCommands','activeTimers'))
                if probe['sceneUrl']!=self.state['originalUrl'] or not neutral:
                    self.goto('finalize-original',self.state['originalUrl']);self.close('finalize-close')
                else:
                    self.lease('tablet',False);self.lease('address',False)
                self.ui()[0].release_actions();probes=[]
                for index in range(3):
                    observed=self.probe(probes[-1]['sampleSequence'] if probes else 0)
                    need(observed['sceneUrl']==self.state['originalUrl'] and not observed['inAir'] and not observed['flying']
                        and math.dist([observed['feetPosition'][k] for k in 'xyz'],[0,0,4])<=.75)
                    probes.append(observed)
                    if index<2:self.sleep(.25)
                view=self.adapter._navigation_view(self.selector,read_only=True).read(self.run)
                need(same(view['source']['storage']['bookmarks'],self.state['baseline']['source']['storage']['bookmarks'])
                    and same(view['source']['preferences'],self.state['baseline']['source']['preferences'])
                    and not view['source']['keyboard']['visible'] and not view['source']['tabletShown'] and not any(view['source']['ui'][k] for k in ('present','addressDialog','notFoundModal','bookmarkDialog','pendingCommands','activeTimers')))
                proof=dict(view=view,probes=probes)
                # Save the final actual owner before any child metadata removal.
                retirement.update(owner=deepcopy(self.previous[self.store.path]),restored=True,proof=proof)
                self.save(self.retirement_store,'retirement',retirement)
            self.runtime(read_only=True)
            current=self.adapter._navigation_view(self.selector,read_only=True).read(self.run)
            need(same(current['source'],retirement['proof']['view']['source']))
            need(self.probe()['sceneUrl']==self.state['originalUrl'])
            need(all(self.adapter.world_render_store(self.selector,role=role).read() is None for role in ('primary','actor')))
            archive=PrivateFeatureState(self.root/('navigation-retired-'+self.run+'.json'))
            record=dict(navigationRetirementVersion=VERSION,runId=self.run,payload=pack([self.frames(retirement,loading=False)]))
            old=archive.read()
            if old is None:archive.write(record,None)
            else:need(same(old,record))
            need(same(archive.read(),record))
            for role in ('primary','actor'):
                store=PrivateFeatureState(self.store.path.with_name('phone-navigation-'+role+'-feature.json'))
                old=store.read();need(old is None or same(old,retirement['roles'][role]))
                if old is not None:store.discard(old)
                need(store.read() is None)
            old=self.store.read();need(old is None or same(old,retirement['owner']))
            if old is not None:self.store.discard(old)
            need(self.store.read() is None)
            self.retirement_store.discard(self.previous[self.retirement_store.path]);need(self.retirement_store.read() is None)
            self.started=None
