#include "repository.h"
#include <QSqlQuery>
#include <QSqlRecord>
#include <QSqlError>
#include <QFile>
#include <QDir>
#include <QFileInfo>
#include <QUuid>
#include <QDateTime>
#include <QRegularExpression>
#include <QStandardPaths>
QString normalizedNumber(QString n){n.remove(QRegularExpression("[ ()\\-\\.]"));if(!QRegularExpression("^\\+?[0-9]{3,15}$").match(n).hasMatch())return {};return n;}
SmsEstimate estimateSms(const QString &text){
 const QString basic=QString::fromUtf8("@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà");
 const QString extended="\f^{}\\[~]|€";
 bool gsm=true;int units=0;QList<int> costs;
 for(auto c:text){if(basic.contains(c))costs<<1;else if(extended.contains(c))costs<<2;else{gsm=false;break;}}
 if(!gsm){costs.clear();for(auto c:text.toUcs4())costs<<(c>0xffff?2:1);}
 for(int cost:costs)units+=cost;
 const int single=gsm?160:70,multi=gsm?153:67;int segments=0;
 if(units>0){segments=1;if(units>single){int used=0;for(int cost:costs){if(used+cost>multi){++segments;used=0;}used+=cost;}}}
 return {gsm?"GSM-7":"Unicode (UTF-16)",units,segments};
}
Repository::Repository(const QString &path):m_connection(QUuid::createUuid().toString()){
 const auto directory=QFileInfo(path).absolutePath();if(!QDir().mkpath(directory)){m_error="Cannot create private message directory";return;}
 QFile::setPermissions(directory,QFileDevice::ReadOwner|QFileDevice::WriteOwner|QFileDevice::ExeOwner);
 // Create privately before SQLite opens it; the process also sets umask 0077.
 if(!QFile::exists(path)){QFile f(path);if(!f.open(QIODevice::WriteOnly|QIODevice::NewOnly)){m_error="Cannot create message database";return;}f.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner);}
 m_db=QSqlDatabase::addDatabase("QSQLITE",m_connection);m_db.setDatabaseName(path);
 if(!m_db.open()){m_error="SQLite driver unavailable or database cannot be opened";return;}
 execute("PRAGMA foreign_keys=ON");execute("PRAGMA busy_timeout=3000");
 auto version=rows("PRAGMA user_version");int v=version.value(0).toMap().value("user_version").toInt();
 if(v>2){m_error="Database was created by a newer EtherSMS version";return;}
 if(v==0){
  m_db.transaction();bool ok=true;
  for(const auto &sql:QStringList{
   "CREATE TABLE messages(id TEXT PRIMARY KEY,number TEXT NOT NULL,body TEXT NOT NULL,timestamp TEXT NOT NULL,direction TEXT NOT NULL,state TEXT NOT NULL,encoding TEXT,segments INTEGER,transport TEXT UNIQUE,error TEXT NOT NULL DEFAULT '',unread INTEGER NOT NULL DEFAULT 0)",
   "CREATE INDEX conversation_time ON messages(number,timestamp DESC)",
   "CREATE INDEX unread_messages ON messages(unread)",
   "CREATE TABLE drafts(number TEXT PRIMARY KEY,body TEXT NOT NULL)",
   "CREATE TABLE contacts(number TEXT PRIMARY KEY,name TEXT NOT NULL)",
   "PRAGMA user_version=1"})ok=execute(sql)&&ok;
  if(!ok||!m_db.commit()){m_db.rollback();m_error="Database migration failed; original database retained";return;}
 }
 if(v<2){
  if(!m_db.transaction()||!execute("CREATE TABLE deleted_transports(transport TEXT PRIMARY KEY)")||!execute("PRAGMA user_version=2")||!m_db.commit()){m_db.rollback();m_error="Tombstone migration failed";return;}
 }
 // Reuse EtherContacts for Phone/SMS. Keep the old table only as a private
 // migration archive; all live reads and writes use the attached shared store.
 const auto shared=qEnvironmentVariable("ETHERCONTACTS_DATABASE",QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation)+"/ethercontacts/contacts.sqlite");
 const auto sharedDir=QFileInfo(shared).absolutePath();
 if(!QDir().mkpath(sharedDir)){m_error="Cannot create shared contact directory";return;}
 QFile::setPermissions(sharedDir,QFileDevice::ReadOwner|QFileDevice::WriteOwner|QFileDevice::ExeOwner);
 if(!QFile::exists(shared)){QFile f(shared);if(!f.open(QIODevice::WriteOnly|QIODevice::NewOnly)){m_error="Cannot create shared contact store";return;}f.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner);}
 if(!execute("ATTACH DATABASE ? AS shared",{shared})||
    !execute("CREATE TABLE IF NOT EXISTS shared.people(id TEXT PRIMARY KEY,name TEXT NOT NULL,emails TEXT NOT NULL DEFAULT '[]',photo TEXT NOT NULL DEFAULT '',notes TEXT NOT NULL DEFAULT '',favourite INTEGER NOT NULL DEFAULT 0,recent REAL)")||
    !execute("CREATE TABLE IF NOT EXISTS shared.numbers(number TEXT PRIMARY KEY,contact TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE)")||
    !execute("CREATE VIEW IF NOT EXISTS shared.contacts AS SELECT n.number,p.name FROM people p JOIN numbers n ON p.id=n.contact")){
  m_error="Shared contact schema unavailable";return;
 }
 QFile::setPermissions(shared,QFileDevice::ReadOwner|QFileDevice::WriteOwner);
 if(!rows("SELECT name FROM sqlite_master WHERE type='table' AND name='contacts'").isEmpty()){
  if(!m_db.transaction()){m_error="Contact migration busy";return;}
  bool ok=true;
  for(const auto &value:rows("SELECT number,name FROM contacts")){
   const auto row=value.toMap();
   if(!rows("SELECT number FROM shared.numbers WHERE number=?",{row.value("number")}).isEmpty())continue;
   auto id=QUuid::createUuid().toString(QUuid::WithoutBraces);
   ok=execute("INSERT INTO shared.people(id,name) VALUES(?,?)",{id,row.value("name")})&&ok;
   ok=execute("INSERT INTO shared.numbers VALUES(?,?)",{row.value("number"),id})&&ok;
  }
  ok=execute("ALTER TABLE contacts RENAME TO contacts_legacy")&&ok;
  if(!ok||!m_db.commit()){m_db.rollback();m_error="Contact migration failed; original data retained";return;}
 }
 QFile::setPermissions(path,QFileDevice::ReadOwner|QFileDevice::WriteOwner);
 // Crash recovery must never turn a submitted operation back into a retryable draft.
 execute("UPDATE messages SET state='Uncertain',error='Application stopped during send. Verify with recipient before resending.' WHERE state IN ('Queued','Sending','Sent to modem')");
}
Repository::~Repository(){if(m_db.isValid())m_db.close();m_db=QSqlDatabase();QSqlDatabase::removeDatabase(m_connection);}
bool Repository::execute(const QString &sql,const QVariantList &args){QSqlQuery q(m_db);if(!q.prepare(sql))return false;for(const auto &a:args)q.addBindValue(a);return q.exec();}
QVariantList Repository::rows(const QString &sql,const QVariantList &args){QVariantList out;QSqlQuery q(m_db);if(!q.prepare(sql))return out;for(const auto &a:args)q.addBindValue(a);if(!q.exec())return out;while(q.next()){QVariantMap r;for(int i=0;i<q.record().count();++i)r[q.record().fieldName(i)]=q.value(i);out<<r;}return out;}
QVariantList Repository::conversations(const QString &search){return rows("SELECT m.number,COALESCE(c.name,m.number) AS name,m.body,m.timestamp,m.state,(SELECT COUNT(*) FROM messages u WHERE u.number=m.number AND u.unread=1) AS unread FROM messages m LEFT JOIN shared.contacts c ON c.number=m.number WHERE m.id=(SELECT id FROM messages x WHERE x.number=m.number ORDER BY timestamp DESC,id DESC LIMIT 1) AND (m.number LIKE ? OR c.name LIKE ? OR m.body LIKE ?) ORDER BY m.timestamp DESC LIMIT 200",{"%"+search+"%","%"+search+"%","%"+search+"%"});}
QVariantList Repository::messages(const QString &number,const QString &search,int offset){return rows("SELECT * FROM (SELECT * FROM messages WHERE number=? AND body LIKE ? ORDER BY timestamp DESC,id DESC LIMIT 200 OFFSET ?) ORDER BY timestamp,id",{number,"%"+search+"%",qMax(0,offset)});}
QString Repository::enqueue(const QString &number,const QString &text){
 if(!ready()||normalizedNumber(number).isEmpty()||text.trimmed().isEmpty())return {};
 auto e=estimateSms(text);if(e.segments>10)return {};
 auto id=QUuid::createUuid().toString(QUuid::WithoutBraces);
 if(!m_db.transaction())return {};
 const bool ok=execute("INSERT INTO messages(id,number,body,timestamp,direction,state,encoding,segments) VALUES(?,?,?,?,?,'Queued',?,?)",{id,normalizedNumber(number),text,QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs),"out",e.encoding,e.segments})
  &&execute("DELETE FROM drafts WHERE number=?",{number});
 if(!ok||!m_db.commit()){m_db.rollback();return {};}
 return id;
}
bool Repository::receive(const QVariantMap &m){if(m.value("key").toString().isEmpty()||!rows("SELECT 1 FROM deleted_transports WHERE transport=?",{m.value("key")}).isEmpty())return false;auto e=estimateSms(m.value("text").toString());return execute("INSERT OR IGNORE INTO messages(id,number,body,timestamp,direction,state,encoding,segments,transport,unread) VALUES(?,?,?,?,'in','Received',?,?,?,1)",{QUuid::createUuid().toString(QUuid::WithoutBraces),m.value("number"),m.value("text"),m.value("timestamp"),e.encoding,e.segments,m.value("key")})&&rows("SELECT changes() AS n").value(0).toMap().value("n").toInt()==1;}
bool Repository::update(const QString &id,const QString &state,const QString &key,const QString &error){return execute("UPDATE messages SET state=?,transport=COALESCE(NULLIF(?,''),transport),error=? WHERE id=? AND direction='out' AND state!='Delivered' AND NOT(state='Submitted to network' AND ?='Uncertain')",{state,key,error.isNull()?QStringLiteral(""):error,id,state});}
bool Repository::markRead(const QString &n){return execute("UPDATE messages SET unread=0,state='Read locally' WHERE number=? AND direction='in'",{n});}
int Repository::unread(){return rows("SELECT COUNT(*) AS n FROM messages WHERE unread=1").value(0).toMap().value("n").toInt();}
QString Repository::draft(const QString &n){return rows("SELECT body FROM drafts WHERE number=?",{n}).value(0).toMap().value("body").toString();}
bool Repository::saveDraft(const QString &n,const QString &text){return execute("INSERT INTO drafts(number,body) VALUES(?,?) ON CONFLICT(number) DO UPDATE SET body=excluded.body",{n.isNull()?QStringLiteral(""):n,text.isNull()?QStringLiteral(""):text});}
bool Repository::remove(const QString &id){
 if(!m_db.transaction())return false;
 auto existing=rows("SELECT transport,state FROM messages WHERE id=?",{id});
 if(existing.isEmpty()||QStringList{"Queued","Sending","Sent to modem"}.contains(existing.first().toMap().value("state").toString())){m_db.rollback();return false;}
 auto key=existing.first().toMap().value("transport").toString();
 bool ok=(key.isEmpty()||execute("INSERT OR IGNORE INTO deleted_transports VALUES(?)",{key}))&&execute("DELETE FROM messages WHERE id=?",{id});
 if(!ok||!m_db.commit()){m_db.rollback();return false;}return true;
}
bool Repository::backup(const QString &path){if(QFile::exists(path))return false;bool ok=execute("VACUUM INTO ?",{path});if(ok)QFile::setPermissions(path,QFileDevice::ReadOwner|QFileDevice::WriteOwner);return ok;}
QVariantList Repository::contacts(const QString &s){return rows("SELECT * FROM shared.contacts WHERE name LIKE ? OR number LIKE ? ORDER BY name LIMIT 200",{"%"+s+"%","%"+s+"%"});}
bool Repository::contact(const QString &n,const QString &name){
 auto number=normalizedNumber(n);if(number.isEmpty()||name.trimmed().isEmpty())return false;
 auto existing=rows("SELECT contact FROM shared.numbers WHERE number=?",{number});
 if(!existing.isEmpty())return execute("UPDATE shared.people SET name=? WHERE id=?",{name.trimmed(),existing.first().toMap().value("contact")});
 if(!m_db.transaction())return false;
 auto id=QUuid::createUuid().toString(QUuid::WithoutBraces);
 bool ok=execute("INSERT INTO shared.people(id,name) VALUES(?,?)",{id,name.trimmed()})&&execute("INSERT INTO shared.numbers VALUES(?,?)",{number,id});
 if(!ok||!m_db.commit()){m_db.rollback();return false;}return true;
}
bool Repository::removeContact(const QString &n){return execute("DELETE FROM shared.numbers WHERE number=?",{n});}

int Repository::messageCount(const QString &number,const QString &search){return rows("SELECT COUNT(*) AS n FROM messages WHERE number=? AND body LIKE ?",{number,"%"+search+"%"}).value(0).toMap().value("n").toInt();}
