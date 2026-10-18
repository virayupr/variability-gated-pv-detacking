"""Package A4: corrected exploratory controller and segment-aware CSI2.
This is a sensitivity/implementation experiment, NOT a validated PV tracker or fatigue model.
Threshold 0.09 and windows 15/30/60 are illustrative, NOT tuned/independently selected.
Usage: python package_a4_corrected_controller.py --data path/to/2019_System_2B_1min.dat
"""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from package_a_causal_nri import compute_features

COLS=['T_module_C','T_ambient_C','Gtotpoa_Wm2','v_wind_ms']

def fit_thermal(raw, train_days):
    z=raw[COLS].copy(); z['next_T']=z.T_module_C.shift(-1)
    next_idx=pd.Series(z.index,index=z.index).shift(-1)
    valid=(next_idx-z.index==pd.Timedelta(minutes=1)) & z[COLS+['next_T']].notna().all(axis=1)
    valid &= pd.Series(z.index.date,index=z.index).isin(train_days)
    z=z.loc[valid]; dt=z.T_module_C-z.T_ambient_C
    X=np.column_stack([z.Gtotpoa_Wm2,dt,z.v_wind_ms*dt]); y=(z.next_T-z.T_module_C).to_numpy()
    if len(y)<500:raise ValueError('Insufficient contiguous training transitions')
    reg=LinearRegression().fit(X,y)
    return float(reg.intercept_),reg.coef_.astype(float),len(y)

def split_contiguous(raw, date):
    """One-minute, complete-sensor segments; never interpolate across gaps."""
    day=raw.loc[pd.Series(raw.index.date,index=raw.index).eq(date)].copy()
    good=day[COLS].notna().all(axis=1) & day.Gtotpoa_Wm2.between(0,1400)
    day=day.loc[good]
    if day.empty:return []
    boundaries=(day.index.to_series().diff()!=pd.Timedelta(minutes=1)).cumsum()
    return [v for _,v in day.groupby(boundaries) if len(v)>=2]

def simulate_segment(seg,eligibility,intercept,coef,ramp_limit=400.,theta_max=45.,dwell_minutes=5):
    """One coherent continuous segment. Control command at time t uses lagged gate and measured G(t).
    The 5-min dwell applies to all angle changes, including gate-off return.
    No sensor-based reinitialization inside the segment; both trajectories share first measured T.
    """
    n=len(seg); idx=seg.index
    G=seg.Gtotpoa_Wm2.to_numpy(float); Ta=seg.T_ambient_C.to_numpy(float)
    v=seg.v_wind_ms.to_numpy(float)
    enabled=np.asarray(eligibility,dtype=bool)
    Tb=np.empty(n);Tc=np.empty(n);Gb=np.empty(n);Gc=np.empty(n);angle=np.zeros(n)
    Tb[0]=Tc[0]=float(seg.T_module_C.iloc[0]);prev_gc=float(G[0]);current_angle=0.
    last_change=None
    for i in range(n):
        gi=float(G[i]);target=min(gi,prev_gc+ramp_limit)
        desired=(min(float(np.degrees(np.arccos(np.clip(target/gi,0,1)))),theta_max)
                 if enabled[i] and gi>50 and target<gi else 0.)
        can_change=last_change is None or (idx[i]-last_change)>=pd.Timedelta(minutes=dwell_minutes)
        if can_change and abs(desired-current_angle)>1e-8:
            current_angle=desired;last_change=idx[i]
        angle[i]=current_angle;Gb[i]=gi;Gc[i]=gi*np.cos(np.radians(current_angle))
        prev_gc=Gc[i]
        if i+1<n:
            Tb[i+1]=Tb[i]+intercept+coef[0]*Gb[i]+(coef[1]+coef[2]*v[i])*(Tb[i]-Ta[i])
            Tc[i+1]=Tc[i]+intercept+coef[0]*Gc[i]+(coef[1]+coef[2]*v[i])*(Tc[i]-Ta[i])
    return pd.DataFrame({'T_base':Tb,'T_control':Tc,'G_base':Gb,'G_control':Gc,
                         'angle':angle,'gate':enabled,'segment':0},index=idx)

def extract_closed_cycle_ranges(values):
    """ASTM-style four-point rainflow stack on reversals; returns full-cycle ranges only.
    Half cycles are excluded to match the closed-cycle CSI2 definition.
    This implementation must be cross-checked against the original rainflow package.
    """
    a=np.asarray(values,float)
    if len(a)<3:return []
    # compress flat runs and retain endpoints
    x=[float(a[0])]
    for z in a[1:]:
        if z!=x[-1]:x.append(float(z))
    if len(x)<3:return []
    tp=[x[0]]
    for i in range(1,len(x)-1):
        if (x[i]-x[i-1])*(x[i+1]-x[i])<0:tp.append(x[i])
    tp.append(x[-1]); stack=[];cycles=[]
    for v in tp:
        stack.append(v)
        while len(stack)>=3:
            x1=abs(stack[-2]-stack[-3]);x2=abs(stack[-1]-stack[-2])
            if x2<x1:break
            if len(stack)==3:
                stack.pop(0) # half-cycle, exclude
            else:
                cycles.append(x1)
                last=stack.pop();stack.pop();stack.pop();stack.append(last)
    return cycles

def severity(segment_values,median_window=5):
    a=pd.Series(segment_values).rolling(median_window,center=True,min_periods=1).median().to_numpy()
    return float(sum(x*x for x in extract_closed_cycle_ranges(a)))

def summarize(parts):
    if not parts:return None
    b=c=gb=gc=0.;detack=gate_minutes=changes=0;travel=0.;maxb=-np.inf;maxc=-np.inf
    for part in parts:
        b+=severity(part.T_base);c+=severity(part.T_control)
        gb+=float(part.G_base.sum());gc+=float(part.G_control.sum())
        ang=part.angle.to_numpy();detack+=int((ang>1e-8).sum());gate_minutes+=int(part.gate.sum())
        # Count first command as change from zero, including segment restart.
        dif=np.diff(np.r_[0.,ang]);changes+=int((abs(dif)>1e-8).sum());travel+=float(abs(dif).sum())
        maxb=max(maxb,float(part.T_base.max()));maxc=max(maxc,float(part.T_control.max()))
    return dict(CSI2_base=b,CSI2_control=c,CSI2_reduction_pct=100*(b-c)/b if b>0 else np.nan,
        irradiance_penalty_pct=100*(gb-gc)/gb if gb>0 else np.nan,
        intervention_minutes=detack,gate_eligible_minutes=gate_minutes,angle_changes=changes,
        angle_travel_deg=travel,Tmax_reduction_C=maxb-maxc,simulated_minutes=sum(len(p) for p in parts),
        contiguous_segments=len(parts))

def run(data,out='package_a4_outputs'):
    raw=pd.read_csv(data,sep=';',comment='#',parse_dates=['Timestamp_UTC']).sort_values('Timestamp_UTC').drop_duplicates('Timestamp_UTC').set_index('Timestamp_UTC')
    for col in COLS:raw[col]=pd.to_numeric(raw[col],errors='coerce')
    features,diag=compute_features(data)
    # Retain A2 21-day cohort for paired comparison; keep 14/7 split explicitly.
    candidate=sorted(pd.to_datetime(diag.date).dt.date)
    days=[]
    for d in candidate:
        x=raw.loc[pd.Series(raw.index.date,index=raw.index).eq(d) & raw.Gtotpoa_Wm2.gt(50)].dropna(subset=COLS)
        if len(x)>=300:days.append(d)
    train=days[:int(.7*len(days))];test=days[int(.7*len(days)):]
    intercept,coef,nfit=fit_thermal(raw,train)
    print('A4 days',len(days),'train',len(train),'test',len(test),'thermal fit transitions',nfit)
    print('Model coefficients:',intercept,coef)
    rows=[];diagnostics=[]
    for d in days:
        segments=split_contiguous(raw,d)
        if not segments:continue
        retro=bool(diag.loc[diag.date.eq(str(d)),'retrospective_gate_at_0p09'].iloc[0])
        for policy in ['baseline','always_available','retrospective_noncausal','causal_15m_illustrative_0p09','causal_30m_illustrative_0p09','causal_60m_illustrative_0p09']:
            parts=[]
            for seg in segments:
                if policy=='baseline':gate=np.zeros(len(seg),bool)
                elif policy=='always_available':gate=np.ones(len(seg),bool)
                elif policy=='retrospective_noncausal':gate=np.full(len(seg),retro,bool)
                else:
                    w=int(policy.split('_')[1][:-1]);gate=features[f'nri_{w}m_lag1'].reindex(seg.index).ge(.09).fillna(False).to_numpy(bool)
                parts.append(simulate_segment(seg,gate,intercept,coef))
            met=summarize(parts)
            if met:rows.append(dict(date=str(d),split='train' if d in train else 'test',policy=policy,**met))
        diagnostics.append(dict(date=str(d),segments=len(segments),valid_minutes=sum(len(s) for s in segments),
                                longest_segment=max(len(s) for s in segments)))
    result=pd.DataFrame(rows);out=Path(out);out.mkdir(exist_ok=True,parents=True)
    result.to_csv(out/'a4_daily_policy_metrics.csv',index=False)
    pd.DataFrame(diagnostics).to_csv(out/'a4_segment_diagnostics.csv',index=False)
    summary=result.groupby(['split','policy'],as_index=False).agg(days=('date','count'),
       mean_CSI2_reduction_pct=('CSI2_reduction_pct','mean'),mean_irradiance_penalty_pct=('irradiance_penalty_pct','mean'),
       mean_intervention_minutes=('intervention_minutes','mean'),mean_angle_changes=('angle_changes','mean'),
       mean_gate_eligible_minutes=('gate_eligible_minutes','mean'),mean_segments=('contiguous_segments','mean'))
    summary.to_csv(out/'a4_policy_summary.csv',index=False)
    print(summary.round(4).to_string(index=False))
    print('A4 is exploratory. 0.09 and windows NOT independently optimized. Physical tracker model unvalidated.')
    return result,summary

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--data',required=True);ap.add_argument('--out',default='package_a4_outputs')
    args=ap.parse_args();run(args.data,args.out)