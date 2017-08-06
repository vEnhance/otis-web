from django.contrib import admin
import roster

# Register your models here.

class ActiveFilter(admin.SimpleListFilter):
	title = "Current"
	parameter_name = 'type'
	def lookups(self, request, model_admin):
		return (("current", "Current"), ("past", "Past"),)
	def queryset(self, request, queryset):
		if self.value() is None:
			return queryset
		elif self.value() == "current":
			return queryset.filter(semester__active=True)
		elif self.value() == "past":
			return queryset.filter(semester__active=False)

class StudentInline(admin.TabularInline):
	model = roster.models.Student
	fields = ('user', 'name', 'semester', 'current_unit_index',)
	readonly_fields = ('user', 'name', 'semester',)
	extra = 0

@admin.register(roster.models.TA)
class TAAdmin(admin.ModelAdmin):
	list_display = ('name', 'semester', 'user', 'student_count',)
	inlines=(StudentInline,)
	list_filter=(ActiveFilter,)

@admin.register(roster.models.Student)
class StudentAdmin(admin.ModelAdmin):
	list_display = ('name', 'user', 'semester', 'assistant', 'current_unit_index',)
	ordering = ('semester', 'name', )
	list_filter=(ActiveFilter,)
