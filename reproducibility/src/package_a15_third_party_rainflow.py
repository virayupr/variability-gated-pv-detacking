"""A15: third-party rainflow comparison of frozen A7 cycle-severity outputs.
Requires independently maintained rainflow==3.2.0 from PyPI, not vendored.
No parameter tuning or physical validation. Exits nonzero if mismatch.
"""
import argparse, hashlib, io, json, zipfile, importlib.metadata
from pathlib import Path
import numpy as np
import pandas as pd
import rainflow
from package_a5_training_selection import load, eligible_days
from package_a_causal_nri import compute_features
from package_a4_corrected_controller import split_contiguous, simulate_segment

def score(series, window, half):
    smooth=pd.Series(series).rolling(window,center=True,min_periods=1).median().to_numpy()
    return float(sum(float(r)**2 * float(c) for r, mean, c, i, j in rainflow.extract_cycles(smooth) if half or c == 1.0))

def archive_csv(path,suffix):
    with zipfile.ZipFile(path) as z:
        return pd.read_csv(io.BytesIO(z.read(next(n for n in z.namelist() if n.endswith(suffix)))))

def archive_json(path,suffix):
    with zipfile.ZipFile(path) as z:
        return json.loads(z.read(next(n for n in z.namelist() if n.endswith(suffix))))

def benchmark_cases():
    # Externally documented reference: https://github.com/pawelkn/rainflow
    # count_cycles [-2,1,-3,5,-1,3,-4,4,-2], bin size 2 =>
    # 4:2.0, 6:0.5, 8:1.0, 10:0.5 (and 2:0)
    x=[-2,1,-3,5,-1,3,-4,4,-2]
    observed=dict(rainflow.count_cycles(x,binsize=2.0))
    expected={4.0:2.0,6.0:0.5,8.0:1.0,10.0:0.5}
    passed=all(abs(observed.get(k,0)-v)<1e-12 for k,v in expected.items()) and abs(sum(observed.values())-4)<1e-12
    return [dict(case='published_cpp_binned_example',pass_test=passed,expected=json.dumps(expected),observed=json.dumps(observed))]

def main(args):
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    version=importlib.metadata.version('rainflow')
    if version!='3.2.0':raise RuntimeError(f'Frozen dependency rainflow==3.2.0 required, found {version}')
    benchmarks=benchmark_cases();pd.DataFrame(benchmarks).to_csv(out/'a15_published_reference_benchmarks.csv',index=False)
    if not all(b['pass_test'] for b in benchmarks):raise AssertionError('Published external reference benchmark failed')
    m=archive_json(args.a5,'a5_manifest.json');assert m['selected_policy']==[30,0.12]
    archived=archive_csv(args.a7,'a7_csi2_sensitivity_daily.csv')
    a14=archive_csv(args.a14,'a14_cycle_counter_crosscheck_624.csv') if args.a14 else None
    coef=np.array(m['coefficients'],float);intercept=float(m['intercept'])
    rows=[];file_hashes={}
    for path in args.external:
        path=Path(path);label=path.stem;file_hashes[label]=hashlib.sha256(path.read_bytes()).hexdigest()
        raw=load(path);features,diag=compute_features(str(path),windows=(15,30,60));days=eligible_days(raw,diag)
        print('A15 external',label,'eligible days',len(days),flush=True)
        for day in days:
            values={(w,h):[0.,0.] for w in (1,3,5,9) for h in (False,True)}
            for seg in split_contiguous(raw,day):
                gate=features['nri_30m_lag1'].reindex(seg.index).ge(0.12).fillna(False).to_numpy(bool)
                sim=simulate_segment(seg,gate,intercept,coef)
                for (w,h),pair in values.items():
                    pair[0]+=score(sim.T_base.to_numpy(),w,h)
                    pair[1]+=score(sim.T_control.to_numpy(),w,h)
            for (w,h),(base,control) in values.items():
                rows.append(dict(dataset=label,date=str(day),median_window=w,include_half_cycles=h,base=base,control=control,reduction_pct=100*(base-control)/base if base>0 else np.nan))
    fresh=pd.DataFrame(rows);keys=['dataset','date','median_window','include_half_cycles']
    if len(fresh)!=624:raise AssertionError(f'Expected 624 rows; found {len(fresh)}')
    joined=fresh.merge(archived,on=keys,validate='one_to_one',suffixes=('_a15','_a7'),indicator=True)
    if len(joined)!=624 or not joined._merge.eq('both').all():raise AssertionError('A7 row identity mismatch')
    for name in ['base','control']:
        joined[name+'_abs_diff']=abs(joined[name+'_a15']-joined[name+'_a7'])
    joined['pass_a7']=(joined.base_abs_diff<=args.tol)&(joined.control_abs_diff<=args.tol)
    joined.to_csv(out/'a15_third_party_vs_a7_624.csv',index=False)
    if a14 is not None:
        # A14 output contains both A14 and A7 metrics. Compare with the separately coded A14 values.
        sub=a14[keys+['base_a14','control_a14']]
        j=fresh.merge(sub,on=keys,validate='one_to_one')
        for n in ['base','control']:j[n+'_abs_diff']=abs(j[n]-j[n+'_a14'])
        j['pass_a14']=(j.base_abs_diff<=args.tol)&(j.control_abs_diff<=args.tol)
        j.to_csv(out/'a15_third_party_vs_a14_624.csv',index=False)
        a14_failed=int((~j.pass_a14).sum());a14_max=float(j[['base_abs_diff','control_abs_diff']].max().max())
    else:a14_failed=None;a14_max=None
    primary=fresh[(fresh.median_window==5)&(~fresh.include_half_cycles)]
    summary=[]
    for label,g in primary.groupby('dataset'):
        summary.append(dict(dataset=label,n_days=len(g),mean_daily_pct=float(g.reduction_pct.mean()),pooled_pct=float(100*(g.base.sum()-g.control.sum())/g.base.sum())))
    pd.DataFrame(summary).to_csv(out/'a15_frozen_primary_summary.csv',index=False)
    failed=int((~joined.pass_a7).sum());maximum=float(joined[['base_abs_diff','control_abs_diff']].max().max())
    result=dict(status='PASS_THIRD_PARTY_COMPARISON' if failed==0 and (a14_failed in [0,None]) else 'FAIL_THIRD_PARTY_COMPARISON',rainflow_version=version,benchmark_pass=True,comparisons=len(joined),a7_failed=failed,a7_max_abs_difference=maximum,a14_failed=a14_failed,a14_max_abs_difference=a14_max,tolerance=args.tol,frozen_policy=m['selected_policy'],external_sha256=file_hashes,limitations=['Third-party library algorithm agreement is not formal ASTM certification.','No measured intervention temperature, fatigue or electrical yield.','Previously inspected external datasets are exploratory, not pristine holdouts.'])
    (out/'a15_manifest.json').write_text(json.dumps(result,indent=2))
    (out/'a15_evidence_lock.md').write_text('# A15 evidence lock\n\nStatus: '+result['status']+'\n\nThird-party library rainflow==3.2.0; comparison with frozen A7 and separately coded A14.\n\nDo not alter archived A5–A14 outputs. Any discrepancy requires investigation, not automatic overwriting.\n\n'+pd.DataFrame(summary).to_markdown(index=False)+'\n\nNo physical fatigue, lifetime, or energy benefit established.\n')
    print('A15 RESULT',json.dumps(result,indent=2),flush=True)
    if failed or (a14_failed not in [0,None]):raise AssertionError('A15 discrepancy: see output CSVs; evidence lock failed')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--a5',required=True);p.add_argument('--a7',required=True);p.add_argument('--a14');p.add_argument('--external',nargs=2,required=True);p.add_argument('--out',default='package_a15_outputs');p.add_argument('--tol',type=float,default=1e-8);main(p.parse_args())