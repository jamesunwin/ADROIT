# Citing ADROIT, its dependencies and its data

Credit the full calculation chain: cite ADROIT and **every research code/data
source actually used**, including indirect dependencies, reference calculations
and validation/cross-check programs. Record versions/commits. Do not attribute a
component's precision, likelihood or physical method solely to ADROIT.

The [README](../README.md#citing-adroit-and-its-dependencies) provides a copyable
LaTeX block. Copy [dependencies.bib](dependencies.bib) into your paper project;
its keys match the block and the table below.
Use `\usepackage{hyperref}` or `\usepackage{url}` in a LaTeX preamble to render the
bibliography's source links. The ADROIT entry names the repository; add the
commit or release used in your manuscript.

## Complete external-tool and data manifest

The following covers every item in [tools.yaml](../adroit/external/tools.yaml),
including optional and validation-only tools. Presence in this table does not mean
that a default run executes every tool: choose the references used by your study.
The current role/version and licence come from the manifest and setup output.

| External item | Role | BibTeX keys |
|---|---|---|
| WIMpy_NREFT | test reference | `WIMpyNREFT` |
| WimPyDD | test reference | `WimPyDD2021`, `WimPyDD2022` |
| DirectDM | dependency | `DirectDM2017` |
| DIAMX | dependency (the xenon likelihoods) | `DIAMX2025` |
| XENONnT SR0+SR1 WIMP data release | validation reference | `XENONnT2025` |
| LZ WS2022+WS2024 spin-dependent limits (HEPData) | validation reference | `LZ2024` |
| Elastic density matrices (Haxton & McElvain) | data (nuclear density matrices) | `Elastic2022` |
| Mu2e nuclear-response scripts (Berkeley-Electroweak-Physics) | dependency (run in its own environment, <tools>/.venv-mu2e) | `Mu2eScripts` |
| DDCalc | cross-check | `DDCalc2017` |
| dmscatter | test reference | `Dmscatter2022` |
| NEST | optional dependency | `NEST2011` |
| Semantic retrieval | optional dependency | `SentenceBERT2019` |
| Capt'n General | reference (ADROIT computes capture itself; only Capt'n General's copy of the B16 solar model is used, as its own data item) | `CaptGeneral2021` |
| MadGraph5_aMC@NLO | dependency (numerical cross-check) | `MadGraph2014` |
| MadDM | dependency (numerical cross-check) | `MadDM2014`, `MadDM2015`, `MadDM2019`, `MadDM2023` |
| RAPIDD (MadDM's vendored copy) | dependency of MadDM | `RAPIDD2018` |
| GNU Scientific Library | dependency of RAPIDD | `GSL` |
| InertDoublet_UFO | model | `InertDoublet2013`, `InertDoublet2015` |
| Pseudoscalar_2HDM | model | `TwoHDMa2017`, `TwoHDMa2019` |
| PPPC photon spectra | theory data | `PPPC2011`, `PPPCWeak2011` |
| McDaniel dwarf likelihoods | experiment data | `McDaniel2024`, `FermiSEDData` |
| LZ extended window (arXiv:2609.02823) | experiment data | `LZ2026` |
| CRESST-III data release (arXiv:1905.07335) | experiment data | `CRESST2019`, `CRESSTData2019` |
| CDMSlite Run 2 data release (arXiv:1707.01632) | experiment data | `CDMSlite2018` |
| Optimum interval code (Yellin) | dependency | `Yellin2002`, `Yellin2007` |
| B16 standard solar model (AGSS09) | data | `B16Solar2017` |
| DarkCast | experiment data | `DarkCast2018`, `DarkCast2021` |
| Slatyer f_eff | experiment data | `Slatyer2016` |
| PDG R ratio | experiment data | `PDG2022`, `HadronicCompilation2004` |
| CCFR trident (digitised) | experiment data | `Trident2014`, `TridentDigitisation2025` |
| SModelS | dependency | `SModelS2023`, `SModelSv32024`, `SModelSv22022`, `SModelSPyhf2021`, `SModelSv122020`, `SModelSv112018`, `SModelS2014` |
| LHC SUSY cross sections | experiment data | `SUSYXsec`, `NNLLFast2024`, `Resummino2024` |
| micrOMEGAs | cross-check | `Micromegas2026`, `Micromegas2024` |
| Higgs Cross Section Working Group YR4 (BSM, 13 TeV) | theory data | `HiggsYR42017` |
| MadGraph production tables | theory data | `MadGraph2014`, `DMForum2015`, `DMWG2017`, `DMsimp2015`, `NNPDF23` |
| PDF4LHC21_40 (LHAPDF grid) | theory data (record derivation: the dilepton recast's LO σ; the twist-2 moments) | `PDF4LHC21`, `LHAPDF6`, `parton` |

MadDM's four entries follow its authors' installed `CITATION.bib`; retain all four
when its cross-check is used. SModelS likewise requests its seven code papers;
these are included following its [author citation guidance](https://smodels.github.io/).
Its separate `database.bib` supplies analysis citations. Cite pyhf/Pythia/Fastlim
or other additional packages when the specific calculation actually uses them. Inert-doublet and 2HDM+a papers credit the published
UFO models. The SUSY table reference supplements, rather than replaces, the
calculation actually used (for example NNLL-fast or Resummino). The external
production manifest identifies MadGraph, DMsimp and the PDF inputs; cite those too.
Capt'n General's code and its distributed B16 data are separate contributions:
using the solar table does not mean ADROIT used that code to compute capture.

The bibliography's arXiv metadata were retrieved from the primary arXiv API on
2026-10-07. Preprint entries use their arXiv date, title/authors and DOI where
provided; their short keys are identifiers, not publication-year guarantees.
MadDM's author-supplied journal records and the published McDaniel DOI are retained.
Software/data items with no paper supplied are explicitly cited as repositories
or datasets, without invented article details. Check author citation instructions
for your installed release, especially when replacing a pinned dependency.

## Scientific Python and application infrastructure

The scientific foundations are NumPy (`NumPy2020`), SciPy (`SciPy2020`), SymPy
(`SymPy2017`), Matplotlib (`Matplotlib2007`), NetworkX (`NetworkX`) and Astropy
(`Astropy2013`, `Astropy2018`, `Astropy2022`). Author guidance is available at
[NumPy](https://numpy.org/citing-numpy/), [SciPy](https://scipy.org/citing-scipy/),
[SymPy](https://docs.sympy.org/latest/citing.html),
[Matplotlib](https://matplotlib.org/stable/project/citing.html) and
[Astropy](https://www.astropy.org/acknowledging.html).

The direct Python dependency inventory is [pyproject.toml](../pyproject.toml);
[uv.lock](../uv.lock) records exact and transitive versions. Application support
also includes Pydantic, ChromaDB, ONNX Runtime, PyYAML, Typer, python-dotenv,
Requests, SQLModel, arxiv.py, pypdf, markdown-it-py, and the Anthropic/OpenAI Python
SDKs. NiceGUI provides the workbench; pytest and Ruff support development.
Optional sentence-transformers/NEST and their dependencies are separately selected.
These packages are acknowledged as software infrastructure, not presented as
independent dark-matter analyses. Use the individual project references below
where their contributions matter to your publication; keep the lock/version
inventory with your reproducibility material.

## Physics methods and experimental sources

Cite the methods underlying any implementation as well as the programs. The
NR-response framework is credited by `DMFormFactor2014` and
[related_work.md](related_work.md). Each curated constraint names its paper,
figure/table, assumptions and human verification. Cite every record/data release
used in a published result, including digitisation authors, not merely the few
example experiments in the README. The HEPData record for LZ's extended window is
[doi:10.17182/hepdata.182472](https://doi.org/10.17182/hepdata.182472).
Citation/acknowledgment is separate from licence permission and record verification.

## The generic route's physics sources (G0–G12)

The generic route computes from a model's own Feynman rules, but several of its pieces are other authors'
calculations, reimplemented or read from their tables. Cite them when a result uses them (the record of each
milestone, `docs/g1_mass_basis.md` to the G12 closure record, says where):
- **DMγSpec** (Beneke, Urban & Vollmann, arXiv:2203.01692; GPLv3, installed by the user in the tools folder and
  never imported): the resummed γ-ray lines of a pure wino or higgsino;
- **the endpoint resummation** of `constraints.endpoint_nll`: Baumgart et al., arXiv:1808.08956 (the wino) and
  arXiv:2309.11562 (any odd n-plet, the quintuplet), with the NLO potential of Beneke, Szafron & Urban,
  arXiv:1909.04584;
- **electroweak multiplets:** the one-loop splitting of Cirelli, Fornengo & Strumia (hep-ph/0512090); the s-wave
  rates of Cirelli, Strumia & Tamburini (arXiv:0706.4071); the Sommerfeld potential of Hisano et al.
  (hep-ph/0412403); the thermal relics and direct detection of Bottaro et al. (arXiv:2107.09688, arXiv:2205.04486);
- **bound states:** Mitridate, Redi, Smirnov & Strumia (arXiv:1702.01141; W and B emission); Harz & Petraki
  (arXiv:1805.01200) and Garny & Heisig (arXiv:2112.01499; colour); von Harling & Petraki (arXiv:1407.7874) and
  Petraki, Postma & Wiechers (arXiv:1505.00109; a dark U(1)); coloured coannihilation as in De Simone, Giudice &
  Strumia (arXiv:1402.6287);
- **DarkCast's ε convention** (D29): a dark photon couples as ε e(0) Q, the convention of DarkCast (cited above).

These are listed by arXiv identifier; their BibTeX entries are not yet in `dependencies.bib` and should be taken
from the arXiv record.

## Suggested acknowledgment wording

> This work used ADROIT to connect deterministic dark-matter calculations,
> experimental likelihoods and validation codes. We acknowledge and cite the
> authors of every underlying code and data release used, including reference
> and cross-check calculations, and report their versions and sources separately.

When optional language-model assistance is used, also report its provider/model,
role and cost. All physical numbers continue to come from deterministic code.
Do not include credentials in a manuscript, supplementary material or shared run.

### Direct Python dependency project links

- [pydantic](https://github.com/pydantic/pydantic)
- [numpy](https://numpy.org)
- [astropy](https://www.astropy.org/)
- [scipy](https://scipy.org/)
- [sympy](https://github.com/sympy/sympy)
- [matplotlib](https://matplotlib.org)
- [anthropic](https://github.com/anthropics/anthropic-sdk-python)
- [chromadb](https://github.com/chroma-core/chroma)
- [onnxruntime](https://onnxruntime.ai/)
- [networkx](https://networkx.org/)
- [pyyaml](https://pypi.org/project/pyyaml/)
- [typer](https://github.com/fastapi/typer)
- [python-dotenv](https://github.com/theskumar/python-dotenv)
- [requests](https://github.com/psf/requests)
- [sqlmodel](https://github.com/fastapi/sqlmodel)
- [arxiv](https://github.com/lukasschwab/arxiv.py)
- [pypdf](https://github.com/py-pdf/pypdf)
- [openai](https://github.com/openai/openai-python)
- [markdown-it-py](https://github.com/executablebooks/markdown-it-py)
