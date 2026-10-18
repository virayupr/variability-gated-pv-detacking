"""A7 frozen-policy external thermal transfer and CSI2 robustness audit.
No retuning. Full-cycle and half-cycle conventions are computational proxies, not calibrated fatigue.
"""
import argparse, json, zipfile, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from package_a5_training_selection import load, eligible_days
from package_a_causal_nri import compute_features
from package_a4_corrected_controller import COLS, split_contiguous, simulate_segment, severity, extract_closed_cycle_ranges

def rainflow_weighted(a, half=False):
    # Exact reference-compatible half/full-cycle counting through reversal stack.
    x=np.asarray(a,float)
    if len(x)<3:return 0.
    z=[float(x[0])]
    for v in x[1:]:
        if v!=z[-1]:z.append(float(v))
    if len(z)<3:return 0.
    rev=[z[0]]+[z[i] for i in range(1,len(z)-1) if (z[i]-z[i-1])*(z[i+1]-z[i])<0]+[z[-1]]
    stack=[];score=0.
    for v in rev:
        stack.append(v)
        while len(stack)>=3:
            a1=abs(stack[-2]-stack[-3]);a2=abs(stack[-1]-stack[-2])
            if a2<a1:break
            if len(stack)==3:
                if half:score+=0.5*a1*a1
                stack.pop(0)
            else:
                score+=a1*a1
                last=stack.pop();stack.pop();stack.pop();stack.append(last)
    if half:
        for i in range(len(stack)-1):score+=0.5*(stack[i+1]-stack[i])**2
    return score

def csi2(arr,win,half):
    sm=pd.Series(arr).rolling(win,center=True,min_periods=1).median().to_numpy()
    return rainflow_weighted(sm,half)

def block_ci(day_df,seed=20261013,B=3000,L=5):
    rng=np.random.default_rng(seed);n=len(day_df)
    base=day_df.base.to_numpy(float);ctrl=day_df.control.to_numpy(float)
    reduction=100*(base-ctrl)/base
    mean=np.mean(reduction);pooled=100*(base.sum()-ctrl.sum())/base.sum()
    vals=np.empty((B,2))
    for k in range(B):
        idx=[]
        while len(idx)<n:
            s=int(rng.integers(n));idx.extend((s+np.arange(L))%n)
        idx=np.asarray(idx[:n]);bb=base[idx];cc=ctrl[idx]
        vals[k]=[np.mean(100*(bb-cc)/bb),100*(bb.sum()-cc.sum())/bb.sum()]
    return {'mean_daily_pct':float(mean),'mean_daily_CI_low':float(np.quantile(vals[:,0],.025)),
            'mean_daily_CI_high':float(np.quantile(vals[:,0],.975)),
            'pooled_pct':float(pooled),'pooled_CI_low':float(np.quantile(vals[:,1],.025)),
            'pooled_CI_high':float(np.quantile(vals[:,1],.975)),'bootstrap_replications':B,'block_length_days':L}

def run(a):
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(a.a5zip) as z:
        names=z.namelist();manifest=json.loads(z.read(next(x for x in names if x.endswith('a5_manifest.json'))))
        old=pd.read_csv(z.open(next(x for x in names if x.endswith('a5_external_daily.csv'))))
    policy=manifest['selected_policy'];assert isinstance(policy,list) and len(policy)==2,'A7 requires frozen selected tuple'
    window=int(policy[0]);threshold=float(policy[1]);intercept=float(manifest['intercept']);coef=np.asarray(manifest['coefficients'],float)
    thermal=[];sens=[];repro=[];summary=[]
    for file in a.external:
        file=Path(file);label=file.stem;raw=load(file);features,diag=compute_features(str(file),windows=(15,30,60));days=eligible_days(raw,diag)
        # Observed one-minute, one-step transfer residuals; does not validate counterfactual control.
        for day in days:
            segs=split_contiguous(raw,day);resid=[];naive=[];yvals=[]
            for seg in segs:
                if len(seg)<2:continue
                T=seg.T_module_C.to_numpy(float);Ta=seg.T_ambient_C.to_numpy(float);G=seg.Gtotpoa_Wm2.to_numpy(float);v=seg.v_wind_ms.to_numpy(float)
                pred=T[:-1]+intercept+coef[0]*G[:-1]+(coef[1]+coef[2]*v[:-1])*(T[:-1]-Ta[:-1]);y=T[1:]
                resid.extend((pred-y).tolist());naive.extend((T[:-1]-y).tolist());yvals.extend(y.tolist())
            if resid:
                e=np.asarray(resid);nv=np.asarray(naive)
                thermal.append({'dataset':label,'date':str(day),'n_transitions':len(e),'bias_C':float(e.mean()),'RMSE_C':float(np.sqrt(np.mean(e*e))),
                                'MAE_C':float(np.mean(abs(e))),'persistence_RMSE_C':float(np.sqrt(np.mean(nv*nv)))})
            per={}
            for seg in segs:
                gate=features[f'nri_{window}m_lag1'].reindex(seg.index).ge(threshold).fillna(False).to_numpy(bool)
                p=simulate_segment(seg,gate,intercept,coef)
                for win in (1,3,5,9):
                    for half in (False,True):
                        key=(win,half)
                        if key not in per:per[key]=[0.,0.]
                        per[key][0]+=csi2(p.T_base.to_numpy(),win,half)
                        per[key][1]+=csi2(p.T_control.to_numpy(),win,half)
            for (win,half),(base,ctrl) in per.items():
                sens.append({'dataset':label,'date':str(day),'median_window':win,'include_half_cycles':half,'base':base,'control':ctrl,
                             'reduction_pct':100*(base-ctrl)/base if base>0 else np.nan})
            orig=old[(old.dataset==label)&(old.policy==str(tuple(policy)))&(old.date==str(day))]
            if len(orig)==1 and (5,False) in per:
                b,c=per[(5,False)];repro.append({'dataset':label,'date':str(day),'baseline_abs_diff':abs(b-float(orig.CSI2_base.iloc[0])),
                                                  'control_abs_diff':abs(c-float(orig.CSI2_control.iloc[0]))})
        print('Completed',label,'days',len(days))
    t=pd.DataFrame(thermal);s=pd.DataFrame(sens);r=pd.DataFrame(repro)
    t.to_csv(out/'a7_thermal_one_step_daily.csv',index=False);s.to_csv(out/'a7_csi2_sensitivity_daily.csv',index=False);r.to_csv(out/'a7_a5_regeneration_checks.csv',index=False)
    for (label,win,half),g in s.groupby(['dataset','median_window','include_half_cycles']):
        g=g.sort_values('date');usable=g[(g.base>0)&g.reduction_pct.notna()]
        if len(usable)<5:continue
        stats=block_ci(usable,seed=20261013+int(win)+int(half),B=a.bootstraps,L=a.block)
        summary.append({'dataset':label,'median_window':int(win),'include_half_cycles':bool(half),'n_days':len(usable),**stats})
    pd.DataFrame(summary).to_csv(out/'a7_block_bootstrap_sensitivity.csv',index=False)
    ts=t.groupby('dataset',as_index=False).agg(days=('date','count'),mean_daily_RMSE_C=('RMSE_C','mean'),mean_daily_bias_C=('bias_C','mean'),mean_persistence_RMSE_C=('persistence_RMSE_C','mean'),total_transitions=('n_transitions','sum'))
    ts.to_csv(out/'a7_thermal_transfer_summary.csv',index=False)
    err=float(r[['baseline_abs_diff','control_abs_diff']].max().max()) if len(r) else float('nan')
    result={'selected_policy':policy,'thermal_transfer':ts.to_dict('records'),'reproduced_days':len(r),'max_A5_CSI2_abs_error':err,
            'regeneration_pass':bool(len(r)==len(t) and err<1e-8),'n_sensitivity_rows':len(s),'block_length':a.block,
            'limitations':['One-step measured-temperature residuals do not validate free-running counterfactual trajectories.',
            'Centered median smoothing is offline; not a causal control feature.',
            'Block bootstrap is a sensitivity estimate, not guaranteed valid under nonstationarity.',
            'Closed/half cycle CSI2 are uncalibrated squared-temperature-range proxies.',
            'No optics or energy validation; external data must not be used for policy retuning.']}
    (out/'a7_manifest.json').write_text(json.dumps(result,indent=2))
    print('A7 RESULT',json.dumps(result,indent=2));print('A7 ROBUSTNESS SUMMARY');print(pd.DataFrame(summary).round(4).to_string(index=False))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--a5zip',required=True);p.add_argument('--external',nargs='+',required=True);p.add_argument('--out',default='package_a7_outputs');p.add_argument('--bootstraps',type=int,default=3000);p.add_argument('--block',type=int,default=5)
    run(p.parse_args())