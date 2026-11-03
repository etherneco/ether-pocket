#pragma once
#include <QObject>
#include <QVariantList>
#include <QNetworkAccessManager>
#include <QJsonObject>
#include <functional>

class Distributor : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantList catalog READ catalog NOTIFY changed)
    Q_PROPERTY(QString status READ status NOTIFY changed)
    Q_PROPERTY(QString ray READ ray NOTIFY changed)
    Q_PROPERTY(bool busy READ busy NOTIFY changed)
public:
    explicit Distributor(QObject *parent=nullptr);
    QVariantList catalog() const {return m_rows;}
    QString status() const {return m_status;}
    QString ray() const {return m_ray;}
    bool busy() const {return m_pending>0;}
    Q_INVOKABLE void refresh();
    Q_INVOKABLE void diagnose(const QString &path);
signals:
    void changed();
    void refreshed(bool ok);
private:
    void get(const QString &,std::function<void(const QJsonObject&)>);
    void page(int number);
    void finish();
    QVariantList emptyRows() const;
    QNetworkAccessManager m_network;
    QVariantList m_rows,m_next;
    QString m_status,m_ray,m_cache;
    int m_pending=0,m_pages=0,m_errors=0,m_httpStatus=0;
    bool m_blocked=false;
};
