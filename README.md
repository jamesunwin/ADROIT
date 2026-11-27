# ADROIT

**ADROIT helps researchers build dark matter models and compare them with experimental data.** It brings model construction, recoil-signal fits, relic-abundance calculations and experimental constraints into one local workbench. You can start with a model from the supplied library, enter your own model, or ask a language-model agent to help turn an idea into a candidate Lagrangian.

The numerical calculations use deterministic physics codes. Optional AI assistance helps prepare models and experimental inputs, find relevant literature and interpret results. You choose the question, review the inputs and decide what to investigate next.

ADROIT stands for **Agentic Dark matter Reinterpretation and Operator Inference Toolkit**. It is intended for researchers familiar with dark matter phenomenology; using the workbench does not require experience with language models or writing Python code.

**Start here:** [Install](#install-adroit) · [Open the workbench](#open-the-workbench) · [Try a first analysis](#try-a-first-analysis) · [Set up optional AI assistance](#optional-ai-assistance) · [Cite ADROIT](#citing-adroit-and-its-dependencies)

## What can I do with it?

| Your question | Where to start in the workbench | What you get |
|---|---|---|
| Can I turn this idea into a particle model? | **Model library → Create or refine a model** | Candidate fields, interactions and parameter values to inspect, edit and save. |
| Which parts of this model's parameter space survive the constraints? | **Constrain a model** | A parameter-space plot, thermal-relic solutions and comparisons with experimental constraints. |
| Which interactions could explain these recoil events? | **Signal best fits** | Ranked interaction hypotheses, fitted signal strengths and statistical comparisons. |
| Can a particular particle model explain this signal? | **Explain a signal** | Fits of the model's physical parameters, followed by relic-abundance and complementary-constraint checks. |

The workbench also supports personal model and experimental libraries, batches of calculations, and downloadable reports and evidence bundles. Results remain available under **Studies**.

**Do I need an API key?** No, for local physics calculations using existing models and inputs. You need a provider account and a key only for tasks that call a language model. Those calls are optional and have a monetary budget that you choose. Installing software or retrieving papers can still require an internet connection.

## Install ADROIT

These instructions are for **macOS or Linux**. ADROIT requires **Python 3.12**; the steps below install it for this project. Some external physics packages also need compilers or their own data files. Native Windows installation is not covered here; see the [installation guide](docs/installation.md) for platform details.

### 1. Open a terminal and install Git and uv

On a Mac, open **Terminal** from Applications → Utilities, or search for it with Spotlight. On Linux, open your terminal application. Paste each command below and press **Return**. Commands in these instructions are entered in the terminal, not in a Python interpreter or an AI chat.

First check whether Git, the tool used to download the repository, is installed:

```bash
git --version
```

If it prints a version, continue. On macOS, you can install Git through Apple's command-line tools:

```bash
xcode-select --install
```

Complete the installation dialog before continuing. For Linux or other installation methods, use the [official Git installation instructions](https://git-scm.com/install/).

Next install **uv**, which manages ADROIT's Python environment and dependencies. The official macOS/Linux installer is:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close and reopen the terminal if the installer asks you to, then check:

```bash
uv --version
```

Alternative installation methods are in the [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).

### 2. Download ADROIT

Choose a local folder whose path has **no spaces**: some external physics tools and executable scripts require this. The following creates a `research` folder in your home directory and downloads ADROIT into it:

```bash
mkdir -p "$HOME/research"
cd "$HOME/research"
git clone https://github.com/jamesunwin/ADROIT.git ADROIT
cd ADROIT
```

### 3. Install Python and the workbench

From inside the `ADROIT` folder, run:

```bash
uv python install 3.12
uv sync --python 3.12 --locked --extra ui
uv run adroit --help
```

The last command should print the available ADROIT commands. The installation creates a `.venv` folder containing this project's Python environment. You do not need to activate it manually: `uv run` selects it for you.

**On an Apple Silicon Mac**, use a native ARM installation of uv and Python. You can check with:

```bash
uv run python -c "import platform; print(platform.machine())"
```

It should print `arm64`. If it prints `x86_64`, see the [Apple Silicon instructions](docs/installation.md): an Intel Python running through Rosetta cannot run the xenon likelihood backend.

## Open the workbench

From the `ADROIT` folder, run:

```bash
uv run adroit workbench
```

A browser window should open. If it does not, visit **http://127.0.0.1:8765** yourself. This address is your own computer: the workbench runs locally, even though its interface appears in a browser. Keep the terminal open while using it.

You can now explore the forms and model library. No API key is needed to open the workbench. Before starting a calculation, install its required physics tools and datasets as described below.

When your calculations have finished, return to the terminal and press **Ctrl+C** to stop the workbench. To open it another day:

```bash
cd "$HOME/research/ADROIT"
uv run adroit workbench
```

If another application already uses port 8765, choose another local port:

```bash
uv run adroit workbench --port 8766
```

### Install the physics tools needed for your study

ADROIT uses external packages and experimental data for particular calculations. In a second terminal, enter the ADROIT folder and run:

```bash
cd "$HOME/research/ADROIT"
uv run adroit setup
```

This command lists what is installed, what is missing and how to obtain each item. It makes no downloads or paid AI calls. A fresh installation will normally have missing items; the command can report an unsuccessful status for that reason.

For an item that supports automatic installation, copy its exact name from the list. For example:

```bash
uv run adroit setup --fetch --only "DirectDM"
```

For items requiring a manual download or a compiler, follow the instructions printed by `setup`, then run it again to check the installation. **Install the items your analysis needs first.** Running `uv run adroit setup --fetch` without `--only` attempts all missing automatic items and may download substantial datasets or compile several research codes.

See the [installation guide](docs/installation.md) for compiler and platform requirements, and the [external-tool manifest](adroit/external/tools.yaml) for sources, versions and licences. A missing tool or dataset can leave a calculation unavailable or a result pending; it does not establish that a model is allowed.

## Try a first analysis

A library model is a useful starting point because it does not require AI model construction.

1. Open **Constrain a model** and select **A library model**.
2. Choose **Real scalar singlet (Higgs portal)**. Expand **Portal scan setup: active coordinates, fixed values and parameter relations** to inspect the scan.
3. Inspect the halo choice and the other assumptions. Leave the optional literature search off for a local calculation.
4. Check the required external inputs with `uv run adroit setup` and install any that are missing.
5. Press **Scan the portal**. Follow the run's progress, then open its study to inspect the plot, report and individual points.

A full physics scan can take minutes or hours, depending on the model, installed tools and computer; the first use of a backend may take longer. Opening the library and inspecting a setup does not start the scan. To list the available library models from the terminal, use:

```bash
uv run adroit portals
```

For signal analyses, start with **Signal best fits** or **Explain a signal**. Their **Check setup ($0)** button checks the requested calculation before you launch it. The [workbench guide](docs/workbench_guide.md) explains the choices in each form.

### Reading the result

ADROIT distinguishes points excluded by a constraint, points allowed within the checks performed, and points whose assessment is pending. The report gives the reason for a pending result, such as a missing input or a calculation outside the available method's scope. A parameter-plane conclusion also depends on whether the relevant region has been covered.

The **Studies** page lets you reopen a calculation. From its study page you can inspect a point, download numerical results and figures, or export an evidence bundle containing the saved inputs and outputs. See [inspecting and exporting studies](docs/workbench_inspection.md) and [evidence bundles](docs/evidence_export.md).

## Optional AI assistance

A language-model API lets ADROIT send a request directly to a provider such as Anthropic or OpenAI. You do not need to install their chat applications or write API code. You do need an **API key**, a private credential linking those requests to your provider account.

API billing is separate from a normal Claude or ChatGPT chat subscription. Check your provider's billing page before using it: [Anthropic billing](https://support.claude.com/en/articles/9876003-why-is-claude-api-usage-billed-separately-from-my-paid-claude-plan) and [OpenAI billing](https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform).

### 1. Obtain a key from the provider you want to use

**Anthropic / Claude**

1. Sign in or create an account at the [Claude Console](https://platform.claude.com/), and arrange API billing or credits there.
2. Open [Settings → API keys](https://platform.claude.com/settings/keys) and select **Create key**. Give it a recognisable name, such as `ADROIT`.
3. For personal use, choose a personal key scoped to one workspace; this works with ADROIT without an additional workspace header. Copy the secret when it is displayed.

See [Anthropic's authentication instructions](https://platform.claude.com/docs/en/manage-claude/authentication) for current account and key options.

**OpenAI**

1. Sign in or create an account at the [OpenAI API dashboard](https://platform.openai.com/), choose your project and arrange API billing.
2. Open [API keys](https://platform.openai.com/api-keys) and create a secret key for that project, with access to the models you intend to use.
3. Name it `ADROIT` and copy the secret when it is displayed.

See the [OpenAI API quickstart](https://developers.openai.com/api/docs/quickstart). ADROIT already includes the client software; no separate API tutorial or test request is needed to configure it.

You can configure one provider first. Select that provider's models in ADROIT. A workflow requesting an independent check from the other provider will need its key too.

### 2. Put the key in ADROIT's local settings file

The key belongs in a file named **`.env` in the main ADROIT folder**, beside `README.md` and `pyproject.toml`. It does not belong in a model description, a chat prompt or the `.venv` folder.

From the ADROIT folder, create the settings file from the supplied template and open it:

```bash
cp -n .env.example .env
chmod 600 .env
nano .env
```

The `-n` keeps an existing `.env` rather than replacing it. `chmod 600` restricts the file to your user account. `nano` is a terminal text editor; if it is unavailable, use a local plain-text editor and ensure the filename stays `.env`, not `.env.txt`.

Find the following entries in the file. Paste your own key directly after the corresponding `=`. Leave the entry blank for a provider you are not using:

```dotenv
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
```

Keep each key on one line, without spaces. In nano, press **Ctrl+O**, then **Return** to save, and **Ctrl+X** to exit. On a Mac these are **Control**, not Command, shortcuts.

After changing settings, restart the workbench when no calculations are running. Existing environment variables take precedence over `.env`, so an old key exported in your terminal can override the one you enter here.

Treat the key like a password: do not share it, include it in screenshots, or commit it to Git. The repository ignores `.env`, but the file is still plain text on your computer. You can check that it is ignored without displaying its contents:

```bash
git check-ignore .env
```

If a key is exposed, revoke it in the provider's console and create a replacement. During an AI request, the selected prompt and source material are sent to that provider; local storage of the key does not make those requests offline.

### 3. Try a budgeted model-building request

In the workbench, open **Model library → Create or refine a model**. Enter a short, specific idea, choose a model from a provider you configured, and set a dollar budget before submitting. For example:

> Construct a real scalar singlet dark-matter model with a Z2 symmetry and a Higgs-portal interaction. State the fields, interactions and parameter conventions.

The budget limits the paid work; it is not a fee charged in advance. The interface reports expenditure and stops when it cannot continue within the available budget. Inspect the proposed fields, interactions and assumptions before saving a model for calculations. Refinement and other AI-assisted steps may also incur charges.

## Your files and the scope of the calculation

By default, ADROIT stores calculations under `runs/`, personal model and experimental libraries under `projects/`, and downloaded data under `data/`. External research tools normally go in `~/agentic-dm-tools`. Keep these folders if you want to retain your work. The [installation guide](docs/installation.md) explains how to move them using `ADROIT_*` settings.

ADROIT's current physics scope centres on nuclear-recoil searches and thermal freeze-out dark matter, including supported coannihilation scenarios. Library models use dedicated calculations; other models are evaluated from their specified interactions where supported. Expert review remains necessary for the model assumptions and the applicability of an experimental constraint.

Constrain a model samples an SHM uncertainty region by default. Shared SHM and SHM++ choices are also available for model studies; see [halo assumptions and constraint support](docs/halo_constraint_support.md). Version 1.0 uses the nominal equation of state for freeze-out; the additional Saikawa–Shirai 2020 table-variation test is deferred and is not a prerequisite for a thermal conclusion. See [the EOS treatment](docs/eos_band.md).

The workbench is designed for local, single-user use. Import executable model files only from sources you trust. Before sharing a run or bundle, inspect it for private prompts or source material.

## Citing ADROIT and its dependencies

For a publication, cite ADROIT and the physics packages and experimental inputs used in your calculation. The repository's [bibliography](docs/dependencies.bib) contains an `ADROIT` entry and citations for the dependencies; the [citation guide](docs/citations.md) explains which to include. Study exports can also provide references for their recorded inputs.

Record the software version and the exact source revision used. You can obtain the latter from the ADROIT folder with:

```bash
git rev-parse HEAD
```

The current software citation is:

```bibtex
@misc{ADROIT,
  author = {Unwin, James},
  year = {2026},
  title = {{ADROIT: Agentic Dark matter Reinterpretation and Operator Inference Toolkit}},
  howpublished = {\url{https://github.com/jamesunwin/ADROIT}},
  note = {Version 1.0.0; report the version and commit used},
}
```

## Help and further reading

| If you need… | Start here |
|---|---|
| Installation, compilers, platform notes or API settings | [Installation guide](docs/installation.md) |
| A walkthrough of the forms | [Workbench guide](docs/workbench_guide.md) |
| Model construction, review and reuse | [Personal model library](docs/personal_model_library_and_intake.md) |
| Models from a paper's equation, and model property declarations | [Paper equations and model styles](docs/model_style_and_paper_intake.md) |
| Importing a limit or signal | [Experimental input guide](docs/experimental_interpretation_and_anomaly_intake.md) |
| Several calculations or an exported study | [Batches and bundles](docs/workbench_batches_and_bundles.md) |
| What was calculated at a point | [Inspecting studies](docs/workbench_inspection.md) |
| Scope and known limitations | [Release notes](docs/release_notes_v1.0.0.md), and what 1.0.1 changed ([1.0.1](docs/release_notes_v1.0.1.md)) |
| How it was validated and audited | [Validation and audits](docs/validation_and_audits.md) |
| Development history | [Changelog](CHANGELOG.md), [build record](docs/adroit_build.md) and [development guide](DEVELOPMENT.md) |

Common installation problems:

| What you see | What to do |
|---|---|
| `uv: command not found` | Reopen the terminal and follow the uv installer's PATH instructions. |
| A complaint about a missing `pyproject.toml` | Enter the ADROIT folder before running `uv run`. |
| Python 3.13 or another unsupported version selected | Repeat `uv sync --python 3.12 --locked --extra ui`. |
| A missing physics tool or dataset | Run `uv run adroit setup` and follow the named item's instructions. |
| Missing API credentials | Set the key for the selected provider in `.env`, then restart the workbench. |
| An API billing or access error | Check billing and model permissions in that provider's console. |
| Port 8765 is already in use | Start with `uv run adroit workbench --port 8766`. |

When reporting a problem, include the command or workbench action, the error message and the revision from `git rev-parse HEAD`. Remove credentials and private material before sharing a log.

ADROIT is distributed under the [BSD 3-Clause licence](LICENSE). External codes and datasets retain their own licences. The project began from the Nomothetica framework; its subsequent development and physics implementation are recorded in the linked build documents.
