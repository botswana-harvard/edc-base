import sys

from django.contrib.sites.models import Site
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.conf import settings


class SiteModelError(Exception):
    pass


class SiteModelMixin(models.Model):

    site = models.ForeignKey(
        Site, on_delete=models.PROTECT, null=True, editable=False)

    def save(self, *args, **kwargs):
        site = Site.objects.get_current()
        try:
            REVIEWER_SITE_ID = settings.REVIEWER_SITE_ID
        except AttributeError:
            REVIEWER_SITE_ID = 0
        if (int(site.id) == int(REVIEWER_SITE_ID)
                and 'migrate' not in sys.argv):
            raise SiteModelError(
                'Adding and updating data has been disabled. '
                f'See Site configuration. Got {site.name}.')
        else:
            try:
                if not self.site:
                    self.site = Site.objects.get_current()
            except ObjectDoesNotExist:
                self.site = Site.objects.get_current()
        super().save(*args, **kwargs)

    class Meta:
        abstract = True
