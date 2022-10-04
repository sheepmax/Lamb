from dataclasses import dataclass

# Represents a (potentially sugared) expression
# These are formed during the parsing of the token stream
# using PRATT parsing
class SExpr: pass

@dataclass
class SOp(SExpr):
	op: str
	exprs: list[SExpr]

@dataclass
class SNative(SExpr):
	code: str

@dataclass
class SIf(SExpr):	
	con: SExpr
	thn: list[SExpr]
	els: list[SExpr]

@dataclass
class SNum(SExpr):
	num: float

@dataclass
class SList(SExpr):
	elems: list[SExpr]

@dataclass
class SStr(SExpr):
	string: str

@dataclass
class SIdent(SExpr):
	ident: str

@dataclass 
class SLoop(SExpr):
	cond: SExpr
	body: list[SExpr]

@dataclass
class Fparam:
	name: str
	vari: bool  # whether is var_arg

@dataclass
class SMacro(SExpr):
	name: str
	params: list[Fparam]
	body: list[SExpr]

@dataclass
class SNone(SExpr): pass

@dataclass 
class SApp(SExpr):
	func: SIdent
	args: list[SExpr]