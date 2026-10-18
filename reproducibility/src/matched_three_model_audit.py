"""Matched 2018 three-model diagnostic. Barry published parameters were fitted to these systems (in-sample).
All models evaluated on identical complete meteorology+longwave runs; segment-start initialization differs:
A5 and persistence start from measured T, Barry published model uses causal normalized kernel.
Short horizons are run prefixes, not rolling forecasts. NOT a head-to-head independent model generalization test.
"""
from pathlib import Path
import zipfile,json
import numpy as np,pandas as pd
from scipy.signal import lfilter
from package_a5_training_selection import load,eligible_days
from package_a_causal_nri import compute_features
from package_a4_corrected_controller import split_contiguous
from package_a9_physical_gap import propagate
OUT=Path('/mnt/data/priority1_thermal_benchmark'); ROOT=Path('/mnt/data')
with zipfile.ZipFile(ROOT/'package_a5_outputs.zip') as z:
 m=json.loads(z.read(next(n for n in z.namelist() if n.endswith('a5_manifest.json'))))
ic=float(m['intercept']);co=np.array(m['coefficients'],float)
PARAM={'1':(26.774,4.355,0.207,588.8),'2A':(27.182,4.155,0.010,508.9)}
rows=[]; pointrows=[]
for sys,(u1,u2,u3,tau) in PARAM.items():
 path=ROOT/f'PV_temperature_model_data_2018_System_{sys}_1min.dat';raw=load(path);_,diag=compute_features(str(path));days=eligible_days(raw,diag)
 barry=pd.read_csv(OUT/f'barry_input_alignment_system_{sys}.csv',parse_dates=['Timestamp_UTC']).set_index('Timestamp_UTC')
 assert not barry.index.has_duplicates
 for day in days:
  for seg in split_contiguous(raw,day):
   common=seg.join(barry[['Etotdownlw_Wm2','T_sky_C']],how='left')
   valid=common[['T_module_C','T_ambient_C','Gtotpoa_Wm2','v_wind_ms','T_sky_C']].notna().all(axis=1)
   groups=(~valid | (valid & ~valid.shift(fill_value=False)) | common.index.to_series().diff().ne(pd.Timedelta(minutes=1))).cumsum()
   for _,g in common.loc[valid].groupby(groups[valid]):
    if len(g)<31:continue
    obs=g.T_module_C.to_numpy(float);G=g.Gtotpoa_Wm2.to_numpy(float);Ta=g.T_ambient_C.to_numpy(float);v=g.v_wind_ms.to_numpy(float);sky=g.T_sky_C.to_numpy(float)
    ours=propagate(obs[0],G,Ta,v,ic,co);pers=np.full(len(obs),obs[0]);eq=Ta+G/(u1+u2*v)+u3*(sky-Ta)
    alpha=np.exp(-60/tau); b=lfilter([1.],[1.,-alpha],eq)/lfilter([1.],[1.,-alpha],np.ones(len(eq)))
    pred={'A5_dynamic':ours,'persistence':pers,'Barry_published':b}
    start=str(g.index[0]); date=str(day)
    for h in [30,60,120,'full_run']:
     n=min(len(g),h+1) if isinstance(h,int) else len(g)
     if n<2:continue
     for name,p in pred.items():
      e=p[:n]-obs[:n]
      rows.append(dict(system=sys,date=date,run_start=start,run_minutes=len(g),horizon=str(h),model=name,n_points=n,RMSE_C=float(np.sqrt(np.mean(e*e))),MAE_C=float(np.mean(abs(e))),bias_C=float(np.mean(e)),SSE_C2=float(np.sum(e*e)),sum_error_C=float(np.sum(e))))
    ramp=np.r_[False,(np.abs(np.diff(G))>=100)&(G[1:]>50)&(G[:-1]>50)]
    for name,p in pred.items():
     e=p-obs
     for condition,mask in [('rapid_ramp',ramp),('other',~ramp)]:
      if not mask.any():continue
      pointrows.append(dict(system=sys,date=date,run_start=start,model=name,condition=condition,n=int(mask.sum()),SSE_C2=float(np.sum(e[mask]**2)),sum_error_C=float(np.sum(e[mask])),sum_abs_C=float(np.sum(np.abs(e[mask])))))
res=pd.DataFrame(rows);pts=pd.DataFrame(pointrows)
assert res.groupby(['system','horizon','model']).size().groupby(level=0).nunique().eq(1).all()
res.to_csv(OUT/'matched_three_model_runs.csv',index=False);pts.to_csv(OUT/'matched_three_model_ramp_parts.csv',index=False)
s=res.groupby(['system','horizon','model'],as_index=False).agg(runs=('RMSE_C','size'),mean_run_RMSE_C=('RMSE_C','mean'),mean_run_MAE_C=('MAE_C','mean'),mean_run_bias_C=('bias_C','mean'),points=('n_points','sum'),SSE_C2=('SSE_C2','sum'),sum_error_C=('sum_error_C','sum'))
s['pooled_RMSE_C']=np.sqrt(s.SSE_C2/s.points);s['pooled_bias_C']=s.sum_error_C/s.points
s.to_csv(OUT/'matched_three_model_summary.csv',index=False)
p=pts.groupby(['system','condition','model'],as_index=False)[['n','SSE_C2','sum_error_C','sum_abs_C']].sum();p['RMSE_C']=np.sqrt(p.SSE_C2/p.n);p['MAE_C']=p.sum_abs_C/p.n;p['bias_C']=p.sum_error_C/p.n;p.to_csv(OUT/'matched_three_model_ramp_summary.csv',index=False)
print(s[['system','horizon','model','runs','mean_run_RMSE_C','pooled_RMSE_C','mean_run_bias_C']].round(4).to_string(index=False));print('\nRAMP\n',p[['system','condition','model','n','RMSE_C','bias_C']].round(4).to_string(index=False))
print('\nCAVEAT: Barry published parameters in-sample; matched forcing and run boundaries, but Barry kernel not initialized from observed temperature; A5 and persistence are.')