"""Original normal account-menu metadata, separate from logout authority proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
from adapters.native_feature_observation import exact,integer,need

VERSION=1
IDS=frozenset({'account-menu.file','account-menu.logout'})
FIELDS={'inputReady','accountInstance','credentialGeneration','endpointSha256','principalSha256'}


def validate_metadata(row):
    exact(row,{'id','token','enabled','focused'}|FIELDS)
    need(row['id'] in IDS and type(row['token']) is str
         and re.fullmatch('(?:[0-9a-f]{32}|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})',row['token'])
         and all(type(row[key]) is bool for key in ('enabled','focused','inputReady'))
         and type(row['accountInstance']) is str and re.fullmatch('[0-9a-f]{32}',row['accountInstance'])
         and integer(row['credentialGeneration'],1)
         and all(type(row[key]) is str and re.fullmatch('[0-9a-f]{64}',row[key]) for key in ('endpointSha256','principalSha256'))
         and (not row['inputReady'] or row['enabled']))
