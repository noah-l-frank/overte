"""Retain one explicitly admitted private namespace by atomic directory move.

Immutable archive copies must precede the move. A directory move removes the
old namespace in one mutation while preserving every original leaf, byte and
physical stamp. It grants no product, process or feature cleanup by itself.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import ctypes
import hashlib
import os
from pathlib import Path

from adapters.chat_journey.archive_file import ClosedOriginalFile,signature
from adapters.chat_journey.evidence_archive import ChatArchiveCatalog,private
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.native_feature_observation import need
from adapters.script_journey.history import canonical

VERSION=1
RENAME_NOREPLACE=1


def rename_original(source_parent,source_name,destination_parent,destination_name):
    """Linux atomic no-replacement move, with no overwrite/copy fallback."""
    rename=getattr(ctypes.CDLL(None,use_errno=True),'renameat2',None)
    need(rename is not None)
    rename.argtypes=(ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint)
    rename.restype=ctypes.c_int
    result=rename(source_parent.fd,os.fsencode(source_name),destination_parent.fd,
        os.fsencode(destination_name),RENAME_NOREPLACE)
    if result:raise OSError(ctypes.get_errno(),'Original namespace retirement is unresolved')


class OriginalDirectoryRetirement:
    """One warm catalog, no discovery, unknown-file adoption or move replay."""
    def __init__(self,catalog,source,destination):
        need(type(catalog) is ChatArchiveCatalog and not catalog.hold_files and not catalog.failed
            and type(source) is type(destination) is type(Path('/'))
            and source.is_absolute() and destination.is_absolute() and source!=destination
            and source.parent!=destination and destination.parent!=source
            and not destination.exists() and not destination.is_symlink()
            and source in catalog.parents and destination.parent in catalog.parents)
        rows=tuple((label,row,row['owner'],row['store'],row['store'].path,
            tuple(row['stamp']),row['raw'],row['sha256'],canonical(row['expected']))
            for label,row in catalog.rows.items() if row['store'].path.parent==source)
        need(rows and all(type(owner) is ClosedOriginalFile and 'retire' not in row
            and label.rsplit('/',1)[-1]==path.name
            for label,row,owner,_store,path,*_rest in rows))
        self.catalog,self.source,self.destination=catalog,source,destination
        self.directory=catalog.parents[source];self.destination_parent=catalog.parents[destination.parent]
        self.source_parent=OriginalDescriptor(source.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        self.rows=self.original_rows=rows
        self.labels=tuple(row[0] for row in rows)
        self.scope=self.original_scope=(catalog,source,destination,self.directory,self.destination_parent,self.source_parent,self.labels)
        self.before=tuple(signature(os.fstat(self.directory.fd)));self.after=None
        self.attempted=self.moved=self.failed=False;self.uncertain=[]
        self.scope_bytes=self.original_scope_bytes=canonical(dict(originalDirectoryRetirementVersion=VERSION,
            source=str(source),destination=str(destination),directoryStamp=list(self.before),
            originals=[dict(label=label,name=path.name,stamp=list(stamp),bytes=len(raw),sha256=sha)
                for label,_row,_owner,_store,path,stamp,raw,sha,_expected in rows]))
        try:self.verify()
        except BaseException:
            self.failed=True
            if not self.source_parent.close():self.uncertain.append(self.source_parent)
            raise

    def control(self):
        need(not self.failed and self.scope is self.original_scope and self.rows is self.original_rows
            and type(self.rows) is tuple and self.scope_bytes is self.original_scope_bytes
            and type(self.scope_bytes) is bytes
            and (self.catalog,self.source,self.destination,self.directory,self.destination_parent,self.source_parent,self.labels)==self.scope)
        for label,row,owner,store,path,stamp,raw,sha,expected in self.rows:
            need(self.catalog.rows.get(label) is row and row['owner'] is owner and row['store'] is store
                and store.path is path and owner.path is path and not owner.failed and owner.active is None
                and row['raw'] is raw and owner.raw is raw and type(raw) is bytes
                and tuple(row['stamp'])==tuple(owner.stamp)==stamp and row['sha256']==sha
                and hashlib.sha256(raw).hexdigest()==sha and canonical(row['expected'])==expected)

    def verify(self,*,historical=False):
        """Fresh complete namespace, exact leaf bytes and original paired OFDs."""
        need(type(historical) is bool);self.control();base=self.destination if self.moved else self.source
        directory=self.directory;temporary=False
        if directory.closed:
            # After proven host closure this is solely a physical archive
            # readback. It cannot rearm a move or become live product evidence.
            need(historical and self.moved and self.attempted and not directory.lost
                and directory.fd==directory.anchor==-1)
            directory=OriginalDescriptor(base,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            temporary=True
            if directory.node!=self.directory.node:
                need(directory.close());need(False)
        try:self.verify_window(base,directory)
        finally:
            if temporary:
                if not directory.close():self.uncertain.append(directory)
                need(directory.closed and not directory.lost)

    def verify_window(self,base,directory):
        require_directory(directory,base)
        expected_stamp=self.after if self.moved else self.before
        need(tuple(signature(base.lstat()))==tuple(signature(os.fstat(directory.fd)))==expected_stamp)
        os.lseek(directory.fd,0,os.SEEK_SET)
        with os.scandir(directory.fd) as entries:
            need({entry.name for entry in entries}=={row[4].name for row in self.rows})
        for _label,_row,_owner,_store,path,stamp,raw,_sha,_expected in self.rows:
            actual=base/path.name;owner=OriginalDescriptor(actual,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
            try:
                info=os.fstat(owner.fd);private(info)
                need(tuple(signature(info))==tuple(signature(actual.lstat()))==stamp)
                observed=os.pread(owner.fd,65537,0)
                owner.require(owner.fd)
                need(observed==raw and tuple(signature(os.fstat(owner.fd)))==tuple(signature(actual.lstat()))==stamp)
            finally:
                if not owner.close():self.uncertain.append(owner)
                need(owner.closed and not owner.lost)
        require_directory(directory,base)
        need(tuple(signature(base.lstat()))==tuple(signature(os.fstat(directory.fd)))==expected_stamp)
        if self.moved:need(not self.source.exists() and not self.source.is_symlink())
        else:need(not self.destination.exists() and not self.destination.is_symlink())

    def verify_physical(self):
        """Fresh complete physical inventory within the SAME move transaction.

        Full bytes precede the source callback. Before mutation every leaf's
        eight kernel fields must still match those exact original bytes. No
        DirEntry/stat or current observation survives this pass. The move's
        postcondition reacquires all bytes through paired file descriptors.
        """
        self.control();need(not self.moved)
        require_directory(self.directory,self.source)
        need(tuple(signature(self.source.lstat()))==tuple(signature(os.fstat(self.directory.fd)))==self.before)
        os.lseek(self.directory.fd,0,os.SEEK_SET)
        with os.scandir(self.directory.fd) as scan:
            entries={entry.name:entry for entry in scan}
            need(set(entries)=={row[4].name for row in self.rows})
            for _label,_row,_owner,_store,path,stamp,_raw,_sha,_expected in self.rows:
                info=entries[path.name].stat(follow_symlinks=False);private(info)
                need(tuple(signature(info))==stamp)
        require_directory(self.directory,self.source)
        need(tuple(signature(self.source.lstat()))==tuple(signature(os.fstat(self.directory.fd)))==self.before
            and not self.destination.exists() and not self.destination.is_symlink())

    def retire(self,check,*,before_move):
        """Called only after archive copies and durable exact group intent.

        The caller's final source/phase and original deadline check follows all
        local verification and immediately precedes the one atomic mutation.
        Unknown delivery remains attempted, with no second call permitted.
        """
        try:
            need(not self.attempted and callable(check) and callable(before_move));self.verify()
            require_directory(self.source_parent,self.source.parent)
            require_directory(self.destination_parent,self.destination.parent)
            need(os.fstat(self.source_parent.fd).st_dev==os.fstat(self.destination_parent.fd).st_dev)
            check()
            # The callback may have performed IO. Recheck original namespaces
            # before the syscall; it never grants permission to replace them.
            self.verify_physical();require_directory(self.source_parent,self.source.parent)
            require_directory(self.destination_parent,self.destination.parent)
            before_move()
            self.attempted=True
            rename_original(self.source_parent,self.source.name,self.destination_parent,self.destination.name)
            self.moved=True
            os.fsync(self.source_parent.fd);os.fsync(self.destination_parent.fd)
            self.after=tuple(signature(os.fstat(self.directory.fd)))
            # rename changes only the original directory's ctime, not leaves.
            need(self.after[:7]==self.before[:7] and self.after[7]>=self.before[7])
            self.verify()
        except BaseException:self.failed=True;raise

    def receipt(self):
        try:self.verify(historical=True);need(self.moved and self.attempted)
        except BaseException:self.failed=True;raise
        return dict(originalDirectoryRetirementVersion=VERSION,
            scopeSha256=hashlib.sha256(self.scope_bytes).hexdigest(),
            source=str(self.source),destination=str(self.destination),
            originals=len(self.rows),originalUnlinks=0,atomicDirectoryMoves=1,
            directoryBefore=list(self.before),directoryAfter=list(self.after))

    def close_host(self):
        # Catalog owns the original source/destination directory pairs.
        return all([self.source_parent.close()]+[owner.close() for owner in self.uncertain])
