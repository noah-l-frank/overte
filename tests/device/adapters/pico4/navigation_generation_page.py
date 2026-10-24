"""Actual post-Delete Places→Home originals for the existing Close algorithm.

This is a concrete page-source association, never a fabricated Transit or
DismissedLookup. It has no input method and owns no normal controller command.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import need,exact
from adapters.script_journey.history import same

VERSION=1


class NavigationGenerationPage:
    def __init__(self,parent,home,before,after,*,before_sample=None):
        parent.control();need(parent.state is not None)
        if parent.state['active'] is not None:
            need(parent.state['active']['arguments']['verb']=='close');ticket=parent.state['active']['arguments']['ticket']
        else:
            need(parent.state['completed'] and parent.state['completed'][-1]['verb']=='close');ticket=parent.state['completed'][-1]['ticket']
        self.parent,self.home=parent,home;self.before_sample=before_sample
        need(before_sample is None or callable(before_sample))
        self.run,self.binding=parent.run,deepcopy(parent.binding)
        self.scene_url,self.arrival=parent.parent.source.inputs['sceneUrl'],parent.source().arrival
        self.navigation=parent.source().normal.io.original.navigation
        self.ticket=ticket
        self.before,self.after=deepcopy(before),deepcopy(after)
        self.home_original=deepcopy(after['home'])
        self.origin=dict(navigationGenerationPageVersion=VERSION,parentScopeSha256=parent.scope_sha,
            beforeSha256=json_digest(before),afterSha256=json_digest(after))
        self.bound();self.archive_frame(before['frame']);self.archive_frame(after['frame'])
        a,b=before['frame'],after['frame'];parent.source().advance_frames(a,b)
        old,new=parent.source().project(a),parent.source().project(b)
        need(old['panel'] and not old['bookmark'] and not old['addressDialog'] and old['error']=='none'
            and not new['panel'] and not new['bookmark'] and not new['addressDialog'] and new['error']=='none'
            and old['location']==new['location'] and after['home']['onHomeScreen'] and after['home']['tabletShown'])
        roots=[row for row in a['after']['directory']['roots'] if row['current']]
        need(len(roots)==1);self.page_root=roots[0]['rootId']
        self.final(self.convert(b))

    def bound(self):
        self.parent.memory_control()
        need(self.origin['parentScopeSha256']==self.parent.scope_sha
            and self.origin['beforeSha256']==json_digest(self.before) and self.origin['afterSha256']==json_digest(self.after)
            and same(self.binding,self.parent.binding))

    def archive_frame(self,frame):
        self.parent.source().project(frame);self.parent.parent.original_facts(frame)

    @staticmethod
    def convert(frame):
        side=frame['after']
        return dict(frame=deepcopy(frame),ui=deepcopy(side['ui']),pose=deepcopy(side['pose']),
            roots=deepcopy(side['directory']),bookmarks=deepcopy(side['bookmarks']),panels=deepcopy(side['panels']))

    def archive(self,group):
        self.bound();exact(group,{'frame','ui','pose','roots','bookmarks','panels'});self.archive_frame(group['frame'])
        need(same(group,self.convert(group['frame'])))

    def final(self,group):
        self.archive(group);facts=self.parent.source().project(group['frame'])
        need(not facts['panel'] and not facts['bookmark'] and not facts['addressDialog'] and facts['error']=='none')
        for side in ('before','after'):
            value=group['frame'][side]
            roots=[row for row in value['directory']['roots'] if row['rootId']==self.page_root]
            need(len(roots)==1 and not roots[0]['alive'] and not roots[0]['current']
                and not any(row['current'] for row in value['directory']['roots'])
                and not any(row['alive'] or row['inCurrentTree'] for row in value['panels']['roots']))
        need(group['bookmarks']['storage']==self.after['frame']['after']['bookmarks']['storage'])

    def advance(self,before,after):
        self.parent.source().advance_frames(before['frame'],after['frame'])

    def query_ids(self,group):
        result=[]
        for side in ('before','after'):
            value=group['frame'][side]
            result.extend(value[key]['commandId'] for key in ('bookmarks','directory','environment','panels','modals','replies'))
            result.append(value['pose']['subject']['requestId'])
        need(len(result)==len(set(result)));return result

    def sample(self):
        if self.before_sample is not None:self.before_sample()
        phase=self.parent.fence();frame=self.parent.source().capture(self.parent.state['receipt'],phase['status'],
            lookup_receipt=self.parent.parent.state['lookupReceipt'])
        group=self.convert(frame);self.final(group);return group
