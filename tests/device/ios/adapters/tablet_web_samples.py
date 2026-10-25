"""Whole original Tablet WDA screenshots with actual page authority and raw WAL.

The same unchanged WDA GET returns its original bytes. An explicit transport
wrapper preserves safe PNG bytes before later native-clock/DOM interpretation.
Every failed or partial file stays owned; no unknown screenshot GET is replayed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import os
from pathlib import Path
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import OriginalFrameStore,MAX_FRAMES
from adapters.original_packet_segments import CHUNK_BYTES
from feature_journeys.contract import identifier
from adapters.operation_transport_guard import scope as transport_scope
from adapters.script_feature.history import same,pack,unpack,canonical
from adapters.original_file_reads import record as original_read
from ios.adapters.tablet_web_images import IOSTabletWebImages,pixels,LIMIT
from ios.adapters.tablet_web_screen_archive import TabletWebScreenArchive,raw_original,with_capture
from ios.adapters.tablet_web_image_measurements import compose,frame as page_frame

VERSION=1


class TabletWebSamples:
    def __init__(self,runtime,root,policy,*,historical=False):
        self.runtime=runtime;source=runtime.observer.source
        self.source,self.binding,self.run,self.role,self.lock=source,source.binding,source.run,source.role,source.lock
        self.root=Path(root);need(self.root.is_absolute() and self.root.resolve()==self.root and self.root.is_dir())
        self.policy=deepcopy(policy);exact(policy,{'source','marker','subject'});need(policy['source']=='native-screen')
        self.historical=historical;self.started=self.last=None;self.failed=False
        self.store=PrivateFeatureState(source.root/('tabletweb-screen-samples-'+self.run+'-'+self.role+'.json'));self.saved=self.store.read()
        if self.saved is None:self.state=dict(records=[],pending=None,original=None,nextRaw=1);self.save()
        else:
            exact(self.saved,{'tabletWebSamplesVersion','binding','runId','role','artifactRoot','policy','payload'})
            need(type(self.saved['tabletWebSamplesVersion']) is int and self.saved['tabletWebSamplesVersion']==VERSION
                and same(self.saved['binding'],self.binding) and self.saved['runId']==self.run and self.saved['role']==self.role
                and self.saved['artifactRoot']==str(self.root) and same(self.saved['policy'],self.policy))
            rows=unpack(self.saved['payload']);need(len(rows)==1);self.state=rows[0]
        self.originals=OriginalFrameStore(self.root,self.binding,self.run,self.role,self.file_guard,self.intent,
            namespace='tabletweb-screen-samples',schema_prefix='tabletWebScreenSample',monotonic=source.monotonic)
        self.raw=TabletWebScreenArchive(self.root,self.binding,self.run,self.role,self.file_guard,self.raw_intent,monotonic=source.monotonic)
        self.decode()
    def live(self):need(not self.historical);self.source.bound()
    def file_guard(self):
        if not self.historical:self.live()
        return True
    def save(self):
        self.live();value=dict(tabletWebSamplesVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,
            artifactRoot=str(self.root),policy=self.policy,payload=pack([self.state]))
        self.store.write(value,self.saved);self.saved=deepcopy(value)
    def intent(self,kind,value):
        need(kind=='original' and self.state['pending'] is not None);self.state['original']=deepcopy(value);self.save()
    def raw_intent(self,value):
        row=self.state['pending'];need(row is not None and row['raw'] is not None);row['archive']=deepcopy(value)
        self.state['nextRaw']=value['first']+sum(max(1,(part['bytes']+CHUNK_BYTES-1)//CHUNK_BYTES) for part in value['parts']);self.save()
    def clock(self):
        now=self.source.monotonic()
        if self.failed or not number(now,0,1e15) or self.last is not None and now<self.last or self.started is not None and now-self.started>=1.5:
            self.failed=True;need(False)
        self.last=now;return True
    def screen(self,client):
        return IOSTabletWebImages(PrivateFeatureState(self.source.root/('tabletweb-screen-owner-'+self.run+'-'+self.role+'.json')),
            self.root,self.binding,self.run,self.role,0,client,self.runtime.native_clock,self.source.guard,source_lock=self.lock,
            epoch_ms=self.source.epoch_ms,monotonic=self.source.monotonic)
    def record(self,row,index):
        exact(row,{'tabletWebScreenSampleVersion','index','ticket','status','before','after','png','raw','archive'})
        need(type(row['tabletWebScreenSampleVersion']) is int and row['tabletWebScreenSampleVersion']==VERSION
            and type(row['index']) is int and row['index']==index and row['status'] in ('acquiring','returned','failed'))
        identifier(row['ticket'])
        for name in ('before','after'):
            if row[name] is not None:self.runtime.validate_tail_source(row[name])
        if row['raw'] is not None:
            raw_original(row['raw']);need(row['raw']['sessionId']==self.binding['sessionId'] and str(row['raw']['processId'])==self.binding['processIdentity'])
        if row['archive'] is not None:
            self.raw.parent(row['archive']);need(same(row['raw'],row['archive']['raw']))
            # Actual partial fragments remain inspectable, never a PNG verdict.
            self.raw.inspect(row['archive'])
        if row['status']=='returned':
            need(row['before'] is not None and row['after'] is not None and row['png'] is not None
                and row['raw'] is not None and row['archive'] is not None and row['archive']['complete'])
            with_capture(row['raw'],row['png']['capture']);need(row['png']['nonce']==row['raw']['requestId'][4:] and row['png']['phase']=='saved')
            png=row['png'];exact(png,{'nonce','name','ticket','phase','file','capture'});identifier(png['nonce'])
            exact(png['file'],{'device','inode'})
            need(png['ticket']==row['ticket'] and png['name']=='tablet-web-'+self.run+'-'+self.role+'-0-'+png['nonce']+'.png'
                and integer(png['file']['device'],0,2**64-1) and integer(png['file']['inode'],1,2**64-1))
        return row
    def decode(self):
        exact(self.state,{'records','pending','original','nextRaw'})
        need(type(self.state['records']) is list and len(self.state['records'])<=32 and integer(self.state['nextRaw'],1,MAX_FRAMES+1))
        first=1
        for index,reference in enumerate(self.state['records'],1):
            full=self.originals.expand(reference);need(full['index']==index);row=self.record(self.originals.read(full),index)
            if row['archive'] is not None:
                need(row['archive']['first']==first)
                first+=sum(max(1,(part['bytes']+CHUNK_BYTES-1)//CHUNK_BYTES) for part in row['archive']['parts'])
        row=self.state['pending']
        if row is not None:
            self.record(row,len(self.state['records'])+1)
            if row['archive'] is not None:
                need(row['archive']['first']==first)
                first+=sum(max(1,(part['bytes']+CHUNK_BYTES-1)//CHUNK_BYTES) for part in row['archive']['parts'])
        need(self.state['nextRaw']==first)
        if self.state['original'] is not None:
            need(row is not None and self.state['original']['index']==len(self.state['records'])+1)
            self.pending_original()
    def pending_original(self):
        """Original opened prefix only; no interrupted write is relabelled."""
        reference=self.originals.original(self.state['original']);row=self.state['pending'];need(row is not None)
        expected=canonical(dict(**{self.originals.key('FrameVersion'):1},kind=self.originals.kind,binding=self.binding,
            runId=self.run,role=self.role,index=reference['index'],frame=row))
        need(len(expected)==reference['bytes'] and hashlib.sha256(expected).hexdigest()==reference['sha256'])
        path=self.originals.path(reference)
        if reference['phase']=='planned':need(not os.path.lexists(path));return None
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            self.originals.file(path,stream.fileno(),reference);before=os.fstat(stream.fileno());raw=stream.read(reference['bytes']+1)
            self.originals.file(path,stream.fileno(),reference);after=os.fstat(stream.fileno())
        need((before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_size,after.st_mtime_ns,after.st_ctime_ns)
            and len(raw)<=len(expected) and expected.startswith(raw))
        complete=raw==expected;need(reference['phase']!='saved' or complete)
        original_read(path)
        if complete:need(same(self.originals.read(reference),row))
        return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),complete=complete)
    def read(self,reference,*,previous=None,changed=False):
        full=self.originals.expand(reference);index=full['index'];need(1<=index<=len(self.state['records']) and same(reference,self.state['records'][index-1]))
        row=self.record(self.originals.read(full),index);need(row['status']=='returned')
        raw=self.raw.read(row['archive']);before=self.runtime.validate_tail_source(row['before']);after=self.runtime.validate_tail_source(row['after'])
        measured,subject=compose(self.run,row['ticket'],self.binding,before,after,row['png']['capture'],raw,self.policy,previous=previous,changed=changed)
        return dict(row=row,raw=raw,measured=measured,subject=subject)
    def artifact(self,reference,sequence,*,previous=None,changed=False):
        """Return a public name only after original pixels and page authority.

        The existing original screen filename is retained. An exported byte
        read below still replays the whole original sample, including the
        actual page/source bracket; a caller cannot select an arbitrary file.
        """
        need(integer(sequence,1));value=self.read(reference,previous=previous,changed=changed);row=value['row']
        return dict(kind='image',name=row['png']['name'],sequence=sequence,
            capturedEpochMs=row['png']['capture']['hostBeginEpochMs'],ticket=row['ticket'],source='native-screen')
    def export(self,name):
        need(type(name) is str and '/' not in name and '\\' not in name)
        matches=[]
        for index,reference in enumerate(self.state['records'],1):
            row=self.record(self.originals.read(self.originals.expand(reference)),index)
            if row['status']=='returned' and row['png']['name']==name:matches.append(reference)
        need(len(matches)==1)
        return self.read(matches[0])['raw']
    def cleanup_files(self):
        """Retire only exact screen-file inodes, preserving immutable bytes.

        This is host-file ownership cleanup, not UIKit/view/callback death.
        Failed captures and partially written raw fragments remain recorded.
        The existing owner performs its own exact inode check and observes
        path absence before marking each file removed.
        """
        self.live();self.decode()
        def forbidden(*_args,**_kwargs):need(False)
        from types import SimpleNamespace
        owner=self.screen(SimpleNamespace(call=forbidden))
        need(owner.cleanup());owner._load()
        need(all(row['phase']=='removed' for row in owner.rows))
        return deepcopy(owner.state)
    def files_absent(self):
        """Read-only exact original screen-owner grammar and path absence.

        The neutral decoder is used only locally. No current/native clock,
        capture client or writable screen owner is returned to the caller.
        Immutable fragment originals remain owned by the final archive.
        """
        self.lock.assert_held();self.decode()
        owner=object.__new__(IOSTabletWebImages)
        owner.namespace,owner.version_key='tablet-web','tabletWebScreenImagesVersion'
        owner.store=PrivateFeatureState(self.source.root/('tabletweb-screen-owner-'+self.run+'-'+self.role+'.json'))
        owner.root,owner.binding,owner.run,owner.role,owner.stage=self.root,self.binding,self.run,self.role,0
        owner.lock,owner.guard=self.lock,self.file_guard;owner._load()
        need(all(row['phase']=='removed' for row in owner.rows))
        for row in owner.rows:
            try:owner._path(row).lstat()
            except FileNotFoundError:pass
            else:need(False)
        for index,reference in enumerate(self.state['records'],1):
            sample=self.record(self.originals.read(self.originals.expand(reference)),index)
            if sample['status']=='returned':
                matches=[row for row in owner.rows if row['nonce']==sample['png']['nonce']]
                need(len(matches)==1 and all(same(matches[0][key],sample['png'][key]) for key in sample['png'] if key!='phase'))
                self.read(reference)
        return deepcopy(owner.state)
    def capture(self,ticket,*,before=None):
        self.live();self.decode();need(self.state['pending'] is self.state['original'] is None and len(self.state['records'])<32)
        self.started=self.source.monotonic();self.last=self.started;self.failed=False
        admitted_before=None
        if before is not None:
            # Reuse only the genuine current complete original. A reference
            # from an older frame, unknown/new child query or changed custody
            # may not save a source acquisition or acquire a screenshot.
            admitted_before=self.runtime.validate_tail_source(before)
            source=self.source;source.history()
            need(not source.blocked and source.state['pending'] is source.state['intent'] is source.state['appPending'] is source.state['appIntent'] is None
                and same(source.store.read(),source.saved) and same(source.saved,source.state)
                and source.state['records'] and same(before['observation']['reference'],source.state['records'][-1])
                and same(admitted_before['row']['apps'],source.state['apps']))
            for part in admitted_before['row']['components']:
                child=source.children[part['component']]
                need(same(child.store.read(),child.saved) and same(child.saved,child.state)
                    and not child.blocked and child.state['pending'] is child.state['recordIntent'] is None
                    and child.state['records'] and same(part['reference'],child.state['records'][-1]))
            self.started=admitted_before['row']['clockJoin']['hostBeforeMonotonic']
            self.clock()
        row=dict(tabletWebScreenSampleVersion=VERSION,index=len(self.state['records'])+1,ticket=ticket,status='acquiring',before=None,after=None,png=None,raw=None,archive=None)
        self.state['pending']=row;self.save();outer=self
        def capture_clock():
            outer.clock()
            if admitted_before is not None:
                # No I/O: keep this original floor through serialization and
                # the real final WebDriver/native send guards as well.
                clock=admitted_before['row']['clockJoin'];epoch=outer.source.epoch_ms();mono=outer.source.monotonic()
                need(clock['hostAfterEpochMs']<=epoch<clock['hostBeforeEpochMs']+1500
                    and clock['hostAfterMonotonic']<=mono<clock['hostBeforeMonotonic']+1.5
                    and abs(epoch-clock['hostBeforeEpochMs']-(mono-clock['hostBeforeMonotonic'])*1000)<=250)
        class ScreenTransport:
            def call(self,method,path,body=None):
                need(method=='GET' and path=='/session/'+outer.binding['sessionId']+'/screenshot' and body is None)
                outer.live();capture_clock()
                result=outer.runtime.client.call(method,path,body)
                need(type(result) is str and len(result)<=4*((LIMIT+2)//3));raw=base64.b64decode(result,validate=True);extent=pixels(raw)
                actual=owner.rows[-1];need(actual['phase']=='opened' and actual['ticket']==ticket)
                receipt=dict(nativeScreenRawVersion=1,requestId='ios-'+actual['nonce'],source='native-screen',transport='webdriveragent-original-png',
                    sessionId=outer.binding['sessionId'],processId=int(outer.binding['processIdentity']),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),extent=extent)
                raw_original(receipt,raw);row['raw']=receipt;outer.save()
                first=outer.state['nextRaw']
                outer.raw.write(receipt,raw,first)
                outer.clock();return result
        owner=self.screen(ScreenTransport())
        try:
            with transport_scope(capture_clock):
                row['before']=self.runtime.tail_source() if before is None else deepcopy(before);self.save()
                # Admission of the genuine controlled WK page precedes the
                # screenshot GET. A login sheet/unavailable/foreign page may
                # not become a new private screenshot merely because a later
                # pixel or document comparison would reject it.
                page_frame(self.runtime.validate_tail_source(row['before']),self.binding);self.clock()
                row['png'],_raw=owner.capture(ticket);self.save()
                row['after']=self.runtime.tail_source();self.save();self.clock()
                row['status']='returned';self.record(row,row['index']);reference=self.originals.write(row['index'],deepcopy(row))
                self.state['records'].append(reference);self.state['pending']=self.state['original']=None;self.save()
                self.read(reference);self.clock();return deepcopy(reference)
        except Exception:
            if self.state['original'] is None:row['status']='failed';self.save()
            raise
