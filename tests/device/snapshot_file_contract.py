"""Closed read-only original Snapshot transport, never a capture operation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re

MAX_FILE_BYTES = 256 * 1024 * 1024
CHUNK_BYTES = 4 * 1024 * 1024
BOUNDED_CHUNK_BYTES = 512 * 1024
MAX_FILES = 8
PREFIX = r'parity-[0-9a-f]{16}-(?:still-png|still-jpg|animated|panorama|cubemap)'


def read_request(value):
    fields = {'schemaVersion', 'commandId', 'action', 'operation', 'prefix'}
    if isinstance(value, dict) and value.get('operation') == 'read':
        fields |= {'name', 'revision', 'offset'}
    if isinstance(value, dict) and value.get('schemaVersion') == 2:
        fields.add('chunkBytes')
    if (not isinstance(value, dict) or set(value) != fields
            or type(value['schemaVersion']) is not int or value['schemaVersion'] not in (1, 2)
            or not isinstance(value['commandId'], str)
            or re.fullmatch(r'ios-[0-9a-f]{32}', value['commandId']) is None
            or value['action'] != 'snapshot-files' or value['operation'] not in ('list', 'read')
            or not isinstance(value['prefix'], str) or re.fullmatch(PREFIX, value['prefix']) is None):
        raise ValueError('Invalid bounded Snapshot file request')
    if value['schemaVersion'] == 2 and (value['operation'] != 'read'
            or type(value['chunkBytes']) is not int or value['chunkBytes'] != BOUNDED_CHUNK_BYTES):
        raise ValueError('Invalid fixed-size Snapshot chunk request')
    if value['operation'] == 'read' and (
            not isinstance(value['name'], str)
            or re.fullmatch(re.escape(value['prefix']) + r'-snap_[0-9]{1,20}_[0-9]{1,10}\.(png|jpg|jpeg|webp|gif)', value['name']) is None
            or not isinstance(value['revision'], str) or re.fullmatch(r'[0-9a-f]{64}', value['revision']) is None
            or type(value['offset']) is not int or not 0 <= value['offset'] <= MAX_FILE_BYTES):
        raise ValueError('Invalid bounded Snapshot original-file read')
    return value
