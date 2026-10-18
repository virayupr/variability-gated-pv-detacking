"""Descriptive conditional free-running errors; not a Barry benchmark."""
from pathlib import Path
import json,zipfile
import numpy as np,pandas as pd
from package_a5_training_selection import load,eligible_days
from package_a_causal_nri import compute_features
from package_a4_corrected_controller import split_contiguous
from package_a9_physical_gap import propagate
root=Path('/mnt/data'); out=root/'priority1_thermal_benchmark'
with zipfile.ZipFile(root/'package_a5_outputs.zip') as z:
 m=json.loads(z.read(next(n for n in z.namelist() if n.endswith('a5_manifest.json'))))
ic=float(m['intercept']);co=np.asarray(m['coefficients'],float)
records=[]
for file in [root/'PV_temperature_model_data_2018_System_1_1min.dat',root/'PV_temperature_model_data_2018_System_2A_1min.dat']:
 raw=load(file);_,diag=compute_features(str(file));days=eligible_days(raw,diag)
 for day in days:
  for seg in split_contiguous(raw,day):
   G=seg.Gtotpoa_Wm2.to_numpy(float);Ta=seg.T_ambient_C.to_numpy(float);v=seg.v_wind_ms.to_numpy(float);obs=seg.T_module_C.to_numpy(float)
   pred=propagate(obs[0],G,Ta,v,ic,co)
   # Rapid ramp is a one-minute absolute irradiance change >= 100 W/m2.
   # Restrict to pairs with both samples daylight >50 W/m2.
   ramp=np.zeros(len(G),bool);ramp[1:]=(np.abs(np.diff(G))>=100)&(G[1:]>50)&(G[:-1]>50)
   for horizon in (30,60,120,'full_segment'):
    n=min(len(G),horizon+1) if isinstance(horizon,int) else len(G)
    for label,mask in [('rapid_ramp',ramp[:n]),('other',~ramp[:n])]:
     if not np.any(mask):continue
     err=(pred[:n]-obs[:n])[mask]; pers=(obs[0]-obs[:n])[mask]
     records.append(dict(dataset=file.stem,date=str(day),segment_start=str(seg.index[0]),horizon=str(horizon),condition=label,n=int(len(err)),model_sse=float(np.sum(err**2)),persistence_sse=float(np.sum(pers**2)),model_sum_error=float(np.sum(err)),persistence_sum_error=float(np.sum(pers))))
d=pd.DataFrame(records);d.to_csv(out/'rapid_ramp_conditional_segments.csv',index=False)
s=d.groupby(['dataset','horizon','condition'],as_index=False)[['n','model_sse','persistence_sse','model_sum_error','persistence_sum_error']].sum()
s['model_RMSE_C']=np.sqrt(s.model_sse/s.n);s['persistence_RMSE_C']=np.sqrt(s.persistence_sse/s.n);s['model_bias_C']=s.model_sum_error/s.n;s['persistence_bias_C']=s.persistence_sum_error/s.n
s.to_csv(out/'rapid_ramp_conditional_summary.csv',index=False)
print(s[['dataset','horizon','condition','n','model_RMSE_C','persistence_RMSE_C','model_bias_C','persistence_bias_C']].round(4).to_string(index=False))