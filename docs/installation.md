# Installing ADROIT and setting up optional API access

ADROIT's physics calculations run locally without an API key. Language-model
assistance is optional and uses your own provider account.

## 1. Install the prerequisites

Install Git and [uv using Astral's official instructions](https://docs.astral.sh/uv/getting-started/installation/).
The commands below use a macOS/Linux shell. The Python package requires **Python
3.12** (not 3.13); uv can obtain it for you. Native research backends have their
own platform and compiler requirements, described in the external-tool manifest.
Do not assume a Python installation alone installs every backend.

## 2. Obtain the code and create its environment

ADROIT v1.0.0 is installed from a clone of its repository only (decision D34): no wheel or PyPI package is
distributed. It reads files from the checkout at run time (`docs/dm3/validation_results.json`, the held-out ledger)
and writes to `runs/`, `projects/` and `data/` inside it by default (`ADROIT_RUNS_DIR`, `ADROIT_PROJECTS_DIR` and `ADROIT_DATA_DIR` move
them; `ADROIT_DATA_DIR` moves the manual external data, `data/external/manual`, too, and `adroit setup` names the
folder each item goes in). Making a wheel work would need those paths moved into package data or a user folder; that is deferred.
These settings, with `ADROIT_TOOLS_DIR`, `ADROIT_MODEL_LIBRARY_DIR` and `ADROIT_EXPERIMENTAL_LIBRARY_DIR`, may be
relative paths: each is read once, against the folder the command or the workbench was started in, and every run the
workbench launches (and resumes) is given the folders it read, whatever folder the run starts in.
`ADROIT_SCAN_WORKERS` sets how many processes a Track 1 scan evaluates its points in (by default the machine's cores
less two, at least one); a run's checkpoint does not depend on it.

Run these commands in a directory where you want to keep the project:

```bash
git clone https://github.com/jamesunwin/ADROIT.git
cd ADROIT
uv python install 3.12
uv sync --python 3.12 --locked
uv run adroit --help
```

Use your GitHub account's normal authentication if repository access requires it.
The `.venv` environment is local to this checkout. Run commands from this project
directory with `uv run`; no manual environment activation is needed.

Optional extras are `uv sync --locked --extra retrieval` for local semantic
embeddings, and `uv sync --locked --extra references` for the NEST reference.
Include both `--extra` flags if you use both: a later sync without an extra may
remove it. The development environment already includes the NiceGUI workbench.

**Intel Macs (x86_64).** Semantic retrieval is not available there. PyTorch
publishes no x86_64 macOS wheels after 2.2.2, which is built against NumPy 1.x,
and ADROIT needs NumPy 2 (`numpy.trapezoid`). So on an Intel Mac the `retrieval`
extra installs nothing, and literature retrieval keeps the deterministic hash
embedder (lexical rather than semantic matching). Everything else works the
same.

Checked on 2026-10-16 under an x86_64 Python on Apple Silicon (Rosetta, macOS 14; the closest test available
without Intel hardware): the locked environment installs, the fast suite passes (2,422 tests; one needs a git
checkout), and `adroit setup` names the problem below. DIAMX's dependencies install and its NEST extension builds for
x86_64, but JAX stops there for want of AVX. jaxlib 0.4.38, the version DIAMX's constraints pin, publishes x86_64
macOS wheels, so a real Intel Mac, which has AVX, should run it; that is untested.

**Apple Silicon with an x86_64 uv: do not.** A uv installed through an Intel
Homebrew (`/usr/local`) runs under Rosetta and chooses an x86_64 Python. ADROIT
installs, but DIAMX, which computes the xenon likelihoods, cannot run: its JAX
needs AVX instructions, which Rosetta does not provide (a real Intel Mac has
them). `adroit setup` warns when this is the case. Install uv natively, or pass
`--python cpython-3.12-macos-aarch64-none` to `uv sync`, and check with
`uv run python -c "import platform; print(platform.machine())"` (`arm64`).

## 3. Install the external codes and data needed for your calculation

```bash
uv run adroit setup
```

This lists each item, its availability, licence, destination and installation
instructions; it does not download anything. Install selected automatic items:

```bash
uv run adroit setup --fetch --only "Saikawa-Shirai relic cross sections (DM2020)"
uv run adroit setup --fetch --only "DirectDM"
uv run adroit setup --fetch --only "PPPC photon spectra"
uv run adroit setup --fetch --only "McDaniel dwarf likelihoods"
```

The first is Saikawa & Shirai's 2020 release (four small files): the s-wave
reference the relic density is validated against, and the equation-of-state
tables whose band ADROIT 1.0 does not assess (Ωh² uses the nominal 2018 fit;
propagating its uncertainty is deferred to 1.0.2: `docs/eos_band.md`). No
verdict needs them. They are fetched, not shipped, because their page states
no redistribution terms. The last two are
optional photon-spectrum inputs, not requirements for a minimal installation. Select detector releases and backends for the searches you will
use. `uv run adroit setup --fetch` attempts **all** missing automatic items and can
download large datasets or compile research codes. Start with selected items.
For manual items, follow the displayed author-download instructions and then run
`uv run adroit setup --only "EXACT ITEM NAME"` again to check their presence.

The authoritative list of versions, licences, sources and build instructions is
[`adroit/external/tools.yaml`](../adroit/external/tools.yaml). Automatic items
normally live in `~/agentic-dm-tools`; manual downloads use the locations printed
by setup. Compiled backends need a tools path without spaces. You can choose one
with `ADROIT_TOOLS_DIR` in `.env`. Follow the manifest's additional environment/
compiler notes for DIAMX, MadGraph/MadDM, micrOMEGAs and SModelS; some items need
those preparations before their build command can succeed.

Missing calculation inputs produce a missing-input or pending result where
supported; an unavailable backend does not imply that a model is allowed.

## 4. Check the installation and start the workbench

```bash
uv run pytest
uv run adroit setup
uv run adroit workbench
```

The first command runs the fast offline suite. Some reference checks require
their optional external inputs; inspect skip/missing-input messages. After the
relevant backends and data are installed, `uv run pytest -m slow` runs additional
local validation. Never run a protected DM10 held-out evaluation as an installation
check. The workbench prints its local address. A deterministic example is:

```bash
uv run adroit idea --fields docs/dm12/inert_doublet.yaml
```

## 5. Obtain API keys only if you want language-model assistance

### Anthropic

1. Open the official [Claude Console](https://platform.claude.com/) and sign in
   or create an account. Arrange API billing/credits in the Console; API access
   is separate from a Claude chat subscription.
2. In **Settings → API keys**, select **Create key**. For your own ADROIT use,
   create a personal key scoped to a single workspace. This works with ADROIT's
   current client without an extra workspace header. Choose an appropriate expiry.
3. Copy the secret when it is displayed. Keep it private and enter it in the
   local `.env` as described below.

Sources: [Anthropic authentication](https://platform.claude.com/docs/en/manage-claude/authentication),
[API billing](https://support.claude.com/en/articles/8977456-how-do-i-pay-for-my-claude-api-usage),
[API and chat subscriptions](https://support.claude.com/en/articles/9876003-i-have-a-paid-claude-subscription-pro-max-team-or-enterprise-plans-why-do-i-have-to-pay-separately-to-use-the-claude-api-and-console).

### OpenAI

1. Open the official [OpenAI API dashboard](https://platform.openai.com/) and
   sign in or create an account. Select the organisation/project for your work
   and arrange its API billing and usage controls.
2. Open [API keys](https://platform.openai.com/api-keys), create a secret key for
   that project, and choose permissions appropriate to your use.
3. Copy the secret when it is displayed and enter it in the local `.env`.
   ADROIT uses this key for workflows that request its OpenAI checker.

Sources: [OpenAI quickstart](https://developers.openai.com/api/docs/quickstart),
[production guidance](https://developers.openai.com/api/docs/guides/production-best-practices).
Console layouts and account permissions may change; use these official links.

## 6. Enter keys in the project's local `.env`

If `.env` does not already exist, copy the template **once**:

```bash
cp -n .env.example .env
chmod 600 .env
```

`chmod` is for macOS/Linux. Keep an existing `.env`; do not overwrite its settings.
Open `.env` in a trusted local text editor and fill only the providers you need:

```dotenv
ANTHROPIC_API_KEY=PASTE_YOUR_OWN_ANTHROPIC_KEY_HERE
OPENAI_API_KEY=PASTE_YOUR_OWN_OPENAI_KEY_HERE
```

These are placeholders, not working keys. Leave unused providers blank. After
obtaining keys from the official provider consoles, **strongly prefer entering
them only in this `.env` for ADROIT**. Never put them in code, notebooks, prompts,
workbench text fields, screenshots, emails, issue reports or shared documents;
never share them with collaborators or commit them to Git. Do not place `.env`
in a publicly shared or synced folder. `.env` is plaintext, not an encrypted
credential vault: protect access to your computer and backups. Revoke and replace
a key through its provider if it is exposed.

ADROIT reads this file locally through `adroit/core/config.py` (the `.env` of the
ADROIT project folder: the checkout, or the folder above the installed package);
`.gitignore` excludes it and any copy beside it (`.env.*`). There is no
ADROIT-hosted central key store. During a paid call, the provider SDK sends the key
to that provider for authentication over HTTPS, and the chosen prompt/source
material goes to that provider. Local storage does not mean paid requests stay
offline. Prompts and responses may also be saved in local provenance/cache files;
review run artifacts before sharing them.

The keys stay inside ADROIT (the security addendum of the audit loop's cycle 3,
2026-11-16):
- `.env` is read, never exported: no program ADROIT starts (a solver, a build, a
  fetched tool's script) is given a key or any other credential-named variable;
  ADROIT's own runs started from the workbench are given the provider keys alone.
- A key is used without the spaces or line breaks around it; one that still holds
  a space or a control character is refused, naming its variable only.
- The provider's own HTTPS endpoint is the only one used. If `ANTHROPIC_BASE_URL`
  or `OPENAI_BASE_URL` is set (in your environment, for another tool, or in
  `.env`) to anything else, ADROIT refuses to send there unless you allow that
  endpoint explicitly: `ADROIT_ALLOWED_ENDPOINTS=<the URL>` (comma-separated for
  several). The host a request goes to is shown beside its model and its cost.
- A command's error output never shows a configured key: its text is replaced by
  the variable's name.

A paid command whose provider has no key stops before anything is reserved against
its budget or sent, and names the variable to set; the key itself is never shown.

Existing process environment variables take precedence over `.env`. Avoid stale
exported credentials. Restart a running workbench or Python process after editing
keys because settings are cached for that process. You can check that Git ignores
the file without displaying its contents:

```bash
git check-ignore .env
```

## 7. Opt in to paid assistance with a budget

Keys do not enable paid calls by themselves. Select a workflow that explicitly
uses a language model and supply its dollar budget, for example:

```bash
uv run adroit idea --text "a scalar singlet with a Z2 symmetry" --budget 0.25
```

`--text` takes an idea in words, and needs `--budget` (dollars). The model
builder proposes up to `--models` field contents (4 by default). ADROIT then
builds each one's most general Lagrangian, audits it, and drops duplicates.
The builder is `claude-opus-5-5` by default; `--model gpt-5.6-sol` uses OpenAI.
Before each request is sent, the command shows the model, the hard cap and the
request's reserved cost. The run folder is `runs/idea_<name>/`, or `--out`. It
holds the report and, for each valid model, a typed model file
`models/<name>.yaml`; the report gives the `uv run adroit track1 …` command that
runs it. `--catalog-draft` also puts each valid model in the model catalog as an
unapproved draft. For a Lagrangian in words, use `--lagrangian-text "…"` in place
of `--text`.

This is a **paid example**, not an installation test; do not run it unless you
want that call. Check the chosen model, access and billing in your account first.
Provider usage controls complement ADROIT's per-command budget. A plain
`uv run adroit workbench`, typed-model calculations and offline tests need no API
key or paid call. No account creation, key generation or paid test is performed
by these written instructions.

## 8. Cite the complete calculation stack

Publications should cite ADROIT **and every research code/data source actually
used**, including validation and cross-check tools. MadDM, MadGraph, micrOMEGAs,
DirectDM, DIAMX, nuclear inputs and photon tables deserve credit in their own right.
Use the [README citation block](../README.md#citing-adroit-and-its-dependencies),
[dependency citation guide](citations.md), and [BibTeX file](dependencies.bib).
Report versions/commits and cite the experimental records behind your results.
