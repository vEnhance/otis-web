from django.contrib import admin
from import_export import fields, resources, widgets
from import_export.admin import ImportExportModelAdmin

from .models import Semester, UnitGroup, Unit

# Register your models here.


class SemesterResource(resources.ModelResource):
	class Meta:
		skip_unchanged = True
		model = Semester
		fields = (
			'id',
			'name',
			'active',
			'show_invoices',
			'exam_family',
		)


@admin.register(Semester)
class SemesterAdmin(ImportExportModelAdmin):
	list_display = (
		'name',
		'id',
		'active',
		'show_invoices',
		'exam_family',
	)
	search_fields = ('name', )
	resource_class = SemesterResource


class UnitIEResource(resources.ModelResource):
	group_name = fields.Field(
		column_name="group_name",
		attribute="group",
		widget=widgets.ForeignKeyWidget(UnitGroup, "name")
	)

	class Meta:
		skip_unchanged = True
		model = Unit
		fields = (
			'id',
			'group_name',
			'code',
			'position',
		)
		export_order = (
			'id',
			'group_name',
			'code',
			'position',
		)


@admin.register(Unit)
class UnitAdmin(ImportExportModelAdmin):
	list_display = (
		'group',
		'code',
		'id',
		'list_display_position',
	)
	list_filter = ('group__subject', )
	search_fields = ('group__name', 'code')
	autocomplete_fields = ('group', )
	ordering = ('position', )
	resource_class = UnitIEResource
	list_per_page = 150
	list_max_show_all = 400


class UnitInline(admin.TabularInline):
	model = Unit
	fields = (
		'code',
		'position',
	)
	extra = 0


class UnitGroupIEResource(resources.ModelResource):
	class Meta:
		skip_unchanged = True
		model = UnitGroup
		fields = (
			'id',
			'subject',
			'name',
			'slug',
			'description',
		)
		export_order = (
			'id',
			'subject',
			'name',
			'slug',
			'description',
		)


@admin.register(UnitGroup)
class UnitGroupAdmin(ImportExportModelAdmin):
	list_display = (
		'name',
		'subject',
		'id',
		'description',
	)
	search_fields = (
		'name',
		'description',
	)
	list_filter = ('subject', )
	resource_class = UnitGroupIEResource
	list_per_page = 150
	list_max_show_all = 400
	inlines = (UnitInline, )
