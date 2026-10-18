"""A10 read-only manuscript evidence consolidation of A5–A9 output ZIPs.
No optimization, refitting, bootstrap reruns, or physical validation.
"""
import argparse, hashlib, json, zipfile
from pathlib import Path
from io import BytesIO
import numpy as np
import pandas as pd

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def archive(path):
    z=zipfile.ZipFile(path)
    bad=z.testzip()
    assert bad is None, f'Corrupt ZIP member: {bad}'
    return z
def read(z,basename,kind='csv'):
    names=[n for n in z.namelist() if n.rsplit('/',1)[-1]==basename]
    assert len(names)==1,(basename,names)
    b=z.read(names[0])
    return json.loads(b) if kind=='json' else pd.read_csv(BytesIO(b))
def fail(cond,msg):
    if not cond: raise AssertionError(msg)
def main(args):
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    paths={k:Path(getattr(args,'a'+str(k))) for k in range(5,10)}
    for k,p in paths.items():fail(p.is_file(),f'Missing A{k}: {p}')
    zs={k:archive(p) for k,p in paths.items()}
    ms={k:read(zs[k],f'a{k}_manifest.json','json') for k in range(5,10)}
    sha={str(k):digest(p) for k,p in paths.items()}
    policy=[30,0.12]
    for k in range(5,10):fail(ms[k].get('selected_policy')==policy,f'A{k} frozen policy mismatch')
    for k in (5,6,7):fail(ms[8]['input_provenance'][f'A{k}']['sha256']==sha[str(k)],f'A8 provenance mismatch for A{k}')
    fail(ms[9]['a5_zip_sha256']==sha['5'],'A9 provenance mismatch for A5')
    for k in (6,7):fail(ms[k].get('regeneration_pass') is True,f'A{k} regeneration not PASS')
    fail(ms[9]['reference_reproduction_pass'] is True and ms[9]['reproduced_days']==78,'A9 reference check not PASS')
    a5=read(zs[5],'a5_external_daily.csv'); a6=read(zs[6],'a6_regeneration_checks.csv')
    a7=read(zs[7],'a7_a5_regeneration_checks.csv');a8=read(zs[8],'a8_primary_and_sensitivity_reconciliation.csv')
    a9=read(zs[9],'a9_reference_checks.csv');a9s=read(zs[9],'a9_assumption_sensitivity_summary.csv')
    a9tr=read(zs[9],'a9_free_running_summary.csv'); a7tr=read(zs[7],'a7_thermal_transfer_summary.csv')
    fail(len(a9)==78 and len(a8)==2,'Expected 78 external days and two datasets')
    fail(a9[['base_error','control_error']].to_numpy().max()<1e-8,'A9 daily numerical checks failed')
    fail(a8['n_days_closed'].eq(39).all(),'Expected 39 days per dataset')
    fail(a9s.groupby('dataset').size().eq(7).all(),'Expected seven sensitivity scenarios per dataset')
    fail(a9tr.groupby('dataset').size().eq(4).all(),'Expected four free-running horizons per dataset')
    # Compare archived A8 reference estimands to A9 independently computed reference rows.
    rows=[]
    for _,r in a8.iterrows():
        s=a9s[(a9s.dataset==r.dataset)&(a9s.scenario=='reference')]
        fail(len(s)==1,f'Missing A9 reference for {r.dataset}')
        v=s.iloc[0]
        delta_daily=abs(float(v.mean_daily_reduction_pct)-float(r.mean_daily_pct_closed))
        delta_pool=abs(float(v.pooled_reduction_pct)-float(r.pooled_pct_closed))
        fail(delta_daily<1e-8 and delta_pool<1e-8,f'A8/A9 metric mismatch for {r.dataset}')
        rows.append(dict(dataset=r.dataset,n_days=int(r.n_days_closed),mean_daily_closed_pct=float(r.mean_daily_pct_closed),
            mean_daily_block_CI_low=float(r.mean_daily_CI_low_closed),mean_daily_block_CI_high=float(r.mean_daily_CI_high_closed),
            pooled_closed_pct=float(r.pooled_pct_closed),pooled_block_CI_low=float(r.pooled_CI_low_closed),pooled_block_CI_high=float(r.pooled_CI_high_closed),
            mean_daily_with_half_pct=float(r.mean_daily_pct_with_half),
            mean_daily_with_half_CI_low=float(r.mean_daily_CI_low_with_half),mean_daily_with_half_CI_high=float(r.mean_daily_CI_high_with_half),
            mean_daily_vs_pooled_sign_disagree=bool(r.daily_vs_pooled_sign_disagree),closed_vs_half_sign_disagree=bool(r.closed_vs_half_sign_disagree),
            a8_a9_daily_difference=delta_daily,a8_a9_pooled_difference=delta_pool))
    main=pd.DataFrame(rows);main.to_csv(out/'a10_evidence_table.csv',index=False)
    a9s.to_csv(out/'a10_assumption_sensitivity.csv',index=False)
    a9tr.to_csv(out/'a10_free_running_transfer.csv',index=False)
    a7tr.to_csv(out/'a10_one_step_transfer.csv',index=False)
    provenance=pd.DataFrame([dict(stage=f'A{k}',archive=paths[k].name,sha256=sha[str(k)],bytes=paths[k].stat().st_size,zip_crc_ok=True) for k in range(5,10)])
    provenance.to_csv(out/'a10_archive_provenance.csv',index=False)
    claim_rows=[
      ('C01','Frozen NRI controller (30 min, 0.12) evaluated without external retuning','SUPPORTED_COMPUTATIONALLY','A5 manifest; A8 and A9 manifests','Frozen in-silico policy; not an operational deployment'),
      ('C02','External mean daily closed-cycle CSI2 reductions are positive','CONTRADICTED','A8 reconciliation; A9 reference rows','Both external point estimates are negative'),
      ('C03','External pooled closed-cycle CSI2 reductions are positive','SUPPORTED_COMPUTATIONALLY','A8 reconciliation; A9 reference rows','Aggregation-dependent; do not present as universal benefit'),
      ('C04','Positive improvement established with external statistical confidence','NOT_ESTABLISHED','A8 block-bootstrap CIs','Reported confidence intervals span zero; inspect CI fields'),
      ('C05','CSI2 improvement robust to half-cycle inclusion','CONTRADICTED','A8 reconciliation','Signs reverse in both datasets'),
      ('C06','One-step thermal model validates free-running counterfactual','UNSUPPORTED','A7 one-step; A9 free-running','One-step residuals are not intervention validation'),
      ('C07','Sensitivity scenarios quantify calibrated parameter uncertainty','UNSUPPORTED','A9 manifest','Arbitrary multipliers, not probability distributions'),
      ('C08','Physical fatigue or lifetime extension demonstrated','UNSUPPORTED','A9 gap register','No validated damage model or physical intervention measurements'),
      ('C09','Energy yield improvement demonstrated','UNSUPPORTED','A9 gap register','Irradiance proxy is not measured DC/AC energy'),
      ('C10','External 2018 systems remain untouched confirmatory holdouts','CONTRADICTED','A8 manifest','External data already inspected'),
      ('C11','A5 reference CSI2 reproducible across archived stages','SUPPORTED_COMPUTATIONALLY','A6/A7/A9 manifests and checks','Computational cross-check, not independent experimental validation')]
    claims=pd.DataFrame(claim_rows,columns=['claim_id','claim','classification','archived_evidence','qualification'])
    claims.to_csv(out/'a10_claim_to_evidence_matrix.csv',index=False)
    gap='''# A10 — Validation and publication readiness gaps\n\n1. **Physical intervention**: no measured detacked-versus-tracking trajectory or validated optical counterfactual.\n2. **Free-running transfer**: longer-horizon observational RMSE is materially larger than one-step error; no counterfactual ground truth.\n3. **Damage model**: closed-cycle CSI2 is an uncalibrated proxy; half-cycle inclusion changes the sign.\n4. **Energy**: modeled plane-of-array irradiance reduction is not measured electrical yield or actuator energy.\n5. **Statistical design**: externally inspected 2018 cohorts are exploratory; primary estimand was not demonstrably preregistered.\n6. **Data collection**: collect genuinely new matched/randomized tracking-versus-detacking observations with synchronized angles, irradiance components, temperatures, wind, and calibrated power.\n7. **Publication**: label this work exploratory and computational, report both external systems and all conflicting estimands, and disclose all A1–A9 exploratory analyses.\n'''
    (out/'a10_validation_and_publication_gaps.md').write_text(gap)
    lines=['# A10 — Evidence-constrained manuscript results','',
      '**Status:** Exploratory computational evidence consolidation; not physical validation.','',
      '**Frozen policy:** 30-minute NRI window and threshold 0.12. No optimization, refitting, or new statistical sampling in A10.','',
      '## External computational findings','']
    for _,r in main.iterrows():
        lines += [f"### {r.dataset}",f"- External days: {r.n_days}.",
          f"- Mean daily closed-cycle CSI2 reduction: {r.mean_daily_closed_pct:+.6f}% (archived block-bootstrap 95% CI [{r.mean_daily_block_CI_low:+.6f}, {r.mean_daily_block_CI_high:+.6f}]).",
          f"- Pooled closed-cycle CSI2 reduction: {r.pooled_closed_pct:+.6f}% (archived block-bootstrap 95% CI [{r.pooled_block_CI_low:+.6f}, {r.pooled_block_CI_high:+.6f}]).",
          f"- Mean daily CSI2 with half cycles: {r.mean_daily_with_half_pct:+.6f}% (archived block-bootstrap 95% CI [{r.mean_daily_with_half_CI_low:+.6f}, {r.mean_daily_with_half_CI_high:+.6f}]).",
          '- Aggregation and cycle-definition sensitivity: sign disagreement in both comparisons.','']
    lines += ['## Interpretation','',
      'A positive pooled percentage does not override a negative mean-daily percentage; they are distinct estimands. The externally inspected cohorts cannot support a confirmatory generalization. The reference full-cycle CSI2 uses an offline five-point centered median and squared full closed rainflow ranges. Neither physical thermal fatigue nor lifetime is established.','',
      '## Transfer and physical-model limitations','',
      'A7 one-step observational thermal errors cannot validate counterfactual controlled trajectories. A9 full-segment free-running observational errors increase with horizon, while optical and thermal coefficient perturbations are uncalibrated stress tests. No observed detacking interventions, measured electrical yield, or physical fatigue measurements are included.','',
      '## Suggested manuscript framing','',
      '**Working title:** Exploratory Transferability and Assumption Sensitivity of Irradiance-Ramp-Triggered PV Tracker Detacking: A Reproducible Computational Audit','',
      '**Scope:** Computational feasibility, external sensitivity, and reproducibility; not proven physical effectiveness.','',
      '## Reproducibility and provenance','',
      'All A5–A9 ZIPs passed CRC tests. A8 SHA-256 lineage agrees with supplied A5–A7 archives; A9 SHA-256 agrees with supplied A5 archive. A8 versus A9 reference daily and pooled metrics agree to tolerance 1e-8. A10 does not rerun the underlying A1–A9 algorithms.','',
      'See `a10_archive_provenance.csv`, `a10_claim_to_evidence_matrix.csv`, and `a10_validation_and_publication_gaps.md`.']
    (out/'a10_manuscript_evidence.md').write_text('\n'.join(lines)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    labels=['2018 System 1','2018 System 2A'];x=np.arange(2);w=.25
    fig,ax=plt.subplots(figsize=(9,5))
    ax.bar(x-w,main.mean_daily_closed_pct,width=w,label='Mean daily, full closed')
    ax.bar(x,main.pooled_closed_pct,width=w,label='Pooled, full closed')
    ax.bar(x+w,main.mean_daily_with_half_pct,width=w,label='Mean daily, full + half')
    ax.axhline(0,color='black',linewidth=.8);ax.set_xticks(x,labels);ax.set_ylabel('Modeled CSI2 reduction (%)');ax.legend(fontsize=8)
    ax.set_title('External estimand and cycle-definition sensitivity')
    fig.tight_layout();fig.savefig(out/'a10_figure_estimand_sensitivity.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,5))
    for ds,g in a9tr.groupby('dataset'):
        g=g.copy();g['sort']=g.horizon.map({'30':0,'60':1,'120':2,'full_segment':3});g=g.sort_values('sort')
        ax.plot(np.arange(4),g.mean_RMSE_C,marker='o',label=ds.replace('PV_temperature_model_data_2018_','').replace('_1min',''))
    ax.set_xticks(np.arange(4),['30 min','60 min','120 min','Full segment']);ax.set_ylabel('Mean free-running RMSE (°C)')
    ax.set_title('A9 observational free-running thermal transfer');ax.legend();fig.tight_layout()
    fig.savefig(out/'a10_figure_free_running_rmse.png',dpi=180);plt.close(fig)
    manifest={'status':'EXPLORATORY_COMPUTATIONAL_EVIDENCE_AUDIT_NOT_PHYSICAL_VALIDATION','selected_policy':policy,
      'archives_sha256':sha,'archive_crc_pass':True,'a8_lineage_pass':True,'a9_a5_lineage_pass':True,
      'a8_a9_reconciliation_pass':True,'external_days':int(main.n_days.sum()),'datasets':len(main),
      'max_a8_a9_reconciliation_difference':float(main[['a8_a9_daily_difference','a8_a9_pooled_difference']].to_numpy().max()),
      'no_retuning':True,'no_new_scientific_experiment':True,
      'limitations':['A10 validates internal archived consistency, not source-data truth or physical effect',
                     'Earlier stage methods and external data have already been inspected',
                     'Confidence intervals are archived calculations, not newly estimated in A10']}
    (out/'a10_manifest.json').write_text(json.dumps(manifest,indent=2))
    print('A10 RESULT',json.dumps(manifest,indent=2))
    print('\nA10 EVIDENCE TABLE\n',main.to_string(index=False))
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for k in range(5,10):p.add_argument('--a'+str(k),required=True)
 p.add_argument('--out',default='package_a10_outputs');main(p.parse_args())