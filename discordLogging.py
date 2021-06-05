import logging
import requests
import socket

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
	"critical": ":fire:",
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

	def emit(self, r : logging.LogRecord):
		print(r)
		print(r.__dict__)
		level = r.levelname.lower().strip()
		emoji = EMOJIS.get(level, ':question:')
		color = COLORS.get(level, 0xaaaaaa)
		title = f'{emoji} {r.message[:200]}'
		fields = [
				{ 'name' : 'Line', 'value' : '`' + str(r.lineno) + '`', 'inline' : True, },
				{ 'name' : 'File', 'value' : '`' + str(r.filename) + '`', 'inline' : True, },
				{ 'name' : 'Scope', 'value' : '`' + r.name + '`', 'inline' : True, }
				]

		status_code = getattr(r, 'status_code', None)
		embed = {
					'title' : title,
					'color' : color,
					'fields' : fields
				}
		if r.exc_text is not None:
			error_msg = r.exc_text
			if len(error_msg) > 800:
				error_msg = error_msg[:300] + '\n...\n' + error_msg[-500:]
			embed['description'] = (f'HTTP {status_code}' \
					if status_code is not None else '') + \
					f'```\n{error_msg}\n```'

		data = {
				'username' : socket.gethostname(),
				'embeds' : [embed],
				}

		if self.url is not None:
			response = requests.post(self.url, json = data)
			return response
