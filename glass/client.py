
import requests
import os, os.path, json, re
import pathspec
from pathspec.gitignore import GitIgnorePattern
import logging

try:
    from json.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError

logger = logging.getLogger()

class Glass(object):

    spec = None

    def __init__(self, email, password, domain=None, glass_url=None, config_path=None, **kwargs):
        self.email = email
        self.password = password
        self.glass_url = glass_url

        self.domain = domain
        self.site = {
            "domain": domain,
            "url": "http://{}.sites.glass".format(self.domain)
        }

        site = kwargs.pop('site', None)
        if site and site['domain'] and not self.domain:
            self.domain = site['domain']
            self.site['url'] = "http://{}.sites.glass".format(self.domain)

        self.exclude = kwargs.pop('exclude', [])
        self.exclude.append('.glass')

        self.config_path = config_path

        if not glass_url:
            self.glass_url = os.getenv('GLASS_PATROL_URL', 'https://website.glass/')

        if self.glass_url[-1] != '/':
            self.glass_url += '/'

        if self.site and self.site.get("domain") and not self.site.get("url"):
            self.site["url"] = "http://{}.sites.glass".format(self.site["domain"])

        if self.site and self.site.get('url') and (self.site['url'][-1] != '/'):
            self.site['url'] += '/'

    def __setattr__(self, key, val):
        old_domain = '------'
        if getattr(self, 'domain', None):
            old_domain = self.domain
        super(Glass, self).__setattr__(key, val)
        if key == 'domain' and getattr(self, 'site', None) and self.site.get('url', ''):
            self.site["url"] = self.site["url"].replace(old_domain, val)

    def patrol_req(self, path, method="GET", **kwargs):
        response = requests.request(
            method,
            "{}{}".format(self.glass_url, path),
            auth=(self.email, self.password),
            **kwargs
        )
        try:
            return response.json()
        except JSONDecodeError:
            logger.error('Error returning json response', exc_info=True)

    def site_req(self, path, method="GET", auth=True, **kwargs):
        response = requests.request(
            method,
            "{}{}".format(self.site["url"], path),
            auth=(self.email, self.password) if auth else None,
            **kwargs
        )
        try:
            assert response.status_code in [200, 201]
        except AssertionError:
            logger.error('Non 200 response', exc_info=True)

        try:
            return response.json()
        except JSONDecodeError:
            logger.error('Error returning json response', exc_info=True)

    def list_sites(self):
        return self.patrol_req('sites.json')

    def get_settings(self):
        return self.site_req('siteapi/settings.json')

    def put_settings(self, settings):
        return self.site_req('siteapi/settings.json', 'post', json=settings)

    def list_files(self):
        return self.site_req('siteapi/files.json')

    def put_file(self, path, buffer, content_type="text/plain"):
        new_path = os.path.dirname(path)
        new_file = os.path.basename(path)
        if len(new_path) and new_path[0] == '/':
            new_path = new_path[1:]

        resp = requests.post(
            "{}siteapi/upload".format(self.site['url']),
            files=[
                ('file', (new_file, buffer, content_type)),
            ], data={
                "path": new_path
            }, auth=(self.email, self.password))

        try:
            assert resp.status_code == 200
        except AssertionError:
            logger.error('Response Code Error in putting file', exc_info=True)
            return False
        return resp.json()[0]

    def get_file(self, path):
        return requests.get(
            "{}{}".format(self.site["url"], path),
        ).content

    def get_site_resource(self, path):
        return requests.get(
            "{}{}".format(self.site["url"], path),
        )

    def list_pages(self):
        return self.site_req('siteapi/pages.json')

    def new_page(self,
                 url,
                 title="", # Shorthand for adding a title. On the backend this is saved as content['title'] on the page.
                 template="", # Path to template e.g "templates/base.html"
                 content=None, # dict that can be safely json encoded, or JSON encoded string.
                 parent=None, # parent path (without leading /), if applicable, e.g "blog/"
                 published=None, # date or datetime, defaults to NOW on the server
                 created=None, # date or datetime, defaults to NOW on the server
                 redirect=None, # If filled, `url` will redirect to `redirect` for all requests.
                 author=None, # email address of existing site user, defaults to None
                 ):
        page_data = {
            "url": url,
            "title": title,
            "template": template,
            "redirect": redirect,
            "parent": parent,
            "author": author,
        }
        if content is None:
            content = {}
        if isinstance(content, str):
            page_data['content'] = content
        else:
            page_data['content'] = json.dumps(content)

        if created:
            page_data['created'] = created.isoformat(),
        if published:
            page_data['published'] = published.isoformat()

        return self.site_req('siteapi/new_page', "POST", data=page_data)

    def get_page(self, path):
        return self.site_req(path + '.json')

    def put_page(self, path, data):
        return self.site_req(path + '.json', "POST", json=data)

    def query_data(self, **kwargs):
        """
        Valid kwargs:
            category
            bucket
            record
            order_by - created, modified, category, bucket, record (or add - to any of those to go in reverse) and ? for random
        """
        return self.site_req('siteapi/data/query', "get", params=kwargs)

    def get_data(self, id):
        return self.site_req('siteapi/data/{}.json'.format(id))

    def put_data(self, id, data):
        return self.site_req('siteapi/data/{}.json'.format(id), 'post', json=data)

    def create_data(self, id, data):
        return self.site_req('siteapi/data/new.json'.format(id), 'post', json=data)

    def load_ignore(self):
        """
        For local development, loads .glass/ignore (same format as gitignore) to exclude files
        from watch and put operations.
        """
        try:
            with open(os.path.join(self.config_path, ".glass", "ignore"), 'r') as fb:
                self.ignore_spec = pathspec.PathSpec.from_lines(pathspec.GitIgnorePattern, fb)
        except IOError:
            self.ignore_spec = pathspec.PathSpec.from_lines(pathspec.GitIgnorePattern, "")

        self.ignore_spec.patterns.append(GitIgnorePattern('.glass'))
        self.ignore_spec.patterns.append(GitIgnorePattern('.git'))
        self.ignore_spec.patterns.append(GitIgnorePattern('.DS_Store'))
        self.ignore_spec.patterns.append(GitIgnorePattern('.hg'))
        self.ignore_spec.patterns.append(GitIgnorePattern('.svn'))
        self.ignore_spec.patterns.append(GitIgnorePattern('.idea'))
        self.ignore_spec.patterns.append(GitIgnorePattern('func.*'))