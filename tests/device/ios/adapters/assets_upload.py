"""Durable ordinary bundle input, independent readback and client cleanup.

This narrow owner does not establish model/oven/rendering or server-data
retirement. Its originals remain private and the whole Assets capability stays
closed. Ordinary input receipts never establish an upload or a closed root.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import time
from adapters.native_feature_observation import NativeFeatureObservation,exact,integer,need,number,validate
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same,pack,unpack
from adapters.operation_transport_guard import check as transport_check
from feature_journeys.asset_fixture import BUNDLES,bundle as fixture_bundle
from ios.adapters.assets_budget import operation
from ios.adapters.assets_controls import project,local,identity
from ios.adapters.assets_bundle_controls import inventory,manifest
from ios.adapters.assets_files import OwnedAssetsFiles,quiet
from ios.adapters.assets_picker import OwnedAssetsPicker,root
from ios.adapters.assets_reply_owner import OwnedAssetsReplyReads
from ios.adapters.graphics_history import follow_native
from ios.adapters.normal_input import NativeInput,observation

VERSION=1
CAPTURES=160


class OwnedAssetsUpload:
    def __init__(self,native,clock,files,picker,replies,store,binding,*,lock,role='primary',monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(native,NativeInput) and isinstance(clock,NativeFeatureObservation) and clock.ios and not clock.native_clock_bound
            and isinstance(files,OwnedAssetsFiles) and isinstance(picker,OwnedAssetsPicker) and isinstance(replies,OwnedAssetsReplyReads)
            and isinstance(store,PrivateFeatureState) and role in ('primary','actor') and callable(monotonic) and callable(sleep));context(binding)
        need(same(binding,files.binding) and same(binding,picker.binding) and same(binding,replies.binding) and clock.pid==files.native.pid)
        self.native,self.clock,self.files,self.picker,self.replies=native,clock,files,picker,replies
        self.store,self.binding,self.lock,self.role=store,deepcopy(binding),lock,role;self.monotonic,self.sleep=monotonic,sleep
        self._native_capture=native.capture;self.previous=store.read();self.state=None;self._cached=[];self._validated_refs=[];self._projects=[]
        self.originals=OriginalFrameStore(store.path.parent,binding,files.run,role,self.guard,self.frame_intent,
            namespace='assets-upload',schema_prefix='iosAssetsUpload',monotonic=monotonic)
        lock.assert_held()
        if self.previous is not None:
            self.state=self.decode(self.previous)
            if self._cached and clock.instance is None:
                from adapters.native_clock_source_history import restore
                restore(clock,self._cached[-1]['clocks'][-1])

    def guard(self):
        self.lock.assert_held();transport_check();need(self.files.native.guard() is not False and self.clock.guard() is not False)
        return True

    def decode(self,value):
        exact(value,{'iosAssetsUploadOwnerVersion','runId','binding','fileOwnerToken','role','payload'})
        need(type(value['iosAssetsUploadOwnerVersion']) is int and value['iosAssetsUploadOwnerVersion']==VERSION
            and value['runId']==self.files.run and same(value['binding'],self.binding) and value['role']==self.role
            and self.files.state is not None and value['fileOwnerToken']==self.files.state['token'])
        decoded=unpack(value['payload']);need(len(decoded)==1);state=decoded[0]
        exact(state,{'phase','page','picker','destination','frames','pending','inputs','baseline','workBefore','workProof','readback','cleanupWindow','aborted'})
        need(state['phase'] in ('ready','review','destination','starting','uploaded','closing','page-dead','releasing','retired')
            and type(state['frames']) is list and len(state['frames'])<=CAPTURES and type(state['inputs']) is list and len(state['inputs'])<=48
            and type(state['aborted']) is bool and state['destination']=='/e2e-'+self.files.run+'/')
        identity(state['page']);identity(state['picker']);previous=None;frames=[];projects=[];previous_native=None;roots={}
        for index,reference in enumerate(state['frames'],1):
            need(reference['index']==index);frame=self.originals.read(self.originals.expand(reference))
            # The exact private inode is still reopened, bounded, hashed and
            # decoded on every inspection. A previously validated digest is
            # immutable; replaying all native grammars on that identical
            # original for each intermediate WAL phase adds no new evidence.
            known=index<=len(self._validated_refs) and reference==self._validated_refs[index-1]
            if not known:
                self.frame(frame,previous)
                for clock in frame['clocks']:
                    if previous_native is not None:follow_native(previous_native,clock)
                    previous_native=clock
                current=project(frame['ui'])
            else:previous_native=frame['clocks'][-1];current=self._projects[index-1]
            for row in current['inventory']['roots']:
                old=roots.get(row['rootId'])
                stable={key:row[key] for key in ('role','componentSource','ownerRootId','firstObservedEpochMs')}
                if old is not None:need(same(old['stable'],stable) and (old['alive'] or not row['alive']))
                roots[row['rootId']]=dict(stable=stable,alive=row['alive'])
            previous=frame;frames.append(frame);projects.append(current)
        slots=set()
        for entry in state['inputs']:
            exact(entry,{'slot','id','action','text','index','before','command','receipt','effect','resolvedBy','abandonedBy'})
            need(type(entry['slot']) is str and re.fullmatch('[a-z][a-z0-9-]{0,47}',entry['slot']) and entry['slot'] not in slots
                and integer(entry['before'],1,len(frames)) and entry['action'] in ('activate','replace','submit','select-index'))
            slots.add(entry['slot']);reference=projects[entry['before']-1];targets=[row for row in reference['controls'] if row['id']==entry['id']];need(len(targets)==1)
            target=targets[0]['assetControl'];need(target['rootId']==state['picker' if entry['id'].startswith('asset-file.') else 'page'] and target['ownerRootId']==state['page'])
            need((entry['action']=='replace')==(entry['text'] is not None) and (entry['action']=='select-index')==(entry['index'] is not None))
            effect=entry['effect'];need(type(effect) is dict);kind=effect.get('kind')
            need(kind in ('focus','text','directory','chosen','review','primary','destination','upload','picker-dead','destination-closed','page-dead'))
            exact(effect,{'kind'}|({'url'} if kind=='directory' else {'urls'} if kind=='chosen' else set()))
            if kind=='directory':need(local(effect['url']).startswith(local(self.files.state['directory'])))
            if kind=='chosen':
                need(type(effect['urls']) is list and len(effect['urls'])==len(set(effect['urls'])) and set(effect['urls'])<=
                    {self.files.state['directory']+'/'+path for path in BUNDLES[self.files.state['resource']][1]})
            if kind=='text':need(entry['action']=='replace')
            if kind=='focus':need(entry['action']=='activate')
            if kind=='primary':need(entry['id']=='asset-file.bundle-primary' and entry['action']=='select-index')
            if kind=='destination':need(entry['id']=='asset-file.bundle-use')
            if kind=='upload':need(entry['id']=='assets.destination.accept')
            if kind=='page-dead':need(entry['id']=='assets.home')
            if kind=='picker-dead':need(entry['id']=='asset-file.cancel')
            if kind=='destination-closed':need(entry['id']=='assets.destination.cancel')
            command=entry['command']
            if command is None:need(entry['receipt'] is None and entry['resolvedBy'] is None)
            else:
                exact(command,{'schemaVersion','commandId','instance','sequence','observedElapsedMs','fieldToken','operation'}
                    |({'text'} if entry['action']=='replace' else {'index'} if entry['action']=='select-index' else set()))
                identity(command['commandId']);scope=reference['scope']
                need(type(command['schemaVersion']) is int and command['schemaVersion']==1 and command['instance']==scope['instance']
                    and command['sequence']==scope['lastSequence']+1 and type(command['sequence']) is int
                    and command['observedElapsedMs']==scope['elapsedMs'] and type(command['observedElapsedMs']) is int
                    and command['fieldToken']==targets[0]['token'] and command['operation']==entry['action'])
                if entry['action']=='replace':need(command['text']==entry['text'])
                if entry['action']=='select-index':need(command['index']==entry['index'] and type(command['index']) is int)
                if entry['receipt'] is not None:
                    receipt=entry['receipt'];exact(receipt,{'schemaVersion','commandId','status'});status=receipt['status']
                    exact(status,{'schemaVersion','commandId','instance','sequence','performed','processId','sampleEpochMs'})
                    need(type(receipt['schemaVersion']) is int and receipt['schemaVersion']==1 and type(receipt['commandId']) is str
                        and re.fullmatch('ios-[a-f0-9]{32}',receipt['commandId']) and type(status['schemaVersion']) is int and status['schemaVersion']==1
                        and status['performed'] is True and status['commandId']==command['commandId'] and status['instance']==command['instance']
                        and status['sequence']==command['sequence'] and status['processId']==self.clock.pid
                        and number(status['sampleEpochMs'],scope['sampleEpochMs'],scope['sampleEpochMs']+1500))
            if entry['resolvedBy'] is not None:
                need(integer(entry['resolvedBy'],entry['before']+1,len(frames)));self.effect(entry,frames[entry['resolvedBy']-1]['ui'],state,current=projects[entry['resolvedBy']-1])
            if entry['abandonedBy'] is not None:
                need(integer(entry['abandonedBy'],entry['before']+1,len(frames)))
                current=projects[entry['abandonedBy']-1];root(current,'page',alive=False,identifier=state['page']);root(current,'picker',alive=False,identifier=state['picker'])
        if state['pending'] is not None:
            exact(state['pending'],{'hostBefore','hostAfter','queries','clocks','ui','uiReceipt','original'})
            need(number(state['pending']['hostBefore'],0,1e15) and type(state['pending']['queries']) is list and type(state['pending']['clocks']) is list)
            if state['pending']['original'] is not None:self.originals.original(state['pending']['original'])
        for name in ('workBefore','workProof'):
            if state[name] is not None:need(any(record['packet']['requestId']==state[name] and record['query']['operation']=='observe' for record in self.files.state['originals']))
        if state['baseline'] is not None:
            baseline=self.replies.proof(state['baseline']);need(baseline['kind']=='inventory' and not any(row['path'].startswith(state['destination']) for row in baseline['mappings']))
        if state['workProof'] is not None:self.upload_evidence(state,frames)
        if state['readback'] is not None:need(state['workProof'] is not None and same(state['readback'],self.readback_proof(state)))
        if state['phase']=='uploaded':need(state['readback'] is not None)
        if state['cleanupWindow'] is not None:self.window(state['cleanupWindow'],state,complete=state['phase']=='retired')
        if state['phase']=='retired':need(self.files.state['phase']=='retired' and self.replies.state['phase']=='closed')
        self._cached=frames;self._validated_refs=deepcopy(state['frames']);self._projects=projects;return state

    def frame(self,value,previous=None):
        exact(value,{'hostBefore','hostAfter','queries','clocks','ui','uiReceipt'})
        need(number(value['hostBefore'],0,1e15) and number(value['hostAfter'],value['hostBefore'],value['hostBefore']+1.5)
            and type(value['clocks']) is list and 2<=len(value['clocks'])<=16 and type(value['queries']) is list)
        for clock in value['clocks']:validate(clock,clock['requestId'],self.clock.pid,clock['capturedEpochMs'])
        queries=[entry['command'] for entry in value['queries'] if entry['kind']=='clock']
        need([entry['commandId'] for entry in queries]==[clock['requestId'] for clock in value['clocks']])
        for query in queries:exact(query,{'schemaVersion','commandId','action'});need(query['schemaVersion']==1 and query['action']=='feature-native-observe')
        ui=value['ui'];observation(ui,self.clock.pid,value['clocks'][-1]['capturedEpochMs']);project(ui)
        need(value['clocks'][0]['capturedEpochMs']<=ui['sampleEpochMs']<=value['clocks'][-1]['capturedEpochMs'])
        inventory(ui.get('assetBundleInventory'),pid=self.clock.pid,ui=ui['assetInventory'])
        need(ui['assetBundleControlsVersion']==1 and ui['assetBundleInventory']['available'] and ui['assetBundleInventory']['complete'])
        receipt=value['uiReceipt'];exact(receipt,{'schemaVersion','commandId','observation'})
        need(type(receipt['schemaVersion']) is int and receipt['schemaVersion']==1 and same(receipt['observation'],ui))
        issued=[entry['command'] for entry in value['queries'] if entry['kind']=='ui'];need(len(issued)==1)
        exact(issued[0],{'schemaVersion','commandId','action','operation'})
        need(issued[0]['schemaVersion']==1 and issued[0]['action']=='normal-ui-input' and issued[0]['operation']=='observe' and issued[0]['commandId']==receipt['commandId'])
        if previous is not None:
            need(value['hostBefore']>=previous['hostAfter'] and ui['instance']==previous['ui']['instance'] and ui['lastSequence']>=previous['ui']['lastSequence']
                and ui['elapsedMs']>=previous['ui']['elapsedMs'] and ui['sampleEpochMs']>=previous['ui']['sampleEpochMs'])
            for key in ('assetInventory','assetBundleInventory'):
                old,new=previous['ui'][key],ui[key];need(old['instance']==new['instance'] and new['sequence']>old['sequence'] and new['capturedEpochMs']>=old['capturedEpochMs'])
            if 'assetTreeInventory' in previous['ui']:
                need('assetTreeInventory' in ui);old,new=previous['ui']['assetTreeInventory'],ui['assetTreeInventory']
                need(old['instance']==new['instance'] and new['sequence']>old['sequence'] and new['capturedEpochMs']>=old['capturedEpochMs'])

    def save(self):
        self.guard();need(same(self.store.read(),self.previous))
        value=dict(iosAssetsUploadOwnerVersion=VERSION,runId=self.files.run,binding=self.binding,fileOwnerToken=self.files.state['token'],role=self.role,payload=pack([self.state]))
        self.decode(value);self.store.write(value,self.previous);self.previous=deepcopy(value)

    def frame_intent(self,kind,value):
        need(kind=='original' and self.state['pending'] is not None);self.state['pending']['original']=deepcopy(value);self.save();return True

    @operation
    def reserve(self):
        need(self.state is None and self.files.state['phase']=='staged' and self.picker.state['phase']=='primary-chosen' and self.replies.state['phase']=='open')
        self.state=dict(phase='ready',page=self.picker.state['page'],picker=self.picker.state['picker'],destination='/e2e-'+self.files.run+'/',
            frames=[],pending=None,inputs=[],baseline=None,workBefore=None,workProof=None,readback=None,cleanupWindow=None,aborted=False);self.save()

    @operation
    def capture(self):
        need(self.state is not None and self.state['pending'] is None and len(self.state['frames'])<CAPTURES);self.guard()
        self.state['pending']=dict(hostBefore=self.monotonic(),hostAfter=None,queries=[],clocks=[],ui=None,uiReceipt=None,original=None);self.save()
        pending=self.state['pending'];original_send,original_read=self.clock.send,self.clock.read;old_intent=getattr(self.native,'observe_intent',None)
        def send(command):pending['queries'].append(dict(kind='clock',command=deepcopy(command)));self.save();return original_send(command)
        def read(*args,**kwargs):
            packet=original_read(*args,**kwargs);pending['clocks'].append(deepcopy(packet));self.save();return packet
        def intent(command):
            pending['queries'].append(dict(kind='ui',command=deepcopy(command)));self.save()
            if old_intent is not None:old_intent(command)
        self.clock.send,self.clock.read,self.native.observe_intent=send,read,intent
        try:
            self.clock.read(self.clock.sequence);packet=self._native_capture();pending['ui']=deepcopy(packet);pending['uiReceipt']=deepcopy(self.native.last_receipt);self.save()
            self.clock.read(self.clock.sequence);pending['hostAfter']=self.monotonic();self.save()
        finally:
            self.clock.send,self.clock.read=original_send,original_read
            if old_intent is None:del self.native.observe_intent
            else:self.native.observe_intent=old_intent
        frame={key:deepcopy(pending[key]) for key in ('hostBefore','hostAfter','queries','clocks','ui','uiReceipt')};self.frame(frame,self._cached[-1] if self._cached else None)
        reference=self.originals.write(len(self.state['frames'])+1,frame);self.state['frames'].append(reference);self.state['pending']=None;self.save();return deepcopy(packet)

    @operation
    def recover_capture(self):
        """Read the exact completed private inode; never repeat its query."""
        pending=self.state['pending'];need(pending is not None and pending['original'] is not None)
        original=pending['original'];frame=self.originals.read(original);self.frame(frame,self._cached[-1] if self._cached else None)
        reference=self.originals.compact(dict(original,phase='saved'));need(reference['index']==len(self.state['frames'])+1)
        self.state['frames'].append(reference);self.state['pending']=None;self.save();return deepcopy(frame['ui'])

    def current(self):return project(self.capture())

    def bundle_row(self,packet,role,*,state=None):
        state=self.state if state is None else state
        rows=[row for row in packet['assetBundleInventory']['rows'] if row['role']==role and row['rootId']==state[role]];need(len(rows)==1);return rows[0]

    def expected_bundle(self,actual,*,primary=False):
        manifest(actual);need(actual is not None and actual['root']==self.files.state['directory'])
        expected=BUNDLES[self.files.state['resource']];need(set(actual['relativePaths'])==set(expected[1]) and set(actual['urls'])=={self.files.state['directory']+'/'+path for path in expected[1]})
        if primary:need(actual['primaryPath']==expected[0])
        return actual

    def upload_evidence(self,state,frames):
        """Rejoin retained UI and client-work originals during reconstruction."""
        need(state['workBefore'] is not None and state['baseline'] is not None)
        records={record['packet']['requestId']:record['packet'] for record in self.files.state['originals'] if record['query']['operation']=='observe'}
        before,after=records[state['workBefore']],records[state['workProof']];work=after['source']['work'];need(work['available'] and work['complete'])
        old={row['id'] for row in before['source']['work']['jobs']};new=[row for row in work['jobs'] if row['id'] not in old];bundles=[row for row in new if row['kind']=='bundle']
        paths={local(self.files.state['directory'])+'/'+path for path in BUNDLES[self.files.state['resource']][1]}
        need(len(bundles)==1 and set(bundles[0]['files'])==paths and bundles[0]['terminal'] and bundles[0]['entered']>0
            and bundles[0]['returned']==bundles[0]['entered'] and bundles[0]['created']['epochMs']>=before['clockAfter']['epochMs'])
        uploads=[row for row in new if row['kind']=='upload'];need(uploads and {file for row in uploads for file in row['files']}==paths)
        for row in new:need(not row['alive'] and row['expired'] is not None and row['pendingBodies']==0)
        found=False
        for frame in frames:
            ui=frame['ui'];rows=[row for row in ui['assetBundleInventory']['rows'] if row['rootId']==state['page'] and row['role']=='page']
            pages=[row for row in ui['assetInventory']['roots'] if row['rootId']==state['page'] and row['alive']]
            if not rows or not pages:continue
            row,page=rows[0],pages[0]
            if (not page['busy'] and not page['bundleRequest'] and not page['pendingBundle'] and not row['destinationVisible']
                    and row['uploadedPrimaryUrl']=='atp:'+state['destination']+BUNDLES[self.files.state['resource']][0]):found=True
        need(found)

    def readback_proof(self,state):
        """Pure projection of exact independent read jobs already owned."""
        first=self.replies.proof('bundle-inventory');final=self.replies.proof('bundle-final-inventory');prefix=state['destination']
        actual=[row for row in first['mappings'] if row['path'].startswith(prefix)];last=[row for row in final['mappings'] if row['path'].startswith(prefix)]
        expected=fixture_bundle(self.files.run,self.files.state['ticket'],self.files.url,self.files.state['resource'])
        need(same(actual,last) and first['binding']==final['binding'] and {row['path'][len(prefix):] for row in actual}==set(BUNDLES[self.files.state['resource']][1]))
        result=[];primary=self.replies.proof('bundle-primary-mapping')
        for index,row in enumerate(actual):
            path=row['path'][len(prefix):];info=self.replies.proof('bundle-info-'+str(index));raw=self.replies.proof('bundle-raw-'+str(index))
            wanted=next(item for item in expected['files'] if item['relativePath']==path)
            need(info['hash']==raw['hash']==row['hash'] and raw['body']['sha256']==wanted['sha256'] and raw['body']['bytes']==wanted['bytes'])
            result.append(dict(relativePath=path,hash=raw['hash'],body=raw['body'],captured=raw['captured'],binding=raw['binding']))
        return dict(iosAssetsSourceBundleVersion=VERSION,resource=self.files.state['resource'],namespace='original',mappings=deepcopy(last),
            files=result,primaryMapping=primary,binding=final['binding'],captured=final['captured'])

    def effect(self,entry,packet,state,*,current=None):
        command=entry['command'];need(command is not None and packet['instance']==command['instance'] and packet['lastSequence']==command['sequence'])
        current=project(packet) if current is None else current;effect=entry['effect'];kind=effect['kind']
        if kind in ('focus','text'):
            rows=[row for row in current['controls'] if row['id']==entry['id']];need(len(rows)==1 and rows[0]['focused'])
            if kind=='text':need(rows[0]['assetControl']['fieldText']==entry['text'])
        elif kind=='directory':need(root(current,'picker',identifier=state['picker'])['directory']==effect['url'])
        elif kind=='chosen':need(root(current,'picker',identifier=state['picker'])['chosen']==effect['urls'])
        elif kind in ('review','primary'):
            actual=self.expected_bundle(self.bundle_row(packet,'picker',state=state)['bundle'])
            if kind=='primary':need(actual['primaryIndex']==entry['index'])
        elif kind=='destination':
            root(current,'picker',alive=False,identifier=state['picker']);row=self.bundle_row(packet,'page',state=state);need(row['destinationVisible']);self.expected_bundle(row['bundle'],primary=True)
        elif kind=='upload':
            page=root(current,'page',identifier=state['page']);row=self.bundle_row(packet,'page',state=state);need(not row['destinationVisible'])
            need(page['busy'] and bool(page['bundleRequest']) or not page['busy'] and not page['bundleRequest'] and row['uploadedPrimaryUrl']=='atp:'+state['destination']+BUNDLES[self.files.state['resource']][0])
        elif kind=='picker-dead':root(current,'picker',alive=False,identifier=state['picker'])
        elif kind=='destination-closed':need(not self.bundle_row(packet,'page',state=state)['destinationVisible'])
        elif kind=='page-dead':root(current,'page',alive=False,identifier=state['page'])
        else:need(False)

    @operation
    def input(self,slot,identifier,action='activate',*,text=None,index=None,effect,cleanup=False):
        need(not any(entry['slot']==slot for entry in self.state['inputs']) and len(self.state['inputs'])<48)
        need(cleanup and identifier in ('asset-file.cancel','assets.destination.cancel','assets.home') or not any(entry['resolvedBy'] is None and entry['abandonedBy'] is None for entry in self.state['inputs']))
        reference=project(self.capture());entry=dict(slot=slot,id=identifier,action=action,text=text,index=index,before=len(self.state['frames']),command=None,receipt=None,effect=deepcopy(effect),resolvedBy=None,abandonedBy=None)
        self.state['inputs'].append(entry);self.save()
        def intent(command):need(entry['command'] is None);entry['command']=deepcopy(command);self.save();return True
        previous_capture=self.native.capture;self.native.capture=self.capture
        try:self.native.assets_input(identifier,action,reference=reference,text=text,index=index,before_send=intent)
        finally:self.native.capture=previous_capture
        entry['receipt']=deepcopy(self.native.last_receipt);self.save();return self.resolve(slot)

    @operation
    def resolve(self,slot):
        entries=[entry for entry in self.state['inputs'] if entry['slot']==slot];need(len(entries)==1);entry=entries[0]
        need(entry['resolvedBy'] is None and entry['abandonedBy'] is None);packet=self.capture();self.effect(entry,packet,self.state)
        entry['resolvedBy']=len(self.state['frames']);self.save();return packet

    def row(self,current,url):
        rows=[row for row in current['controls'] if row['id'].startswith('asset-file.row.') and row['assetControl']['rowUrl']==url];need(len(rows)==1);return rows[0]['id']

    @operation
    def review(self):
        need(self.state['phase']=='ready');directory=self.files.state['directory'];expected=BUNDLES[self.files.state['resource']]
        for number,path in enumerate(expected[1][1:],1):
            # Enter actual folder rows; no arbitrary folder-path extension.
            current=self.current();picker=root(current,'picker',identifier=self.state['picker'])
            if picker['directory']!=directory:
                self.input('root-focus-'+str(number),'asset-file.folder',effect=dict(kind='focus'))
                self.input('root-text-'+str(number),'asset-file.folder','replace',text=local(directory),effect=dict(kind='text'))
                self.input('root-submit-'+str(number),'asset-file.folder','submit',effect=dict(kind='directory',url=directory))
            target=directory
            for level,part in enumerate(path.split('/')[:-1]):
                target+='/'+part;current=self.current();self.input('folder-'+str(number)+'-'+str(level),self.row(current,target),effect=dict(kind='directory',url=target))
            current=self.current();selected=root(current,'picker',identifier=self.state['picker'])['chosen']+[directory+'/'+path]
            self.input('companion-'+str(number),self.row(current,directory+'/'+path),effect=dict(kind='chosen',urls=selected))
        self.input('review-bundle','asset-file.select',effect=dict(kind='review'));packet=self.capture();self.expected_bundle(self.bundle_row(packet,'picker')['bundle'])
        self.state['phase']='review';self.save();return packet

    @operation
    def destination(self):
        need(self.state['phase']=='review');packet=self.capture();actual=self.expected_bundle(self.bundle_row(packet,'picker')['bundle']);index=actual['relativePaths'].index(BUNDLES[self.files.state['resource']][0])
        self.input('focus-primary','asset-file.bundle-primary',effect=dict(kind='focus'))
        self.input('choose-bundle-primary','asset-file.bundle-primary','select-index',index=index,effect=dict(kind='primary'))
        self.input('use-bundle','asset-file.bundle-use',effect=dict(kind='destination'));packet=self.capture()
        self.state['phase']='destination';self.save();return packet

    @operation
    def start_upload(self):
        need(self.state['phase']=='destination' and self.state['baseline'] is None and self.state['workBefore'] is None)
        before=self.replies.read('upload-before');need(not any(row['path'].startswith(self.state['destination']) for row in before['mappings']))
        self.state['baseline']='upload-before';self.save()
        self.input('focus-destination','assets.destination',effect=dict(kind='focus'))
        self.input('replace-destination','assets.destination','replace',text=self.state['destination'],effect=dict(kind='text'))
        packet=self.files.observe();self.state['workBefore']=packet['requestId'];self.state['phase']='starting';self.save()
        return self.input('accept-destination','assets.destination.accept',effect=dict(kind='upload'))

    @operation
    def uploaded(self):
        need(self.state['phase']=='starting');pending=[entry for entry in self.state['inputs'] if entry['resolvedBy'] is None and entry['abandonedBy'] is None]
        if pending:need(len(pending)==1 and pending[0]['slot']=='accept-destination');self.resolve('accept-destination')
        packet=self.capture();page=root(project(packet),'page',identifier=self.state['page']);actual=self.bundle_row(packet,'page')
        need(not page['busy'] and not page['bundleRequest'] and not page['pendingBundle'] and not actual['destinationVisible']
            and actual['uploadedPrimaryUrl']=='atp:'+self.state['destination']+BUNDLES[self.files.state['resource']][0])
        original=self.files.observe();work=original['source']['work'];need(work['available'] and work['complete'])
        before=next(record['packet'] for record in self.files.state['originals'] if record['packet']['requestId']==self.state['workBefore'])
        old={row['id'] for row in before['source']['work']['jobs']};new=[row for row in work['jobs'] if row['id'] not in old];bundle=[row for row in new if row['kind']=='bundle']
        paths={local(self.files.state['directory'])+'/'+path for path in BUNDLES[self.files.state['resource']][1]}
        need(len(bundle)==1 and set(bundle[0]['files'])==paths and bundle[0]['terminal'] and bundle[0]['entered']>0
            and bundle[0]['returned']==bundle[0]['entered'] and not bundle[0]['alive'] and bundle[0]['expired'] is not None
            and bundle[0]['created']['epochMs']>=before['clockAfter']['epochMs'])
        uploads=[row for row in new if row['kind']=='upload'];need(uploads and {file for row in uploads for file in row['files']}==paths)
        for row in new:need(not row['alive'] and row['pendingBodies']==0 and row['expired'] is not None)
        self.state['workProof']=original['requestId'];self.save();readback=self.replies.observe_bundle()
        self.state['readback']=deepcopy(readback);self.state['phase']='uploaded';self.save();return readback

    def window(self,window,state,*,complete):
        exact(window,{'requests','hostBrackets'});need(type(window['requests']) is list and type(window['hostBrackets']) is list
            and len(window['requests'])==len(window['hostBrackets'])<=64 and len(set(window['requests']))==len(window['requests']))
        frames=[];previous=None;jobs=None
        for request,host in zip(window['requests'],window['hostBrackets']):
            exact(host,{'before','after'});need(number(host['before'],0,1e15) and number(host['after'],host['before'],host['before']+1.5))
            records=[record for record in self.files.state['originals'] if record['query']['operation']=='observe' and record['packet']['requestId']==request];need(len(records)==1)
            packet=records[0]['packet'];source=packet['source'];quiet(source);need(source['files'].get('exists') is True and source['files']['complete']
                and not source['files']['retiredPrimary'] and not source['files']['releasing'] and all(row['exists'] for row in source['files']['files']))
            root(dict(inventory=source['ui']),'picker',alive=False,identifier=state['picker']);root(dict(inventory=source['ui']),'page',alive=False,identifier=state['page'])
            if jobs is None:jobs=source['work']['jobs']
            need(same(jobs,source['work']['jobs']))
            if previous is not None:
                need(previous['after']<=host['before']<=previous['after']+.25)
                for key in ('epochMs','monotonicMs'):need(0<=packet['clockBefore'][key]-frames[-1]['clockAfter'][key]<=250)
            previous=host;frames.append(packet)
        if complete:
            need(len(frames)>=2 and window['hostBrackets'][-1]['before']-window['hostBrackets'][0]['after']>=3)
            for key in ('epochMs','monotonicMs'):need(frames[-1]['clockBefore'][key]-frames[0]['clockAfter'][key]>=3000)
        return frames

    @operation
    def cleanup(self,*,abort=False):
        need(self.state['phase'] in ('ready','review','destination','starting','uploaded','closing','page-dead','releasing','retired'))
        if self.state['phase']=='retired':self.decode(self.previous);return self.files.state['originals'][-1]['packet']
        if self.state['phase'] not in ('closing','page-dead','releasing'):
            need(abort or self.state['phase']=='uploaded');self.state['aborted']=abort;self.state['phase']='closing';self.save()
        if self.state['phase']=='closing':
            packet=self.capture();current=project(packet)
            if any(row['alive'] and row['rootId']==self.state['picker'] for row in current['inventory']['roots']):
                self.input('cleanup-picker','asset-file.cancel',effect=dict(kind='picker-dead'),cleanup=True)
                packet=self.capture()
            if (any(row['alive'] and row['rootId']==self.state['page'] for row in project(packet)['inventory']['roots'])
                    and self.bundle_row(packet,'page')['destinationVisible']):
                self.input('cleanup-destination','assets.destination.cancel',effect=dict(kind='destination-closed'),cleanup=True)
            current=self.current()
            if any(row['alive'] and row['rootId']==self.state['page'] for row in current['inventory']['roots']):
                existing=[entry for entry in self.state['inputs'] if entry['slot']=='cleanup-home']
                if existing:self.resolve('cleanup-home')
                else:self.input('cleanup-home','assets.home',effect=dict(kind='page-dead'),cleanup=True)
            packet=self.capture();current=project(packet);root(current,'page',alive=False,identifier=self.state['page']);root(current,'picker',alive=False,identifier=self.state['picker'])
            for entry in self.state['inputs']:
                if entry['resolvedBy'] is None:entry['abandonedBy']=len(self.state['frames'])
            self.state['phase']='page-dead';self.save()
        if self.state['phase']=='page-dead':
            self.replies.close()
            if self.state['cleanupWindow'] is None:self.state['cleanupWindow']=dict(requests=[],hostBrackets=[]);self.save()
            window=self.state['cleanupWindow']
            for _ in range(64-len(window['requests'])):
                before=self.monotonic();packet=self.files.observe();after=self.monotonic();window['requests'].append(packet['requestId']);window['hostBrackets'].append(dict(before=before,after=after))
                frames=self.window(window,self.state,complete=False);self.save()
                if len(frames)>=2 and before-window['hostBrackets'][0]['after']>=3 and all(packet['clockBefore'][key]-frames[0]['clockAfter'][key]>=3000 for key in ('epochMs','monotonicMs')):
                    self.window(window,self.state,complete=True);break
                self.sleep(.1)
            else:need(False)
            self.state['phase']='releasing';self.save()
        need(self.state['phase']=='releasing')
        if self.files.state['phase']=='staged':packet=self.files.release()
        else:packet=self.files.recover_release()
        self.state['phase']='retired';self.save();return packet
