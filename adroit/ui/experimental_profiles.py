"""Visible immutable selection review, explicit activation and rollback."""
from nicegui import ui
from adroit.library.experimental import ExperimentalCatalog
from adroit.library import experimental_profiles as profiles

def search_options(role):
    """The reviewed private searches with the given role (signal or null), by reference."""
    from adroit.constraints.experimental_search_review import load_bound
    catalog=ExperimentalCatalog()
    out={}
    for path in catalog.path('searches').glob('*.json'):
        try:
            bound=load_bound('private-search:'+path.stem,catalog)
            if bound.contract.role==role:
                out[bound.reference]=bound.record.name+' · '+bound.search_id[:10]
        except (ValueError,OSError):
            continue
    return out

def options():
    """The saved personal experimental profiles by reference, after the packaged defaults (a profile that cannot be
    loaded is named on the profiles page: ``damaged_notice``)."""
    out={'none':'Packaged defaults (no personal profile)'}
    found,_=profiles.listing(ExperimentalCatalog())
    out.update({ref:p.name+' · '+p.profile_id[:10]+' · '+p.created_at for ref,p in found.items()})
    return out

def damaged_notice():
    """Name the saved profiles that cannot be loaded, and an active selection whose record cannot be read, or
    nothing (the consolidation plan's M3)."""
    from adroit.core.durable import DamagedRecord
    from adroit.ui.pages import _damaged
    _damaged(None,'saved profile(s)',profiles.listing(ExperimentalCatalog())[1],'unreadable_profiles')
    try:
        profiles.active()
    except DamagedRecord as error:
        ui.label(f'The active profile cannot be used: {error}. Runs that use the active profile are refused until '
                 'it is repaired; choosing a profile or the packaged defaults explicitly still works.') \
            .classes('text-sm text-orange-800').mark('damaged_active_profile')

def selector():
    """A selection of the pinned experimental profiles, set to the active one; where the active selection's record
    cannot be read, set to none of them, with why, so that nothing runs on the defaults in its place."""
    choices=options()
    active=profiles.current()
    if active==profiles.DAMAGED:
        choices={'':'The active profile cannot be read: choose one, or the packaged defaults, explicitly',**choices}
        select=ui.select(choices,value='',label='Pinned personal experimental profile').classes('w-full')
        damaged_notice()
        return select
    if active and active not in choices:
        choices[active]=active
    return ui.select(choices,value=active or 'none',label='Pinned personal experimental profile').classes('w-full')

def page(root):
    """The personal experimental profiles: the one in use, making one (choose, review, save), and using one
    (activate, roll back)."""
    from adroit.ui.pages import header
    from adroit.ui.style import section
    from adroit.ui.experimental_review import limit_options
    from adroit.experiments.registry import module_names,signal_search_names
    header('Experimental profiles','A profile is your choice of which experimental results ADROIT uses: the packaged '
           'ones, with limits and searches you reviewed added or substituted. Activate one for new runs; old results '
           'and queued runs keep the data they were given.',facts=('$0','applies to new runs only'))
    current=profiles.current()
    ui.label('In use for new runs: '+('none: the active profile cannot be read (below)' if current==profiles.DAMAGED
                                       else options().get(current,current) if current else 'the packaged defaults')) \
        .classes('text-lg font-medium')
    damaged_notice()
    with section('Make a profile','Choose its data, review the exact selection (sources, independence, replacements), '
                 'then save it. Saving does not activate it.'):
        name=ui.input('Profile name')
        limits=ui.select(limit_options(),multiple=True,value=[],label='Private published limits').classes('w-full')
        signal=ui.select({'':'No signal selection',**{n:n for n in signal_search_names()},**search_options('signal')},value='',label='Exact signal search').classes('w-full')
        nulls=ui.select({**{n:n for n in module_names()},**search_options('null')},multiple=True,value=[],label='Complete null-search selection').classes('w-full')
        reviewer=ui.input('Selection reviewer name')
        independent=ui.checkbox('I checked independence and replacements for these exact selected datasets')
        confirmed=ui.checkbox('I reviewed the source and adapter scopes of this exact selection')
        state={}
        view=ui.column()
        saved=ui.input('Pinned profile reference').props('readonly')
        def values():return (list(limits.value or []),signal.value or '',list(nulls.value or []))
        def review():
            try:
                state['review']=profiles.review_selection(*values())
                view.clear()
                with view:
                    ui.code(__import__('json').dumps(state['review'],indent=2))
            except (ValueError,OSError) as error:
                ui.notify(str(error))
        def create():
            try:
                p=profiles.create(name.value or '',*values(),state.get('review',{}).get('review_sha256',''),reviewer.value or '',
                    confirmed=confirmed.value,independence_confirmed=independent.value,
                    parent='' if current==profiles.DAMAGED else current)
                saved.value=p.reference
                ui.notify('Immutable profile saved; activation is separate')
            except (ValueError,OSError) as error:
                ui.notify(str(error))
        with ui.row().classes('gap-2'):
            ui.button('Review exact selection',on_click=review).props('outline')
            ui.button('Save reviewed profile',on_click=create).props('color=primary')
    with section('Use a profile','Activate a saved profile for new runs, or roll back to an earlier one (or the packaged '
                 'defaults).'):
        chosen=ui.select(options(),value='none' if current==profiles.DAMAGED else current or 'none',
                         label='Profile to activate or restore').classes('w-full')
        activate_consent=ui.checkbox('Apply this pinned selection to fresh runs only')
        def activate(reference):
            try:
                profiles.activate('' if reference=='none' else reference,current,confirmed=activate_consent.value)
                ui.notify('Fresh-run selection changed; reload to review another activation')
            except (ValueError,OSError) as error:
                ui.notify(str(error))
        with ui.row().classes('gap-2'):
            ui.button('Activate saved profile',on_click=lambda:activate(saved.value or chosen.value)).props('color=primary')
            ui.button('Rollback to selected profile',on_click=lambda:activate(chosen.value)).props('outline color=negative')
