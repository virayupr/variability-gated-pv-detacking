"""Comment 14: host-only benchmark of A1/A4 online causal gate and command logic.
Uses exact A1 feature implementation and command expressions from A4; no embedded claims.
Run alongside package_a_causal_nri.py and package_a4_corrected_controller.py.
"""
import argparse, json, platform, sys, time, tracemalloc
from pathlib import Path
import numpy as np
import pandas as pd
from package_a_causal_nri import compute_features
from package_a4_corrected_controller import simulate_segment


def command_step(gi, nri_lag1, prev_gc, current_angle, last_change_minute, minute, threshold=0.12, ramp_limit=400., theta_max=45., dwell_minutes=5):
    enabled = bool(np.isfinite(nri_lag1) and nri_lag1 >= threshold)
    target = min(gi, prev_gc + ramp_limit)
    desired = (min(float(np.degrees(np.arccos(np.clip(target / gi, 0, 1)))), theta_max)
               if enabled and gi > 50 and target < gi else 0.)
    can_change = last_change_minute is None or (minute - last_change_minute) >= dwell_minutes
    if can_change and abs(desired - current_angle) > 1e-8:
        current_angle = desired
        last_change_minute = minute
    gc = gi * np.cos(np.radians(current_angle))
    return current_angle, gc, last_change_minute, enabled


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--data',required=True); ap.add_argument('--out',default='comment14_host_benchmark.json'); ap.add_argument('--repeats',type=int,default=30)
    a=ap.parse_args()
    p=Path(a.data)
    features,_=compute_features(p,windows=(30,),threshold=0.12)
    # Timing excludes CSV ingestion, full-series feature preprocessing, and offline thermal/rainflow evaluation.
    # This is the scalar command step with precomputed lagged NRI, not end-to-end online timing.
    df=features.loc[features.irradiance.notna(),['irradiance','nri_30m_lag1']].copy()
    df=df.iloc[:min(len(df),10000)]
    if len(df)<100: raise ValueError('Not enough samples')
    G=df.irradiance.to_numpy(float); N=df.nri_30m_lag1.to_numpy(float)
    def replay(timed=False):
        prev=float(G[0]); angle=0.; last=None; lat=[]; angles=[]
        for i,(gi,nri) in enumerate(zip(G,N)):
            t0=time.perf_counter_ns() if timed else None
            angle,prev,last,_=command_step(float(gi),float(nri),prev,angle,last,i)
            if timed:lat.append(time.perf_counter_ns()-t0)
            angles.append(angle)
        return np.asarray(angles),np.asarray(lat,dtype=np.int64)
    # Exact-command parity on one contiguous segment against original A4 implementation.
    raw=pd.read_csv(p,sep=';',comment='#',parse_dates=['Timestamp_UTC']).sort_values('Timestamp_UTC').drop_duplicates('Timestamp_UTC').set_index('Timestamp_UTC')
    for col in ['T_module_C','T_ambient_C','Gtotpoa_Wm2','v_wind_ms']:raw[col]=pd.to_numeric(raw[col],errors='coerce')
    valid=raw[['T_module_C','T_ambient_C','Gtotpoa_Wm2','v_wind_ms']].notna().all(axis=1)
    chunks=(raw.index.to_series().diff()!=pd.Timedelta(minutes=1)).cumsum()
    candidates=[s for _,s in raw.loc[valid].groupby(chunks.loc[valid]) if len(s)>=100]
    parity=None
    if candidates:
        seg=candidates[0].iloc[:min(1000,len(candidates[0]))]
        f=features.nri_30m_lag1.reindex(seg.index).to_numpy(float)
        x=seg.Gtotpoa_Wm2.to_numpy(float)
        pa=float(x[0]);an=0.;lc=None;out=[]
        for i,(gi,ni) in enumerate(zip(x,f)):
            an,pa,lc,_=command_step(gi,ni,pa,an,lc,i);out.append(an)
        original=simulate_segment(seg,np.isfinite(f)&(f>=0.12),0.,np.zeros(3))
        err=float(np.max(np.abs(np.asarray(out)-original.angle.to_numpy(float))))
        parity={'samples':len(seg),'max_absolute_angle_difference_deg':err,'passed':err<1e-9}
        if not parity['passed']:raise AssertionError(f'Controller parity failed: {parity}')
    replay()
    latencies=[]
    tracemalloc.start();baseline,_=tracemalloc.get_traced_memory()
    for _ in range(a.repeats):
        _,ns=replay(timed=True);latencies.append(ns)
    current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    ms=np.concatenate(latencies)/1e6
    report={'scope':'Host-only scalar command decision, precomputed lagged NRI; excludes feature updates, IO, network, tracker motion, thermal model and rainflow',
            'hardware':{'platform':platform.platform(),'python':sys.version.split()[0],'processor':platform.processor(),'numpy':np.__version__,'pandas':pd.__version__},
            'data_file':p.name,'samples_per_replay':len(df),'repeats':a.repeats,'calls':len(ms),
            'latency_ms':{'median':float(np.median(ms)),'p95':float(np.percentile(ms,95)),'maximum':float(np.max(ms))},
            'tracemalloc_peak_increment_bytes':int(max(0,peak-baseline)),
            'control_period_ms':60000,'parity_check':parity,
            'limitations':['No embedded hardware benchmark','Python tracemalloc excludes native allocator and process RSS','NRI feature update excluded from scalar timing','No deadline or real-time operating-system guarantee']}
    Path(a.out).write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()