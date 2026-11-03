#pragma once
#include "repository.h"
#include "sms.h"
#include "settings.h"
#include "speech.h"
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QProcess>
class Controller final:public QObject {
 Q_OBJECT
 Q_CLASSINFO("D-Bus Interface", "org.etherneco.EtherSMS")
 Q_PROPERTY(QVariantList conversations READ conversations NOTIFY changed)
 Q_PROPERTY(QVariantList messages READ messages NOTIFY changed)
 Q_PROPERTY(QVariantList contacts READ contacts NOTIFY changed)
 Q_PROPERTY(QString number READ number NOTIFY changed)
 Q_PROPERTY(QString draft READ draft WRITE setDraft NOTIFY draftChanged)
 Q_PROPERTY(QString error READ error NOTIFY changed)
 Q_PROPERTY(int unread READ unread NOTIFY changed)
 Q_PROPERTY(bool hasOlder READ hasOlder NOTIFY changed)
 Q_PROPERTY(bool hasNewer READ hasNewer NOTIFY changed)
 Q_PROPERTY(QString proposal READ proposal NOTIFY proposalChanged)
 Q_PROPERTY(bool aiBusy READ aiBusy NOTIFY proposalChanged)
public:
 Controller(ISmsTransport *transport,SmsSettings *settings,Speech *speech,const QString &database,QObject *parent=nullptr);
 QVariantList conversations(){return m_repo.ready()?m_repo.conversations(m_search):QVariantList();}
 QVariantList messages(){return m_repo.ready()?m_repo.messages(m_number,m_messageSearch,m_offset):QVariantList();}
 QVariantList contacts(){return m_repo.contacts(m_search);}
 bool hasOlder(){return m_repo.messageCount(m_number,m_messageSearch)>m_offset+200;}
 bool hasNewer()const{return m_offset>0;}
 Q_INVOKABLE void older(){if(hasOlder()){m_offset+=200;emit changed();}}
 Q_INVOKABLE void newer(){m_offset=qMax(0,m_offset-200);emit changed();}
 QString number()const{return m_number;}QString draft()const{return m_draft;}QString error()const{return m_error;}
 QString proposal()const{return m_proposal;}bool aiBusy()const{return m_reply!=nullptr;}int unread(){return m_repo.unread();}
 void setDraft(const QString &text);
 Q_INVOKABLE void open(const QString &number);
 Q_INVOKABLE void search(const QString &text);Q_INVOKABLE void searchMessages(const QString &text);
 Q_INVOKABLE QVariantMap estimate(const QString &text)const;
 Q_INVOKABLE bool validRecipient(const QString &number)const;
 Q_INVOKABLE bool send();Q_INVOKABLE void retry(const QString &id);Q_INVOKABLE void remove(const QString &id);Q_INVOKABLE void copy(const QString &text);
 Q_INVOKABLE void saveContact(const QString &number,const QString &name);Q_INVOKABLE void deleteContact(const QString &number);
 Q_INVOKABLE bool backup(const QString &path);
 Q_INVOKABLE void correct(const QString &mode);Q_INVOKABLE void reject();Q_INVOKABLE void accept();
 Q_INVOKABLE void speak(const QString &text);Q_INVOKABLE void stopPlayback();
 Q_INVOKABLE void setVisible(bool visible);
 Q_INVOKABLE void keyboard();
 Q_INVOKABLE void openSettings();
public slots:
 void Activate(){emit activated();}
 int GetUnread(){return unread();}
signals:void activated();void changed();void draftChanged();void proposalChanged();
private slots:void notificationAction(uint id,const QString &action);
private:
 void notify(const QVariantMap &message);void publishUnread();
 Repository m_repo;ISmsTransport *m_transport;SmsSettings *m_settings;Speech *m_speech;
 QString m_number,m_draft,m_search,m_messageSearch,m_error,m_proposal,m_original,m_aiNumber;
 int m_offset=0;bool m_visible=false;QNetworkAccessManager m_network;QNetworkReply *m_reply=nullptr;QProcess m_tts,m_playback;QByteArray m_voice;QMap<uint,QString> m_notifications;
};
