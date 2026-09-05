from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import StartupProfile

from .models import Startup


@receiver(post_save, sender=StartupProfile)
def create_startup_passport(sender, instance, created, **kwargs):
    """
    Every STARTUP user automatically gets a Startup Passport the moment
    they register, seeded from their registration profile. The passport
    then evolves independently as the startup builds out its capabilities,
    evidence, and pilot history — it is the object used for matching,
    evaluation, and the Trust Graph, not the lightweight account profile.
    """
    if not created:
        return

    Startup.objects.get_or_create(
        user=instance.user,
        defaults=dict(
            company_name=instance.company_name,
            description=instance.description,
            website=instance.website,
            industry=instance.industry,
            technologies=instance.technologies,
            location=instance.location,
            founded_year=instance.founded_year,
            team_size=instance.team_size,
        ),
    )
