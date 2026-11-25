"""Honest report chronology; rendering is not a new physics calculation."""
from datetime import datetime, timezone
from functools import wraps


def utc_now() -> str:
    """An explicit UTC timestamp for a newly performed operation."""
    return datetime.now(timezone.utc).isoformat()


def analysis_report(text: str,recorded: str='',context=None,references: list[str] | None=None) -> str:
    """Attach dates and pinned inputs without changing a scientific conclusion."""
    start='<!-- adroit-chronology -->'
    end='<!-- /adroit-chronology -->'
    if start in text and end in text:
        before,rest=text.split(start,1)
        _,after=rest.split(end,1)
        text=before+after.lstrip('\n')
    started=getattr(context,'calculation_started_at','')
    completed=getattr(context,'calculation_completed_at','')
    lines=[start,f'Report generated (UTC): {utc_now()}']
    if started:
        lines += [f'Calculation started (UTC): {started}',f'Calculation completed (UTC): {completed or "not recorded"}']
    else:
        lines += [f'Calculation date: {recorded+" (saved date; time not recorded)" if recorded else "unknown / not recorded"}']
    if getattr(context,'identity',''):
        lines.append(f'Calculation input identity: `{context.identity}`')
    lines += [f'Pinned model revision: `{r}`' for r in references or []]
    lines += ['Conclusions apply to the recorded inputs and calculation date; later data or revisions require a new analysis.',end,'']
    first,sep,rest=text.partition('\n')
    return first+'\n\n'+'\n'.join(lines)+'\n'+rest.lstrip('\n') if sep else '\n'.join(lines)+text


def model_references(result) -> list[str]:
    """Find exact catalog revisions in the result's typed request."""
    request=getattr(result,'request',None)
    refs=[getattr(request,'catalog_reference','')]
    refs += [getattr(m,'catalog_reference','') for m in getattr(request,'user_models',[])]
    return sorted(set(r for r in refs if r))


def dated_report(function):
    """Date report rendering; absent historical calculation dates stay unknown."""
    @wraps(function)
    def render(result,*args,**kwargs):
        recorded=str(getattr(result,'created','')) if 'created' in getattr(result,'model_fields_set',set()) else ''
        timed=result if getattr(result,'calculation_started_at','') else None
        return analysis_report(function(result,*args,**kwargs),recorded,timed,references=model_references(result))
    return render


def timed(function):
    """Record when a calculation ran: its UTC start and completion, on the result it returns (which declares
    ``calculation_started_at`` and ``calculation_completed_at``)."""
    @wraps(function)
    def run(*args,**kwargs):
        started=utc_now()
        result=function(*args,**kwargs)
        if 'calculation_started_at' not in getattr(type(result),'model_fields',{}):
            return result
        return result.model_copy(update={'calculation_started_at':started,'calculation_completed_at':utc_now()})
    return run
