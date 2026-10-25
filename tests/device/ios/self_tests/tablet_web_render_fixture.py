"""Explicit host screenshot model from actual controlled DOM/image sources.

This produces model WDA PNG bytes, never native/UIKit/GPU evidence. Original
marker bytes are fetched from the actual DOM image URL or decoded from its
actual inline data source. No requested ticket, expected page or actor fact is
an operand of rendering.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from io import BytesIO
from urllib.parse import urlsplit
from urllib.request import urlopen
from PIL import Image,ImageDraw,ImageFont
from adapters.native_feature_observation import need


def screenshot(boundary):
    actual=boundary.host_app.call('page-render');view=actual['render'];need(view is not None)
    source=view['markerSource'];need(type(source) is str)
    if source.startswith('data:image/png;base64,'):raw=base64.b64decode(source.split(',',1)[1],validate=True)
    else:
        parsed=urlsplit(source)
        origins=[urlsplit(value) for value in boundary.runtime.observer.origins.values()]
        need(any((parsed.scheme,parsed.netloc)==(origin.scheme,origin.netloc) for origin in origins)
            and not parsed.query and not parsed.fragment and parsed.username is parsed.password is None
            and parsed.path.startswith(urlsplit(boundary.source.fixture).path+'tickets/') and parsed.path.endswith('/marker.png'))
        with urlopen(source,timeout=5) as response:raw=response.read(65537)
        need(len(raw)<=65536)
    with Image.open(BytesIO(raw)) as original:
        original.load();need(original.size==(160,40));marker=original.convert('RGB')
    image=Image.new('RGB',(500,800),(32,37,44));draw=ImageDraw.Draw(image)
    draw.rectangle((0,0,499,43),fill='white');draw.text((12,12),'Close',fill='black')
    draw.text((12,52),view['title'],font=ImageFont.load_default(size=18),fill='white')
    draw.text((12,80),view['href'],font=ImageFont.load_default(size=11),fill='white')
    draw.rectangle((12,144,488,184),fill='white',outline='black')
    draw.text((18,152),view['text'],fill='black')
    rect=view['markerRect'];need(rect['right']-rect['left']==160 and rect['bottom']-rect['top']==40)
    image.paste(marker,(round(rect['left']),round(rect['top']+44)))
    output=BytesIO();image.save(output,format='PNG');return output.getvalue()
