#pragma once
#include <QString>
#include <QVariantList>
#include <QVariantMap>
#include <QSqlDatabase>
struct SmsEstimate {QString encoding;int units=0,segments=0;};
QString normalizedNumber(QString number);
SmsEstimate estimateSms(const QString &text);
class IMessageRepository {
public:
 virtual ~IMessageRepository()=default;
 virtual QVariantList conversations(const QString &search={})=0;
 virtual QVariantList messages(const QString &number,const QString &search={},int offset=0)=0;
};
class Repository final : public IMessageRepository {
public:
 explicit Repository(const QString &path);~Repository();
 int messageCount(const QString &number,const QString &search={});
 bool ready()const{return m_error.isEmpty();}QString error()const{return m_error;}
 QVariantList conversations(const QString &search={})override;
 QVariantList messages(const QString &number,const QString &search={},int offset=0)override;
 QString enqueue(const QString &number,const QString &text);
 bool receive(const QVariantMap &message);
 bool update(const QString &id,const QString &state,const QString &key,const QString &error);
 bool markRead(const QString &number);int unread();
 QString draft(const QString &number);bool saveDraft(const QString &number,const QString &text);
 bool remove(const QString &id);bool backup(const QString &path);
 QVariantList contacts(const QString &search={});bool contact(const QString &number,const QString &name);bool removeContact(const QString &number);
private:
 QVariantList rows(const QString &sql,const QVariantList &args={});
 bool execute(const QString &sql,const QVariantList &args={});
 QSqlDatabase m_db;QString m_error,m_connection;
};
