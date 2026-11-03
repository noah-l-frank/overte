"""Version2 page parent rooted in action1 birth before first file staging.

The actual page/window/model origin remains the independent native UI/clock
source. Later episode captures attach to that original existing page.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same
from ios.adapters.assets_page_birth import AssetsPageBirth
from ios.adapters.assets_page_lease import OwnedAssetsPageLease


class BornAssetsPageLease(OwnedAssetsPageLease):
    OWNER_VERSION=2
    def archive_context(self,value):
        need(type(value) is AssetsPageBirth and value.historical and value.selected is self.episodes.selected
            and value.lock is self.lock and value.run==self.run);self.birth=value
    def __init__(self,*args,birth,**kwargs):
        need(type(birth) is AssetsPageBirth);self.birth=birth
        super().__init__(*args,**kwargs)
        need(birth.selected is self.episodes.selected and birth.lock is self.lock and birth.run==self.run)
    def native_record(self,row,index):
        if row.get('originKind')!='page-birth':return super().native_record(row,index)
        exact(row,{'iosAssetsPageLeaseSourceVersion','index','originKind','birth','page'})
        need(type(row['iosAssetsPageLeaseSourceVersion']) is int and row['iosAssetsPageLeaseSourceVersion']==2
            and type(row['index']) is int and row['index']==index==1 and same(row['birth'],self.birth.link())
            and same(row['page'],self.birth.page()) and row['page']['alive'])
        return row
    def record(self,row,index):
        if row.get('originKind')=='page-birth':return self.native_record(row,index)
        return super().record(row,index)
    def attach_birth(self):
        self.bound();need(not self.historical and self.state is not None and self.state['phase']=='reserved'
            and self.state['pending'] is None and not self.state['records'] and not self.episodes.state['entries'])
        page=self.birth.page();row=dict(iosAssetsPageLeaseSourceVersion=2,index=1,originKind='page-birth',birth=self.birth.link(),page=deepcopy(page))
        self.state['pending']=dict(row=row,original=None);self.save();self.record(row,1)
        ref=self.originals.write(1,row);self.state.update(phase='open',origin=ref,records=[ref],pending=None);self.save();return self.identity()
