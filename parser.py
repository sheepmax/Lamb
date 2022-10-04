from lexer import *
from sexpr import *
import pprint

# Generic exception used for any sort of parsing errors we might encounter
class ParseException(Exception): pass

__prefix_table = {}
__prefix_tables_table = {}

__otherfix_table = {}
__otherfix_tables_table = {}
__otherfix_precedences = {}
__otherfix_precedences_tables = {}

def register_prefix_group(gp):
	__prefix_tables_table[gp] = {}
	__prefix_table[gp] = lambda token: __prefix_tables_table[gp][token] if token in __prefix_tables_table[gp] else None

# More general function for a possible API
def register_in_prefix_group(gp, token, parse_func):
	__prefix_tables_table[gp][token] = parse_func

def register_prefix_op(symbol, parse_func):
	__prefix_tables_table[TOKENS.OP][symbol] = parse_func
	
def register_unary(symbol, precedence):
	register_prefix_op(symbol, lambda lexer: SOp(symbol, [parse_expression(lexer, precedence)]))

def register_terminal(typ, cls):
	__prefix_table[typ] = lambda token: lambda _: cls(token)

def register_keyword(keyword, parse_func):
	__prefix_tables_table[TOKENS.KEYWORD][keyword] = parse_func

def register_otherfix_group(gp):
	__otherfix_tables_table[gp] = {}
	__otherfix_table[gp] = lambda token: __otherfix_tables_table[gp][token] if token in __otherfix_tables_table[gp] else None
	__otherfix_precedences_tables[gp] = {}
	__otherfix_precedences[gp] = lambda token: __otherfix_precedences_tables[gp][token]

def register_in_otherfix_group(gp, token, parse_func, precedences):
	__otherfix_tables_table[gp][token] = parse_func
	__otherfix_precedences_tables[gp][token] = precedences

def register_otherfix_op(symbol, parse_func, precedences):
	__otherfix_tables_table[TOKENS.OP][symbol] = parse_func
	__otherfix_precedences_tables[TOKENS.OP][symbol] = precedences

def register_binary(symbol, precedences):
	register_otherfix_op(symbol, lambda lexer, left: SOp(symbol, [left, parse_expression(lexer, precedences[1])]),
		              precedences)

def register_postfix(symbol, precedence):
	register_otherfix_op(symbol, lambda lexer, left: SOp(symbol, [left]), (precedence, None))

def check_next(lexer, expected):
	if ((got := get_next(lexer)) != expected):
		raise ParseException(f"Expected: {expected}, but got: {got}")

def get_parslet(token, table):
	if (token[0] not in table):
		return None
	return table[token[0]](token[1])

def __parse_block(lexer):
	check_next(lexer, (TOKENS.PARENS, '{'))
	body = []
	while (peek_next(lexer) != (TOKENS.PARENS, '}')):
		body.append(__parse_statement(lexer))
	consume_next(lexer)

	return body

def __parse_if(lexer):
	cond = parse_expression(lexer, -1)
	then = __parse_block(lexer)

	els = []
	if (peek_next(lexer) == (TOKENS.KEYWORD, "else")):
		consume_next(lexer)
		els = __parse_block(lexer)

	return SIf(cond, then, els)

def __parse_loop(lexer):
	check_next(lexer, (TOKENS.PARENS, '('))
	cond = parse_expression(lexer, -1)
	check_next(lexer, (TOKENS.PARENS, ')'))
	body = __parse_block(lexer)
  
	return SLoop(cond, body)

def __parse_open_paren(lexer):
	lhs = parse_expression(lexer, -1)

	# Make sure we ended at a parenthesis and not some other token
	check_next(lexer, (TOKENS.PARENS, ')'))
	return lhs

def __parse_macro(lexer):
	application = parse_expression(lexer, -1)
	
	args = []
	name = application.func.ident

	encountered_vari = False
	for arg in application.args:
		if (encountered_vari):
			raise ParseException("Variable argument must be last to function.")
		match arg:
			case SIdent(ident): args.append(Fparam(ident, False))
			case SOp("...", [SIdent(ident)]): 
				args.append(Fparam(ident, True))
				encountered_vari = True

	body = __parse_block(lexer)

	return SMacro(name, args, body)

def __parse_indexing(lexer, left):
	index = parse_expression(lexer, -1)
	check_next(lexer, (TOKENS.PARENS, ']'))

	# Indexed assignment
	if (peek_next(lexer) == (TOKENS.OP, "=")):
		consume_next(lexer)
		return SOp("[=", [left, index, parse_expression(lexer, -1)])

	return SOp("[", [left, index])

def __parse_application(lexer, left):
	args = []
	while (peek_next(lexer) != (TOKENS.PARENS, ')')):
		args.append(parse_expression(lexer, -1))
		
		if (peek_next(lexer) != (TOKENS.PARENS, ')')): 
			check_next(lexer, (TOKENS.PARENS, ','))
	
	consume_next(lexer)
	return SApp(left, args)

def __parse_list(lexer):
	elems = []
	while (peek_next(lexer) != (TOKENS.PARENS, ']')):
		elems.append(parse_expression(lexer, -1))

		if (peek_next(lexer) != (TOKENS.PARENS, ']')):
			check_next(lexer, (TOKENS.PARENS, ','))

	consume_next(lexer)
	return SList(elems)

def __parse_statement(lexer):
	next_token = get_next(lexer)

	if (next_token == (TOKENS.KEYWORD, "MACRO")): 
		return __parse_macro(lexer)
		
	elif (next_token[0] == TOKENS.NATIVE): 
		return SNative(next_token[1])

	return parse_expression(lexer, -1, next_token)
	
def parse_expression(lexer, min_prec, nxt=None):
	token = nxt if (nxt != None) else get_next(lexer)

	parselet = get_parslet(token, __prefix_table)
	if (parselet is None):
		raise ParseException(f"Cannot end on left expression: {token}")
	lhs = parselet(lexer)

	while True:
		token = peek_next(lexer)
		parselet = get_parslet(token, __otherfix_table)

		if (parselet is None):
			break

		lp, rp = __otherfix_precedences[token[0]](token[1])

		if (lp < min_prec): 
			break

		consume_next(lexer)
		lhs = parselet(lexer, lhs)

	return lhs

def parse(lexer):
	statements = []
	while (peek_next(lexer) != (TOKENS.EOF, None)):
		statements.append(__parse_statement(lexer))

	return statements

# Nice declarative grammar definition :)
register_terminal(TOKENS.NUM, SNum)
register_terminal(TOKENS.IDENT, SIdent)
register_terminal(TOKENS.STR, SStr)
register_terminal(TOKENS.NONE, lambda _: SNone()) # Hacked

register_prefix_group(TOKENS.KEYWORD)
register_keyword("if", __parse_if)
register_keyword("loop", __parse_loop)

register_prefix_group(TOKENS.PARENS)
register_in_prefix_group(TOKENS.PARENS, "(", __parse_open_paren)

register_otherfix_group(TOKENS.OP)
register_binary(";" , (0, 0.1))
register_binary("in", (1, 1.1))
register_binary("=" , (1, 1.1))
register_binary(":=", (1, 1.1))
register_binary("<",  (1, 1.1))
register_binary("||",  (1, 1.1))
register_binary(">=",  (2, 2.1))
register_binary("<=",  (2, 2.1))
register_binary("==" , (2, 2.1))
register_binary("+" , (2, 2.1))
register_binary("-" , (2, 2.1))
register_binary("*" , (3, 3.1))
register_binary("/" , (3, 3.1))

register_otherfix_op("[", __parse_indexing, (13, None))
register_postfix("!", 11)
register_postfix("...", 12)
register_postfix("++", 2)
register_postfix("--", 2)

register_otherfix_group(TOKENS.PARENS)
register_in_otherfix_group(TOKENS.PARENS, "(", __parse_application, (100, None))

register_prefix_group(TOKENS.OP)
register_unary("-", 10)
register_in_prefix_group(TOKENS.OP, '[', __parse_list)

def __test_fake_lex():
	yield (TOKENS.IDENT, 'vec')
	yield (TOKENS.PARENS, '(') 
	yield (TOKENS.NUM, 1.0)
	yield (TOKENS.PARENS, ',') 
	yield (TOKENS.NUM, 2.0)
	yield (TOKENS.PARENS, ',') 
	yield (TOKENS.NUM, 3.0)
	yield (TOKENS.PARENS, ',') 
	yield (TOKENS.NUM, 4.0)
	yield (TOKENS.PARENS, ',') 
	yield (TOKENS.NUM, 5.0)
	yield (TOKENS.PARENS, ')') 
	yield (TOKENS.EOF, None)

# Small test for parsing, very coolio
if (__name__ == "__main__"):
	statements = parse(lex_file("interpreter_with_macros.py"))    #parse(lex_file("examples/basic.pre"))
	for statement in statements:
		pprint.pprint(statement)