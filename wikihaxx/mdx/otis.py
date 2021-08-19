from typing import Any, List

import markdown
import markdown.preprocessors


class OTISExtension(markdown.Extension):
	def extendMarkdown(self, md: Any):
		md.preprocessors.add('otis-extras', OTISPreprocessor(md), '>html_block')


class OTISPreprocessor(markdown.preprocessors.Preprocessor):
	# TODO implement cool stuff
	def run(self, lines: List[str]):
		return lines
