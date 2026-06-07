from django.contrib import admin

from .models import OIMEAttempt, OIMEComment, OIMEProposal, OIMESolverRole


@admin.register(OIMEProposal)
class OIMEProposalAdmin(admin.ModelAdmin[OIMEProposal]):
    list_display = ["__str__", "author", "subject", "difficulty", "created_at"]
    list_filter = ["subject", "difficulty"]
    search_fields = ["author__username", "statement"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(OIMESolverRole)
class OIMESolverRoleAdmin(admin.ModelAdmin[OIMESolverRole]):
    list_display = ["user", "is_serious"]
    list_filter = ["is_serious"]
    search_fields = ["user__username"]


@admin.register(OIMEAttempt)
class OIMEAttemptAdmin(admin.ModelAdmin[OIMEAttempt]):
    list_display = ["user", "proposal", "status", "wrong_answers", "solve_time_seconds", "started_at"]
    list_filter = ["status"]
    search_fields = ["user__username"]
    readonly_fields = ["started_at"]


@admin.register(OIMEComment)
class OIMECommentAdmin(admin.ModelAdmin[OIMEComment]):
    list_display = ["author", "proposal", "created_at"]
    search_fields = ["author__username", "content"]
    readonly_fields = ["created_at"]
