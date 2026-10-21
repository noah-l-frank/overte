"""Controlled HTTPS origin from the existing iOS process environment contract."""
# Derived from frozen Phone pure origin validator; no Android launcher is used.
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import ipaddress
import re
from urllib.parse import urlsplit
from adapters.native_account_origin import origin_text
from adapters.native_feature_observation import need

def origin(fixture_url):
    need(type(fixture_url) is str and fixture_url.isascii() and len(fixture_url)<=1024
         and not any(ord(char)<33 or ord(char)>126 for char in fixture_url))
    parsed=urlsplit(fixture_url)
    need(parsed.scheme=='https' and parsed.path=='/feature-fixture/v1'
         and not parsed.query and not parsed.fragment and '?' not in fixture_url and '#' not in fixture_url
         and '%' not in fixture_url and parsed.netloc==parsed.netloc.lower() and parsed.geturl()==fixture_url)
    value=origin_text('https://'+parsed.netloc)
    host=parsed.hostname;need(host is not None and len(host)<=253)
    if ':' in host:ipaddress.IPv6Address(host)
    elif all(char in '0123456789.' for char in host):ipaddress.IPv4Address(host)
    else:
        need(all(re.fullmatch('[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',label) is not None for label in host.split('.')))
    return value

