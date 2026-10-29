"""Explicit Callback paired-window2 selects Live2 and typed Actor originals.

Existing receipt/role/held/sample clocks and exact publication joins remain.
No source cutoff is renewed; no public terminal/process/SDK gate is opened.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from ios.adapters.emote_terminal_window import IOSEmoteTerminalWindow
from ios.adapters.emote_callback_live import IOSEmoteCallbackLive
from ios.adapters import emote_callback_archive as archive
from ios.adapters import emote_callback_publications as publications


class IOSEmoteCallbackWindow(IOSEmoteTerminalWindow):
    Live=IOSEmoteCallbackLive
    FORMAT_VERSION=2

    def group_snapshots(self,snapshots,*,lock,primary_lock):return archive.grouped(snapshots,lock=lock,primary_lock=primary_lock)

    def reopen_snapshot(self,snapshot,*,lock,primary_lock):return archive.reopen(snapshot,lock=lock,primary_lock=primary_lock)

    def select_publications(self,snapshot,value,*,retirement_floor,**options):
        selector=publications.select_with_retirement_clocks if retirement_floor else publications.select
        return selector(snapshot,value,**options)
