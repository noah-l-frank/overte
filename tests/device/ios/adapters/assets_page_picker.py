"""Normal picker on the actually owned shared page, with separate page duty.

Version2 never calls a live leased page dead. Local file retirement requires
original native/file/work quiet windows while that exact page stays alive;
page duty remains in the independent PageLease until actual final Home close.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from types import MethodType,FunctionType
from adapters.native_feature_observation import need
from ios.adapters.assets_budget import operation
from ios.adapters.assets_picker import OwnedAssetsPicker,root
from ios.adapters.assets_controls import project
from ios.adapters.assets_files import quiet
from ios.adapters.assets_page_lease import OwnedAssetsPageLease
from ios.adapters.assets_episodes import AssetsEpisodeScope
from ios.adapters.assets_born_page_lease import BornAssetsPageLease
from ios.adapters.assets_page_identity_round import PageIdentityRound


class PageLeasePicker(OwnedAssetsPicker):
    OWNER_VERSION=2
    def __init__(self,*args,page_lease,episode,**kwargs):
        need(isinstance(page_lease,OwnedAssetsPageLease) and type(episode) is AssetsEpisodeScope and episode.owner is page_lease.episodes)
        self.page_lease,self.episode=page_lease,episode;super().__init__(*args,**kwargs);page_lease.context(episode,self)
    def extra_envelope(self):return dict(pageLease=self.page_lease.link(),episode=self.episode.link())
    def validate_extra(self,value):need(value['pageLease']==self.page_lease.link() and value['episode']==self.episode.link())
    def retirement_phase(self):return 'page-borrowed-retired'
    def cleanup_page(self,current,state):
        return self._cleanup_page_from_origin(current,state,self.page_lease.identity())
    def _cleanup_page_from_origin(self,current,state,original):
        page=root(current,'page',identifier=state['page'])
        need(page['alive'] and page['visible'] and all(page[key]==original[key] for key in ('rootId','windowId','modelId','componentSource','ownerRootId')))
        return page
    def _window_validate(self,window,state,*,complete):
        if type(window) is not dict or window.get('kind')!='cleanup' or not _window_eligible(self):
            return super()._window_validate(window,state,complete=complete)
        # Only immutable origin interpretation is reused within this one pure
        # synchronous window. Actual current roots/files/work stay per-frame.
        with PageIdentityRound(self,_window_eligible) as scope:
            return self._window_validate_with_page(window,state,complete=complete,page_check=scope.page)

    def cleanup_files(self,files):
        need(files.get('exists') is True and files['complete'] and not files['releasing'] and type(files['retiredPrimary']) is bool
            and files['files'][0]['exists'] is (not files['retiredPrimary']) and all(row['exists'] for row in files['files'][1:]))
    @operation
    def open_page(self):
        self.page_lease.live(self.episode);need(self.state['phase']=='reserved')
        if self.page_lease.state['origin'] is None:
            need(self.episode.index==1);current=super().open_page();self.page_lease.attach(self.episode,self);return current
        # Real normal UI capture on the already owned page, not menu reopen.
        row=self.page_lease.attach(self.episode,self);page=row['page'];need(page['alive'])
        self.state.update(page=page['rootId'],phase='page-open');self.save();return project(self.state['captures'][-1])
    @operation
    def cancel_owned(self):
        self.page_lease.live(self.episode)
        if self.state['phase']=='picker-closed':return self.files.observe()
        if self.state['phase']=='canceling':return self.recover_cancel()
        need(self.state['phase'] in ('picker-open','primary-chosen','unavailable'))
        self.state['phase']='canceling';self.save();self.input('cancel-picker','asset-file.cancel');return self.recover_cancel()
    @operation
    def retire_inputs(self):
        self.page_lease.live(self.episode)
        if self.state['phase']==self.retirement_phase():
            self.page_lease.transferred(self.episode,self);return self.files.state['originals'][-1]['packet']
        need(self.state['phase']=='picker-closed');self._window('cleanupWindow','cleanup')
        packet=self.files.recover_release() if self.files.state['phase']=='releasing' else self.files.release()
        quiet(packet['source']);self.cleanup_page(dict(inventory=packet['source']['ui']),self.state)
        self.state['phase']=self.retirement_phase();self.save();self.page_lease.transferred(self.episode,self);return packet
    @operation
    def close_shared_page(self):
        self.page_lease.live(self.episode);need(self.page_lease.state['phase']=='closing' and self.state['phase']==self.retirement_phase())
        self._prepare_slot('close-assets-page','assets.home');current=self._until_dead('page',self.state['page'])
        # File inputs are already retired; no fresh file query is needed to
        # label the actual native root dead. Parent retains the page source.
        return current


def _function(value):
    value=value.__func__ if isinstance(value,MethodType) else value
    return value,value.__code__ if isinstance(value,FunctionType) else None


_WINDOW=_function(OwnedAssetsPicker._window_validate)
_WINDOW_CORE=_function(OwnedAssetsPicker._window_validate_with_page)
_CLEANUP_PAGE=_function(PageLeasePicker.cleanup_page)
_CLEANUP_FILES=_function(PageLeasePicker.cleanup_files)
_PAGE_FROM_ORIGIN=_function(PageLeasePicker._cleanup_page_from_origin)
_LEASE_IDENTITY=_function(OwnedAssetsPageLease.identity)
_LEASE_BOUND=_function(OwnedAssetsPageLease.bound)
_NATIVE_RECORDS={OwnedAssetsPageLease:_function(OwnedAssetsPageLease.native_record),BornAssetsPageLease:_function(BornAssetsPageLease.native_record)}
_ROOT=_function(root)


def _window_eligible(picker):
    parent=picker.page_lease
    return (type(picker) is PageLeasePicker and type(parent) in _NATIVE_RECORDS
        and parent.state is not None and parent.state['origin'] is not None
        and _function(OwnedAssetsPicker._window_validate)==_WINDOW
        and _function(picker._window_validate_with_page)==_WINDOW_CORE
        and _function(picker.cleanup_page)==_CLEANUP_PAGE and _function(picker.cleanup_files)==_CLEANUP_FILES
        and _function(picker._cleanup_page_from_origin)==_PAGE_FROM_ORIGIN
        and _function(parent.identity)==_LEASE_IDENTITY and _function(parent.bound)==_LEASE_BOUND
        and _function(parent.originals.guard)==_LEASE_BOUND and _function(parent.native_record)==_NATIVE_RECORDS[type(parent)]
        and _function(root)==_ROOT)
