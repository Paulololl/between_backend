from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Populates all users with dummy entries'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Populating Companies, Pics, Internship-Postings'))
        call_command('populate_companies_pics_internship-postings')

        self.stdout.write(self.style.NOTICE('Populating Schools, Departments, Programs'))
        call_command('populate_schools_departments_programs')

        self.stdout.write(self.style.NOTICE('Populating CEA, Coordinators'))
        call_command('populate_cea_coordinators')

        self.stdout.write(self.style.NOTICE('Populating all 4 users with demo accounts'))
        call_command('populate_demo_users')

        self.stdout.write(self.style.NOTICE('Making system admin group'))
        call_command('create_system_admin_group')

        self.stdout.write(self.style.SUCCESS("All scripts ran successfully."))