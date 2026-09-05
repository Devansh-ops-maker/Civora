from django.core.management.base import BaseCommand, CommandError

from challenges.models import Challenge
from startups.models import Startup

from intelligence.ollama import OllamaError
from intelligence.services import update_challenge_embedding, update_startup_embedding


class Command(BaseCommand):
    help = "Generate missing (or all, with --force) Startup Radar embeddings."

    def add_arguments(self, parser):
        parser.add_argument("--startups", action="store_true", help="Refresh startup embeddings")
        parser.add_argument("--challenges", action="store_true", help="Refresh challenge embeddings")
        parser.add_argument("--force", action="store_true", help="Regenerate existing embeddings")

    def handle(self, *args, **options):
        do_startups = options["startups"] or not options["challenges"]
        do_challenges = options["challenges"] or not options["startups"]
        force = options["force"]

        try:
            if do_startups:
                startups = Startup.objects.all() if force else Startup.objects.filter(embedding__isnull=True)
                for startup in startups.iterator():
                    update_startup_embedding(startup)
                    self.stdout.write(self.style.SUCCESS(f"Startup embedded: {startup.company_name}"))

            if do_challenges:
                challenges = Challenge.objects.all() if force else Challenge.objects.filter(embedding__isnull=True)
                for challenge in challenges.iterator():
                    update_challenge_embedding(challenge)
                    self.stdout.write(self.style.SUCCESS(f"Challenge embedded: {challenge.title}"))
        except OllamaError as exc:
            raise CommandError(str(exc)) from exc
