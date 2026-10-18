"""Package A5: training-only selection, frozen external transfer diagnostics.
Exploratory sensitivity model only; no validated tracker optics, fatigue, or energy.
"""
import argparse, json, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from package_a_causal_nri import compute_features
from package_a4_corrected_controller import COLS, fit_thermal, split_contiguous, simulate_segment, summarize

WINDOWS=(15,30,60)
THRESHOLDS=(0.03,0.06,0.09,0.12,0.15,0.20)

def load(path):
    raw=pd.read_csv(path,sep=';',comment='#',parse_dates=['Timestamp_UTC']).sort_values('Timestamp_UTC').drop_duplicates('Timestamp_UTC').set_index('Timestamp_UTC')
    for c in COLS: raw[c]=pd.to_numeric(raw[c],errors='coerce')
    return raw

def eligible_days(raw,diag):
    days=[]
    for d in sorted(pd.to_datetime(diag.date).dt.date):
        day=raw.loc[pd.Series(raw.index.date,index=raw.index).eq(d)&raw.Gtotpoa_Wm2.gt(50)].dropna(subset=COLS)
        if len(day)>=300:days.append(d)
    return days

def evaluate(raw,features,days,intercept,coef,policy,split):
    rows=[]
    for d in days:
        parts=[]
        for seg in split_contiguous(raw,d):
            if policy=='baseline': gate=np.zeros(len(seg),bool)
            elif policy=='always_available':gate=np.ones(len(seg),bool)
            else:
                w,thr=policy
                gate=features[f'nri_{w}m_lag1'].reindex(seg.index).ge(thr).fillna(False).to_numpy(bool)
            parts.append(simulate_segment(seg,gate,intercept,coef))
        m=summarize(parts)
        if m: rows.append({'date':str(d),'split':split,'policy':str(policy),'window':policy[0] if isinstance(policy,tuple) else None,'threshold':policy[1] if isinstance(policy,tuple) else None,**m})
    return rows

def mean_summary(df):
    return df.groupby(['policy','window','threshold'],dropna=False,as_index=False).agg(days=('date','count'),mean_CSI2_reduction_pct=('CSI2_reduction_pct','mean'),mean_irradiance_penalty_pct=('irradiance_penalty_pct','mean'),mean_intervention_minutes=('intervention_minutes','mean'),mean_angle_changes=('angle_changes','mean'))

def run(data,external,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    raw=load(data); feat,diag=compute_features(data,windows=WINDOWS)
    days=eligible_days(raw,diag);cut=int(.7*len(days));train=days[:cut];old_test=days[cut:]
    if len(train)<5:raise ValueError('Insufficient training days')
    intercept,coef,nfit=fit_thermal(raw,train)
    grid=[(w,t) for w in WINDOWS for t in THRESHOLDS]
    train_rows=[]
    for p in ['baseline','always_available',*grid]:train_rows+=evaluate(raw,feat,train,intercept,coef,p,'train')
    train_df=pd.DataFrame(train_rows);summ=mean_summary(train_df)
    reference=summ.loc[summ.policy.eq('always_available')].iloc[0]
    # Frozen prespecified feasibility: mean reduction strictly positive, not worse than
    # always available, and penalty no greater than always available.
    candidate=summ[summ.window.notna()].copy()
    candidate['feasible']=(candidate.mean_CSI2_reduction_pct>0)&(candidate.mean_CSI2_reduction_pct>=reference.mean_CSI2_reduction_pct)&(candidate.mean_irradiance_penalty_pct<=reference.mean_irradiance_penalty_pct)
    viable=candidate[candidate.feasible].sort_values(['mean_CSI2_reduction_pct','mean_irradiance_penalty_pct','window','threshold'],ascending=[False,True,True,True])
    selected=(int(viable.iloc[0].window),float(viable.iloc[0].threshold)) if len(viable) else 'baseline'
    # Previously inspected 2019 days are reported separately, never used for selection.
    old_rows=[]
    for p in ['baseline','always_available',selected] if isinstance(selected,tuple) else ['baseline','always_available']:
        old_rows+=evaluate(raw,feat,old_test,intercept,coef,p,'previously_inspected_2019')
    external_rows=[];external_info=[]
    for file in external:
        eraw=load(file);ef,ed=compute_features(file,windows=WINDOWS)
        edays=eligible_days(eraw,ed)
        label=Path(file).stem
        external_info.append({'dataset':label,'eligible_days':len(edays),'first_date':str(edays[0]) if edays else None,'last_date':str(edays[-1]) if edays else None})
        for p in ['baseline','always_available',selected] if isinstance(selected,tuple) else ['baseline','always_available']:
            rows=evaluate(eraw,ef,edays,intercept,coef,p,label)
            for row in rows:row['dataset']=label
            external_rows+=rows
    train_df.to_csv(out/'a5_training_daily.csv',index=False)
    candidate.to_csv(out/'a5_training_candidate_grid.csv',index=False)
    pd.DataFrame(old_rows).to_csv(out/'a5_previously_inspected_2019.csv',index=False)
    pd.DataFrame(external_rows).to_csv(out/'a5_external_daily.csv',index=False)
    ext_summary=pd.DataFrame(external_rows)
    if not ext_summary.empty:ext_summary.groupby(['dataset','policy'],as_index=False).agg(days=('date','count'),mean_CSI2_reduction_pct=('CSI2_reduction_pct','mean'),mean_irradiance_penalty_pct=('irradiance_penalty_pct','mean'),mean_intervention_minutes=('intervention_minutes','mean')).to_csv(out/'a5_external_summary.csv',index=False)
    else:pd.DataFrame().to_csv(out/'a5_external_summary.csv',index=False)
    provenance={'original_2019':str(data),'original_sha256':hashlib.sha256(Path(data).read_bytes()).hexdigest(),'training_days':[str(d) for d in train],'previously_inspected_days':[str(d) for d in old_test],'fit_transitions':nfit,'intercept':intercept,'coefficients':coef.tolist(),'thresholds':THRESHOLDS,'windows':WINDOWS,'selection_rule':'mean training CSI2 reduction >0, >= always_available; mean irradiance penalty <= always_available; maximize CSI2 reduction, tie break penalty/window/threshold; otherwise baseline','selected_policy':selected,'external_datasets':external_info,'warning':'2018 transfer is out-of-year/system model transfer, not validated counterfactual; 2019 seven days previously inspected; selection not nested CV; no real energy/fatigue/lifetime claims'}
    (out/'a5_manifest.json').write_text(json.dumps(provenance,indent=2,default=str))
    print('A5 TRAIN',len(train),'PREVIOUSLY INSPECTED',len(old_test),'FIT',nfit)
    print('Reference training CSI2 reduction',round(float(reference.mean_CSI2_reduction_pct),6),'penalty',round(float(reference.mean_irradiance_penalty_pct),6))
    print('Feasible candidates',len(viable),'of',len(grid),'SELECTED',selected)
    print('External cohorts:',external_info)
    print('Results saved:',out)
    print('CAUTION: computational exploratory model only; no independent validation of optical or fatigue physics.')
    return provenance

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--data',required=True);ap.add_argument('--external',nargs='*',default=[]);ap.add_argument('--out',default='package_a5_outputs');a=ap.parse_args();run(a.data,a.external,a.out)