"""Explicit ReplyOwner3: current new-job ticket, retained originating-job ticket.

Current phase custody uses the existing Assets Action journal and immutable
OriginalFrame store. Literal ReplyOwner1/2 and native request DTO stay intact.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters.assets_action_phase import AssetsActionPhases,AssetsActionScope
from ios.adapters.assets_episodes import AssetsEpisodeScope
from ios.adapters.assets_reply_owner import OwnedAssetsReplyReads
from ios.adapters.assets_reply_action_sources import AssetsReplyActionSources
from ios.adapters import assets_replies as source


class ActionAssetsReplyReads(OwnedAssetsReplyReads):
    CURRENT_VERSION=3
    ALLOW_LEGACY=False
    EXTRA_FIELDS=frozenset({'replyActions'})
    def __init__(self,*args,actions,episode,action=None,**kwargs):
        need(type(actions) is AssetsActionPhases and type(episode) is AssetsEpisodeScope
            and (action is None or type(action) is AssetsActionScope and action.owner is actions))
        self.action_history,self.reply_episode,self.reply_action=actions,episode,action
        super().__init__(*args,**kwargs)
    def profile(self):
        self.query_sources=AssetsReplyActionSources(self,self.action_history,self.reply_episode,self.reply_action)
    def extra_envelope(self):return dict(replyActions=self.query_sources.link())
    def reserve(self,ticket,resource='gltf-bundle/main.gltf',namespace='original'):
        need(self.state is None and self.reply_action is not None);self.reply_action.guard()
        if self.query_sources.state is None:self.query_sources.reserve(ticket,resource,namespace)
        else:
            self.query_sources.bound();need(self.query_sources.previous is not None and not self.query_sources.state['refs']
                and self.query_sources.state['pending'] is None
                and same(self.query_sources.state['reservation'],dict(ticket=ticket,resource=resource,namespace=namespace)))
        return super().reserve(ticket,resource,namespace)
    def query_context(self,query,state):self.query_sources.query(query,state)
    def query_ticket(self,kind,values):
        need(self.reply_action is not None);self.reply_action.guard()
        if kind in source.STARTS:
            if kind!='inventory':
                parents=[job for job in self.state['jobs'] if job['query']['commandId']==values.get('sourceJob')]
                need(len(parents)==1 and parents[0]['query']['ticket']==self.reply_action.ticket)
            return self.reply_action.ticket
        jobs=[job for job in self.state['jobs'] if job['query']['commandId']==values.get('jobId')];need(len(jobs)==1)
        return jobs[0]['query']['ticket']
    def query_intent(self,query):
        origin=None
        if query['operation'] not in source.STARTS:
            jobs=[job for job in self.state['jobs'] if job['query']['commandId']==query['jobId']];need(len(jobs)==1);origin=jobs[0]['query']
        return self.query_sources.capture(query,origin)
