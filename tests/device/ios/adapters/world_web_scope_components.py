"""Closed World Web profile for the reviewed normal marker lifecycle owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from ios.adapters import emote_world as world,world_web_marker_measurements as measurements
from ios.adapters.emote_ui_inventory import absent as absent_chooser
from ios.adapters.world_web_files import OwnedWorldWebFiles
from ios.adapters.world_web_originals import IOSWorldWebOriginals


def components():
    return SimpleNamespace(profile='worldweb',scope_key='iosWorldWebMarkerScopeVersion',Files=OwnedWorldWebFiles,Originals=IOSWorldWebOriginals,
        manifest_key='worldWebManifestVersion',generation_key='emoteGeneration',source_sequence_key='emoteSourceSequence',
        world_factory='emote_world',world_original=world.original,world_packet=world.validate,WORLD_ACTION=world.ACTION,
        actual_domain=world.actual_domain,owned_marker=world.owned_marker,admitted=measurements.admitted,restored=measurements.restored,
        body_preserved=measurements.body_preserved,view_preserved=measurements.view_preserved,image_body_preserved=measurements.body_preserved,
        partial_execution=measurements.executed,finished_execution=measurements.finished,partial_restored=measurements.partial_restored,
        drained_partial=measurements.drained_partial,absent_chooser=absent_chooser)
