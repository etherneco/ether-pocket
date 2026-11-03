#pragma once
#include <QObject>
#include <QVariantList>
#include <QVariantMap>
#include <QProcess>
#include <QTimer>
#include <QQueue>
#include <QImage>
#include <QQuickImageProvider>
#include <functional>
class QDBusMessage;
class Bluetooth;

class Icons : public QQuickImageProvider {
public:
    Icons(): QQuickImageProvider(QQuickImageProvider::Image) {}
    QImage requestImage(const QString &, QSize *, const QSize &) override;
};

class Core : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantList apps READ apps NOTIFY appsChanged)
    Q_PROPERTY(QVariantList windows READ windows NOTIFY windowsChanged)
    Q_PROPERTY(QVariantList networks READ networks NOTIFY networksChanged)
    Q_PROPERTY(QVariantList displays READ displays NOTIFY displaysChanged)
    Q_PROPERTY(QVariantList notices READ notices NOTIFY noticesChanged)
    Q_PROPERTY(int smsUnread READ smsUnread NOTIFY smsUnreadChanged)
    Q_PROPERTY(QVariantMap telemetry READ telemetry NOTIFY telemetryChanged)
    Q_PROPERTY(QVariantMap preferences READ preferences NOTIFY preferencesChanged)
    Q_PROPERTY(QObject* bluetooth READ bluetooth CONSTANT)
    Q_PROPERTY(QVariantMap settingsData READ settingsData NOTIFY settingsDataChanged)
    Q_PROPERTY(QString message READ message NOTIFY messageChanged)
    Q_PROPERTY(bool busy READ busy NOTIFY messageChanged)
    Q_PROPERTY(bool keyboardFocusAvailable READ keyboardFocusAvailable NOTIFY keyboardFocusChanged)
    Q_PROPERTY(bool physicalKeyboardConnected READ physicalKeyboardConnected NOTIFY physicalKeyboardChanged)
public:
    explicit Core(QObject *parent=nullptr);
    ~Core();
    QVariantList apps() const {return m_apps;}
    QVariantList windows() const {return m_windows;}
    QVariantList networks() const {return m_networks;}
    QVariantList displays() const {return m_displays;}
    QVariantList notices() const {return m_notices;}
    int smsUnread()const{return m_smsUnread;}
    Q_INVOKABLE void activateNotice(uint id);
    void synchronizeNotices(const QVariantList &cards){m_notices=cards;emit noticesChanged();}
    QVariantMap telemetry() const {return m_telemetry;}
    QVariantMap preferences() const {return m_preferences;}
    QObject *bluetooth() const;
    QVariantMap settingsData() const {return m_settingsData;}
    Q_INVOKABLE void inspectSettings(const QString &page);
    Q_INVOKABLE void wifiProfileAction(const QString &uuid,const QString &action);
    Q_INVOKABLE void audioDevice(const QString &kind,const QString &name);
    Q_INVOKABLE void defaultBrowser(const QString &desktopId);
    QString message() const {return m_message;}
    bool busy() const {return m_busy>0;}
    bool keyboardFocusAvailable() const {return m_keyboardFocusAvailable;}
    bool physicalKeyboardConnected() const {return m_physicalKeyboardConnected;}
    Q_INVOKABLE void discover();
    Q_INVOKABLE void refresh();
    void setPowerState(const QVariantMap &state);
    Q_INVOKABLE void launch(const QString &id);
    Q_INVOKABLE void windowAction(const QString &id, const QString &action);
    Q_INVOKABLE void setting(const QString &name, const QVariant &value);
    Q_INVOKABLE void control(const QString &action, const QString &value=QString());
    Q_INVOKABLE void connectWifi(const QString &ssid, const QString &password);
    Q_INVOKABLE void key(const QString &symbol, bool ctrl=false, bool alt=false, bool shift=false, bool super=false, bool altgr=false);
    Q_INVOKABLE void text(const QString &text);
    Q_INVOKABLE void pointer(int dx, int dy);
    Q_INVOKABLE void mouse(int button, bool down);
    Q_INVOKABLE void configureWindow(QObject *window, const QString &kind, int reserve=0);
    Q_INVOKABLE void notify(const QString &title, const QString &body);
    Q_INVOKABLE void clearNotices();
    Q_INVOKABLE void diagnose(const QString &path);
    Q_INVOKABLE void nativeFrameTheme(bool desktop);
signals:
    void appsChanged(); void windowsChanged(); void networksChanged();
    void displaysChanged(); void noticesChanged(); void telemetryChanged();
    void preferencesChanged(); void messageChanged();
    void smsUnreadChanged();
    void noticeActivated(uint id);
    void settingsDataChanged();
    void keyboardFocusChanged();void textInputFocus(bool editable);
    void physicalKeyboardChanged();
private slots:
    void accessibleFocus(const QDBusMessage &message);
    void updateSmsUnread(int count);
    void readSmsUnread();
private:
    int m_smsUnread=0;
    Bluetooth *m_bluetooth=nullptr;
    void setupAccessibility();
    void run(const QString &, const QStringList &, std::function<void(int,QString)> done={}, bool report=true);
    void status(const QString &);
    void readTelemetry();
    bool savePreferences();
    void sendNextText();
    void injectKey(const QString &,bool,bool,bool,bool,bool);
    QVariantList m_apps,m_windows,m_networks,m_displays,m_notices;
    QVariantMap m_telemetry,m_preferences;
    QVariantMap m_powerState;
    QVariantMap m_settingsData;
    QString m_message,m_config;
    QString m_mappingJournal;
    QString m_accessibilityBus;
    QString m_brightnessSession;
    bool m_keyboardFocusAvailable=false;
    bool m_physicalKeyboardConnected=false;
    quint64 m_focusRevision=0;
    QTimer m_inputTimer;
    QString m_nativeFrameTheme;
    QTimer m_timer;
    int m_busy=0;
    bool m_refreshing=false;
    void *m_display=nullptr;
    struct Input {QString text,symbol;bool ctrl=false,alt=false,shift=false,super=false,altgr=false;};
    QQueue<Input> m_textQueue;
    bool m_typing=false;
    int m_injectionCode=0,m_mappingWidth=0;
    QVector<unsigned long> m_originalMapping;
    bool m_restoreOnboard=false;
    unsigned int m_previousLocked=0,m_previousLatched=0;
};

