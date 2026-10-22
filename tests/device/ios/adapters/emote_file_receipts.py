"""Preserve original Emote v1 ownership and native receipt semantics."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_marker_file_receipts import OriginalMarkerFileReceipts,receipt as _receipt,VERSION


def receipt(value,*,root,binding,run,role,previous=None):return _receipt(value,root=root,binding=binding,run=run,role=role,previous=previous,profile='emote')


class IOSEmoteFileReceipts(OriginalMarkerFileReceipts):
    PROFILE='emote'

    @staticmethod
    def partial(pending):return OriginalMarkerFileReceipts.partial(object.__new__(IOSEmoteFileReceipts),pending)
