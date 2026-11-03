"""Assets reply query custody in the existing action/OriginalFrame architecture.

A new read job uses the actual current action ticket. Inspect/retire keeps its
original job ticket and separately binds the current cleanup action. No native
result, delivery, absence or complete action is manufactured by this owner.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import secrets
import time
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same,pack,unpack
from feature_journeys.phase_fixture import validate as phase_original
from ios.adapters.assets_action_phase import AssetsActionPhases,AssetsActionScope
from ios.adapters.assets_episodes import AssetsEpisodeScope
from ios.adapters.assets_model_sources import AssetsModelSources
from ios.adapters import assets_replies as replies


class AssetsReplyActionSources:
    def __init__(self,owner,actions,episode,action=None,*,metadata=None):
        from ios.adapters.assets_end_metadata import store as metadata_store
        need(type(actions) is AssetsActionPhases and type(episode) is AssetsEpisodeScope and episode.owner.selected is actions.selected
            and owner.role=='primary' and owner.lock is episode.locks['primary']
            and owner.store.path.parent==Path(episode.descriptor['directories']['primary']['stateRoot']['path'])
            and owner.run==actions.run and owner.url==actions.context['fixtureUrl']
            and same(owner.binding,episode.owner.context['roles']['primary']['binding']))
        need(action is None or type(action) is AssetsActionScope and action.owner is actions)
        self.owner,self.actions,self.episode,self.action,self.metadata=owner,actions,episode,action,metadata
        self.store=metadata_store(owner.store.path.with_name('ios-assets-'+owner.run+'-primary-reply-actions.json'),metadata)
        self.previous=self.store.read();self.state=None;self.refs_by_query={};self._validated=[]
        self.originals=OriginalFrameStore(self.store.path.parent,owner.binding,owner.run,'primary',self.bound,self.intent,
            namespace='assets-reply-actions',schema_prefix='iosAssetsReplyActionSource',monotonic=owner.native.monotonic)
        if self.previous is not None:self.state=self.decode(self.previous)
    def bound(self):
        self.owner.lock.assert_held();self.episode.guard();self.actions.guard();need(same(self.store.read(),self.previous));return True
    def envelope(self):
        return dict(iosAssetsReplyActionsVersion=1,binding=self.owner.binding,runId=self.owner.run,role='primary',
            selectedPair=self.actions.selected.link(),episode=self.episode.link(),actionsPath=str(self.actions.store.path),
            replyPath=str(self.owner.store.path),payload=pack([self.state]))
    def save(self):
        self.bound();need(self.action is not None and self.metadata is None);value=self.envelope();self.decode(value)
        self.store.write(value,self.previous);self.previous=deepcopy(value)
    def reserve(self,ticket,resource,namespace):
        self.bound();need(self.state is None and self.action is not None);self.action.guard()
        need(ticket==self.episode.descriptor['ticket'] and resource==self.episode.descriptor['resource'] and namespace in ('original','renamed'))
        self.state=dict(token=secrets.token_hex(32),reservation=dict(ticket=ticket,resource=resource,namespace=namespace),refs=[],pending=None);self.save()
    def link(self):
        self.bound();need(self.state is not None);return dict(iosAssetsReplyActionsLinkVersion=1,path=str(self.store.path),token=self.state['token'])
    def intent(self,kind,reference):
        need(kind=='original' and self.state is not None and self.state['pending'] is not None)
        self.state['pending']['original']=deepcopy(reference);self.save()
    def record(self,row,index):
        exact(row,{'iosAssetsReplyActionVersion','index','query','actionIndex','actionTicket','phaseBefore','jobOrigin'})
        need(type(row['iosAssetsReplyActionVersion']) is int and row['iosAssetsReplyActionVersion']==1 and type(row['index']) is int
            and row['index']==index and integer(row['actionIndex'],1,len(self.actions.plan())))
        query=replies.command(row['query']);need(query['runId']==self.owner.run)
        need(self.actions.state is not None and same(self.actions.store.read(),self.actions.previous)
            and same(self.actions.envelope(),self.actions.previous))
        if len(self.actions.state['records'])>=row['actionIndex']:
            source=self.actions.read(row['actionIndex']);ticket=source['ticket'];before=source['phaseBefore']
        else:
            source=self.actions.state['pending'];need(source is not None and source['index']==row['actionIndex'])
            ticket,before=source['ticket'],source['before']
        need(row['actionTicket']==ticket);self.actions.phase_packet(row['phaseBefore'],row['actionIndex'],ticket)
        phase_original(row['phaseBefore'],run=self.owner.run,area='assets',request=row['phaseBefore']['requestId'],
            epoch=row['phaseBefore']['capturedEpochMs'],previous=before)
        origin=row['jobOrigin']
        if query['operation'] in replies.STARTS:need(origin is None and query['ticket']==ticket)
        else:
            original=replies.command(origin);need(original['operation'] in replies.STARTS and query['jobId']==original['commandId']
                and all(query[key]==original[key] for key in ('runId','ticket','ownerToken','resource','namespace')))
        return row
    def decode(self,value):
        exact(value,{'iosAssetsReplyActionsVersion','binding','runId','role','selectedPair','episode','actionsPath','replyPath','payload'})
        need(type(value['iosAssetsReplyActionsVersion']) is int and value['iosAssetsReplyActionsVersion']==1
            and same(value['binding'],self.owner.binding) and value['runId']==self.owner.run and value['role']=='primary'
            and same(value['selectedPair'],self.actions.selected.link()) and same(value['episode'],self.episode.link())
            and value['actionsPath']==str(self.actions.store.path) and value['replyPath']==str(self.owner.store.path))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0];exact(state,{'token','reservation','refs','pending'})
        exact(state['reservation'],{'ticket','resource','namespace'});need(state['reservation']['ticket']==self.episode.descriptor['ticket']
            and state['reservation']['resource']==self.episode.descriptor['resource'] and state['reservation']['namespace'] in ('original','renamed'))
        need(type(state['token']) is str and __import__('re').fullmatch('[a-f0-9]{64}',state['token']) is not None
            and type(state['refs']) is list and len(state['refs'])<=512)
        mapping={}
        for index,ref in enumerate(state['refs'],1):
            full=self.originals.expand(ref);need(full['index']==index);row=self.originals.read(full)
            if index>len(self._validated) or not same(ref,self._validated[index-1]):self.record(row,index)
            need(row['query']['commandId'] not in mapping);mapping[row['query']['commandId']]=ref
        if state['pending'] is not None:
            pending=state['pending'];exact(pending,{'row','original'});self.record(pending['row'],len(state['refs'])+1)
            if pending['original'] is not None:
                self.originals.original(pending['original']);need(pending['original']['index']==len(state['refs'])+1)
                AssetsModelSources.prefix(self,pending['original'])
                if pending['original']['phase']=='saved':need(same(self.originals.read(pending['original']),pending['row']))
        self.refs_by_query=mapping;self._validated=deepcopy(state['refs']);return state
    def capture(self,query,origin):
        self.bound();need(self.state is not None and self.state['pending'] is None and self.action is not None and len(self.state['refs'])<512)
        self.action.guard();phase=self.actions.phase.status();self.actions.phase_packet(phase,self.action.index,self.action.ticket)
        row=dict(iosAssetsReplyActionVersion=1,index=len(self.state['refs'])+1,query=deepcopy(query),actionIndex=self.action.index,
            actionTicket=self.action.ticket,phaseBefore=phase,jobOrigin=deepcopy(origin));self.record(row,row['index'])
        self.state['pending']=dict(row=row,original=None);self.save();ref=self.originals.write(row['index'],row)
        self.state['refs'].append(ref);self.state['pending']=None;self.save();return query
    def recover(self):
        self.bound();need(self.state is not None and self.state['pending'] is not None and self.action is not None)
        pending=self.state['pending'];ref=pending['original'];need(ref is not None and ref['phase']=='saved')
        row=self.originals.read(ref);self.record(row,len(self.state['refs'])+1);need(same(row,pending['row']))
        self.state['refs'].append(self.originals.compact(ref));self.state['pending']=None;self.save();return row
    def query(self,query,state):
        self.bound();ref=self.refs_by_query.get(query['commandId']);need(ref is not None)
        full=self.originals.expand(ref);row=self.record(self.originals.read(full),full['index']);need(same(row['query'],query))
        need(same(self.state['reservation'],{key:state[key] for key in ('ticket','resource','namespace')})
            and all(query[key]==expected for key,expected in (('runId',self.owner.run),('ownerToken',state['token']),('resource',state['resource']),('namespace',state['namespace']))))
        if query['operation'] in ('mapping','info','raw-server'):
            parents=[job for job in state['jobs'] if job['query']['commandId']==query['sourceJob']]
            need(len(parents)==1 and all(query[key]==parents[0]['query'][key] for key in replies.SCOPE))
        if query['operation'] not in replies.STARTS:
            targets=[job for job in state['jobs'] if job['query']['commandId']==query['jobId']]
            need(len(targets)==1 and same(row['jobOrigin'],targets[0]['query']))
        return row
