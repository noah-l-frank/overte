"""Durable ordinary Browse/Rename/Delete joined to independent mapping reads.

Only namespace mapping effects are established here. Blob/meta/oven/client
mutation-holder retirement needs its original backend owner; capability and
ordinary installed teardown remain closed while that responsibility exists.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same,pack,unpack
from feature_journeys.asset_fixture import BUNDLES
from ios.adapters.assets_budget import operation
from ios.adapters.assets_controls import project as controls,identity
from ios.adapters.assets_picker import root
from ios.adapters.assets_tree_controls import project,inventory,control_id,owned_root
from ios.adapters.assets_upload import OwnedAssetsUpload

VERSION=1
LABELS=('--','Not Baked','Pending','Baking','Baked','Error')
READS=frozenset(('tree-before','tree-rename-admission','tree-renamed','tree-delete-admission','tree-deleted'))


class OwnedAssetsTree:
    def __init__(self,upload,store,*,lock):
        need(isinstance(upload,OwnedAssetsUpload) and isinstance(store,PrivateFeatureState));lock.assert_held()
        self.upload,self.store,self.lock=upload,store,lock;self.native=upload.native;self.monotonic=upload.monotonic
        self.previous=store.read();self.state=None
        if self.previous is not None:self.state=self.decode(self.previous)

    def guard(self):
        self.lock.assert_held();self.upload.guard();need(same(self.upload.store.read(),self.upload.previous));return True

    def decode(self,value):
        exact(value,{'iosAssetsTreeOwnerVersion','runId','role','binding','fileOwnerToken','page','payload'})
        need(type(value['iosAssetsTreeOwnerVersion']) is int and value['iosAssetsTreeOwnerVersion']==VERSION
            and value['runId']==self.upload.files.run and value['role']==self.upload.role and same(value['binding'],self.upload.binding)
            and value['fileOwnerToken']==self.upload.files.state['token'] and value['page']==self.upload.state['page'])
        decoded=unpack(value['payload']);need(len(decoded)==1);state=decoded[0]
        exact(state,{'phase','captures','inputs','reads','clientClosedBy'});need(state['phase'] in ('reserved','browsed','renaming','renamed','deleting','deleted')
            and type(state['captures']) is list and len(state['captures'])<=128 and state['captures']==sorted(set(state['captures']))
            and type(state['inputs']) is list and len(state['inputs'])<=32 and type(state['reads']) is list and len(state['reads'])<=8
            and all(type(slot) is str and slot in READS for slot in state['reads']) and len(state['reads'])==len(set(state['reads'])))
        previous=None;stable=None
        for index in state['captures']:
            packet=self.packet(index);inventory(packet['assetTreeInventory'],pid=self.upload.clock.pid,ui=packet['assetInventory'])
            if previous is not None:
                old,new=previous['assetTreeInventory'],packet['assetTreeInventory'];need(old['instance']==new['instance'] and new['sequence']>old['sequence'])
            alive=[item for item in packet['assetInventory']['roots'] if item['rootId']==value['page'] and item['alive']]
            if alive:
                page=project(packet,value['page']);current=tuple(page[key] for key in ('rootId','windowId','treeId','modelId','componentSource'))
                need(stable is None or current==stable);stable=current
            previous=packet
        slots=set()
        for entry in state['inputs']:
            exact(entry,{'slot','id','action','text','before','command','receipt','effect','resolvedBy','abandonedBy'})
            need(type(entry['slot']) is str and re.fullmatch('[a-z][a-z0-9-]{0,47}',entry['slot']) and entry['slot'] not in slots
                and control_id(entry['id']) and entry['action'] in ('activate','replace') and entry['before'] in state['captures'])
            slots.add(entry['slot']);packet=self.packet(entry['before']);reference=controls(packet);targets=[row for row in reference['controls'] if row['id']==entry['id']]
            need(len(targets)==1 and targets[0]['assetControl']['rootId']==value['page'])
            if entry['action']=='replace':need(entry['id']=='assets.rename.path');owned_root(entry['text'])
            else:need(entry['text'] is None)
            command=entry['command']
            if command is None:need(entry['receipt'] is None and entry['resolvedBy'] is None)
            else:
                exact(command,{'schemaVersion','commandId','instance','sequence','observedElapsedMs','fieldToken','operation'}|({'text'} if entry['action']=='replace' else set()))
                identity(command['commandId']);need(type(command['schemaVersion']) is int and command['schemaVersion']==1 and command['instance']==packet['instance']
                    and type(command['sequence']) is int and command['sequence']==packet['lastSequence']+1
                    and command['observedElapsedMs']==packet['elapsedMs'] and type(command['observedElapsedMs']) is int
                    and command['fieldToken']==targets[0]['token'] and command['operation']==entry['action'])
                if entry['action']=='replace':need(command['text']==entry['text'])
                if entry['receipt'] is not None:
                    receipt=entry['receipt'];exact(receipt,{'schemaVersion','commandId','status'});status=receipt['status']
                    exact(status,{'schemaVersion','commandId','instance','sequence','performed','processId','sampleEpochMs'})
                    need(receipt['schemaVersion']==status['schemaVersion']==1 and status['performed'] is True and status['commandId']==command['commandId']
                        and status['instance']==command['instance'] and status['sequence']==command['sequence'] and status['processId']==self.upload.clock.pid
                        and packet['sampleEpochMs']<=status['sampleEpochMs']<=packet['sampleEpochMs']+1500)
            if entry['resolvedBy'] is not None:
                need(entry['resolvedBy'] in state['captures'] and entry['resolvedBy']>entry['before']);self.effect(entry,self.packet(entry['resolvedBy']))
            if entry['abandonedBy'] is not None:
                need(entry['abandonedBy']==state['clientClosedBy']);root(controls(self.packet(entry['abandonedBy'])),'page',alive=False,identifier=value['page'])
        if state['phase'] in ('browsed','renaming','renamed','deleting','deleted'):
            self.baseline(self.read_proof('tree-before'));self.resolved(state,'browse-primary')
        if state['phase'] in ('renamed','deleting','deleted'):
            admission=self.read_proof('tree-rename-admission');self.baseline(admission)
            self.renamed_proof(admission,self.read_proof('tree-renamed'));self.read_after_input(state,'confirm-rename','tree-rename-admission','tree-renamed');self.resolved(state,'renamed-primary')
        if state['phase']=='deleted':
            admission=self.read_proof('tree-delete-admission');self.delete_admission(admission)
            self.deleted_proof(admission,self.read_proof('tree-deleted'));self.read_after_input(state,'confirm-delete','tree-delete-admission','tree-deleted')
        if state['clientClosedBy'] is not None:
            need(state['clientClosedBy'] in state['captures'] and self.upload.state['phase']=='retired')
            root(controls(self.packet(state['clientClosedBy'])),'page',alive=False,identifier=value['page'])
        return state

    def packet(self,index):
        need(integer(index,1,len(self.upload._cached)));return self.upload._cached[index-1]['ui']

    def save(self):
        self.guard();need(same(self.store.read(),self.previous))
        value=dict(iosAssetsTreeOwnerVersion=VERSION,runId=self.upload.files.run,role=self.upload.role,binding=self.upload.binding,
            fileOwnerToken=self.upload.files.state['token'],page=self.upload.state['page'],payload=pack([self.state]))
        self.decode(value);self.store.write(value,self.previous);self.previous=deepcopy(value)

    @operation
    def reserve(self):
        need(self.state is None and self.upload.state['phase']=='uploaded' and self.upload.replies.state['phase']=='open')
        self.state=dict(phase='reserved',captures=[],inputs=[],reads=[],clientClosedBy=None);self.save()

    @operation
    def capture(self):
        self.guard();packet=self.upload.capture();index=len(self.upload.state['frames']);need(index not in self.state['captures'])
        self.state['captures'].append(index);self.save();return packet

    def page(self,packet=None):return project(self.capture() if packet is None else packet,self.upload.state['page'])
    def prefix(self,renamed=False):return '/'+('renamed-' if renamed else 'e2e-')+self.upload.files.run+'/'

    def resolved(self,state,slot):
        entries=[entry for entry in state['inputs'] if entry['slot']==slot];need(len(entries)==1 and entries[0]['resolvedBy'] is not None);return entries[0]

    def read_after_input(self,state,slot,admission,after):
        entry=self.resolved(state,slot);need(self.read_proof(admission)['captured']['epochMs']<=self.packet(entry['before'])['sampleEpochMs']
            and self.read_proof(after)['captured']['epochMs']>=self.packet(entry['resolvedBy'])['sampleEpochMs'])

    def baseline(self,proof):
        owned=[row for row in proof['mappings'] if row['path'].startswith(self.prefix())]
        need(same(owned,self.upload.state['readback']['mappings']) and not any(row['path'].startswith(self.prefix(True)) for row in proof['mappings']))

    def renamed_proof(self,before,after):
        expected=[dict(row,path=self.prefix(True)+row['path'][len(self.prefix()):]) if row['path'].startswith(self.prefix()) else row for row in before['mappings']]
        need(sorted(expected,key=lambda row:row['path'].encode('utf-16be'))==after['mappings'])

    def delete_admission(self,proof):
        original=self.read_proof('tree-renamed');need([row for row in proof['mappings'] if row['path'].startswith(self.prefix(True))]
            ==[row for row in original['mappings'] if row['path'].startswith(self.prefix(True))] and not any(row['path'].startswith(self.prefix()) for row in proof['mappings']))

    def deleted_proof(self,before,after):
        need(after['mappings']==[row for row in before['mappings'] if not row['path'].startswith(self.prefix(True))]
            and not any(row['path'].startswith((self.prefix(),self.prefix(True))) for row in after['mappings']))

    def effect(self,entry,packet):
        need(entry['command'] is not None and packet['instance']==entry['command']['instance'] and packet['lastSequence']==entry['command']['sequence'])
        actual=self.page(packet);effect=entry['effect'];kind=effect.get('kind')
        exact(effect,{'kind'}|({'path'} if kind=='selected' else set()))
        if kind=='selected':need(effect['path'].startswith((self.prefix(),self.prefix(True))) and actual['currentPath']==effect['path'] and actual['selectedPaths']==[effect['path']])
        elif kind=='rename-open':need(actual['renameVisible'] and actual['selectedPaths']==[self.prefix()])
        elif kind=='rename-focus':
            rows=[row for row in packet['controls'] if row['id']=='assets.rename.path'];need(len(rows)==1 and rows[0]['focused'])
        elif kind=='rename-text':need(actual['renameVisible'] and actual['renameText']==entry['text'])
        elif kind in ('renamed','deleted'):
            need(not actual['busy'] and not actual['renameVisible'] and not actual['deleteVisible'])
            old=[row for row in actual['modelRows'] if row['path'].startswith(self.prefix())];new=[row for row in actual['modelRows'] if row['path'].startswith(self.prefix(True))]
            need(not old)
            if kind=='deleted':need(not new)
            else:need({row['path'][len(self.prefix(True)):] for row in new if not row['folder']}==set(BUNDLES[self.upload.files.state['resource']][1]))
        elif kind=='delete-open':need(actual['deleteVisible'] and actual['selectedPaths']==[self.prefix(True)])
        elif kind=='rename-canceled':need(not actual['renameVisible'])
        elif kind=='delete-canceled':need(not actual['deleteVisible'])
        else:need(False)

    @operation
    def input(self,slot,identifier,effect,*,action='activate',text=None,cleanup=False):
        need(not any(entry['slot']==slot for entry in self.state['inputs']) and len(self.state['inputs'])<32)
        need(cleanup and identifier in ('assets.rename.cancel','assets.delete.cancel') or not any(entry['resolvedBy'] is None and entry['abandonedBy'] is None for entry in self.state['inputs']))
        packet=self.capture();actual=self.page(packet)
        if identifier.startswith('assets.tree.row.'):
            target=next(row for row in packet['controls'] if row['id']==identifier)['assetControl']['row'];need(target['model']['path'].startswith((self.prefix(),self.prefix(True))))
        elif identifier.startswith('assets.rename') and not identifier.endswith('.cancel'):
            need(actual['selectedPaths']==[self.prefix()] and actual['currentPath']==self.prefix())
            if action=='replace':need(text==self.prefix(True))
            if identifier.endswith('.accept'):need(self.state['phase']=='renaming' and actual['renameText']==self.prefix(True));self.baseline(self.read_proof('tree-rename-admission'))
        elif identifier.startswith('assets.delete') and not identifier.endswith('.cancel'):
            need(actual['selectedPaths']==[self.prefix(True)] and actual['currentPath']==self.prefix(True))
            if identifier.endswith('.accept'):need(self.state['phase']=='deleting');self.delete_admission(self.read_proof('tree-delete-admission'))
        entry=dict(slot=slot,id=identifier,action=action,text=text,before=len(self.upload.state['frames']),command=None,receipt=None,
            effect=deepcopy(effect),resolvedBy=None,abandonedBy=None);self.state['inputs'].append(entry);self.save()
        def intent(command):need(entry['command'] is None);entry['command']=deepcopy(command);self.save();return True
        before=self.native.capture;self.native.capture=self.upload.capture
        try:self.native.assets_input(identifier,action,reference=controls(packet),text=text,before_send=intent)
        finally:self.native.capture=before
        entry['receipt']=deepcopy(self.native.last_receipt);self.save();return self.resolve(slot)

    @operation
    def resolve(self,slot):
        matches=[entry for entry in self.state['inputs'] if entry['slot']==slot];need(len(matches)==1);entry=matches[0];need(entry['resolvedBy'] is None)
        packet=self.capture();self.effect(entry,packet);entry['resolvedBy']=len(self.upload.state['frames']);self.save();return packet

    def row(self,actual,path):
        rows=[row for row in actual['rows'] if row['model']['path']==path];need(len(rows)==1);return 'assets.tree.row.'+str(rows[0]['index'])

    def select(self,path,slot):
        parts=path.strip('/').split('/');ancestors=['/'+ '/'.join(parts[:count])+'/' for count in range(1,len(parts))]
        for depth,parent in enumerate(ancestors):
            actual=self.page();rows=[row for row in actual['rows'] if row['model']['path']==parent];need(len(rows)==1)
            if not rows[0]['expanded']:self.input(slot+'-expand-'+str(depth),self.row(actual,parent),dict(kind='selected',path=parent))
        actual=self.page();return self.input(slot,self.row(actual,path),dict(kind='selected',path=path))

    def read_proof(self,slot):
        proof=self.upload.replies.proof(slot);need(proof['kind']=='inventory' and proof['binding']==self.upload.state['readback']['binding']);return proof

    @operation
    def read(self,slot):
        need(slot in READS)
        if slot not in self.state['reads']:self.state['reads'].append(slot);self.save()
        jobs=[job for job in self.upload.replies.state['jobs'] if job['slot']==slot]
        if not jobs:self.upload.replies.read(slot)
        elif jobs[0]['phase']=='issued':self.upload.replies.recover(slot)
        else:need(jobs[0]['phase']=='complete')
        proof=self.read_proof(slot)
        # Reusing an owned completed job is historical recovery only; its
        # old reply cannot become a fresh checkpoint after a long interruption.
        current=self.upload.capture();need(0<=current['sampleEpochMs']-proof['captured']['epochMs']<=1500)
        return proof

    def joined(self,proof,actual,renamed=False):
        prefix=self.prefix(renamed);wanted=[row for row in proof['mappings'] if row['path'].startswith(prefix)]
        observed=[row for row in actual['modelRows'] if row['path'].startswith(prefix) and not row['folder']]
        need({row['path'] for row in wanted}=={row['path'] for row in observed})
        for row in observed:
            original=next(item for item in wanted if item['path']==row['path']);need(row['status']==LABELS[original['status']] and row['bakingErrors']==original['bakingErrors'])
        return wanted

    @operation
    def browse(self):
        need(self.state['phase']=='reserved');before=self.read('tree-before');actual=self.page()
        self.joined(before,actual);self.baseline(before)
        self.select(self.prefix()+BUNDLES[self.upload.files.state['resource']][0],'browse-primary');self.state['phase']='browsed';self.save()

    @operation
    def finish_browse(self):
        need(self.state['phase']=='reserved');self.baseline(self.read('tree-before'))
        pending=[entry for entry in self.state['inputs'] if entry['resolvedBy'] is None and entry['abandonedBy'] is None]
        if pending:need(len(pending)==1 and pending[0]['effect']['kind']=='selected');self.resolve(pending[0]['slot'])
        self.once_selected(self.prefix()+BUNDLES[self.upload.files.state['resource']][0],'browse-primary');self.state['phase']='browsed';self.save()

    def once_selected(self,path,slot):
        entries=[entry for entry in self.state['inputs'] if entry['slot']==slot]
        if not entries:return self.select(path,slot)
        need(len(entries)==1)
        if entries[0]['resolvedBy'] is None:self.resolve(slot)
        actual=self.page();need(actual['currentPath']==path and actual['selectedPaths']==[path])

    @operation
    def rename(self):
        need(self.state['phase']=='browsed');self.select(self.prefix(),'rename-root');self.input('open-rename','assets.rename',dict(kind='rename-open'))
        self.input('focus-rename','assets.rename.path',dict(kind='rename-focus'));self.input('replace-rename','assets.rename.path',dict(kind='rename-text'),action='replace',text=self.prefix(True))
        self.baseline(self.read('tree-rename-admission'));self.state['phase']='renaming';self.save();self.input('confirm-rename','assets.rename.accept',dict(kind='renamed'));return self.finish_rename()

    @operation
    def finish_rename(self):
        need(self.state['phase']=='renaming');pending=[entry for entry in self.state['inputs'] if entry['resolvedBy'] is None and entry['abandonedBy'] is None]
        if pending:need(len(pending)==1 and pending[0]['slot']=='confirm-rename');self.resolve('confirm-rename')
        before=self.read_proof('tree-rename-admission');after=self.read('tree-renamed');self.renamed_proof(before,after);self.joined(after,self.page(),True)
        self.once_selected(self.prefix(True)+BUNDLES[self.upload.files.state['resource']][0],'renamed-primary');self.state['phase']='renamed';self.save();return after

    @operation
    def delete(self):
        need(self.state['phase']=='renamed');self.select(self.prefix(True),'delete-root');self.input('open-delete','assets.delete',dict(kind='delete-open'))
        self.delete_admission(self.read('tree-delete-admission'));self.state['phase']='deleting';self.save();self.input('confirm-delete','assets.delete.accept',dict(kind='deleted'));return self.finish_delete()

    @operation
    def finish_delete(self):
        need(self.state['phase']=='deleting');pending=[entry for entry in self.state['inputs'] if entry['resolvedBy'] is None and entry['abandonedBy'] is None]
        if pending:need(len(pending)==1 and pending[0]['slot']=='confirm-delete');self.resolve('confirm-delete')
        before=self.read_proof('tree-delete-admission');after=self.read('tree-deleted');self.deleted_proof(before,after)
        self.joined(after,self.page(),True);self.state['phase']='deleted';self.save();return after

    @operation
    def close_clients(self):
        if self.state['clientClosedBy'] is not None:self.decode(self.previous);return
        if self.upload.state['phase'] not in ('closing','page-dead','releasing','retired'):
            actual=self.page()
            if actual['renameVisible']:self.input('cleanup-rename','assets.rename.cancel',dict(kind='rename-canceled'),cleanup=True)
            if actual['deleteVisible']:self.input('cleanup-delete','assets.delete.cancel',dict(kind='delete-canceled'),cleanup=True)
        self.upload.cleanup(abort=self.state['phase']!='deleted');self.capture();index=len(self.upload.state['frames'])
        root(controls(self.packet(index)),'page',alive=False,identifier=self.upload.state['page']);self.state['clientClosedBy']=index
        for entry in self.state['inputs']:
            if entry['resolvedBy'] is None:entry['abandonedBy']=index
        self.save()
