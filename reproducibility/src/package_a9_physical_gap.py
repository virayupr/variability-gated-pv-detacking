"""A9 exploratory transfer/assumption sensitivity; NEVER validates tracker optics or fatigue.
Frozen A5 policy; no optimization. Usage: python package_a9_physical_gap.py --a5zip ... --external file1 file2 --out ...
"""
import argparse, json, zipfile, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from package_a5_training_selection import load, eligible_days
from package_a_causal_nri import compute_features
from package_a4_corrected_controller import split_contiguous, simulate_segment, severity

def propagate(T0,G,Ta,v,intercept,coef):
    n=len(G); T=np.empty(n);T[0]=T0
    for i in range(n-1):
        T[i+1]=T[i]+intercept+coef[0]*G[i]+(coef[1]+coef[2]*v[i])*(T[i]-Ta[i])
        if not np.isfinite(T[i+1]) or abs(T[i+1])>1e5:
            T[i+1:]=np.nan;break
    return T

def main(a):
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(a.a5zip) as z:
        m=json.loads(z.read(next(n for n in z.namelist() if n.endswith('a5_manifest.json'))))
        old=pd.read_csv(z.open(next(n for n in z.namelist() if n.endswith('a5_external_daily.csv'))))
    policy=m['selected_policy'];assert policy==[30,0.12], 'Unexpected policy; stop and audit'
    ic=float(m['intercept']);co=np.asarray(m['coefficients'],float)
    transfer=[]; sensitivity=[];checks=[]
    for fname in a.external:
        path=Path(fname);raw=load(path);f,diag=compute_features(str(path));days=eligible_days(raw,diag);label=path.stem
        assert len(days)==39, f'Unexpected eligible days in {label}: {len(days)}'
        for day in days:
            parts=[]; daily={key:[0.,0.] for key in ['reference','optics_0p5','optics_1p5','Gcoef_0p8','Gcoef_1p2','cooling_0p8','cooling_1p2']}
            for seg in split_contiguous(raw,day):
                gate=f['nri_30m_lag1'].reindex(seg.index).ge(.12).fillna(False).to_numpy(bool)
                p=simulate_segment(seg,gate,ic,co)
                G=seg.Gtotpoa_Wm2.to_numpy(float);Ta=seg.T_ambient_C.to_numpy(float);v=seg.v_wind_ms.to_numpy(float);obs=seg.T_module_C.to_numpy(float)
                angle=p.angle.to_numpy(float);attenuation=1-np.cos(np.deg2rad(angle))
                cases={
                    'reference':(co,G*(1-attenuation)),
                    'optics_0p5':(co,G*np.clip(1-0.5*attenuation,0,1)),
                    'optics_1p5':(co,G*np.clip(1-1.5*attenuation,0,1)),
                    'Gcoef_0p8':(co*np.array([0.8,1,1]),G*(1-attenuation)),
                    'Gcoef_1p2':(co*np.array([1.2,1,1]),G*(1-attenuation)),
                    'cooling_0p8':(co*np.array([1,0.8,0.8]),G*(1-attenuation)),
                    'cooling_1p2':(co*np.array([1,1.2,1.2]),G*(1-attenuation))}
                for key,(coeff,gcontrol) in cases.items():
                    base=propagate(obs[0],G,Ta,v,ic,coeff)
                    control=propagate(obs[0],gcontrol,Ta,v,ic,coeff)
                    daily[key][0]+=severity(base);daily[key][1]+=severity(control)
                # free-running observational baseline from first sample, no internal reset
                predicted=p.T_base.to_numpy(float)
                for horizon in (30,60,120,'full_segment'):
                    n=min(len(obs),horizon+1) if isinstance(horizon,int) else len(obs)
                    if n<2:continue
                    e=predicted[:n]-obs[:n]
                    transfer.append(dict(dataset=label,date=str(day),segment_start=str(seg.index[0]),horizon=str(horizon),n_points=n,
                        RMSE_C=float(np.sqrt(np.mean(e*e))),MAE_C=float(np.mean(abs(e))),bias_C=float(e.mean()),
                        max_abs_error_C=float(np.max(abs(e))),segment_minutes=len(obs)))
                parts.append(p)
            for key,(base,ctrl) in daily.items():
                sensitivity.append(dict(dataset=label,date=str(day),scenario=key,CSI2_base=base,CSI2_control=ctrl,
                    reduction_pct=100*(base-ctrl)/base if base>0 else np.nan))
            ref=daily['reference'];match=old[(old.dataset==label)&(old.policy==str(tuple(policy)))&(old.date==str(day))]
            assert len(match)==1
            checks.append(dict(dataset=label,date=str(day),base_error=abs(ref[0]-float(match.CSI2_base.iloc[0])),
                               control_error=abs(ref[1]-float(match.CSI2_control.iloc[0]))))
        print('A9 completed',label,len(days),'days')
    tr=pd.DataFrame(transfer);ss=pd.DataFrame(sensitivity);ck=pd.DataFrame(checks)
    assert len(ck)==78 and ck[['base_error','control_error']].max().max()<1e-8,'A5 reproduction failure'
    for name,frame in [('a9_free_running_segments.csv',tr),('a9_assumption_sensitivity_daily.csv',ss),('a9_reference_checks.csv',ck)]:frame.to_csv(out/name,index=False)
    ts=tr.groupby(['dataset','horizon'],as_index=False).agg(evaluations=('RMSE_C','size'),mean_RMSE_C=('RMSE_C','mean'),median_RMSE_C=('RMSE_C','median'),mean_bias_C=('bias_C','mean'),mean_max_abs_error_C=('max_abs_error_C','mean'))
    ts.to_csv(out/'a9_free_running_summary.csv',index=False)
    summ=ss.groupby(['dataset','scenario'],as_index=False).agg(n_days=('date','count'),mean_daily_reduction_pct=('reduction_pct','mean'),sum_baseline=('CSI2_base','sum'),sum_control=('CSI2_control','sum'))
    summ['pooled_reduction_pct']=100*(summ.sum_baseline-summ.sum_control)/summ.sum_baseline
    summ.to_csv(out/'a9_assumption_sensitivity_summary.csv',index=False)
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    result={'status':'EXPLORATORY_ASSUMPTION_STRESS_TEST_NOT_PHYSICAL_VALIDATION','selected_policy':policy,
        'a5_zip_sha256':sha(a.a5zip),'external_sha256':{Path(p).name:sha(p) for p in a.external},
        'reference_reproduction_pass':True,'reproduced_days':len(ck),'max_reference_error':float(ck[['base_error','control_error']].max().max()),
        'design':{'free_running':'initial measured T at start of each contiguous segment; 30/60/120-minute prefixes and full segment; no resetting inside segment',
          'optical':'fixed reference angle commands; scale modeled fractional cosine attenuation by 0.5 and 1.5; no command recomputation',
          'thermal':'multiply fitted irradiance coefficient or both cooling coefficients by 0.8 or 1.2; intercept unchanged; uncalibrated perturbations',
          'severity':'five-point centered median, full closed cycles only; A5 definition'},
        'limitations':['No observed detacked tracker trajectory; optical scenarios are assumed, not validated.',
          'Free-running baseline uses observed forcing, not counterfactual intervention validation.',
          'Only one start per contiguous segment; short horizons are prefixes, not independent sliding windows.',
          'No new controller tuning, statistical confirmation, measured power, fatigue, or lifetime inference.']}
    (out/'a9_manifest.json').write_text(json.dumps(result,indent=2))
    (out/'a9_validation_gap_register.md').write_text('''# A9 validation gap register\n\n1. **Tracker geometry and optics:** measure tracker angles, plane-of-array irradiance at different commands, incidence-angle response, diffuse/direct decomposition, shading, actuator constraints. The G*cos(angle) model is not validated.\n2. **Thermal counterfactual:** record matched or randomized tracking versus detacking intervals with module backsheet temperature, ambient temperature, wind, irradiance, and synchronized controls. Avoid relying on one-step transfer RMSE alone.\n3. **Energy:** collect calibrated DC/AC power and energy, inverter curtailment, and tracking actuation energy; do not equate irradiance sum with yield.\n4. **Damage:** predefine cycle counting and temperature-to-damage relationship with material and accelerated-aging evidence. CSI2 is not measured fatigue.\n5. **Inference:** preregister primary estimand, sample size and blocked design; acquire genuinely new sites/time periods because 2018 systems have been inspected.\n6. **Governance:** preserve frozen A5 policy and A1–A9 provenance; no retuning on inspected 2018 cohorts.\n\nA9 sensitivity multipliers are arbitrary stress tests, not confidence intervals or calibrated physical uncertainty.\n''')
    print('A9 RESULT',json.dumps(result,indent=2));print('\nFREE-RUNNING SUMMARY\n',ts.round(4).to_string(index=False));print('\nASSUMPTION SENSITIVITY\n',summ[['dataset','scenario','mean_daily_reduction_pct','pooled_reduction_pct']].round(4).to_string(index=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--a5zip',required=True);p.add_argument('--external',nargs='+',required=True);p.add_argument('--out',default='package_a9_outputs');main(p.parse_args())