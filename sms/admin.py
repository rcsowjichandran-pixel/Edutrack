from django.contrib import admin
from .models import Attendance, Batch, Certificate, Course, Student

admin.site.register(Batch)
admin.site.register(Student)
admin.site.register(Attendance)
admin.site.register(Course)
admin.site.register(Certificate)
