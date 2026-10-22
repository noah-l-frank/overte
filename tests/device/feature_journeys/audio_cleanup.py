"""One independently observed OS identity exchange after native Audio cleanup.

The adapter separately owns durable Stop/Launch, original native birth counters
and old-process ESRCH. This caller keeps the later common OS guard attached to
that replacement; it cannot grant another restart on an idempotent cleanup.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0


def identity(previous,observed,restarted):
    if type(restarted) is not bool or any(type(value) is not str or not 0<len(value)<=160 or any(ord(c)<33 or ord(c)>126 for c in value) for value in (previous,observed)):
        raise AssertionError('Audio cleanup has no independent OS process identity')
    if restarted and observed!=previous:raise AssertionError('Idempotent Audio cleanup replaced the application again')
    if not restarted and observed==previous:raise AssertionError('Audio cleanup did not replace the native preview process')
    return observed,True
