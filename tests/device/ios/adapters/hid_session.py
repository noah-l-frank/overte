"""Authenticate physical HID on the already-owned userspace Wi-Fi tunnel."""
# Copyright 2026 Overte e.V.
# SPDX-License-Identifier: Apache-2.0
import asyncio
from contextlib import asynccontextmanager, suppress
import ipaddress
import uuid


@asynccontextmanager
async def touch_session(rsd, local_address, *, display_factory=None,
                        hid_factory=None, socket_factory=None, observation=None):
    # An in-process RSD relay has no reachable kernel endpoint. Bind RTP on
    # the exact authenticated tunnel's existing IP stack instead; never open
    # a second tunnel, patch runtime globals or advertise a loopback endpoint.
    address = ipaddress.IPv6Address(local_address)
    if address.is_unspecified or address.is_multicast or address.is_loopback:
        raise ValueError("native HID requires a reachable owned tunnel address")
    if display_factory is None:
        from pymobiledevice3.remote.core_device.display_service import DisplayService
        display_factory = DisplayService
    if hid_factory is None:
        from pymobiledevice3.remote.core_device.hid_service import UniversalHIDServiceService
        hid_factory = UniversalHIDServiceService
    if socket_factory is None:
        from pmd_pytcp.socket import AF_INET6, SOCK_DGRAM, socket
        socket_factory = lambda: socket(AF_INET6, SOCK_DGRAM)
    if observation is not None:
        from ios.adapters.lifecycle_touch_resources import TouchResourceObservation
        if type(observation) is not TouchResourceObservation:
            raise TypeError("Passive touch resource observation is unavailable")
    def edge(name):
        if observation is not None:
            try:TouchResourceObservation.edge(observation,name)
            except Exception:observation.failed=True
    def watch(kind,actual):
        if observation is not None:
            try:TouchResourceObservation.watch(observation,kind,actual)
            except Exception:observation.failed=True
    receiver = socket_factory()
    stream_id = uuid.uuid4()
    drain = None
    try:
        edge('source-entered');watch('receiver',receiver)
        receiver.bind((str(address), 0))
        bound = receiver.getsockname()
        if bound[0] != str(address) or type(bound[1]) is not int or not 0 < bound[1] <= 65535:
            raise RuntimeError("native HID media receiver binding is invalid")
        edge('receiver-bound')
        async def discard_media():
            while True:
                await receiver.recv(65535)
        drain = asyncio.create_task(discard_media())
        watch('drain',drain);edge('drain-created')
        async with display_factory(rsd) as display:
            watch('display',display);edge('display-entered')
            try:
                edge('stream-start-entered')
                await asyncio.wait_for(display.start_video_stream(
                    receiver_ip=str(address), receiver_port=bound[1],
                    sender_ip=rsd.service.address[0], display_id=1,
                    client_session_id=stream_id), timeout=10)
                edge('stream-start-returned')
                await asyncio.sleep(0.3)
                async with hid_factory(rsd) as hid:
                    watch('hid',hid);edge('hid-entered')
                    try:yield hid
                    finally:edge('yield-resumed')
                edge('hid-context-exit-returned')
            finally:
                # Request stop using the UUID chosen before negotiation, even
                # after a lost reply. A returned SDK call alone does not prove
                # native stream absence or device-side session isolation.
                edge('stream-stop-entered')
                await asyncio.wait_for(display.stop_media_stream(stream_id), timeout=5)
                edge('stream-stop-returned')
        edge('display-context-exit-returned')
    finally:
        try:
            if drain is not None:
                edge('drain-cancel-entered')
                drain.cancel()
                edge('drain-cancel-returned')
                with suppress(asyncio.CancelledError, OSError):
                    await drain
                edge('drain-await-settled')
        finally:
            # A failed drain remains an error, but must not prevent the local
            # receiver from releasing its own descriptor.
            edge('receiver-close-entered')
            receiver.close()
            edge('receiver-close-returned')
            edge('source-finally-body-tail-observed')
