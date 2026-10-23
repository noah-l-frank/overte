"""Persistent actual generated host JS, driven only by ordinary model inputs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import select
import subprocess


class TabletHostApp:
    def __init__(self,test,filename):
        script=Path(__file__).with_suffix('.js')
        self.process=subprocess.Popen(['node',str(script),str(filename)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
        test.addCleanup(self.close)
        self.original=self.call('read')
    def call(self,operation,**arguments):
        if self.process.poll() is not None:raise AssertionError('Host Script ended before ordinary input')
        self.process.stdin.write(json.dumps(dict(operation=operation,**arguments),ensure_ascii=True)+'\n');self.process.stdin.flush()
        if not select.select([self.process.stdout],[],[],5)[0]:raise AssertionError('Host Script callback did not return')
        line=self.process.stdout.readline()
        if not line:raise AssertionError('Host Script output ended: '+self.process.stderr.read())
        receipt=json.loads(line)
        if receipt.get('okay') is not True:raise AssertionError(receipt)
        return receipt['value']
    def close(self):
        if self.process.stdin:self.process.stdin.close()
        try:self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:self.process.terminate();self.process.wait(timeout=5)
        for stream in (self.process.stdout,self.process.stderr):
            if stream:stream.close()
