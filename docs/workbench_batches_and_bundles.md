# The workbench's batch queue and bundle viewer (the batch plan's §7, 2026-10-20)

## Batches (`/batches`)

Several requests run one after another, each as its own run with its own folder, log, live view and budget.

1. On a wizard's page (Constrain a model, Signal best fits, Explain a signal, Add a signal) turn on **"Add to the batch
   instead of running now"** and prepare the request as usual: its folder and inputs are written, and instead of
   starting it joins the **draft**. A paid request still asks for its budget now, as a run would.
2. On **Batches**, the draft lists the requests (each removable). **Start the batch**: name it and, if any request is
   paid, confirm the batch's total (the sum of its requests' budgets).
3. The batch's runner, detached like a run's, starts each request through the ordinary launch (its job file, its lock
   and its budget gate: no request spends more than was confirmed for it) and waits for it to finish before the next.
   A failed request does not stop the batch. The page shows each request's status and links to its live view; the
   batch continues when the workbench is closed.
4. **Cancel** stops the running request (as its own Cancel would) and marks the rest cancelled.

Files: `<runs>/.adroit/batch_draft.json` (the draft) and `<runs>/batches/<folder>/batch.json` (a batch); the logic is
`adroit/ui/batch.py`, the pages `adroit/ui/batch_page.py`.

## Open a bundle (`/bundle`)

An exported evidence bundle (a study's Downloads, "the evidence bundle") checked read-only: whether its files agree with
their recorded hashes, what that does and does not show ("internally consistent; provenance not verified"), the
saved decisions it holds, any issue, and whether reproduction was checked. Nothing is run or written. Give the
bundle's file or folder, or open `/bundle?path=…`.

## The batch audit's repairs (B20-01, B20-02; 2026-10-20)

- **A confirmation binds the requests it confirmed.** Starting a batch freezes its approval: each request's command
  (its sha256) with the budget its command line gives, recomputed from the command (never taken from the draft's
  numbers), and the total the person confirmed. The approval's sha256 goes to the runner on its command line from the
  confirming process. Before each launch the runner checks the approval and the request's command against it.
  - A request edited after confirmation is not launched (failed: "confirm a new batch").
  - A batch whose approval was edited is refused.
  - A command giving `--budget` twice is refused (`engine.paid`; the command line takes the last option), as is a
    budget that is not finite or is negative.
- **One runner, and recovery.**
  - The runner holds the batch's lock for its life: a second runner stops at once (`RunnerBusy`).
  - A runner restarted over an item marked running follows that item's own job to its end.
  - A request whose folder already holds the approved command's job is that job; any other job there fails the item,
    untouched.
  - A batch is completed only when every item has a final status, else interrupted.
  - A batch whose runner died is shown interrupted and resumes only with a new confirmation (`batch.resume`, the
    page's Resume).
  - The batch's file is replaced whole.

## The recheck's repairs (RB20-01, RB20-02; 2026-10-20)

- **A confirmation launches each request once.** The approval also names the batch's own folder and each request's
  folder, so two batches never share one. Before launching a request the runner records it in the batch's ledger
  (`dispatched.json`, under the batch's lock), and the job it launches records its owner (the batch and the item).
  - A request already in the ledger is not launched again: it is followed to its end through the job its batch
    launched for it (under any of the batch's confirmations), else failed, needing a new confirmation.
  - A request moved to another folder after confirmation is not launched (failed).
  - A completed or cancelled batch is never run again; another batch's job in a request's folder fails the item.
- **A launch that never started its run.** A launch closes its job ("the launch failed before its run started") if it
  fails on the way; a job whose run has not recorded its process 60 s after the job's start is closed by
  `engine.poll` ("launch not confirmed", RC20-02 below), and is not launched again. A run that starts late finds its
  job closed and does nothing; one cancelled before it starts records the cancel. A recovered batch then goes on to
  its next request.

## The auditor's repairs (RC20-01, RC20-02; 2026-10-20)

- **The run is the command its launch confirmed.** The launching process hands the runner the command's sha256 on the
  runner's command line (`python -m adroit.ui.runner FOLDER SHA256`), never read back from `job.json`; just before
  running, under the job's lock, the runner refuses a job whose command differs (an edited budget included) or that
  came without a confirmation, and starts nothing ("refused: the job's command is not the one its launch confirmed").
- **A record the batch cannot roll back.** Each dispatch is also appended to the runs folder's ledger,
  `<runs>/.adroit/dispatches.jsonl`, whose path the approval freezes (its digest covers it); a request found in either
  record is not launched again, so emptying `dispatched.json`, removing the finished job and requeueing the item no
  longer dispatches an approval twice.
- **Starting is acknowledged within a bound.** A job's run records its process within 60 s of the job's start, or the
  job is closed, whatever process now holds the launcher's PID (a bare PID can be reused); a resume that fails to start
  its run closes the job with the reason, and the job can be resumed again. Nothing ever starts a command again on its
  own.
- **The trust boundary.** These records protect against crashes, restarts, concurrent runners and a batch's or job's
  own files changing; a person editing every record by hand (the batch, its ledger, the runs folder's ledger and the
  job) is outside it.

## The candidate audit's repairs (C21-05, C21-06; 2026-10-21)

- **The command checked is the command run.** The runner checked the confirmed sha256 and then ran the command it
  read back from `job.json` when recording its process, so an edit landing in between ran ($5 under a $0.50
  approval). It now keeps its own copy of the command it checked, refuses the job if the file's command differs once
  it has recorded its start, runs only its copy, and ends by writing that command and its budget back to the job.
- **A spawned process is not a start.** The launcher records the spawned process's PID at once, and the 60 s bound
  applied only while the PID was 0, so a live process that never started its run kept the job running for ever. The
  runner now acknowledges its start on the job (`acknowledged`, under the job's lock); without it the job is closed
  after 60 s by `poll`, whether or not the spawned process lives, and by the runner itself if it reaches the job
  late, so a late run dispatches nothing. An acknowledged job's process alone decides; a job written before
  acknowledgements keeps the old rule. A spawned process past its bound is not killed (its PID could have been
  reused); finding its job closed, it does nothing.

## The recheck's repair (RC21-05; 2026-10-22)

- **A batch whose runner never starts is recoverable.** `start` saved the batch as running and emptied the draft
  before spawning its runner; a spawn that failed left it running for ever (PID 0), its resume refused and its cancel
  unfinished. Now a failed spawn leaves the batch interrupted with the reason, its requests kept, resumable with a new
  confirmation; the runner acknowledges its start on the batch (`acknowledged`), and without that acknowledgement
  within 60 s the batch is interrupted when the batches are listed, and by a late runner itself, which then runs
  nothing (a runner runs only a running batch: an interrupted one only through resume's new confirmation). Cancelled
  with no runner holding it, the batch closes at once: a running request's job is asked to stop, the queued ones are
  cancelled. The one-use dispatch records are unchanged, so recovery never sends an approved request twice.

## The re-audit's repair (RR22-04; 2026-10-22)

- **An acknowledged runner that dies is noticed.** The runner records its own process with its acknowledgement, and
  an acknowledged running batch that no runner holds (the runner holds the batch's lifetime lock from its
  acknowledgement to its final status) is interrupted when the batches are listed, whatever process holds its PID:
  a runner that died after acknowledging, its launcher dying before it recorded the PID, had left the batch running
  for ever. The batch's state is read again under its lock before it is changed, so a runner's final status is never
  overwritten. It resumes with a new confirmation; the one-use dispatch records still prevent a second dispatch.
