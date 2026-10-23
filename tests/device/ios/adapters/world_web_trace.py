"""Read-only current-document projection from an original native World trace."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from ios.adapters import world_web_source as native


def current_view(ledger):
    native.original(ledger);need(ledger['complete']);views={}
    for row in ledger['events']:
        item=row['identity'];view=(item['handle'],item['creation']);kind=row['kind']
        if kind=='view-created':need(view not in views);views[view]=None
        elif kind=='document-began':need(view in views);views[view]=deepcopy(item)
        elif kind in ('view-teardown','owner-destroyed'):views.pop(view,None)
    need(len(views)<=1)
    return None if not views else deepcopy(next(iter(views.values())))

