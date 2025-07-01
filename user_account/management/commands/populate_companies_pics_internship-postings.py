import json
import random
from pathlib import Path
from django.core.management.base import BaseCommand
from django.core.files import File
from django.utils import timezone
from django.db import transaction

from user_account.models import User, Company
from client_matching.models import PersonInCharge
from client_matching.models import InternshipPosting, KeyTask, MinQualification, Benefit, HardSkillsTagList, \
    SoftSkillsTagList

SEED_ASSETS = Path(__file__).resolve().parent.parent.parent.parent / 'seed_assets'

HARD_SKILLS = [
    {"id": "KS1219N6Z3XQ19V0HSKR", "name": "C# (Programming Language)"},
    {"id": "KS1232D6PH6SBVWWPQWC", "name": "Django (Web Framework)"},
    {"id": "KS1298JH6GHTY72LMNVB", "name": "JavaScript"},
    {"id": "KS1298ABC3DFGHJKLQWE", "name": "React"},
    {"id": "KS1255LPUYX98TZVVCXQ", "name": "Cybersecurity"},
]

SOFT_SKILLS = [
    {"id": "KS120626HMWCXJWJC7VK", "name": "Adaptability"},
    {"id": "KS122556LMQ829GZCCRV", "name": "Communication"},
    {"id": "KS122323VXZ123GZCCRV", "name": "Teamwork"},
    {"id": "KS1299SSQQQ829GHFGRR", "name": "Problem Solving"},
    {"id": "KS1211ASDQWE192BCYUR", "name": "Critical Thinking"},
]

PH_ADDRESSES = [
    "SM Megamall, Metro Manila",
    "Bonifacio Global City, Taguig",
    "UP Diliman, Quezon City",
    "Ortigas Center, Pasig",
    "Ayala Avenue, Makati"
]

TASKS = ["Develop UI components using React", "Collaborate with backend team for API integration"]
QUALIFICATIONS = ["Currently enrolled in BSIT or related field", "Completed at least 3rd year"]
BENEFITS = ["Certificate of Completion", "Meal Allowance"]

COMPANY_IMAGES = {
    "apple": ("Apple-Logo.png", "apple branch center.jpg"),
    "google": ("google logo.webp", "google store.jpg"),
    "microsoft": ("microsoft logo.avif", "microsoft store.jpg"),
    "samsung": ("samsuing.png", "samsung store.avif"),
    "xiaomi": ("XIAOMI.png", "SIAOMI.jpg")
}


class Command(BaseCommand):
    help = "Populate dummy Companies, PICs, and Internship Postings."

    def handle(self, *args, **options):
        companies = ["Xiaomi", "Samsung", "Apple", "Microsoft", "Google"]

        for company_name in companies:
            self.stdout.write(f"Creating company: {company_name}")
            with transaction.atomic():
                slug = company_name.lower()
                user = User.objects.create_user(
                    email=f"{slug}@example.com",
                    password="@A123456",
                    user_role="company"
                )
                user.status = "Active"
                user.save()

                company = Company.objects.create(
                    user=user,
                    company_name=f"{company_name} Philippines",
                    company_address=random.choice(PH_ADDRESSES),
                    company_information=f"{company_name} specializes in tech solutions for Filipino businesses.",
                    company_website_url=f"https://{slug}.ph",
                    business_nature="Technology"
                )

                profile_name, background_name = COMPANY_IMAGES[slug]
                with open(SEED_ASSETS / profile_name, 'rb') as img:
                    company.profile_picture.save(profile_name, File(img), save=True)
                with open(SEED_ASSETS / background_name, 'rb') as bg:
                    company.background_image.save(background_name, File(bg), save=True)

                for i in range(1, 3):
                    PersonInCharge.objects.create(
                        company=company,
                        name=f"{company_name} PIC {i}",
                        position="HR Officer",
                        email=f"{slug}_pic{i}@example.com",
                        mobile_number="09171234567" if i == 1 else "",
                        landline_number="(02) 8123 4567" if i == 2 else ""
                    )

                pics = company.personincharge_set.all()

                for j in range(1, 3):
                    pic = random.choice(pics)
                    posting = InternshipPosting.objects.create(
                        company=company,
                        internship_position=f"{company_name} IT Intern {j}",
                        address=random.choice(PH_ADDRESSES),
                        modality="Onsite",
                        internship_date_start=timezone.now() + timezone.timedelta(days=10),
                        ojt_hours=random.choice([240, 486]),
                        application_deadline=timezone.now() + timezone.timedelta(days=5),
                        person_in_charge=pic,
                        other_requirements="Bring laptop and resume.",
                        is_paid_internship=True,
                        is_only_for_practicum=False,
                        status="Open",
                        latitude=14.5995,
                        longitude=120.9842
                    )

                    for task in TASKS:
                        kt = KeyTask.objects.create(internship_posting=posting, key_task=task)
                        posting.key_tasks.add(kt)

                    for qual in QUALIFICATIONS:
                        q = MinQualification.objects.create(internship_posting=posting, min_qualification=qual)
                        posting.min_qualifications.add(q)

                    for benefit in BENEFITS:
                        b = Benefit.objects.create(internship_posting=posting, benefit=benefit)
                        posting.benefits.add(b)

                    for hs in random.sample(HARD_SKILLS, 2):
                        skill, _ = HardSkillsTagList.objects.get_or_create(lightcast_identifier=hs['id'],
                                                                           defaults={'name': hs['name']})
                        posting.required_hard_skills.add(skill)

                    for ss in random.sample(SOFT_SKILLS, 2):
                        skill, _ = SoftSkillsTagList.objects.get_or_create(lightcast_identifier=ss['id'],
                                                                           defaults={'name': ss['name']})
                        posting.required_soft_skills.add(skill)

                    posting.save()

        self.stdout.write(self.style.SUCCESS("✅ Successfully populated all companies, PICs, and internships."))
