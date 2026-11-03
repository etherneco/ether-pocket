#pragma once
#include <QObject>
#include <QVariantList>
#include <QVariantMap>
#include <QTimer>
#include <QRect>
#include <QMap>
#include <QSet>
#include <QImage>
#include <QQuickImageProvider>

// An EWMH client of the existing WM. Never claims SubstructureRedirect.
class Pocket : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantList windows READ windows NOTIFY changed)
    Q_PROPERTY(QStringList windowIds READ windowIds NOTIFY windowIdsChanged)
    Q_PROPERTY(QString activeClass READ activeClass NOTIFY changed)
    Q_PROPERTY(QVariantMap activeProfile READ activeProfile NOTIFY changed)
    Q_PROPERTY(bool enabled READ enabled NOTIFY changed)
    Q_PROPERTY(bool external READ external NOTIFY changed)
    Q_PROPERTY(double gestureStart READ gestureStart CONSTANT)
    Q_PROPERTY(double gestureEnd READ gestureEnd CONSTANT)
    Q_PROPERTY(QString activeId READ activeId NOTIFY changed)
    Q_PROPERTY(QVariantMap activeWindow READ activeWindow NOTIFY changed)
    Q_PROPERTY(QVariantMap capabilities READ capabilities CONSTANT)
public:
    explicit Pocket(QObject *parent=nullptr);
    ~Pocket();
    QVariantList windows() const { return m_windows; }
    QStringList windowIds() const;
    QString activeClass() const { return m_activeClass; }
    QVariantMap activeProfile() const { return profile(m_activeClass); }
    bool enabled() const { return !m_safe; }
    bool external() const { return m_external; }
    double gestureStart() const { return m_gestureStart; }
    double gestureEnd() const { return m_gestureEnd; }
    QString activeId() const { return m_active?QString("0x%1").arg(m_active,0,16):QString(); }
    QVariantMap activeWindow() const;
    QVariantMap capabilities() const { return m_capabilities; }
    Q_INVOKABLE void presentation(int margin, int radius, bool previews, bool lowPower);
    Q_INVOKABLE void bindHeader(QObject *header, const QString &windowId);
    Q_INVOKABLE void moveBy(const QString &id,int dx,int dy);
    Q_INVOKABLE void resizeBy(const QString &id,int dx,int dy);
    Q_INVOKABLE void resizeTo(const QString &id,int width,int height);
    QImage preview(const QString &id, int width);
    Q_INVOKABLE void scan();
    Q_INVOKABLE void action(const QString &action, const QString &id=QString());
    Q_INVOKABLE void setEnabled(bool enabled);
    Q_INVOKABLE void diagnose(const QString &path);
signals:
    void changed();
    void windowIdsChanged();
private:
    struct Saved { QRect geometry,keyboardGeometry; bool maxH=false,maxV=false,fullscreen=false,keyboardFullscreen=false,styled=false,originalShaped=false,shapeApplied=false; QString policy,signature,identity; QVector<unsigned long> motif; QSize shapeSize; int shapeRadius=-1; };
    void *m_display=nullptr;
    QTimer m_timer;
    QMap<unsigned long,Saved> m_saved;
    QVariantList m_windows;
    QVariantMap m_config;
    unsigned long m_active=0;
    QString m_activeClass;
    bool m_safe=false,m_external=false;
    double m_gestureStart=.08,m_gestureEnd=.92;
    bool m_surface=false,m_previews=true,m_shape=false;
    bool m_nativeFrames=false;
    int m_margin=16,m_radius=24;
    QVariantMap m_capabilities;
    QSet<unsigned long> m_redirected;
    QString m_recoveryFile;
    QTimer m_debounce;
    void decorate(unsigned long window,Saved &saved,const QSize &size,bool fullscreen);
    void restoreDecoration(unsigned long window,const Saved &saved);
    void persist();
    QRect phone() const;
    QRect usable(const QRect &screen) const;
    QVariantMap profile(const QString &wmClass) const;
    void restore();
    void releasePreviews();
    void fit(unsigned long window, const QRect &frame);
    void state(unsigned long window, const char *name, bool on, const char *second=nullptr);
    void send(unsigned long window,const char *type,long a=0,long b=0,long c=0,long d=0,long e=0);
};

class WindowPreviews : public QQuickImageProvider {
public:
    explicit WindowPreviews(Pocket *p):QQuickImageProvider(QQuickImageProvider::Image),pocket(p){}
    QImage requestImage(const QString &id,QSize *size,const QSize &requested) override {auto image=pocket->preview(id.split('?').first(),requested.width()>0?requested.width():420);if(size)*size=image.size();return image;}
private:
    Pocket *pocket;
};
