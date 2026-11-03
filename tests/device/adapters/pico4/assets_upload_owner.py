"""Next normal glTF Upload in one Prefix3; no Common/Actor/render success.

The parent owns every raw/decoded copy and one global bill. Failure retains the
same inputs, original backend/upload claims and actual staged file lease.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import math
from urllib.parse import unquote,urlsplit

from adapters.native_feature_observation import decode,need,number,integer,exact
from adapters.normal_ui import NativeUIError
from adapters.pico4.assets_backend import baseline,responsibility,owned_inventory
from adapters.pico4.assets_backend_originals import PicoAssetsBackendOriginals
from adapters.pico4.assets_file_owner import OwnedAssetsFiles
from adapters.pico4.assets_inventory import original as inventory
from adapters.pico4.assets_raw_archive import compact
from adapters.pico4.assets_source import PicoAssetsSource,nonce
from adapters.pico4.assets_ui import PicoAssetsIO
from adapters.pico4.navigation import NativeNavigationIO
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.script_journey.history import canonical,same,unpack
from adapters.token_assets_ui import TokenAssetsUI
from adapters.token_create_ui import scope

RESOURCE='gltf-bundle/main.gltf'
UNRESOLVED_UPLOADS=[]
class AssetsMappingPending(Exception):pass


def validate_state(value,steps,bundles):
    if value is None:return
    exact(value,{'assetsUploadOwnerVersion','ticket','resource','phase','startedMonotonic','startedEpochMs',
        'baseline','files','browser','claim','downloads','quiet','result'})
    need(type(value['assetsUploadOwnerVersion']) is int and value['assetsUploadOwnerVersion']==1
        and type(steps) is list and len(steps)==4 and value['ticket']==steps[3]['ticket']
        and nonce(value['ticket']) and value['resource']==RESOURCE
        and value['phase'] in ('reserved','delivering','quiet','files-retired')
        and number(value['startedMonotonic'],0,1e15) and integer(value['startedEpochMs'],1)
        and type(value['downloads']) is list and len(value['downloads'])<=3)
    for reference in [value[k] for k in ('baseline','files','claim','quiet','result')]+value['downloads']:
        need(reference is None or integer(reference,0,bundles-1))
    browser=value['browser']
    if browser is not None:
        exact(browser,{'id','modelId','contextId','windowId','componentSource','bornEpochMs'})
        need(all(nonce(browser[k]) for k in ('id','modelId','contextId','windowId')) and integer(browser['bornEpochMs'],1)
            and type(browser['componentSource']) is str and len(browser['componentSource'])<=4096)
        url=urlsplit(browser['componentSource'])
        need(url.scheme in ('qrc','file') and not url.netloc and not url.query and not url.fragment
            and url.path.endswith('/dialogs/NativeFileBrowser.qml'))
    if value['phase']=='files-retired':
        need(all(value[k] is not None for k in ('baseline','files','browser','claim','quiet','result'))
             and len(value['downloads'])==3)


class OwnedAssetsUpload:
    def __init__(self,parent,files,backend,downloader):
        need(parent.version==3 and parent.upload_owner is None and parent.state['upload'] is None
            and len(parent.state['steps'])==4 and parent.state['steps'][-1]['status']=='issued'
            and type(files) is OwnedAssetsFiles and files.native.stage==2 and files.previous is None
            and files.run==parent.run and files.ticket==parent.state['steps'][-1]['ticket']
            and same(files.binding,parent.binding) and files.url==parent.url
            and type(backend) is PicoAssetsBackendOriginals and not backend.history and backend.last is None and backend.pending is None
            and type(downloader) is PicoAssetsSource and downloader.is_download and not downloader.is_resolve
            and downloader.pid==parent.pid and not downloader.history and downloader.last is None and downloader.pending is None)
        self.parent,self.files,self.backend,self.downloader=parent,files,backend,downloader
        self.started,self.epoch=None,None;self.active_ui=None;self.ui_anchor=None;self.last_ui_anchor=None;self.failed=False;self.call_returned=False
        self.sleep=files.native.sleep
        self.draft=None;self.control_anchor=None;self.query=None;self.baseline=None;self.browser_baseline=None;self.acquired=None
        self.file_journal=object.__new__(LifecycleProcessFile)
        try:LifecycleProcessFile.__init__(self.file_journal,files.store)
        except BaseException:UNRESOLVED_UPLOADS.append(self);raise
        files.store.write=self.file_journal.write
        self.file_send,self.file_raw=files.native.send,files.native.original
        files.native.send=lambda value:self.issue('files',value,self.file_send)
        files.native.original=lambda:self.raw('files',self.file_raw)
        original_request=files.native.request
        def file_request(*args,**kwargs):
            value=original_request(*args,**kwargs);self.finish();return value
        files.native.request=file_request
        original_download_send,original_download_raw=downloader.send,downloader.original
        downloader.intent=lambda command:self.begin('download',command)
        downloader.send=lambda command:self.send('download',command,original_download_send)
        downloader.original=lambda:self.raw('download',original_download_raw)
        backend.capacity=lambda:self.backend_capacity()
        backend.retain=lambda raw:self.retain_raw('backend',raw)

    def bill(self):
        self.file_journal.guard()
        count=len(self.backend.history)+len(self.downloader.history)
        size=len(canonical(self.backend.history))+len(canonical(self.downloader.history));paths=[]
        value=self.files.store.read()
        if value is not None:
            paths.append(self.files.store.path);count+=max(len(unpack(value['originals'])),len(self.files.native.history))
            size+=len(canonical(value))+max(value['originals']['bytes'],len(canonical(self.files.native.history)))
        elif self.files.native.history:
            count+=len(self.files.native.history);size+=len(canonical(self.files.native.history))
        return dict(frames=count,decodedBytes=size,paths=paths)

    def age(self):
        if self.started is not None and not self.call_returned:
            p=self.parent;now=p.phases.monotonic();epoch=p.clock_ms();ended=p.phases.monotonic()
            need(number(now,self.started,self.started+20) and number(ended,now,self.started+20)
                 and integer(epoch,self.epoch,self.epoch+20000))

    def guard(self):
        p=self.parent;p.bound();p.business();need(not self.failed and not p.failed and p.guard() is not False)
        self.file_journal.guard()
        p.phase('upload');return True

    def update(self,**values):
        self.parent.state['upload'].update(deepcopy(values))
        validate_state(self.parent.state['upload'],self.parent.state['steps'],len(self.parent.state['bundles']))
        self.parent.save()

    def begin(self,role,command):
        p=self.parent;anchor=(p.phases.monotonic(),p.clock_ms())
        self.guard();need(self.query is None and p.disk['pendingSource'] is None)
        p.query_anchor=anchor
        self.query=dict(role=role,command=deepcopy(command));p.state['pendingSource']=dict(role=role,command=p.command_reference(command),raw=[])
        p.raw_archive.reserve(role,command);p.query_age()

    def send(self,role,command,send):
        need(self.query is not None and self.query['role']==role and same(command,self.query['command']))
        self.parent.query_age()
        return send(command) if self.parent.wire is None else self.parent.wire.dispatch(command,send)

    def issue(self,role,command,send):
        self.begin(role,command);return self.send(role,command,send)

    def retain_raw(self,role,raw):
        p=self.parent;need(self.query is not None and self.query['role']==role)
        ref=p.raw_archive.retain_bytes(raw) if type(raw) is bytes else p.raw_archive.retain(raw)
        index=p.raw_receipt(dict(role=role,rawOriginal=compact(ref)),p.state['pendingSource']['raw'])
        # Binary backend transport is parsed by its own exact decoder later.
        if type(raw) is str:p.raw_archive.parser_capacity(raw,self.query['command'])
        return index

    def raw(self,role,getter):
        p=self.parent;need(self.query is not None and self.query['role']==role)
        if p.raw_archive.active is None:p.raw_archive.reserve(role,self.query['command'])
        p.query_age();raw=getter() if p.wire is None else p.wire.read(role)
        self.acquired=raw
        if p.wire is None:self.retain_raw(role,raw)
        else:p.wire.consume(role,raw);p.raw_archive.parser_capacity(raw,self.query['command'])
        self.acquired=None;return raw

    def finish(self):
        p=self.parent;need(self.query is not None and p.disk['pendingSource']['raw'])
        p.state['pendingSource']=None;p.save();self.query=None;p.bill();self.age()

    def file_read(self,operation='observe'):
        # OwnedAssetsFiles controls the exact once-only stage/release transitions.
        return self.files.read(operation)

    def prepare_files(self):
        # Each existing owner method may make multiple original queries. Seal
        # each completed one before the next send without retrying a command.
        return self.files.prepare()

    def backend_capacity(self):
        p=self.parent;need(self.query is not None and self.query['role']=='backend')
        if p.raw_archive.active is None:p.raw_archive.reserve('backend',self.query['command'])
        p.query_age()

    def backend_read(self):
        self.begin('backend',dict(schemaVersion=1,runId=self.parent.run))
        result=self.backend.read(self.parent.run);self.finish();return result

    def downloaded(self,digest):
        value=self.downloader.read(self.parent.run,digest);self.finish();return value

    def sample(self,*,files=True):
        p=self.parent;self.guard();observation=p.sample()
        packet=decode(p.literal(observation['sourceUi']).decode('utf-8'))
        result=dict(mappings=deepcopy(p.mappings.last),uploads=deepcopy(p.uploads.last),
            ui=inventory(packet),uiPacket=packet,observation=observation,
            files=self.file_read() if files and self.files.previous is not None else None,
            backend=self.backend_read(),started=p.anchor[0],epoch=p.anchor[1])
        p.fresh();self.age();return result

    def wrap_ui(self,ui):
        need(type(ui) is TokenAssetsUI and type(ui.io) is PicoAssetsIO)
        io=ui.io.original.navigation.io;need(type(io) is NativeNavigationIO)
        from adapters.pico4.assets_wire_owner import bind_assets_navigation_raw
        bind_assets_navigation_raw(self,io)
        return ui

    def ui(self):
        if self.active_ui is None:self.active_ui=self.wrap_ui(self.parent.controls(self.intent,before_send=self.before_send,audit=self.audit))
        return self.active_ui

    def audit(self,kind,value):
        p=self.parent
        if kind=='intent':
            self.guard();need(self.draft is None);self.draft=deepcopy(value);return True
        need(kind=='receipt' and p.disk['pendingInput'] is not None and self.draft is not None)
        pending=p.disk['pendingInput'];native=pending['native'];after=value['after']['scope'];scope(after)
        need(native is not None and after['instance']==native['bridgeId'] and after['processId']==p.pid
             and after['generation']==native['generation'] and after['sequence']==native['sequence'])
        p.archive(dict(uploadReceipt=deepcopy(value),native=deepcopy(native)))
        p.state['pendingInput']=None;p.save();identifier=self.draft['controlId'];self.draft=None
        if identifier=='assets.upload':
            sample=self.sample();self.admit_browser(sample)
        return True

    def intent(self,value):
        p=self.parent;self.guard();need(self.draft is not None and p.disk['pendingInput'] is None)
        scope(value['scope']);need(value['scope']['instance']==p.binding['sessionId'] and value['scope']['processId']==p.pid
            and value['controlId']==self.draft['controlId'] and value['action']==self.draft['action'])
        p.fence.mark();p.state['pendingInput']=dict(reference=deepcopy(value),native=None)
        p.save();p.fence.check()

    def before_send(self,command,navigation):
        p=self.parent;self.guard();p.fence.check();pending=p.disk['pendingInput']
        need(pending is not None and pending['native'] is None and self.draft is not None)
        ref=pending['reference'];need(all(command[k]==ref[k] for k in ('controlId','controlToken','action'))
            and command['bridgeId']==ref['scope']['instance'] and command['generation']==ref['scope']['generation']
            and command['sequence']==ref['scope']['sequence']+1 and command['observedElapsedMs']==ref['scope']['elapsedMs'])
        if command['action']=='replace':need(command['text']==self.draft['value'])
        elif command['action']=='select-index':need(command['index']==self.draft['value'])
        elif command['action']=='scroll':need(command['direction']==self.draft['value'])
        else:need(self.draft['value'] is None)
        p.state['pendingInput']['native']=deepcopy(command)
        p.archive(dict(uploadIntent=deepcopy(self.draft),native=deepcopy(command)),on_seal=lambda index:p.state['inputs'].append(index))
        self.begin('ui-status',deepcopy(command))
        need(self.last_ui_anchor is not None);p.query_anchor=self.last_ui_anchor
        p.fence.check();p.query_age();self.age()

    @staticmethod
    def dead(row):
        return not any(row[k] for k in ('rootAlive','modelAlive','inCurrentTree','pendingDocuments'))

    def browser(self,sample):
        rows=sample['ui']['browsers'];baseline={r['id']:r for r in self.browser_baseline}
        current={r['id']:r for r in rows};need(set(baseline)<=set(current))
        immutable=('id','modelId','contextId','windowId','componentSource','bornEpochMs')
        for key,before in baseline.items():
            after=current[key];need(self.dead(after) and all(after[k]==before[k] for k in immutable)
                and (before['contextAlive'] or not after['contextAlive']) and (before['windowAlive'] or not after['windowAlive']))
        opened=[r for r in rows if r['id'] not in baseline];need(len(opened)==1)
        return opened[0]

    def admit_browser(self,sample):
        row=self.browser(sample);need(row['rootAlive'] and row['modelAlive'] and row['inCurrentTree'] and not row['pendingDocuments'])
        need(self.parent.state['upload']['browser'] is None)
        self.update(browser={k:row[k] for k in ('id','modelId','contextId','windowId','componentSource','bornEpochMs')})

    def retired(self,sample):
        row=self.browser(sample);known=self.parent.state['upload']['browser'];need(known is not None)
        need(all(row[k]==v for k,v in known.items()))
        uploads=sample['uploads']['source']
        return self.dead(row) and uploads['originalActiveBundles']==uploads['activeBundles']==uploads['liveRequests']==0

    def evidence(self,sample):
        claim=responsibility(sample['uploads'],sample['files'],RESOURCE,self.parent.run,
            {k:sample['mappings']['source'][k] for k in ('domainId','sessionId','assetServerId','domainSession')})
        backend=sample['backend']['source'];client=sample['mappings']['source']
        need(all(backend[k]==client[k] for k in ('domainId','assetServerId')))
        if {r['path']:r['hash'] for r in backend['mappings']}!={r['path']:r['hash'] for r in client['mappings']}:
            raise AssetsMappingPending()
        owned=owned_inventory(sample['mappings'],sample['backend'],self.baseline,[claim],self.parent.run)
        return claim,owned

    def quiet(self):
        p=self.parent;first=previous=sample=self.sample();started=p.phases.monotonic()
        for attempt in range(41):
            claim,owned=self.evidence(sample);need(claim['complete'] and claim['terminal'] and self.retired(sample))
            if p.phases.monotonic()-started>=3 and sample['ui']['elapsedMs']-first['ui']['elapsedMs']>=3000:break
            need(p.phases.monotonic()-started<=5)
            self.sleep(max(0,.25-(p.phases.monotonic()-sample['started'])))
            sample=self.sample();need(0<sample['ui']['elapsedMs']-previous['ui']['elapsedMs']<=500
                and 0<sample['ui']['capturedEpochMs']-previous['ui']['capturedEpochMs']<=500);previous=sample
        else:need(False)
        need(p.phases.monotonic()-started>=3 and sample['ui']['elapsedMs']-first['ui']['elapsedMs']>=3000)
        self.update(quiet=p.archive(dict(first=first,last=sample,started=started,finished=p.phases.monotonic())))
        return claim,owned

    def release_files(self):
        def current():
            sample=self.sample();claim,_owned=self.evidence(sample)
            need(claim['complete'] and self.retired(sample));return True
        self.files.release(current)
        return self.files.read()['source']

    def run(self,fields):
        p=self.parent;self.started=p.phases.monotonic();self.epoch=p.clock_ms()
        p.state['upload']=dict(assetsUploadOwnerVersion=1,ticket=fields['ticket'],resource=RESOURCE,phase='reserved',
            startedMonotonic=self.started,startedEpochMs=self.epoch,baseline=None,files=None,browser=None,claim=None,downloads=[],quiet=None,result=None)
        p.save()
        try:
            initial=self.sample(files=False)
            need(initial['mappings']['source']['canWrite'] and initial['uploads']['source']['originalActiveBundles']==0
                and initial['uploads']['source']['activeBundles']==initial['uploads']['source']['liveRequests']==0
                and all(self.dead(row) for row in initial['ui']['browsers']))
            self.browser_baseline=deepcopy(initial['ui']['browsers'])
            self.baseline=baseline(initial['mappings'],initial['backend'],p.run)
            self.update(baseline=p.archive(dict(originalBackendBaseline=self.baseline,ui=initial['uiPacket'])))
            directory=self.prepare_files();files=self.file_read()
            self.update(files=p.archive(dict(stageOriginal=files)),phase='delivering')
            self.ui().upload_bundle(unquote(urlsplit(directory).path),RESOURCE,'/e2e-'+p.run+'/')
            self.age();settle=p.phases.monotonic();sample=self.sample()
            for attempt in range(51):
                try:claim,owned=self.evidence(sample)
                except AssetsMappingPending:claim=None
                if claim is not None:
                    self.update(claim=p.archive(claim))
                    if claim['complete'] and claim['terminal'] and self.retired(sample):break
                need(p.phases.monotonic()-settle<5 and attempt<50);self.sleep(.1);sample=self.sample()
            else:need(False)
            self.ui().input('assets.refresh')
            self.ui().select_mapping(claim['published'][claim['primary']]['path'])
            downloads=[]
            for name,actual in sorted(claim['published'].items()):
                packet=self.downloaded(actual['hash']);raw=base64.b64decode(packet['source']['base64'],validate=True)
                expected=self.files.inputs['gltf-bundle/'+name]
                need(raw==expected and len(raw)==claim['files'][name]['bytes']
                     and hashlib.sha256(raw).hexdigest()==claim['files'][name]['sha256'])
                downloads.append(p.archive(dict(relativePath=name,actualDownload=packet)))
            self.update(downloads=downloads,phase='quiet')
            claim,owned=self.quiet();retired=self.release_files()
            need(retired['retired'] and not retired['exists'])
            self.update(phase='files-retired',result=p.archive(dict(claim=claim,mappings=owned,files=retired)))
            self.age();return dict(assetsUploadComponentVersion=1,normalUploadObserved=True,exactDownloadedBytes=True,
                stagedFilesRetired=True,completeCommonObservation=False,retained=True)
        except BaseException:
            self.failed=True;UNRESOLVED_UPLOADS.append(self);raise
