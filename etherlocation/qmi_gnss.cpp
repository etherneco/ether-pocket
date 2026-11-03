// Rootless, session-owned libqmi LOC transport. No assistance or firmware writes.
#include <libqmi-glib.h>
#include <libqrtr-glib.h>
#include <glib-unix.h>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QCoreApplication>
#include <cstdio>
#include <cmath>
#include <algorithm>
#include <sys/prctl.h>

static GMainLoop *loop=nullptr;
static QrtrBus *bus=nullptr;static QmiDevice *device=nullptr;static QmiClient *client=nullptr;
static bool stopping=false,started=false,redacted=true,pending=false,diagnostic=false;static guint interval=10000;
static gint64 startTime=0;static constexpr guint8 session=208;
static void send(QJsonObject object){auto text=QJsonDocument(object).toJson(QJsonDocument::Compact);fwrite(text.constData(),1,text.size(),stdout);fputc('\n',stdout);fflush(stdout);}
static void status(const char *state,const char *error=""){send({{"event","status"},{"state",state},{"error",error}});}
static void closeDevice();static gboolean stop(gpointer);
static void failure(GError *error){pending=false;status("Error",error?error->message:"GNSS operation failed");if(error)g_error_free(error);stop(nullptr);}
static void closed(GObject *source,GAsyncResult *result,gpointer){GError *error=nullptr;qmi_device_close_finish(QMI_DEVICE(source),result,&error);if(error)g_error_free(error);g_clear_object(&device);g_clear_object(&bus);send({{"event","released"}});g_main_loop_quit(loop);}
static void closeDevice(){if(device)qmi_device_close_async(device,5,nullptr,closed,nullptr);else {send({{"event","released"}});g_main_loop_quit(loop);}}
static void released(GObject *source,GAsyncResult *result,gpointer){GError *error=nullptr;qmi_device_release_client_finish(QMI_DEVICE(source),result,&error);if(error)g_error_free(error);g_clear_object(&client);closeDevice();}
static void releaseClient(){if(client)qmi_device_release_client(device,client,QMI_DEVICE_RELEASE_CLIENT_FLAGS_RELEASE_CID,5,nullptr,released,nullptr);else closeDevice();}
static void stopped(GObject *source,GAsyncResult *result,gpointer){GError *error=nullptr;auto output=qmi_client_loc_stop_finish(QMI_CLIENT_LOC(source),result,&error);bool ok=output&&qmi_message_loc_stop_output_get_result(output,&error);if(output)qmi_message_loc_stop_output_unref(output);send({{"event","stop"},{"acknowledged",ok}});if(error)g_error_free(error);releaseClient();}
static void beginStop(){
 if(client&&started){auto input=qmi_message_loc_stop_input_new();qmi_message_loc_stop_input_set_session_id(input,session,nullptr);qmi_client_loc_stop(QMI_CLIENT_LOC(client),input,10,nullptr,stopped,nullptr);qmi_message_loc_stop_input_unref(input);}
 else releaseClient();
}
static gboolean stop(gpointer){if(stopping)return G_SOURCE_REMOVE;stopping=true;if(!pending)beginStop();return G_SOURCE_REMOVE;}
static void position(QmiClientLoc*,QmiIndicationLocPositionReportOutput *output,gpointer){
 if(stopping)return;QmiLocSessionStatus state;guint8 id=0;
 if(diagnostic){
  gdouble coordinate;gfloat uncertainty;guint64 utc;QmiLocTechnologyUsed tech;QmiLocSessionStatus reportState;guint8 reportSession;
  const bool stateKnown=qmi_indication_loc_position_report_output_get_session_status(output,&reportState,nullptr);
  const bool sessionKnown=qmi_indication_loc_position_report_output_get_session_id(output,&reportSession,nullptr);
  send({{"event","report-validity"},{"ourSession",sessionKnown&&reportSession==session},{"sessionReported",sessionKnown},{"status",stateKnown?qmi_loc_session_status_get_string(reportState):"missing"},
   {"latitudeReported",bool(qmi_indication_loc_position_report_output_get_latitude(output,&coordinate,nullptr))},{"longitudeReported",bool(qmi_indication_loc_position_report_output_get_longitude(output,&coordinate,nullptr))},
   {"circularAccuracyReported",bool(qmi_indication_loc_position_report_output_get_horizontal_uncertainty_circular(output,&uncertainty,nullptr))},{"ellipseAccuracyReported",bool(qmi_indication_loc_position_report_output_get_horizontal_uncertainty_elliptical_major(output,&uncertainty,nullptr))},
   {"utcReported",bool(qmi_indication_loc_position_report_output_get_utc_timestamp(output,&utc,nullptr))},{"technologyReported",bool(qmi_indication_loc_position_report_output_get_technology_used(output,&tech,nullptr))}});
 }
 if(!qmi_indication_loc_position_report_output_get_session_id(output,&id,nullptr)||id!=session||!qmi_indication_loc_position_report_output_get_session_status(output,&state,nullptr))return;
 if(state!=QMI_LOC_SESSION_STATUS_SUCCESS){if(state==QMI_LOC_SESSION_STATUS_IN_PROGRESS)status("Searching");else status("Fix lost",qmi_loc_session_status_get_string(state));return;}
 QmiLocTechnologyUsed technology;
 if(!qmi_indication_loc_position_report_output_get_technology_used(output,&technology,nullptr)||!(technology&QMI_LOC_TECHNOLOGY_USED_SATELLITE)||(technology&QMI_LOC_TECHNOLOGY_USED_INJECTED_POSITION))return;
 gdouble lat=0,lon=0;gfloat accuracy=0;guint64 timestamp=0;
 bool accuracyReported=qmi_indication_loc_position_report_output_get_horizontal_uncertainty_circular(output,&accuracy,nullptr);
 if(!accuracyReported)accuracyReported=qmi_indication_loc_position_report_output_get_horizontal_uncertainty_elliptical_major(output,&accuracy,nullptr);
 if(!qmi_indication_loc_position_report_output_get_latitude(output,&lat,nullptr)||!qmi_indication_loc_position_report_output_get_longitude(output,&lon,nullptr)||!accuracyReported||!qmi_indication_loc_position_report_output_get_utc_timestamp(output,&timestamp,nullptr))return;
 double now=g_get_real_time()/1e6;
 if(!std::isfinite(lat)||!std::isfinite(lon)||!std::isfinite(accuracy)||std::abs(lat)>90||std::abs(lon)>180||accuracy<=0||timestamp/1000.>now+5||now-timestamp/1000.>30)return;
 QJsonObject fix{{"latitude",lat},{"longitude",lon},{"accuracy",accuracy},{"timestamp",timestamp/1000.},{"provider","qualcomm-loc"},{"kind","live"},{"fixType","GNSS"}};
 GArray *used=nullptr;if(qmi_indication_loc_position_report_output_get_satellites_used(output,&used,nullptr)&&used)fix["satellitesUsed"]=int(used->len);
 gfloat value=0;
 if(qmi_indication_loc_position_report_output_get_altitude_from_sealevel(output,&value,nullptr))fix["altitude"]=value;
 if(qmi_indication_loc_position_report_output_get_vertical_uncertainty(output,&value,nullptr))fix["verticalAccuracy"]=value;
 if(qmi_indication_loc_position_report_output_get_horizontal_speed(output,&value,nullptr))fix["speed"]=value;
 if(qmi_indication_loc_position_report_output_get_heading(output,&value,nullptr))fix["heading"]=value;
 auto elapsed=(g_get_monotonic_time()-startTime)/1e6;
 if(redacted)send({{"event","fix"},{"accuracy",accuracy},{"timestamp",timestamp/1000.},{"elapsedSeconds",elapsed},{"coordinates","redacted"}});
 else send({{"event","position"},{"position",fix},{"elapsedSeconds",elapsed}});
}
static void satellites(QmiClientLoc*,QmiIndicationLocGnssSvInfoOutput *output,gpointer){
 if(stopping)return;GArray *rows=nullptr;if(!qmi_indication_loc_gnss_sv_info_output_get_list(output,&rows,nullptr))return;QJsonArray items;
 for(guint i=0;i<std::min(rows->len,256u);i++){
  const auto &s=g_array_index(rows,QmiIndicationLocGnssSvInfoOutputListElement,i);QJsonObject row;
  if(s.valid_information&QMI_LOC_SATELLITE_VALID_INFORMATION_SYSTEM){auto name=qmi_loc_system_get_string(s.system);if(name)row["constellation"]=name;}
  if(s.valid_information&QMI_LOC_SATELLITE_VALID_INFORMATION_GNSS_SATELLITE_ID)row["id"]=s.gnss_satellite_id;
  if(s.valid_information&QMI_LOC_SATELLITE_VALID_INFORMATION_PROCESS_STATUS){auto name=qmi_loc_satellite_status_get_string(s.satellite_status);if(name)row["status"]=name;}
  if((s.valid_information&QMI_LOC_SATELLITE_VALID_INFORMATION_SIGNAL_TO_NOISE_RATIO)&&std::isfinite(s.signal_to_noise_ratio_bhz))row["signal"]=s.signal_to_noise_ratio_bhz;
  if((s.valid_information&QMI_LOC_SATELLITE_VALID_INFORMATION_ELEVATION)&&std::isfinite(s.elevation_degrees))row["elevation"]=s.elevation_degrees;
  if((s.valid_information&QMI_LOC_SATELLITE_VALID_INFORMATION_AZIMUTH)&&std::isfinite(s.azimuth_degrees))row["azimuth"]=s.azimuth_degrees;
  items.append(row);
 }send({{"event","satellites"},{"satellites",items}});
}
static void startReady(GObject *source,GAsyncResult *result,gpointer){pending=false;GError *error=nullptr;auto output=qmi_client_loc_start_finish(QMI_CLIENT_LOC(source),result,&error);bool ok=output&&qmi_message_loc_start_output_get_result(output,&error);if(output)qmi_message_loc_start_output_unref(output);if(!ok){if(stopping)stopping=false;failure(error);return;}started=true;if(stopping)beginStop();else status("Searching");}
static void registered(GObject *source,GAsyncResult *result,gpointer){
 pending=false;GError *error=nullptr;auto output=qmi_client_loc_register_events_finish(QMI_CLIENT_LOC(source),result,&error);bool ok=output&&qmi_message_loc_register_events_output_get_result(output,&error);if(output)qmi_message_loc_register_events_output_unref(output);if(!ok){if(stopping)stopping=false;failure(error);return;}if(stopping){beginStop();return;}
 auto input=qmi_message_loc_start_input_new();qmi_message_loc_start_input_set_session_id(input,session,nullptr);qmi_message_loc_start_input_set_fix_recurrence_type(input,QMI_LOC_FIX_RECURRENCE_TYPE_REQUEST_PERIODIC_FIXES,nullptr);qmi_message_loc_start_input_set_intermediate_report_state(input,QMI_LOC_INTERMEDIATE_REPORT_STATE_ENABLE,nullptr);qmi_message_loc_start_input_set_minimum_interval_between_position_reports(input,interval,nullptr);
 pending=true;qmi_client_loc_start(QMI_CLIENT_LOC(source),input,10,nullptr,startReady,nullptr);qmi_message_loc_start_input_unref(input);
}
static void allocated(GObject *source,GAsyncResult *result,gpointer){
 pending=false;GError *error=nullptr;client=qmi_device_allocate_client_finish(QMI_DEVICE(source),result,&error);if(!client){if(stopping)stopping=false;failure(error);return;}if(stopping){beginStop();return;}
 g_signal_connect(client,"position-report",G_CALLBACK(position),nullptr);g_signal_connect(client,"gnss-sv-info",G_CALLBACK(satellites),nullptr);
 auto input=qmi_message_loc_register_events_input_new();qmi_message_loc_register_events_input_set_event_registration_mask(input,static_cast<QmiLocEventRegistrationFlag>(QMI_LOC_EVENT_REGISTRATION_FLAG_POSITION_REPORT|QMI_LOC_EVENT_REGISTRATION_FLAG_GNSS_SATELLITE_INFO),nullptr);pending=true;qmi_client_loc_register_events(QMI_CLIENT_LOC(client),input,10,nullptr,registered,nullptr);qmi_message_loc_register_events_input_unref(input);
}
static void opened(GObject *source,GAsyncResult *result,gpointer){pending=false;GError *error=nullptr;if(!qmi_device_open_finish(QMI_DEVICE(source),result,&error)){if(stopping)stopping=false;failure(error);return;}if(stopping){beginStop();return;}pending=true;qmi_device_allocate_client(device,QMI_SERVICE_LOC,QMI_CID_NONE,10,nullptr,allocated,nullptr);}
static void deviceReady(GObject*,GAsyncResult *result,gpointer){pending=false;GError *error=nullptr;device=qmi_device_new_from_node_finish(result,&error);if(!device){if(stopping)stopping=false;failure(error);return;}if(stopping){beginStop();return;}pending=true;qmi_device_open(device,QMI_DEVICE_OPEN_FLAGS_NONE,10,nullptr,opened,nullptr);}
static void busReady(GObject*,GAsyncResult *result,gpointer){pending=false;GError *error=nullptr;bus=qrtr_bus_new_finish(result,&error);if(!bus){if(stopping)stopping=false;failure(error);return;}if(stopping){beginStop();return;}auto node=qrtr_bus_get_node(bus,0);if(!node){status("Unsupported","Qualcomm QRTR node 0 not found");stop(nullptr);return;}pending=true;qmi_device_new_from_node(node,nullptr,deviceReady,nullptr);g_object_unref(node);}
int main(int argc,char **argv){
 QCoreApplication app(argc,argv);auto args=app.arguments();redacted=!args.contains("--private-json");diagnostic=args.contains("--diagnostic");
 const auto i=args.indexOf("--interval");if(i>=0&&i+1<args.size())interval=std::clamp(args[i+1].toUInt(),5u,300u)*1000;
 loop=g_main_loop_new(nullptr,FALSE);startTime=g_get_monotonic_time();status("Initialising");g_unix_signal_add(SIGTERM,stop,nullptr);g_unix_signal_add(SIGINT,stop,nullptr);signal(SIGPIPE,SIG_IGN);
 // Parent death requests a clean stop; normal service shutdown also sends SIGTERM.
 prctl(PR_SET_PDEATHSIG,SIGTERM);g_timeout_add_seconds(3600,stop,nullptr);
 const auto t=args.indexOf("--test-seconds");if(t>=0&&t+1<args.size())g_timeout_add_seconds(std::clamp(args[t+1].toUInt(),10u,300u),stop,nullptr);
 pending=true;qrtr_bus_new(1000,nullptr,busReady,nullptr);g_main_loop_run(loop);g_main_loop_unref(loop);return 0;
}
