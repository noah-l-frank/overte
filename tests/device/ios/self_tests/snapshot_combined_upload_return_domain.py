"""One fresh actual Page/Pending/PNG/Upload/Share path, all selected at birth.

Native/Qt/V8/SDK remain declared models. One real PNG, actual Node callback,
protected backend bytes and original return/cleanup coordinators are shared.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
from adapters.native_feature_observation import need
from ios.self_tests import snapshot_page_return_domain
from ios.self_tests.snapshot_page_return_domain import PageJourneyDomain
from ios.self_tests.snapshot_combined_return_domain import CombinedPageReturnFlow
from ios.self_tests.snapshot_combined_journey_domain import CombinedJourneyDomain
from ios.self_tests.snapshot_causal_parent_domain import CausalParentDomain
from ios.self_tests.snapshot_upload_flow_domain import RUN


class CombinedUploadJourneyDomain(CausalParentDomain,CombinedJourneyDomain):
    def file_post(self,request,timeout):
        result=super().file_post(request,timeout);packet=self.ctx.files.value
        if packet['operation']=='list':packet['files']=[row for row in packet['files'] if row['name'].startswith(packet['prefix']+'-')]
        return result


class CombinedUploadPageDomain(PageJourneyDomain):
    combined=True
    def __init__(self,case):
        with patch.object(snapshot_page_return_domain,'SnapshotJourneyFilesDomain',CombinedUploadJourneyDomain):super().__init__(case)


class CombinedUploadReturnFlow(CombinedPageReturnFlow):
    def prepare_main(self,case):
        self.page=CombinedUploadPageDomain(case);prepared=self.page.prepare_png();main=self.page.capture
        main.runtime._sources=self.page.runtime._sources
        with main.capture_owner() as capture:self.name_restoration=capture.restore_name_before_destination()
        self.prepared_phase=prepared['phase']
        return main,deepcopy(main.activations),prepared['phase']['createdEpochMs']
    def __init__(self,case):
        # The Archive is admitted by the existing constructor while its exact
        # original Capture phase is still active. Upload follows that admission.
        super().__init__(case)
        main=self.main
        # One live provider ledger grows; every saved phase packet contains its
        # own original deep copy. Main and Share readers cannot diverge.
        main.activations=self.activations
        if not self.main_foreground:self.primary.activate()
        main.advance();ticket='b'*32
        main.activations.append(dict(sequence=len(main.activations)+1,ticket=ticket,activatedEpochMs=main.epoch(),stimulus=dict(verb='upload',inputs={})))
        main.backend.accounts.activate(RUN,ticket);main.backend.provider.activate(RUN,ticket);main.control_server.journal.runs[RUN]['ticket']=ticket
        with main.upload_owner() as upload:upload.start(ticket);self.upload_result=upload.finish()
        with main.backend_owner() as backend:self.backend_result=backend.original()
        need(main.upload_count==1)
