"""Pure original VM transaction and quiet-window grammar."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,integer,need
from adapters.native_script_object_lifetimes import validate as object_packet,ACTION
from adapters.pico4.browser_measurements import browser_status


def validate_frame(frame,previous,origin,script_url,pid):
    from adapters.pico4.browser_vm import join
    origin,facts=join(frame,script_url,pid,origin=origin)
    if previous:
        old=previous[-1]
        object_packet(frame['objectsBefore'],dict(schemaVersion=1,commandId=frame['objectsBefore']['commandId'],action=ACTION),
            pid,frame['objectsAfter']['capturedEpochMs'],previous=old['objectsAfter'])
        browser_status(frame['http'],old['http'])
        events=frame['scripts']['source']['loads'];old_events=old['scripts']['source']['loads']
        need(not any(row['url']==script_url for row in events['events'][old_events['sequence']:]))
    return origin,facts


def window(frame_count,frame_at,first,last,after_epoch,origin,script_url,pid):
    from adapters.pico4.browser_vm import join
    need(integer(first,0,frame_count-1) and integer(last,first,frame_count-1) and last-first<64 and integer(after_epoch,1))
    rows=[frame_at(index) for index in range(first,last+1)]
    for frame in rows:
        _origin,facts=join(frame,script_url,pid,origin=origin)
        need(facts['retired'] and min(frame['objectsBefore']['requestedEpochMs'],frame['scripts']['requestedEpochMs'],
            frame['objectsAfter']['requestedEpochMs'])>=after_epoch)
    def clocks(frame):return [frame['objectsBefore']['source']['capturedEpochMs'],frame['scripts']['capturedEpochMs'],
        frame['objectsAfter']['source']['capturedEpochMs']]
    for before,after in zip(rows,rows[1:]):
        need(0<after['hostMonotonic']-before['hostMonotonic']<=.5
            and all(0<b-a<=500 for a,b in zip(clocks(before),clocks(after))))
    return len(rows)>=3 and rows[-1]['hostMonotonic']-rows[0]['hostMonotonic']>=3 \
        and all(b-a>=3000 for a,b in zip(clocks(rows[0]),clocks(rows[-1])))
