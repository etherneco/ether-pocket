#pragma once
#include <QObject>
#include <QSettings>
#include <QVariantMap>
#include <QProcess>
class SmsSettings final:public QObject {
 Q_OBJECT
 Q_PROPERTY(QVariantMap values READ values NOTIFY changed)
 Q_PROPERTY(QVariantMap diagnostics READ diagnostics NOTIFY changed)
public:
 explicit SmsSettings(QObject *parent=nullptr);
 ~SmsSettings();
 QVariantMap values()const;QVariantMap diagnostics()const{return m_diagnostics;}
 Q_INVOKABLE void set(const QString &key,const QVariant &value);
 Q_INVOKABLE void refresh();
 Q_INVOKABLE void launch();
 Q_INVOKABLE void installModel(const QString &source,const QString &sha);
 Q_INVOKABLE void downloadModel(const QString &variant,const QString &sha);
 Q_INVOKABLE void removeModel(const QString &name);
signals:void changed();
private:QSettings m_settings;QVariantMap m_diagnostics;QProcess m_probe,m_model;
};
