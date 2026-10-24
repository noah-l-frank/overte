"""Narrow normal Assets picker unavailable-file/cancellation owner.

This is a partial vertical, not the feature.assets operation implementation.
Product effects require new original UI/file/work observations. An input
receipt never supplies an error, closed picker, page death or file absence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import time
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.operation_transport_guard import check as transport_check
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.asset_fixture import BUNDLES
from ios.adapters.assets_controls import project,local,identity,control_id
from ios.adapters.assets_files import OwnedAssetsFiles,quiet
from ios.adapters.assets_budget import operation
from ios.adapters.normal_input import NativeInput,observation

VERSION=1
ERROR='A selected file is no longer available.'


def root(value,role,*,alive=True,identifier=None):
    rows=[row for row in value['inventory']['roots'] if row['role']==role and row['alive'] is alive
        and (identifier is None or row['rootId']==identifier)]
    need(len(rows)==1);return rows[0]


class OwnedAssetsPicker:
    def __init__(self,native,files,store,binding,*,lock,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(native,NativeInput) and isinstance(files,OwnedAssetsFiles) and isinstance(store,PrivateFeatureState)
            and callable(monotonic) and callable(sleep) and callable(getattr(native,'native_epoch_ms',None)));context(binding)
        need(same(binding,files.binding));self.native,self.files,self.store,self.binding,self.lock=native,files,store,deepcopy(binding),lock
        self.monotonic,self.sleep=monotonic,sleep;lock.assert_held();self.previous=store.read();self.state=None
        if self.previous is not None:self.state=self.decode(self.previous)

    def decode(self,value):
        exact(value,{'iosAssetsPickerOwnerVersion','runId','binding','fileOwnerToken','payload'})
        need(type(value['iosAssetsPickerOwnerVersion']) is int and value['iosAssetsPickerOwnerVersion']==VERSION
            and value['runId']==self.files.run and same(value['binding'],self.binding) and self.files.state is not None
            and value['fileOwnerToken']==self.files.state['token'])
        states=unpack(value['payload']);need(len(states)==1);state=states[0]
        exact(state,{'phase','page','picker','captures','inputs','workBeforeSelect','negativeWindow','cleanupWindow'})
        need(state['phase'] in ('reserved','page-open','picker-open','primary-chosen','checking-unavailable','unavailable','canceling','picker-closed','closing-page','page-closed','retired')
            and type(state['captures']) is list and len(state['captures'])<=96 and type(state['inputs']) is list and len(state['inputs'])<=16)
        for key in ('page','picker'):
            if state[key] is not None:identity(state[key])
        previous=None;pages={};pickers={}
        for packet in state['captures']:
            observation(packet,self.files.native.pid,packet['sampleEpochMs']);current=project(packet)
            for row in current['inventory']['roots']:
                if not row['alive']:continue
                if row['role']=='page':
                    stable=(row['componentSource'],row['ownerRootId'],row['windowId'],row['modelId'])
                    need(row['rootId'] not in pages or pages[row['rootId']]==stable);pages[row['rootId']]=stable
                else:
                    stable=(row['componentSource'],row['ownerRootId'],row['windowId'])
                    need(row['rootId'] not in pickers or pickers[row['rootId']]==stable);pickers[row['rootId']]=stable
            if previous is not None:
                need(current['scope']['instance']==previous['scope']['instance'] and current['scope']['lastSequence']>=previous['scope']['lastSequence']
                    and current['scope']['sampleEpochMs']>=previous['scope']['sampleEpochMs'] and current['scope']['elapsedMs']>=previous['scope']['elapsedMs'])
            previous=current
        slots=set()
        for entry in state['inputs']:
            exact(entry,{'slot','id','action','text','reference','command','receipt','resolvedBy'})
            need(type(entry['slot']) is str and re.fullmatch('[a-z][a-z-]{0,39}',entry['slot']) and entry['slot'] not in slots)
            slots.add(entry['slot']);need(control_id(entry['id']) and entry['action'] in ('activate','replace','submit'))
            need(any(same(project(packet),entry['reference']) for packet in state['captures']))
            targets=[row for row in entry['reference']['controls'] if row['id']==entry['id']];need(len(targets)==1)
            if entry['action']=='replace':need(type(entry['text']) is str and entry['id']=='asset-file.folder')
            else:need(entry['text'] is None)
            command=entry['command'];receipt=entry['receipt']
            if command is None:need(receipt is None and entry['resolvedBy'] is None);continue
            exact(command,{'schemaVersion','commandId','instance','sequence','observedElapsedMs','fieldToken','operation'}|({'text'} if entry['action']=='replace' else set()))
            scope=entry['reference']['scope']
            need(type(command['schemaVersion']) is int and command['schemaVersion']==1 and command['instance']==scope['instance']
                and type(command['sequence']) is int and command['sequence']==scope['lastSequence']+1
                and type(command['observedElapsedMs']) is int and command['observedElapsedMs']==scope['elapsedMs']
                and command['fieldToken']==targets[0]['token'] and command['operation']==entry['action'])
            identity(command['commandId'])
            if entry['action']=='replace':need(command['text']==entry['text'])
            if entry['resolvedBy'] is not None:
                need(type(entry['resolvedBy']) is int and 0<=entry['resolvedBy']<len(state['captures']))
                self._effect(entry,project(state['captures'][entry['resolvedBy']]),state)
            if receipt is None:continue
            exact(receipt,{'schemaVersion','commandId','status'})
            need(type(receipt['schemaVersion']) is int and receipt['schemaVersion']==1 and type(receipt['commandId']) is str
                and re.fullmatch('ios-[0-9a-f]{32}',receipt['commandId']))
            status=receipt['status'];exact(status,{'schemaVersion','commandId','instance','sequence','performed','processId','sampleEpochMs'})
            need(type(status['schemaVersion']) is int and status['schemaVersion']==1 and status['performed'] is True
                and status['commandId']==command['commandId'] and status['instance']==command['instance']
                and type(status['sequence']) is int and status['sequence']==command['sequence'] and type(status['processId']) is int and status['processId']==self.files.native.pid
                and number(status['sampleEpochMs'],scope['sampleEpochMs'],scope['sampleEpochMs']+1500))
        if state['workBeforeSelect'] is not None:
            from ios.adapters.assets_files import work
            work(state['workBeforeSelect'],self.files.native.pid)
            need(any(entry['query']['operation']=='observe' and entry['packet']['source']['files'].get('retiredPrimary') is True
                and same(entry['packet']['source']['work'],state['workBeforeSelect']) for entry in self.files.state['originals']))
        for name in ('negativeWindow','cleanupWindow'):
            if state[name] is not None:self._window_validate(state[name],state,complete=False)
        if state['phase']!='reserved':
            need(previous is not None and state['page'] is not None)
            if state['phase'] in ('picker-open','primary-chosen','unavailable'):need(state['picker'] is not None)
            if state['phase']=='unavailable':
                self._unavailable(previous,state);self._window_validate(state['negativeWindow'],state,complete=True)
            if state['phase'] in ('picker-closed','page-closed','retired'):
                need(state['picker'] is not None);root(previous,'picker',alive=False,identifier=state['picker'])
            if state['phase'] in ('page-closed','retired'):root(previous,'page',alive=False,identifier=state['page'])
            if state['phase']=='retired':
                need(self.files.state['phase']=='retired');self._window_validate(state['cleanupWindow'],state,complete=True)
        return state

    def save(self):
        self.lock.assert_held();transport_check();need(self.files.native.guard() is not False and same(self.store.read(),self.previous))
        value=dict(iosAssetsPickerOwnerVersion=VERSION,runId=self.files.run,binding=self.binding,
            fileOwnerToken=self.files.state['token'],payload=pack([self.state]))
        self.decode(value);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    @operation
    def reserve(self):
        need(self.state is None and self.files.state is not None and self.files.state['phase']=='staged')
        self.state=dict(phase='reserved',page=None,picker=None,captures=[],inputs=[],workBeforeSelect=None,negativeWindow=None,cleanupWindow=None);self.save()

    @operation
    def capture(self):
        need(self.state is not None and len(self.state['captures'])<96);self.lock.assert_held();transport_check();need(self.files.native.guard() is not False)
        packet=self.native.capture();project(packet);self.state['captures'].append(deepcopy(packet));self.save();return project(packet)

    @operation
    def input(self,slot,identifier,action='activate',text=None):
        # An uncertain earlier delivery blocks new input. Only original passive
        # observations may resolve it; the same slot is never dispatched again.
        need(not any(entry['receipt'] is None and entry['resolvedBy'] is None for entry in self.state['inputs']) and not any(entry['slot']==slot for entry in self.state['inputs']))
        reference=self.capture();need(len(self.state['inputs'])<16)
        entry=dict(slot=slot,id=identifier,action=action,text=text,reference=deepcopy(reference),command=None,receipt=None,resolvedBy=None)
        self.state['inputs'].append(entry);self.save()
        def before_send(command):
            need(entry['command'] is None);entry['command']=deepcopy(command);self.save();return True
        self.native.assets_input(identifier,action,reference=reference,text=text,before_send=before_send)
        entry['receipt']=deepcopy(self.native.last_receipt);self.save()

    def _effect(self,entry,current,state):
        command=entry['command'];need(command is not None and current['scope']['instance']==command['instance']
            and current['scope']['lastSequence']==command['sequence'])
        slot=entry['slot'];directory=self.files.state['directory'];url=directory+'/'+BUNDLES[self.files.state['resource']][0]
        if slot=='open-edit-menu':need(any(row['id']=='assets.open' for row in current['controls']))
        elif slot=='open-assets':need(root(current,'page')['visible'])
        elif slot=='open-picker':
            picker=root(current,'picker');need(picker['ownerRootId']==state['page'] and picker['visible'] and not picker['closing'])
        elif slot in ('focus-folder','replace-folder'):
            rows=[row for row in current['controls'] if row['id']=='asset-file.folder'];need(len(rows)==1 and rows[0]['focused'])
            if slot=='replace-folder':need(rows[0]['assetControl']['fieldText']==entry['text'])
        elif slot=='submit-folder':need(root(current,'picker',identifier=state['picker'])['directory']==directory)
        elif slot=='choose-primary':need(root(current,'picker',identifier=state['picker'])['chosen']==[url])
        elif slot=='select-unavailable':self._unavailable(current,state)
        elif slot=='cancel-picker':root(current,'picker',alive=False,identifier=state['picker'])
        elif slot=='close-assets-page':root(current,'page',alive=False,identifier=state['page'])
        else:need(False)

    @operation
    def resolve_pending(self):
        """Observe an uncertain input's actual effect; never dispatch it again."""
        pending=[entry for entry in self.state['inputs'] if entry['receipt'] is None and entry['resolvedBy'] is None]
        need(len(pending)==1);entry=pending[0];current=self.capture();self._effect(entry,current,self.state)
        entry['resolvedBy']=len(self.state['captures'])-1;self.save();return current

    @operation
    def open_page(self):
        need(self.state['phase']=='reserved');current=self.capture()
        need(not any(row['alive'] and row['role'] in ('page','picker') for row in current['inventory']['roots']))
        if not any(row['id']=='assets.open' for row in current['controls']):self.input('open-edit-menu','assets.menu')
        self.input('open-assets','assets.open');current=self.capture();page=root(current,'page')
        need(page['visible'] and page['canWrite'] and not page['busy'] and not page['pendingBundle'] and not page['destinationOpen'])
        self.state['page']=page['rootId'];self.state['phase']='page-open';self.save();return current

    @operation
    def open_picker(self):
        need(self.state['phase']=='page-open');self.input('open-picker','assets.upload');current=self.capture()
        picker=root(current,'picker');need(picker['ownerRootId']==self.state['page'] and picker['visible'] and not picker['closing']
            and not picker['requestId'] and not picker['chosen'] and not picker['bundleReview'])
        self.state['picker']=picker['rootId'];self.state['phase']='picker-open';self.save()
        directory=local(self.files.state['directory'])
        self.input('focus-folder','asset-file.folder');self.input('replace-folder','asset-file.folder','replace',directory)
        current=self.capture();fields=[row for row in current['controls'] if row['id']=='asset-file.folder'];need(len(fields)==1 and fields[0]['assetControl']['fieldText']==directory)
        self.input('submit-folder','asset-file.folder','submit');current=self.capture()
        need(root(current,'picker',identifier=self.state['picker'])['directory']==self.files.state['directory']);return current

    @operation
    def choose_primary(self):
        need(self.state['phase']=='picker-open');current=self.capture();url=self.files.state['directory']+'/'+BUNDLES[self.files.state['resource']][0]
        controls=[row for row in current['controls'] if row['id'].startswith('asset-file.row.') and row['assetControl']['rowUrl']==url]
        need(len(controls)==1);self.input('choose-primary',controls[0]['id']);current=self.capture()
        picker=root(current,'picker',identifier=self.state['picker']);need(picker['chosen']==[url] and not picker['bundleReview'] and not picker['closing'])
        self.state['phase']='primary-chosen';self.save();return current

    @operation
    def retire_and_select(self):
        need(self.state['phase']=='primary-chosen');self.files.retire_primary();return self.select_after_primary()

    @operation
    def select_after_primary(self):
        """Resume from original primary absence without repeating its unlink."""
        need(self.state['phase']=='primary-chosen')
        if self.files.state['phase']=='retiring-primary':self.files.recover_primary()
        need(self.files.state['phase']=='primary-retired');packet=self.files.observe()
        self.state['workBeforeSelect']=deepcopy(packet['source']['work']);self.save();self.input('select-unavailable','asset-file.select')
        return self.observe_unavailable()

    def _unavailable(self,current,state):
        picker=root(current,'picker',identifier=state['picker']);page=root(current,'page',identifier=state['page'])
        need(picker['ownerRootId']==state['page'] and picker['visible'] and not picker['closing'] and picker['error']==ERROR
            and not picker['requestId'] and not picker['bundleReview'] and picker['chosen']==[self.files.state['directory']+'/'+BUNDLES[self.files.state['resource']][0]]
            and not page['busy'] and not page['pendingBundle'] and not page['destinationOpen'] and not page['bundleRequest'])

    @operation
    def observe_unavailable(self):
        need(self.state['phase'] in ('primary-chosen','checking-unavailable','unavailable') and self.files.state['phase']=='primary-retired')
        current=self.capture();self._unavailable(current,self.state);packet=self.files.observe();source=packet['source']
        pending=[entry for entry in self.state['inputs'] if entry['receipt'] is None and entry['resolvedBy'] is None]
        if pending:
            need(len(pending)==1 and pending[0]['slot']=='select-unavailable');self.resolve_pending()
        need(source['ui']['available'] and source['ui']['complete'] and self.state['workBeforeSelect'] is not None
            and same(source['work']['jobs'],self.state['workBeforeSelect']['jobs']))
        independent=dict(current,inventory=source['ui']);self._unavailable(independent,self.state)
        if self.state['phase']!='unavailable':
            self.state['phase']='checking-unavailable';self.save();self._window('negativeWindow','unavailable')
        self.state['phase']='unavailable';self.save();return packet

    def _window_validate(self,window,state,*,complete):
        exact(window,{'kind','requests','hostBrackets'});kind=window['kind']
        need(kind in ('unavailable','cleanup') and type(window['requests']) is list and type(window['hostBrackets']) is list
            and len(window['requests'])==len(window['hostBrackets'])<=64 and len(set(window['requests']))==len(window['requests']))
        originals={entry['query']['commandId']:entry for entry in self.files.state['originals']}
        frames=[];previous_host=None;previous_packet=None;first_jobs=None
        for request,host in zip(window['requests'],window['hostBrackets']):
            exact(host,{'before','after'});need(number(host['before'],0,1e15) and number(host['after'],host['before'],host['before']+1.5))
            entry=originals.get(request);need(entry is not None and entry['query']['operation']=='observe');packet=entry['packet'];source=packet['source']
            if previous_host is not None:
                need(previous_host['after']<=host['before']<=previous_host['after']+.25)
                for key in ('epochMs','monotonicMs'):need(0<=packet['clockBefore'][key]-previous_packet['clockAfter'][key]<=250)
            need(source['ui']['available'] and source['ui']['complete'] and source['work']['available'] and source['work']['complete'])
            files=source['files'];need(files.get('exists') is True and files['retiredPrimary'] and not files['releasing']
                and not files['files'][0]['exists'] and all(row['exists'] for row in files['files'][1:]))
            if first_jobs is None:first_jobs=source['work']['jobs']
            need(same(source['work']['jobs'],first_jobs))
            if kind=='unavailable':
                need(state['workBeforeSelect'] is not None and same(source['work']['jobs'],state['workBeforeSelect']['jobs']))
                self._unavailable(dict(inventory=source['ui']),state)
            else:
                quiet(source);root(dict(inventory=source['ui']),'picker',alive=False,identifier=state['picker'])
                root(dict(inventory=source['ui']),'page',alive=False,identifier=state['page'])
            previous_host,previous_packet=host,packet;frames.append(packet)
        if complete:
            need(len(frames)>=2 and window['hostBrackets'][-1]['before']-window['hostBrackets'][0]['after']>=3)
            for key in ('epochMs','monotonicMs'):need(frames[-1]['clockBefore'][key]-frames[0]['clockAfter'][key]>=3000)
        return frames

    def _window(self,name,kind):
        if self.state[name] is None:self.state[name]=dict(kind=kind,requests=[],hostBrackets=[]);self.save()
        window=self.state[name];need(window['kind']==kind)
        for _ in range(64-len(window['requests'])):
            before=self.monotonic();need(number(before,0,1e15));packet=self.files.observe();after=self.monotonic()
            need(number(after,before,before+1.5));window['requests'].append(packet['requestId']);window['hostBrackets'].append(dict(before=before,after=after))
            self._window_validate(window,self.state,complete=False);self.save()
            if len(window['requests'])>=2:
                frames=self._window_validate(window,self.state,complete=False)
                if (before-window['hostBrackets'][0]['after']>=3
                        and all(packet['clockBefore'][key]-frames[0]['clockAfter'][key]>=3000 for key in ('epochMs','monotonicMs'))):
                    self._window_validate(window,self.state,complete=True);return packet
            self.sleep(.1)
        need(False)

    def _until_dead(self,role,identifier):
        started=last=self.monotonic();need(number(started,0,1e15))
        for attempt in range(61):
            current=self.capture();now=self.monotonic();need(number(now,last,started+1.5) and now-started<1.5);last=now
            found=[row for row in current['inventory']['roots'] if row['role']==role and row['rootId']==identifier]
            need(len(found)==1)
            if found[0]['alive'] is False:return current
            if attempt<60:self.sleep(.025)
        need(False)

    @operation
    def cancel(self):
        need(self.state['phase']=='unavailable');self.state['phase']='canceling';self.save();self.input('cancel-picker','asset-file.cancel')
        return self.recover_cancel()

    @operation
    def recover_cancel(self):
        need(self.state['phase']=='canceling');current=self._until_dead('picker',self.state['picker'])
        if any(entry['receipt'] is None and entry['resolvedBy'] is None for entry in self.state['inputs']):self.resolve_pending()
        packet=self.files.observe();quiet(packet['source']);root(dict(current,inventory=packet['source']['ui']),'picker',alive=False,identifier=self.state['picker'])
        self.state['phase']='picker-closed';self.save();return packet

    @operation
    def close_page(self):
        need(self.state['phase']=='picker-closed');self.state['phase']='closing-page';self.save();self.input('close-assets-page','assets.home')
        return self.recover_close()

    @operation
    def recover_close(self):
        need(self.state['phase']=='closing-page');current=self._until_dead('page',self.state['page'])
        if any(entry['receipt'] is None and entry['resolvedBy'] is None for entry in self.state['inputs']):self.resolve_pending()
        packet=self.files.observe();quiet(packet['source']);root(dict(current,inventory=packet['source']['ui']),'page',alive=False,identifier=self.state['page'])
        self.state['phase']='page-closed';self.save();return packet

    @operation
    def release(self):
        need(self.state['phase']=='page-closed');self._window('cleanupWindow','cleanup');packet=self.files.release();quiet(packet['source'])
        self.state['phase']='retired';self.save();return packet

    @operation
    def recover_release(self):
        need(self.state['phase']=='page-closed' and self.files.state['phase']=='releasing')
        self._window_validate(self.state['cleanupWindow'],self.state,complete=True)
        packet=self.files.recover_release();quiet(packet['source']);current=dict(inventory=packet['source']['ui'])
        root(current,'picker',alive=False,identifier=self.state['picker']);root(current,'page',alive=False,identifier=self.state['page'])
        self.state['phase']='retired';self.save();return packet
