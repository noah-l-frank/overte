#!/usr/bin/env python3
"""Run production avatar metadata and timing traversal with both Qt majors."""
# Copyright 2026 Overte e.V.
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
import re
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
avatar_source = (ROOT / 'interface/src/Application_UI.cpp').read_text()
metadata = re.search(r'QString modelName = fstMapping[^;]+;\s*QString modelLicense = fstMapping[^;]+;',
                     avatar_source)
assert metadata, 'production avatar metadata lookup is missing'
stats_source = (ROOT / 'interface/src/ui/Stats.cpp').read_text()
start = stats_source.index('        int linesDisplayed = 0;')
end_marker = '        emit timingStatsChanged();'
end = stats_source.index(end_marker, start) + len(end_marker)
timing = stats_source[start:end]
program = r'''
#include <cassert>
#include <utility>
#include <QObject>
#include <QMap>
#include <QMultiMap>
#include <QStringList>
#include <shared/HifiTypes.h>
struct PerformanceTimerRecord {
    double micros;
    int count;
    double getMovingAverage() const { return micros; }
    int getCount() const { return count; }
};
constexpr double USECS_PER_MSEC = 1000.0;
std::pair<QString, QString> avatarMetadata(hifi::VariantMultiHash& fstMapping) {
    @METADATA@
    return {modelName, modelLicense};
}
QString timingStats(const QMultiMap<float, QString>& sortedRecords,
                    const QMap<QString, PerformanceTimerRecord>& allRecords,
                    bool onlyDisplayTopTen) {
    QString _timingStats;
    auto timingStatsChanged = [] {};
    @TIMING@
    return _timingStats;
}
QStringList names(const QString& text) {
    QStringList result;
    for (const auto& line : text.split(QChar(10), Qt::SkipEmptyParts)) {
        result.append(line.section(QChar(':'), 0, 0).trimmed());
    }
    return result;
}
int main() {
    hifi::VariantMultiHash mapping;
    mapping.insert(QStringLiteral("name"), QStringLiteral("earlier"));
    mapping.insert(QStringLiteral("name"), QStringLiteral("latest"));
    mapping.insert(QStringLiteral("license"), QStringLiteral("license text"));
    const auto size = mapping.size();
    auto metadata = avatarMetadata(mapping);
    assert(metadata.first == QStringLiteral("latest"));
    assert(metadata.second == QStringLiteral("license text"));
    assert(mapping.size() == size);
    hifi::VariantMultiHash missing;
    metadata = avatarMetadata(missing);
    assert(metadata.first.isEmpty() && metadata.second.isEmpty() && missing.isEmpty());
    QMap<QString, PerformanceTimerRecord> records;
    QMultiMap<float, QString> sorted;
    auto add = [&](const QString& name, double micros) {
        records.insert(name, {micros, 3});
        sorted.insert(float(micros / USECS_PER_MSEC), name);
    };
    add(QStringLiteral("slowest"), 3000);
    add(QStringLiteral("duplicate-a"), 2000);
    add(QStringLiteral("duplicate-b"), 2000);
    add(QStringLiteral("fastest"), 1000);
    assert(names(timingStats(sorted, records, false)) == QStringList({
        QStringLiteral("slowest"), QStringLiteral("duplicate-a"),
        QStringLiteral("duplicate-b"), QStringLiteral("fastest")}));
    sorted.clear(); records.clear();
    assert(timingStats(sorted, records, false).isEmpty());
    for (int value = 0; value < 15; ++value) {
        add(QStringLiteral("entry%1").arg(value), value * USECS_PER_MSEC);
    }
    auto top = names(timingStats(sorted, records, true));
    assert(top.size() == 10);
    for (int index = 0; index < 10; ++index) {
        assert(top[index] == QStringLiteral("entry%1").arg(14 - index));
    }
    assert(names(timingStats(sorted, records, false)).size() == 15);
}
'''.replace('@METADATA@', metadata.group()).replace('@TIMING@', timing)

with tempfile.TemporaryDirectory(prefix='overte-qt-containers-') as directory:
    folder = Path(directory)
    source = folder / 'containers.cpp'
    source.write_text(program)
    for major in ('5', '6'):
        flags = shlex.split(subprocess.check_output(
            ['pkg-config', '--cflags', '--libs', 'Qt' + major + 'Core'], text=True))
        binary = folder / ('qt' + major)
        subprocess.run(['c++', '-std=c++17', '-fPIC',
                        '-I' + str(ROOT / 'libraries/shared/src'), str(source),
                        '-o', str(binary), *flags, '-UNDEBUG'], check=True, timeout=60)
        subprocess.run([str(binary)], check=True, timeout=10)
        print('PASS Qt' + major + ': production metadata lookup and descending timing traversal')
