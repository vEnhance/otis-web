import logging
import pprint
import socket
from collections import OrderedDict
from typing import Any, Dict

import requests
from django.http import HttpRequest

COLORS = {
	"default": 2040357,
	"error": 14362664,
	"critical": 14362664,
	"warning": 16497928,
	"info": 2196944,
	"verbose": 6559689,
	"debug": 2196944,
	"success": 2210373,
}
EMOJIS = {
	"default": ":loudspeaker:",
	"error": ":x:",
	"critical": ":skull_crossbones:",
	"warning": ":warning:",
	"info": ":bell:",
	"verbose": ":mega:",
	"debug": ":microscope:",
	"success": ":rocket:",
}

class DiscordHandler(logging.Handler):
	def __init__(self, url = None):
		super().__init__()
		self.url = url

	def emit(self, r: logging.LogRecord):
		level = r.levelname.lower().strip()
		emoji = EMOJIS.get(level, ':question:')
		color = COLORS.get(level, 0xaaaaaa)

		try:
			user = r.request.user.first_name + ' ' + r.request.user.last_name # type: ignore
		except AttributeError:
			user = 'anonymous'
		s = str(getattr(r, 'status_code', ''))
		if s:
			s = '**' + s + '**'
		else:
			s = 'None'

		fields = [
				{ 'name': 'Status', 'value': s, 'inline': True, },
				{ 'name': 'Level', 'value': r.levelname.title(), 'inline': True, },
				{ 'name': 'Scope', 'value': f"`{r.name}`", 'inline': True, },
				{ 'name': 'Module', 'value': f"`{r.module}`", 'inline': True, },
				{ 'name': 'User', 'value': user, 'inline': True, },
				{ 'name': 'Filename', 'value': f"{r.lineno}:`{r.filename}`", 'inline': True, },
				]

		description_parts = OrderedDict()

		# if the message is short (< 1 line), we set it as the title
		if '\n' not in r.message:
			title = f'{emoji} {r.message[:200]}'
		# otherwise, set the first line as title and include the rest in description
		else:
			i = r.message.index('\n')
			title = f"{emoji} {r.message[:i]}"
			description_parts[':green_heart: MESSAGE :green_heart:'] =  "```" + r.message[i+1:] + "```"

		# if exc_text nonempty, add that to description
		if r.exc_text is not None:
			# always truncate r.exc_text to at most 600 chars since it's fking long
			if len(r.exc_text) > 600:
				blob = r.exc_text[:300] + '\n...\n' + r.exc_text[-300:]
			else:
				blob = r.exc_text
			description_parts[':yellow_heart: EXCEPTION :yellow_heart:'] =  "```" + blob + "```"

		# if request data is there, include that too
		if hasattr(r, 'request'):
			request: HttpRequest = getattr(r, 'request')
			s = ''
			s += f'> **Method** {request.method}\n'
			s += f'> **Path** `{request.path}`\n'
			s += f'> **Content Type** {request.content_type}\n'
			s += f'> **Agent** {request.headers.get("User-Agent", "Unknown")}\n'
			if request.user.is_authenticated:
				s += f'> **User** {getattr(request.user, "username", "wtf")}\n'
			if request.method == 'POST':
				# redact the token for evan's personal api
				d: Dict[str, Any] = {}
				for k,v in request.POST.items():
					if k == 'token' or k == 'password':
						d[k] = '<redacted>'
					else:
						d[k] = v
				s += r'POST data' + '\n'
				s += r'```' + '\n'
				pp = pprint.PrettyPrinter(indent = 2)
				s += pp.pformat(d)
				s += r'```'
			if request.FILES is not None and len(request.FILES) > 0:
				s += f'Files included\n'
				for name, fileobj in request.FILES.items():
					s += f'> `{name}` ({fileobj.size} bytes, { fileobj.content_type })\n'
			description_parts[':blue_heart: REQUEST :blue_heart:'] = s

		embed = {
					'title': title,
					'color': color,
					'fields': fields
				}

		desc = ''
		no_worries = sum(len(_) for _ in description_parts.values()) <= 1800
		for k,v in description_parts.items():
			if len(v) < 600 or no_worries:
				desc += k + '\n' + v.strip() + '\n'
		if desc:
			embed['description'] = desc

		data = {
				'username': socket.gethostname(),
				'embeds': [embed],
				}

		if self.url is not None:
			response = requests.post(self.url, json = data)
			return response
