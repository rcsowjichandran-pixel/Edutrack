from django.db import models


class Batch(models.Model):
    name = models.CharField(max_length=100)
    start_date = models.DateField()

    def __str__(self):
        return self.name


class Course(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()

    def __str__(self):
        return self.name


class Student(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='students')
    courses = models.ManyToManyField(Course, related_name='students', blank=True)

    def __str__(self):
        return f'{self.first_name} {self.last_name}'


class Certificate(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='certificates'
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name='certificates'
    )
    date_issued = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'course'],
                name='unique_student_course_certificate',
            ),
        ]

    def __str__(self):
        return f'{self.student} - {self.course}'


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'Present', 'Present'
        ABSENT = 'Absent', 'Absent'
        LATE = 'Late', 'Late'

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='attendance_records'
    )
    date = models.DateField()
    status = models.CharField(max_length=7, choices=Status.choices)

    def __str__(self):
        return f'{self.student} - {self.date}: {self.status}'
