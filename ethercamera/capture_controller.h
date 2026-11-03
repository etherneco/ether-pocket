#pragma once
#include <QObject>
#include <QQuickImageProvider>
#include <QImage>
#include <QMutex>
#include <QTimer>
#include <QVariant>
#include <functional>

class CaptureImage:public QQuickImageProvider {
 QMutex mutex;QImage frame;
public:
 CaptureImage():QQuickImageProvider(QQuickImageProvider::Image){}
 void put(const QImage &image);
 QImage requestImage(const QString&,QSize*,const QSize&) override;
};

class CaptureController:public QObject {
 Q_OBJECT
 Q_PROPERTY(QVariantList devices READ devices NOTIFY changed)
 Q_PROPERTY(QString message READ message NOTIFY changed)
 Q_PROPERTY(QString imageSource READ imageSource NOTIFY changed)
 Q_PROPERTY(QString savedReference READ savedReference NOTIFY changed)
 Q_PROPERTY(bool busy READ busy NOTIFY changed)
 Q_PROPERTY(bool active READ active NOTIFY changed)
 Q_PROPERTY(bool recording READ recording NOTIFY changed)
 Q_PROPERTY(bool hasFrame READ hasFrame NOTIFY changed)
 Q_PROPERTY(bool privateState READ privateState NOTIFY changed)
 Q_PROPERTY(bool permissionDenied READ permissionDenied NOTIFY changed)
 Q_PROPERTY(int seconds READ seconds NOTIFY changed)
 QVariantList m_devices;QString m_message,m_source,m_saved,token;
 bool m_busy=false,m_active=false,m_recording=false,m_private=true,m_denied=false,framePending=false,closing=false;
 int generation=0,privacyRevision=0,version=0,m_seconds=0;CaptureImage *images;QTimer frames,clock;
 using Done=std::function<void(QVariant)>;
 void call(const QString&,const QVariantList&,Done,std::function<void(QString)> fail={});
 void clearFrame();void reset();void updateLock();void failed(const QString&);void nextFrame();
public:
 explicit CaptureController(CaptureImage*);
 ~CaptureController() override;
 QVariantList devices()const{return m_devices;}
 QString message()const{return m_message;}QString imageSource()const{return m_source;}
 QString savedReference()const{return m_saved;}
 bool busy()const{return m_busy;}bool active()const{return m_active;}
 bool recording()const{return m_recording;}bool hasFrame()const{return !m_source.isEmpty();}
 bool privateState()const{return m_private;}bool permissionDenied()const{return m_denied;}
 int seconds()const{return m_seconds;}
 Q_INVOKABLE void refresh();
 Q_INVOKABLE void start(const QString &device);
 Q_INVOKABLE void photo();
 Q_INVOKABLE void requestLocation();
 Q_INVOKABLE void enableLocation(bool);
 Q_INVOKABLE void record(bool microphoneConsent);
 Q_INVOKABLE void stopRecording();
 Q_INVOKABLE void release();
 Q_INVOKABLE void gallery();
signals:void changed();void saved(const QString &kind);
private slots:
 void state(const QString&);
 void lockState(const QString&);
 void ownerChanged(const QString&,const QString&,const QString&);
};
