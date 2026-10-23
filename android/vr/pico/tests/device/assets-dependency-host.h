// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QSharedPointer>
#include <QtGlobal>
// Explicit per-process host endpoints; never construct absent dependencies.
class DependencyManager {
public:
 template<class T>static QSharedPointer<T>& slot(){static QSharedPointer<T> value;return value;}
 template<class T>static bool isSet(){return !slot<T>().isNull();}
 template<class T>static QSharedPointer<T> get(){if(!isSet<T>()) {qFatal("Unavailable host dependency must not be instantiated");}return slot<T>();}
};
