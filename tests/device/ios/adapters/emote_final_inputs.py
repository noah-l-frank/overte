"""Join current copied input responsibility to the actually proved cleanup."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same


def validate(final,copies,native_original):
    role=final.flow.role;need(role in ('primary','actor'))
    def raw(name):return copies[str(final.path(name).path)]
    # Released Scope has already retired these two child intents. A later
    # unknown/pending child must not be deleted under its older Scope proof.
    for tail in ('marker-files','marker-script'):
        need(raw('ios-emote-'+role+'-'+tail+'.json') is None)
    inputs=native_original['inputOwners'];exact(inputs,{'cleanup','actions','background'})
    if role=='primary':
        for key,name in (('cleanup','cleanup-inputs'),('actions','inputs'),('background','background')):
            need(same(raw('ios-emote-'+name+'.json'),inputs[key]))
    else:need(all(value is None for value in inputs.values()))
    return True
