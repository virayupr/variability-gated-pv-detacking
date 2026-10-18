import sys,json,time
from pathlib import Path
import numpy as np,pandas as pd
sys.path.insert(0,'/mnt/data')
from package_a5_training_selection import load,eligible_days
from package_a_causal_nri import compute_features
from package_a4_corrected_controller import split_contiguous,simulate_segment,summarize
out=Path('/mnt/data/priority2_controller'); out.mkdir(exist_ok=True)
files=[Path('/mnt/data/PV_temperature_model_data_2018_System_1_1min.dat'),Path('/mnt/data/PV_temperature_model_data_2018_System_2A_1min.dat')]
import zipfile
with zipfile.ZipFile('/mnt/data/package_a5_outputs.zip') as z: man=json.loads(z.read('package_a5_outputs/a5_manifest.json'))
b0=man['intercept'];co=np.asarray(man['coefficients'])
print('coeff',b0,co,'selected',man['selected_policy'],flush=True)
configs=[(r,th,.12) for r in (200.,400.,600.) for th in (30.,45.,60.)]+[(400.,45.,thr) for thr in (.09,.15)]
rows=[]
for file in files:
 raw=load(file);feat,diag=compute_features(str(file),windows=(30,));days=eligible_days(raw,diag)
 print(file.name,'days',len(days),flush=True)
 for d in days:
  segs=split_contiguous(raw,d)
  for r,th,thr in configs:
   parts=[]
   for seg in segs:
    gate=feat['nri_30m_lag1'].reindex(seg.index).ge(thr).fillna(False).to_numpy(bool)
    parts.append(simulate_segment(seg,gate,b0,co,ramp_limit=r,theta_max=th,dwell_minutes=5))
   m=summarize(parts)
   if m:rows.append(dict(system='System 1' if 'System_1_' in file.name else 'System 2A',date=str(d),ramp_target=r,theta_max=th,gate_threshold=thr,**m))
 df=pd.DataFrame(rows);df.to_csv(out/'controller_grid_daily_checkpoint.csv',index=False)
 print('checkpoint',len(df),flush=True)
df=pd.DataFrame(rows);df.to_csv(out/'controller_grid_daily.csv',index=False)
summary=df.groupby(['system','ramp_target','theta_max','gate_threshold'],as_index=False).agg(days=('date','count'),mean_CSI2_reduction_pct=('CSI2_reduction_pct','mean'),mean_irradiance_penalty_pct=('irradiance_penalty_pct','mean'),mean_nonzero_minutes=('intervention_minutes','mean'),mean_gate_minutes=('gate_eligible_minutes','mean'),mean_angle_changes=('angle_changes','mean'),mean_angle_travel_deg=('angle_travel_deg','mean'),mean_simulated_minutes=('simulated_minutes','mean'))
summary.to_csv(out/'controller_grid_summary.csv',index=False)
print(summary.round(4).to_string(index=False),flush=True)