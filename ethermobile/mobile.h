#pragma once
#include "provider.h"
#include "dbustypes.h"
#include <QDBusMessage>
#include <QProcess>
#include <QTimer>
#include <functional>

class Mobile final : public ModemProvider {
    Q_OBJECT
    Q_PROPERTY(QVariantMap status READ snapshot NOTIFY changed)
    Q_PROPERTY(QVariantList modems READ modems NOTIFY changed)
    Q_PROPERTY(QVariantList profiles READ profiles NOTIFY changed)
    Q_PROPERTY(QVariantList stages READ stages NOTIFY changed)
    Q_PROPERTY(bool busy READ busy NOTIFY changed)
    Q_PROPERTY(QString message READ message NOTIFY changed)
    Q_PROPERTY(QVariantMap editor READ editor NOTIFY editorChanged)
    Q_PROPERTY(QVariantMap operation READ operation NOTIFY operationChanged)
    Q_PROPERTY(QVariantList modes READ modes NOTIFY changed)
    Q_PROPERTY(QVariantList operators READ operators NOTIFY changed)
    Q_PROPERTY(QVariantMap usage READ usage NOTIFY usageChanged)
public:
    explicit Mobile(QObject *parent=nullptr);
    QVariantMap snapshot() const override { return m_status; }
    QVariantList modems() const { return m_modems; }
    QVariantList profiles() const { return m_profiles; }
    QVariantList stages() const { return m_stages; }
    bool busy() const { return m_busy || m_doctor.state()!=QProcess::NotRunning; }
    QString message() const { return m_message; }
    QVariantMap editor()const{return m_editor;}
    QVariantMap operation()const{return m_operation;}
    QVariantList modes()const{return m_modes;}
    QVariantList operators()const{return m_operators;}
    QVariantMap usage()const{return m_usage;}
    Q_INVOKABLE void refresh() override;
    Q_INVOKABLE void selectModem(const QString &path);
    Q_INVOKABLE void diagnose();
    Q_INVOKABLE void saveProfile(const QString &path, const QString &name, const QString &apn, bool roaming, bool internetRoute, const QString &ipType);
    Q_INVOKABLE void deleteProfile(const QString &path);
    Q_INVOKABLE void connectProfile(const QString &path);
    Q_INVOKABLE void disconnectData();
    Q_INVOKABLE void setRadio(bool enabled);
    Q_INVOKABLE void sendPin(const QString &pin);
    Q_INVOKABLE void editConfiguration(const QString &path, bool duplicate=false);
    Q_INVOKABLE void saveConfiguration(const QVariantMap &fields);
    Q_INVOKABLE void deleteConfiguration(const QString &path,const QString &version);
    Q_INVOKABLE void clearConfigurationSecrets(const QString &path,const QString &version);
    Q_INVOKABLE void rollbackConfiguration();
    Q_INVOKABLE void changeProfilePreferences(const QString &path,const QString &version,bool autoconnect,bool roaming);
    Q_INVOKABLE void restoreProviderDefaults();
    Q_INVOKABLE void simAction(const QString &action,const QString &first,const QString &second=QString());
    Q_INVOKABLE void scanOperators();
    Q_INVOKABLE void registerOperator(const QString &code);
    Q_INVOKABLE void applyMode(const QString &id);
    Q_INVOKABLE void rollbackMode();
    Q_INVOKABLE void selectSimSlot(int slot);
    Q_INVOKABLE void reconnectProfile(const QString &path);
    Q_INVOKABLE void rollbackConnection();
    Q_INVOKABLE void sampleUsage();
    Q_INVOKABLE void setUsageOptions(int billingDay,double warningMegabytes);
signals:
    void editorChanged();
    void operationChanged();
    void usageChanged();
private slots:
    void scheduleRefresh();
private:
    void fetchProfiles();
    void fetchNetwork();
    void fetchSim();
    void recompute();
    void fetchIpaData();
    void mergeIpaData();
    void ipaDataAction(bool connect,const QString &profile=QString());
    void mutate(const QString &service,const QString &path,const QString &iface,const QString &method,const QVariantList &args,std::function<void()> accepted={});
    bool knownProfile(const QString &path) const;
    void fail(const QString &message);
    void result(const QString &state,const QString &message);
    bool beginOperation(const QString &description);
    void readProfile(const QString &path,std::function<void(bool,Settings,quint64)> done);
    QVariantMap profileFields(const QString &path,const Settings &settings,quint64 version)const;
    void writeVerified(const QString &path,Settings settings,quint64 version,Settings previous={},bool rollback=false);
    void monitorConnection(bool connected);
    void finishObservedOperation();
    using Reply=std::function<void(const QDBusMessage&)>;
    void call(const QString &service,const QString &path,const QString &iface,const QString &method,const QVariantList &args,Reply done,bool interactive=false,int timeoutMs=15000);
    ManagedObjects m_objects;
    QMap<QString,Settings> m_settings;
    QVariantMap m_status;
    QVariantList m_modems,m_profiles,m_stages;
    QString m_selected,m_device,m_active,m_sim,m_message;
    bool m_busy=false,m_fetching=false,m_dirty=false,m_mmAvailable=false;
    bool m_nmActivated=false,m_hasIp=false;
    bool m_ipa=false,m_dataFetching=false,m_ipaOperation=false;
    quint32 m_dataMainPid=0;
    QVariantMap m_dataState,m_dataUnit;
    QTimer m_dataTimer;
    quint64 m_generation=0,m_networkGeneration=0,m_profileGeneration=0;
    QTimer m_debounce;
    QTimer m_doctorTimeout;
    QProcess m_doctor;
    QVariantMap m_editor,m_operation{{"state","Ready"}},m_usage;
    QVariantMap m_networkInfo;
    QVariantMap m_simInfo;
    QString m_simInfoPath;
    QVariantList m_modes,m_operators;
    Settings m_editBaseline,m_rollbackSettings;
    quint64 m_editVersion=0,m_rollbackVersion=0;
    QString m_editPath,m_rollbackPath,m_ipInterface,m_activeProfile,m_reconnectProfile;
    bool m_duplicate=false;
    int m_connectionTarget=-1;
    QTimer m_operationTimeout,m_usageTimer;
    RadioMode m_previousMode,m_appliedMode;
    bool m_modeRollback=false;
    std::function<bool()> m_verify;
    QString m_activationProfile,m_previousConnectionProfile;
    quint64 m_previousConnectionVersion=0;
};
