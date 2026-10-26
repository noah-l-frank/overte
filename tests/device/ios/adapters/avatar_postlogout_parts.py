"""Private immutable parts for Avatar postlogout reads; no new native facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from adapters.native_feature_observation import exact,integer,need
from adapters.native_clock_join import digest
from adapters.original_file_reads import record as actual_read
from adapters.original_packet_segments import OriginalPacketSegments
from adapters.script_feature.history import canonical,same


class AvatarPostLogoutSegments(OriginalPacketSegments):
    PROFILE='avatar-postlogout'


class AvatarPostLogoutParts:
    def parts_init(self):
        self.part_slot=None
        self.segments=AvatarPostLogoutSegments(self.root,self.binding,self.run,self.role,self.subject,
            lambda:True,self.part_transition,monotonic=self.monotonic)

    def part_tag(self,index,name):
        return hashlib.sha256(canonical(dict(runId=self.run,role=self.role,subject=self.subject,index=index,part=name))).hexdigest()

    def part_transition(self,parent):
        self.bound();p=self.state['pending'];need(p is not None and self.part_slot is not None)
        self.segments.parent(parent);kind,index=self.part_slot
        need(kind in ('partial','clock','before','after','model'))
        if not parent['chunks']:
            # A parent without a child describes no file or transport. The
            # first planned child carries this entire parent in the same
            # durable metadata write, before OriginalFrameStore can open it.
            current=(p['partialOriginal'] if kind=='partial' else p['parts']['clocks'][index]['packet']
                if kind=='clock' else p['parts'].get(kind))
            need(current is None and not parent['complete'] and parent['first']==self.state['nextSegment'])
            return
        if kind=='partial':p['partialOriginal']=deepcopy(parent)
        elif kind=='clock':p['parts']['clocks'][index]['packet']=deepcopy(parent)
        else:need(kind in ('before','after','model'));p['parts'][kind]=deepcopy(parent)
        if parent['chunks']:
            ref=parent['chunks'][-1]
            if ref['phase']=='planned':need(ref['index']==self.state['nextSegment']);self.state['nextSegment']+=1
            else:need(ref['index']==self.state['nextSegment']-1)
        self.save()

    def remember_part(self,name,value,index=None):
        self.bound();p=self.state['pending'];need(p is not None and self.part_slot is None)
        raw=canonical(value);need(self.state['nextSegment']+max(1,(len(raw)+524287)//524288)-1<=1024)
        self.part_slot=(name,index);tag=self.part_tag(p['index'],name if index is None else 'clock-'+str(index))
        try:return self.segments.write('partial' if name=='partial' else 'parts',tag,raw,self.state['nextSegment'])
        finally:self.part_slot=None

    def part_complete(self,parent):
        if parent is None:return False
        snapshots=self.segments.inspect(parent)
        return len(snapshots)==max(1,(parent['bytes']+524287)//524288) and all(v is not None and v['complete'] for v in snapshots)

    def part_value(self,parent,index,name,*,required=False):
        self.segments.parent(parent);need(parent['label']=='parts' and parent['tag']==self.part_tag(index,name))
        if not self.part_complete(parent):need(not required);return None
        raw=self.segments.read(parent);value=json.loads(raw.decode());need(type(value) is dict and canonical(value)==raw);return value

    def resolved_parts(self,parts,index):
        need(type(parts) is dict and set(parts)<={'before','after','model','modelQuery','modelAcquisition','clocks'});output={}
        for name,value in parts.items():
            if name in ('before','after','model'):
                actual=self.part_value(value,index,name)
                if actual is not None:output[name]=actual
            elif name=='clocks':
                need(type(value) is list and len(value)<=64);output[name]=[]
                for n,row in enumerate(value):
                    exact(row,{'query','packet'});packet=None if row['packet'] is None else self.part_value(row['packet'],index,'clock-'+str(n))
                    output[name].append(dict(query=deepcopy(row['query']),packet=packet))
            else:output[name]=deepcopy(value)
        return output

    def part_parents(self,p):
        parts=p['parts'];parents=[parts[name] for name in ('before','model','after') if name in parts]
        parents += [row['packet'] for row in parts.get('clocks',[]) if row['packet'] is not None]
        parents += [row['parent'] for row in p['orphanPartials']]
        return parents

    def native_file(self,original):
        if original is None:return None
        self.originals.original(original);path=self.originals.path(original)
        if original['phase']=='planned':need(not os.path.lexists(path));return None
        fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(fd,'rb') as stream:
            self.originals.file(path,stream.fileno(),original);raw=stream.read(original['bytes']+1);self.originals.file(path,stream.fileno(),original)
        need(len(raw)<=original['bytes']);actual_read(path)
        complete=len(raw)==original['bytes'] and hashlib.sha256(raw).hexdigest()==original['sha256']
        if original['phase']=='saved':need(complete)
        return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),complete=complete)

    def part_partial(self,p):
        value=dict(avatarPostLogoutPartialVersion=1,index=p['index'],parts=deepcopy(p['parts']),original=deepcopy(p['original']),
            acquisition=deepcopy(p['acquisition']),orphanPartials=deepcopy(p['orphanPartials']))
        value['files']=[self.segments.inspect(parent) for parent in self.part_parents(value)]
        value['originalFile']=self.native_file(value['original']);return value

    def retained_partial(self,value):
        exact(value,{'avatarPostLogoutPartialVersion','index','parts','original','acquisition','orphanPartials','files','originalFile'})
        need(type(value['avatarPostLogoutPartialVersion']) is int and value['avatarPostLogoutPartialVersion']==1 and integer(value['index'],1,64))
        need(type(value['orphanPartials']) is list and len(value['orphanPartials'])<=64)
        for row in value['orphanPartials']:
            exact(row,{'parent','snapshots'});need(row['parent']['label']=='partial' and row['parent']['tag']==self.part_tag(value['index'],'partial'))
            self.segments.retained(row['parent'],row['snapshots'])
        parents=self.part_parents(value);need(type(value['files']) is list and len(parents)==len(value['files']))
        for parent,snapshot in zip(parents,value['files']):self.segments.retained(parent,snapshot)
        need(same(value['originalFile'],self.native_file(value['original'])))
        return value

    def row_partial(self,row):
        if 'parts' in row:return row
        return self.row_material(row)['partial']

    def row_material(self,row,*,check_only=False):
        """Reuse only exact decoded immutable bytes, never a derived verdict."""
        from ios.adapters.avatar_record_cache import AvatarRecordCache
        if not hasattr(self,'part_cache'):
            from ios.adapters.avatar_api_entry import original_cache
            self.part_cache=original_cache('postlogout-parts') or AvatarRecordCache()
        key=dict(context=digest(dict(binding=self.binding,runId=self.run,role=self.role,subject=self.subject,
            root=str(self.root),store=str(self.store.path),inputs=self.inputs)),row=row)
        missing=set()
        def decode():
            value=self.row_partial_original(row);missing.clear()
            for parent in self.part_parents(value):
                for ref in parent['chunks']:
                    if ref['phase']=='planned':missing.add(self.segments.store.path(ref))
            if value['original'] is not None and value['original']['phase']=='planned':missing.add(self.originals.path(value['original']))
            return dict(partial=value,parts=self.resolved_parts(value['parts'],value['index']))
        read=self.part_cache.check if check_only else self.part_cache.read
        return read(key,decode,absent=lambda:missing)

    def row_partial_original(self,row):
        parent=row['partsCarrier'];self.segments.parent(parent)
        need(parent['label']=='partial' and parent['tag']==self.part_tag(row['index'],'partial'))
        raw=self.segments.read(parent);value=json.loads(raw.decode());need(type(value) is dict and canonical(value)==raw)
        self.retained_partial(value);need(value['index']==row['index'] and same(value['original'],row['original']) and same(value['acquisition'],row['acquisition']))
        return value

    def row_parts(self,row):
        if 'partsCarrier' in row:return self.row_material(row)['parts']
        p=self.row_partial(row)
        return self.resolved_parts(p['parts'],p['index']) if 'partsStorageVersion' in row else p['parts']

    def parts_inventory(self,state,materials=None):
        need(integer(state['nextSegment'],1,1025));seen={}
        def admit(parent):
            self.segments.parent(parent)
            for ref in parent['chunks']:
                if ref['index'] in seen:need(same(ref,seen[ref['index']]))
                else:seen[ref['index']]=deepcopy(ref)
        for row in state['rows']:
            if 'partsCarrier' not in row:continue
            value=self.row_partial(row) if materials is None else materials[row['index']]['partial']
            for parent in self.part_parents(value):admit(parent)
            admit(row['partsCarrier'])
        p=state['pending']
        if p is not None and 'partsStorageVersion' in p:
            for parent in self.part_parents(p):admit(parent)
            if p['partialOriginal'] is not None:admit(p['partialOriginal'])
        need(set(seen)==set(range(1,state['nextSegment'])))
