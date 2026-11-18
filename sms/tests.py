from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Attendance, Batch, Certificate, Course, Student


class CourseCertificateModelTests(TestCase):
    def setUp(self):
        batch = Batch.objects.create(name='Spring 2026', start_date='2026-03-01')
        self.student = Student.objects.create(
            first_name='Alex',
            last_name='Morgan',
            email='alex@example.com',
            phone_number='5551234567',
            batch=batch,
        )
        self.course = Course.objects.create(
            name='Python Fundamentals',
            description='Core Python programming concepts.',
        )

    def test_student_can_be_enrolled_in_multiple_courses(self):
        another_course = Course.objects.create(
            name='Data Science',
            description='Introductory data science.',
        )
        self.student.courses.add(self.course, another_course)

        self.assertEqual(
            set(self.student.courses.all()),
            {self.course, another_course},
        )
        self.assertEqual(str(self.course), 'Python Fundamentals')

    def test_certificate_links_student_course_and_issue_date(self):
        issued_date = timezone.localdate()
        certificate = Certificate.objects.create(
            student=self.student,
            course=self.course,
            date_issued=issued_date,
        )

        self.assertEqual(certificate.student, self.student)
        self.assertEqual(certificate.course, self.course)
        self.assertEqual(certificate.date_issued, issued_date)
        self.assertEqual(str(certificate), 'Alex Morgan - Python Fundamentals')


class StudentRegistrationTests(TestCase):
    def setUp(self):
        self.batch = Batch.objects.create(name='Spring 2026', start_date='2026-03-01')

    def test_root_page_displays_student_list(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sms/student_list.html')

    def test_student_page_has_navigation_to_main_sections(self):
        response = self.client.get(reverse('sms:student_list'))

        self.assertContains(response, reverse('sms:student_list'))
        self.assertContains(response, reverse('sms:register_student'))
        self.assertContains(response, reverse('sms:batch_list'))

    def test_registration_form_includes_courses(self):
        Course.objects.create(
            name='Python Fundamentals',
            description='Core Python programming concepts.',
        )
        response = self.client.get(reverse('sms:register_student'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="courses"')

    def test_existing_student_course_selection_can_be_updated(self):
        course = Course.objects.create(
            name='Python Fundamentals',
            description='Core Python programming concepts.',
        )
        student = Student.objects.create(
            first_name='Alex',
            last_name='Morgan',
            email='alex@example.com',
            phone_number='5551234567',
            batch=self.batch,
        )

        response = self.client.post(
            reverse('sms:edit_student', args=[student.pk]),
            {
                'first_name': 'Alex',
                'last_name': 'Morgan',
                'email': 'alex@example.com',
                'phone_number': '5551234567',
                'batch': self.batch.pk,
                'courses': [course.pk],
            },
        )

        self.assertRedirects(response, reverse('sms:student_list'))
        self.assertEqual(list(student.courses.all()), [course])


    def test_registration_page_renders_form(self):
        response = self.client.get(reverse('sms:register_student'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Register student')
        self.assertContains(response, 'name="batch"')

    def test_valid_registration_saves_student_and_redirects(self):
        response = self.client.post(
            reverse('sms:register_student'),
            {
                'first_name': 'Alex',
                'last_name': 'Morgan',
                'email': 'alex@example.com',
                'phone_number': '5551234567',
                'batch': self.batch.pk,
            },
        )

        self.assertRedirects(response, reverse('sms:student_list'))
        self.assertTrue(
            Student.objects.filter(
                first_name='Alex', last_name='Morgan', batch=self.batch
            ).exists()
        )

    def test_student_list_displays_student_details(self):
        Student.objects.create(
            first_name='Alex',
            last_name='Morgan',
            email='alex@example.com',
            phone_number='5551234567',
            batch=self.batch,
        )

        response = self.client.get(reverse('sms:student_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alex Morgan')
        self.assertContains(response, 'alex@example.com')
        self.assertContains(response, 'Spring 2026')


class BatchManagementTests(TestCase):
    def setUp(self):
        self.batch = Batch.objects.create(
            name='Spring 2026',
            start_date='2026-03-01',
        )

    def test_batch_overview_shows_date_student_count_and_actions(self):
        Student.objects.create(
            first_name='Alex',
            last_name='Morgan',
            email='alex@example.com',
            phone_number='5551234567',
            batch=self.batch,
        )
        earlier_batch = Batch.objects.create(
            name='Winter 2026',
            start_date='2026-01-15',
        )

        response = self.client.get(reverse('sms:batch_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mar 01, 2026')
        self.assertContains(response, 'Take attendance')
        self.assertContains(response, 'View report')
        batches = list(response.context['batches'])
        self.assertEqual(batches[0], earlier_batch)
        self.assertEqual(batches[1].student_count, 1)

    def test_add_batch_saves_batch_and_returns_to_overview(self):
        response = self.client.post(
            reverse('sms:create_batch'),
            {'name': 'Summer 2026', 'start_date': '2026-06-15'},
        )

        self.assertRedirects(response, reverse('sms:batch_list'))
        self.assertTrue(
            Batch.objects.filter(name='Summer 2026', start_date='2026-06-15').exists()
        )

    def test_add_batch_page_renders_date_input(self):
        response = self.client.get(reverse('sms:create_batch'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="name"')
        self.assertContains(response, 'name="start_date"')
        self.assertContains(response, 'type="date"')


class AttendanceTakingTests(TestCase):
    def setUp(self):
        self.batch = Batch.objects.create(name='Spring 2026', start_date='2026-03-01')
        self.student = Student.objects.create(
            first_name='Alex',
            last_name='Morgan',
            email='alex@example.com',
            phone_number='5551234567',
            batch=self.batch,
        )

    def test_batch_list_links_to_attendance(self):
        response = self.client.get(reverse('sms:batch_list'))

        self.assertContains(
            response, reverse('sms:take_attendance', args=[self.batch.pk])
        )

    def test_attendance_page_renders_students_and_status_choices(self):
        response = self.client.get(
            reverse('sms:take_attendance', args=[self.batch.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alex Morgan')
        self.assertContains(response, 'Present')
        self.assertContains(response, 'Absent')
        self.assertContains(response, 'Late')

    def test_post_records_attendance_for_each_student(self):
        second_student = Student.objects.create(
            first_name='Sam',
            last_name='Lee',
            email='sam@example.com',
            phone_number='5557654321',
            batch=self.batch,
        )

        response = self.client.post(
            reverse('sms:take_attendance', args=[self.batch.pk]),
            {
                f'student-{self.student.pk}-status': Attendance.Status.PRESENT,
                f'student-{second_student.pk}-status': Attendance.Status.LATE,
            },
        )

        self.assertRedirects(response, reverse('sms:batch_list'))
        self.assertEqual(Attendance.objects.count(), 2)
        self.assertEqual(
            set(Attendance.objects.values_list('status', flat=True)),
            {Attendance.Status.PRESENT, Attendance.Status.LATE},
        )
        self.assertEqual(
            set(Attendance.objects.values_list('date', flat=True)),
            {timezone.localdate()},
        )

    def test_existing_attendance_prevents_duplicate_records(self):
        Attendance.objects.create(
            student=self.student,
            date=timezone.localdate(),
            status=Attendance.Status.PRESENT,
        )

        response = self.client.post(
            reverse('sms:take_attendance', args=[self.batch.pk]),
            {f'student-{self.student.pk}-status': Attendance.Status.ABSENT},
            follow=True,
        )

        self.assertContains(response, 'already been recorded today')
        self.assertEqual(Attendance.objects.count(), 1)

    def test_invalid_status_does_not_save_attendance(self):
        response = self.client.post(
            reverse('sms:take_attendance', args=[self.batch.pk]),
            {f'student-{self.student.pk}-status': 'Excused'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Attendance.objects.count(), 0)
        self.assertContains(response, 'Select a valid choice')


class AttendanceReportTests(TestCase):
    def setUp(self):
        self.batch = Batch.objects.create(name='Spring 2026', start_date='2026-03-01')
        self.student = Student.objects.create(
            first_name='Alex',
            last_name='Morgan',
            email='alex@example.com',
            phone_number='5551234567',
            batch=self.batch,
        )

    def test_batch_report_counts_statuses_and_includes_students_without_records(self):
        no_records_student = Student.objects.create(
            first_name='Sam',
            last_name='Lee',
            email='sam@example.com',
            phone_number='5557654321',
            batch=self.batch,
        )
        today = timezone.localdate()
        Attendance.objects.create(
            student=self.student,
            date=today - timedelta(days=2),
            status=Attendance.Status.PRESENT,
        )
        Attendance.objects.create(
            student=self.student,
            date=today - timedelta(days=1),
            status=Attendance.Status.PRESENT,
        )
        Attendance.objects.create(
            student=self.student,
            date=today,
            status=Attendance.Status.ABSENT,
        )
        Attendance.objects.create(
            student=self.student,
            date=today,
            status=Attendance.Status.LATE,
        )

        response = self.client.get(
            reverse('sms:attendance_report', args=[self.batch.pk])
        )

        self.assertEqual(response.status_code, 200)
        summaries = {
            entry['student'].pk: entry
            for entry in response.context['attendance_summary']
        }
        self.assertEqual(
            {key: summaries[self.student.pk][key] for key in ('present', 'absent', 'late')},
            {'present': 2, 'absent': 1, 'late': 1},
        )
        self.assertEqual(
            {key: summaries[no_records_student.pk][key] for key in ('present', 'absent', 'late')},
            {'present': 0, 'absent': 0, 'late': 0},
        )
        self.assertContains(response, 'Alex Morgan')

    def test_student_report_shows_attendance_in_chronological_order(self):
        today = timezone.localdate()
        first_date = today - timedelta(days=2)
        last_date = today - timedelta(days=1)
        Attendance.objects.create(
            student=self.student,
            date=last_date,
            status=Attendance.Status.ABSENT,
        )
        Attendance.objects.create(
            student=self.student,
            date=first_date,
            status=Attendance.Status.PRESENT,
        )

        response = self.client.get(
            reverse('sms:student_attendance_report', args=[self.student.pk])
        )

        self.assertEqual(response.status_code, 200)
        records = list(response.context['attendance_records'])
        self.assertEqual(
            [record.date for record in records],
            [first_date, last_date],
        )
        self.assertContains(response, 'Present')
        self.assertContains(response, 'Absent')

    def test_student_list_links_to_individual_attendance_report(self):
        response = self.client.get(reverse('sms:student_list'))

        self.assertContains(
            response,
            reverse('sms:student_attendance_report', args=[self.student.pk]),
        )


class CertificateIssuanceTests(TestCase):
    def setUp(self):
        batch = Batch.objects.create(name='Spring 2026', start_date='2026-03-01')
        self.student = Student.objects.create(
            first_name='Alex',
            last_name='Morgan',
            email='alex@example.com',
            phone_number='5551234567',
            batch=batch,
        )
        self.course = Course.objects.create(
            name='Python Fundamentals',
            description='Core Python programming concepts.',
        )
        self.student.courses.add(self.course)

    def test_issue_certificate_downloads_pdf_and_creates_record(self):
        response = self.client.get(
            reverse(
                'sms:issue_certificate',
                args=[self.student.pk, self.course.pk],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment;', response['Content-Disposition'])
        pdf_content = b''.join(response.streaming_content)
        self.assertTrue(pdf_content.startswith(b'%PDF'))
        self.assertTrue(pdf_content.rstrip().endswith(b'%%EOF'))
        certificate = Certificate.objects.get(student=self.student, course=self.course)
        self.assertEqual(certificate.date_issued, timezone.localdate())

    def test_repeated_request_does_not_create_or_redate_certificate(self):
        issued_date = timezone.localdate() - timedelta(days=1)
        Certificate.objects.create(
            student=self.student,
            course=self.course,
            date_issued=issued_date,
        )

        response = self.client.get(
            reverse(
                'sms:issue_certificate',
                args=[self.student.pk, self.course.pk],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Certificate.objects.count(), 1)
        self.assertEqual(
            Certificate.objects.get().date_issued,
            issued_date,
        )

    def test_certificate_is_not_issued_for_non_enrolled_course(self):
        other_course = Course.objects.create(
            name='Data Science',
            description='An unrelated course.',
        )

        response = self.client.get(
            reverse(
                'sms:issue_certificate',
                args=[self.student.pk, other_course.pk],
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Certificate.objects.count(), 0)

    def test_student_list_links_to_enrolled_course_certificate(self):
        response = self.client.get(reverse('sms:student_list'))

        self.assertContains(
            response,
            reverse(
                'sms:issue_certificate',
                args=[self.student.pk, self.course.pk],
            ),
        )
        self.assertContains(response, 'Issue Certificate')
