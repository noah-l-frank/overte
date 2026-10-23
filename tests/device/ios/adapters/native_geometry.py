"""Request a stable, fresh native UIKit geometry sample before physical input."""
# Copyright 2026 Overte e.V.
# SPDX-License-Identifier: Apache-2.0
import base64
import json
import time
import uuid
from urllib.request import Request, urlopen

from ios.adapters.appium_adapter import AppiumAdapter
from ios.adapters.viewport import viewport

VERSION=1


def validate(receipt, command_id, *, native_epoch_ms=None):
    if (not isinstance(receipt, dict) or set(receipt) != {
            "schemaVersion", "commandId", "observation"}
            or type(receipt["schemaVersion"]) is not int or receipt["schemaVersion"] != 1
            or receipt["commandId"] != command_id):
        raise ValueError("native geometry sample did not match this request")
    document = receipt["observation"]
    return document, viewport(document,now_ms=native_epoch_ms)


class OriginalGeometry:
    """Existing geometry command with independent native time and originals.

    The legacy component capture below keeps its existing API. Full feature
    acquisition supplies canonical HTTP/AFC guards and an actual native clock.
    The receipt itself has no PID field; process binding is separately guarded.
    """
    def __init__(self,send,original,clock_ms,guard,*,monotonic=time.monotonic,sleep=time.sleep):
        from adapters.native_feature_observation import need
        need(all(callable(fn) for fn in (send,original,clock_ms,guard,monotonic,sleep)))
        self.send,self.original,self.clock_ms,self.guard=send,original,clock_ms,guard
        self.monotonic,self.sleep=monotonic,sleep;self.sequence=0;self.epoch=0;self.last=None

    def capture(self, *, native_before_floor=None):
        from adapters.native_feature_observation import decode,fresh,integer,need,number
        from adapters.normal_ui import NativeUIError
        try:
            need(self.guard() is not False);started=previous=self.monotonic();need(number(started,0,1e15))
            # An explicit floor is an already-retained original BEFORE epoch,
            # never a new current clock. Its owning Source validates PID,
            # native birth/nonce/prefix and acquisition provenance before send.
            # Both terminal clock reads below remain independent and new.
            before=self.clock_ms() if native_before_floor is None else native_before_floor
            need(integer(before,1 if native_before_floor is None else max(1,self.epoch)))
            nonce='ios-'+uuid.uuid4().hex
            current=self.monotonic();need(number(current,previous,1e15) and current-started<1.5);previous=current
            need(self.guard() is not False)
            self.send(dict(schemaVersion=1,commandId=nonce,action='native-geometry-snapshot'))
            for attempt in range(61):
                need(self.guard() is not False)
                raw=self.original();need(type(raw) is str and len(raw.encode())<=65536)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                current=self.monotonic();need(number(current,previous,1e15) and current-started<1.5);previous=current
                if type(value) is dict and value.get('commandId')==nonce:
                    need(type(value.get('schemaVersion')) is int and value['schemaVersion']==1)
                    epoch=self.clock_ms();need(integer(epoch,before))
                    document,_rect=validate(value,nonce,native_epoch_ms=epoch)
                    fresh(document['sampleEpochMs'],epoch)
                    need(integer(document['sampleEpochMs'],max(before,self.epoch))
                         and integer(document['sampleSequence'],max(1,self.sequence)))
                    final=self.clock_ms();need(integer(final,epoch));fresh(document['sampleEpochMs'],final)
                    ended=self.monotonic();need(number(ended,previous,1e15) and ended-started<1.5 and self.guard() is not False)
                    self.sequence,self.epoch=document['sampleSequence'],document['sampleEpochMs']
                    self.last=value;return value
                if attempt<60:self.sleep(.025)
        except Exception:
            raise NativeUIError('Original iOS geometry is unavailable or lost its native binding') from None
        raise NativeUIError('Original iOS geometry did not answer this request')


def capture(client, session, target, observe_process):
    before = observe_process()
    if (not isinstance(before, dict) or type(before.get("pid")) is not int
            or before["pid"] <= 0 or before.get("foregroundRunning") is not True):
        raise RuntimeError("native geometry requires the configured foreground process")
    command_id = "ios-" + uuid.uuid4().hex
    payload = {"schemaVersion": 1, "commandId": command_id,
               "action": "native-geometry-snapshot"}
    origin = target["testBuild"]["fixtureOrigin"]
    AppiumAdapter.controlled_http_url(origin, "native geometry fixture origin")
    request = Request(origin + "/e2e-client-command.json", data=json.dumps(payload).encode(),
                      method="POST", headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=5) as response:
        content = response.read(4097)
        if response.status != 200 or len(content) > 4096 or json.loads(content) != payload:
            raise RuntimeError("owned fixture did not accept the exact native geometry request")
    remote = (f"@{target['appId']}:documents/"
              f"{target['testBuild']['resultsDirectory']}/ios-ui-request-result.json")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        encoded = client.execute(session, "mobile: pullFile", {"remotePath": remote})
        try:
            document, rect = validate(json.loads(base64.b64decode(encoded, validate=True)), command_id)
        except (ValueError, UnicodeError):
            time.sleep(0.1)
            continue
        after = observe_process()
        if (not isinstance(after, dict) or type(after.get("pid")) is not int
                or after["pid"] != before["pid"] or after.get("foregroundRunning") is not True):
            raise RuntimeError("native geometry crossed process or foreground identities")
        return document, rect
    raise RuntimeError("fresh request-bound native UIKit geometry was not observed")
