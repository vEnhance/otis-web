import re
from typing import Any

import markdown
import markdown.preprocessors
from django.db.models.aggregates import Sum
from django.db.models.query_utils import Q

from core.models import UnitGroup
from dashboard.models import PSet
from roster.models import Student
from rpg.models import Achievement, AchievementUnlock


class OTISExtension(markdown.Extension):
    def extendMarkdown(self, md: Any):
        md.preprocessors.add("otis-extras", OTISPreprocessor(md), ">html_block")


special_start_regex = re.compile(r"\[(diamond|unit|generic)([ a-zA-Z0-9]*)\]")
special_end_regex = re.compile(r"\[/(diamond|unit|generic)+\]")


class OTISPreprocessor(markdown.preprocessors.Preprocessor):
    # TODO implement cool stuff
    def run(self, lines: list[str]) -> list[str]:
        output: list[str] = []
        body: list[str] = []
        active = False

        for line in lines:
            m_start = special_start_regex.match(line)
            m_end = special_end_regex.match(line)
            if m_start is not None:
                output.append(r'<div class="col-md-4 float-right">')
                table_output: list[str] = []
                table_output.append(r"<table>")
                table_output.append(r"<tbody>")
                active = True
                tag_name = m_start.group(1)
                tag_arg = m_start.group(2).strip()

                if tag_name == "diamond":
                    try:
                        diamond = Achievement.objects.get(pk=tag_arg)
                    except Achievement.DoesNotExist:
                        table_output.append(
                            '<tr class="danger"><th>Diamond</th><td>INVALID</td></tr>'
                        )
                    else:
                        num_found = (
                            AchievementUnlock.objects.filter(
                                achievement=diamond
                            ).count()
                            or 0
                        )

                        if diamond.creator is None and num_found > 0:
                            if diamond.image:
                                art_url = diamond.image.url
                                output.append(
                                    f'<div class="W-100 text-center"><a href="{art_url}">'
                                    f'<img class="w-100" src="{art_url}" /></a></div>'
                                )
                            table_output.append(
                                f"<tr><th>Name</th><td>{diamond.name}</td></tr>"
                            )
                            table_output.append(
                                f"<tr><th>Value</th><td>{diamond.diamonds}♦</td></tr>"
                            )
                            table_output.append(
                                f"<tr><th>Found by</th><td>{num_found}</td></tr>"
                            )
                            table_output.append(
                                f"<tr><th>Description</th><td>{diamond.description}</td></tr>"
                            )
                        else:
                            table_output.append(
                                '<tr class="danger"><th>Diamond</th><td>NOT ALLOWED</td></tr>'
                            )

                elif tag_name == "unit":
                    try:
                        unitgroup = UnitGroup.objects.get(
                            Q(slug__iexact=tag_arg) | Q(name__iexact=tag_arg)
                        )
                    except UnitGroup.DoesNotExist:
                        table_output.append(
                            f'<tr class="danger"><th>Name</th><td>{tag_arg}</td></tr>'
                        )
                    else:
                        num_taking = Student.objects.filter(
                            curriculum__group=unitgroup
                        ).count()
                        num_psets = PSet.objects.filter(
                            unit__group=unitgroup, status__in=("A", "PA")
                        ).count()
                        clubs_given = (
                            PSet.objects.filter(
                                unit__group=unitgroup,
                            ).aggregate(
                                Sum("clubs")
                            )["clubs__sum"]
                            or 0
                        )
                        hearts_given = (
                            PSet.objects.filter(
                                unit__group=unitgroup,
                            ).aggregate(
                                Sum("hours")
                            )["hours__sum"]
                            or 0
                        )
                        versions = ", ".join(u.code for u in unitgroup.unit_set.all())
                        if unitgroup.artwork:
                            art_url = unitgroup.artwork.url
                            if unitgroup.artwork_thumb_md:
                                art_src = unitgroup.artwork_thumb_md.url
                            else:
                                art_src = art_url
                            output.append(
                                f'<div class="w-100 text-center"><a href="{art_url}">'
                                f'<img class="w-100" src="{art_src}" /></a></div>'
                            )
                        table_output.append(
                            f"<tr><th>Name</th><td>{unitgroup.name}</td></tr>"
                        )
                        if unitgroup.artist_name:
                            table_output.append(
                                f"<tr><th>Artist</th><td>{unitgroup.artist_name}</td></tr>"
                            )
                        table_output.append(
                            f"<tr><th>Classification</th><td>{unitgroup.get_subject_display()}</td></tr>"
                        )
                        table_output.append(
                            f"<tr><th>Slug</th><td>{unitgroup.slug}</td></tr>"
                        )
                        table_output.append(
                            f"<tr><th>Versions</th><td>{versions}</td></tr>"
                        )
                        table_output.append(
                            f"<tr><th>Participants</th><td>{num_taking}</td></tr>"
                        )
                        table_output.append(
                            f"<tr><th>Submissions</th><td>{num_psets}</td></tr>"
                        )
                        table_output.append(
                            f"<tr><th>♣ earned</th><td>{clubs_given}</td></tr>"
                        )
                        table_output.append(
                            f"<tr><th>♥ earned</th><td>{round(hearts_given,ndigits=2)}</td></tr>"
                        )

                        body.append('<blockquote class="catalog-quote">')
                        body.append("<em>")
                        body.append(unitgroup.description)
                        body.append("</em>")
                        body.append("<br />")
                        body.append("— Evan")
                        body.append("</blockquote>")

                output += table_output
            elif m_end is not None:
                output.append(r"</tbody>")
                output.append(r"</table>")
                output.append(r"</div>")
                active = False
            elif active is True:
                parts = line.split(" | ")
                if len(parts) == 2:
                    output.append("<tr>")
                    output.append("<th>" + parts[0].strip() + "</th>")
                    output.append("<td>" + parts[1].strip() + "</td>")
                    output.append("</tr>")
            else:
                output.append(line)
        body += output

        return body
