// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Only the native sound/enum endpoints are fixtures; Phone controls are real.
#include <QtQuickTest/quicktest.h>
#include <QQmlContext>
#include <QQmlEngine>
#include <QQmlFileSelector>
#include <QJSValue>
#include <QObject>

class TabletBoundary : public QObject {
    Q_OBJECT
public:
    Q_INVOKABLE void playSound(int) {}
};

class PhoneSetup : public QObject {
    Q_OBJECT
    TabletBoundary tablet;
public slots:
    void qmlEngineAvailable(QQmlEngine* engine) {
        qmlRegisterModule("TabletScriptingInterface", 1, 0);
        engine->rootContext()->setContextProperty("Tablet", &tablet);
        engine->rootContext()->setContextProperty("TabletEnums",
            QVariant::fromValue(engine->evaluate("({ButtonClick:0,ButtonHover:1})")));
        auto selector = new QQmlFileSelector(engine, engine);
        selector->setExtraSelectors({"android_phoneInterface", "android_interface"});
    }
};

QUICK_TEST_MAIN_WITH_SETUP(phone_emote, PhoneSetup)
#include "phone-native-context.moc"
