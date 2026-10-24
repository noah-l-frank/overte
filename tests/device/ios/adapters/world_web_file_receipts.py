"""World Web original staged bytes and native file-absence receipts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_marker_file_receipts import OriginalMarkerFileReceipts,receipt as original_receipt


def receipt(value,*,root,binding,run,role,previous=None):
    return original_receipt(value,root=root,binding=binding,run=run,role=role,previous=previous,profile='worldweb')


class WorldWebFileReceipts(OriginalMarkerFileReceipts):
    PROFILE='worldweb'
