# The usability tasks (R-24)

The four tasks of the [protocol](protocol.md). Give a participant only the statement in `tasks/`; its SHA-256 is
the session's input hash. If a statement changes, its hash changes, and sessions on the old and new statements do
not pair. The keys and bars are kept outside the repository; [`keys_commitment.md`](keys_commitment.md) holds their sha256.

| task | ADROIT's route | statement | SHA-256 of the statement |
|---|---|---|---|
| T1 a limit for a non-standard coupling | Path 1 (`adroit exclude O1` with `c_n = 0`) | [`tasks/T1.txt`](tasks/T1.txt) | `9cd98b7ab00f8142adb4254bdd941ea5e8611f41cd6c39d1a9ce83689806c035` |
| T2 what explains an excess | Explain a signal (`adroit single-idea`), Signal best fits (Path 2) | [`tasks/T2.txt`](tasks/T2.txt) | `3b6c2030309f809fee3fe2d7f97a1c8b790bdac8904815b9df6c8aa2deb255b2` |
| T3 the most general Lagrangian | Track 1's front end (`adroit idea --fields`) | [`tasks/T3.txt`](tasks/T3.txt) | `0da17963eeb280488ba250c9dda75c5e27ebd1e6f4464d28f627f0c439ea76d8` |
| T4 a thermal model's verdict | Track 1 (`adroit track1 --portal higgs_portal_vector`) | [`tasks/T4.txt`](tasks/T4.txt) | `8085af8016c59953a4b34323e346864c60252c4aca79f8deae1a88f43249ca8d` |

Why these four:
- they cover ADROIT's main routes;
- each has an answer a physicist could reach without ADROIT in an afternoon or a day;
- each answer can be checked against a key from outside ADROIT, or by hand.

The manual route for each:
- T1: rescale LZ's published isoscalar limit by the xenon isotopes' ⟨A²⟩/Z²;
- T2: read the paper, or fit the three events;
- T3: enumerate the invariants by hand;
- T4: micrOMEGAs or an estimate of the relic coupling, then the direct-detection cross-section against LZ.

ADROIT does each in a few commands. Whether that saves effort at the same quality is what the sessions measure.

`tests/evaluation/test_usability.py` checks that the hashes above match the files.
