from io import BytesIO

from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from .forms import AttendanceForm, BatchForm, StudentForm
from .models import Attendance, Batch, Certificate, Course, Student


def register_student(request):
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('sms:student_list')
    else:
        form = StudentForm()

    return render(request, 'sms/register_student.html', {'form': form})


def student_list(request):
    students = Student.objects.select_related('batch').prefetch_related('courses')
    return render(request, 'sms/student_list.html', {'students': students})


def edit_student(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    if request.method == 'POST':
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            return redirect('sms:student_list')
    else:
        form = StudentForm(instance=student)

    return render(request, 'sms/edit_student.html', {'form': form, 'student': student})


def batch_list(request):
    batches = Batch.objects.annotate(student_count=Count('students')).order_by(
        'start_date', 'name'
    )
    return render(request, 'sms/batch_list.html', {'batches': batches})


def create_batch(request):
    if request.method == 'POST':
        form = BatchForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Batch created successfully.')
            return redirect('sms:batch_list')
    else:
        form = BatchForm()

    return render(request, 'sms/batch_form.html', {'form': form})


def take_attendance(request, batch_id):
    batch = get_object_or_404(Batch, pk=batch_id)
    today = timezone.localdate()

    if Attendance.objects.filter(student__batch=batch, date=today).exists():
        messages.error(request, f'Attendance for {batch.name} has already been recorded today.')
        return redirect('sms:batch_list')

    students = list(
        Student.objects.filter(batch=batch).order_by('last_name', 'first_name', 'pk')
    )
    if request.method == 'POST' and not students:
        messages.error(request, f'There are no students in {batch.name}.')
        return redirect('sms:batch_list')

    attendance_forms = [
        {
            'student': student,
            'form': AttendanceForm(
                request.POST if request.method == 'POST' else None,
                prefix=f'student-{student.pk}',
            ),
        }
        for student in students
    ]

    if request.method == 'POST':
        forms_are_valid = True
        for entry in attendance_forms:
            if not entry['form'].is_valid():
                forms_are_valid = False

        if forms_are_valid:
            with transaction.atomic():
                locked_batch = Batch.objects.select_for_update().get(pk=batch.pk)
                if Attendance.objects.filter(
                    student__batch=locked_batch, date=today
                ).exists():
                    messages.error(
                        request,
                        f'Attendance for {batch.name} has already been recorded today.',
                    )
                    return redirect('sms:batch_list')

                Attendance.objects.bulk_create(
                    [
                        Attendance(
                            student=entry['student'],
                            date=today,
                            status=entry['form'].cleaned_data['status'],
                        )
                        for entry in attendance_forms
                    ]
                )

            messages.success(request, f'Attendance recorded for {batch.name}.')
            return redirect('sms:batch_list')

    return render(
        request,
        'sms/take_attendance.html',
        {
            'batch': batch,
            'attendance_forms': attendance_forms,
            'today': today,
        },
    )


def attendance_report(request, batch_id):
    batch = get_object_or_404(Batch, pk=batch_id)
    students = Student.objects.filter(batch=batch).order_by(
        'last_name', 'first_name', 'pk'
    )
    summaries = {
        student.pk: {
            'student': student,
            'present': 0,
            'absent': 0,
            'late': 0,
        }
        for student in students
    }

    attendance_counts = (
        Attendance.objects.filter(student__batch=batch)
        .values('student_id', 'status')
        .annotate(total=Count('pk'))
    )
    for attendance_count in attendance_counts:
        status = attendance_count['status'].lower()
        summaries[attendance_count['student_id']][status] = attendance_count['total']

    return render(
        request,
        'sms/attendance_report.html',
        {'batch': batch, 'attendance_summary': list(summaries.values())},
    )


def student_attendance_report(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    attendance_records = student.attendance_records.order_by('date', 'pk')
    return render(
        request,
        'sms/student_attendance_report.html',
        {'student': student, 'attendance_records': attendance_records},
    )


def issue_certificate(request, student_id, course_id):
    student = get_object_or_404(
        Student.objects.prefetch_related('courses'), pk=student_id
    )
    course = get_object_or_404(student.courses.all(), pk=course_id)
    certificate, _ = Certificate.objects.get_or_create(
        student=student,
        course=course,
        defaults={'date_issued': timezone.localdate()},
    )

    pdf_buffer = BytesIO()
    page_width, page_height = landscape(letter)
    pdf = canvas.Canvas(pdf_buffer, pagesize=(page_width, page_height))
    pdf.setTitle(f'{course.name} certificate for {student}')
    pdf.setAuthor('EduTrack')

    pdf.setStrokeColor(colors.HexColor('#1e3a8a'))
    pdf.setLineWidth(3)
    pdf.rect(30, 30, page_width - 60, page_height - 60)
    pdf.setStrokeColor(colors.HexColor('#bfdbfe'))
    pdf.setLineWidth(1)
    pdf.rect(40, 40, page_width - 80, page_height - 80)

    pdf.setFillColor(colors.HexColor('#1e3a8a'))
    pdf.setFont('Times-Bold', 30)
    pdf.drawCentredString(page_width / 2, page_height - 130, 'CERTIFICATE')
    pdf.setFont('Times-Roman', 18)
    pdf.drawCentredString(page_width / 2, page_height - 165, 'OF COMPLETION')

    pdf.setFillColor(colors.HexColor('#334155'))
    pdf.setFont('Helvetica', 13)
    pdf.drawCentredString(page_width / 2, page_height - 220, 'This certificate is proudly presented to')

    name_lines = simpleSplit(str(student), 'Times-Bold', 27, page_width - 120)
    pdf.setFillColor(colors.HexColor('#172554'))
    pdf.setFont('Times-Bold', 27)
    name_y = page_height - 270
    for line in name_lines:
        pdf.drawCentredString(page_width / 2, name_y, line)
        name_y -= 34

    course_lines = simpleSplit(course.name, 'Helvetica-Bold', 18, page_width - 120)
    pdf.setFillColor(colors.HexColor('#334155'))
    pdf.setFont('Helvetica-Bold', 18)
    course_y = name_y - 10
    for line in course_lines:
        pdf.drawCentredString(page_width / 2, course_y, line)
        course_y -= 24

    pdf.setFont('Helvetica', 12)
    pdf.drawCentredString(
        page_width / 2,
        105,
        f'Issued on {certificate.date_issued.strftime("%B %d, %Y")}',
    )
    pdf.save()
    pdf_buffer.seek(0)

    return FileResponse(
        pdf_buffer,
        as_attachment=True,
        filename=f'certificate-{student.pk}-{course.pk}.pdf',
        content_type='application/pdf',
    )
