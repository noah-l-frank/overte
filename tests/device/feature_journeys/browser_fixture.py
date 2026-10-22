"""Owned HTTP browser stimuli using the existing parity page and echo script.

Server receipts describe HTTP responses, never what a client loaded/rendered or
whether native bridge authority was enforced. Product sources remain mandatory.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
from pathlib import Path
import secrets
import threading
import time
from .contract import exact, identifier
from .fixtures import pinned_resource

ROOT = Path(__file__).resolve().parents[1] / 'fixture/parity'
ASSETS = {'reference.js', 'client.js', 'injected.js', 'feature-marker.js'}
PAGES = {'index.html', 'reference.html', 'page-b.html', 'recovery.html'}


def inline_source(run,ticket,fixture_url):
    """Controlled ordinary app INPUT bytes, never an HTTP inline-page result.

    A later platform recipe must use a normal owned fixture-app button calling
    gotoWebScreen(data:...). This does not call any product API or issue a grant.
    """
    from .contract import arguments
    from .scenarios import VERSION
    from .fixtures import marker_bytes
    arguments('feature.tablet-web.act',dict(contractVersion=VERSION,runId=run,ticket=ticket,
        fixtureUrl=fixture_url,verb='open-inline-app',inputs={'resource':'parity-inline-v1'}))
    page=pinned_resource('web-source/index.html').decode('utf-8')
    script=pinned_resource('web-source/reference.js').decode('utf-8')
    if '</script' in script.lower():raise ValueError('Original inline script needs a reviewed HTML encoding')
    page=page.replace('Overte web parity reference','Overte owned inline parity')
    page=page.replace('</head>','<meta name="overte-fixture-owner" content="'+run+'"></head>')
    page=page.replace('<script src="reference.js"></script>','<script>'+script+'</script>')
    page=page.replace('preload="metadata"','preload="none"')
    # The only inline image checkpoint is initial open. Later text/bridge/retire
    # checkpoints use independent sources, not a stale image challenge relabel.
    marker=base64.b64encode(marker_bytes(run,ticket)).decode('ascii')
    page=page.replace('<body>','<body><img id="feature-marker" alt="Owned challenge" src="data:image/png;base64,'+marker+'">')
    return page.encode('utf-8')


def inline_data_url(run,ticket,fixture_url):
    return 'data:text/html;charset=utf-8;base64,'+base64.b64encode(inline_source(run,ticket,fixture_url)).decode('ascii')


class BrowserResources:
    def __init__(self, *, clock_ms=lambda: int(time.time() * 1000)):
        if not callable(clock_ms): raise ValueError('Browser fixture clock is required')
        self.clock_ms, self.lock, self.runs = clock_ms, threading.RLock(), {}

    def open(self, run):
        identifier(run)
        with self.lock:
            if run in self.runs or len(self.runs) >= 32: raise ValueError('Browser fixture ownership already exists or is full')
            self.runs[run] = dict(instance=secrets.token_hex(16), ready=False, sequence=0, epoch=0, responses=[])

    def control(self, run, value):
        exact(value, {'operation'}, 'browser fixture control')
        if value['operation'] != 'restore-resource': raise ValueError('Unsupported browser resource input')
        with self.lock:
            row = self.runs[identifier(run)]
            if row['ready']: raise ValueError('Uncertain browser resource input cannot be replayed')
            row['ready'] = True

    def has_run(self, run):
        with self.lock:return identifier(run) in self.runs

    def resource(self, run, ticket, name, *, origin):
        identifier(run); identifier(ticket)
        if origin not in ('primary', 'foreign'): raise ValueError('Unknown actual browser listener')
        with self.lock:
            row = self.runs.get(run)
            if row is None or name not in PAGES | ASSETS: return None
            if row['sequence'] >= 256: raise ValueError('Browser response inventory is full')
            epoch = self.clock_ms()
            if type(epoch) is not int or not 0 < epoch <= 2**53 - 1 or epoch < row['epoch']:
                raise ValueError('Browser fixture clock is unavailable or regressed')
            response = secrets.token_hex(16)
            status = 404 if name == 'recovery.html' and not row['ready'] else 200
            if name == 'feature-marker.js':
                path = '/feature-fixture/v1/runs/' + run
                body = ('(function(){let busy=false;async function refresh(){if(busy)return;busy=true;try{'
                    'let r=await fetch("' + path + '/current",{cache:"no-store"});if(!r.ok)return;let v=await r.json();'
                    'if(typeof v.ticket!=="string"||v.ticket.length!==32||!/^[0-9a-f]{32}$/.test(v.ticket))return;'
                    'let m=document.getElementById("feature-marker"),p="' + path + '/tickets/"+v.ticket+"/marker.png";'
                    'if(m&&m.getAttribute("src")!==p)m.src=p;}finally{busy=false}}refresh();setInterval(refresh,100);})();').encode()
                content_type = 'application/javascript'
            elif name in ASSETS:
                body = pinned_resource('web-source/'+name); content_type = 'application/javascript'
            else:
                # Reuse the actual reference DOM and real echo protocol. The
                # fixture never fills echo output or cooperatively rejects an
                # untrusted origin; native authority must reject it.
                body = pinned_resource('web-source/index.html').decode('utf-8')
                title = 'Overte web parity ' + ('foreign ' if origin=='foreign' else '') + ('second' if name == 'page-b.html' else
                    'recovery unavailable' if status == 404 else 'recovery available' if name == 'recovery.html' else 'reference')
                body = body.replace('Overte web parity reference', title)
                body = body.replace('href="index.html?page=second"', 'id="second" href="page-b.html"')
                body = body.replace('<button id="back">', '<a id="reference" href="reference.html">Reference document</a><button id="back">')
                # A real ordinary link exposes the failing/recovered resource.
                body = body.replace('<button id="back">', '<a id="recovery" href="recovery.html">Recovery document</a><button id="back">')
                marker = '/feature-fixture/v1/runs/' + run + '/tickets/' + ticket + '/marker.png'
                head = ('<meta name="overte-fixture-response" content="' + response + '">'
                        '<meta name="overte-fixture-owner" content="' + run + '">')
                body = body.replace('</head>', head + '</head>')
                # An ordinary fixed fixture header keeps the current challenge
                # and actual document label visible after native history/scroll
                # restoration. It grants no bridge and supplies no observation.
                # Its full viewport width keeps all 128 challenge bits legible
                # when the original high-DPI Web entity is rendered in-world.
                color = ('#594917' if origin=='foreign' else '#4d2e5c' if name=='page-b.html' else
                         '#5c2828' if status==404 else '#285c32' if name=='recovery.html' else '#263d52')
                style = ('<style>body{padding-top:calc(25vw + 96px)}'
                    '#feature-marker{position:fixed;left:0;top:0;width:100vw;height:25vw;image-rendering:pixelated;z-index:2147483646;pointer-events:none}'
                    '#feature-document-label{position:fixed;left:0;top:25vw;width:100%;height:88px;box-sizing:border-box;padding:12px;'
                    'font:24px sans-serif;color:white;background:'+color+';z-index:2147483646;pointer-events:none}</style>')
                body = body.replace('</head>',style+'</head>')
                body = body.replace('<body>', '<body><img id="feature-marker" alt="Owned challenge" src="' + marker + '">' +
                    '<div id="feature-document-label">'+title+'</div>')
                body = body.replace('</body>', '<script src="feature-marker.js"></script></body>')
                body = body.encode('utf-8'); content_type = 'text/html; charset=utf-8'
            row['sequence'] += 1; row['epoch'] = epoch
            row['responses'].append(dict(sequence=row['sequence'], responseId=response, capturedEpochMs=epoch,
                ticket=ticket, resource=name, origin=origin, status=status, bytes=len(body), sha256=hashlib.sha256(body).hexdigest()))
            return status, content_type, body, response

    def snapshot(self, run):
        with self.lock:
            row = self.runs[identifier(run)]
            return dict(browserFixtureVersion=1, instance=row['instance'], ready=row['ready'],
                sequence=row['sequence'], responses=deepcopy(row['responses']))

    def close(self, run):
        with self.lock:
            self.runs.pop(identifier(run), None)
