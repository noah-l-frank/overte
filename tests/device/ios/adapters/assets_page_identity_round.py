"""One synchronous quiet-window's immutable page origin, never current facts.

The existing full identity source is physically read before/after the window.
All raw-original membership, file identities, metadata, held locks, directory
contents and owning contexts remain guarded. Nothing survives this scope.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_feature_observation import need
from adapters.native_clock_join import digest
from adapters.original_file_reads import collect
from adapters.script_feature.history import same
from ios.adapters.assets_end_metadata import signature


class PageIdentityRound:
    def __init__(self,picker,eligible):
        need(callable(eligible) and eligible(picker));self.picker,self.parent,self.eligible=picker,picker.page_lease,eligible
        self.active=True;self.origin=None;self.parents=(self.parent,self.parent.episodes,self.parent.episodes.selected)
        self.contexts=tuple((index,value,value.files) for index,value in sorted(self.parent.pickers.items()))
        self.headers()
        with collect() as reads:self.origin=deepcopy(self.parent.identity())
        self.reads=set(reads);self.origin_digest=digest(self.origin);self.memory=self.memory_identity()
        self.paths=self.reads|{owner.store.path for owner in (*self.parents,*[value for _i,value,_files in self.contexts],*[files for _i,_value,files in self.contexts])}
        self.pins={path:signature(path) for path in self.paths};need(all(pin is not None for pin in self.pins.values()))
        roots={path.parent for path in self.paths}
        for info in self.parent.episodes.context['roles'].values():roots.update(Path(info[key]) for key in ('stateRoot','artifactRoot'))
        for row in self.parent.episodes.state['entries']:
            roots.update(Path(value['path']) for role in row['directories'].values() for value in role.values() if value['identity'] is not None)
        self.roots=roots;self.directories=self.directory_identity();self.fast_guard();self.headers()
    def headers(self):
        for owner in (*self.parents,*[value for _i,value,_files in self.contexts],*[files for _i,_value,files in self.contexts]):
            need(same(owner.store.read(),owner.previous))
    def memory_identity(self):
        return digest([[(owner.store.path.as_posix(),owner.previous,owner.state) for owner in self.parents],
            [(index,id(picker),id(files),picker.previous,picker.state,files.previous,files.state) for index,picker,files in self.contexts],
            self.parent.binding,self.parent.run,self.picker.binding,self.picker.episode.link()])
    def fast_guard(self):
        need(self.active and self.eligible(self.picker) and digest(self.origin)==self.origin_digest)
        self.parent.lock.assert_held();self.picker.lock.assert_held()
        need(tuple((index,id(value),id(value.files)) for index,value in sorted(self.parent.pickers.items()))
            ==tuple((index,id(value),id(files)) for index,value,files in self.contexts))
        return True
    def directory_identity(self):
        result={}
        for root in self.roots:
            entries=list(root.iterdir());need(len(entries)<=8192)
            result[str(root)]=(signature(root),{path.name:signature(path) for path in entries})
        return result
    def page(self,current,state):
        self.fast_guard();return self.picker._cleanup_page_from_origin(current,state,self.origin)
    def close(self):
        try:
            self.fast_guard();self.headers();need(self.memory==self.memory_identity())
            need(self.pins=={path:signature(path) for path in self.paths} and self.directories==self.directory_identity())
            with collect() as reads:again=self.parent.identity()
            need(same(self.origin,again) and self.reads==set(reads));self.headers()
            need(self.memory==self.memory_identity() and self.pins=={path:signature(path) for path in self.paths}
                and self.directories==self.directory_identity())
        finally:self.active=False;self.origin=None
    def __enter__(self):self.fast_guard();return self
    def __exit__(self,kind,error,traceback):
        try:self.close()
        except BaseException as secondary:
            if error is None:raise
            error.add_note('Closing Assets page origin window also failed: '+type(secondary).__name__)
        return False
