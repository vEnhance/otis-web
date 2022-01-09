# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from dashboard.models import BonusLevel, BonusLevelUnlock, PalaceCarving, QuestComplete  # NOQA

from .models import Achievement, AchievementUnlock, Level, ProblemSuggestion, PSet, SemesterDownloadFile, UploadedFile  # NOQA


@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
	list_display = (
		'id',
		'content',
		'created_at',
		'description',
		'benefactor',
		'unit',
		'category',
		'owner',
	)
	search_fields = ('description', )
	list_filter = ('category', )
	list_per_page = 30
	autocomplete_fields = (
		'benefactor',
		'unit',
		'owner',
	)


@admin.register(SemesterDownloadFile)
class SemesterDownloadFileAdmin(admin.ModelAdmin):
	list_display = (
		'id',
		'semester',
		'content',
		'created_at',
		'description',
	)
	search_fields = ('description', )
	list_filter = ('semester', )
	list_per_page = 30


@admin.register(PSet)
class PSetAdmin(admin.ModelAdmin):
	list_display = (
		'approved',
		'student',
		'unit',
		'hours',
		'clubs',
	)
	search_fields = (
		'unit__group__name',
		'student__user__first_name',
		'student__user__last_name',
		'feedback',
		'special_notes',
	)
	list_filter = (
		'approved',
		'student__assistant',
		'student__track',
		'student__semester__active',
		'student__semester',
	)
	list_display_links = (
		'student',
		'unit',
	)
	list_per_page = 30

	def approve_pset(self, request: HttpRequest, queryset: QuerySet[PSet]):
		for pset in queryset:
			if pset.next_unit_to_unlock is not None:
				pset.student.unlocked_units.add(pset.next_unit_to_unlock)
			if pset.unit is not None:
				pset.student.unlocked_units.remove(pset.unit)
		queryset.update(approved=True)

	def reject_pset(self, request: HttpRequest, queryset: QuerySet[PSet]):
		queryset.update(approved=False)

	actions = [
		'approve_pset',
		'reject_pset',
	]


@admin.register(ProblemSuggestion)
class ProblemSuggestionAdmin(admin.ModelAdmin):
	list_display = (
		'id',
		'user',
		'source',
		'description',
		'acknowledge',
		'eligible',
		'resolved',
	)
	search_fields = (
		'user__first_name',
		'user__last_name',
		'unit__group__name',
		'source',
		'description',
		'statement',
		'solution',
		'comments',
	)
	list_filter = (
		'eligible',
		'resolved',
		'unit__group',
	)
	autocomplete_fields = (
		'user',
		'unit',
	)
	list_per_page = 50

	def mark_eligible(self, request: HttpRequest, queryset: QuerySet[ProblemSuggestion]):
		queryset.update(eligible=True)

	def mark_uneligible(self, request: HttpRequest, queryset: QuerySet[ProblemSuggestion]):
		queryset.update(eligible=False)

	actions = [
		'mark_eligible',
		'mark_uneligible',
	]


class LevelIEResource(resources.ModelResource):
	class Meta:
		skip_unchanged = True
		model = Level
		fields = ('id', 'threshold', 'name')


@admin.register(Level)
class LevelAdmin(ImportExportModelAdmin):
	list_display = (
		'threshold',
		'name',
	)
	search_fields = ('name', )
	resource_class = LevelIEResource


class AchievementIEResource(resources.ModelResource):
	class Meta:
		skip_unchanged = True
		model = Level
		fields = (
			'code',
			'name',
			'diamonds',
			'active',
			'description',
		)


@admin.register(Achievement)
class AchievementAdmin(ImportExportModelAdmin):
	list_display = ('code', 'name', 'diamonds', 'active', 'description', 'image')
	search_fields = ('code', 'description')
	list_filter = ('active', )
	resource_class = AchievementIEResource


@admin.register(AchievementUnlock)
class AchievementUnlockAdmin(admin.ModelAdmin):
	list_display = ('user', 'achievement', 'timestamp')
	list_filter = ('achievement__active', )
	autocomplete_fields = ('user', )


@admin.register(QuestComplete)
class QuestCompleteAdmin(admin.ModelAdmin):
	list_display = (
		'pk',
		'title',
		'student',
		'spades',
		'timestamp',
		'category',
	)
	autocomplete_fields = ('student', )
	list_filter = (
		'student__semester',
		'category',
	)


@admin.register(BonusLevel)
class BonusLevelAdmin(admin.ModelAdmin):
	list_display = ('pk', 'group', 'level', 'active')
	autocomplete_fields = ('group', )
	list_filter = ('active', )
	search_fields = ('group__name', )


@admin.register(BonusLevelUnlock)
class BonusLevelUnlockAdmin(admin.ModelAdmin):
	list_display = ('pk', 'timestamp', 'student', 'bonus')
	autocomplete_fields = ('student', 'bonus')
	list_filter = ('student__semester__active', )


@admin.register(PalaceCarving)
class PalaceCarvingAdmin(admin.ModelAdmin):
	list_display = (
		'display_name',
		'message',
		'created_at',
	)
