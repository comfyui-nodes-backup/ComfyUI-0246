import uuid
import re
import pathlib
import sys

import aiohttp.web

from server import PromptServer

# Some python fucky wucky

class TautologyStr(str):
	def __ne__(self, other):
		return False

class ByPassTypeTuple(tuple):
	def __getitem__(self, index):
		if index > 0:
			index = 0
		item = super().__getitem__(index)
		if isinstance(item, str):
			return TautologyStr(item)
		return item

#####################################################################################
######################################## API ########################################
#####################################################################################

@PromptServer.instance.routes.post('/0246-parse')
async def parse_handler(request):
	data = await request.json()

	# Validate json
	if data.get("input") is None:
		return aiohttp.web.json_response({
			"error": ["No input provided"]
		})

	# Parse the input string
	expr_res, order, errors = parse_query(data["input"], HIGHWAY_OPS)

	highway_check(expr_res, errors)

	# Return a JSON response with the processed data
	return aiohttp.web.json_response({
		"expr": expr_res,
		"order": order,
		"error": errors
	})

print("Added new endpoint: /0246-parse")

######################################################################################
######################################## CODE ########################################
######################################################################################

# Special thanks to ChatGPT for this
HIGHWAY_OPS = {'>': 'set', '<': 'get', '!': 'eat'}

def parse_query(input, ops):
	# States
	inside_backticks = False
	operation = None
	name = []
	result = {value: [] for value in ops.values()}  # Initialize result with values from ops
	errors = []
	order = []  # To keep track of the order of operations
	i = 0  # Current index in the input string

	# Helper function to add a command to the result and order
	def add_command(op, name_str):
		if op and name_str:  # Only add if both operation and name are present
			result[op].append(name_str)
			order.append((op, name_str))

	# Iterate over the input string
	while i < len(input):
		char = input[i]

		# Handle operation characters
		if char in ops:
			if inside_backticks:
				name.append(char)
			elif operation is not None:
				errors.append(f"Error at char {i+1}: Multiple operation symbols")
				break
			else:
				operation = ops[char]

		# Handle backticks
		elif char == '`':
			inside_backticks = not inside_backticks
			if not inside_backticks and operation:  # Closing backtick
				if name:
					add_command(operation, ''.join(name))
				name = []
				operation = None

		# Handle valid name characters
		elif char.isalnum() or char in ['-', '_'] or (inside_backticks and char):
			if operation is not None or inside_backticks:
				name.append(char)
			else:
				errors.append(f"Error at char {i+1}: Operation symbol expected before name")
				break

		# Handle spaces
		elif char.isspace():
			if inside_backticks:
				name.append(char)
			elif name:
				add_command(operation, ''.join(name))
				name = []
				operation = None

		# Handle semicolons
		elif char == ';':
			if inside_backticks:
				name.append(char)
			elif name:  # Semicolon outside of backticks ends the current command
				add_command(operation, ''.join(name))
				name = []
				operation = None

		# Handle any other character that is not whitespace (error case)
		elif not char.isspace():
			errors.append(f"Error at char {i+1}: Invalid character '{char}'")
			break

		i += 1  # Move to the next character

	# Check if we're in a valid state after parsing all characters
	if inside_backticks:
		errors.append("Error: Unclosed backticks")

	# If there's an unfinished operation at the end
	if operation and name:
		add_command(operation, ''.join(name))

	# If there's an operation symbol but no name and no other errors
	if operation and not name and not errors:
		errors.append(f"Error at char {i + 1}: Operation '{operation}' without a name")

	# Return the result, any errors, and the order of operations
	return (result, order, errors)

def highway_check(result, errors):
	# Check if duplicate names exist within results
	exists = set()
	for name in result['set']:
		if name in exists:
			errors.append(f"Error: Duplicate input name '{name}'")
		else:
			exists.add(name)

	exists = set()
	for name in result['get'] + result['eat']:
		if name in exists:
			errors.append(f"Error: Duplicate output name '{name}'")
		else:
			exists.add(name)

def check_used(_way_in, elem):
	if elem[1] in _way_in["used"]:
		raise Exception(f"Output \"{elem[1]}\" is already used.")

class Highway:
	@classmethod
	def INPUT_TYPES(s):
		return {
			"required": {
				"_query": ("STRING", {
					"default": ">data; <data",
					"multiline": False
				}),
			},
			"optional": {
				"_way_in": ("HIGHWAY_PIPE", ),
			},
			"hidden": {
				"_prompt": "PROMPT",
				"_id": "UNIQUE_ID"
			}
		}

	# Amogus moment ඞ
	RETURN_TYPES = ByPassTypeTuple(("HIGHWAY_PIPE", ))
	RETURN_NAMES = ByPassTypeTuple(("_way_out", ))
	FUNCTION = "execute"
	CATEGORY = "0246"

	# [TODO] Potential recursion error when attempting to hook the inout in not a very specific way
		# => May have to keep a unique identifier for each class and each node instance
			# Therefore if already exist then throw error
				# => Cyclic detection in JS instead of python

	def execute(self, _id = None, _prompt = None, _way_in = None, _query = "", **kwargs):
		_type = _prompt[_id]["inputs"]["_type"]

		if (_way_in is None):
			_way_in = {}
			_way_in["orig"] = self
			_way_in["curr"] = self
			_way_in["data"] = {}
			_way_in["type"] = {}
			_way_in["used"] = set()
		else:
			_way_in["curr"] = self

		# Time to let the magic play out

		for param, key in zip(_type["in"], list(kwargs)):
			name = param["name"][1:]
			_way_in["data"][name] = kwargs[key]
			_way_in["type"][name] = param["type"]

		res = []

		for elem in _type["out"]:
			name = elem["name"][1:]
			if (name in _way_in["data"] and _way_in["type"][name] == elem["type"]) or elem["type"] == "*":
				res.append(_way_in["data"][name])
			else:
				raise Exception(f"Output \"{name}\" is not defined or is not of type \"{elem['type']}\". Expected \"{_way_in['type'][name]}\".")

		return (_way_in, ) + tuple(res)

######################################################################################

def parse_offset(input):
	# Split the string by semicolons
	segments = input.split(';')
	
	# Initialize an empty list to store the parsed data
	parsed_data = []
	
	# Iterate over each segment
	for segment in segments:
		# Trim whitespace and check if the segment is not empty
		segment = segment.strip()
		if segment:
			# Split the segment by comma
			parts = segment.split(',')
			
			# Check if there are exactly two parts after splitting by comma
			if len(parts) != 2:
				return (None, f"Segment '{segment}' is invalid: expected a pair separated by a single comma.")
			
			# Trim whitespace from the string part
			string_part = parts[0].strip()
			
			# Ensure the string part is not empty
			if not string_part:
				return (None, f"Segment '{segment}' is invalid: string part is empty.")
			
			# Concatenate the number part to remove spaces and keep the operator
			number_part = ''.join(parts[1].split())
			try:
				# Check for multiple operators or incorrect placement
				if number_part.count('+') + number_part.count('-') > 1 or not number_part.lstrip('+-').isdigit():
					return (None, f"Segment '{segment}' is invalid: number part has multiple operators or incorrect placement.")

				# Check if the substring is an integer
				int(number_part.lstrip('+-'))
			except ValueError:
				return (None, f"Segment '{segment}' is invalid: number part is not an integer.")
			
			# Add the tuple to the list
			parsed_data.append((string_part, number_part))
	
	return (parsed_data, None)

class TwoDictList:
	def __init__(self):
		self.data = {}

	def __getitem__(self, index):
		for key in self.data:
			if index < len(self.data[key]):
				return self.data[key][index]
			index -= len(self.data[key])

	def get_type(self, type):
		return self.data.get(type, None)

	def type_keys(self):
		return self.data.keys()

	def get_type_index(self, type, index):
		for name in self.data[type]:
			if index < len(self.data[type][name]):
				return self.data[type][name][index]
			index -= len(self.data[type][name])

	def put(self, type, name, data):
		if type not in self.data:
			self.data[type] = {}
		if name not in self.data[type]:
			self.data[type][name] = []
		self.data[type][name].append(data)

	def name_del(self, name):
		for key in self.data:
			if name in self.data[key]:
				del self.data[key][name]

	def type_name_del(self, type, name):
		if type in self.data:
			if name in self.data[type]:
				del self.data[type][name]

	def __len__(self):
		return sum([len(self.data[key]) for key in self.data])
	
	def type_len(self, type):
		return sum([len(self.data[type][key]) for key in self.data[type]])
	
	def __repr__(self):
		return repr(self.data)

class Junction:
	@classmethod
	def INPUT_TYPES(s):
		return {
			"required": {
				"_offset": ("STRING", {
					"default": ";",
					"multiline": False
				}),
			},
			"optional": {
				"_junc_in": ("JUNCTION_PIPE", ),
			},
			"hidden": {
				"_prompt": "PROMPT",
				"_id": "UNIQUE_ID"
			}
		}
	
	RETURN_TYPES = ByPassTypeTuple(("JUNCTION_PIPE", ))
	RETURN_NAMES = ByPassTypeTuple(("_junc_out", ))
	FUNCTION = "execute"
	CATEGORY = "0246"

	def __init__(self):
		self._prev_offset = None
		self._parsed_offset = None

	def execute(self, _id = None, _prompt = None, _junc_in = None, _offset = "", **kwargs):
		_type = _prompt[_id]["inputs"]["_type"]

		if _junc_in is None:
			_junc_in = {}
			_junc_in["orig"] = self
			_junc_in["curr"] = self
			_junc_in["data"] = TwoDictList()
			_junc_in["index"] = {}

		_junc_in["data"].name_del(_id)

		# Pack all data from _junc_in and kwargs together with the following format:

		for param, key in zip(_type["in"], list(kwargs)):
			_junc_in["data"].put(param["type"], _id, kwargs[key])
			if param["type"] not in _junc_in["index"]:
				_junc_in["index"][param["type"]] = 0

		# Parse the offset string

		if _offset != self._prev_offset:
			parsed_offset, err = parse_offset(_offset)
			if err:
				raise Exception(err)
			self._prev_offset = _offset
			self._parsed_offset = parsed_offset

		# Apply the offset to the junction input

		if self._parsed_offset is None:
			raise Exception("Offset is not parsed.")
		
		for elem in self._parsed_offset:
			if _junc_in["data"].get_type(elem[0]) is None:
				raise Exception(f"Type \"{elem[0]}\" in offset string does not available in junction.")
			
			total = _junc_in["data"].type_len(elem[0])

			# Check for ops char
			if elem[1][0] == '+':
				_junc_in["index"][elem[0]] += int(elem[1][1:])
				if _junc_in["index"][elem[0]] >= total:
					raise Exception(f"Offset \"{elem[1]}\" (total: \"{_junc_in['index'][elem[0]]}\") is too large (count: \"{total}\").")
			elif elem[1][0] == '-':
				_junc_in["index"][elem[0]] -= int(elem[1][1:])
				if _junc_in["index"][elem[0]] < 0:
					raise Exception(f"Offset \"{elem[1]}\" (total: \"{_junc_in['index'][elem[0]]}\") is too small (count: \"{total}\").")
			else:
				_junc_in["index"][elem[0]] = int(elem[1])
				if _junc_in["index"][elem[0]] >= total:
					raise Exception(f"Offset \"{elem[1]}\" (total: \"{_junc_in['index'][elem[0]]}\") is too large (count: \"{total}\").")
				elif _junc_in["index"][elem[0]] < 0:
					raise Exception(f"Offset \"{elem[1]}\" (total: \"{_junc_in['index'][elem[0]]}\") is too small (count: \"{total}\").")

		res = []
		track = {}

		for key in _junc_in["data"].type_keys():
			track[key] = 0

		for elem in _type["out"]:
			if elem["full_name"] == "..." or elem["full_name"][0] == "_":
				continue

			if _junc_in["data"].get_type(elem["type"]) is None:
				raise Exception(f"Type \"{elem['type']}\" of output \"{elem['full_name']}\" does not available in junction.")
			
			offset = _junc_in["index"][elem["type"]]
			real_index = track[elem["type"]] + offset
			total = _junc_in["data"].type_len(elem["type"])

			if real_index >= total:
				raise Exception(f"Too much type \"{elem['type']}\" being taken or offset \"{offset}\" is too large (count: \"{total}\").")
			
			res.append(_junc_in["data"].get_type_index(elem["type"], real_index))
			track[elem["type"]] += 1
		
		return (_junc_in, ) + tuple(res)

######################################################################################

NODE_CLASS_MAPPINGS = {
	"Highway": Highway,
	"Junction": Junction
}

NODE_DISPLAY_NAME_MAPPINGS = {
	"Highway": "Highway",
	"Junction": "Junction"
}

######################################################################################

# Trash that may be used later, don't mind me :)
# https://pastebin.com/raw/Z3Y9HimQ