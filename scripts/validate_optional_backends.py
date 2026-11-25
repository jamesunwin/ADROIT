"""Pinned upstream examples and explicitly separated reference comparisons."""
from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import tarfile
import sys

import numpy as np

import argparse
import importlib.util
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'audit/optional_backends'


def checked_reference(name: str) -> Path:
    """Bind a reference calculation to the manifest's pinned source revision."""
    from adroit.external import fetch
    from adroit.external.manifest import load_manifest
    item = load_manifest().item(name)
    folder = fetch.locate(name)
    if folder is None:
        raise RuntimeError(f'{name}: reference is not installed')
    actual = subprocess.run(['git','-C',str(folder),'rev-parse','HEAD'],
                            capture_output=True,text=True,check=True).stdout.strip()
    if not item.version or not actual.startswith(item.version):
        raise RuntimeError(f'{name}: installed revision {actual} differs from pinned {item.version}')
    path = OUT/'reference_revisions.json'
    revisions = json.loads(path.read_text()) if path.exists() else {}
    revisions[name] = {'actual_commit':actual,'manifest_pin':item.version,'path':str(folder)}
    save('reference_revisions',revisions)
    return folder


def module(path: str) -> ModuleType:
    """Load a repository reference driver without executing its main entry point."""
    spec = importlib.util.spec_from_file_location(Path(path).stem,ROOT/path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded

def save(name: str, value: Any) -> None:
    """Retain raw numerical evidence beside the comparison summary."""
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/f'{name}.json').write_text(json.dumps(value,indent=2,default=str))

def command(argv: list[str], cwd: Path = ROOT) -> None:
    """Run a checked reference build without shell interpolation."""
    subprocess.run(argv,cwd=cwd,check=True)



def nest() -> None:
    """Compare deterministic NR yields with the pinned upstream helper interface."""
    import nestpy
    from importlib.metadata import version
    calculator = nestpy.NESTcalc(nestpy.detectors.VDetector())
    rows = []
    for field in (124.,200.,500.):
        for energy in (1.,10.,50.):
            result = calculator.GetYields(nestpy.interactions.NR,energy,2.9,field,131.293,54)
            repeat = calculator.GetYields(nestpy.interactions.NR,energy,2.9,field,131.293,54)
            upstream = nestpy.helpers.get_yields_df(nestpy.interactions.NR,np.array([energy]),
                nest_calc=calculator,density=2.9,drift_field=field,A=131.293,Z=54)
            row = dict(energy_kev=energy,field_v_cm=field,photons=result.PhotonYield,
                       electrons=result.ElectronYield,lindhard=result.Lindhard,
                       upstream_photons=float(upstream.PhotonYield[0]))
            assert all(math.isfinite(row[k]) and row[k]>=0 for k in ('photons','electrons','lindhard'))
            assert result.PhotonYield == repeat.PhotonYield == row['upstream_photons']
            rows.append(row)
    save('nest',{'nestpy':version('nestpy'),'nest':nestpy.__nest_version__, 'rows':rows,
        'reference':'nestpy 2.1.1 upstream README GetYields / helpers.get_yields_df; interface consistency, not independent detector validation',
        'assumptions':'VDetector, liquid Xe 2.9 g/cm3, mean yields, A=131.293,Z=54, default NR parameters'})
    print('NEST 9 deterministic NR yields',flush=True)


def scatter() -> None:
    """Check archived spectra and independently computed matched recoil rates."""
    from adroit.external.reference_rates import dmscatter
    from adroit.core.dm_state import DarkMatterParticle, HaloModel, InteractionModel, OperatorCoefficient
    from adroit.physics import rates, targets
    from adroit.physics.conventions import AMU_GEV
    folder = checked_reference('dmscatter')
    work = OUT/'dmscatter'
    work.mkdir(exist_ok=True)
    with tarfile.open(folder/'test/data.tar.gz') as archive:
        archive.extractall(work,filter='data')
    rows = []
    # Before comparison: bulk agreement 5%, endpoint reported separately. Published
    # density models/rounded masses are retained; no calibration from ADROIT results.
    for op in (1,4,6):
        e, reference = dmscatter(folder,work,folder/'test/si29nb-iso.dres',14,29,{op:(1./246.2**2,0.)},high=270,
                                 controls={'ntscale':2500.})
        path = next(work.rglob(f'dmformfactor.vesc550.si29.p.{op}.{op}.dat'))
        energies, published = np.loadtxt(path,unpack=True)
        # DMFormFactor's archived rates are per GeV, same as dmscatter.
        ref = np.interp(energies,e,reference)*1e6
        bulk = (energies<200)&(published>max(published)*1e-10)
        error = float(np.max(abs(ref[bulk]/published[bulk]-1)))
        rows.append({'operator':op,'comparison':'archived upstream DMFormFactor Si29 proton',
                     'bulk_error':error,'pass':error<.05,
                     'endpoint_relative_errors':(ref[~bulk]/np.maximum(published[~bulk],1e-300)-1).tolist()})
    for op in (1,4,6):
        e,reference = dmscatter(folder,work,folder/'targets/F/f19w18.dres',9,19,{op:(1e-8,1e-8)},high=200,
                               controls={'mnucleon':AMU_GEV,'ntscale':.938272/AMU_GEV,'vescape':2000.})
        interaction = InteractionModel(name='reference',layer='nonrelativistic',coefficients=[
            OperatorCoefficient(operator=op,proton=1e-8,neutron=1e-8)])
        halo = HaloModel(rho_gev_cm3=.3,v0_km_s=220,v_esc_km_s=2000,
                         v_lsr_km_s=(0,232,0),v_peculiar_km_s=(0,0,0),v_earth_km_s=(0,0,0))
        mine = np.array(rates.differential_rate(e,DarkMatterParticle(mass_gev=150),interaction,
                                               targets.single_isotope('F19'),halo).rate)
        bulk = (reference>max(reference)*1e-4)&(e<100)
        error = float(np.max(abs(mine[bulk]/reference[bulk]-1)))
        rows.append({'operator':op,'comparison':'ADROIT vs upstream F19 Wildenthal USD, effectively untruncated Maxwellian (2000 km/s)',
                     'bulk_error':error,'pass':error<.05,'energies_kev':e.tolist(),
                     'adroit':mine.tolist(),'reference':reference.tolist()})
    save('dmscatter',rows)
    print('dmscatter',[(r['comparison'],r['operator'],r['bulk_error']) for r in rows],flush=True)
    assert all(r['pass'] for r in rows)


def capt() -> None:
    """Compare independent capture integrations with explicit unit conversion."""
    folder = checked_reference("Capt'n General")
    # Build a standalone caller, avoiding architecture-dependent ctypes imports.
    command(['gfortran','-O3','-fopenmp',str(ROOT/'scripts/captngen_reference.f90'),
             '-L'+str(folder),'-Wl,-rpath,'+str(folder),'-o',str(folder/'adroit_reference.x'),
             str(folder/'gencaplib.so')],folder)
    process = subprocess.run([str(folder/'adroit_reference.x'),
          str(folder/'solarmodels/struct_b16_agss09_nohead.dat')],cwd=folder,
          capture_output=True,text=True,check=True,timeout=600)
    (OUT/'captngen_stdout.txt').write_text(process.stdout+process.stderr)
    from adroit.constraints import capture
    from adroit.physics.conventions import AMU_GEV
    from adroit.core.dm_state import DarkMatterParticle,HaloModel,InteractionModel,OperatorCoefficient
    halo=HaloModel(rho_gev_cm3=.3,v0_km_s=220,v_esc_km_s=2000,
                   v_lsr_km_s=(0,220,0),v_peculiar_km_s=(0,0,0))
    rows=[]
    for line in process.stdout.splitlines():
        if not line.startswith('RESULT '):
            continue
        _,op,value=line.split()
        op=int(op)
        interaction=InteractionModel(name='reference',layer='nonrelativistic',coefficients=[
            OperatorCoefficient(operator=op,proton=1e-8,neutron=0. if op in (4,6) else 1e-8)])
        mine=capture.capture_rate(DarkMatterParticle(mass_gev=100),interaction,halo)
        # Upstream factor_final uses NAvo*rho/(mnuc*A), but rho is in g/cm3
        # and mnuc is in GeV. A GeV has 1/AMU_GEV g/mol: restore that unit
        # conversion, without adjusting a fitted coefficient or physics equation.
        from adroit.external.reference_capture import physical_capture_rate
        physical=physical_capture_rate(float(value))
        ratio=mine/physical
        rows.append(dict(operator=op,adroit=mine,raw_reference=float(value),reference=physical,
                         unit_conversion=AMU_GEV,ratio=ratio,passed=abs(ratio-1)<.05))
    save('captngen',dict(rows=rows,source_commit='59b55a4b31dc27e6d2435d588a6d72a463cb04ca',
        independence='independent upstream capture integration; shared B16 solar input and published Catena nuclear responses',
        assumptions='untruncated Maxwellian v0=220, sun=220 km/s, rho=.3 GeV/cm3, B16 AGSS09; mean dominant isotopes; 5% declared comparison tolerance; opercap factor_final NAvo*rho/mass_GeV converted using AMU_GEV (raw values retained)'))
    print('Capt',rows,flush=True)
    assert len(rows)==5 and all(r['passed'] for r in rows)
    capture_gate=module('docs/dm7/capture_check.py')
    capture_gate.ROOT=OUT
    (OUT/'docs/dm7').mkdir(parents=True,exist_ok=True)
    capture_gate.main()


def wimpy() -> None:
    """Exercise the registered checkout through the existing compatibility driver."""
    from adroit.external import setup
    ref=module('docs/dm2/reference_spectra.py')
    ref.WORK=OUT/'wimpy'
    ref.WORK.mkdir(exist_ok=True)
    # NumPy/SciPy are core dependencies; the existing driver supplies the
    # upstream's removed SciPy aliases. No audit-only environment is required.
    ref.PYTHON['wimpy']=Path(sys.executable)
    # Existing driver uses explicit registered checkout path, never PYTHONPATH.
    folder=checked_reference('WIMpy_NREFT')
    ref.EXTERNAL=folder.parent
    selected=[c for c in ref.cases() if c['name'] in ('O1 alone','O4 alone','O6 alone')]
    patched=ref.patch_wimpy(ref.WORK/'wimpy_exact')
    output=ref.run('wimpy',patched,selected,ref.HaloModel())
    errors=[ref.deviation(ref.ours(c),r,ref.bulk_mask(c,ref.HaloModel())) for c,r in zip(selected,output)]
    save('wimpy',dict(path=str(folder),setup=setup.run(only='WIMpy_NREFT')[0].model_dump(),bulk_errors=errors))
    assert max(errors)<.01
    print('WIMpy',errors,flush=True)


def preflight() -> list[str]:
    """What an offline run of ``main`` lacks, checked before any backend runs (the release checks skip the step
    only for these; the external audit of 2026-10-17, R17-9)."""
    import shutil
    from adroit.external import fetch
    missing = [f"the Python package {name} is not installed" for name in ("nestpy", "sentence_transformers")
               if importlib.util.find_spec(name) is None]
    try:
        from huggingface_hub import try_to_load_from_cache
        from adroit.retrieval.embeddings import _ST_MODEL_NAME, _ST_MODEL_REVISION
        if not isinstance(try_to_load_from_cache(f"sentence-transformers/{_ST_MODEL_NAME}", "config.json",
                                                 revision=_ST_MODEL_REVISION), str):
            missing.append(f"the embedding model {_ST_MODEL_NAME} is not in the local cache")
    except ImportError:
        missing.append("huggingface_hub is not installed")
    missing += [f"the reference {name} is not installed" for name in ("dmscatter", "Capt'n General", "WIMpy_NREFT")
                if fetch.locate(name) is None]
    if shutil.which("gfortran") is None:
        missing.append("gfortran is not on the PATH")
    return missing


def main() -> None:
    """Run all five optional capabilities and retain their numerical evidence."""
    from adroit.retrieval.embeddings import get_embedding_function
    q,related,unrelated=get_embedding_function('st')([
        'dark matter scattering off nuclei in a xenon detector',
        'WIMP nuclear recoil direct detection in liquid xenon',
        'the orbit of Jupiter around the Sun'])
    save('retrieval',{'related':float(np.dot(q,related)),'unrelated':float(np.dot(q,unrelated))})
    assert np.dot(q,related)>np.dot(q,unrelated)
    nest()
    scatter()
    capt()
    wimpy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=OUT)
    parser.add_argument('--preflight',action='store_true',help='only list what an offline run lacks')
    args=parser.parse_args()
    if args.preflight:
        lacking=preflight()
        print('; '.join(lacking) if lacking else 'available')
        sys.exit(3 if lacking else 0)
    OUT=args.out.resolve()
    OUT.mkdir(parents=True,exist_ok=True)
    main()
