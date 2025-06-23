from django.core.management.base import BaseCommand
from django.db import transaction

from cea_management.models import School, Department, Program

PH_SCHOOLS = [
    {
        "name": "De La Salle-College of Saint Benilde",
        "acronym": "DLS-CSB",
        "address": "2544 Taft Ave, Malate, Manila, 1004 Metro Manila",
        "domain": "@benilde.edu.ph",
        "departments": [
            {
                "name": "School of Management and Information Technology",
                "programs": [
                    "BS in Information Systems",
                    "BS in Interactive Entertainment and Multimedia Computing",
                    "BS in Business Administration major in Computer Applications"
                ]
            }
        ]
    },
    {
        "name": "University of Santo Tomas",
        "acronym": "UST",
        "address": "España Blvd, Sampaloc, Manila, 1008 Metro Manila",
        "domain": "@ust.edu.ph",
        "departments": [
            {
                "name": "College of Information and Computing Sciences",
                "programs": [
                    "BS in Information Technology",
                    "BS in Computer Science"
                ]
            }
        ]
    },
    {
        "name": "De La Salle University",
        "acronym": "DLSU",
        "address": "2401 Taft Ave, Malate, Manila, 1004 Metro Manila",
        "domain": "@dlsu.edu.ph",
        "departments": [
            {
                "name": "College of Computer Studies",
                "programs": [
                    "BS in Computer Science",
                    "BS in Information Systems",
                    "BS in Information Technology"
                ]
            }
        ]
    },
    {
        "name": "Far Eastern University",
        "acronym": "FEU",
        "address": "Nicanor Reyes St, Sampaloc, Manila, 1008 Metro Manila",
        "domain": "@feu.edu.ph",
        "departments": [
            {
                "name": "Institute of Technology",
                "programs": [
                    "BS in Information Technology",
                    "BS in Computer Science"
                ]
            }
        ]
    },
    {
        "name": "Ateneo de Manila University",
        "acronym": "ADMU",
        "address": "Katipunan Ave, Loyola Heights, Quezon City, 1108 Metro Manila",
        "domain": "@ateneo.edu",
        "departments": [
            {
                "name": "Department of Information Systems and Computer Science",
                "programs": [
                    "BS in Computer Science",
                    "BS in Management Information Systems"
                ]
            }
        ]
    }
]


class Command(BaseCommand):
    help = "Populate sample schools, departments, and programs in the Philippines"

    def handle(self, *args, **options):
        for school_data in PH_SCHOOLS:
            self.stdout.write(f"Creating school: {school_data['name']}")
            with transaction.atomic():
                school, _ = School.objects.get_or_create(
                    school_name=school_data["name"],
                    defaults={
                        "school_acronym": school_data["acronym"],
                        "school_address": school_data["address"],
                        "domain": school_data["domain"],
                        "status": "Active"
                    }
                )

                for dept_data in school_data["departments"]:
                    department, _ = Department.objects.get_or_create(
                        school=school,
                        department_name=dept_data["name"]
                    )

                    for program_name in dept_data["programs"]:
                        Program.objects.get_or_create(
                            department=department,
                            program_name=program_name
                        )

        self.stdout.write(self.style.SUCCESS("✅ Successfully populated schools, departments, and programs."))
