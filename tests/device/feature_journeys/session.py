"""Prepare the existing session without disconnecting domain-backed features."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from .scenarios import DOMAIN_AREAS


def prepare(session, area):
    if area in DOMAIN_AREAS:
        return session.enter_controlled_domain()
    return session.ensure_controlled_scene()
