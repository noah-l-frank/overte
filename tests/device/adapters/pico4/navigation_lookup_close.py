"""Original dismissed-lookup sources for the existing normal tablet close owner.

The actual lookup and dismissal journals stay immutable. This source context
does not deliver input, manufacture a transit or prove whole Navigation cleanup.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib

from adapters.native_feature_observation import need
from adapters.native_navigation_modals import retired
from adapters.navigation_missing import NavigationMissing
from adapters.navigation_error_dismissal import NavigationErrorDismissal
from adapters.script_journey.history import canonical,unpack


class NavigationDismissedLookup:
    def __init__(self,lookup,dismissal):
        need(isinstance(lookup,NavigationMissing) and isinstance(dismissal,NavigationErrorDismissal)
            and lookup.state is not None and lookup.state['phase']=='visible'
            and dismissal.state is not None and dismissal.state['phase']=='complete'
            and lookup.run==dismissal.run and lookup.binding==dismissal.binding
            and lookup.provider==dismissal.provider_instance and lookup.inputs==dismissal.inputs
            and lookup.origin==dismissal.origin
            and lookup.navigation is dismissal.ui.io.original.navigation)
        need(dismissal.state['lookupTicket']==lookup.state['ticket']
            and dismissal.state['afterEpochMs']==lookup.state['submitEpochMs']
            and dismissal.state['joined']==lookup.state['joined'])
        need(unpack(lookup.disk['payload'])==[lookup.state]
            and dismissal.disk==dismissal.state and dismissal.disk['navigationErrorDismissalVersion']==2)
        self.lookup,self.dismissal=lookup,dismissal
        self.run,self.binding,self.home=lookup.run,deepcopy(lookup.binding),lookup.home
        self.navigation,self.scene_url,self.arrival=lookup.navigation,lookup.inputs['sceneUrl'],lookup.arrival
        self.headers=(deepcopy(lookup.disk),deepcopy(dismissal.disk))
        self.states=(deepcopy(lookup.state),deepcopy(dismissal.state))
        # This is source correlation, not a fabricated NavigationTransit state.
        self.ticket=dismissal.state['ticket']
        self.home_original=deepcopy(lookup.state['last']['home'])
        self.origin=dict(lookupSha256=hashlib.sha256(canonical(self.headers[0])).hexdigest(),
            dismissalSha256=hashlib.sha256(canonical(self.headers[1])).hexdigest())
        self.bound()

    def bound(self):
        need(self.lookup.guard() is not False and self.dismissal.guard() is not False
            and self.lookup.store.read()==self.lookup.disk==self.headers[0]
            and self.dismissal.store.read()==self.dismissal.disk==self.headers[1]
            and self.lookup.state==self.states[0] and self.dismissal.state==self.states[1])

    def archive(self,group):
        self.bound();self.lookup.archive(group)

    def final(self,group):
        self.bound()
        self.dismissal.archive_group({key:group[key] for key in ('provider','reply','modal')})
        self.dismissal.current({key:group[key] for key in ('provider','reply','modal')})
        event=self.lookup.state['joined']['event']
        actual=retired(group['modal'],event)
        need(actual['modalId']==self.dismissal.state['input']['modalId']
            and group['ui']['scope']['sequence']==self.dismissal.state['input']['scope']['sequence']+1
            and group['bookmarks']['storage']==self.lookup.state['original']['bookmarks']['storage']
            and not self.lookup.live(group) and not group['ui']['native']['lookup']['address']
            and group['home']['onHomeScreen'])
        self.bound()

    def advance(self,before,after):
        self.bound();self.lookup.advance(before,after)

    def query_ids(self,group):return self.lookup.queries(group)

    def sample(self):
        self.bound();lookup=self.lookup
        provider=lookup.status();ui=lookup.ui.capture();pose=lookup.arrival.read()
        value=dict(provider=provider,ui=ui,pose=pose,home=lookup.home.source.capture(),
            bookmarks=lookup.bookmarks.read(self.run),reply=lookup.replies.read(self.run),modal=lookup.modals.read(self.run))
        self.archive(value);self.final(value);self.bound();return value
