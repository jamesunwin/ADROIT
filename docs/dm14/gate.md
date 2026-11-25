# DM14 gate

- G1: PASS
- G2: PASS
- G3: PASS
- G4: PASS

**PASSED**; spent $0.00

```
{
 "G1": {
  "a": {
   "problems": {
    "cdms_ii_ge_2009": [],
    "cdms_ii_si_2013": []
   },
   "pass": true
  },
  "b": {
   "caught": {
    "an event outside the window": [
     "events: [150.0] keV lie outside the window 5-50 keV"
    ],
    "an efficiency above one": [
     "efficiency: values must lie in [0, 1]"
    ],
    "a reversed window": [
     "window: (50.0, 5.0) is not an interval of positive energies"
    ],
    "an unknown target": [
     "target: 'Unobtainium' is not an element or compound the system knows"
    ],
    "a halo in m/s": [
     "halo: v0_km_s = 220000 lies outside the plausible range 150-300"
    ],
    "decreasing efficiency energies": [
     "efficiency: the energies must not decrease (a repeated energy is a step)"
    ],
    "a downward error above the background": [
     "background uncertainty: negative, or a downward error larger than the background itself"
    ],
    "no references": [
     "references: none given"
    ]
   },
   "pass": true
  },
  "c": {
   "rows": [
    {
     "mass": 5.0,
     "s_hat": [
      1.0629039770294428,
      1.0629039770294428
     ],
     "z": [
      1.6140278772407932,
      1.6140278772407932
     ],
     "pass": true
    },
    {
     "mass": 10.0,
     "s_hat": [
      2.8123208953219394,
      2.8123208953219394
     ],
     "z": [
      2.993752490806424,
      2.993752490806424
     ],
     "pass": true
    },
    {
     "mass": 20.0,
     "s_hat": [
      2.613925445272328,
      2.613925445272328
     ],
     "z": [
      2.2518732597496576,
      2.2518732597496576
     ],
     "pass": true
    }
   ],
   "pass": true
  },
  "d": {
   "refused": true,
   "accepted_when_asked": true,
   "pass": true
  }
 },
 "G2": {
  "rows": [
   {
    "model": "vector_mediator@5",
    "z": 1.6140202557492873,
    "z_O1": 1.6140278772407932,
    "same_class": true,
    "pass": true
   },
   {
    "model": "vector_mediator@10",
    "z": 2.9937740829916946,
    "z_O1": 2.993752490806424,
    "same_class": true,
    "pass": true
   },
   {
    "model": "vector_mediator@20",
    "z": 2.25212755255987,
    "z_O1": 2.2518732597496576,
    "same_class": true,
    "pass": true
   },
   {
    "model": "vector_mediator@50",
    "z": 0.9816177433114214,
    "z_O1": 0.9806285141726772,
    "same_class": true,
    "pass": true
   },
   {
    "model": "scalar_mediator@5",
    "z": 1.6140278772152312,
    "z_O1": 1.6140278772407932,
    "same_class": true,
    "pass": true
   },
   {
    "model": "scalar_mediator@10",
    "z": 2.9937524908807163,
    "z_O1": 2.993752490806424,
    "same_class": true,
    "pass": true
   },
   {
    "model": "scalar_mediator@20",
    "z": 2.25187326063024,
    "z_O1": 2.2518732597496576,
    "same_class": true,
    "pass": true
   },
   {
    "model": "scalar_mediator@50",
    "z": 0.9806285176046542,
    "z_O1": 0.9806285141726772,
    "same_class": true,
    "pass": true
   }
  ],
  "pass": true
 },
 "G3": {
  "a": {
   "best_mass": 8.815912549960212,
   "pass": true
  },
  "b": {
   "level": "no_thermal",
   "fitted": 11,
   "resolved": 11,
   "physical_fit_checks": true,
   "dd_everywhere_resolved": true,
   "bounded_fit_checks": true,
   "pass": true
  },
  "c": {
   "thermal_pending": [],
   "pass": true
  }
 },
 "G4": {
  "leader": "O1v@10",
  "class": "class:1",
  "members": [
   "L01s@10",
   "L01v@10",
   "O1s@10",
   "O1v@10"
  ],
  "children": [
   "scalar_mediator_for_L01",
   "vector_mediator_for_O1",
   "scalar_mediator_for_O1"
  ],
  "undetermined": {
   "L01v@10": "isovector: no computable simplified completion produces it at tree level; the model builder can propose isovector completions",
   "O1v@10": "isovector: no computable simplified completion produces it at tree level; the model builder can propose isovector completions"
  },
  "pass": true
 }
}
```
