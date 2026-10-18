"""A4 real-trajectory rainflow audit. Reference rainflow required; no scientific result is assumed."""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd
import rainflow
from package_a_causal_nri import compute_features
from package_a4_corrected_controller import (COLS,fit_thermal,split_contiguous,simulate_segment,
                                             extract_closed_cycle_ranges)

def scores(a):
    smoothed=pd.Series(np.asarray(a,float)).rolling(5,center=True,min_periods=1).median().to_numpy()
    ref=sorted(float(r)**2 for r,mean,count,*_ in rainflow.extract_cycles(smoothed) if np.isclose(count,1.0))
    custom=sorted(float(r)**2 for r in extract_closed_cycle_ranges(smoothed))
    ok=len(ref)==len(custom) and np.allclose(ref,custom,rtol=1e-10,atol=1e-10)
    return len(ref),len(custom),float(sum(ref)),float(sum(custom)),bool(ok)

def run(data,output='a4_real_trajectory_verification',existing=None):
    raw=pd.read_csv(data,sep=';',comment='#',parse_dates=['Timestamp_UTC']).sort_values('Timestamp_UTC').drop_duplicates('Timestamp_UTC').set_index('Timestamp_UTC')
    for col in COLS: raw[col]=pd.to_numeric(raw[col],errors='coerce')
    features,diag=compute_features(data)
    candidate=sorted(pd.to_datetime(diag.date).dt.date)
    days=[]
    for d in candidate:
        x=raw.loc[pd.Series(raw.index.date,index=raw.index).eq(d) & raw.Gtotpoa_Wm2.gt(50)].dropna(subset=COLS)
        if len(x)>=300:days.append(d)
    train=days[:int(.7*len(days))]
    intercept,coef,nfit=fit_thermal(raw,train)
    print('Cohort:',len(days),'train:',len(train),'test:',len(days)-len(train),'transitions:',nfit)
    policies=['baseline','always_available','retrospective_noncausal','causal_15m_illustrative_0p09','causal_30m_illustrative_0p09','causal_60m_illustrative_0p09']
    rows=[]
    for d in days:
        segments=split_contiguous(raw,d)
        retro=bool(diag.loc[diag.date.eq(str(d)),'retrospective_gate_at_0p09'].iloc[0])
        for policy in policies:
            for j,seg in enumerate(segments):
                if policy=='baseline': gate=np.zeros(len(seg),bool)
                elif policy=='always_available':gate=np.ones(len(seg),bool)
                elif policy=='retrospective_noncausal':gate=np.full(len(seg),retro,bool)
                else:
                    w=int(policy.split('_')[1][:-1]);gate=features[f'nri_{w}m_lag1'].reindex(seg.index).ge(.09).fillna(False).to_numpy(bool)
                simulated=simulate_segment(seg,gate,intercept,coef)
                for trajectory,col in [('baseline','T_base'),('controlled','T_control')]:
                    nr,nc,sr,sc,match=scores(simulated[col].to_numpy())
                    rows.append(dict(date=str(d),split='train' if d in train else 'test',policy=policy,
                        segment=j,trajectory=trajectory,minutes=len(seg),reference_full_cycles=nr,
                        custom_full_cycles=nc,reference_CSI2=sr,custom_CSI2=sc,
                        abs_CSI2_error=abs(sr-sc),match=match))
    detail=pd.DataFrame(rows)
    agg=detail.groupby(['date','split','policy','trajectory'],as_index=False).agg(
        reference_CSI2=('reference_CSI2','sum'),custom_CSI2=('custom_CSI2','sum'),
        reference_full_cycles=('reference_full_cycles','sum'),custom_full_cycles=('custom_full_cycles','sum'),
        all_segments_match=('match','all'))
    pivot=agg.pivot(index=['date','split','policy'],columns='trajectory',values='reference_CSI2').reset_index()
    pivot.columns=['date','split','policy','CSI2_base_reference','CSI2_control_reference']
    pivot['CSI2_reduction_pct_reference']=np.where(pivot.CSI2_base_reference>0,
        100*(pivot.CSI2_base_reference-pivot.CSI2_control_reference)/pivot.CSI2_base_reference,np.nan)
    if existing:
        old=pd.read_csv(existing)
        pivot=pivot.merge(old[['date','policy','CSI2_base','CSI2_control','CSI2_reduction_pct']],on=['date','policy'],how='left',validate='one_to_one')
        for a,b in [('CSI2_base_reference','CSI2_base'),('CSI2_control_reference','CSI2_control'),('CSI2_reduction_pct_reference','CSI2_reduction_pct')]:
            pivot[f'{a}_abs_diff_vs_A4']=abs(pivot[a]-pivot[b])
    out=Path(output);out.mkdir(exist_ok=True,parents=True)
    detail.to_csv(out/'a4_real_rainflow_segment_checks.csv',index=False)
    pivot.to_csv(out/'a4_real_rainflow_daily_comparison.csv',index=False)
    summary=dict(cohort_days=len(days),policy_day_rows=len(pivot),trajectory_segment_checks=len(detail),
        mismatched_trajectories=int((~detail.match).sum()),max_abs_segment_CSI2_error=float(detail.abs_CSI2_error.max()))
    if existing:
        summary['max_abs_daily_CSI2_diff_vs_A4']=float(max(pivot.CSI2_base_reference_abs_diff_vs_A4.max(),pivot.CSI2_control_reference_abs_diff_vs_A4.max()))
        summary['max_abs_daily_reduction_pct_diff_vs_A4']=float(pivot.CSI2_reduction_pct_reference_abs_diff_vs_A4.max())
    print('RESULT:',summary)
    if summary['mismatched_trajectories']:
        print('FAIL: reference and custom rainflow disagree on real simulated trajectories. Stop before A5.')
    else:
        print('PASS: reference and custom rainflow agree on every simulated segment; review A4 daily comparison too.')
    return detail,pivot,summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',required=True);p.add_argument('--existing');p.add_argument('--out',default='a4_real_trajectory_verification');a=p.parse_args()
    run(a.data,a.out,a.existing)