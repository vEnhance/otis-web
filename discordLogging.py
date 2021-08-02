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

	def emit(self, r : logging.LogRecord):
		level = r.levelname.lower().strip()
		emoji = EMOJIS.get(level, ':question:')
		color = COLORS.get(level, 0xaaaaaa)
		if '\n' not in r.message:
			i = None
			title = f'{emoji} {r.message[:200]}'
		else:
			i = r.message.index('\n')
			title = f"{emoji} {r.message[:i]}"

		fields = [
				{ 'name' : 'Line', 'value' : f"`{r.filename}` ({r.lineno})"'`', 'inline' : True, },
				{ 'name' : 'Module', 'value' : f"`{r.module}`", 'inline' : True, },
				{ 'name' : 'Scope', 'value' : f"`{r.name}`", 'inline' : True, }
				]

		status_code = getattr(r, 'status_code', None)
		embed = {
					'title' : title,
					'color' : color,
					'fields' : fields
				}

		description = ''
		if r.exc_text is not None:
			msg = r.exc_text
			if len(msg) > 800:
				msg = msg[:300] + '\n...\n' + msg[-500:]
			description = (f'HTTP {status_code}' \
					if status_code is not None else '') + \
					f'```\n{msg}\n```'
		if i is not None:
			msg = r.message[i+1:]
			if len(msg) > 800:
				msg = msg[:300] + '\n...\n' + msg[-500:]
			description += f"\n```{msg}```\n"
		description = description.strip()
		if len(description) > 0:
			embed['description']  = description

		data = {
				'username' : socket.gethostname(),
				'embeds' : [embed],
				}

		if self.url is not None:
			try:
				response = requests.post(self.url, json = data)
			except:
				pass
			else:
				return response
