"""
Management command to upload all existing local media files to Cloudinary.
Run this once after setting up Cloudinary to migrate existing images.
Usage: python manage.py upload_to_cloudinary
"""
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from django.apps import apps
from django.db import models
import cloudinary
import cloudinary.uploader


class Command(BaseCommand):
    help = 'Upload all existing local media files to Cloudinary and update database references'

    def handle(self, *args, **options):
        # Check if Cloudinary is configured
        cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME')
        api_key = os.environ.get('CLOUDINARY_API_KEY')
        api_secret = os.environ.get('CLOUDINARY_API_SECRET')

        if not all([cloud_name, api_key, api_secret]):
            self.stderr.write(self.style.ERROR('Cloudinary credentials not set in environment variables.'))
            return

        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
        )

        media_root = settings.MEDIA_ROOT
        self.stdout.write(self.style.NOTICE(f'Media root: {media_root}'))

        # Find all models with ImageField or FileField
        all_models = apps.get_models()
        upload_count = 0
        skip_count = 0
        error_count = 0

        for model in all_models:
            file_fields = [
                f for f in model._meta.get_fields()
                if isinstance(f, (models.ImageField, models.FileField))
            ]
            if not file_fields:
                continue

            self.stdout.write(self.style.NOTICE(
                f'\nProcessing model: {model.__name__} (fields: {[f.name for f in file_fields]})'
            ))

            for obj in model.objects.all():
                for field in file_fields:
                    field_file = getattr(obj, field.name)
                    if not field_file or not field_file.name:
                        continue

                    # Skip if already a Cloudinary URL (already uploaded)
                    if field_file.name.startswith('http') or 'cloudinary' in str(field_file.name):
                        skip_count += 1
                        continue

                    # Build the local file path
                    local_path = os.path.join(media_root, field_file.name)
                    if not os.path.exists(local_path):
                        self.stderr.write(self.style.WARNING(
                            f'  File not found locally: {local_path} (skipping)'
                        ))
                        skip_count += 1
                        continue

                    try:
                        # Upload to Cloudinary
                        # Use the relative path (without extension) as the public_id
                        public_id = os.path.splitext(field_file.name)[0]
                        result = cloudinary.uploader.upload(
                            local_path,
                            public_id=public_id,
                            resource_type='auto',
                            overwrite=True,
                        )

                        # Update the field to point to Cloudinary
                        # django-cloudinary-storage expects just the public_id path
                        setattr(obj, field.name, result['public_id'])
                        obj.save(update_fields=[field.name])

                        upload_count += 1
                        self.stdout.write(self.style.SUCCESS(
                            f'  Uploaded: {field_file.name} -> {result["public_id"]}'
                        ))
                    except Exception as e:
                        error_count += 1
                        self.stderr.write(self.style.ERROR(
                            f'  Error uploading {field_file.name}: {e}'
                        ))

        self.stdout.write(self.style.SUCCESS(
            f'\nDone! Uploaded: {upload_count}, Skipped: {skip_count}, Errors: {error_count}'
        ))
