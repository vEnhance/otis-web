# Django Discordo Package Structure

This guide describes the structure for the new `django-discordo` package that will be published on PyPI.

## Directory Structure

```
django-discordo/
├── LICENSE
├── README.md
├── pyproject.toml
└── src/
    └── django_discordo/
        ├── __init__.py
        └── handler.py
```

## File Contents

### LICENSE

```
MIT License

Copyright (c) 2025 Evan Chen

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### README.md

```markdown
# django-discordo

A Discord webhook handler for Django logging that sends beautifully formatted log messages to Discord channels.

## Features

- 🎨 Color-coded log levels with emoji indicators
- 📝 Automatic formatting of Django request data
- 🔒 Automatic redaction of sensitive data (passwords, tokens)
- 🎯 Support for custom log levels (VERBOSE, SUCCESS, ACTION)
- 🔧 Configurable webhook URLs per log level
- 📊 Rich metadata including user info, status codes, and stack traces

## Installation

```bash
pip install django-discordo
```

## Configuration

### 1. Set up Discord Webhook

Create a webhook in your Discord channel:
1. Go to Server Settings → Integrations → Webhooks
2. Click "New Webhook"
3. Copy the webhook URL

### 2. Configure Environment Variables

Add your webhook URL to your `.env` file:

```bash
# General webhook for all log levels
WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL

# Optional: Level-specific webhooks
WEBHOOK_URL_ERROR=https://discord.com/api/webhooks/YOUR_ERROR_WEBHOOK_URL
WEBHOOK_URL_WARNING=https://discord.com/api/webhooks/YOUR_WARNING_WEBHOOK_URL
```

### 3. Update Django Settings

Add the Discord handler to your Django `settings.py`:

```python
import logging
from django_discordo import ACTION_LOG_LEVEL, SUCCESS_LOG_LEVEL, VERBOSE_LOG_LEVEL

# Custom log levels are automatically registered when you import django_discordo

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "discord": {
            "class": "django_discordo.DiscordWebhookHandler",
            "level": "WARNING",  # Adjust as needed
        },
    },
    "root": {
        "handlers": ["discord"],
        "level": "INFO",
    },
}
```

## Custom Log Levels

django-discordo provides three custom log levels in addition to Django's standard levels:

- **VERBOSE** (level 15): Between DEBUG and INFO, for detailed but not critical information
- **SUCCESS** (level 25): Between INFO and WARNING, for successful operations
- **ACTION** (level 35): Between WARNING and ERROR, for important user actions

### Usage Example

```python
import logging
from django_discordo import VERBOSE_LOG_LEVEL, SUCCESS_LOG_LEVEL, ACTION_LOG_LEVEL

logger = logging.getLogger(__name__)

# Using custom log levels
logger.log(VERBOSE_LOG_LEVEL, "Detailed operation info")
logger.log(SUCCESS_LOG_LEVEL, "User registration completed successfully")
logger.log(ACTION_LOG_LEVEL, "Admin user modified critical settings")
```

## Advanced Configuration

### Filtering Logs

You can add filters to prevent certain logs from being sent to Discord:

```python
def filter_useless_404(record):
    if record.args and len(record.args) >= 2:
        return "wp-include" not in str(record.args[1])
    return True

LOGGING = {
    "filters": {
        "filter_useless_404": {
            "()": "django.utils.log.CallbackFilter",
            "callback": filter_useless_404,
        },
    },
    "handlers": {
        "discord": {
            "class": "django_discordo.DiscordWebhookHandler",
            "level": "WARNING",
            "filters": ["filter_useless_404"],
        },
    },
}
```

### Level-Specific Webhooks

You can route different log levels to different Discord channels by setting level-specific webhook URLs:

```bash
WEBHOOK_URL_CRITICAL=https://discord.com/api/webhooks/CRITICAL_CHANNEL
WEBHOOK_URL_ERROR=https://discord.com/api/webhooks/ERROR_CHANNEL
WEBHOOK_URL_WARNING=https://discord.com/api/webhooks/WARNING_CHANNEL
WEBHOOK_URL=https://discord.com/api/webhooks/DEFAULT_CHANNEL
```

The handler will check for `WEBHOOK_URL_{LEVELNAME}` first, then fall back to `WEBHOOK_URL`.

## Testing Mode

When running tests, you may want to disable Discord logging to avoid spam:

```python
import logging
from django_discordo import ACTION_LOG_LEVEL

if TESTING:
    logging.disable(ACTION_LOG_LEVEL)
```

This disables all logs at ACTION level and below (including SUCCESS, INFO, VERBOSE, and DEBUG).

## How It Works

When a log record is emitted:
1. The handler formats the log message with appropriate emoji and color
2. Extracts metadata (user, module, filename, line number, status code)
3. Includes Django request details (method, path, user agent, POST data)
4. Redacts sensitive fields (passwords, tokens)
5. Sends a beautifully formatted embed to Discord via webhook

## Discord Embed Format

Each log message appears as a Discord embed with:
- **Title**: Log message (with emoji indicator)
- **Color**: Coded by log level (red for errors, yellow for warnings, etc.)
- **Fields**: Status code, log level, module, user, filename
- **Description**: Detailed message, exception traceback, and request data

## Requirements

- Python 3.8+
- Django 3.2+
- requests
- python-dotenv

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Credits

Originally part of evans_django_tools by Evan Chen.
```

### pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "django-discordo"
version = "0.1.0"
description = "Discord webhook handler for Django logging"
readme = "README.md"
license = { text = "MIT" }
authors = [
    { name = "Evan Chen", email = "evan@evanchen.cc" }
]
keywords = ["django", "discord", "logging", "webhook", "handler"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Framework :: Django",
    "Framework :: Django :: 3.2",
    "Framework :: Django :: 4.0",
    "Framework :: Django :: 4.1",
    "Framework :: Django :: 4.2",
    "Framework :: Django :: 5.0",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Topic :: System :: Logging",
]
requires-python = ">=3.8"
dependencies = [
    "django>=3.2",
    "requests>=2.25.0",
    "python-dotenv>=0.19.0",
]

[project.urls]
Homepage = "https://github.com/vEnhance/django-discordo"
Repository = "https://github.com/vEnhance/django-discordo"
Issues = "https://github.com/vEnhance/django-discordo/issues"

[tool.hatch.build.targets.wheel]
packages = ["src/django_discordo"]

[tool.hatch.version]
path = "src/django_discordo/__init__.py"
```

### src/django_discordo/__init__.py

```python
"""
django-discordo: Discord webhook handler for Django logging
"""

__version__ = "0.1.0"

from .handler import ACTION_LOG_LEVEL as _ACTION_LOG_LEVEL
from .handler import SUCCESS_LOG_LEVEL as _SUCCESS_LOG_LEVEL
from .handler import VERBOSE_LOG_LEVEL as _VERBOSE_LOG_LEVEL
from .handler import DiscordWebhookHandler as _DiscordWebhookHandler

ACTION_LOG_LEVEL = _ACTION_LOG_LEVEL
SUCCESS_LOG_LEVEL = _SUCCESS_LOG_LEVEL
VERBOSE_LOG_LEVEL = _VERBOSE_LOG_LEVEL
DiscordWebhookHandler = _DiscordWebhookHandler

__all__ = [
    "ACTION_LOG_LEVEL",
    "SUCCESS_LOG_LEVEL",
    "VERBOSE_LOG_LEVEL",
    "DiscordWebhookHandler",
]
```

### src/django_discordo/handler.py

```python
import logging
import os
import pprint
import socket
from collections import OrderedDict
from typing import Any, Optional, TypedDict

import requests
from dotenv import load_dotenv

VERBOSE_LOG_LEVEL = 15
SUCCESS_LOG_LEVEL = 25
ACTION_LOG_LEVEL = 35
logging.addLevelName(VERBOSE_LOG_LEVEL, "VERBOSE")
logging.addLevelName(SUCCESS_LOG_LEVEL, "SUCCESS")
logging.addLevelName(ACTION_LOG_LEVEL, "ACTION")

load_dotenv()

COLORS = {
    "default": 2040357,
    "error": 14362664,
    "critical": 14362664,
    "warning": 16497928,
    "info": 2196944,
    "verbose": 6559689,
    "debug": 2196944,
    "success": 2210373,
    "action": 17663,
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
    "action": ":factory_worker:",
}


def truncate(s: str, n: int = 800) -> str:
    if len(s) > n:
        return s[: n // 2] + "\n...\n" + s[-n // 2 :]
    return s


class Payload(TypedDict):
    username: str
    embeds: list[dict[str, Any]]


class DiscordWebhookHandler(logging.Handler):
    def get_payload(self, record: logging.LogRecord) -> Payload:
        self.format(record)
        level = record.levelname.lower().strip()
        emoji = EMOJIS.get(level, ":question:")
        color = COLORS.get(level, 0xAAAAAA)

        # this only works in django
        try:
            user = record.request.user.first_name + " " + record.request.user.last_name  # type: ignore
        except AttributeError:
            user = "anonymous"
        s = str(getattr(record, "status_code", ""))
        if s:
            s = "**" + s + "**"
        else:
            s = "None"

        fields = [
            {
                "name": "Status",
                "value": s,
                "inline": True,
            },
            {
                "name": "Level",
                "value": record.levelname.title(),
                "inline": True,
            },
            {
                "name": "Scope",
                "value": f"`{record.name}`",
                "inline": True,
            },
            {
                "name": "Module",
                "value": f"`{record.module}`",
                "inline": True,
            },
            {
                "name": "User",
                "value": user,
                "inline": True,
            },
            {
                "name": "Filename",
                "value": f"{record.lineno}:`{record.filename}`",
                "inline": True,
            },
        ]

        description_parts = OrderedDict()

        # if the message is short (< 1 line), we set it as the title
        if "\n" not in record.message:
            title = f"{emoji} {record.message[:200]}"
        # otherwise, set the first line as title and include the rest in description
        else:
            i = record.message.index("\n")
            title = f"{emoji} {record.message[:i]}"
            msg_key = ":green_heart: MESSAGE :green_heart:"
            description_parts[msg_key] = truncate(record.message[i + 1 :])

        # if exc_text nonempty, add that to description
        if record.exc_text is not None:
            # always truncate r.exc_text to at most 600 chars since it's fking long
            msg_key = ":yellow_heart: EXCEPTION :yellow_heart:"
            description_parts[msg_key] = truncate(record.exc_text)

        # if request data is there, include that too
        if hasattr(record, "request"):
            request = getattr(record, "request")
            s = ""
            s += f"> **Method** {request.method}\n"
            s += f"> **Path** `{request.path}`\n"
            s += f"> **Content Type** {request.content_type}\n"
            s += f'> **Agent** {request.headers.get("User-Agent", "Unknown")}\n'
            if request.user.is_authenticated:
                s += f'> **User** {getattr(request.user, "username", "wtf")}\n'
            if request.method == "POST":
                # redact the token for evan's personal api
                d: dict[str, Any] = {}
                for k, v in request.POST.items():
                    if k == "token" or k == "password":
                        d[k] = "<redacted>"
                    else:
                        d[k] = v
                s += r"POST data" + "\n"
                s += r"```" + "\n"
                pp = pprint.PrettyPrinter(indent=2)
                s += pp.pformat(d)
                s += r"```"
            if request.FILES is not None and len(request.FILES) > 0:
                s += "Files included\n"
                for name, fileobj in request.FILES.items():
                    s += (
                        f"> `{name}` ({fileobj.size} bytes, { fileobj.content_type })\n"
                    )

            chars_remaining = 1800 - sum(len(v) for v in description_parts.values())
            description_parts[":blue_heart: REQUEST :blue_heart:"] = s[:chars_remaining]

        embed = {"title": title, "color": color, "fields": fields}

        desc = ""
        for k, v in description_parts.items():
            desc += k + "\n" + v.strip() + "\n"
        if desc:
            embed["description"] = desc

        data: Payload = {
            "username": socket.gethostname(),
            "embeds": [embed],
        }
        return data

    def get_url(self, record: logging.LogRecord) -> Optional[str]:
        return os.getenv(
            f"WEBHOOK_URL_{record.levelname.upper()}", os.getenv("WEBHOOK_URL")
        )

    def post_response(self, record: logging.LogRecord) -> Optional[requests.Response]:
        data = self.get_payload(record)
        url = self.get_url(record)
        if url is not None:
            return requests.post(url, json=data)
        else:
            return None

    def emit(self, record: logging.LogRecord):
        self.post_response(record)
```

## Publishing to PyPI

### 1. Prepare the Package

```bash
cd django-discordo
python -m pip install --upgrade build twine
python -m build
```

### 2. Test on TestPyPI (Optional but Recommended)

```bash
python -m twine upload --repository testpypi dist/*
# Then test install: pip install --index-url https://test.pypi.org/simple/ django-discordo
```

### 3. Publish to PyPI

```bash
python -m twine upload dist/*
```

### 4. Install from PyPI

Once published, users can install with:

```bash
pip install django-discordo
```

## Version Management

To release a new version:

1. Update the version in `src/django_discordo/__init__.py`
2. Update the version in `pyproject.toml`
3. Build and upload the new version to PyPI
4. Tag the release in git: `git tag v0.1.0 && git push --tags`
