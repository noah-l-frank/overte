// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Declared EntityTree/HUD dependencies, original Application/Keyboard bodies.
#include "tests/device/native/PicoWorldCurrentConsumptionBridge.h"
#include <QPointer>
#include <QKeyEvent>
#include <QInputMethodEvent>
#include <QDateTime>
#include <thread>
const QUuid UNKNOWN_ENTITY_ID;
quint64 usecTimestampNow(){return quint64(QDateTime::currentMSecsSinceEpoch())*1000;}
struct Application:QGuiApplication {
    using QGuiApplication::QGuiApplication;
    struct Focus {QUuid value;QUuid get()const{return value;}} _keyboardFocusedEntity;
    struct Entities {QObject* handler{};QObject* getEventHandler(const QUuid&){return handler;}} entities;
    quint64 _lastAcceptedKeyPress{0};
    bool isHMDMode(){return true;}
    QUuid getKeyboardFocusEntity()const{return _keyboardFocusedEntity.get();}
    void setKeyboardFocusEntity(const QUuid& value){_keyboardFocusedEntity.value=value;}
    Entities* getEntities(){return &entities;}
    QObject* getPrimaryWidget(){return entities.handler;}
    bool handleKeyEventForFocusedEntity(QEvent*);
    bool handleInputMethodEventForFocusedEntity(QEvent*);
    bool dispatchVirtualKeyboardEvent(QEvent*,const QUuid&);
};
using CurrentAppBoundary=Application;
#undef qApp
#define qApp static_cast<Application*>(QCoreApplication::instance())
struct Keyboard:QObject {
    bool _inputToHudUI{false};QUuid _inputTarget;
    bool containsID(const QUuid&)const{return false;}
    void dispatchKey(int,Qt::KeyboardModifiers,const QString&);
};
// ORIGINAL_METHODS
