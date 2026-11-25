"""Deterministic TeX view of the typed model, not a general TeX parser."""
from __future__ import annotations
import ast
from adroit.core.model_spec import ModelSpec

def identifier(value:str) -> str:
    """A name as upright TeX (mathrm), with backslashes, braces and underscores escaped."""
    escaped=value.replace('\\',r'\backslash ').replace('{',r'\{').replace('}',r'\}').replace('_',r'\_')
    return r'\mathrm{'+escaped+'}'

def expression(value:str) -> str:
    """A coupling's arithmetic (names, numbers, + − × / and powers, sqrt, exp, log, abs) as TeX; anything else raises
    ValueError."""
    def tex(node):
        if isinstance(node,ast.Name):
            return identifier(node.id)
        if isinstance(node,ast.Constant) and isinstance(node.value,(int,float)):
            return str(node.value)
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            return ('-' if isinstance(node.op,ast.USub) else '+')+tex(node.operand)
        if isinstance(node,ast.BinOp):
            a,b=tex(node.left),tex(node.right)
            if isinstance(node.op,ast.Div):
                return r'\frac{'+a+'}{'+b+'}'
            if isinstance(node.op,ast.Pow):
                return '{'+a+'}^{'+b+'}'
            if isinstance(node.op,ast.Mult):
                return r'\left('+a+r'\right)\left('+b+r'\right)'
            if isinstance(node.op,(ast.Add,ast.Sub)):
                return '('+a+('+' if isinstance(node.op,ast.Add) else '-')+b+')'
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in ('sqrt','exp','log','abs') and len(node.args)==1:
            x=tex(node.args[0])
            return r'\sqrt{'+x+'}' if node.func.id=='sqrt' else '\\'+node.func.id+r'\left('+x+r'\right)'
        raise ValueError('coefficient is outside the deterministic TeX arithmetic view')
    return tex(ast.parse(value,mode='eval').body)

def render(spec:ModelSpec) -> str:
    """The model as TeX lines: the interaction Lagrangian term by term, the masses, the couplings' values, and each
    field's quantum numbers."""
    if spec.scalar_potential is not None:
        from adroit.model_building.scalar_contract import resolved_spec
        spec=resolved_spec(spec)
    terms=[]
    for term in spec.terms:
        fields=[]
        for occ in term.fields:
            f=spec.field(occ.field)
            name=identifier(occ.field)
            if occ.conjugate:
                name=r'\overline{'+name+'}' if f.spin==.5 else '{'+name+r'}^{\dagger}'
            fields.append(name)
        # Explicit Lorentz operator avoids inventing contractions for unsupported structures.
        gamma={'vector':r'\gamma^\mu','axial':r'\gamma^\mu\gamma^5','pseudoscalar':r'i\gamma^5','scalar':''}.get(term.lorentz)
        body=(' '.join(fields[:1]+([gamma] if gamma else [])+fields[1:]) if gamma is not None else
              r'\mathcal O_{'+identifier(term.lorentz)+'}('+','.join(fields)+')')
        try:
            c=expression(term.coupling)
        except (ValueError,SyntaxError):
            c=identifier(term.coupling)
        terms.append(r'\left('+c+r'\right) '+body+(r'+\mathrm{h.c.}' if term.plus_hc else ''))
    lines=[r'\mathcal L_{\rm int} = '+(' + '.join(terms) if terms else r'\text{interaction terms not specified}')]
    lines += [r'm_{'+identifier(f.name)+'} = '+str(f.mass_gev)+r'\,\mathrm{GeV}' for f in spec.fields if f.mass_gev is not None]
    lines += [identifier(c.name)+' = '+(str(c.value) if c.value is not None else r'\text{unspecified}') for c in spec.couplings]
    lines += [r'\text{Field }'+identifier(f.name)+r':\quad '+
              r'\text{spin='+str(f.spin)+', role='+f.role.value+', SU(3)='+f.charges.su3+
              ', SU(2)='+str(f.charges.su2)+', Y='+str(f.charges.hypercharge)+', Q='+str(f.charges.electric_charge)+
              ', parity='+str(f.dark_parity)+'}' for f in spec.fields]
    return '\n'.join(lines)
