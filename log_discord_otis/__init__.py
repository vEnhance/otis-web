import logging
import traceback
import os
from pathlib import Path
from discord_logger import DiscordLogger
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent.absolute()
ENV_PATH = PROJECT_ROOT / '.env'
if ENV_PATH.exists():
	load_dotenv(ENV_PATH)


DISCORD_LOGGING_OPTIONS = {
    "application_name": "OTIS",
    "service_name": "OTIS-WEB",
    "display_hostname": True,
    "default_level": "warning",
}
dlogger = DiscordLogger(webhook_url=os.getenv("WEBHOOK_URL"),
		**DISCORD_LOGGING_OPTIONS)

class DHandler(logging.StreamHandler):
	def emit(self, r : logging.LogRecord):
		level = r.levelname.lower()
		if level == 'warning':
			level = 'warn'
		if not level in dlogger.EMOJIS:
			level = 'default'
		kwargs = {
				'title' : f'{r.name} (line {r.lineno} of {r.filename})',
				'description' : r.message or '(no message)',
				'level' : level,
				}
		self.service_environment = r.funcName
		if r.exc_info is not None:
			etype, value, tb = r.exc_info
			kwargs['error'] = '\n'.join(
					traceback.format_exception(etype, value, tb))
		try:
			dlogger.construct(**kwargs)
			dlogger.send()
		except:
			print("Couldn't use webhook")
			print(kwargs)

