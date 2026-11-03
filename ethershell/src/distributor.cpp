#include "distributor.h"
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QJsonDocument>
#include <QJsonArray>
#include <QUrlQuery>
#include <QFile>
#include <QFileInfo>
#include <QSaveFile>
#include <QDir>
#include <QStandardPaths>
#include <QDateTime>

static const QString base="https://autoupddate.etherneco.com";
QVariantList Distributor::emptyRows() const {
    QVariantList rows;for(const QString &name:QStringList{"EtherRemote","EtherMCP","EtherDeck","EtherAIR","EtherTrust","EtherFleet","EtherHardware","EtherPower","EtherAudio","EtherPhone","EtherLock","EtherLocation","EtherMAP"})
        rows<<QVariantMap{{"name",name},{"family",name.toLower()},{"variants",QVariantList()}};
    return rows;
}
Distributor::Distributor(QObject *parent):QObject(parent),m_network(this){
    m_rows=emptyRows();m_cache=QStandardPaths::writableLocation(QStandardPaths::CacheLocation)+"/ethershell/catalog.json";
    QFile cache(m_cache);if(cache.open(QIODevice::ReadOnly)){auto doc=QJsonDocument::fromJson(cache.readAll()).object();auto rows=doc["catalog"].toArray();if(doc["schema"].toInt()==1&&!rows.isEmpty()){
        // Preserve existing offline releases when a new product family is added.
        for(const auto &saved:rows){auto row=saved.toObject().toVariantMap();for(int i=0;i<m_rows.size();++i)if(m_rows[i].toMap().value("family")==row.value("family")){m_rows[i]=row;break;}}
        m_status="Zapisany katalog: "+doc["fetchedAt"].toString();}}
    refresh();
}
void Distributor::refresh(){
    if(busy()||m_blocked)return;m_next=emptyRows();m_pages=0;m_errors=0;m_status="Pobieranie katalogu AutoUpdate…";page(1);
}
void Distributor::get(const QString &path,std::function<void(const QJsonObject&)> done){
    if(m_blocked)return;
    QUrl url(base+path);QNetworkRequest request(url);
    request.setRawHeader("User-Agent","EtherShell-Autoupdate/1.0 (+https://etherneco.com)");
    request.setRawHeader("Accept","application/json, text/event-stream");request.setRawHeader("Content-Type","application/json");
    request.setAttribute(QNetworkRequest::RedirectPolicyAttribute,QNetworkRequest::SameOriginRedirectPolicy);
    request.setTransferTimeout(20000);++m_pending;emit changed();
    auto *reply=m_network.get(request);
    connect(reply,&QNetworkReply::finished,this,[this,reply,done]{
        const int code=reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();m_httpStatus=code;m_ray=QString::fromUtf8(reply->rawHeader("cf-ray"));
        auto doc=QJsonDocument::fromJson(reply->readAll());auto object=doc.object();
        if(reply->error()!=QNetworkReply::NoError||code!=200||!doc.isObject()){
            ++m_errors;
            if(object["error_code"].toInt()==1010){m_blocked=true;m_status="Cloudflare 1010 · wymagane odblokowanie API. Próby zatrzymane.";}
            else m_status=code?QString("AutoUpdate: HTTP %1 · cf-ray %2").arg(code).arg(m_ray):"AutoUpdate offline · pozostawiono zapisany katalog.";
        }else if(!m_blocked)done(object);
        --m_pending;reply->deleteLater();if(!m_pending)finish();emit changed();
    });
}
void Distributor::page(int number){
    get("/api/projects?page="+QString::number(number),[this,number](const QJsonObject &data){
        if(!data["data"].isArray()){++m_errors;m_status="Nieobsługiwany format katalogu AutoUpdate.";return;}
        ++m_pages;
        for(const auto &value:data["data"].toArray()){
            const auto project=value.toObject();const auto slug=project["slug"].toString();auto normalized=slug.toLower();normalized.remove('-');
            for(int index=0;index<m_next.size();++index){auto row=m_next[index].toMap();if(!normalized.startsWith(row["family"].toString()))continue;
                auto variants=row["variants"].toList();
                QVariantMap variant{{"slug",slug},{"name",project["name"].toString()},{"platform",project["platform"].toString()},{"version",QString()},{"format",QString()},{"architecture",QString()},{"sha256",QString()},{"signatureAvailable",false},{"reason","Oczekiwanie na metadane wydania"}};
                variants<<variant;row["variants"]=variants;m_next[index]=row;
                QUrlQuery query;query.addQueryItem("project",slug);query.addQueryItem("channel","Stable");
                get("/api/releases/check?"+query.toString(QUrl::FullyEncoded),[this,index,slug](const QJsonObject &release){
                    auto row=m_next[index].toMap();auto variants=row["variants"].toList();
                    for(int i=0;i<variants.size();++i){auto v=variants[i].toMap();if(v["slug"]!=slug)continue;
                        const auto artifact=release["artifact"].toObject();const auto metadata=release["metadata"].toObject();
                        const auto arch=metadata["arch"].toString(metadata["architecture"].toString());
                        v["version"]=release["latest"].toVariant().toString();v["platform"]=artifact["platform"].toString(v["platform"].toString());v["format"]=artifact["extension"].toString();v["architecture"]=arch;
                        v["sha256"]=release["sha256"].toString();v["signatureAvailable"]=!release["signature"].isNull()&&!release["signature"].isUndefined();
                        v["reason"]=v["platform"]!="linux"?"Wydanie nie jest przeznaczone dla natywnego Debiana":arch!="arm64"&&arch!="aarch64"?"Brak potwierdzonej architektury Linux ARM64":"Pakiet wymaga weryfikacji formatu, zależności i podpisu";
                        variants[i]=v;
                    }
                    row["variants"]=variants;m_next[index]=row;
                });
                break;
            }
        }
        const int last=data["last_page"].toInt(number);
        if(number<last && number<100)page(number+1);
    });
}
void Distributor::finish(){
    if(m_pages&&!m_blocked){m_rows=m_next;if(!m_errors){m_status="Połączono z AutoUpdate · katalog Stable · "+QDateTime::currentDateTime().toString("HH:mm");QDir().mkpath(QFileInfo(m_cache).absolutePath());QSaveFile file(m_cache);if(file.open(QIODevice::WriteOnly)){file.write(QJsonDocument(QJsonObject{{"schema",1},{"fetchedAt",QDateTime::currentDateTimeUtc().toString(Qt::ISODate)},{"catalog",QJsonArray::fromVariantList(m_rows)}}).toJson());file.commit();}}}
    emit refreshed(m_pages>0&&m_errors==0&&!m_blocked);
}
void Distributor::diagnose(const QString &path){QSaveFile file(path);if(file.open(QIODevice::WriteOnly)){file.write(QJsonDocument::fromVariant(QVariantMap{{"status",m_status},{"httpStatus",m_httpStatus},{"cf-ray",m_ray},{"pages",m_pages},{"errors",m_errors},{"catalog",m_rows}}).toJson());file.commit();}}
