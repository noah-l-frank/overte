"""Original Pico process restart and exact persisted bookmark continuity.

This validates retained originals only. It supplies no fresh source, ordinary
input, world arrival, image, resource retirement or whole-feature verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact, need, validate as lifecycle_packet
from adapters.native_location_bookmarks import validate as bookmark_packet
from adapters.native_process_presence import validate as presence_packet
from adapters.graphics_journey.restart_proof import pico_binding_change
from adapters.restart_inputs import validate_native_restart, native
from feature_journeys.contract import identifier
from feature_journeys.fixtures import context

VERSION = 1


def validate(value, run):
    identifier(run)
    exact(value, {'navigationBookmarkRestartProofVersion', 'input', 'oldNative', 'native', 'exit', 'oldBookmark', 'bookmark'})
    need(type(value['navigationBookmarkRestartProofVersion']) is int
         and value['navigationBookmarkRestartProofVersion'] == VERSION)
    plan = value['input']
    exact(plan, {'restartInputVersion', 'componentOnly', 'oldBinding', 'oldNative', 'phase',
                 'newBinding', 'newNative', 'ownerFiles', 'scriptHandoff'})
    need(type(plan['restartInputVersion']) is int and plan['restartInputVersion'] == 1
         and plan['componentOnly'] is False and plan['phase'] == 'observed' and plan['scriptHandoff'] is None
         and type(plan['ownerFiles']) is list and len(plan['ownerFiles']) == 3
         and all(type(path) is str and path.startswith('/') for path in plan['ownerFiles'])
         and len(set(plan['ownerFiles'])) == 3)
    old, new = plan['oldBinding'], plan['newBinding']
    pico_binding_change(old, new)
    validate_native_restart(plan['oldNative'], plan['newNative'])
    for binding, key, birth_key, book_key in ((old, 'oldNative', 'oldNative', 'oldBookmark'),
                                             (new, 'native', 'newNative', 'bookmark')):
        pid = int(binding['processIdentity'].split(':')[0]); packet = value[key]
        lifecycle_packet(packet, packet.get('requestId'), pid, packet.get('capturedEpochMs'))
        measured = native(dict(pid=packet['processId'], instance=packet['instance'], lifecycle=packet['lifecycle']))
        need(measured == plan[birth_key])
        book = value[book_key]
        bookmark_packet(book, dict(schemaVersion=1, commandId=book.get('commandId'),
            action='feature-location-bookmarks', runId=run), pid, book.get('capturedEpochMs'))
    before, after, exited = value['oldNative'], value['native'], value['exit']
    identifier(exited['commandId'])
    presence_packet(exited, dict(schemaVersion=1, commandId=exited['commandId'],
        action='feature-process-presence', queryProcessId=before['processId']), after['processId'], exited['capturedEpochMs'])
    need(exited['presence'] == 'absent' and exited['instance'] == after['instance']
         and after['requestedEpochMs'] >= before['capturedEpochMs']
         and exited['requestedEpochMs'] >= after['capturedEpochMs'])
    old_book, book = value['oldBookmark'], value['bookmark']
    need(old_book['capturedEpochMs'] <= before['capturedEpochMs']
         and book['requestedEpochMs'] >= exited['capturedEpochMs']
         and book['instance'] != old_book['instance'] and book['commandId'] != old_book['commandId']
         and book['storage'] == old_book['storage'] and book['storage']['file'] is not None)
    owned = book['storage']['owned']
    need(len(owned) == 1 and owned[0]['name'] == context(run)['renamed'])
    return deepcopy(value)
