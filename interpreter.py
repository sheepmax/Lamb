#!/usr/bin/env python3.10

from parser import *
from lexer import *
from sexpr import *
from math import gamma
from dataclasses import dataclass
from copy import deepcopy
import sys
from io import StringIO

# Generic exception used for any sort of interpretation errors we might encounter
class InterpException(Exception): pass

# Represents a value produced from interpreting an SExpr
class Value: pass

class Environment: pass

@dataclass
class Environment:
	binds: dict[str, Value]
	parent: Environment

@dataclass
class VNum(Value):
	val: int
	def __str__(self):
		return str(int(self.val))

@dataclass
class VNone(Value):
	def __str__(self):
		return "none"


@dataclass
class VStr(Value):
	val: str
	def __str__(self):
		return self.val

@dataclass
class VList(Value):
	vals: list[Value]
	def __str__(self):
		return ", ".join([str(val) for val in self.vals])

@dataclass
class VClos(Value):
	params: list[Fparam]
	body: SExpr
	env: Environment

def search_environment(env, ident):
	while (env != None):
		if (ident in env.binds):
			return env.binds[ident]
		env = env.parent
	return None

def set_variable(env, ident, val, localized = False, index = -1):
	if (localized and (ident in env.binds)):
		return deepcopy(env.binds[ident])
	elif (localized):
		env.binds[ident] = val
		return val

	base = env
	while (ident not in env.binds):
		env = env.parent
		if (env == None):
			env = base # We didn't find it so we restore back to the local level
			break

	env.binds[ident] = val
	return val

def __interp_block(exprs, env):
	last = VNone()
	for expr in exprs:
		last = __interp(expr, env)
	return last

# Keeps track of context for native string output, like a stack
__native_strings = []

# Returns (call_beginning, call_ending, macro_name/var_name, args/None),
# None if no calls are found
# Call syntax = ($var_name) || ($macro_name(arg1, arg2...))

def parse_native_line_call(line):
	# We search in reverse to evaluate macros back to front
	beg = len(line) - line[::-1].find(MACRO_CHAR) - 1
	if (beg == len(line)): return None # We did not find any special character

	end = beg + 2
	
	paren_depth = 1
	while (paren_depth != 0): 
		end += 1
		if (line[end] == '('): paren_depth += 1
		elif (line[end] == ')'): paren_depth -= 1

	expression = parse_expression(new_lex(StringIO(line[beg + 2: end]), in_macro = True), -1)

	return (beg, end, expression)

def iterable_to_iterator(iterable):
	match iterable:
		case VList(vals): return vals
		case VStr(val): return [VStr(char) for char in list(val)]

def mutate_iterable_index(iterable, idx, new_value):
	match iterable:
		case VList(vals): 
			vals[idx] = new_value
	return new_value

# Super basic interpreter, no error checking
def __interp(expr, env):
	match expr:
		case SNum(num): return VNum(num)
		case SNone(): return VNone()
		case SStr(string): return VStr(string)

		case SIdent(ident): 
			value = search_environment(env, ident)
			if (value == None): raise InterpException(f"Identifier {ident} not bound.")
			return value

		# If only there was a macro to make this simpler 
		case SOp("+", [a, b]): 
			match (__interp(a, env), __interp(b, env)):
				case (VNum(va), VNum(vb)): return VNum(va + vb)
				case (VStr(va), VStr(vb)): return VStr(va + vb)

		case SOp("-", [a, b]): return VNum(__interp(a, env).val - __interp(b, env).val)
		case SOp("*", [a, b]): return VNum(__interp(a, env).val * __interp(b, env).val)
		case SOp("/", [a, b]): return VNum(__interp(a, env).val / __interp(b, env).val)
		case SOp("<", [a, b]): return VNum(int(__interp(a, env).val < __interp(b, env).val))
		case SOp(">=", [a, b]): return VNum(int(__interp(a, env).val >= __interp(b, env).val))
		case SOp("<=", [a, b]): return VNum(int(__interp(a, env).val <= __interp(b, env).val))
		case SOp("==", [a, b]): return VNum(int(__interp(a, env).val == __interp(b, env).val))
		case SOp("||", [a, b]): return VNum(int(__interp(a, env).val or __interp(b, env).val))

		case SOp("-", [a]): return VNum(-__interp(a, env).val)
		case SOp("!", [a]): return VNum(gamma(__interp(a, env).val + 1))

		case SOp("++", [a]):
			value = search_environment(env, a.ident)
			value.val += 1
			return VNum(value.val)

		case SOp("--", [a]):
			value = search_environment(env, a.ident)
			value.val -= 1
			return VNum(value.val)

		case SOp("=", [a, b]):
			variable_name = a.ident
			new_value = __interp(b, env)
			return set_variable(env, variable_name, new_value)

		case SOp(":=", [a, b]):
			variable_name = a.ident
			new_value = __interp(b, env)
			return set_variable(env, variable_name, new_value, localized = True)

		case SOp(";", [a, b]):
			__interp(a, env)
			return __interp(b, env)

		case SOp("[", [a, b]):
			return iterable_to_iterator(__interp(a, env))[int(__interp(b, env).val)]

		case SOp("[=", [a, b, c]):
			return mutate_iterable_index(__interp(a, env), int(__interp(b, env).val), __interp(c, env))

		case SList(elems):
			return VList([__interp(elem, env) for elem in elems])

		case SIf(con, thn, els):
			if (__interp(con, env).val):
				return __interp_block(thn, env)
			return __interp_block(els, env)

		case SLoop(cond, body):
			last = VNone()
			loop_env = Environment({}, env)
			while (__interp(cond, loop_env).val > 0):
				last = __interp_block(body, loop_env)
			return last

		case SMacro(name, params, body):
			closure = VClos(params, body, Environment({}, env))
			return set_variable(env, name, closure)

		case SApp(SIdent("len"), args):
			if (len(args) != 1): raise InterpException("len only takes 1 argument")

			return VNum(len(iterable_to_iterator(__interp(args[0], env))))

		case SApp(SIdent("debug"), args):
			print([__interp(arg, env) for arg in args])
			return VNone()

		case SApp(func, args):
			macro = search_environment(env, func.ident)
			args = [__interp(arg, env) for arg in args]
			for idx, param in enumerate(macro.params):
				if (param.vari):
					set_variable(macro.env, param.name, VList(args[idx:]))
				else:
					set_variable(macro.env, param.name, args[idx])
			return __interp_block(macro.body, macro.env)

		# This is probably the trickiest part of the whole thing :/
		# Plan: buffer line somehwere until fully processed
		# Try to parse args as native objects otherwise bail
		case SNative(line):
			native_line_idx = len(__native_strings)
			__native_strings.append("")

			# If the line ends with the special character, remove newline
			line_stripped = line.rstrip()
			parsing_needed = True

			# If the line stripped is nothing we can just assume no parsing is needed and move on
			if (line_stripped == ""):
				parsing_needed = False
			else:
				line = line_stripped[:-1] if line_stripped[-1] == MACRO_CHAR else line

			while (parsing_needed):
				parse_result = parse_native_line_call(line)

				if (parse_result == None): break

				beg, end, expr = parse_result
				
				result = __interp(expr, env)

				to_output = str(result)

				# Function is pure, so we output its result
				if (type(expr) is SApp and len(__native_strings) != (native_line_idx + 1)):
					to_output = ""
		
				# If a pure function is called, it won't join in any impure functions it calls, so we may
				# have more than one native string after the current one.
				line = line[:beg] + to_output + "".join(__native_strings[native_line_idx + 1:]) + line[end + 1:]

				del __native_strings[native_line_idx + 1:]

			# We must be outside of a macro, let's output this to the file
			if (native_line_idx == 0): 
				__output_file.write(line)
				del __native_strings[0]
			else: 
				__native_strings[native_line_idx] = line
			return

	raise InterpException(f"Unknown expression: {expr}")

__output_file = None

def interp(file, output_filepath):
	global __output_file
	with open(output_filepath, "w") as f:
		__output_file = f

		global_env = Environment({}, None)
		for statement in parse(lex_file(file)): 
			__interp(statement, global_env)

	return True

# Small test for interpreting, very coolio
if (__name__ == "__main__"):
	if len(sys.argv) != 3:
		print("Usage: interpreter [input filepath] [output filepath]")
		sys.exit(0)

	if (interp(sys.argv[1], sys.argv[2])):
		print(f"Interpretation was successful, wrote to {sys.argv[2]}!")
	