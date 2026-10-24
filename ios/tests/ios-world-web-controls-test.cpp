// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include <QtQuickTest/quicktest.h>
#include <QQmlContext>
#include <QQmlEngine>
#include <QQmlFileSelector>
#include <CapabilityProfile.h>
#include <QDir>

class Setup : public QObject {
    Q_OBJECT
public slots:
    void qmlEngineAvailable(QQmlEngine* engine) {
        const QString root = qEnvironmentVariable("OVERTE_WORLD_WEB_SOURCE_ROOT");
        qmlRegisterModule("Hifi", 1, 0);
        qmlRegisterModule("TabletScriptingInterface", 1, 0);
        qmlRegisterModule("PerformanceEnums", 1, 0);
        qmlRegisterModule("OverteIOS", 1, 0);
        qmlRegisterType(QUrl::fromLocalFile(qEnvironmentVariable("OVERTE_WORLD_WEB_BOUNDARY")),
                        "Overte.iOS", 1, 0, "IOSWebView");
        engine->rootContext()->setContextProperty("worldWebRoot", QUrl::fromLocalFile(root).toString());
        engine->addImportPath(root + "/interface/resources/qml");
        auto* selector = new QQmlFileSelector(engine, engine);
        QStringList profile;
        for (const auto& item : overte::ui::profileSelectors(overte::ui::Product::IOS, true)) {
            profile.append(QString::fromStdString(item));
        }
        selector->setExtraSelectors(profile);
    }
};
QUICK_TEST_MAIN_WITH_SETUP(ios_world_web_controls, Setup)
#include "ios-world-web-controls-test.moc"
