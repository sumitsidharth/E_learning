from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from Eduverse.models import User, TeacherProfile, StudentProfile, Subject, Notes, Purchase
from django.utils.text import slugify
import random
from decimal import Decimal

class Command(BaseCommand):
    help = 'Seed the database with sample data for testing and development.'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding data...')

        # 1. Create Admin
        admin, created = User.objects.get_or_create(
            username='admin',
            email='admin@eduverse.com',
            role=User.Role.ADMIN,
            is_staff=True,
            is_superuser=True
        )
        if created:
            admin.set_password('admin123')
            admin.save()
            self.stdout.write(self.style.SUCCESS('Admin created: admin/admin123'))

        # 2. Create Subjects
        subjects_data = [
            ('Mathematics', 'Calculus, Algebra, and Geometry.'),
            ('Science', 'Physics, Chemistry, and Biology essentials.'),
            ('History', 'World history and ancient civilizations.'),
            ('Computer Science', 'Programming, Data Structures, and AI.')
        ]
        subjects = []
        for name, desc in subjects_data:
            subject, created = Subject.objects.get_or_create(
                name=name,
                defaults={'description': desc}
            )
            subjects.append(subject)

        # 3. Create Teachers
        teachers = []
        for i in range(1, 4):
            username = f'teacher{i}'
            email = f'teacher{i}@eduverse.com'
            teacher, created = User.objects.get_or_create(
                username=username,
                email=email,
                role=User.Role.TEACHER
            )
            if created:
                teacher.set_password('teacher123')
                teacher.save()
                # Create and approve profile
                profile = TeacherProfile.objects.get(user=teacher)
                profile.is_approved = True
                profile.bio = f"Experienced educator in {subjects[i-1].name}."
                profile.save()
            teachers.append(teacher)

        # 4. Create Notes for each teacher (5 each)
        all_notes = []
        for i, teacher in enumerate(teachers):
            for j in range(1, 6):
                title = f"{subjects[i].name} Module {j}"
                price = Decimal(random.choice([0.00, 9.99, 14.99, 19.99, 29.99]))
                note = Notes.objects.create(
                    title=title,
                    description=f"Comprehensive study material for {title}. This covers all key concepts.",
                    teacher=teacher,
                    subject=subjects[i],
                    price=price,
                    is_published=True
                )
                # Add dummy file
                note.file.save(f'sample_note_{i}_{j}.pdf', ContentFile(b"Sample PDF content for testing."))
                all_notes.append(note)

        # 5. Create Students
        students = []
        for i in range(1, 6):
            username = f'student{i}'
            email = f'student{i}@eduverse.com'
            student, created = User.objects.get_or_create(
                username=username,
                email=email,
                role=User.Role.STUDENT
            )
            if created:
                student.set_password('student123')
                student.save()
            students.append(student)

        # 6. Create Random Purchases (2-3 per student)
        paid_notes = [n for n in all_notes if not n.is_free]
        for student in students:
            purchased_count = random.randint(2, 3)
            notes_to_buy = random.sample(paid_notes, min(purchased_count, len(paid_notes)))
            for note in notes_to_buy:
                Purchase.objects.get_or_create(
                    student=student,
                    note=note,
                    defaults={'amount_paid': note.price, 'stripe_payment_id': f'ch_fake_{random.randint(1000, 9999)}'}
                )
                # Update teacher earnings
                teacher_profile = TeacherProfile.objects.get(user=note.teacher)
                teacher_profile.total_earnings += note.price
                teacher_profile.save()

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {len(subjects)} subjects, {len(teachers)} teachers, {len(all_notes)} notes, and {len(students)} students.'))
