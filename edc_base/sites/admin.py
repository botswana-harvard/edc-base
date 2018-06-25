from django.conf import settings


class ReviewerSiteSaveError(Exception):
    pass


class ModelAdminSiteMixin:

    def save_model(self, request, obj, form, change):
        if 'django.contrib.sites' in settings.INSTALLED_APPS:
            try:
                REVIEWER_SITE_ID = settings.REVIEWER_SITE_ID
            except AttributeError:
                REVIEWER_SITE_ID = 0
            if int(request.site.id) == int(REVIEWER_SITE_ID):
                raise ReviewerSiteSaveError('Reviewers may not update data.')
        super().save_model(request, obj, form, change)
