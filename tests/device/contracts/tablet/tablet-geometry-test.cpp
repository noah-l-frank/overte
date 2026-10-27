// SPDX-License-Identifier: Apache-2.0
// Execute the actual presenter resize method with the Qt item/service boundaries.
#include <QGuiApplication>
#include <QQuickItem>
#include <QThread>
#include <QVariantMap>
#include <cassert>
#include <algorithm>

class TabletScriptingInterface : public QObject {
    Q_OBJECT
public:
    QVariantMap metrics;
    QVariantMap getTouchUiRuntimeMetrics() const { return metrics; }
};
struct DesktopWindow {
    QQuickItem root;
    QQuickItem* asQuickItem() { return &root; }
    void setPosition(int x, int y) { root.setPosition(QPointF(x, y)); }
    void setSize(int w, int h) { root.setSize(QSizeF(w, h)); }
};
class TabletProxy : public QObject {
    Q_OBJECT
public:
    using QObject::QObject;
    bool _androidScreenSpaceMode { true };
    DesktopWindow window;
    DesktopWindow* _desktopWindow { &window };
public slots:
    void resizeAndroidTablet(int width, int height);
};
#include "tablet-geometry-test.moc"
#include "production.inc"

int main(int argc, char** argv) {
    QGuiApplication application(argc, argv);
    struct Case { int w, h, left, right, x, width; };
    const Case cases[] {
        {2400, 1080, 132, 0, 132, 2136},
        {2400, 1080, 0, 132, 132, 2136},
        {1024, 768, 8, 32, 32, 960},
        {640, 360, 24, 8, 24, 592},
        {360, 640, 0, 0, 0, 360},
        {100, 80, 80, 19, 80, 1}, // never sacrifice real cutout protection
    };
    for (const auto& c : cases) {
        for (bool runtime : {false, true}) {
            TabletScriptingInterface service;
            TabletProxy tablet(&service);
            auto& root = tablet.window.root;
            root.setProperty("screenSpaceCenterHorizontally", true);
            for (int cycle = 0; cycle < 3; ++cycle) {
                for (int ime : {0, c.h / 2, 0}) {
                    const QVariantMap metrics {
                        {"valid", runtime}, {"surfaceWidth", c.w}, {"surfaceHeight", c.h},
                        {"safeInsetLeft", c.left}, {"safeInsetRight", c.right},
                        {"safeInsetTop", 12}, {"safeInsetBottom", 24},
                        {"imeInsetBottom", ime}, {"density", 2.625}, {"contentScale", 2.5}
                    };
                    service.metrics = metrics;
                    root.setProperty("screenSpaceSafeInsetLeft", c.left);
                    root.setProperty("screenSpaceSafeInsetRight", c.right);
                    root.setProperty("screenSpaceSafeInsetTop", 12);
                    root.setProperty("screenSpaceSafeInsetBottom", 24);
                    root.setProperty("screenSpaceImeInsetBottom", ime);
                    // Valid runtime measurements win over a caller's stale/reduced size.
                    tablet.resizeAndroidTablet(c.w + (runtime ? 123 : 0), c.h + (runtime ? 456 : 0));
                    assert(root.x() == c.x && root.width() == c.width);
                    assert(root.y() == 12 && root.height() == c.h - 12 - std::max(24, ime));
                }
            }
            root.setProperty("screenSpaceCenterHorizontally", false);
            tablet.resizeAndroidTablet(c.w, c.h);
            assert(root.x() == c.left && root.width() == c.w - c.left - c.right);
        }
    }
}
