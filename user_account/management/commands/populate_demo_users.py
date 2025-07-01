import random
import os
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.core.files import File
from django.utils.timezone import now

from user_account.models import User, Applicant, Company, CareerEmplacementAdmin, OJTCoordinator
from cea_management.models import School, Department, Program
from client_matching.models import HardSkillsTagList, SoftSkillsTagList
from user_account.filepaths import applicant_resume, applicant_enrollment_record, company_profile_picture, company_background_image

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

DUMMY_FILE = Path(__file__).resolve().parent.parent.parent.parent / "seed_assets" / "landscape-placeholder.svg"


class Command(BaseCommand):
    help = "Populate 1 school applicant, 1 gmail applicant, 1 company, 1 CEA, and 1 OJT Coordinator (all in DLS-CSB)"

    def handle(self, *args, **options):
        with transaction.atomic():
            school = School.objects.prefetch_related('departments__programs').get(school_acronym="DLS-CSB")
            department = random.choice(school.departments.all())
            program = random.choice(department.programs.all())

            for s in IT_SOFT_SKILLS:
                SoftSkillsTagList.objects.get_or_create(
                    lightcast_identifier=s['id'],
                    defaults={'name': s['name']}
                )

            for h in IT_HARD_SKILLS:
                HardSkillsTagList.objects.get_or_create(
                    lightcast_identifier=h['id'],
                    defaults={'name': h['name']}
                )

            def create_user(email, role):
                self.stdout.write(f"Creating {role} user: {email}")
                user = User.objects.create_user(
                    email=email,
                    password='@A123456',
                    user_role=role,
                    status='Active'
                )
                return user

            def get_skills():
                hards = [
                    HardSkillsTagList.objects.get(lightcast_identifier=s['id'])
                    for s in random.sample(IT_HARD_SKILLS, 2)
                ]
                softs = [
                    SoftSkillsTagList.objects.get(lightcast_identifier=s['id'])
                    for s in random.sample(IT_SOFT_SKILLS, 2)
                ]
                return hards, softs

            with open(DUMMY_FILE, 'rb') as f:
                resume_file = File(f, name="resume-placeholder.svg")
                enrollment_file = File(f, name="enrollment-placeholder.svg")

                school_user = create_user("applicant_school@benilde.edu.ph", "applicant")
                hards, softs = get_skills()
                school_app = Applicant.objects.create(
                    user=school_user,
                    first_name="applicant",
                    last_name="school",
                    middle_initial="A.",
                    address=random.choice(ADDRESSES),
                    latitude=14.5995,
                    longitude=120.9842,
                    quick_introduction="I'm a school applicant",
                    preferred_modality="Hybrid",
                    mobile_number="09" + ''.join(str(random.randint(0, 9)) for _ in range(9)),
                    school=school,
                    department=department,
                    program=program,
                    resume=resume_file,
                    enrollment_record=enrollment_file
                )
                school_app.hard_skills.set(hards)
                school_app.soft_skills.set(softs)

            with open(DUMMY_FILE, 'rb') as f:
                gmail_resume = File(f, name="resume-placeholder.svg")

                gmail_user = create_user("applicant_personal@gmail.com", "applicant")
                hards, softs = get_skills()
                gmail_app = Applicant.objects.create(
                    user=gmail_user,
                    first_name="applicant",
                    last_name="personal",
                    middle_initial="B.",
                    address=random.choice(ADDRESSES),
                    latitude=14.6095,
                    longitude=120.9800,
                    quick_introduction="I'm a gmail applicant",
                    preferred_modality="Onsite",
                    mobile_number="09" + ''.join(str(random.randint(0, 9)) for _ in range(9)),
                    academic_program="BS Information Technology",
                    resume=gmail_resume
                )
                gmail_app.hard_skills.set(hards)
                gmail_app.soft_skills.set(softs)

            with open(DUMMY_FILE, 'rb') as f:
                company_profile = File(f, name="company-profile.svg")
                company_bg = File(f, name="company-bg.svg")

                company_user = create_user("company@example.com", "company")
                company = Company.objects.create(
                    user=company_user,
                    company_name="company",
                    company_address=random.choice(ADDRESSES),
                    company_information="A demo company",
                    business_nature="IT Services",
                    company_website_url="https://company.example.com",
                    profile_picture=company_profile,
                    background_image=company_bg
                )

            cea_user = create_user("cea@example.com", "cea")
            CareerEmplacementAdmin.objects.create(
                user=cea_user,
                school=school
            )

            coord_user = create_user("ojtcoordinator@example.com", "coordinator")
            OJTCoordinator.objects.create(
                user=coord_user,
                department=department,
                program=program,
                first_name="ojtcoordinator",
                last_name="admin",
                middle_initial="D.",
                endorsements_responded=0
            )

        self.stdout.write(self.style.SUCCESS("✅ All demo users created successfully."))