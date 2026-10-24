// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Production callbacks and Qt timers/focus queries are real; UIKit is a seam.
#include <QGuiApplication>
#include <QQuickItem>
#include <QQuickWindow>
#include <QPointer>
#include <QSharedPointer>
#include <QInputMethodQueryEvent>
#include <QTimer>
#include <QEventLoop>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <iostream>

struct NativeBoundary {
    bool userEditorOrPresentation { false };
    int dismissals { 0 };
} native;
void dismissIOSKeyboard() { ++native.dismissals; }
void dismissIOSStartupKeyboard() {
    // Public UIKit/WK responder/controller inspection remains a native seam.
    if (!native.userEditorOrPresentation) { ++native.dismissals; }
}
class Editor : public QQuickItem {
public:
    bool editable { false };
    explicit Editor(QQuickItem* parent) : QQuickItem(parent) {
        setFlag(ItemAcceptsInputMethod, true);
    }
    QVariant inputMethodQuery(Qt::InputMethodQuery query) const override {
        return query == Qt::ImEnabled ? QVariant(editable) : QQuickItem::inputMethodQuery(query);
    }
};
struct OffscreenUi : QObject {
    bool _focusText { false };
    QQuickWindow window;
#include "production-offscreen-focus-getter.inc"
    QQuickWindow* getWindow() { return &window; }
};
struct Application : QObject {
    QSharedPointer<OffscreenUi> ui { new OffscreenUi };
    QSharedPointer<OffscreenUi> getOffscreenUI() { return ui; }
    void initialize() {
#include "production-startup-cleanup.inc"
    }
};
void wait(int milliseconds) {
    QEventLoop loop;
    QTimer::singleShot(milliseconds, &loop, &QEventLoop::quit);
    loop.exec();
}
int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);
    QJsonArray results;
    const auto check = [&](const char* name, int expected, const auto& arrange) {
        native = {};
        Application application;
        Editor editor(application.ui->window.contentItem());
        application.ui->window.show();
        editor.forceActiveFocus();
        app.processEvents();
        application.initialize();
        const bool immediateCleaned = native.dismissals == 1;
        arrange(application, editor);
        wait(1080); // Execute the unscaled production 250ms and 1000ms timers.
        const bool passed = immediateCleaned && native.dismissals == expected;
        results.append(QJsonObject{{"case", name}, {"expected", expected},
            {"actual", native.dismissals}, {"passed", passed}});
    };
    check("idle hidden editor still cleaned at initialization, 250ms and 1000ms", 3,
        [](Application&, Editor&) {});
    for (int focusAt : {100, 500}) {
        check(focusAt == 100 ? "cached QML focus before250ms" : "cached QML focus before1000ms",
            focusAt == 100 ? 1 : 2, [focusAt](Application& application, Editor&) {
                QTimer::singleShot(focusAt, &application, [&application] { application.ui->_focusText = true; });
            });
        check(focusAt == 100 ? "live native Web IM query before250ms despite stale focus cache" :
                              "live native Web IM query before1000ms despite stale focus cache",
            focusAt == 100 ? 1 : 2, [focusAt](Application& application, Editor& editor) {
                QTimer::singleShot(focusAt, &application, [&editor] { editor.editable = true; editor.forceActiveFocus(); });
            });
        check(focusAt == 100 ? "UIKit/WK editor or presentation before250ms" : "UIKit/WK editor or presentation before1000ms",
            focusAt == 100 ? 1 : 2, [focusAt](Application& application, Editor&) {
                QTimer::singleShot(focusAt, &application, [] { native.userEditorOrPresentation = true; });
            });
    }
    check("editor released before1000ms permits idle cleanup", 2,
        [](Application& application, Editor&) {
            QTimer::singleShot(100, &application, [&application] { application.ui->_focusText = true; });
            QTimer::singleShot(500, &application, [&application] { application.ui->_focusText = false; });
        });
    // The real QPointer callback cannot touch a replacement/deleted UI owner.
    native = {};
    {
        Application application;
        application.initialize();
        application.ui.reset();
        wait(1080);
        results.append(QJsonObject{{"case", "deleted OffscreenUi owner"}, {"expected", 1},
            {"actual", native.dismissals}, {"passed", native.dismissals == 1}});
    }
    native = {};
    { Application application; application.initialize(); }
    wait(1080);
    results.append(QJsonObject{{"case", "destroyed application cancels timers"}, {"expected", 1},
        {"actual", native.dismissals}, {"passed", native.dismissals == 1}});
    int failures = 0;
    for (const auto& result : results) { failures += !result.toObject()["passed"].toBool(); }
    std::cout << QJsonDocument(QJsonObject{{"cases", results}, {"failures", failures}}).toJson().toStdString();
    return failures ? 1 : 0;
}
