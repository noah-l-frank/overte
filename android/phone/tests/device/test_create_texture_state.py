"""Actual Qt mutex-protected texture provenance under concurrent readers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]
SOURCE=r'''#include "tests/device/native/CreateTextureState.h"
#include <atomic>
#include <thread>
#include <vector>
using overte::e2e::CreateTextureState;
int main() {
    CreateTextureState state;
    std::atomic<bool> done{false},failed{false};
    std::vector<std::thread> readers;
    for(int n=0;n<4;++n)readers.emplace_back([&] {
        while(!done.load()) {
            auto value=state.read();const int size=value.value("originalBytes").toInt();
            if(size) {
                const auto raw=QByteArray(size,char(size%251));
                if(value.value("originalSha256").toString()!=QString::fromLatin1(QCryptographicHash::hash(raw,QCryptographicHash::Sha256).toHex()))failed=true;
            }
            CreateTextureState copy;copy.copyFrom(state);auto original=copy.read();
            const int copied=original.value("originalBytes").toInt();
            if(copied && original.value("originalSha256").toString()!=QString::fromLatin1(QCryptographicHash::hash(
                    QByteArray(copied,char(copied%251)),QCryptographicHash::Sha256).toHex()))failed=true;
        }
    });
    for(int n=1;n<3000;++n) {
        const int size=1+n%1024;state.decode(QByteArray(size,char(size%251)));
        state.resource(QString(64,'a'),true,false,16,16,true);
        if(n%37==0)state.refresh();
    }
    done=true;for(auto&thread:readers)thread.join();if(failed)return 1;
    CreateTextureState retired;retired.decode("old-decoder");retired.refresh();retired.decode("new-decoder");
    retired.resource(QString(64,'a'),true,false,16,16,true);
    if(retired.read().value("complete").toBool())return 2;
    CreateTextureState overlap;overlap.decode("first");overlap.decode("second");
    overlap.resource(QString(64,'a'),true,false,16,16,true);
    if(overlap.read().value("complete").toBool())return 3;
    CreateTextureState foreign;foreign.resource({},false,false,0,0,false);
    if(foreign.read().value("complete").toBool())return 4;
    CreateTextureState original;original.decode("actual");original.resource(QString(64,'b'),true,false,16,16,true);
    CreateTextureState copy;copy.copyFrom(original);
    if(copy.read()!=original.read())return 5;
    original.refresh();if(copy.read()==original.read())return 6;
    return 0;
}
'''


class CreateTextureStateTests(unittest.TestCase):
    def test_native_mutex_state_keeps_atomic_originals_and_refuses_decoder_overlap(self):
        build=ROOT/'build/create-native-contract';build.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='texture-state-',dir=build) as temporary:
            stage=Path(temporary);(stage/'source.cpp').write_text(SOURCE)
            flags=subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True).split()
            subprocess.run(['c++','-std=c++17','-pthread','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-I'+str(ROOT),
                str(stage/'source.cpp'),'-o',str(stage/'check'),*flags],check=True,timeout=60)
            subprocess.run([str(stage/'check')],check=True,timeout=20)


if __name__=='__main__':unittest.main()
