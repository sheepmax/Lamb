from enum import Enum, auto

class LexException(Exception): pass

class TOKENS(Enum):
	OP      = auto()
	NUM     = auto()
	STR     = auto()
	IDENT   = auto()
	PARENS  = auto()
	KEYWORD = auto()
	NATIVE  = auto()
	NONE    = auto()
	NL      = auto()
	EOF     = auto()

# List of all valid operators
OPS = ['+', '-', '*', '/', '!', ';', '=', "...", ":=", '<', '[', "++", "--", "==", ">=", "||", "<=", "in"]
PARENS = ['(', ')', '{', '}', ']', ',']

# List of special keywords
KEYWORDS = ["if", "else", "MACRO", "loop"]

# Returns whether a character forms part of a number
def in_num(c):
	return c.isnumeric() or c == '.'

# Returns whether a character can be used in identifiers
def in_ident(c):
	return c.isalpha() or c == '_'

# Keeps track of tokens that have been peeked
__previous_token = None

# Basic heuristics to check if we're inside a macro or not
# This allows different syntax in the macro whilst still capturing native code properly
__in_macro = False
__block_depth = 0

# The macro char is used to denote the difference between native code and
# macro code within a macro. This can be set at the beginning of a file so the most
# suitable (producing least conflict) character can be chosen.
# TODO
MACRO_CHAR = '$'

# Returns next token in lexer stream
# Returns and erases previous token if the token was peeked
def get_next(lexer):
	global __previous_token
	if (__previous_token != None):
		temp = __previous_token
		__previous_token = None
		return temp

	return next(lexer)

# Throws away next token
def consume_next(lexer):
	global __previous_token
	if (__previous_token != None):
		__previous_token = None
	else:
		next(lexer)

# Peeks at, but does not consume the next token in the stream
def peek_next(lexer):
	global __previous_token
	if (__previous_token == None):
		__previous_token = next(lexer)
	return __previous_token

def in_ops(s, ops):
	return list(filter(lambda op: s in op, ops))

# Turns a text file into a generator for a stream of tokens
# The tokens consist of 4 basic types:
#	1. OP - operators as defined by the OPS list
#	2. NUM - numbers, represented as floating point
#	3. STR - string literals
#	4. IDENT - identifiers that may represent variable names
# EOF token is given to signify the end of the stream.
def lex(file, in_macro = None):
	global __in_macro, __block_depth

	# Little work around for parsing StringIO sort of things
	if (in_macro != None): __in_macro = True

	while (char := file.read(1)):
		# Check to see if this is the beginning of macro def, otherwise consume as native line
		if (not __in_macro):
			initial_whitespace = ""
			while (char.isspace()):
				initial_whitespace += char
				char = file.read(1)
			macro_check = char + file.read(4)
			if (macro_check == "MACRO"):
				__in_macro = True
				yield (TOKENS.KEYWORD, macro_check)
				continue

			yield (TOKENS.NATIVE, initial_whitespace + macro_check + file.readline())
			continue

		# if (char == '\n'): yield (TOKENS.NL, '\n')
		if (char.isspace()): continue

		# Basic python-style comments that just skip over the line
		if (char == '#'):
			file.readline()
			continue

		if (ops := in_ops(char, OPS)):
			s = char
			# Continue consuming characters until we filter the possible
			# operators. We reach 0 when we had the correct token and overconsume.
			while (len(ops) > 0):
				s += file.read(1)
				ops = in_ops(s, ops)

			# To compensate for the overconsumptions, we rollback
			file.seek(file.tell() - 1, 0)
			s = s[:-1]

			if (s in OPS):
				yield (TOKENS.OP, s)
				continue

			# Incases of multicharacter tokens, the operator could start right, but be interrupted,
			# consider: .a., which would be recognized as being only [...] on the first loop,
			# when the lexer reads 'a' it then reaches 0 possible tokens and exists, thus believing it has
			# parsed all of the ... operator. However it has actually only parsed '.', an invalid operator.
			# If s is not found in OPS we need to then rollack and let it fall through to the rest of the lexer
			file.seek(file.tell() - len(s) + 1, 0)

		if (char == MACRO_CHAR):
			yield (TOKENS.NATIVE, file.readline())

		elif (char in PARENS):
			if (char == '{'): 
				__block_depth += 1
			elif (char == '}'): 
				__block_depth -= 1
				__in_macro = __block_depth > 0
			yield (TOKENS.PARENS, char)

		# String can only be delimited by " " at the moment and no proper
		# escaping is provided :(
		elif (char == '"'):
			string = ""
			# WARNING, if there is no closing ", the program lexer will hang, can be mitigated latter by checking for EOF
			while ((char := file.read(1)) != '"'):
				string += char
			yield (TOKENS.STR, string)

		elif (in_num(char)):
			number = char if char != '.' else '0.'
			while (in_num(char := file.read(1))):
				number += char

			# Move back one character to account for the ending condition of while loop
			if (char != ''): file.seek(file.tell() - 1, 0)    
			
			yield (TOKENS.NUM, float(number))
		
		elif (in_ident(char)):
			ident = char
			while (in_ident(char := file.read(1))):
				ident += char

			# Move back one character to account for the ending condition of while loop
			if (char != ''): file.seek(file.tell() - 1, 0)  

			if (ident in KEYWORDS): yield (TOKENS.KEYWORD, ident)
			elif (ident == "none"): yield(TOKENS.NONE, None)
			else: yield (TOKENS.IDENT, ident)
		else:
			raise LexException(f"Character cannot be recognized in token: {char}")

	file.close()
	yield (TOKENS.EOF, None)	

# Need to reset the lexer state properly
def new_lex(file, in_macro = None):
	global __previous_token
	__previous_token = None
	return lex(file, in_macro = in_macro)

def lex_file(file_name):
	file = open(file_name, "r")
	return new_lex(file)
	 
# Small test for lexing, very coolio
if (__name__ == "__main__"):
	for token in lex_file("examples/basic.pre"):
		print(token)