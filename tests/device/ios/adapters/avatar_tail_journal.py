"""Private segmented byte ownership for the version-3 Avatar tail journal.

The mixin supplies storage only; native validation remains in the tail reader.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import time
from adapters.native_feature_observation import integer,need
from adapters.script_feature.history import canonical,same
from ios.adapters.avatar_tail_segments import AvatarTailSegments


class AvatarTailJournal:
    def journal_init(self):
        self.segment_slot=None
        self.segments=AvatarTailSegments(self.root,self.binding,self.run,self.role,self.subject,
            lambda:True,self.segment_intent,
            monotonic=getattr(self,'monotonic',time.monotonic))

    def segment_intent(self,value):
        self.bound();p=self.state['pending'];need(p is not None and self.segment_slot is not None)
        self.segments.parent(value);kind,name=self.segment_slot
        if kind=='raw':
            rows=p['raws'][name]
            if not rows or rows[-1].get('complete') is True:rows.append(deepcopy(value))
            else:rows[-1]=deepcopy(value)
        elif kind=='geometry':
            rows=p['geometryRaws']
            if not rows or rows[-1].get('complete') is True:rows.append(deepcopy(value))
            else:rows[-1]=deepcopy(value)
        else:
            need(kind in ('staged','rowCarrier'));p[kind]=deepcopy(value)
        if value['chunks']:
            ref=value['chunks'][-1]
            if ref['phase']=='planned':
                need(ref['index']==self.state['nextSegment']);self.state['nextSegment']+=1
            else:need(ref['index']==self.state['nextSegment']-1)
        self.save()

    def segment_write(self,kind,name,label,tag,raw):
        self.bound();need(self.segment_slot is None and type(raw) is bytes)
        need(self.state['nextSegment']+max(1,(len(raw)+524287)//524288)-1<=1024);self.segment_slot=(kind,name)
        try:
            value=self.segments.write(label,tag,raw,self.state['nextSegment']);self.bound();return value
        finally:self.segment_slot=None

    def raw_text(self,value):
        if type(value) is str:return value
        return self.segments.read(value).decode('utf-8')

    def complete_raws(self,values):
        """Only actually complete returned bytes can impose a typed source floor."""
        for value in values:
            if type(value) is str:yield value;continue
            snapshots=self.segments.inspect(value)
            if len(snapshots)==max(1,(value['bytes']+524287)//524288) and all(row is not None and row['complete'] for row in snapshots):
                yield self.raw_text(value)

    def partial_parents(self,p):
        if 'tailStorageVersion' not in p:return []
        output=[parent for name in sorted(p['raws']) for parent in p['raws'][name]]
        output+=p['geometryRaws']
        output += [row['parent'] for row in p['orphanCarriers']]
        if p['staged'] is not None:output.append(p['staged'])
        return output

    def row_partial(self,row):
        if 'partial' in row:return deepcopy(row['partial'])
        parent=row['partialCarrier'];need(parent['label']=='partial' and parent['tag']==self.tail_record_tag(row['index']))
        raw=self.segments.read(parent);value=json.loads(raw.decode('utf-8'));need(type(value) is dict and canonical(value)==raw)
        self.segment_snapshots(value);return value

    def segment_snapshots(self,p):
        if 'tailStorageVersion' not in p:return
        need(type(p['tailStorageVersion']) is int and p['tailStorageVersion']==1)
        need(type(p['orphanCarriers']) is list and len(p['orphanCarriers'])<=128)
        for row in p['orphanCarriers']:
            need(type(row) is dict and set(row)=={'parent','snapshots'})
            need(row['parent']['label']=='partial' and row['parent']['tag']==self.tail_record_tag(p['index']))
            self.segments.retained(row['parent'],row['snapshots'])
        parents=self.partial_parents(p);snapshots=p['segmentFiles']
        if p['keyFiles'] is not None:
            need(type(p['keyFiles']) is list and len(p['keyFiles'])==len(p['keyRaws']))
            for original,retained in zip(p['keyRaws'],p['keyFiles']):need(same(self.key_partial(original),retained))
        if snapshots is None:return
        need(type(snapshots) is list and len(snapshots)==len(parents))
        for parent,snapshot in zip(parents,snapshots):self.segments.retained(parent,snapshot)

    def finish_partial(self,p):
        value=deepcopy(p);value['rowCarrier']=None
        value['segmentFiles']=[self.segments.inspect(parent) for parent in self.partial_parents(value)]
        value['keyFiles']=[self.key_partial(original) for original in value['keyRaws']]
        return value

    def key_partial(self,original):
        self.key_originals.original(original)
        if original['phase']=='planned':
            import os
            need(not os.path.lexists(self.key_originals.originals.path(original)));return None
        return self.key_originals.inspect_partial(original)

    def validate_segment_rows(self,state):
        if 'nextSegment' not in state:return
        need(integer(state['nextSegment'],1,1025));seen={}
        def admit(parent):
            self.segments.parent(parent)
            for ref in parent['chunks']:
                index=ref['index']
                if index in seen:need(same(seen[index],ref))
                else:seen[index]=deepcopy(ref)
        for row in state['rows']:
            p=self.row_partial(row)
            for parent in self.partial_parents(p):admit(parent)
            if 'partialCarrier' in row:admit(row['partialCarrier'])
        if state['pending'] is not None:
            p=state['pending']
            for parent in self.partial_parents(p):admit(parent)
            if p.get('rowCarrier') is not None:admit(p['rowCarrier'])
        need(set(seen)==set(range(1,state['nextSegment'])))
