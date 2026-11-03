#pragma once
#include <QObject>
#include <functional>
#include <QProcess>
#include <QVariantList>
class Audio : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantList outputs MEMBER outputs NOTIFY changed)
    Q_PROPERTY(QVariantList inputs MEMBER inputs NOTIFY changed)
    Q_PROPERTY(QVariantList cards MEMBER cards NOTIFY changed)
    Q_PROPERTY(QString status MEMBER status NOTIFY changed)
public:
    explicit Audio(QObject *parent=nullptr);
    Q_INVOKABLE void refresh();
    Q_INVOKABLE void select(const QString &kind,const QString &name);
    Q_INVOKABLE void volume(const QString &name,int percent);
    Q_INVOKABLE void mute(const QString &name,bool enabled);
    Q_INVOKABLE void profile(const QString &card,const QString &profile);
    Q_INVOKABLE void controlPanel();
signals:
    void changed();
private:
    void run(const QStringList &,std::function<void(int,QByteArray)>);
    void mutate(const QStringList &);
    QVariantList outputs,inputs,cards;
    QString status="Audio backend has not been inspected.";
    bool refreshing=false;
    int pending=0;
};
