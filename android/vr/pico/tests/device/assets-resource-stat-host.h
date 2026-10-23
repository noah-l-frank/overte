// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QString>
#include <QMap>
// Statistics storage only; no network/cache/renderer result is manufactured.
class StatTracker {
public:
 QMap<QString,qint64> values;
 void incrementStat(const QString& name){++values[name];}
 void updateStat(const QString& name,qint64 delta){values[name]+=delta;}
};
