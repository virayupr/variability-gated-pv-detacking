from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path('/mnt/data')
OUT=ROOT/'priority1_thermal_benchmark'
LW=ROOT/'Longwave_thermal_emission_data_2018_1min.dat'
SIGMA=5.670374419e-8
lw=pd.read_csv(LW,sep=';',comment='#',parse_dates=['Timestamp_UTC'])
assert lw.Timestamp_UTC.is_unique
assert (lw.Etotdownlw_Wm2>0).all()
rows=[]
for system in ['1','2A']:
 path=ROOT/f'PV_temperature_model_data_2018_System_{system}_1min.dat'
 data=pd.read_csv(path,sep=';',comment='#',parse_dates=['Timestamp_UTC'])
 assert data.Timestamp_UTC.is_unique
 merged=data.merge(lw,on='Timestamp_UTC',how='left',validate='one_to_one')
 core=['T_module_C','T_ambient_C','Gtotpoa_Wm2','v_wind_ms']
 valid=merged[core].notna().all(axis=1)
 matched=merged.Etotdownlw_Wm2.notna()
 merged['T_sky_C']=np.where(matched,(merged.Etotdownlw_Wm2/SIGMA)**0.25-273.15,np.nan)
 # Input alignment only; this does not calibrate or evaluate Barry's model.
 merged.to_csv(OUT/f'barry_input_alignment_system_{system}.csv',index=False)
 rows.append({'system':system,'PV_rows':len(merged),'PV_complete_core_rows':int(valid.sum()),'longwave_matched_rows':int(matched.sum()),'PV_complete_and_longwave_rows':int((valid&matched).sum()),'PV_complete_missing_longwave_rows':int((valid&~matched).sum()),'complete_core_retained_pct':float(100*(valid&matched).sum()/valid.sum()),'first_PV_UTC':str(data.Timestamp_UTC.min()),'last_PV_UTC':str(data.Timestamp_UTC.max()),'first_longwave_UTC':str(lw.Timestamp_UTC.min()),'last_longwave_UTC':str(lw.Timestamp_UTC.max())})
pd.DataFrame(rows).to_csv(OUT/'longwave_alignment_summary.csv',index=False)
print(pd.DataFrame(rows).to_string(index=False))