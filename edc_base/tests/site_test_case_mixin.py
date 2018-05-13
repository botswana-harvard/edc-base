from django.contrib.sites.models import Site


class SiteTestCaseMixin:

    fqdn = 'clinicedc.org'

    default_sites = [
        (10, 'mochudi', 'mochudi'),
        (20, 'molepolole', 'molepolole'),
        (30, 'lobatse', 'lobatse'),
        (40, 'gaborone', 'gaborone'),
        (50, 'karakobis', 'karakobis')]

    @property
    def site_names(self):
        return [s[1] for s in self.default_sites]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Site.objects.all().delete()
        for site_id, site_name, _ in cls.default_sites:
            Site.objects.create(
                pk=site_id, name=site_name, domain=f'{site_name}.{cls.fqdn}')

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        Site.objects.all().delete()
