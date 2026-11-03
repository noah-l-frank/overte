"""Explicit later-action query challenge; original upload ticket stays intact.

These v2 envelopes must be independently bound to their current shared action
by the whole coordinator/read graph. They do not supply phase admission alone.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from feature_journeys.contract import identifier
from ios.adapters.assets_baking_owner import OwnedAssetsBaking
from ios.adapters.assets_parsed_owner import OwnedAssetsParsedInput


class ActionTicket:
    OWNER_VERSION=2
    def extra_envelope(self):return dict(actionTicket=self.action_ticket)
    def ticket(self):return self.action_ticket
    def validate_extra(self,value):
        identifier(value['actionTicket']);need(value['actionTicket']==self.action_ticket)


class ActionAssetsBaking(ActionTicket,OwnedAssetsBaking):
    def __init__(self,*args,action_ticket,**kwargs):
        self.action_ticket=identifier(action_ticket);super().__init__(*args,**kwargs)
    def decode(self,value):
        state=super().decode(value)
        for index in state['admissions']+state['observations']:need(self.row(index)['query']['ticket']==self.action_ticket)
        return state


class ActionAssetsParsed(ActionTicket,OwnedAssetsParsedInput):
    def __init__(self,*args,action_ticket,**kwargs):
        self.action_ticket=identifier(action_ticket);super().__init__(*args,**kwargs)
    def backend_row(self,index):
        row=super().backend_row(index);need(row['query']['ticket']==self.action_ticket);return row
