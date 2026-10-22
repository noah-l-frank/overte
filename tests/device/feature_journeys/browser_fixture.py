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
                title = 'Overte web parity ' + ('second' if name == 'page-b.html' else
                    'recovery unavailable' if status == 404 else 'recovery available' if name == 'recovery.html' else 'reference')
                # The actual selected resource listener supplies this visible
                # distinction; a world view has no native address bar.
                if origin == 'foreign': title = title.replace('parity ', 'parity foreign ', 1)
                body = body.replace('Overte web parity reference', title)
                # Keep the pinned DOM/handlers, making the browser journey's
                # original controls fit its actual bounded world viewport.
                # Independent video parity resources remain unchanged.
                body = body.replace('</head>', '<style id="owned-browser-controls-v1">\nbody{margin:8px;font:16px sans-serif;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:4px}\nbody>section{display:contents}section>*{display:none!important}\nsection>label:has(>input#text),section>label:has(>input#foreign),#bridge,#bridgeStatus,#back,#reload,#recovery,section>a,#navigate{display:block!important}\nh1{grid-column:1;grid-row:1;font-size:18px;margin:0}#document{grid-column:1;grid-row:2;font-size:12px;margin:0;overflow-wrap:anywhere}\n#feature-marker{grid-column:2;grid-row:1/span 2;width:400px;max-width:100%;height:auto;justify-self:end}\nsection>label,#bridgeStatus{grid-column:1/-1}button,input,a{font:inherit;min-height:40px;margin:0;padding:6px;box-sizing:border-box}\ninput{width:100%;display:block}#bridgeStatus{min-height:24px;overflow-wrap:anywhere}\n</style>' + '</head>')
                body = body.replace('href="index.html?page=second"', 'href="page-b.html"')
                # A real ordinary link exposes the failing/recovered resource.
                body = body.replace('<button id="back">', '<a id="recovery" href="recovery.html">Recovery document</a><a id="reference" href="reference.html">Reference document</a><button id="back">')
                marker = '/feature-fixture/v1/runs/' + run + '/tickets/' + ticket + '/marker.png'
                head = ('<meta name="overte-fixture-response" content="' + response + '">'
                        '<meta name="overte-fixture-owner" content="' + run + '">')
                body = body.replace('</head>', head + '</head>')
                body = body.replace('<body>', '<body><img id="feature-marker" alt="Owned challenge" src="' + marker + '">')
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
