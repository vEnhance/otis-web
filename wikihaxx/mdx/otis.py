import re
from typing import Any, List

import markdown
import markdown.preprocessors

TABLE = r'''<div class="col-md-6 float-right">
<table>
<tbody>
	<tr>
		<th>Hi</th>
		<td></td>
	</tr>
</tbody>
</table>
</div>'''


class OTISExtension(markdown.Extension):
	def extendMarkdown(self, md: Any):
		md.preprocessors.add('otis-extras', OTISPreprocessor(md), '>html_block')


special_start_regex = re.compile(r'\[(arch|diamond|unit|generic)([ a-zA-Z0-9]*)\]')
special_end_regex = re.compile(r'\[/(arch|diamond|unit|generic)+\]')


class OTISPreprocessor(markdown.preprocessors.Preprocessor):
	# TODO implement cool stuff
	def run(self, lines: List[str]) -> List[str]:
		output: List[str] = []
		active = False

		for line in lines:
			m_start = special_start_regex.match(line)
			m_end = special_end_regex.match(line)
			if m_start is not None:
				active = True
				output.append(r'<div class="col-md-6 float-right">')
				output.append(r'<table>')
				output.append(r'<tbody>')
			elif m_end is not None:
				output.append(r'</tbody>')
				output.append(r'</table>')
				output.append(r'</div>')
				output.append(r'')
				output.append(r'[toc]')
				output.append(r'')
				active = False
			elif active is True:
				parts = line.split(' | ')
				if len(parts) == 2:
					output.append('<tr>')
					output.append('<th>' + parts[0].strip() + '</th>')
					output.append('<td>' + parts[1].strip() + '</td>')
					output.append('</tr>')
			else:
				output.append(line)
		return output
