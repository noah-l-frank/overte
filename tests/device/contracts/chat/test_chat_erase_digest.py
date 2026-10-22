"""Compile the original bounded Erase digest against real Qt item models.

QML page/model association is an explicit seam; no application or device runs.
This focused compiler check is separate from the no-build control-plane suite.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]


def body(source, marker):
    start = source.index(marker); opening = source.index('{', start)
    depth = 1; end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}'); end += 1
    return source[start:end]


HARNESS = r'''
#include <QAbstractListModel>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDataStream>
#include <QRegularExpression>
#include <cassert>
struct QQuickItem {};
struct Rows:QAbstractListModel {
    QVariantList values;bool role{true};
    int rowCount(const QModelIndex& parent=QModelIndex()) const override { return parent.isValid()?0:values.size(); }
    QVariant data(const QModelIndex& at,int name) const override { return name==Qt::UserRole && at.isValid()?values.value(at.row()):QVariant(); }
    QHash<int,QByteArray> roleNames() const override { return role?QHash<int,QByteArray>{{Qt::UserRole,"text"}}:QHash<int,QByteArray>(); }
};
Rows local,domain;bool available{true};
inline QAbstractItemModel* chatModel(QQuickItem*,const char* name) {
    if(!available)return nullptr;
    auto model=QByteArray(name)=="localHistory"?&local:QByteArray(name)=="domainHistory"?&domain:nullptr;
    return model && model->rowCount()<=1000?model:nullptr;
}
SOURCE
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);QQuickItem page;
    local.values={QString("one"),QString("two")};domain.values={QString::fromUtf8("Overte ä Ω 東京")};
    const auto original=chatEraseHistoryDigest(&page);
    assert(QRegularExpression("\\A[0-9a-f]{64}\\z").match(original).hasMatch());
    assert(chatEraseHistoryDigest(&page)==original);
    local.values[0]=QString("foreign private row");assert(chatEraseHistoryDigest(&page)!=original);
    local.values={QString("two"),QString("one")};assert(chatEraseHistoryDigest(&page)!=original);
    local.values={QString("one"),QString("two"),QString("two")};assert(chatEraseHistoryDigest(&page)!=original);
    local.values={QString("one")};domain.values={QString("two"),QString::fromUtf8("Overte ä Ω 東京")};assert(chatEraseHistoryDigest(&page)!=original);
    available=false;assert(chatEraseHistoryDigest(&page).isEmpty());available=true;
    local.values={QVariant(true)};assert(chatEraseHistoryDigest(&page).isEmpty());
    local.values={QString(4097,'x')};assert(chatEraseHistoryDigest(&page).isEmpty());
    local.values={QString("one")};local.role=false;assert(chatEraseHistoryDigest(&page).isEmpty());local.role=true;
    local.values.clear();for(int i=0;i<40;++i)local.values.append(QString(4096,'x'));
    assert(chatEraseHistoryDigest(&page).isEmpty());
    local.values.clear();domain.values.clear();const auto empty=chatEraseHistoryDigest(&page);
    assert(empty.size()==64 && empty!=original);
}
'''


class ChatEraseDigestTests(unittest.TestCase):
    def test_original_digest_binds_every_actual_model_row_without_exporting_private_text(self):
        source = (ROOT / 'tests/device/native/NormalChatControls.h').read_text()
        major = os.environ.get('OVERTE_CHAT_TEST_QT', 'Qt5')
        self.assertIn(major, ('Qt5', 'Qt6'))
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', major + 'Core'], text=True))
        if os.environ.get('PKG_CONFIG_SYSROOT_DIR'):
            library = subprocess.check_output(['pkg-config', '--variable=libdir', major + 'Core'], text=True).strip()
            flags = ['-L' + library, '-Wl,-rpath,' + library, *flags]
        with tempfile.TemporaryDirectory(prefix='overte-chat-erase-digest-') as scratch:
            unit = Path(scratch) / 'test.cpp'; binary = Path(scratch) / 'test'
            unit.write_text(HARNESS.replace('SOURCE', body(source, 'inline QString chatEraseHistoryDigest(')))
            compiled = subprocess.run(['c++', '-std=c++17', '-fPIC', str(unit), '-o', str(binary), *flags],
                capture_output=True, text=True, timeout=45)
            self.assertEqual(0, compiled.returncode, compiled.stderr[:6000])
            executed = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
            self.assertEqual(0, executed.returncode, executed.stderr[:2000])


if __name__ == '__main__': unittest.main()
