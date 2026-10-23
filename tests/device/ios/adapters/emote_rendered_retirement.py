"""Separate original native-and-rendered cleanup journal; no live acquisition."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from io import BytesIO
from PIL import Image,ImageChops,ImageStat
from adapters.native_feature_observation import exact,need
from adapters.original_marker_restoration_image import restored
from adapters.script_feature.history import pack,unpack,same
from ios.adapters.emote_marker_scope import IOSEmoteMarkerScope
from ios.adapters.emote_native_prefix import follow
from ios.adapters.emote_restoration_frames import IOSEmoteRestorationFrames
from ios.adapters.emote_retirement import IOSEmoteRetirement,Frozen

VERSION=1


def world_pixels(first,last,old_raw,new_raw):
    """Conservative whole-target restoration; unchanged real camera required."""
    a,b=(Image.open(BytesIO(raw)).convert('RGB') for raw in (old_raw,new_raw))
    need(a.size==b.size and list(a.size)==first['capture']['source']['targetExtent']==last['capture']['source']['targetExtent']
        and same(first['capture']['source']['renderTrace']['recordedView'],last['capture']['source']['renderTrace']['recordedView']))
    delta=ImageChops.difference(a,b);red,green,blue=delta.split();maximum=ImageChops.lighter(ImageChops.lighter(red,green),blue)
    changed=sum(maximum.histogram()[11:]);mean=sum(ImageStat.Stat(delta).mean)/3
    need(changed/(a.width*a.height)<=.001 and mean<=.5)
    return dict(changedPixels=changed,pixels=a.width*a.height,meanChannelDelta=mean)


class IOSEmoteRenderedRetirement(IOSEmoteRetirement):
    def __init__(self,store,native,frames,*,historical=False):
        need(isinstance(native,IOSEmoteRetirement) and not isinstance(native,IOSEmoteRenderedRetirement)
            and isinstance(frames,IOSEmoteRestorationFrames) and same(native.binding,frames.binding)
            and native.run==frames.run and native.role==frames.role and native.root==frames.root)
        self.native_owner,self.frames_owner=native,frames
        super().__init__(store,native.root,native.binding,native.primary_binding,native.run,native.role,native.fixture_url,
            native.phase_instance,native.lock,native.primary_lock,native.policy,native.paths,native.guard,historical=historical)

    def envelope(self,state):
        value=super().envelope(state);del value['iosEmoteRetirementVersion']
        value['iosEmoteRenderedRetirementVersion']=self.FORMAT_VERSION;value['framesPath']=str(self.frames_owner.store.path)
        return value

    def record_store(self,index):
        value=super().record_store(index)
        return type(value)(value.path.with_name(value.path.name.replace('emote-retirement-','emote-rendered-retirement-',1)))

    def wrap(self,original):
        exact(original,{'nativeReference','frames','initialReference','currentReference'})
        return dict(iosEmoteRenderedRetirementOriginalVersion=self.FORMAT_VERSION,runId=self.run,role=self.role,binding=self.binding,
            primaryBinding=self.primary_binding,phaseInstance=self.phase_instance,fixtureUrl=self.fixture_url,payload=pack([original]))

    def original(self,reference):
        from adapters.native_clock_join import digest
        exact(reference,{'index','sha256'});value=self.record_store(reference['index']).read()
        need(value is not None and digest(value)==reference['sha256'])
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.wrap(rows[0])));return deepcopy(rows[0])

    def decode(self,value):
        exact(value,set(self.envelope(dict(records=[],abandoned=[],pending=None))))
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'records','abandoned','pending'})
        need(all(type(state[key]) is list for key in ('records','abandoned')))
        used=state['records']+state['abandoned'];need(len(used)<=128);indices=[]
        for key in ('records','abandoned'):
            previous=0
            for ref in state[key]:
                self.original(ref);need(ref['index']>previous);previous=ref['index'];indices.append(ref['index'])
                if key=='records':self.derive(ref)
        need(sorted(indices)==list(range(1,len(used)+1)))
        pending=state['pending']
        if pending is not None:
            exact(pending,{'index','value'});need(pending['index']==len(used)+1 and pending['index']<=128)
            candidate=pending['value'];need(same(candidate,self.wrap(unpack(candidate['payload'])[0])))
            existing=self.record_store(pending['index']).read();need(existing is None or same(existing,candidate))
        elif not self.historical and len(used)<128:need(self.record_store(len(used)+1).read() is None)
        return deepcopy(state)

    def derive(self,reference):
        self.lock.assert_held();self.primary_lock.assert_held();original=self.original(reference)
        need(original['nativeReference'] in self.native_owner.state['records'])
        native_original=self.native_owner.original(original['nativeReference']);derived=self.native_owner.derive(original['nativeReference'])
        frame_store=Frozen(self.frames_owner.store.path,original['frames'])
        frames=IOSEmoteRestorationFrames.archive(original['frames'],store=frame_store,root=self.root,binding=self.binding,
            run=self.run,role=self.role,lock=self.lock)
        need(frames.state['pending'] is None)
        initial,current=original['initialReference'],original['currentReference']
        need(initial in frames.state['records'] and frames.state['records'] and current==frames.state['records'][-1])
        first,old_raw=frames.frame(initial);last,new_raw=frames.frame(current)
        need(frames.original(initial)['kind']=='initial' and frames.original(current)['kind']=='cleanup')
        scope=self.Marker.archive(native_original['scope'],root=self.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock)
        baseline=scope.frames[scope.state['baseline']-1]
        need(first['clockJoin']['hostAfterMonotonic']<=baseline['clockJoin']['hostBeforeMonotonic']
            and first['clockJoin']['hostAfterEpochMs']<=baseline['clockJoin']['hostBeforeEpochMs'])
        follow(first['clockJoin']['nativeAfter'],baseline['clockJoin']['nativeBefore'])
        from ios.adapters.emote_marker_entities import IOSEmoteMarkerEntities
        entities=IOSEmoteMarkerEntities.archive(native_original['entities'],store=Frozen(self.paths['entities'],native_original['entities']),
            root=self.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock)
        closure=entities.closed(scope);barrier=entities.latest()['clockJoin']['nativeAfter']
        if native_original['fileReceipts'] is not None:
            from ios.adapters.emote_file_receipts import IOSEmoteFileReceipts
            files=IOSEmoteFileReceipts.archive(native_original['fileReceipts'],store=Frozen(self.paths['files'],native_original['fileReceipts']),
                root=self.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock)
            barrier=files.original(files.state['records'][-1])['clockJoin']['nativeAfter']
        follow(barrier,last['clockJoin']['nativeBefore'])
        if scope.state['admission'] is not None:
            admitted=scope.frames[scope.state['admissionFrame']-1]['world']
            restored(frames,initial,current,admitted,scope.state['admission']['marker']['id'],after_native=barrier)
        else:
            need(closure['kind'] in ('unloaded','not-called','null-return'))
            c=frames.components;c.body_preserved(first['worldAfter'],last['worldBefore']);c.view_preserved(first['worldAfter'],last['worldBefore'])
            need(same(c.actual_domain(first['worldAfter']),c.actual_domain(last['worldBefore']))
                and same(first['worldAfter']['source']['tree']['entities'],last['worldBefore']['source']['tree']['entities']))
        sources,peers,decoder=self.native_owner.owners(native_original)
        if self.role=='primary':source=decoder.source(native_original['observation']['source'])
        else:source=decoder.retained(peers,native_original['observation']['peerAfter'])['peer']
        quiet_first=scope.frames[scope.state['quiet'][0]-1]['clockJoin']['nativeAfter']
        calls=quiet_first['animation']['history']['callSequence']
        for packet in (barrier,last['clockJoin']['nativeBefore'],last['clockJoin']['nativeAfter'],
                       source['clockJoin']['nativeBefore'],source['clockJoin']['nativeAfter']):
            need(packet['animation']['history']['callSequence']==calls and packet['animation']['overrideActive'] is False)
        follow(last['clockJoin']['nativeAfter'],source['clockJoin']['nativeBefore'])
        need(last['clockJoin']['hostAfterMonotonic']<=derived['acquisition']['hostBeforeMonotonic']
            and last['clockJoin']['hostAfterEpochMs']<=derived['acquisition']['hostBeforeEpochMs'])
        # Whole world-target pixels include the former avatar pose as well as
        # the marker. A changing uncontrolled scene cannot qualify this test.
        world_pixels(first,last,old_raw,new_raw)
        derived['retirement']['originalSha256']=reference['sha256']
        derived['retirement']['provenance']=dict(version=1,namespace='ios-emote-rendered-retirement-original',
            reference=deepcopy(reference),originalSha256=reference['sha256'])
        return derived
