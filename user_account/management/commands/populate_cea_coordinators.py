import random
from django.core.management.base import BaseCommand
from django.db import transaction

from user_account.models import User, CareerEmplacementAdmin, OJTCoordinator
from cea_management.models import School, Department, Program


class Command(BaseCommand):
    help = "Populate 1 CEA per school and 2 OJT Coordinators per school with unique department/program."

    def handle(self, *args, **options):
        with transaction.atomic():
            schools = School.objects.prefetch_related('departments__programs').all()

            for school in schools:
                cea_email = f"cea_{school.school_acronym.lower()}{school.domain}"
                cea_user = User.objects.create_user(
                    email=cea_email,
                    password='@A123456',
                    user_role='cea'
                )
                cea_user.status = 'Active'
                cea_user.save()

                cea = CareerEmplacementAdmin.objects.create(user=cea_user, school=school)
                self.stdout.write(self.style.SUCCESS(f"Created CEA for {school.school_name} - {cea_email}"))

                departments = list(school.departments.all())
                if not departments:
                    self.stdout.write(
                        self.style.WARNING(f"No departments found for {school.school_name}, skipping coordinators.")
                    )
                    continue

                used_depts = set()

                for i in range(2):  # Aim for 2 coordinators
                    available_depts = [d for d in departments if d.pk not in used_depts]
                    if not available_depts:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Not enough unique departments for 2 coordinators in {school.school_name}, only created {i}.")
                        )
                        break

                    dept = random.choice(available_depts)
                    used_depts.add(dept.pk)

                    programs = list(dept.programs.all())
                    program = random.choice(programs) if programs else None

                    coord_email = f"coordinator{i + 1}_{school.school_acronym.lower()}{school.domain}"
                    coord_user = User.objects.create_user(
                        email=coord_email,
                        password='@A123456',
                        user_role='coordinator'
                    )
                    coord_user.status = 'Active'
                    coord_user.save()

                    OJTCoordinator.objects.create(
                        user=coord_user,
                        department=dept,
                        program=program,
                        first_name=f"Coordinator{i + 1}",
                        last_name=school.school_acronym,
                        middle_initial=random.choice(['A', 'B', 'C', 'D', 'E']),
                        endorsements_responded=0
                    )

                    self.stdout.write(self.style.SUCCESS(
                        f"Created Coordinator: {coord_email} | Dept: {dept.department_name} | Program: {program.program_name if program else 'N/A'}"
                    ))

        self.stdout.write(self.style.SUCCESS("✅ All CEAs and OJT Coordinators created."))
