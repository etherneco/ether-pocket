"""Recording limits on validated, timestamped EtherPower telemetry only."""
import datetime
import math

def recording_guard(state, now=None):
    try:
        if not isinstance(state,dict) or state.get('ready') is not True:return 'Power telemetry unavailable'
        stamp=datetime.datetime.fromisoformat(state['timestamp'])
        if stamp.tzinfo is None:return 'Power telemetry unavailable'
        now=now or datetime.datetime.now(datetime.timezone.utc)
        age=(now-stamp).total_seconds()
        if not -30<=age<=180:return 'Power telemetry stale'
        for key,low,high in [('capacity',0,100),('cpuTemperatureC',-30,150),('batteryTemperatureC',-30,100)]:
            value=state.get(key)
            if type(value) not in (float,int) or not math.isfinite(value) or not low<=value<=high:return 'Power telemetry unavailable'
        if state['capacity']<=5:return 'Battery recording limit'
        if state['cpuTemperatureC']>=85 or state['batteryTemperatureC']>=45:return 'Thermal recording limit'
        gpu=state.get('gpuTemperatureC')
        if gpu is not None:
            if type(gpu) not in (float,int) or not math.isfinite(gpu) or not -30<=gpu<=150:return 'Power telemetry unavailable'
            if gpu>=85:return 'Thermal recording limit'
        return ''
    except (KeyError,ValueError,TypeError,OverflowError):return 'Power telemetry unavailable'
