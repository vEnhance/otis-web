# https://github.com/jordemort/action-pyright/blob/main/pyright_to_rdjson.py

import json
import sys
from typing import Any, Dict, TextIO


def pyright_to_rdjson(jsonin: TextIO):
	pyright = json.load(jsonin)

	if "generalDiagnostics" not in pyright:
		raise RuntimeError("This doesn't look like pyright json")

	rdjson: Dict[str, Any] = {
		"source": {
		"name": "pyright",
		"url": "https://github.com/Microsoft/pyright"
		},
		"severity": "WARNING",
		"diagnostics": [],
	}

	for d in pyright["generalDiagnostics"]:
		rdjson["diagnostics"].append(
			{
			"message": f"{d['message']} ({d['rule']})",
			"severity": d["severity"].upper(),
			"location":
			{
			"path": d["file"],
			"range":
			{
			"start":
			{
			"line": d["range"]["start"]["line"] + 1,
			"column": d["range"]["start"]["character"],
			},
			"end": {
			"line": d["range"]["end"]["line"] + 1,
			"column": d["range"]["end"]["character"],
			},
			},
			},
			}
		)

	return json.dumps(rdjson)


if __name__ == "__main__":
	print(pyright_to_rdjson(sys.stdin))
