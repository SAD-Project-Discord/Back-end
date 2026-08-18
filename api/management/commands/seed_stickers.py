from django.core.management.base import BaseCommand
from api.services.stickers import seed_official_sticker_packs


class Command(BaseCommand):
    help = "Seed official sticker packs and stickers into database."

    def handle(self, *args, **options):
        seed_official_sticker_packs()
        self.stdout.write(self.style.SUCCESS("Successfully seeded official sticker packs and stickers."))
