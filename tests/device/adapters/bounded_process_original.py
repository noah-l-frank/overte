"""One owned process with bounded literal stdout/stderr and failure custody.

This collector supplies no PID interpretation or process-absence verdict.
Its caller must register it and reserve its fixed storage before acquisition.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
import selectors
import subprocess
import time

from adapters.native_feature_observation import need,number


class BoundedProcessOriginal:
    LIMIT=128
    ARGUMENT_BYTES=16384

    def __init__(self,*,monotonic=time.monotonic):
        need(callable(monotonic))
        self.monotonic=monotonic
        self.started=self.deadline=None
        self.argv=None;self.process=None;self.selector=None
        self.buffers={'stdout':bytearray(),'stderr':bytearray()}
        self.eof={'stdout':False,'stderr':False}
        self.overflow=None;self.returncode=None
        self.failure=None;self.cleanup_failures=[]
        self.closed=False;self.result=None;self.used=False

    def now(self):
        value=self.monotonic()
        need(number(value,self.started,1e15))
        if value>=self.deadline:
            raise subprocess.TimeoutExpired(self.argv,self.deadline-self.started)
        return value

    def _cleanup(self):
        # This exact Popen is the only process we can terminate. Keep every
        # actual error and the original handle if a close/wait is uncertain.
        process=self.process
        if process is not None:
            try:
                if process.poll() is None:process.kill()
                self.returncode=process.wait(timeout=2)
            except BaseException as error:
                self.cleanup_failures.append((error,error.__traceback__))
        if self.selector is not None:
            try:self.selector.close()
            except BaseException as error:self.cleanup_failures.append((error,error.__traceback__))
        if process is not None:
            for stream in (process.stdout,process.stderr):
                if stream is not None:
                    try:stream.close()
                    except BaseException as error:self.cleanup_failures.append((error,error.__traceback__))
        self.closed=not self.cleanup_failures and (process is None or process.returncode is not None)

    def capture(self,argv,*,timeout,retain):
        need(not self.used and self.process is None and callable(retain)
             and type(argv) is list and 0<len(argv)<=32
             and all(type(arg) is str and 0<len(arg)<=8192 and '\x00' not in arg for arg in argv)
             and sum(len(arg.encode('utf-8')) for arg in argv)<=self.ARGUMENT_BYTES
             and number(timeout,.001,5))
        self.used=True;self.argv=tuple(argv)
        self.started=self.monotonic();need(number(self.started,0,1e15))
        self.deadline=self.started+timeout
        try:
            self.now()
            self.process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,close_fds=True)
            self.selector=selectors.DefaultSelector()
            for name,stream in (('stdout',self.process.stdout),('stderr',self.process.stderr)):
                os.set_blocking(stream.fileno(),False)
                self.selector.register(stream,selectors.EVENT_READ,name)
            while self.selector.get_map():
                remaining=self.deadline-self.now()
                for key,_events in self.selector.select(min(.05,remaining)):
                    name=key.data;buffer=self.buffers[name]
                    # At most LIMIT+1 bytes are ever acquired per stream.
                    chunk=os.read(key.fd,self.LIMIT+1-len(buffer))
                    if not chunk:
                        self.eof[name]=True;self.selector.unregister(key.fileobj)
                    else:
                        buffer.extend(chunk)
                        if len(buffer)>self.LIMIT:
                            self.overflow=name
                            raise ValueError('Original process output exceeds its bound')
            self.returncode=self.process.wait(timeout=self.deadline-self.now())
            self.now()
            self.result=subprocess.CompletedProcess(self.argv,self.returncode,
                bytes(self.buffers['stdout']),bytes(self.buffers['stderr']))
        except BaseException as error:
            self.failure=(error,error.__traceback__)
        finally:
            self._cleanup()
        if self.failure is None and self.cleanup_failures:
            self.failure=self.cleanup_failures[0]
        # Preserve bounded actual bytes and original failure before any parser
        # or caller postclock. Callback failure cannot replace acquisition error.
        try:retain(self)
        except BaseException as error:
            if self.failure is None:self.failure=(error,error.__traceback__)
            else:self.cleanup_failures.append((error,error.__traceback__))
        if self.failure is not None:
            error,traceback=self.failure
            raise error.with_traceback(traceback)
        if not self.closed:
            error,traceback=self.cleanup_failures[0]
            raise error.with_traceback(traceback)
        try:self.now()
        except BaseException as error:
            self.failure=(error,error.__traceback__)
            raise
        return self.result
