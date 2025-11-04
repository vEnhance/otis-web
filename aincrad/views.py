import json
import logging
import string
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
from json.decoder import JSONDecodeError
from typing import Any, Literal, TypedDict, Union

from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.db.models.aggregates import Sum
from django.db.models.query import QuerySet, prefetch_related_objects
from django.db.models.query_utils import Q
from django.http.request import HttpRequest
from django.http.response import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from sql_util.aggregates import SubqueryCount
from unidecode import unidecode

from arch.models import Hint, Problem
from dashboard.models import Announcement, PSet
from hanabi.models import HanabiContest, HanabiParticipation, HanabiPlayer, HanabiReplay
from opal.models import OpalPuzzle
from payments.models import Job
from roster.models import (
    ApplyUUID,
    Invoice,
    Student,
    StudentRegistration,
    UnitInquiry,
    build_students,
)
from suggestions.models import ProblemSuggestion


class HintData(TypedDict):
    content: str
    number: int
    keywords: str
    pk: int


class ReplayData(TypedDict):
    game_score: int
    turn_count: int
    replay_id: int
    players: list[str]


class JSONData(TypedDict):
    action: str
    token: str

    arch_puid: str | None
    puid: str
    uid: int
    pk: int
    status: str
    eligible: bool
    clubs: int
    hours: float
    staff_comments: str

    # keys for add single hint
    content: str
    number: int
    keywords: str

    # keys for add multiple hints
    old_hints: list[HintData]
    new_hints: list[HintData]
    allow_delete_hints: bool

    # invoice
    entries: dict[str, float]
    field: Union[Literal["adjustment"], Literal["extras"], Literal["total_paid"]]

    # jobs
    progress: str

    # arch update urls
    urls: dict[str, str]  # puid -> url

    # hanabi
    num_suits: int
    replays: list[ReplayData]

    # announcement
    slug: str
    subject: str
    content: str

    # ApplyUUID
    uuid: str
    percent_aid: int


PSET_VENUEQ_INIT_QUERYSET = PSet.objects.filter(
    status__in=("PA", "PR", "P"),
    student__legit=True,
    student__enabled=True,
).annotate(
    num_accepted_all=SubqueryCount(
        "student__user__student__pset",
        filter=Q(status="A") & ~Q(unit__group__name="Dummy Unit"),
    ),
    num_accepted_current=SubqueryCount(
        "student__pset",
        filter=Q(status="A") & ~Q(unit__group__name="Dummy Unit"),
    ),
)
PSET_VENUEQ_INIT_KEYS = (
    "pk",
    "status",
    "feedback",
    "special_notes",
    "student__pk",
    "student__user__first_name",
    "student__user__last_name",
    "student__user__email",
    "student__last_level_seen",
    "hours",
    "clubs",
    "unit__group__name",
    "unit__group__slug",
    "unit__code",
    "next_unit_to_unlock__group__name",
    "next_unit_to_unlock__code",
    "upload__content",
    "num_accepted_all",
    "num_accepted_current",
    "staff_comments",
    "student__reg__aops_username",
    "student__reg__container__semester__end_year",
    "student__reg__country",
    "student__reg__gender",
    "student__reg__graduation_year",
    "student__user__profile__email_on_pset_complete",
)

INQUIRY_VENUEQ_INIT_QUERYSET = UnitInquiry.objects.filter(
    status="INQ_NEW",
    student__semester__active=True,
    student__legit=True,
).annotate(
    unlock_inquiry_count=SubqueryCount(
        "student__unitinquiry",
        filter=Q(action_type="INQ_ACT_UNLOCK"),
    ),
)
INQUIRY_VENUEQ_INIT_KEYS = (
    "action_type",
    "unit__group__name",
    "unit__code",
    "student__user__first_name",
    "student__user__last_name",
    "student__user__email",
    "explanation",
    "created_at",
    "unlock_inquiry_count",
    "student__user__profile__email_on_inquiry_complete",
)
INQUIRY_VENUEQ_AUTO_QUERYSET = UnitInquiry.objects.filter(
    was_auto_processed=True,
    created_at__gte=timezone.now() + timedelta(days=-2),
)
INQUIRY_VENUEQ_AUTO_KEYS = (
    "action_type",
    "unit__group__name",
    "unit__code",
    "student__user__first_name",
    "student__user__last_name",
    "explanation",
    "created_at",
)

SUGGESTION_VENUEQ_INIT_QUERYSET = ProblemSuggestion.objects.filter(status="SUGG_NEW")
SUGGESTION_VENUEQ_INIT_KEYS = (
    "pk",
    "status",
    "eligible",
    "created_at",
    "updated_at",
    "user__first_name",
    "user__last_name",
    "user__email",
    "source",
    "description",
    "hyperlink",
    "statement",
    "solution",
    "comments",
    "acknowledge",
    "weight",
    "unit__group__name",
    "unit__code",
    "staff_comments",
    "user__profile__email_on_suggestion_processed",
)

JOB_VENUEQ_INIT_QUERYSET = Job.objects.filter(progress="JOB_SUB")
JOB_VENUEQ_INIT_KEYS = (
    "pk",
    "folder__name",
    "name",
    "progress",
    "spades_bounty",
    "usd_bounty",
    "payment_preference",
    "hours_estimate",
    "worker_deliverable",
    "worker_notes",
    "assignee__user__email",
    "assignee__user__first_name",
    "assignee__user__last_name",
    "assignee__gmail_address",
    "assignee__twitch_username",
    "assignee__paypal_username",
    "assignee__venmo_handle",
    "assignee__zelle_info",
    "assignee__notes",
    "updated_at",
)

REG_VENUEQ_INIT_QUERYSET = StudentRegistration.objects.filter(
    processed=False,
    container__semester__active=True,
)
REG_VENUEQ_INIT_KEYS = (
    "user__first_name",
    "user__last_name",
    "user__email",
    "created_at",
    "user__profile__email_on_registration_processed",
)


def venueq_handler(action: str, data: JSONData) -> JsonResponse:
    if action == "init":
        output_data: dict[str, Any] = {
            "timestamp": str(timezone.now()),
            "_name": "Root",
            "result": "success",
        }
        output_data["_children"] = [
            {
                "_name": "Problem sets",
                "_children": list(
                    PSET_VENUEQ_INIT_QUERYSET.values(*PSET_VENUEQ_INIT_KEYS)
                ),
            },
            {
                "_name": "Inquiries",
                "inquiries": list(
                    INQUIRY_VENUEQ_INIT_QUERYSET.values(*INQUIRY_VENUEQ_INIT_KEYS)
                ),
                "reading": list(
                    INQUIRY_VENUEQ_AUTO_QUERYSET.values(*INQUIRY_VENUEQ_AUTO_KEYS)
                ),
            },
            {
                "_name": "Suggestions",
                "_children": list(
                    SUGGESTION_VENUEQ_INIT_QUERYSET.values(*SUGGESTION_VENUEQ_INIT_KEYS)
                ),
            },
            {
                "_name": "Jobs",
                "_children": list(
                    JOB_VENUEQ_INIT_QUERYSET.values(*JOB_VENUEQ_INIT_KEYS)
                ),
            },
            {
                "_name": "Regs",
                "registrations": list(
                    REG_VENUEQ_INIT_QUERYSET.values(*REG_VENUEQ_INIT_KEYS)
                ),
            },
        ]
        return JsonResponse(output_data, status=200)
    elif action == "accept_inquiries":
        n = 0
        for inquiry in UnitInquiry.objects.filter(
            status="INQ_NEW",
            student__semester__active=True,
            student__legit=True,
        ):
            inquiry.run_accept()
            n += 1
        if n > 0:
            return JsonResponse({"result": "success", "count": n}, status=200)
        else:
            return JsonResponse({"result": "failed", "count": 0}, status=400)
    elif action == "accept_registrations":
        n = build_students(REG_VENUEQ_INIT_QUERYSET)
        if n > 0:
            return JsonResponse({"result": "success", "count": n}, status=200)
        else:
            return JsonResponse({"result": "failed", "count": 0}, status=400)
    elif action == "grade_problem_set":
        # mark problem set as done
        pset = get_object_or_404(PSet, pk=data["pk"])
        original_status = pset.status
        pset.status = data["status"]
        pset.clubs = data.get("clubs", None)
        pset.hours = data.get("hours", None)
        if "staff_comments" in data:
            if pset.staff_comments:
                pset.staff_comments += "\n\n" + "-" * 40 + "\n\n"
            pset.staff_comments += data["staff_comments"]
        pset.save()
        # mark other problem sets for this (student, unit) no longer eligible
        if pset.status == "A" and pset.unit is not None:
            PSet.objects.filter(
                student__user=pset.student.user, unit=pset.unit
            ).exclude(pk=pset.pk).update(eligible=False)
        # Unlock
        if (
            pset.status == "A"
            and original_status in ("P", "PR")
            and pset.unit is not None
        ):
            # remove the old unit since it's done now
            pset.student.unlocked_units.remove(pset.unit)
            # unlock the unit the student asked for
            if pset.next_unit_to_unlock is not None:
                if pset.student.unlocked_units.count() < 9:
                    pset.student.unlocked_units.add(pset.next_unit_to_unlock)
                else:
                    logging.error(
                        f"{pset.student} somehow already has 9 units "
                        f"after submitting {pset.unit} "
                        f"and trying to unlock {pset.next_unit_to_unlock}."
                    )
        return JsonResponse({"result": "success"}, status=200)
    elif action == "mark_suggestion":
        suggestion = get_object_or_404(ProblemSuggestion, pk=data["pk"])
        suggestion.status = data["status"]
        suggestion.eligible = data["eligible"]
        if "staff_comments" in data:
            if suggestion.staff_comments:
                suggestion.staff_comments += "\n\n" + "-" * 40 + "\n\n"
            suggestion.staff_comments += data["staff_comments"]
        suggestion.save()
        if (
            suggestion.status == "SUGG_OK"
            and data["arch_puid"] is not None
            and not Problem.objects.filter(puid=data["arch_puid"]).exists()
        ):
            Problem.objects.create(puid=data["arch_puid"])
        return JsonResponse({"result": "success"}, status=200)
    elif action == "triage_job":
        if data["progress"] == "JOB_SUB":
            return JsonResponse({"result": "success", "changed": False}, status=200)
        job: Job = Job.objects.get(pk=data["pk"])
        job.progress = data["progress"]
        job.save()
        if data["progress"] == "JOB_VFD" and job.payment_preference == "PREF_INVCRD":
            assert job.assignee is not None
            try:
                invoice = Invoice.objects.get(
                    student__semester__active=True, student__user=job.assignee.user
                )
            except Invoice.DoesNotExist:
                logging.warning(f"Could not get invoice for {job.assignee.user}")
                return JsonResponse({"result": "failed", "changed": False}, status=400)
            else:
                invoice.credits += job.usd_bounty
                invoice.save()
        return JsonResponse({"result": "success", "changed": True}, status=200)
    else:
        raise Exception("No such command")


def discord_handler(action: str, data: JSONData) -> JsonResponse:
    assert action == "register"
    # check whether social account exists
    uid = data["uid"]
    queryset = SocialAccount.objects.filter(uid=uid)
    if (n := len(queryset)) != 1:
        return JsonResponse({"result": "nonexistent", "length": n})

    social = queryset.get()  # get the social account for this; should never 404
    user = social.user
    student = Student.objects.filter(user=user, semester__active=True).first()
    if student is None:
        student = Student.objects.filter(user=user).order_by("-pk").first()
        active = False
    else:
        active = True
    regform = StudentRegistration.objects.filter(user=user).order_by("-pk").first()

    if student is not None:
        logging.info(
            f"Student {student} /register'd with Discord ID {uid}, aka {social.user.username}",
        )
        return JsonResponse(
            {
                "result": "success",
                "user": social.user.username,
                "name": student.name,
                "uid": uid,
                "gender": regform.gender if regform is not None else "?",
                "country": regform.country if regform is not None else "???",
                "num_years": Student.objects.filter(user=user).count(),
                "active": active,
            }
        )
    elif regform is not None:
        return JsonResponse({"result": "pending"})
    else:
        return JsonResponse({"result": "unregistered"})


def problems_handler(action: str, data: JSONData) -> JsonResponse:
    if action not in (
        "get_hints",
        "add_hints",
        "add_many_hints",
    ):
        raise SuspiciousOperation("Invalid command")
    puid = data["puid"].upper()
    problem, _ = Problem.objects.get_or_create(puid=puid)

    if action == "get_hints":
        hints = Hint.objects.filter(problem=problem)
        hint_values = hints.values("keywords", "pk", "number", "content")
        return JsonResponse(
            {
                "hints": list(hint_values),
                "hyperlink": problem.hyperlink,
            }
        )
    elif action == "add_hints":
        hints = Hint.objects.filter(problem=problem)
        existing_hint_numbers = hints.values_list("number", flat=True)
        if "number" in data:
            number = data["number"]
        else:
            number = 0
            while number in existing_hint_numbers:
                number += 10
        hint = Hint.objects.create(
            problem=problem,
            number=number,
            content=data["content"],
            keywords=data.get("keywords", "imported from discord"),
        )
        return JsonResponse({"pk": hint.pk, "number": number})
    elif action == "add_many_hints":
        # update existing hints
        num_deletes = 0
        existing_hints = list(Hint.objects.filter(problem=problem))
        for h in existing_hints:
            for d in data["old_hints"]:
                if d["pk"] == h.pk:
                    h.number = d["number"]
                    h.keywords = d["keywords"]
                    h.content = d["content"]
                    break
            else:
                if data["allow_delete_hints"] is True:
                    h.delete()
                    num_deletes += 1
                else:
                    return JsonResponse(
                        {"msg": f"Couldn't find hint with pk {h.pk}"}, status=400
                    )
        Hint.objects.bulk_update(
            [h for h in existing_hints if h.pk is not None],
            fields=("number", "keywords", "content"),
        )
        # create new hints
        created_hints = Hint.objects.bulk_create(
            Hint(problem=problem, **d) for d in data["new_hints"]
        )
        return JsonResponse(
            {"pks": [h.pk for h in created_hints], "num_deletes": num_deletes}
        )
    else:
        raise SuspiciousOperation("Action not implemented")


def invoice_handler(action: str, data: JSONData) -> JsonResponse:
    del action

    def sanitize(s: str, last: bool = False) -> str:
        return "".join(
            c
            for c in unidecode(s).lower().split(" ")[-1 if last else 0]
            if c in string.ascii_lowercase
        )

    invoices = Invoice.objects.filter(student__semester__active=True)
    invoices = invoices.select_related("student__user")
    field = data["field"]
    assert field in ("adjustment", "extras", "total_paid")
    entries = data["entries"]
    invoices_to_update: list[Invoice] = []
    updated_names_list: list[str] = []
    now = timezone.now()

    for inv in invoices:
        if inv.student.user is not None:
            first_name = sanitize(inv.student.user.first_name)
            last_name = sanitize(inv.student.user.last_name, last=True)
            email = inv.student.user.email.lower()
            pk = inv.student.pk
            keys_to_try = (str(pk), email, f"{first_name}.{last_name}")
            for k in keys_to_try:
                if k in entries:
                    amount = Decimal(entries.pop(k))
                    if abs(getattr(inv, field) - amount) > 0.0001:
                        setattr(inv, field, amount)
                        invoices_to_update.append(inv)
                        updated_names_list.append(
                            f"{inv.student.user.first_name} {inv.student.user.last_name} <{email}>"
                        )
                        inv.updated_at = now

    if field == "total_paid":
        prefetch_related_objects(invoices_to_update, "paymentlog_set")
        for inv in invoices_to_update:
            logs: QuerySet[Invoice] = inv.paymentlog_set.filter(refunded=False)  # type: ignore
            stripe_paid: Union[Decimal, int] = logs.aggregate(s=Sum("amount"))["s"] or 0
            inv.total_paid += stripe_paid

    Invoice.objects.bulk_update(
        invoices_to_update, (field, "updated_at"), batch_size=25
    )
    return JsonResponse(
        {
            "updated_count": len(invoices_to_update),
            "updated_names_list": updated_names_list,
            "entries_remaining": entries,
        }
    )


def arch_url_handler(action: str, data: JSONData) -> JsonResponse:
    del action
    urls_map = data["urls"]
    # update existing problem URL's
    problems_to_update: list[Problem] = []
    for problem in Problem.objects.all():
        puid = problem.puid
        if puid in urls_map and problem.hyperlink != (new_link := urls_map.pop(puid)):
            problem.hyperlink = new_link
            problems_to_update.append(problem)
    Problem.objects.bulk_update(
        problems_to_update,
        fields=("hyperlink",),
        batch_size=25,
    )
    problems_to_create: list[Problem] = [
        Problem(puid=puid, hyperlink=hyperlink) for puid, hyperlink in urls_map.items()
    ]
    Problem.objects.bulk_create(problems_to_create)
    return JsonResponse(
        {
            "updated_count": len(problems_to_update),
            "created_count": len(problems_to_create),
        }
    )


def hanabi_handler(action: str, data: JSONData) -> JsonResponse:
    del action
    contest = HanabiContest.objects.get(pk=data["pk"])

    name_to_pk_dict: dict[str, int] = {}
    eligible_players: list[str] = []
    for d in HanabiPlayer.objects.all().values("pk", "hanab_username"):
        eligible_players.append(d["hanab_username"])
        name_to_pk_dict[d["hanab_username"]] = d["pk"]
    name_to_replay_id_dict: dict[str, int] = {}

    # Create the hanabi replay objects
    replays: list[HanabiReplay] = []

    # first, compute the set of eligible players after disqualifications
    for replay_json in data["replays"]:
        for name in replay_json["players"]:
            if name in eligible_players:
                if name in name_to_replay_id_dict:
                    # Disqualify the player
                    del name_to_replay_id_dict[name]
                    eligible_players.remove(name)
                else:
                    name_to_replay_id_dict[name] = replay_json["replay_id"]

    for replay_json in data["replays"]:
        if all(name not in eligible_players for name in replay_json["players"]):
            continue
        game_score = replay_json["game_score"]
        replay = HanabiReplay(
            contest=contest,
            replay_id=replay_json["replay_id"],
            game_score=game_score,
            turn_count=replay_json["turn_count"],
        )
        replay.spades_score = replay.get_base_spades()

        replays.append(replay)
    assert replays

    # Compute the max score
    max_score = max(r.game_score for r in replays)
    best_turn_count_with_max_score = min(
        r.turn_count for r in replays if r.game_score == max_score
    )

    # Award bonus spades
    for replay in replays:
        if replay.game_score == max_score:
            replay.spades_score += 1
            if replay.turn_count == best_turn_count_with_max_score:
                replay.spades_score += 1

    # Create the replay objects
    HanabiReplay.objects.bulk_create(replays, batch_size=25)

    # ... and re-grab them
    created_replay_data = HanabiReplay.objects.filter(contest=contest).values(
        "pk", "replay_id", "game_score", "turn_count", "spades_score"
    )
    replay_id_to_pk_dict = {
        replay_json["replay_id"]: replay_json["pk"]
        for replay_json in created_replay_data
    }

    participations: list[HanabiParticipation] = [
        HanabiParticipation(
            player_id=name_to_pk_dict[name],
            replay_id=replay_id_to_pk_dict[replay_id],
        )
        for name, replay_id in name_to_replay_id_dict.items()
    ]
    HanabiParticipation.objects.bulk_create(participations, batch_size=25)

    # Finally, mark the contest as processed
    contest.processed = True
    contest.save()

    return JsonResponse(
        {
            "replays": list(created_replay_data),
            "names": name_to_replay_id_dict,
        }
    )


def email_handler(action: str, data: JSONData) -> JsonResponse:
    del action
    del data
    return JsonResponse(
        {
            "students": list(
                Student.objects.filter(
                    semester__active=True,
                    user__profile__email_on_announcement=True,
                    enabled=True,
                ).values(
                    "user__first_name",
                    "user__last_name",
                    "user__username",
                    "user__email",
                )
            )
        }
    )


def opal_handler(action: str, data: JSONData) -> JsonResponse:
    del action
    del data
    return JsonResponse(
        {
            "puzzles": list(
                OpalPuzzle.objects.all().values(
                    "pk",
                    "hunt__slug",
                    "title",
                    "slug",
                    "order",
                    "num_to_unlock",
                    "content",
                    "is_metapuzzle",
                    "answer",
                    "partial_answers",
                    "credits",
                )
            )
        }
    )


def announcement_handler(action: str, data: JSONData) -> JsonResponse:
    del action
    announcement, is_new = Announcement.objects.update_or_create(
        slug=data["slug"],
        defaults={
            "content": data["content"],
            "subject": data["subject"],
        },
    )
    if is_new is False:
        announcement.save()  # need to retrigger markdown render

    return JsonResponse({"is_new": is_new})


def apply_handler(action: str, data: JSONData) -> JsonResponse:
    del action
    au = ApplyUUID.objects.create(uuid=data["uuid"], percent_aid=data["percent_aid"])
    return JsonResponse({"pk": au.pk})


@csrf_exempt
def api(request: HttpRequest) -> JsonResponse:
    if not request.method == "POST":
        raise PermissionDenied("Must use POST")
    try:
        data: JSONData = json.loads(request.body)
    except JSONDecodeError:
        raise SuspiciousOperation("Not valid JSON")

    if "action" not in data:
        raise SuspiciousOperation("You need to provide an action, silly")
    action = data["action"]

    if "token" not in data:
        raise SuspiciousOperation("No token provided")
    elif settings.API_TARGET_HASH is None:
        return JsonResponse({"error": "Not accepting tokens right now"}, status=503)
    elif sha256(data["token"].encode("ascii")).hexdigest() != settings.API_TARGET_HASH:
        return JsonResponse({"error": "🧋"}, status=418)

    if action in (
        "grade_problem_set",
        "accept_registrations",
        "accept_inquiries",
        "mark_suggestion",
        "triage_job",
        "init",
    ):
        return venueq_handler(action, data)
    elif action == "register":
        return discord_handler(action, data)
    elif action in ("get_hints", "add_hints", "add_many_hints"):
        return problems_handler(action, data)
    elif action == "invoice":
        return invoice_handler(action, data)
    elif action == "arch_url_update":
        return arch_url_handler(action, data)
    elif action == "hanabi_results":
        return hanabi_handler(action, data)
    elif action == "email_list":
        return email_handler(action, data)
    elif action == "announcement_write":
        return announcement_handler(action, data)
    elif action == "opal_list":
        return opal_handler(action, data)
    elif action == "apply_uuid":
        return apply_handler(action, data)
    else:
        return JsonResponse({"error": "No such command"}, status=400)


# vim: fdm=indent
