# The usability and timing sessions: the protocol (R-24)

R-24 of the G12 closure record, signed by the owner on 2026-10-16: the sessions run after the release
and before any announcement or paper submission. **Not run** (the owner, 2026-10-22): the sessions are skipped, now
and later, unless the owner asks for them; neither the release, an announcement nor a paper waits on them. The kit
below is kept as it was, with its keys' commitment, should they ever be run. This kit was built beforehand (the
batch plan's §8). It contains:
- this protocol;
- the tasks ([`tasks.md`](tasks.md); the statements given to participants are in `tasks/`);
- the answer keys, kept outside the repository ([`keys_commitment.md`](keys_commitment.md) holds their sha256);
- an opt-in command log;
- the analysis, `adroit assist-session report`.

The sessions themselves need participants and are the owner's.

## 1. The question

Does ADROIT save a researcher's effort on representative dark-matter phenomenology tasks, at the same quality, and
is it simple to use? R12 of the release plan names efficiency and simpler interaction as the
handoff's primary aims, unmeasured so far. Nothing here measures whether ADROIT's physics is right. The validations,
the gates and the audits do that.

## 2. The design

- **Paired, within participant.** Each participant does each task twice on the same input: once in the **manual**
  condition (their usual tools: papers, their own code, micrOMEGAs, a spreadsheet; no ADROIT) and once in the
  **assisted** condition (ADROIT, the CLI or the workbench, with whatever else they want).
- **Counterbalanced.** Doing a task the second time is faster whatever the tools. To balance this, half the
  participants start each task in the manual condition and half in the assisted, assigned by the order of
  enrolment: odd-numbered participants start manual on T1 and T3, assisted on T2 and T4; even-numbered the reverse.
  The two conditions of one task are at least a day apart.
- **Participants.** At least four, so that each order has at least two. They are researchers who could do the
  tasks manually (graduate students or above in particle or astroparticle physics), not ADROIT's developers. Each
  has a pseudonymous label (P01, P02, …), the only identifier in any file. Before the assisted sessions, each gets
  the same 20-minute introduction: the README's "Install and check", "The two paths" and "The two tracks", and the
  workbench's home page; nothing task-specific.
- **Consent.** Each participant agrees in writing to take part and may stop at any time; their files are deleted on
  request. Before recruiting, the owner checks with UIC's IRB whether this needs its review. An evaluation of
  software by colleagues is often judged not to be human-subjects research, but that determination is the IRB's.
  The owner (2026-10-22): the study does not need IRB review.

## 3. The tasks

Four tasks, one for each of ADROIT's main routes ([`tasks.md`](tasks.md)):
- T1, a limit for a non-standard coupling (Path 1);
- T2, what explains an excess (Path 2);
- T3, the most general Lagrangian of a field content (the model front end);
- T4, a thermal model's verdict (Track 1).

Each task has:
- a fixed statement (`tasks/T<n>.txt`, whose SHA-256 is the session's input hash);
- a quality bar;
- a key, fixed before the first session.

The keys are not shown to participants: they are not in the repository, and participants get `tasks/` only.

## 4. Measures

- **Primary: active effort**, self-timed with the existing paired timer: `adroit assist-session start`, then
  `mark … pause` and `mark … resume` for breaks, and `mark … finish --attest --success/--unsuccessful`. Paused time
  is excluded. Waiting on a calculation is counted, since the researcher is waiting. The participant attests that
  the timed effort is their own work.
- **Quality.** The researcher running the session, not the participant, compares the answer with the key and the
  bar, and records `--success` or `--unsuccessful` at finish.
- **The System Usability Scale** (Brooke 1996): ten statements answered 1 (strongly disagree) to 5 (strongly
  agree), once per participant after their last assisted session. The standard wording is below (§8).
- **Optional: the command log.** With `ADROIT_USAGE_LOG=<file>` and `ADROIT_USAGE_SESSION=<label>` set (the label
  as `P03-T2-assisted`), each `adroit` command, including the workbench's runs, appends one line: its name, start,
  duration and whether it ended in an error. It never records arguments, paths, inputs or outputs, and records a
  label only in the protocol's form `Pnn[-Tn[-condition]]` (`adroit/evaluation/usage_log.py`; any other label, a
  name above all, is left out). It is off unless set. It shows where the assisted time went.
- **Cost:** an assisted session's API spend, recorded with `--assistance-result` when an agent was used. The report
  totals every assisted session's, paired or not, failed or not.

## 5. Procedure, per session

1. The session's researcher sets up the condition and gives the participant `tasks/T<n>.txt`.
2. Start the timer:
   `uv run adroit assist-session start sessions/P03_T2_assisted.json P03 T2 <sha256 of tasks/T2.txt> assisted`.
3. The participant works, pausing the timer for any break. In the assisted condition, optionally with
   `ADROIT_USAGE_LOG=usage/P03.jsonl ADROIT_USAGE_SESSION=P03-T2-assisted` in the environment.
4. On the participant's answer, the researcher checks it against the key and finishes:
   `uv run adroit assist-session mark sessions/P03_T2_assisted.json finish --attest --success`.
   An answer that misses the bar is `--unsuccessful`, recorded, never retried in the same condition.
5. After the participant's last assisted session, the SUS. Its ten answers go in `sus.json` as
   `{"participant": "P03", "answers": [...]}`.

## 6. The analysis (declared before any session)

`uv run adroit assist-session report sessions --sus sus.json --usage usage/P01.jsonl … --out report.md`
(`adroit/evaluation/usability.py`) runs the analysis.

- **Effort saved**, per pair: the manual active seconds minus the assisted. A pair counts only when there is exactly
  one session per condition for that participant, task and input, counted before any quality filter, so that a failed
  attempt and a retry are a repeat, excluded, not a pair. Both sessions must also be finished, attested and
  successful. This is the rule of `assistance_timing.summarize`, applied task by task. Every session left out is
  named with why.
- **Reported:**
  - each task's pairs and their median;
  - the median and quartiles over all pairs (descriptive);
  - each participant's mean saving over their paired tasks;
  - each condition's success rate ("k of n" finished and attested);
  - each participant's SUS score and the median;
  - the command logs;
  - the API cost of every assisted session.
- **The test:** on participants, the independent units, not on their tasks. Each participant's mean saving over their
  paired tasks is one observation. With six or more participants: the Wilcoxon signed-rank test, two-sided. Below
  six, descriptive only: with five or fewer no two-sided p-value can fall below 0.05. A test for one task alone would
  need six participants with that task paired. (Corrected before any session, after the batch audit's B20-06: the
  first draft had tested all pairs together, a participant's four tasks as four independent units.)
- **Nothing is imputed or dropped after the fact.** Every session is counted. One left out of the time comparison
  is named with why. A miss is reported as a miss.
- **The claim it supports:** the paired effort of these participants on these tasks. It is descriptive, not a
  population estimate. A small sample is said to be small.

## 7. The report

The report is `report.md` from the command above. Add:
- the participants' backgrounds, in words, without names;
- the dates;
- the ADROIT commit;
- any deviation from this protocol.

It goes in `docs/usability/` with the session files only if every participant agrees to that. Otherwise only the
report goes there.

## 8. The System Usability Scale (Brooke 1996), as given

Answer each from 1 (strongly disagree) to 5 (strongly agree), about ADROIT:

1. I think that I would like to use this system frequently.
2. I found the system unnecessarily complex.
3. I thought the system was easy to use.
4. I think that I would need the support of a technical person to be able to use this system.
5. I found the various functions in this system were well integrated.
6. I thought there was too much inconsistency in this system.
7. I would imagine that most people would learn to use this system very quickly.
8. I found the system very cumbersome to use.
9. I felt very confident using the system.
10. I needed to learn a lot of things before I could get going with this system.

The score: odd items (answer − 1), even items (5 − answer), the sum times 2.5, so 0 to 100 (`usability.sus_score`).
