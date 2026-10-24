"""Conservative evidence requirements for repeated ordinary browser recipes.

The same verb and inputs can occur at multiple real checkpoints. Their union
requests every required original; it supplies no expected or observed facts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from feature_journeys.scenarios import SCENARIOS,expand
from feature_journeys.fixtures import context


def required(run,verb,inputs):
    if verb in ('baseline','cleanup'):
        need(same(inputs,{}));return set()
    rows=[row['evidence'] for row in SCENARIOS['world-web']['steps']
        if row['verb']==verb and same(expand(row['inputs'],context(run)),inputs)]
    need(rows)
    return set().union(*rows)
