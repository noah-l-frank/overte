"""Ordinary Create-token removal of the actually adopted Assets Model.

This child observes local entity/Model disposal and retained cached resources.
It does not retire the old picker, parent page, remote entity or any cache.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import uuid
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack,same
from ios.adapters import create_controls_v2 as controls,create_state
from ios.adapters.assets_budget import operation
from ios.adapters.assets_parsed_owner import OwnedAssetsParsedInput
from ios.adapters.create_action_owner import intent as input_intent,receipt as input_receipt
from ios.adapters.create_inputs import IOSCreateUI

VERSION=1


class RemovalIO:
    def __init__(self,owner):self.owner=owner
    def capture(self):return controls.project(self.owner.capture_ui())
    def input(self,identifier,action,reference,value=None):
        owner=self.owner;current=self.capture();row=controls.same_reference(reference,current,identifier);scope=current['scope']
        command=dict(schemaVersion=1,commandId=str(uuid.uuid4()),instance=scope['instance'],sequence=scope['sequence']+1,
            observedElapsedMs=scope['elapsedMs'],fieldToken=row['token'],operation=action)
        if action=='replace':command['text']=value
        elif action=='select-index':command['index']=value
        elif action=='scroll':command['direction']=value
        event=dict(before=owner.last_ui,controlId=identifier,action=action,value=value,command=command,receipt=None,observed=None)
        owner.admit(event);need(not owner.state['inputs'] or owner.state['inputs'][-1]['observed'] is not None)
        need(len(owner.state['inputs'])<48);owner.state['inputs'].append(event);owner.save()
        owner.native.deliver(command,before_send=owner.guard)
        event['receipt']=deepcopy(owner.native.last_receipt);input_receipt(event['receipt'],owner.intended(event),owner.pid);owner.save()
        # IOSCreateUI.input immediately performs its existing fresh after-read.
        # That read adopts this exact ACK/sequence in capture_ui(); acquiring
        # the same post-input UI here first duplicates history, not evidence.
        return dict(performed=True)
    def activate(self,identifier,*,reference):return self.input(identifier,'activate',reference)
    def replace(self,identifier,value,*,reference):return self.input(identifier,'replace',reference,value)
    def select_index(self,identifier,value,*,reference):return self.input(identifier,'select-index',reference,value)
    def scroll(self,identifier,value,*,reference):return self.input(identifier,'scroll',reference,value)


class OwnedAssetsModelRemoval:
    def __init__(self,parsed,store,*,lock):
        need(isinstance(parsed,OwnedAssetsParsedInput) and isinstance(store,PrivateFeatureState));lock.assert_held()
        self.parsed,self.model,self.sources,self.store,self.lock=parsed,parsed.model,parsed.sources,store,lock
        self.usage=self.model.usage;self.native=self.usage.native;self.pid=self.sources.native.pid;self.monotonic=self.sources.monotonic
        self.previous=store.read();self.state=None;self.last_ui=None
        self.ui=IOSCreateUI(RemovalIO(self),lambda _summary:None,monotonic=self.monotonic,sleep=self.native.sleep)
        if self.previous is not None:self.state=self.decode(self.previous)

    def guard(self):
        self.lock.assert_held();self.parsed.guard();need(same(self.store.read(),self.previous));return True
    def target(self):return self.model.state['creation']['proof']['entityId']
    def packet(self,index):need(integer(index,1,len(self.usage.source._cached)));return self.usage.source._cached[index-1]['ui']
    def frame(self,index):
        rows=[frame for ref,frame in zip(self.sources.state['frames'],self.sources._cached) if self.sources.originals.expand(ref)['index']==index]
        need(len(rows)==1);return rows[0]
    def intended(self,event):
        packet=self.packet(event['before'])
        return dict(reference=controls.project(packet),admission=packet,controlId=event['controlId'],action=event['action'],value=event['value'],command=event['command'])

    def admit(self,event):
        input_intent(self.intended(event),self.pid);id_=event['controlId']
        fixed={'tablet.home','create.entry','create.tab.1','create.tab.2','create.refresh','create.filter','create.scrollbar','create.delete','create.entity.'+self.target()}
        need(id_ in fixed or id_.startswith('tablet.page.') and id_.rsplit('.',1)[1].isdigit())
        if id_=='create.filter':need(event['action'] in ('activate','replace') and (event['action']!='replace' or event['value']==''))
        elif id_=='create.scrollbar':need(event['action']=='scroll' and event['value'] in ('up','down'))
        else:need(event['action']=='activate' and event['value'] is None)
        if id_=='create.delete':
            page=next(row for row in controls.project(self.packet(event['before']))['controls'] if row['id']=='create.page')
            need(page['selectedIds']==[self.target()])

    def envelope(self):
        source=self.usage.source
        return dict(iosAssetsModelRemovalVersion=VERSION,binding=source.binding,runId=source.files.run,role=source.role,
            fileOwnerToken=source.files.state['token'],page=source.state['page'],entityId=self.target(),payload=pack([self.state]))

    def decode(self,value):
        source=self.usage.source
        exact(value,{'iosAssetsModelRemovalVersion','binding','runId','role','fileOwnerToken','page','entityId','payload'})
        need(type(value['iosAssetsModelRemovalVersion']) is int and value['iosAssetsModelRemovalVersion']==VERSION and same(value['binding'],source.binding)
            and value['runId']==source.files.run and value['role']==source.role and value['fileOwnerToken']==source.files.state['token']
            and value['page']==source.state['page'] and value['entityId']==self.target())
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'phase','baseline','editor','inputs','observations','result','contextClosedBy'})
        need(state['phase'] in ('reserved','opening','selecting','deleting','model-gone') and type(state['inputs']) is list and len(state['inputs'])<=48
            and type(state['observations']) is list and len(state['observations'])<=16 and state['observations']==sorted(set(state['observations'])))
        if state['baseline'] is not None:self.frame(state['baseline'])
        else:need(state['phase']=='reserved' and not state['inputs'] and not state['observations'])
        if state['editor'] is not None:create_state.uuid(state['editor'])
        elif state['phase'] in ('selecting','deleting','model-gone'):need(False)
        commands=set();last_after=0
        for position,event in enumerate(state['inputs']):
            exact(event,{'before','controlId','action','value','command','receipt','observed'});self.admit(event)
            need(event['before']>=last_after and event['command']['commandId'] not in commands);commands.add(event['command']['commandId'])
            if event['receipt'] is not None:input_receipt(event['receipt'],self.intended(event),self.pid)
            if event['observed'] is not None:
                after=controls.project(self.packet(event['observed']));before=controls.project(self.packet(event['before']))
                need(event['observed']>event['before'] and all(after['scope'][key]==before['scope'][key] for key in ('instance','generation','processId'))
                    and after['scope']['sequence']==event['command']['sequence'])
                last_after=event['observed']
            else:need(position==len(state['inputs'])-1)
        for index in state['observations']:need(state['baseline'] is not None and index>state['baseline']);self.frame(index)
        if state['result'] is not None:need(state['phase']=='model-gone' and same(state['result'],self.removed(state)))
        if state['phase']=='model-gone':
            need(state['result'] is not None and all(row['observed'] is not None or row['controlId']=='tablet.home' for row in state['inputs']))
        if state['contextClosedBy'] is not None:
            need(state['phase']=='model-gone');frame=self.frame(state['contextClosedBy']);roots=frame['originals']['createAfter']['source']['roots']
            rows=[row for row in roots if row['id']==state['editor']];need(len(rows)==1 and (rows[0]['destroyed'] or not rows[0]['active']))
        return state

    def save(self):
        self.guard();value=self.envelope();self.store.write(value,self.previous);self.previous=deepcopy(value)

    def capture_ui(self):
        packet=self.usage.capture();self.last_ui=len(self.usage.source._cached)
        if self.state is not None and self.state['inputs']:
            event=self.state['inputs'][-1]
            if event['observed'] is None and event['receipt'] is not None:
                need(controls.project(packet)['scope']['sequence']==event['command']['sequence']);event['observed']=self.last_ui;self.save()
        return packet

    def capture_source(self):
        if self.sources.state['pending'] is not None:self.sources.recover_capture()
        else:self.sources.capture(self.sources.epoch_ms())
        return self.sources.originals.expand(self.sources.state['frames'][-1])['index']

    @operation
    def reserve(self):
        need(self.state is None and self.parsed.state['phase']=='observed')
        self.parsed.decode(self.parsed.previous)
        self.state=dict(phase='reserved',baseline=None,editor=None,inputs=[],observations=[],result=None,contextClosedBy=None);self.save()

    @operation
    def recover(self):
        self.guard();need(self.state is not None and self.state['inputs']);event=self.state['inputs'][-1]
        need(event['observed'] is None);packet=self.capture_ui();after=controls.project(packet)
        need(after['scope']['sequence']==event['command']['sequence']);id_=event['controlId'];rows={row['id']:row for row in after['controls']}
        page=rows.get('create.page')
        if id_=='create.delete':
            index=self.capture_source();self.state['observations'].append(index);self.save();proof=self.removed()
            self.state.update(phase='model-gone',result=proof)
        elif id_=='tablet.home':
            need(page is None and any(row['id']=='create.entry' or row['id'].startswith('tablet.page.') for row in after['controls']))
            roots=packet['assetInventory']['roots'];need(any(row['rootId']==self.usage.source.state['page'] and not row['alive'] for row in roots))
        elif id_=='create.entry':need(page is not None)
        elif id_.startswith('create.tab.'):need(page is not None and page['tab']==int(id_.rsplit('.',1)[1]))
        elif id_.startswith('create.entity.'):need(page is not None and page['selectedIds']==[self.target()])
        elif id_=='create.refresh':need(page is not None)
        elif id_=='create.filter':
            need(id_ in rows and (rows[id_]['text']==event['value'] if event['action']=='replace' else rows[id_]['focused']))
        else:need(False)
        event['observed']=self.last_ui;self.save();self.decode(self.previous)

    def removed(self,state=None):
        state=self.state if state is None else state;need(state['baseline'] is not None and state['observations'])
        before=self.frame(state['baseline'])['originals']['createAfter'];last=self.frame(state['observations'][-1])['originals'];after=last['createAfter']
        id_=self.target();old={row['id']:row for row in before['source']['tree']['entities']};new={row['id']:row for row in after['source']['tree']['entities']}
        need(id_ in old and id_ not in new and set(new)==set(old)-{id_} and all(same(row,new[key]) for key,row in old.items() if key!=id_))
        life=last['work']['source']['entityLifetimes'];need(life['complete']);entries=[row for row in life['entities'] if row['id']==id_]
        need(len(entries)==1 and entries[0]['destroyed'] and entries[0]['models'] and all(row['destroyed'] for row in entries[0]['models']))
        packet=last['origin'];history=packet['source']['history']
        # Both validated histories retain the same original QObject/HFM
        # observations. Geometry3 adds its separate weak consumer inventory.
        need(type(history['assetModelOriginHistoryVersion']) is int and history['assetModelOriginHistoryVersion'] in (2,3))
        original=self.parsed.frame(self.parsed.state['sourceIndex'])['originals']['origin'];known={row['id'] for row in original['source']['history']['downloads']}
        resources=[dict(id=row['id'],originalLeaseAlive=row['resourceAlive'],objectAlive=row['resourceObjectAlive'],hfmAlive=row['parsedModelAlive'])
            for row in history['downloads'] if row['id'] in known];need(len(resources)==len(known))
        deleted=[event for event in state['inputs'] if event['controlId']=='create.delete'];need(len(deleted)==1)
        return dict(assetModelRemovalObservationVersion=VERSION,entityId=id_,inputCommandId=deleted[0]['command']['commandId'],requestId=after['requestId'],
            workRequestId=last['work']['requestId'],originRequestId=packet['requestId'],resources=resources,resourceRetirementAvailable=False)

    @operation
    def remove(self):
        self.guard();need(self.state is not None);self.decode(self.previous)
        if self.state['phase']=='model-gone':return deepcopy(self.state['result'])
        need(not self.state['inputs'] or self.state['inputs'][-1]['observed'] is not None)
        if self.state['phase']=='reserved':
            index=self.capture_source();native=self.frame(index)['originals']['createAfter']
            # This first route admits only a fresh editor context; an existing
            # editor's selection/drafts need a separate exact restoration path.
            need(not any(row['kind']=='editor' and not row['destroyed'] for row in native['source']['roots']))
            self.state.update(phase='opening',baseline=index);self.save()
        if self.state['phase']=='opening':
            current=self.ui.capture()
            if self.ui.row(current,'create.page',enabled=False) is None:self.ui.open_create()
            index=self.capture_source();roots=self.frame(index)['originals']['createAfter']['source']['roots']
            editors=[row for row in roots if row['kind']=='editor' and row['active'] and not row['destroyed']];need(len(editors)==1)
            self.state.update(phase='selecting',editor=editors[0]['id']);self.save()
        if self.state['phase']=='selecting':
            if self.ui.selected()!=[self.target()]:self.ui.select_entity(self.target())
            need(self.ui.selected()==[self.target()])
            self.state['phase']='deleting';self.save();self.ui.delete_entity()
        need(self.state['phase']=='deleting')
        for _ in range(16):
            index=self.capture_source();self.state['observations'].append(index);self.save()
            try:proof=self.removed()
            except RuntimeError:self.native.sleep(.1);continue
            self.state.update(phase='model-gone',result=proof);self.save();self.decode(self.previous);return deepcopy(proof)
        need(False)

    @operation
    def close_context(self):
        self.guard();need(self.state['phase']=='model-gone')
        if self.state['contextClosedBy'] is not None:self.decode(self.previous);return self.state['contextClosedBy']
        need(not self.state['inputs'] or self.state['inputs'][-1]['observed'] is not None)
        current=self.ui.capture()
        if self.ui.row(current,'create.page',enabled=False) is not None:self.ui.input('tablet.home')
        index=self.capture_source();roots=self.frame(index)['originals']['createAfter']['source']['roots'];rows=[row for row in roots if row['id']==self.state['editor']]
        need(len(rows)==1 and (rows[0]['destroyed'] or not rows[0]['active']))
        self.state['contextClosedBy']=index;self.save();self.decode(self.previous);return index

    @operation
    def close_parent_clients(self):
        need(self.state['contextClosedBy'] is not None)
        # The actual child Home input and separate original source prove the
        # old Assets root is gone. Parent cleanup independently re-observes
        # that root, actual upload holders and the native/host file quiet span.
        self.usage.source.cleanup(abort=self.usage.source.state['phase']!='uploaded');self.usage.close_clients();self.guard()
