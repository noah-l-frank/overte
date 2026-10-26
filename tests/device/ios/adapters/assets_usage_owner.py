"""Durable ordinary baking/model-dialog input, without backend/render verdicts.

The existing source carrier owns exact clock/UI originals. Mapping reads and
UI resolution cannot establish oven completion, entity creation or rendering.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same,pack,unpack
from feature_journeys.asset_fixture import BUNDLES
from ios.adapters.assets_budget import operation
from ios.adapters.assets_controls import project as controls,identity
from ios.adapters.assets_files import original_bytes
from ios.adapters.assets_picker import root
from ios.adapters.assets_tree_controls import project as tree,ROW
from ios.adapters.assets_upload import OwnedAssetsUpload
from ios.adapters.assets_usage_controls import project as usage,control_id

VERSION=1


class OwnedAssetsUsage:
    def __init__(self,source,store,*,lock):
        need(isinstance(source,OwnedAssetsUpload) and isinstance(store,PrivateFeatureState));lock.assert_held()
        self.source,self.store,self.lock=source,store,lock;self.native,self.monotonic=source.native,source.monotonic
        self.previous=store.read();self.state=None
        if self.previous is not None:self.state=self.decode(self.previous)

    def guard(self):
        self.lock.assert_held();self.source.guard();need(same(self.source.store.read(),self.source.previous));return True

    def path(self):return self.source.state['destination']+BUNDLES[self.source.files.state['resource']][0]
    def url(self):return 'atp:'+self.path()
    def packet(self,index):need(integer(index,1,len(self.source._cached)));return self.source._cached[index-1]['ui']

    def decode(self,value):
        exact(value,{'iosAssetsUsageOwnerVersion','binding','runId','role','fileOwnerToken','page','path','payload'})
        need(type(value['iosAssetsUsageOwnerVersion']) is int and value['iosAssetsUsageOwnerVersion']==VERSION
            and same(value['binding'],self.source.binding) and value['runId']==self.source.files.run and value['role']==self.source.role
            and value['fileOwnerToken']==self.source.files.state['token'] and value['page']==self.source.state['page'] and value['path']==self.path())
        decoded=unpack(value['payload']);need(len(decoded)==1);state=decoded[0];exact(state,{'captures','inputs','reads','clientClosedBy'})
        need(type(state['captures']) is list and len(state['captures'])<=128 and state['captures']==sorted(set(state['captures']))
            and type(state['inputs']) is list and len(state['inputs'])<=24 and type(state['reads']) is list and len(state['reads'])<=12)
        stable=None;previous=None
        for index in state['captures']:
            packet=self.packet(index);roots=[row for row in packet['assetInventory']['roots'] if row['rootId']==value['page'] and row['alive']]
            if roots:
                current=usage(packet,value['page']);identity_fields=tuple(current[key] for key in ('rootId','windowId','treeId','modelId','apiId','clientNodeId','domainId','componentSource'))
                need(stable is None or stable==identity_fields);stable=identity_fields
            current=packet['assetUsageInventory']
            if previous is not None:need(current['instance']==previous['instance'] and current['sequence']>previous['sequence'])
            previous=current
        slots=set()
        for entry in state['inputs']:
            exact(entry,{'slot','id','before','command','receipt','effect','admission','resolvedBy','abandonedBy'})
            need(type(entry['slot']) is str and re.fullmatch('[a-z][a-z0-9-]{0,47}',entry['slot']) is not None and entry['slot'] not in slots
                and entry['before'] in state['captures'] and (control_id(entry['id']) or ROW.fullmatch(entry['id']) is not None));slots.add(entry['slot'])
            packet=self.packet(entry['before']);rows=[row for row in packet['controls'] if row['id']==entry['id']]
            need(len(rows)==1 and rows[0]['assetControl']['rootId']==value['page']);self.admit_input(entry,packet)
            command=entry['command']
            if command is None:need(entry['receipt'] is None and entry['resolvedBy'] is None)
            else:
                exact(command,{'schemaVersion','commandId','instance','sequence','observedElapsedMs','fieldToken','operation'});identity(command['commandId'])
                need(type(command['schemaVersion']) is int and command['schemaVersion']==1 and command['instance']==packet['instance']
                    and type(command['sequence']) is int and command['sequence']==packet['lastSequence']+1
                    and type(command['observedElapsedMs']) is int and command['observedElapsedMs']==packet['elapsedMs']
                    and command['fieldToken']==rows[0]['token'] and command['operation']=='activate')
                if entry['receipt'] is not None:
                    receipt=entry['receipt'];exact(receipt,{'schemaVersion','commandId','status'});status=receipt['status']
                    exact(status,{'schemaVersion','commandId','instance','sequence','performed','processId','sampleEpochMs'})
                    need(type(receipt['schemaVersion']) is type(status['schemaVersion']) is int and receipt['schemaVersion']==status['schemaVersion']==1
                        and type(receipt['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',receipt['commandId']) is not None
                        and status['commandId']==command['commandId'] and status['instance']==command['instance']
                        and type(status['sequence']) is int and status['sequence']==command['sequence'] and status['performed'] is True
                        and type(status['processId']) is int and status['processId']==self.source.clock.pid
                        and integer(status['sampleEpochMs'],packet['sampleEpochMs'],packet['sampleEpochMs']+1500))
            if entry['resolvedBy'] is not None:
                need(entry['resolvedBy'] in state['captures'] and entry['resolvedBy']>entry['before']);self.effect(entry,self.packet(entry['resolvedBy']))
            if entry['abandonedBy'] is not None:need(entry['abandonedBy']==state['clientClosedBy'])
        reads=set()
        for row in state['reads']:
            exact(row,{'slot','capture'});slot=row['slot'];need(slot not in reads and row['capture'] in state['captures']);reads.add(slot)
            proof=self.proof(slot);packet=self.packet(row['capture']);current=usage(packet,value['page'])
            need(current['domainId']==proof['binding']['domainId'] and 0<=packet['sampleEpochMs']-proof['captured']['epochMs']<=1500)
        for entry in state['inputs']:
            if entry['admission'] is not None:
                need(entry['admission'] in state['reads'] and entry['admission']['capture']<=entry['before'])
                proof=self.proof(entry['admission']['slot']);need(0<=self.packet(entry['before'])['sampleEpochMs']-proof['captured']['epochMs']<=1500)
        if state['clientClosedBy'] is not None:
            need(state['clientClosedBy'] in state['captures'] and self.source.state['phase']=='retired')
            root(controls(self.packet(state['clientClosedBy'])),'page',alive=False,identifier=value['page'])
        return state

    def save(self):
        self.guard();need(same(self.store.read(),self.previous))
        value=dict(iosAssetsUsageOwnerVersion=VERSION,binding=self.source.binding,runId=self.source.files.run,role=self.source.role,
            fileOwnerToken=self.source.files.state['token'],page=self.source.state['page'],path=self.path(),payload=pack([self.state]))
        self.decode(value);self.store.write(value,self.previous);self.previous=deepcopy(value)

    @operation
    def reserve(self):
        need(self.state is None and self.source.state is not None and self.source.files.state['resource']=='asset-stand.fbx' and self.source.replies.state['phase']=='open')
        self.state=dict(captures=[],inputs=[],reads=[],clientClosedBy=None);self.save()

    @operation
    def capture(self):
        self.guard();packet=self.source.capture();index=len(self.source.state['frames']);need(index not in self.state['captures'])
        self.state['captures'].append(index);self.save();return packet

    def proof(self,slot):
        need(type(slot) is str and re.fullmatch('usage-[a-z0-9-]{1,36}',slot) is not None)
        proof=self.source.replies.proof(slot);need(proof['kind']=='inventory');wanted=[row for row in proof['mappings'] if row['path']==self.path()]
        raw=original_bytes(self.source.files.state['files'][BUNDLES[self.source.files.state['resource']][0]])
        need(len(wanted)==1 and wanted[0]['hash']==hashlib.sha256(raw).hexdigest());return proof

    @operation
    def read(self,slot):
        need(type(slot) is str and re.fullmatch('usage-[a-z0-9-]{1,36}',slot) is not None)
        jobs=[job for job in self.source.replies.state['jobs'] if job['slot']==slot]
        if not jobs:self.source.replies.read(slot)
        else:
            need(len(jobs)==1)
            if jobs[0]['phase']=='issued':self.source.replies.recover(slot)
        proof=self.proof(slot);packet=self.capture();current=usage(packet,self.source.state['page'])
        need(current['domainId']==proof['binding']['domainId'] and 0<=packet['sampleEpochMs']-proof['captured']['epochMs']<=1500)
        if not any(row['slot']==slot for row in self.state['reads']):self.state['reads'].append(dict(slot=slot,capture=len(self.source.state['frames'])));self.save()
        return proof

    def selected(self,current):need(current['currentPath']==self.path() and current['currentUrl']==self.url() and current['selectedPaths']==[self.path()])

    def admit_input(self,entry,packet):
        current=usage(packet,self.source.state['page']);identifier=entry['id'];effect=entry['effect'];kind=effect.get('kind')
        exact(effect,{'kind'}|({'path'} if kind=='selected' else {'checked'} if kind=='baking-ui' else {'model'} if kind=='accepted-ui' else set()))
        if ROW.fullmatch(identifier):
            need(kind=='selected' and entry['admission'] is None and effect['path'] in (self.source.state['destination'],self.path()))
            row=next(row for row in packet['controls'] if row['id']==identifier)['assetControl']['row'];need(row['model']['path']==effect['path']);return
        self.selected(current)
        if identifier=='assets.model.cancel':need(entry['admission'] is None)
        else:
            need(type(entry['admission']) is dict);exact(entry['admission'],{'slot','capture'})
            proof=self.proof(entry['admission']['slot']);need(current['domainId']==proof['binding']['domainId']
                and 0<=packet['sampleEpochMs']-proof['captured']['epochMs']<=1500)
        if identifier=='assets.baking':
            need(kind=='baking-ui' and type(effect['checked']) is bool and current['permissions']['canWriteAssets'] and not current['busy']
                and current['baking']['enabled'] and current['baking']['checked']!=effect['checked'] and not current['model']['visible'])
        elif identifier in ('assets.import','assets.import-uploaded'):
            need(kind=='model-open' and (current['permissions']['canRez'] or current['permissions']['canRezTmp']) and not current['model']['visible'])
            if identifier=='assets.import-uploaded':need(current['uploadedPrimaryUrl']==self.url())
        elif identifier=='assets.model.accept':
            need(kind=='accepted-ui' and current['model']['visible'] and same(effect['model'],current['model'])
                and current['model']['url']==self.url() and current['model']['shapeIndex']==2 and not current['model']['dynamicChecked']
                and (current['permissions']['canRez'] or current['permissions']['canRezTmp']))
        else:need(identifier=='assets.model.cancel' and kind=='model-closed' and current['model']['visible'])

    def effect(self,entry,packet):
        need(entry['command'] is not None and packet['instance']==entry['command']['instance'] and packet['lastSequence']==entry['command']['sequence'])
        current=usage(packet,self.source.state['page']);kind=entry['effect']['kind']
        if kind=='selected':need(current['currentPath']==entry['effect']['path'] and current['selectedPaths']==[entry['effect']['path']]);return
        self.selected(current)
        if kind=='baking-ui':need(not current['busy'] and current['baking']['checked']==entry['effect']['checked'])
        elif kind=='model-open':need(current['model']['visible'] and current['model']['url']==self.url() and current['model']['shapeIndex']==2 and not current['model']['dynamicChecked'])
        else:need(kind in ('model-closed','accepted-ui') and not current['model']['visible'])

    @operation
    def input(self,slot,identifier,effect,*,cleanup=False):
        need(self.state['clientClosedBy'] is None and not any(entry['slot']==slot for entry in self.state['inputs'])
            and (cleanup and identifier=='assets.model.cancel' or not any(entry['resolvedBy'] is None and entry['abandonedBy'] is None for entry in self.state['inputs'])))
        admission=None
        if ROW.fullmatch(identifier) is None and identifier!='assets.model.cancel':need(self.state['reads']);admission=deepcopy(self.state['reads'][-1])
        packet=self.capture();entry=dict(slot=slot,id=identifier,before=len(self.source.state['frames']),command=None,receipt=None,effect=deepcopy(effect),admission=admission,resolvedBy=None,abandonedBy=None)
        self.admit_input(entry,packet);self.state['inputs'].append(entry);self.save()
        def intent(command):need(entry['command'] is None);entry['command']=deepcopy(command);self.save();return True
        before=self.native.capture;self.native.capture=self.source.capture
        try:self.native.assets_input(identifier,'activate',reference=controls(packet),before_send=intent)
        finally:self.native.capture=before
        entry['receipt']=deepcopy(self.native.last_receipt);self.save();return self.resolve(slot)

    @operation
    def resolve(self,slot):
        entries=[entry for entry in self.state['inputs'] if entry['slot']==slot];need(len(entries)==1 and entries[0]['resolvedBy'] is None)
        packet=self.capture();self.effect(entries[0],packet);entries[0]['resolvedBy']=len(self.source.state['frames']);self.save();return packet

    @operation
    def select(self):
        for number,path in enumerate((self.source.state['destination'],self.path())):
            packet=self.capture();current=tree(packet,self.source.state['page']);rows=[row for row in current['rows'] if row['model']['path']==path];need(len(rows)==1)
            if path.endswith('/') and rows[0]['expanded']:continue
            self.input('usage-select-'+str(number),'assets.tree.row.'+str(rows[0]['index']),dict(kind='selected',path=path))

    @operation
    def baking(self,enabled):
        need(type(enabled) is bool);self.read('usage-bake-'+('on' if enabled else 'off')+'-before')
        return self.input('usage-bake-'+('on' if enabled else 'off'),'assets.baking',dict(kind='baking-ui',checked=enabled))

    @operation
    def open_model(self,*,uploaded=False):
        self.read('usage-import-before');return self.input('usage-open-model','assets.import-uploaded' if uploaded else 'assets.import',dict(kind='model-open'))

    @operation
    def accept_model(self):
        self.read('usage-accept-before');packet=self.capture();current=usage(packet,self.source.state['page']);return self.input('usage-accept-model','assets.model.accept',dict(kind='accepted-ui',model=current['model']))

    @operation
    def cancel_model(self):return self.input('usage-cancel-model','assets.model.cancel',dict(kind='model-closed'),cleanup=True)

    @operation
    def close_clients(self):
        if self.state['clientClosedBy'] is not None:self.decode(self.previous);return
        if self.source.state['phase'] not in ('closing','page-dead','releasing','retired'):
            packet=self.capture();current=usage(packet,self.source.state['page'])
            if current['model']['visible']:self.cancel_model()
        self.source.cleanup(abort=self.source.state['phase']!='uploaded');self.capture();index=len(self.source.state['frames'])
        root(controls(self.packet(index)),'page',alive=False,identifier=self.source.state['page']);self.state['clientClosedBy']=index
        for entry in self.state['inputs']:
            if entry['resolvedBy'] is None:entry['abandonedBy']=index
        self.save()
