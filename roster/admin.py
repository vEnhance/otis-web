from django.contrib import admin
import roster

# Register your models here.


class StudentInline(admin.TabularInline):
	model = roster.models.Student
	fields = ('user', 'semester', 'current_unit_index',)

@admin.register(roster.models.TA)
class TAAdmin(admin.ModelAdmin):
	list_display = ('user', 'name', 'student_count',)
	inlines=(StudentInline,)

@admin.register(roster.models.Student)
class StudentAdmin(admin.ModelAdmin):
	list_display = ('user', 'name', 'semester', 'assistant', 'current_unit_index',)
