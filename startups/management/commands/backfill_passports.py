from django.core.management.base import BaseCommand

from accounts.models import StartupProfile
from startups.models import Startup


class Command(BaseCommand):
    help = (
        "Create a Startup Passport for any STARTUP user whose StartupProfile "
        "predates the startups app / signal (e.g. accounts created during "
        "Phase 1 testing before Phase 2 existed)."
    )

    def handle(self, *args, **options):
        created_count = 0
        for profile in StartupProfile.objects.select_related("user").all():
            _, created = Startup.objects.get_or_create(
                user=profile.user,
                defaults=dict(
                    company_name=profile.company_name,
                    description=profile.description,
                    website=profile.website,
                    industry=profile.industry,
                    technologies=profile.technologies,
                    location=profile.location,
                    founded_year=profile.founded_year,
                    team_size=profile.team_size,
                ),
            )
            if created:
                created_count += 1
                self.stdout.write(f"Created passport for {profile.company_name} ({profile.user.email})")

        self.stdout.write(self.style.SUCCESS(f"Done. {created_count} passport(s) created."))
