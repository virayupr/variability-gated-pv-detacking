"""Barry et al (2020) Table 3 published-parameter reproduction; NOT independent validation.
Causal exponential smoothing per Eq (2)-(5), normalized at run starts.
"""
from pathlib import Path
import numpy as np, pandas as pd
from scipy.signal import lfilter
OUT=Path('/mnt/data/priority1_thermal_benchmark')
PARAM={'1':(26.774,4.355,0.207,588.8),'2A':(27.182,4.155,0.010,508.9)}
rows=[]; predictions=[]
for sys,(u1,u2,u3,tau) in PARAM.items():
 df=pd.read_csv(OUT/f'barry_input_alignment_system_{sys}.csv',parse_dates=['Timestamp_UTC'])
 cols=['T_module_C','T_ambient_C','Gtotpoa_Wm2','v_wind_ms','T_sky_C']
 valid=df[cols].notna().all(axis=1).to_numpy()
 time=df.Timestamp_UTC
 runs=np.cumsum((~valid)|(~pd.Series(valid).shift(fill_value=False).to_numpy())|(time.diff().dt.total_seconds().fillna(60).to_numpy()!=60))
 b=np.full(len(df),np.nan)
 for _,g in df.loc[valid].groupby(runs[valid],sort=False):
  idx=g.index.to_numpy()
  raw=g.T_ambient_C.to_numpy()+g.Gtotpoa_Wm2.to_numpy()/(u1+u2*g.v_wind_ms.to_numpy())+u3*(g.T_sky_C.to_numpy()-g.T_ambient_C.to_numpy())
  alpha=np.exp(-60/tau)
  # exact normalized exponential moving mean with row-specific denominator
  num=lfilter([1.],[1.,-alpha],raw)
  den=lfilter([1.],[1.,-alpha],np.ones(len(raw)))
  b[idx]=num/den
 df['barry_published_C']=b
 df['valid_run']=np.where(valid,runs,np.nan)
 df.to_csv(OUT/f'barry_published_predictions_system_{sys}.csv',index=False)
 # Summarize only runs >=30min, whole run is same evaluation for this method
 for _,g in df.loc[valid].groupby('valid_run'):
  if len(g)<31:continue
  err=(g.barry_published_C-g.T_module_C).to_numpy()
  for h in [30,60,120,'full_run']:
   n=min(len(g),h+1) if isinstance(h,int) else len(g)
   if n<2:continue
   e=err[:n]
   rows.append(dict(system=sys,date=str(g.Timestamp_UTC.iloc[0].date()),run_start=str(g.Timestamp_UTC.iloc[0]),run_minutes=len(g),horizon=str(h),n_points=n,RMSE_C=float(np.sqrt(np.mean(e**2))),MAE_C=float(np.mean(abs(e))),bias_C=float(e.mean()),max_abs_C=float(np.max(abs(e)))))
res=pd.DataFrame(rows)
res.to_csv(OUT/'barry_published_run_evaluations.csv',index=False)
summ=res.groupby(['system','horizon'],as_index=False).agg(n_runs=('RMSE_C','size'),mean_run_RMSE_C=('RMSE_C','mean'),mean_run_MAE_C=('MAE_C','mean'),mean_run_bias_C=('bias_C','mean'))
summ.to_csv(OUT/'barry_published_run_summary.csv',index=False)
print(summ.to_string(index=False))
print('IMPORTANT: published parameters were fitted using the same 2018 systems. This is NOT out-of-sample validation. Run boundaries differ from A9 and results MUST NOT be directly compared with A9 means.')