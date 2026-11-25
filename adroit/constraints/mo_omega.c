/*
 * mo_omega.c -- generic batch driver for the freeze-out relic density in any
 * micrOMEGAs model directory (IDM, SingletDM, ZpPortal, ...).
 *
 * Build (from inside a model directory, e.g. micromegas_7.1.10/IDM):
 *     cp /path/to/mo_omega.c .  &&  make main=mo_omega.c
 *
 * Usage:
 *     ./mo_omega [options] [file.par] NAME=VALUE [NAME=VALUE ...]
 *
 *   NAME=VALUE    assign a free model parameter (names as in work/models/vars1.mdl);
 *                 assignments are applied left to right, after any .par file.
 *   file.par      a micrOMEGAs parameter file ("NAME VALUE" per line), read by readVar.
 *   -m LIST       comma separated list of off-shell (VV*) modes to compute, default "0,1".
 *                 Each item is either  k   (sets VWdecay=VZdecay=k)  or  w:z.
 *                   0 : 2->2 only (no virtual W/Z final states, and no 1->3 decays
 *                       with virtual W/Z in the automatically computed widths);
 *                   1 : add 2->3 with W* / Z* for DM-DM annihilation (micrOMEGAs default);
 *                   2 : add 2->3 with W* / Z* in co-annihilation channels too.
 *   -f FAST       darkOmega 'fast' flag: 0 (default here; accurate integration),
 *                 1 (micrOMEGAs' "fast" mode; ~1% nominal, but up to ~4% off near the
 *                 Higgs pole in the IDM), -1 (documented as "no interpolation of 2->3
 *                 cross sections"; identical to 0 in our 7.1.10 IDM tests).
 *                 fast=0 costs only ~10% more time than fast=1.
 *   -b BEPS       Beps co-annihilation cutoff (default 1e-5).
 *   -w P=WIDTH    impose a fixed total width [GeV] for particle P (e.g. -w h=4.07e-3).
 *                 Implemented by loading an SLHA DECAY block and pWidthPref(P,2), so the
 *                 width is the same in every VV* mode. Not possible for W+ and Z
 *                 (the SLHA reader ignores their DECAY blocks). Repeatable.
 *   -c CUT        also list channels contributing more than CUT (fraction) to 1/Omega.
 *   -v NAME       also print the value of a (free or public constrained) parameter.
 *                 Repeatable.
 *   -h            help.
 *
 * Machine-readable output: every line we print starts with "MO_" and contains
 * space separated key=value pairs (the rest of stdout is micrOMEGAs chatter):
 *   MO_INFO   micrO=<install path> cdm=<name> Mcdm=<GeV> spin2=<2s> pdg=<code>
 *   MO_VAR    name=<NAME> value=<value>
 *   MO_OMEGA  mode=<w:z> VWdecay=<w> VZdecay=<z> fast=<f> Beps=<b> Omega=<Oh2> Xf=<M/Tf>
 *             err=<code> wh=<Higgs width used, GeV or -1> time=<s>
 *   MO_CHANNEL mode=<w:z> frac=<fraction of 1/Omega> proc=<p1,p2->p3,p4[,p5]>
 *   MO_ERROR  msg=<text>
 *   MO_DONE   status=0
 */

#include "../include/micromegas.h"
#include "../include/micromegas_aux.h"
#include "../include/microPath.h"
#include <sys/time.h>

#define MAXW 16
#define MAXM 8
#define MAXV 32

static double wallTime(void)
{ struct timeval tv; gettimeofday(&tv, NULL); return tv.tv_sec + 1e-6 * tv.tv_usec; }

static void usage(void)
{
  printf("Usage: ./mo_omega [-m 0,1[,2|w:z]] [-f fast] [-b Beps] [-w P=width]... "
         "[-c cut] [-v NAME]... [file.par] NAME=VALUE ...\n");
}

static int parseModes(const char *s, int vw[], int vz[])
{ int n = 0;
  char buf[256];
  strncpy(buf, s, 255); buf[255] = 0;
  for (char *tok = strtok(buf, ","); tok && n < MAXM; tok = strtok(NULL, ","))
  { int w, z;
    if (sscanf(tok, "%d:%d", &w, &z) == 2) { vw[n] = w; vz[n] = z; n++; }
    else if (sscanf(tok, "%d", &w) == 1)   { vw[n] = w; vz[n] = w; n++; }
    else return -1;
  }
  return n;
}

/* Write an SLHA file holding only DECAY blocks for the imposed widths and load it. */
static int loadWidths(int nW, char *wName[], double wVal[])
{ char fname[64];
  sprintf(fname, "/tmp/mo_omega_widths_%d.slha", getpid());
  FILE *f = fopen(fname, "w");
  if (!f) return -1;
  for (int i = 0; i < nW; i++)
  { int s2, c3, cd;
    int pdg = qNumbers(wName[i], &s2, &c3, &cd);
    if (pdg == 0) { fclose(f); remove(fname); return i + 1; }
    /* a single dummy channel (b bbar) carries BR=1; only the total width matters here */
    fprintf(f, "DECAY %d %.10E\n   1.0  2  5  -5\n", pdg, wVal[i]);
  }
  fclose(f);
  /* SLHAplus reader mode bits (SLHAreader.c, arXiv:1008.0181): 1 keep old data,
     2 stop on format errors, 4 skip DECAY, 8 skip BLOCK. NB the reader always
     ignores DECAY blocks of Z (23) and W (24), so their widths cannot be imposed. */
  int err = slhaRead(fname, 8);
  remove(fname);
  return err ? -2 : 0;
}

/* Switch the imposed particles to SLHA widths and check that the value took effect. */
static int applyWidthPrefs(int nW, char *wName[], double wVal[])
{ for (int i = 0; i < nW; i++)
  { pWidthPref(wName[i], 2);
    double w = pWidth(wName[i], NULL);
    if (fabs(w - wVal[i]) > 1e-6 * fabs(wVal[i]))
    { printf("MO_ERROR msg=width_not_applied particle=%s imposed=%g got=%g\n", wName[i], wVal[i], w);
      return 1; }
  }
  return 0;
}

static void printChannelList(const char *mode, double Xf, double cut, double Beps)
{ FILE *null = fopen("/dev/null", "w");
  printChannels(Xf, cut, Beps, 0, null);
  fclose(null);
  if (!omegaCh) return;
  for (int k = 0; omegaCh[k].weight > 0; k++)
  { if (omegaCh[k].weight < cut) continue;
    char proc[200] = "";
    int nin = omegaCh[k].nin > 0 ? omegaCh[k].nin : 2;
    for (int j = 0; j < 10 && omegaCh[k].prtcl[j]; j++)
    { strcat(proc, omegaCh[k].prtcl[j]);
      if (j + 1 == nin) strcat(proc, "->");
      else if (j + 1 < 10 && omegaCh[k].prtcl[j + 1]) strcat(proc, ",");
    }
    printf("MO_CHANNEL mode=%s frac=%.6g proc=%s\n", mode, omegaCh[k].weight, proc);
  }
}

int main(int argc, char **argv)
{
  int vw[MAXM] = {0, 1}, vz[MAXM] = {0, 1}, nModes = 2;
  int fast = 0, nW = 0, nV = 0, err;
  double Beps = 1.E-5, chCut = -1;
  char *wName[MAXW]; double wVal[MAXW];
  char *vName[MAXV];
  char cdmName[50];

  ForceUG = 0;
  setvbuf(stdout, NULL, _IOLBF, 0);

  for (int i = 1; i < argc; i++)
  { char *a = argv[i];
    if (!strcmp(a, "-h") || !strcmp(a, "--help")) { usage(); return 0; }
    else if (!strcmp(a, "-m") && i + 1 < argc)
    { nModes = parseModes(argv[++i], vw, vz);
      if (nModes <= 0) { printf("MO_ERROR msg=bad_mode_list\n"); return 2; } }
    else if (!strcmp(a, "-f") && i + 1 < argc) fast = atoi(argv[++i]);
    else if (!strcmp(a, "-b") && i + 1 < argc) Beps = atof(argv[++i]);
    else if (!strcmp(a, "-c") && i + 1 < argc) chCut = atof(argv[++i]);
    else if (!strcmp(a, "-v") && i + 1 < argc) { if (nV < MAXV) vName[nV++] = argv[++i]; else i++; }
    else if (!strcmp(a, "-w") && i + 1 < argc)
    { char *eq = strchr(argv[++i], '=');
      if (!eq || nW >= MAXW) { printf("MO_ERROR msg=bad_width_option\n"); return 2; }
      *eq = 0; wName[nW] = argv[i]; wVal[nW] = atof(eq + 1); nW++; }
    else if (strchr(a, '='))
    { char *eq = strchr(a, '=');
      *eq = 0;
      if (assignVal(a, atof(eq + 1)))
      { printf("MO_ERROR msg=unknown_parameter name=%s\n", a); return 3; } }
    else
    { err = readVar(a);
      if (err == -1) { printf("MO_ERROR msg=cannot_open_file file=%s\n", a); return 3; }
      if (err > 0)   { printf("MO_ERROR msg=bad_file_line file=%s line=%d\n", a, err); return 3; } }
  }

  err = sortOddParticles(cdmName);
  if (err) { printf("MO_ERROR msg=sortOddParticles_failed detail=%s\n", cdmName); return 4; }

  int spin2, charge3, cdim;
  int pdg = qNumbers(cdmName, &spin2, &charge3, &cdim);
  printf("MO_INFO micrO=%s cdm=%s Mcdm=%.10g spin2=%d pdg=%d charge3=%d cdim=%d\n",
         micrO, cdmName, Mcdm, spin2, pdg, charge3, cdim);
  if (charge3 || cdim != 1) { printf("MO_ERROR msg=charged_or_coloured_DM\n"); return 4; }

  for (int i = 0; i < nV; i++)
  { double val;
    if (findVal(vName[i], &val) == 0) printf("MO_VAR name=%s value=%.10g\n", vName[i], val);
    else printf("MO_VAR name=%s value=nan\n", vName[i]);
  }

  if (nW)
  { int e = loadWidths(nW, wName, wVal);
    if (e) { printf("MO_ERROR msg=width_override_failed code=%d\n", e); return 5; }
  }

  char *hName = pdg2name(25);
  for (int m = 0; m < nModes; m++)
  { char mode[16];
    sprintf(mode, "%d:%d", vw[m], vz[m]);
    VWdecay = vw[m]; VZdecay = vz[m];
    /* sortOddParticles resets micrOMEGAs' per-subprocess cache of virtual-W/Z flags and
       2->3 interpolation tables, which would otherwise leak from one mode to the next. */
    if (m > 0 && sortOddParticles(cdmName))
    { printf("MO_ERROR msg=sortOddParticles_failed detail=%s\n", cdmName); return 4; }
    cleanDecayTable();
    if (applyWidthPrefs(nW, wName, wVal)) return 5;
    double Xf = 0, t0 = wallTime();
    int oerr = 0;
    double Omega = darkOmega(&Xf, fast, Beps, &oerr);
    double t1 = wallTime();
    double wh = hName ? pWidth(hName, NULL) : -1;
    printf("MO_OMEGA mode=%s VWdecay=%d VZdecay=%d fast=%d Beps=%g Omega=%.8g Xf=%.8g "
           "err=%d wh=%.6g time=%.3f\n",
           mode, VWdecay, VZdecay, fast, Beps, Omega, Xf, oerr, wh, t1 - t0);
    if (chCut >= 0 && Omega > 0) printChannelList(mode, Xf, chCut, Beps);
  }
  printf("MO_DONE status=0\n");
  killPlots();
  return 0;
}
