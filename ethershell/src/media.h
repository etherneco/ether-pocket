#pragma once
#include <QObject>
#include <functional>
#include <QVariantList>
#include <QTimer>
#include <QDBusUnixFileDescriptor>
#include <QElapsedTimer>

class Media : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantList images READ images NOTIFY imagesChanged)
    Q_PROPERTY(int volume READ volume NOTIFY volumeChanged)
    Q_PROPERTY(bool muted READ muted NOTIFY volumeChanged)
    Q_PROPERTY(bool screenBlank READ screenOff NOTIFY powerStateChanged)
    Q_PROPERTY(int powerTimeout READ powerTimeout NOTIFY powerStateChanged)
public:
    explicit Media(QObject *parent=nullptr);
    ~Media();
    QVariantList images() const { return m_images; }
    int volume() const { return m_volume; }
    bool muted() const { return m_muted; }
    int powerTimeout() const{return m_powerTimeout;}
    Q_INVOKABLE void scan();
    Q_INVOKABLE void screenshot();
    Q_INVOKABLE void setVolume(int value);
    Q_INVOKABLE void toggleMute();
    Q_INVOKABLE void setScreenBlank(bool blank);
    void setPowerTimeout(int seconds,bool preserveExternal);
    void setLockGuard(std::function<bool()> guard){m_lockGuard=guard;}
    void setSecureLockPolicy(bool enabled);
signals:
    void imagesChanged();
    void volumeChanged();
    void volumeShown();
    void saved(const QString &path);
    void capturing();
    void failed(const QString &message);
    void powerStateChanged();void powerMenuRequested();
private:
    std::function<bool()> m_lockGuard;
    bool m_secureLock=false;
    int m_requestedPowerTimeout=60;
    void events();
    void captureScreen();
    void button(int key, bool down);
    void adjustVolume(int delta);
    void adjustMasterVolume(int delta);
    void readVolume();
    void audioCommand(const QStringList &args);
    bool screenOff() const;
    void syncBlankWindow(bool off);
    QVariantList m_images;
    void *m_display=nullptr;
    int m_opcode=0,m_up=0,m_down=0,m_power=0,m_volume=0,m_pendingDelta=0;
    bool m_muted=false,m_upHeld=false,m_downHeld=false,m_powerHeld=false,m_combo=false,m_saving=false,m_audioBusy=false;
    QTimer m_repeat,m_defer,m_audioPoll;
    QVariant m_oldPowerAction;
    QDBusUnixFileDescriptor m_inhibitor;
    int m_saverEvent=0;
    bool m_screenOff=false,m_wakePress=false,m_dpmsOff=false;
    bool m_softBlank=false,m_restoreDpms=false;
    unsigned long m_blankWindow=0;
    QTimer m_displayPoll;
    QElapsedTimer m_screenWake;
    QTimer m_powerHold;
    bool m_longPress=false,m_preserveExternal=true;
    int m_originalTimeout=-1,m_originalInterval=0,m_originalBlanking=0,m_originalExposures=0,m_powerTimeout=-1;
};
