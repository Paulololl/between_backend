import random
import uuid
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
import json

from user_account.models import User, Applicant
from cea_management.models import School, Department, Program
from client_matching.models import HardSkillsTagList, SoftSkillsTagList

IT_HARD_SKILLS = [
    {"id": "KS1219N6Z3XQ19V0HSKR", "name": "C# (Programming Language)"},
    {"id": "KS1232D6PH6SBVWWPQWC", "name": "Django (Web Framework)"},
    {"id": "KS1298JH6GHTY72LMNVB", "name": "JavaScript"},
    {"id": "KS1298ABC3DFGHJKLQWE", "name": "React"},
    {"id": "KS1255LPUYX98TZVVCXQ", "name": "Cybersecurity"},
]

IT_SOFT_SKILLS = [
    {"id": "KS120626HMWCXJWJC7VK", "name": "Adaptability"},
    {"id": "KS122556LMQ829GZCCRV", "name": "Communication"},
    {"id": "KS122323VXZ123GZCCRV", "name": "Teamwork"},
    {"id": "KS1299SSQQQ829GHFGRR", "name": "Problem Solving"},
    {"id": "KS1211ASDQWE192BCYUR", "name": "Critical Thinking"},
]

ADDRESSES = [
    "Wakas, Bocaue, Bulacan",
    "Diliman, Quezon City",
    "Sta. Mesa, Manila",
    "Sampaloc, Manila",
    "Taft Ave, Manila",
    "BGC, Taguig"
]


class Command(BaseCommand):
    help = "Populate 8 dummy applicants (5 .edu.ph, 3 gmail)"

    def handle(self, *args, **kwargs):
        with transaction.atomic():
            schools = {s.school_acronym: s for s in School.objects.prefetch_related('departments__programs')}

            applicants_data = [
                # Institutional (.edu.ph) - with school, department, program
                {
                    "first_name": "Alex",
                    "last_name": "Santos",
                    "middle_initial": "R.",
                    "applicant_email": "alex.santos@benilde.edu.ph",
                    "school_acronym": "DLS-CSB",
                    "academic_program": None
                },
                {
                    "first_name": "Jamie",
                    "last_name": "Reyes",
                    "middle_initial": "T.",
                    "applicant_email": "jamie.reyes@ust.edu.ph",
                    "school_acronym": "UST",
                    "academic_program": None
                },
                {
                    "first_name": "Miguel",
                    "last_name": "Tan",
                    "middle_initial": "L.",
                    "applicant_email": "miguel.tan@dlsu.edu.ph",
                    "school_acronym": "DLSU",
                    "academic_program": None
                },
                {
                    "first_name": "Erika",
                    "last_name": "Cruz",
                    "middle_initial": "B.",
                    "applicant_email": "erika.cruz@feu.edu.ph",
                    "school_acronym": "FEU",
                    "academic_program": None
                },
                {
                    "first_name": "Leo",
                    "last_name": "Garcia",
                    "middle_initial": "D.",
                    "applicant_email": "leo.garcia@ateneo.edu.ph",
                    "school_acronym": "ADMU",
                    "academic_program": None
                },
                # Gmail (manual academic_program only)
                {
                    "first_name": "Isabel",
                    "last_name": "Lopez",
                    "middle_initial": "M.",
                    "applicant_email": "isabel.lopez@gmail.com",
                    "academic_program": "BS Information Technology"
                },
                {
                    "first_name": "Kevin",
                    "last_name": "Chua",
                    "middle_initial": "N.",
                    "applicant_email": "kevin.chua@gmail.com",
                    "academic_program": "BS Computer Science"
                },
                {
                    "first_name": "Trisha",
                    "last_name": "Lim",
                    "middle_initial": "P.",
                    "applicant_email": "trisha.lim@gmail.com",
                    "academic_program": "BS Information Systems"
                }
            ]

            for data in applicants_data:
                email = data["applicant_email"]
                is_institutional = email.endswith(".edu.ph")

                self.stdout.write(f"Creating applicant user: {email}")

                user = User.objects.create_user(
                    email=email,
                    password="@A123456",
                    user_role="applicant"
                )
                user.status = "Active"
                user.save()

                # Resolve hard and soft skill objects
                selected_hard_skills = random.sample(IT_HARD_SKILLS, 2)
                selected_soft_skills = random.sample(IT_SOFT_SKILLS, 2)

                hard_skill_objs = [
                    HardSkillsTagList.objects.get(lightcast_identifier=skill["id"])
                    for skill in selected_hard_skills
                ]
                soft_skill_objs = [
                    SoftSkillsTagList.objects.get(lightcast_identifier=skill["id"])
                    for skill in selected_soft_skills
                ]

                applicant_kwargs = dict(
                    user=user,
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    middle_initial=data["middle_initial"],
                    address=random.choice(ADDRESSES),
                    quick_introduction="I'm excited to intern in IT!",
                    preferred_modality="Hybrid",
                    mobile_number="09" + "".join(str(random.randint(0, 9)) for _ in range(9)),
                )

                if is_institutional:
                    school = schools.get(data["school_acronym"])
                    if school:
                        dept = random.choice(school.departments.all())
                        prog = random.choice(dept.programs.all())
                        applicant_kwargs.update(
                            school=school,
                            department=dept,
                            program=prog,
                            academic_program=None
                        )
                else:
                    applicant_kwargs.update(
                        academic_program=data["academic_program"]
                    )

                applicant = Applicant.objects.create(**applicant_kwargs)
                applicant.hard_skills.set(hard_skill_objs)
                applicant.soft_skills.set(soft_skill_objs)

        self.stdout.write(self.style.SUCCESS("8 Applicants successfully created."))
