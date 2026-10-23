"""Private Pico tablet-browser coordinator with independently sampled originals.

All product facts come from original sources. Fixture activations authorize
inputs only; an ACK never supplies text, document counts, HTTP status or pixels.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time
import uuid
from urllib.parse import urlsplit

from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.native_web_runtime import released
from adapters.feature_fixture_access import AdapterFixtureClient
from feature_journeys.contract import arguments,result,identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,PhasePending,PhaseRetired
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from feature_journeys.witness import projection
from adapters.script_journey.history import pack,unpack,same
from adapters.script_journey.lock import ScriptSourceLock
from adapters.pico4.browser_source import continuity,fixture,validate as validate_source
from adapters.pico4.browser_measurements import browser_status,measurement

VERSION=3
READS=(1,2,3)


def archive_originals(value):
    """Compress repeated originals together within the unchanged private cap."""
    if type(value) is list:return [archive_originals(item) for item in value]
    if type(value) is not dict:return value
    if set(value)=={'encoding','bytes','sha256','data'}:
        return dict(webPackedSourceVersion=1,frames=archive_originals(unpack(value)))
    return {key:archive_originals(item) for key,item in value.items()}


def restore_originals(value):
    if type(value) is list:return [restore_originals(item) for item in value]
    if type(value) is not dict:return value
    if 'webPackedSourceVersion' in value:
        exact(value,{'webPackedSourceVersion','frames'})
        need(type(value['webPackedSourceVersion']) is int and value['webPackedSourceVersion']==1)
        return pack(restore_originals(value['frames']))
    return {key:restore_originals(item) for key,item in value.items()}


class PicoTabletWebFeature:
    area="tablet-web"
    surface="tablet"
    action="pico-tablet-web"
    version_field="picoTabletWebFeatureVersion"
    def __init__(self,adapter,selector,source,artifact_root,foreign_fixture_url,*,role='primary',monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(source,PhaseFixtureReader) and source.area==self.area and role in ('primary','actor')
            and callable(monotonic) and callable(sleep))
        self.adapter,self.selector,self.source,self.role=adapter,selector,source,role
        self.run,self.fixture_url=source.run,source.fixture_url
        self.artifact_root=Path(artifact_root);PrivateFeatureState(self.artifact_root/(self.area+'-boundary.json'))._parent()
        fixture(self.run,self.fixture_url)
        foreign=foreign_fixture_url.rstrip('/')+'/runs/'+self.run+'/'
        fixture(self.run,foreign);a,b=urlsplit(self.fixture_url),urlsplit(foreign)
        need((a.scheme,a.netloc)!=(b.scheme,b.netloc));self.foreign_url=foreign
        if role=='actor':need(not isinstance(source.client,AdapterFixtureClient))
        self.monotonic,self.sleep=monotonic,sleep
        path=adapter.state_path(selector)
        self.store=PrivateFeatureState(path.with_name('pico-'+self.area+'-feature.json'))
        self.role_store=PrivateFeatureState(path.with_name('pico-'+self.area+'-'+role+'.json'))
        self.retirement_store=PrivateFeatureState(path.with_name('pico-'+self.area+'-retirement.json'))
        self.lock=adapter._lock(selector)
        self.originals={};self.live_owner=None;self.fence=None
        self._owner_cache=None;self._sealed_owner_cache=None
        self._image_cache={};self.image_cache_digests={}
        self.vm_cache=None;self.vm_cache_scope=None
        self.quiet_cache=None;self.quiet_cache_scope=None
        self.history_cache=None;self.history_scope=None
        self.completed_store=PrivateFeatureState(self.artifact_root/(self.area+'-'+self.run+'-retirement.json'))

    def manager_store(self):
        return getattr(self.adapter,self.area.replace('-','_')+'_manager_store')(self.selector)

    def manager(self):
        return self.adapter._tablet_web_manager(self.selector,self)

    def vm_reader(self,owner):
        from adapters.pico4.browser_vm import PicoBrowserVm
        self.lock.assert_held();need(owner['scriptUrl'] is not None)
        scope=dict(binding=owner['binding'],scriptUrl=owner['scriptUrl'],role=self.role,runId=self.run,fixtureUrl=self.fixture_url)
        if self.vm_cache is None:
            reader=self.adapter._tablet_web_vm(self.selector,self);need(isinstance(reader,PicoBrowserVm))
            self.vm_cache,self.vm_cache_scope=reader,deepcopy(scope)
        need(same(self.vm_cache_scope,scope));return self.vm_cache

    def check_released(self,runtime):
        return released(runtime,require_renderers=True)

    @contextmanager
    def serialized(self):
        pending=None
        with self.lock.held():
            try:yield
            except PhasePending as error:pending=error
        if pending is not None:raise pending

    def read(self,store,kind):
        value=store.read();self.originals[store.path]=deepcopy(value)
        return self.decode_record(value,kind)

    def decode_record(self,value,kind):
        if value is None:return None
        exact(value,{self.version_field,'kind','runId','fixtureUrl','artifactRoot','foreignFixtureUrl','payload'})
        need(type(value[self.version_field]) is int and value[self.version_field] in READS and value['kind']==kind
            and value['runId']==self.run and value['fixtureUrl']==self.fixture_url and value['artifactRoot']==str(self.artifact_root)
            and value['foreignFixtureUrl']==self.foreign_url.rsplit('/runs/',1)[0])
        rows=unpack(value['payload']);need(len(rows)==1)
        decoded=restore_originals(rows[0]) if kind in ('retirement','completed') else rows[0]
        if kind in ('primary','actor') and value[self.version_field]==1:
            # Verify every original v1 file and duplicate body before replacing
            # the duplicate with its existing full-stamp/hash file reference.
            self.verify_images(decoded,kind,legacy=True)
            for image in decoded['images']:del image['record']
        return decoded

    def write(self,store,kind,value):
        self.lock.assert_held();need(store.path in self.originals and same(store.read(),self.originals[store.path]))
        record=dict(**{self.version_field:VERSION},kind=kind,runId=self.run,fixtureUrl=self.fixture_url,
            artifactRoot=str(self.artifact_root),foreignFixtureUrl=self.foreign_url.rsplit('/runs/',1)[0],
            payload=pack([archive_originals(value) if kind in ('retirement','completed') else value]))
        store.write(record,self.originals[store.path]);need(same(store.read(),record));self.originals[store.path]=deepcopy(record)

    def owner(self):
        # Always read the actual private root. Only pure validation/decompression
        # of this exact unchanged record and context can reuse immutable bytes.
        from adapters.chat_journey.source_chunks import json_digest
        from adapters.script_journey.history import canonical
        record=self.store.read();self.originals[self.store.path]=deepcopy(record)
        need(self._owner_cache is self._sealed_owner_cache)
        if record is None:return None
        key=json_digest(dict(record=record,area=self.area,runId=self.run,fixtureUrl=self.fixture_url,
            foreignFixtureUrl=self.foreign_url,artifactRoot=str(self.artifact_root),store=str(self.store.path),
            lock=str(self.lock.path),versionField=self.version_field,reads=list(READS)))
        if self._owner_cache is not None and self._owner_cache[0]==key:
            value=json.loads(self._owner_cache[1])
        else:
            value=self.decode_record(record,'owner');self.validate_owner(value)
            # Strict JSON admission precedes freezing; caller inspection/input
            # copies never become a trusted mutable validation cache.
            json_digest(value);self._owner_cache=(key,canonical(value));self._sealed_owner_cache=self._owner_cache
        # A referenced independent journal remains a physical source, even
        # when this parent record is unchanged. Never cache its verification.
        if value['cleanupProof'] is not None and 'browserQuietReferenceVersion' in value['cleanupProof']:
            self.cleanup_window(value)
        self.live_owner=value;return value

    def validate_owner(self,value):
        exact(value,{'binding','ownerToken','phase','reserved','scriptUrl','call','tickets','phaseSource','cleanupProof','lifecycle','inputs','tabletOwned'})
        context(value['binding']);identifier(value['ownerToken'])
        need(value['phase'] in ('preparing','baseline','acting','active','cleaning','cleaned') and type(value['reserved']) is bool
            and type(value['tickets']) is list and len(value['tickets'])<=256 and len(set(value['tickets']))==len(value['tickets'])
            and (value['cleanupProof'] is None or type(value['cleanupProof']) is dict))
        for ticket in value['tickets']:identifier(ticket)
        if value['scriptUrl'] is not None:
            need(value['scriptUrl'].startswith(self.fixture_url+'tickets/') and re_script(value['scriptUrl'][len(self.fixture_url+'tickets/'):]))
        if value['call'] is not None:
            arguments('feature.'+self.area+'.act',value['call']);need(value['call']['runId']==self.run and value['call']['fixtureUrl']==self.fixture_url
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
                packet=anchor[field];phase_packet(packet,run=self.run,area=self.area,request=packet['requestId'],epoch=packet['capturedEpochMs'])
                need(packet['activations'] and packet['activations'][-1]['ticket']==row['ticket'])
            need(anchor['before']['activations']==anchor['packet']['activations'])
            need(row['envelope'] is None or type(row['envelope']) is dict)
            if index:need(anchor['hostMonotonic']>=value['inputs'][index-1]['anchor']['hostMonotonic'])
        if value['cleanupProof'] is not None and 'browserQuietReferenceVersion' not in value['cleanupProof']:
            from adapters.pico4.browser_quiet import validate as quiet_packet
            quiet_packet(value['cleanupProof'],self.run,self.fixture_url,value['ownerToken'],
                int(value['binding']['processIdentity'].split(':',1)[0]),retired=False)

    def save(self,value):
        self.live_owner=value;self.write(self.store,'owner',value)

    def runtime(self,owner):
        _ui,_observe,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        need(same(context(binding),owner['binding']) and guard() is not False)
        return binding,guard

    def io(self,owner,*,read_only=True):
        self.runtime(owner);return self.adapter._tablet_web_io(self.selector,self,read_only=read_only)

    def phase(self,owner):
        active=self.source.read(owner['phaseSource'])
        if owner['phase'] in ('acting','cleaning'):raise PhasePending('Owned Tablet Web input or retirement is in progress')
        return active

    def prepare(self):
        need(self.role=='primary')
        with self.serialized(),self.adapter.existing_input_session(self.selector):
            owner=self.owner()
            if owner is None:
                need(self.retirement_store.read() is None and self.role_store.read() is None and self.completed_store.read() is None
                    and self.manager_store().read() is None)
                need(not any(path.name.startswith('pico-'+self.area+'-') for path in self.store.path.parent.iterdir()))
                self.adapter._tablet_web_capture_guard(self.selector,self.lock)
                phase=self.source.read();need(phase['verb']=='baseline')
                _ui,_observe,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
                guard();owner=dict(binding=deepcopy(binding),ownerToken=uuid.uuid4().hex,phase='preparing',reserved=False,scriptUrl=None,
                    call=None,tickets=[],phaseSource=phase['status'],cleanupProof=None,lifecycle=None,inputs=[],tabletOwned=False);self.save(owner)
            self.runtime(owner)
            if owner['phase']=='preparing':
                need(not owner['inputs'])
                packet=self.source_control(owner,'reserve')
                need(packet['source']=={'reserved':True})
                owner.update(reserved=True,phase='baseline');self.save(owner)
            return deepcopy(owner)

    def sample_native(self,owner,previous=None):
        io=self.io(owner);io.last=deepcopy(previous)
        return io.request(self.run,self.fixture_url,owner['ownerToken'],'observe')

    def source_control(self,owner,operation):
        self.input_begin(dict(kind='source-control',operation=operation))
        return self.io(owner,read_only=False).request(self.run,self.fixture_url,owner['ownerToken'],operation)

    def input(self,owner,control,text=''):
        before=self.sample_native(owner);current=before['source']['current'];need(bool(current))
        io=self.io(owner,read_only=False);view=current['source']['nativeView']
        return io.input_visible(self.run,self.fixture_url,owner['ownerToken'],view,control,text,
            intent=lambda original:self.input_begin(dict(kind='browser',original=deepcopy(original))))

    def deliver(self,owner,call):
        verb=call['verb']
        if verb=='open':
            need(owner['scriptUrl'] is None)
            owner['scriptUrl']=self.fixture_url+'tickets/'+call['ticket']+'/client.js';self.save(owner)
            manager=self.manager()
            manager.open();manager.load_source(owner['scriptUrl'])
            manager.wait_rows(lambda rows:any(row['url']==owner['scriptUrl'] for row in rows));manager.close_tablet()
            self.adapter._tablet_web_entry(self.selector,self,'browser-app.web',initial=True)
            self.vm_reader(owner).capture()
        elif verb in ('open-inline-app','return-from-inline'):
            need(bool(self.sample_native(owner)['source']['current']))
            self.adapter._tablet_web_entry(self.selector,self,'browser-app.inline' if verb=='open-inline-app' else 'browser-app.web',initial=False)
        elif verb=='hold-inline-message':
            self.source_control(owner,'arm-held');self.input(owner,'bridge')
        elif verb=='deliver-retired-inline-message':self.source_control(owner,'deliver-held')
        elif verb=='close':self.close_source(owner)
        elif verb in ('focus-type','clear-text'):self.input(owner,'text',call['inputs'].get('text',''))
        elif verb in ('submit','foreign-origin-message'):self.input(owner,'bridge')
        elif verb=='navigate':self.input(owner,{'reference.html':'reference','page-b.html':'second','recovery.html':'recovery'}[call['inputs']['resource']])
        elif verb=='navigate-foreign':
            native=self.sample_native(owner);url=native['source']['current']['source']['nativeView']['sourceUrl']
            path=urlsplit(url).path;foreign=urlsplit(self.foreign_url)
            target=foreign.scheme+'://'+foreign.netloc+path
            self.input(owner,'foreign',target);self.input(owner,'navigate')
        elif verb in ('back','reload'):self.input(owner,verb)
        elif verb=='restore-resource':
            # The reader-owned phase activation already changed the server.
            # This adapter may only inspect that original control state.
            status=browser_status(self.source.client.request('/runs/'+self.run+'/browser'));need(status['ready'] is True)
        elif verb=='background-resume':
            before=self.adapter._native_feature_observer(self.selector,read_only=True).read(0)
            self.input_begin(dict(kind='lifecycle',operation='lifecycle.background'))
            self.adapter._tablet_web_lifecycle(self.selector,self,'lifecycle.background');self.input_done()
            for attempt in range(41):
                observed=self.adapter._graphics_lifecycle_status(self.selector,owner['binding'])
                if observed['foreground'] is False:break
                need(attempt<40);self.sleep(.1)
            self.input_begin(dict(kind='lifecycle',operation='app.launch'))
            self.adapter._tablet_web_lifecycle(self.selector,self,'app.launch');self.input_done()
            after=self.adapter._native_feature_observer(self.selector,read_only=True).read(0)
            need(after['lifecycle']['launches']==before['lifecycle']['launches']
                and after['lifecycle']['backgrounds']>before['lifecycle']['backgrounds']
                and after['lifecycle']['activations']>before['lifecycle']['activations'])
        else:need(False)

    def act(self,value):
        need(self.role=='primary');call=deepcopy(arguments('feature.'+self.area+'.act',value))
        need(call['runId']==self.run and call['fixtureUrl']==self.fixture_url)
        self.prepare()
        with self.serialized(),self.adapter.existing_input_session(self.selector):
            owner=self.owner();need(owner['phase'] in ('baseline','acting','active'))
            active=self.source.read(owner['phaseSource']);need(active['ticket']==call['ticket'] and active['verb']==call['verb'] and same(active['inputs'],call['inputs']))
            if call['ticket'] in owner['tickets']:
                need(same(owner['call'],call) and owner['phase']=='active');return {'performed':True}
            need(owner['phase'] in ('baseline','active') and len(owner['tickets'])<256)
            self.observation_admission(owner)
            owner.update(phase='acting',call=call,phaseSource=active['status']);owner['tickets'].append(call['ticket']);self.save(owner)
            # One durable intent precedes any ordinary product input. A lost
            # response stays issued; another act cannot repeat it.
            self.runtime(owner);self.deliver(owner,call);self.runtime(owner)
            owner.update(phase='active');self.save(owner)
            return {'performed':True}

    def input_fence(self):
        from adapters.phase_input_fence import PhaseInputFence
        if self.fence is None:
            owner=self
            class Fence(PhaseInputFence):
                def original(inner):
                    owner.lock.assert_held();need(not inner.failed and owner.live_owner is not None
                        and owner.live_owner['phase'] in ('preparing','acting','cleaning'))
                    return owner.live_owner['phaseSource']
            self.fence=Fence(self.source);self.fence.stream_intent=self.input_envelope
        return self.fence

    def input_begin(self,original):
        self.lock.assert_held();need(self.role=='primary' and self.live_owner is not None)
        owner=self.live_owner;fence=self.input_fence();fence.mark()
        need(len(owner['inputs'])<4096)
        if owner['inputs'] and not owner['inputs'][-1]['complete']:
            need(owner['phase']=='cleaning' and owner['inputs'][-1]['ticket']!=fence.anchor['ticket'])
        owner['inputs'].append(dict(ticket=fence.anchor['ticket'],original=deepcopy(original),anchor=deepcopy(fence.anchor),
            complete=False,envelope=None));self.save(owner)

    def input_envelope(self,envelope):
        # Runs under the original controller's OS lock: host journal only.
        self.lock.assert_held();fence=self.input_fence();fence.host_fresh()
        owner=self.live_owner;need(owner is not None and owner['inputs'] and not owner['inputs'][-1]['complete'])
        owner['inputs'][-1]['envelope']=deepcopy(envelope);self.save(owner);fence.host_fresh()

    def input_done(self):
        self.lock.assert_held();owner=self.live_owner
        need(owner is not None and owner['inputs'] and not owner['inputs'][-1]['complete'])
        owner['inputs'][-1]['complete']=True;self.save(owner)

    def tablet_owned(self):need(self.live_owner is not None);return self.live_owner['tabletOwned']
    def tablet_lease(self,value):
        need(type(value) is bool and self.live_owner is not None);self.live_owner['tabletOwned']=value;self.save(self.live_owner)

    def role_state(self):
        value=self.read(self.role_store,self.role)
        if value is None:return dict(sequence=0,native=None,runtime=None,browser=None,lifecycle=None,last=None,quiet=None,retired=None,images=[],publication=None,phase=None)
        exact(value,{'sequence','native','runtime','browser','lifecycle','last','quiet','retired','images','publication','phase'})
        need(integer(value['sequence'],0,1000000000) and type(value['images']) is list and len(value['images'])<=256)
        if value['native'] is not None:
            owner=self.owner();need(owner is not None)
            packet=value['native'];request=dict(schemaVersion=1,commandId=packet['commandId'],action=self.action,runId=self.run,
                fixtureUrl=self.fixture_url,ownerToken=owner['ownerToken'],operation='observe')
            validate_source(packet,request,int(owner['binding']['processIdentity'].split(':')[0]),packet['capturedEpochMs'])
        if value['runtime'] is not None:
            from adapters.native_web_runtime import validate as runtime_packet
            packet=value['runtime'];owner=self.owner();need(owner is not None)
            runtime_packet(packet,dict(schemaVersion=1,commandId=packet['commandId'],action='feature-web-runtime-observe',
                runId=self.run,fixtureUrl=self.fixture_url),int(owner['binding']['processIdentity'].split(':',1)[0]),packet['capturedEpochMs'],require_renderers=True)
        if value['quiet'] is not None:
            from adapters.pico4.browser_quiet import validate as quiet_packet
            owner=self.owner();quiet_packet(value['quiet'],self.run,self.fixture_url,owner['ownerToken'],
                int(owner['binding']['processIdentity'].split(':',1)[0]),retired=True)
        if value['phase'] is not None:
            from feature_journeys.phase_fixture import validate as phase_packet
            packet=value['phase'];phase_packet(packet,run=self.run,area=self.area,request=packet['requestId'],epoch=packet['capturedEpochMs'])
        if value['publication'] is not None:
            exact(value['publication'],{'phase','payload'});need(value['publication']['phase'] in ('issued','accepted') and value['phase'] is not None)
            payload=value['publication']['payload'];exact(payload,{'ticket','actor','actorSequence','capturedEpochMs','facts'})
            need(self.role=='actor' and payload['actor']=='owned-observer' and payload['actorSequence']==value['sequence']
                and value['last'] is not None and payload['capturedEpochMs']==value['last']['capturedEpochMs']
                and payload['ticket']==value['phase']['activations'][-1]['ticket']
                and payload['facts']==projection(self.area,value['last']['state']))
        if value['browser'] is not None:browser_status(value['browser'])
        self.verify_images(value,self.role)
        if value['last'] is not None:result('feature.'+self.area+'.observe',value['last'])
        return value

    def verify_images(self,value,role,*,legacy=False):
        from adapters.pico4.browser_stereo import original_name
        from feature_journeys.stereo_browser_evidence import archive_sources
        owner=self.owner() if value['images'] else None
        need(not value['images'] or owner is not None)
        journals=set();captures=set();pngs=set()
        for image in value['images']:
            exact(image,{'journalId','ticket','phase','metadata'}|({'record'} if legacy else set()))
            identifier(image['journalId']);identifier(image['ticket']);need(image['phase'] in ('planned','saved')
                and image['journalId'] not in journals);journals.add(image['journalId'])
            if image['phase']=='planned':
                need(image['metadata'] is None and (not legacy or image['record'] is None));continue
            name=original_name(self.run,role,image['journalId']);raw=self.metadata(name,image['metadata'])
            cache_key=(role,image['journalId']);cached=None if legacy else self.cached_image(cache_key)
            scope=dict(binding=owner['binding'],runId=self.run,fixtureUrl=self.fixture_url,foreignFixtureUrl=self.foreign_url,
                artifactRoot=str(self.artifact_root),scriptUrl=owner['scriptUrl'],ownerToken=owner['ownerToken'],sceneUrl=self.adapter.scene_url)
            if cached is not None:
                need(same(cached['image'],image) and same(cached['scope'],scope))
                self._original_image_bytes(cached['png'],expected=cached['stamp'])
                key=tuple(cached['capture']);png_name=cached['png']['name']
                need(key not in captures and png_name not in pngs);captures.add(key);pngs.add(png_name)
                continue
            body=json.loads(raw);need((not legacy or same(body,image['record'])) and body['role']==role and body['runId']==self.run)
            rows=unpack(body['payload']);need(len(rows)==1 and rows[0]['phase']=='complete' and rows[0]['ticket']==image['ticket'])
            capture=rows[0]['frame']['capture'];key=(capture['instance'],capture['requestId'])
            need(key not in captures and rows[0]['image']['name'] not in pngs)
            captures.add(key);pngs.add(rows[0]['image']['name'])
            png,stamp=self.original_image(rows[0]['image'])
            original,_state,_facts=archive_sources(raw,png,self.run,image['ticket'],self.adapter.scene_url,role=role)
            need(original['binding']==owner['binding'] and original['journalId']==image['journalId']
                and original['artifactRoot']==str(self.artifact_root)
                and original['scope']==dict(fixtureUrl=self.fixture_url,foreignFixtureUrl=self.foreign_url,
                    ownerToken=owner['ownerToken'],scriptUrl=owner['scriptUrl']))
            if not legacy:
                need(len(self._image_cache)<512)
                cached=dict(image=deepcopy(image),scope=deepcopy(scope),png=deepcopy(rows[0]['image']),stamp=stamp,capture=list(key),
                    facts=deepcopy(_facts),lifecycle=deepcopy(rows[0]['frame']['nativeBefore']['lifecycle']))
                self.image_cache_digests[cache_key]=self.image_digest(cached)
                from adapters.script_journey.history import canonical
                self._image_cache[cache_key]=canonical(cached)
        need(all(key[1] in journals for key in self._image_cache if key[0]==role))

    @property
    def image_cache(self):
        """Inspection copies of immutable, fully admitted original semantics."""
        return {key:self.cached_image(key) for key in self._image_cache}

    def cached_image(self,key):
        raw=self._image_cache.get(key)
        if raw is None:return None
        need(type(raw) is bytes and hashlib.sha256(raw).hexdigest()==self.image_cache_digests[key])
        return json.loads(raw)

    @staticmethod
    def image_digest(value):
        from adapters.chat_journey.source_chunks import json_digest
        return json_digest(value)

    def original_image(self,value,*,expected=None):
        """Read all original PNG bytes; reuse only validated immutable semantics.

        Warm reads still check the complete file stamp and SHA256. A cache hit
        cannot admit new bytes, a replaced inode or a changed original source.
        Cold callers always run the complete common stereo/source validator.
        """
        from adapters.graphics_journey.originals import record
        record(value);need(value['kind']=='image' and value['phase']=='saved')
        return self._original_image_bytes(value,expected=expected)

    def _original_image_bytes(self,value,*,expected=None):
        """Physical/full-byte checks after immutable original semantics validation."""
        from adapters.chat_journey.archive_file import signature
        path=self.artifact_root/value['name'];PrivateFeatureState(path)._parent()
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            first=os.fstat(stream.fileno());original=signature(first)
            need(stat.S_ISREG(first.st_mode) and first.st_nlink==1 and first.st_uid==os.geteuid()
                and stat.S_IMODE(first.st_mode)==0o600 and first.st_size==value['bytes']
                and (first.st_dev,first.st_ino)==(value['file']['device'],value['file']['inode'])
                and signature(path.lstat())==original and (expected is None or original==expected))
            raw=stream.read(value['bytes']+1)
            need(len(raw)==value['bytes'] and hashlib.sha256(raw).hexdigest()==value['sha256']
                and signature(os.fstat(stream.fileno()))==signature(path.lstat())==original)
            return raw,original

    def metadata(self,name,expected=None):
        need(type(name) is str and '/' not in name and '\\' not in name)
        path=self.artifact_root/name;PrivateFeatureState(path)._parent()
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            first=os.fstat(stream.fileno());named=path.lstat()
            def stamp(info):return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)
            need(stamp(first)==stamp(named) and stat.S_ISREG(first.st_mode) and first.st_nlink==1
                and first.st_uid==os.geteuid() and stat.S_IMODE(first.st_mode)==0o600 and first.st_size<=65536)
            raw=stream.read(65537);need(len(raw)==first.st_size and stamp(os.fstat(stream.fileno()))==stamp(path.lstat())==stamp(first))
            tag=dict(device=first.st_dev,inode=first.st_ino,bytes=len(raw),mtimeNs=first.st_mtime_ns,
                ctimeNs=first.st_ctime_ns,sha256=hashlib.sha256(raw).hexdigest())
            if expected is not None:need(same(tag,expected))
            return raw if expected is not None else (raw,tag)

    def image_required(self,phase):
        from feature_journeys.scenarios import SCENARIOS,expand
        from feature_journeys.fixtures import context as fixture_context
        if phase['verb'] in ('baseline','cleanup'):return False
        index=len(phase['status']['activations'])-2;steps=SCENARIOS[self.area]['steps']
        need(0<=index<len(steps));step=steps[index]
        need(step['verb']==phase['verb'] and same(expand(step['inputs'],fixture_context(self.run)),phase['inputs']))
        return bool({'image','changed'}.intersection(step['evidence']))

    def source_history(self,owner):
        from adapters.pico4.browser_history import PicoBrowserHistory
        self.lock.assert_held()
        scope=dict(binding=owner['binding'],ownerToken=owner['ownerToken'],runId=self.run,fixtureUrl=self.fixture_url,
            foreignFixtureUrl=self.foreign_url,artifactRoot=str(self.artifact_root),role=self.role,sceneUrl=self.adapter.scene_url)
        if self.history_cache is None:
            self.history_cache=PicoBrowserHistory(PrivateFeatureState(self.store.path.with_name('pico-tablet-web-'+self.role+'-sources.json')),
                self.lock,scope,self.validate_original_sample)
            self.history_scope=deepcopy(scope)
        need(same(scope,self.history_scope));self.history_cache.verify();return self.history_cache

    def observation_admission(self,owner):
        """Pending original reads/publications cannot authorize another input."""
        state=self.role_state();history=self.source_history(owner);history.matches(state)
        actor=self.read(PrivateFeatureState(self.store.path.with_name('pico-tablet-web-actor.json')),'actor')
        actor_root=PrivateFeatureState(self.store.path.with_name('pico-tablet-web-actor-sources.json')).read()
        if actor is None:need(actor_root is None);return
        need(actor['publication'] is None or actor['publication']['phase']=='accepted')
        if actor_root is None:need(actor['sequence']==0);return
        scope={**history.scope,'role':'actor'}
        exact(actor_root,set(scope)|{'phase','revision','chunks','intent'})
        need(all(same(actor_root[key],value) for key,value in scope.items())
            and actor_root['phase']=='ready' and actor_root['intent'] is None
            and type(actor_root['chunks']) is list and integer(actor_root['revision'],2)
            and actor_root['revision']==2*len(actor_root['chunks']))

    def validate_original_sample(self,frame,previous):
        """Replay complete historical source validation without any target query."""
        from adapters.native_feature_observation import validate as feature_packet
        from adapters.native_web_runtime import validate as runtime_packet,continuity as runtime_advance
        from adapters.normal_script_manager import diagnostic as service_packet
        from feature_journeys.phase_fixture import validate as phase_packet
        exact(frame,{'phaseBefore','phaseAfter','nativeBefore','nativeAfter','native','runtime','browser','diagnostic',
            'scriptUrl','vm','sample','startedHost','startedEpoch','finishedHost','finishedEpoch'})
        # During cold construction the callback precedes cache assignment.
        binding=self.live_owner['binding'];pid=int(binding['processIdentity'].split(':',1)[0])
        epoch=frame['finishedEpoch'];need(integer(epoch,1) and integer(frame['startedEpoch'],1,epoch)
            and number(frame['startedHost'],0,1e15) and number(frame['finishedHost'],frame['startedHost'],frame['startedHost']+10))
        for field in ('phaseBefore','phaseAfter'):
            packet=frame[field];phase_packet(packet,run=self.run,area=self.area,request=packet['requestId'],epoch=packet['capturedEpochMs'])
            need(packet['active']);fresh(packet['capturedEpochMs'],epoch)
        need(same(frame['phaseBefore']['activations'],frame['phaseAfter']['activations']))
        need(frame['scriptUrl'] is None or frame['scriptUrl']==self.live_owner['scriptUrl'])
        if previous is not None and previous['scriptUrl'] is not None:need(frame['scriptUrl']==previous['scriptUrl'])
        for field in ('nativeBefore','nativeAfter'):
            packet=frame[field];feature_packet(packet,packet['requestId'],pid,epoch)
        before,after=frame['nativeBefore'],frame['nativeAfter']
        need(before['instance']==after['instance'] and before['sequence']<after['sequence']
            and before['lifecycle']==after['lifecycle'] and before['capturedEpochMs']<=after['capturedEpochMs'])
        native=frame['native'];request=dict(schemaVersion=1,commandId=native['commandId'],action=self.action,runId=self.run,
            fixtureUrl=self.fixture_url,ownerToken=self.live_owner['ownerToken'],operation='observe')
        validate_source(native,request,pid,epoch)
        runtime=frame['runtime'];runtime_packet(runtime,dict(schemaVersion=1,commandId=runtime['commandId'],
            action='feature-web-runtime-observe',runId=self.run,fixtureUrl=self.fixture_url),pid,epoch,require_renderers=True)
        service_packet(frame['diagnostic'],epoch);browser_status(frame['browser'],None if previous is None else previous['browser'])
        if previous is not None:
            continuity(previous['native'],native);runtime_advance(previous['runtime'],runtime,pid,self.fixture_url)
            need(before['instance']==previous['nativeAfter']['instance'] and before['sequence']>previous['nativeAfter']['sequence']
                and all(after['lifecycle'][key]>=value for key,value in previous['nativeAfter']['lifecycle'].items())
                and frame['diagnostic']['instance']==previous['diagnostic']['instance']
                and frame['diagnostic']['sampleSequence']>previous['diagnostic']['sampleSequence']
                and frame['startedHost']>=previous['finishedHost'])
        measured,resources=measurement(self.run,self.fixture_url,self.foreign_url,native,frame['browser'],runtime,
            frame['diagnostic']['scripts'],frame['scriptUrl'],area=self.area)
        if frame['vm'] is not None:
            from adapters.chat_journey.source_chunks import digest
            exact(frame['vm'],{'scopeSha256','index','sha256'})
            need(frame['scriptUrl']==self.live_owner['scriptUrl'])
            vm=self.vm_reader(self.live_owner);vm.verify();reference=frame['vm'];index=reference['index']
            need(integer(index,0,vm.frame_count-1) and reference['scopeSha256']==digest(vm.scope)
                and reference['sha256']==vm.frame_hash(index))
            from adapters.pico4.browser_vm import join
            _origin,facts=join(vm.frame(index),frame['scriptUrl'],pid,origin=vm.origin)
            if not facts['retired'] and 'script:tablet-web-client' not in resources:resources.append('script:tablet-web-client')
        else:need(frame['scriptUrl'] is None)
        sample=result('feature.'+self.area+'.observe',frame['sample'])
        need(sample['runId']==self.run and sample['state']==measured and sample['resources']==resources
            and sample['lifecycle']==after['lifecycle'])
        if sample['artifacts']:
            from adapters.pico4.browser_stereo import original_name
            need(len(sample['artifacts'])==2)
            artifacts={value['kind']:value for value in sample['artifacts']};need(set(artifacts)=={'image','file'})
            matching=[key for key in self._image_cache if key[0]==self.role
                and original_name(self.run,key[0],key[1])==artifacts['file']['name']]
            need(len(matching)==1);cached=self.cached_image(matching[0]);capture=cached['png']['capture'];facts=cached['facts']
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

    def screenshot(self,owner,ticket,sequence,role,state):
        from adapters.pico4.browser_stereo_source import validate as frame_packet
        journal=uuid.uuid4().hex;image=dict(journalId=journal,ticket=ticket,phase='planned',metadata=None)
        state['images'].append(image);self.write(self.role_store,self.role,state)
        stereo=self.adapter._tablet_web_stereo(self.selector,self,journal,role)
        captured=stereo.acquire(ticket);raw=stereo.image_bytes()
        facts=frame_packet(captured['frame'],raw,self.run,owner['binding'],self.adapter.scene_url)
        metadata,tag=self.metadata(stereo.store.path.name)
        need(same(json.loads(metadata),stereo.disk));image.update(phase='saved',metadata=tag)
        self.write(self.role_store,self.role,state)
        return stereo.artifacts(sequence),facts

    def acquire(self,owner,phase,state,*,after_sequence=0):
        history=self.source_history(owner);history.matches(state)
        start=self.monotonic();need(number(start,0,1e15) and integer(after_sequence) and after_sequence<=state['sequence']
            and all(image['phase']=='saved' for image in state['images']))
        epoch_started=self.source.epoch_ms();need(number(epoch_started,1,1e16))
        history.begin('sample',state['sequence']+1)
        self.runtime(owner)
        vm=None;vm_facts=None
        if owner['scriptUrl'] is not None:
            vm=self.vm_reader(owner);vm_facts=vm.capture()
        native=self.sample_native(owner,state['native'])
        if native['source']['retired']:need(owner['phase']=='cleaned')
        before=self.adapter._native_feature_observer(self.selector,read_only=True).read(0)
        runtime_reader=self.adapter._web_runtime_observer(self.selector,read_only=True);runtime_reader.last=deepcopy(state['runtime'])
        runtime=runtime_reader.read(self.run,self.fixture_url)
        status=browser_status(self.source.client.request('/runs/'+self.run+'/browser'),state['browser'])
        _ui,observe,_binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        diagnostic,_diagnostic_epoch=observe(0);rows=diagnostic['scripts']
        measured,resources=measurement(self.run,self.fixture_url,self.foreign_url,native,status,runtime,rows,owner['scriptUrl'],area=self.area)
        if vm_facts is not None and not vm_facts['retired'] and 'script:tablet-web-client' not in resources:
            resources.append('script:tablet-web-client')
        artifacts=[];sequence=state['sequence']+1
        if measured['open'] and self.image_required(phase):
            need(len(state['images'])<256)
            originals,facts=self.screenshot(owner,phase['ticket'],sequence,self.role,state);artifacts.extend(originals)
            need(facts['state']==measured)
        after=self.adapter._native_feature_observer(self.selector,read_only=True).read(0)
        epoch=self.adapter._world_web_clock(self.selector)
        need(after['instance']==before['instance'] and after['lifecycle']==before['lifecycle']
            and min(before['capturedEpochMs'],native['capturedEpochMs'],runtime['source']['nativeBefore']['capturedEpochMs'])>=phase['afterEpochMs'])
        for captured in (native['capturedEpochMs'],runtime['source']['nativeBefore']['capturedEpochMs'],before['capturedEpochMs'],diagnostic['sampleEpochMs']):fresh(captured,epoch)
        need(self.monotonic()-start<10 and self.source.epoch_ms()-phase['afterEpochMs']>=0)
        if state['lifecycle'] is not None:need(all(after['lifecycle'][k]>=v for k,v in state['lifecycle'].items()))
        captured=facts['earliestEpochMs'] if artifacts else after['capturedEpochMs']
        value=result('feature.'+self.area+'.observe',dict(schemaVersion=1,contractVersion=CONTRACT_VERSION,runId=self.run,sequence=sequence,
            capturedEpochMs=captured,state=measured,artifacts=artifacts,resources=resources,lifecycle=after['lifecycle']))
        end=self.source.read();need(end['ticket']==phase['ticket'] and end['verb']==phase['verb'] and same(end['inputs'],phase['inputs']))
        state.update(sequence=sequence,native=native,runtime=runtime,browser=status,lifecycle=after['lifecycle'],last=value,phase=deepcopy(phase['status']),publication=None)
        if measured==dict(surface=self.surface,text='',page='none',bridgeMessages=0,bridgeEchoes=0,attemptedMessages=0,documentLoads=0,
                httpStatus=0,origin='none',documentKind='none',inlineLeases=0,deferredMessages=0,error='none',focused=False,open=False) and not resources and native['source']['retired']:
            from adapters.pico4.browser_quiet import append as quiet_append
            state['quiet']=quiet_append(state['quiet'],native,runtime,self.monotonic(),self.run,self.fixture_url,owner['ownerToken'],
                int(owner['binding']['processIdentity'].split(':',1)[0]),retired=True)
        else:state['quiet']=None
        # Copies and every host CAS precede the final original phase/guard and
        # both clocks. A newly fetched phase cannot renew an old product sample.
        candidate=deepcopy(value)
        epochs=[native['capturedEpochMs'],runtime['capturedEpochMs'],before['capturedEpochMs'],
            after['capturedEpochMs'],diagnostic['sampleEpochMs'],captured]
        epochs.extend(runtime['source'][key]['capturedEpochMs'] for key in ('nativeBefore','java','nativeAfter'))
        if vm is not None:
            frame=vm.frame(-1);epochs.extend((frame['objectsBefore']['source']['capturedEpochMs'],
                frame['scripts']['capturedEpochMs'],frame['objectsAfter']['source']['capturedEpochMs']))
        self.sample_fence=(deepcopy(phase),start,epoch_started,epochs)
        guard();self.write(self.role_store,self.role,state)
        self.verify_images(state,self.role)
        finished=self.completion_fence(owner)
        from adapters.chat_journey.source_chunks import digest
        vm_reference=None if vm is None else dict(scopeSha256=digest(vm.scope),index=vm.frame_count-1,sha256=vm.frame_hash(-1))
        history.finish(dict(phaseBefore=deepcopy(phase['status']),phaseAfter=finished['phase'],nativeBefore=before,nativeAfter=after,
            native=native,runtime=runtime,browser=status,diagnostic=diagnostic,scriptUrl=owner['scriptUrl'],vm=vm_reference,
            sample=candidate,startedHost=start,startedEpoch=epoch_started,finishedHost=finished['host'],finishedEpoch=finished['epoch']))
        self.completion_fence(owner,originals=lambda:self.sample_originals(state,history))
        return candidate

    def sample_originals(self,state,history):
        """The last target guard cannot hide changed host originals or parents."""
        parent=deepcopy(self.originals[self.store.path]);role=deepcopy(self.originals[self.role_store.path])
        need(same(self.store.read(),parent) and same(self.role_store.read(),role));history.matches(state)
        self.verify_images(state,self.role)
        need(same(self.store.read(),parent) and same(self.role_store.read(),role));history.matches(state)

    def completion_fence(self,owner,*,originals=None):
        phase,start,epoch_started,epochs=self.sample_fence
        end=self.source.read(phase['status'])
        need(same(end['status']['activations'],phase['status']['activations']))
        self.runtime(owner)
        if originals is not None:need(callable(originals));originals()
        measured=self.monotonic();epoch=self.source.epoch_ms();finished=self.monotonic()
        need(number(measured,start,start+10) and number(finished,measured,start+10)
            and number(epoch,epoch_started,1e16))
        for captured in [*epochs,end['status']['capturedEpochMs']]:
            fresh(captured,epoch)
            need(max(epoch-captured,epoch_started-captured+math.ceil((finished-start)*1000),
                epoch-captured+math.ceil((finished-measured)*1000))<=1500)
        return dict(phase=deepcopy(end['status']),host=finished,epoch=epoch)

    def observe(self,value):
        call=arguments('feature.'+self.area+'.observe',value);need(self.role=='primary' and call['runId']==self.run)
        self.prepare()
        with self.serialized(),self.adapter.existing_input_session(self.selector):
            owner=self.owner();phase=self.phase(owner);state=self.role_state()
            return self.acquire(owner,phase,state,after_sequence=call['afterSequence'])

    def publish(self):
        need(self.role=='actor')
        with self.serialized(),self.adapter.existing_input_session(self.selector):
            owner=self.owner();need(owner is not None);state=self.role_state()
            need(state['publication'] is None or state['publication']['phase']=='accepted')
            try:phase=self.phase(owner)
            except PhaseRetired as retired:
                need(owner['phase']=='cleaned' and state['quiet'] is not None and state['quiet']['complete'] and state['native']['source']['retired'])
                native=self.sample_native(owner,state['native']);need(native['source']['retired'])
                state.update(native=native,retired=retired.status);self.write(self.role_store,self.role,state);raise
            value=self.acquire(owner,phase,state)
            payload=dict(ticket=phase['ticket'],actor='owned-observer',actorSequence=value['sequence'],capturedEpochMs=value['capturedEpochMs'],facts=projection(self.area,value['state']))
            history=self.source_history(owner);history.begin('publication-intent',value['sequence'])
            state['publication']=dict(phase='issued',payload=deepcopy(payload));self.write(self.role_store,self.role,state)
            history.finish(dict(payload=payload,ack=None))
            self.completion_fence(owner,originals=lambda:self.sample_originals(state,history))
            ack=self.source.client.request('/runs/'+self.run+'/samples',payload)
            exact(ack,set())
            history.begin('publication-accepted',value['sequence'])
            state['publication']['phase']='accepted';self.write(self.role_store,self.role,state)
            history.finish(dict(payload=payload,ack=ack))
            self.completion_fence(owner,originals=lambda:self.sample_originals(state,history))
            return value

    def close_source(self,owner):
        if owner['tabletOwned']:self.adapter._tablet_web_close(self.selector,self)
        if self.manager_store().read() is None:return
        manager=self.manager()
        if manager.state['loadAttempted']:
            manager.close_dialog();manager.open();manager.stop_source(owner['scriptUrl'])
        manager.close()
        deferred=self.sample_native(owner)['source']['deferred']
        if deferred['armed']:self.source_control(owner,'cancel-held')
        if deferred['pending']:self.source_control(owner,'deliver-held')

    def cleanup_window(self,owner):
        from adapters.pico4.browser_quiet_journal import PicoBrowserQuietJournal
        self.lock.assert_held()
        scope=dict(runId=self.run,fixtureUrl=self.fixture_url,ownerToken=owner['ownerToken'],binding=owner['binding'])
        if self.quiet_cache is None:
            self.quiet_cache=PicoBrowserQuietJournal(PrivateFeatureState(self.store.path.with_name('pico-tablet-web-cleanup-quiet.json')),
                self.lock,self.run,self.fixture_url,owner['ownerToken'],owner['binding'],owner['cleanupProof'])
            self.quiet_cache_scope=deepcopy(scope)
        journal=self.quiet_cache;need(same(scope,self.quiet_cache_scope));journal.verify()
        reference=journal.value if journal.legacy else (None if journal.disk is None else journal.reference())
        need(same(owner['cleanupProof'],reference));return journal

    def cleanup(self,value):
        call=arguments('feature.'+self.area+'.cleanup',value);need(self.role=='primary' and call['runId']==self.run)
        with self.serialized(),self.adapter.existing_input_session(self.selector):
            owner=self.owner()
            if owner is None:return {'performed':True} # No reserved scope or product input was ever issued.
            phase=self.source.read(owner['phaseSource']);need(phase['verb']=='cleanup')
            if owner['phase']=='cleaned':
                if owner['scriptUrl'] is not None:
                    vm=self.vm_reader(owner);need(vm.capture()['retired'] and vm.quiet(phase['afterEpochMs']))
                return {'performed':True}
            owner.update(phase='cleaning',phaseSource=phase['status']);self.save(owner);self.close_source(owner)
            quiet=self.cleanup_window(owner)
            if quiet.legacy:
                quiet.migrate();owner['cleanupProof']=quiet.reference();self.save(owner)
            vm=None if owner['scriptUrl'] is None else self.vm_reader(owner)
            start=previous=self.monotonic();runtime_reader=self.adapter._web_runtime_observer(self.selector,read_only=True)
            if quiet.value is not None:runtime_reader.last=deepcopy(quiet.value['frames'][-1]['runtime'])
            for attempt in range(81):
                self.runtime(owner);self.source.read(owner['phaseSource'])
                sample_start=self.monotonic();sample_epoch=self.source.epoch_ms()
                quiet.begin()
                vm_quiet=True
                if vm is not None:vm.capture();vm_quiet=vm.quiet(phase['afterEpochMs'])
                floor=None if quiet.value is None else quiet.value['frames'][-1]['browser']
                native=self.sample_native(owner,floor);runtime=runtime_reader.read(self.run,self.fixture_url)
                now=self.monotonic();need(number(now,previous,start+20));previous=now
                owner['cleanupProof']=quiet.finish(native,runtime,now)
                self.save(owner)
                epochs=[native['capturedEpochMs'],runtime['capturedEpochMs']]
                epochs.extend(runtime['source'][key]['capturedEpochMs'] for key in ('nativeBefore','java','nativeAfter'))
                if vm is not None:
                    original=vm.frame(-1);epochs.extend((original['objectsBefore']['source']['capturedEpochMs'],
                        original['scripts']['capturedEpochMs'],original['objectsAfter']['source']['capturedEpochMs']))
                self.sample_fence=(deepcopy(phase),sample_start,sample_epoch,epochs);self.completion_fence(owner)
                if quiet.value['complete'] and vm_quiet:break
                need(attempt<80);self.sleep(.1)
            receipt=self.source_control(owner,'retire');need(receipt['source']=={'retired':True})
            owner.update(phase='cleaned');self.save(owner)
            return {'performed':True}

    def verify_retirement(self,plan):
        """Every retry obtains a new original empty native/Java/service window."""
        original=unpack(plan['owner']['payload'])[0]
        self.runtime(original);start=previous=self.monotonic();window=None
        runtime_reader=self.adapter._web_runtime_observer(self.selector,read_only=True)
        from adapters.pico4.browser_quiet import append as quiet_append
        for attempt in range(81):
            native=self.sample_native(original,None if window is None else window['frames'][-1]['browser'])
            runtime=runtime_reader.read(self.run,self.fixture_url)
            _ui,observe,_binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
            diagnostic,_epoch=observe(0);url=original['scriptUrl']
            need(not any(row['url']==url or url is not None and row['url'].rsplit('/',1)[-1]==url.rsplit('/',1)[-1] for row in diagnostic['scripts']))
            guard();now=self.monotonic();need(number(now,previous,start+15));previous=now
            window=quiet_append(window,native,runtime,now,self.run,self.fixture_url,original['ownerToken'],
                int(original['binding']['processIdentity'].split(':',1)[0]),retired=True)
            if window['complete']:return dict(quiet=window,diagnostic=diagnostic)
            need(attempt<80);self.sleep(.1)
        raise NativeUIError('Original Tablet Web retirement did not remain empty')

    def finalize(self):
        # This private composition is deliberately unavailable as a complete
        # feature. Current browser/renderer emptiness does not prove original
        # Script VM destruction or fresh absence of every retired capture.
        # Keep all original role/owner/metadata journals for that next join.
        need(self.role=='primary')
        raise NativeUIError('Original browser VM and capture finalization are not integrated; ownership is retained')


def re_script(value):
    import re
    return re.fullmatch('[0-9a-f]{32}/client\\.js',value) is not None
