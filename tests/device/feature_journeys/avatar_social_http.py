"""Optional social route attached to the existing trusted HTTPS fixture only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import ssl
from feature_journeys.avatar_social_provider import REQUEST, USERS, CONNECTIONS, DELETE
from feature_journeys.account_provider import AccountProvider


class AccountAuthenticator:
    """Inspectable binding to one existing actual OAuth authority provider."""
    __slots__ = ('_provider',)
    def __init__(self, provider):
        if not isinstance(provider, AccountProvider): raise ValueError('Actual account provider is required')
        self._provider = provider
    @property
    def provider(self): return self._provider
    def __call__(self, authorization):
        status, value = self._provider.profile(authorization)
        if status != 200: return None
        return value['data']['user']['username']


def account_authenticator(provider):
    """Resolve existing actual OAuth authority without minting new principals."""
    return AccountAuthenticator(provider)


def handle(handler, parsed):
    if parsed.path not in (REQUEST, USERS, CONNECTIONS) and not parsed.path.startswith(DELETE): return False
    provider = getattr(handler.server, 'avatar_social_provider', None)
    handler.close_connection = True
    if (provider is None or not isinstance(handler.connection, ssl.SSLSocket)
            or handler.connection.version() not in ('TLSv1.2', 'TLSv1.3')):
        handler.send(404, {'error': 'not-found'}); return True
    if parsed.scheme or parsed.netloc or parsed.fragment:
        raise ValueError('Invalid original social route')
    auth = handler.headers.get_all('Authorization', [])
    lengths = handler.headers.get_all('Content-Length', [])
    if (len(auth) != 1 or len(auth[0]) > 512 or len(lengths) > 1
            or handler.headers.get('Transfer-Encoding') or handler.headers.get('Content-Encoding')):
        raise ValueError('Invalid original social request headers')
    size = 0
    if lengths:
        if not lengths[0].isdigit() or not 0 <= int(lengths[0]) <= 4096:
            raise ValueError('Invalid bounded social request body')
        size = int(lengths[0])
    if handler.command == 'POST' and (not size or
            handler.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json'):
        raise ValueError('Original connection POST requires bounded JSON')
    if handler.command != 'POST' and size:
        raise ValueError('Original social read/delete cannot carry a body')
    # Reuse the existing bounded socket deadline/body reader, without replacing
    # the listener, weakening TLS, or installing credentials/trust material.
    from feature_journeys.server import read_account_body
    raw = read_account_body(handler.rfile, handler.connection, size) if size else b''
    with provider.response(handler.command, parsed.path, parsed.query, raw, auth[0]) as response:
        status, data, response_id, written = response
        handler.send(status, data, response_id=response_id, observe_write=written)
    return True
