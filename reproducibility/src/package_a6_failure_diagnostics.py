"""A6: frozen A5 diagnostic audit. No policy optimization or validation claims."""
import argparse, json, zipfile, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from package_a5_training_selection import load, eligible_days
from package_a_causal_nri import compute_features
from package_a4_corrected_controller import split_contiguous, simulate_segment, severity

def boot(x, seed=20261013, n=20000):
    x=np.asarray(x,float);x=x[np.isfinite(x)]
    if len(x)==0:return [None,None,None]
    rng=np.random.default_rng(seed)
    samples=rng.choice(x,(n,len(x)),replace=True).mean(axis=1)
    return [float(x.mean()),*map(float,np.quantile(samples,[.025,.975]))]

def main(zip_path, data_files, out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        def csv(s):return pd.read_csv(z.open('package_a5_outputs/'+s))
        ext=csv('a5_external_daily.csv');train=csv('a5_training_daily.csv');old=csv('a5_previously_inspected_2019.csv')
        manifest=json.load(z.open('package_a5_outputs/a5_manifest.json'))
    sel=manifest['selected_policy'];assert isinstance(sel,list) and len(sel)==2, 'A6 expects selected tuple policy'
    window,threshold=int(sel[0]),float(sel[1]);selected=str((window,threshold))
    assert selected in set(ext.policy),f'Missing selected policy {selected}'
    coef=np.asarray(manifest['coefficients'],float);intercept=float(manifest['intercept'])
    datasets={Path(p).stem:p for p in data_files}
    assert set(ext.dataset)==set(datasets),f'External files mismatch: {set(ext.dataset)^set(datasets)}'
    daily=[];summary=[];events=[];segments=[];checks=[]
    for name,g in ext.groupby('dataset',sort=True):
        wide={p:t.set_index('date').sort_index() for p,t in g.groupby('policy')}
        assert {selected,'baseline','always_available'}<=set(wide)
        common=sorted(set.intersection(*(set(t.index) for t in wide.values())))
        assert len(common)==len(wide[selected]),'Missing paired dates'
        for date in common:
            s=wide[selected].loc[date];a=wide['always_available'].loc[date];b=wide['baseline'].loc[date]
            assert np.isclose(s.CSI2_base,a.CSI2_base) and np.isclose(s.CSI2_base,b.CSI2_base)
            daily.append(dict(dataset=name,date=date,baseline_CSI2=s.CSI2_base,selected_CSI2=s.CSI2_control,always_CSI2=a.CSI2_control,
                selected_reduction_pct=s.CSI2_reduction_pct,always_reduction_pct=a.CSI2_reduction_pct,
                selected_advantage_pp=s.CSI2_reduction_pct-a.CSI2_reduction_pct,
                selected_irradiance_penalty_pct=s.irradiance_penalty_pct,
                always_irradiance_penalty_pct=a.irradiance_penalty_pct,
                selected_intervention_minutes=s.intervention_minutes,always_intervention_minutes=a.intervention_minutes,
                selected_angle_changes=s.angle_changes,always_angle_changes=a.angle_changes,
                segments=s.contiguous_segments,minutes=s.simulated_minutes,
                baseline_CSI2_zero=bool(np.isclose(s.CSI2_base,0))))
        d=pd.DataFrame([r for r in daily if r['dataset']==name])
        for metric in ['selected_reduction_pct','always_reduction_pct','selected_advantage_pp']:
            mean,lo,hi=boot(d[metric]);summary.append(dict(dataset=name,metric=metric,n_days=len(d),mean=mean,CI_low=lo,CI_high=hi,
                positive_days=int((d[metric]>1e-10).sum()),negative_days=int((d[metric]<-1e-10).sum()),ties=int((d[metric].abs()<=1e-10).sum()),
                zero_baseline_days=int(d.baseline_CSI2_zero.sum())))
        # Raw CSI2 weighted aggregate differs from mean percentage across days; report both.
        summary.append(dict(dataset=name,metric='pooled_CSI2_reduction_pct',n_days=len(d),
            mean=100*(d.baseline_CSI2.sum()-d.selected_CSI2.sum())/d.baseline_CSI2.sum() if d.baseline_CSI2.sum()>0 else np.nan,
            CI_low=np.nan,CI_high=np.nan,positive_days=np.nan,negative_days=np.nan,ties=np.nan,zero_baseline_days=int(d.baseline_CSI2_zero.sum())))
        raw=load(datasets[name]);feat,diag=compute_features(datasets[name],windows=(window,))
        dates=eligible_days(raw,diag)
        assert set(map(str,dates))==set(common), 'External cohort differs from frozen A5'
        for day in dates:
            parts=split_contiguous(raw,day)
            for j,seg in enumerate(parts):
                gate=feat[f'nri_{window}m_lag1'].reindex(seg.index).ge(threshold).fillna(False).to_numpy(bool)
                p=simulate_segment(seg,gate,intercept,coef)
                angle=p.angle.to_numpy();delta=np.diff(np.r_[0.,angle]);chg=np.flatnonzero(np.abs(delta)>1e-8)
                Tbase=p.T_base.to_numpy();Tctrl=p.T_control.to_numpy()
                # Five-minute windows are descriptive, and overlap; do not add them to infer total CSI2.
                for ix in chg:
                    lo=max(0,ix-5);hi=min(len(p)-1,ix+5)
                    events.append(dict(dataset=name,date=str(day),segment=j,timestamp=str(p.index[ix]),change_deg=float(delta[ix]),
                        change_type='enter_or_increase' if delta[ix]>0 else 'decrease_or_exit',
                        deltaT_before_C=float(Tctrl[ix]-Tbase[ix]),deltaT_5min_after_C=float(Tctrl[hi]-Tbase[hi]),
                        baseline_abs_5min_change_C=float(abs(Tbase[hi]-Tbase[ix])),
                        control_abs_5min_change_C=float(abs(Tctrl[hi]-Tctrl[ix])),
                        control_minus_baseline_abs_change_C=float(abs(Tctrl[hi]-Tctrl[ix])-abs(Tbase[hi]-Tbase[ix])),
                        gate_at_change=bool(gate[ix]),irradiance_Wm2=float(seg.Gtotpoa_Wm2.iloc[ix])))
                segments.append(dict(dataset=name,date=str(day),segment=j,minutes=len(p),changes=len(chg),
                    baseline_CSI2=severity(p.T_base),selected_CSI2=severity(p.T_control),
                    max_abs_temperature_difference_C=float(np.max(np.abs(Tctrl-Tbase))),
                    mean_temperature_difference_C=float(np.mean(Tctrl-Tbase))))
            # Check full daily regeneration against A5 outputs, from segment severity only.
            r=d.loc[d.date.eq(str(day))].iloc[0]
            dd=[v for v in segments if v['dataset']==name and v['date']==str(day)]
            c=sum(v['selected_CSI2'] for v in dd);b=sum(v['baseline_CSI2'] for v in dd)
            checks.append(dict(dataset=name,date=str(day),baseline_abs_error=abs(b-r.baseline_CSI2),selected_abs_error=abs(c-r.selected_CSI2)))
    pd.DataFrame(daily).to_csv(out/'a6_paired_external_days.csv',index=False)
    pd.DataFrame(summary).to_csv(out/'a6_external_bootstrap_summary.csv',index=False)
    pd.DataFrame(events).to_csv(out/'a6_angle_transition_events.csv',index=False)
    pd.DataFrame(segments).to_csv(out/'a6_segment_diagnostics.csv',index=False)
    pd.DataFrame(checks).to_csv(out/'a6_regeneration_checks.csv',index=False)
    maxerr=float(pd.DataFrame(checks)[['baseline_abs_error','selected_abs_error']].max().max())
    report={'selected_policy':sel,'external_datasets':sorted(datasets),'paired_days':len(daily),
      'transition_events':len(events),'segment_rows':len(segments),'max_abs_regeneration_error':maxerr,
      'regeneration_pass':bool(maxerr<1e-8),
      'warnings':['Bootstraps resample days independently within each dataset; serial dependence may make intervals optimistic.',
      'CSI2 uses only closed cycles, centered offline 5-point median, and squared temperature ranges; not calibrated fatigue damage.',
      'Event-window changes are descriptive and overlapping, not causal attribution or CSI2 decomposition.',
      'Thermal model fitted on 2019 System 2B is transferred unchanged to 2018 systems; no external thermal-model validation.',
      'G*cos(angle) is not validated tracker optical geometry; irradiance penalty is a proxy, not measured electrical energy.',
      'A6 is a frozen failure audit. Do not retune using these external results.']}
    (out/'a6_manifest.json').write_text(json.dumps(report,indent=2))
    print('A6 RESULT',json.dumps(report,indent=2))
    print('\nEXTERNAL SUMMARY\n',pd.DataFrame(summary).round(5).to_string(index=False))
    print('\nEVENT DESCRIPTIVES\n',pd.DataFrame(events).groupby(['dataset','change_type']).agg(events=('change_deg','size'),mean_extra_abs_5min_temp_change_C=('control_minus_baseline_abs_change_C','mean')).to_string() if events else 'No events')
    if not report['regeneration_pass']:raise RuntimeError('STOP: regenerated trajectories differ from frozen A5 daily CSI2')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--a5zip',required=True);ap.add_argument('--external',nargs='+',required=True);ap.add_argument('--out',default='package_a6_outputs');a=ap.parse_args();main(a.a5zip,a.external,a.out)