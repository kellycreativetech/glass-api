#!/usr/bin/env python
from glass import Glass
from io import StringIO
from os import environ
import datetime
import json
import os.path
import uuid
import unittest
import re
import requests
import sys

try:
    from urllib.parse import urlparse
except ImportError: #py2
    from urlparse import urlparse


class APITests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.shared_domain_root = environ.get('GLASS_SHARED_DOMAIN_ROOT', 'temp.servee.com')
        cls.domain = environ.get('GLASS_DOMAIN', None)
        cls.email = environ.get('GLASS_EMAIL', None)
        cls.password = environ.get('GLASS_PASSWORD', None)

        if not cls.email or not cls.password or not cls.domain:
            raise Exception('Requires following environment vars to be set: GLASS_DOMAIN, GLASS_EMAIL, GLASS_PASSWORD')

        cls.glass = Glass(cls.email, cls.password, cls.domain)

    def test_settings(self):
        settings = self.glass.get_settings()

        # Obvious plant is obvious.
        self.assertEqual(settings['domain'], self.domain)
        response = requests.get('http://{}.{}'.format(self.domain, self.shared_domain_root))
        self.assertEqual(response.status_code, 200)

        # new domain doesn't work.
        settings['domain'] += uuid.uuid4().hex[:3]
        response = requests.get('http://{}.{}'.format(settings['domain'], self.shared_domain_root))
        self.assertEqual(response.status_code, 404)

        # Flip them
        self.glass.put_settings(settings)
        self.glass.domain = settings['domain']
        response = requests.get('http://{}.{}'.format(settings['domain'], self.shared_domain_root))
        self.assertEqual(response.status_code, 200)
        response = requests.get('http://{}.{}'.format(self.domain, self.shared_domain_root))
        self.assertEqual(response.status_code, 404)

        # ok now put it back
        settings['domain'] = self.domain
        self.glass.put_settings(settings)
        self.glass.domain = self.domain
        response = requests.get('http://{}.{}'.format(self.domain, self.shared_domain_root))
        self.assertEqual(response.status_code, 200)

    def test_sites(self):
        sites = self.glass.list_sites()
        found_site = False
        for site in sites:
            if site['domain'] == self.domain:
                found_site = True
        self.assertTrue(found_site)

    def test_pages(self):
        orig_pages = self.glass.list_pages()
        path = 'some-page-%s' % uuid.uuid4().hex[:16]
        self.glass.new_page(
            path
        )
        self.assertEqual(len(orig_pages) + 1, len(self.glass.list_pages()))

        page = self.glass.get_page(path)
        self.assertEqual(page['content'], {"title": ""})

        page['content']['title'] = 'Sample Title'
        self.glass.put_page(path, page)

        self.assertEqual(self.glass.get_page(path)['content'], page['content'])

    def test_files(self):
        orig_files = self.glass.list_files()
        dir_path = os.path.dirname(os.path.realpath(__file__))
        new_path = os.path.join(dir_path, 'space.jpg')
        gen_path = 'uploads/{}/space.jpg'.format(uuid.uuid4().hex[:16])
        with open(new_path, 'rb') as fb:
            new_file = self.glass.put_file(gen_path, fb, 'image/jpg')

        new_files = self.glass.list_files()
        self.assertEqual(len(new_files), len(orig_files) + 1)
        self.assertEqual(new_file['name'], 'space.jpg')
        self.assertEqual(new_file['filelink'], '/' + gen_path)

        found = False
        for n in new_files:
            if n['path'] == gen_path:
                found = True

        self.assertTrue(found)


if __name__ == '__main__':
    python_version = sys.version_info[0]
    if python_version < 3:
        unittest.main()

    else:
        out = StringIO()
        runner = unittest.TextTestRunner(stream=out, descriptions=True, verbosity=1)

        start = datetime.datetime.utcnow()
        main = unittest.main(
            testRunner=runner,
            exit=False
        )
        end = datetime.datetime.utcnow()
        microseconds = (start - end).microseconds

        out.seek(0)
        results = out.read()
        success = 'FAILED' not in results

        counts = re.search('Ran (\d+) test', results)
        test_count = int(counts.groups()[0])

        if environ.get('SLACK_URL'):
            requests.post(
                environ['SLACK_URL'],
                data=json.dumps({
                    "username": "Python API Tests",
                    "icon_emoji": ":snake:" if success else ":no_entry:",
                    "channel": "glass-tests",
                    "text": """{out}
                        """.format(
                        out=results,
                    ),
                })
            )

        # Send run data to elasticsearch
        if environ.get('ELASTIC_URL'):
            resp = requests.post("{url}/internal/pythonapi/".format(**{
                "url": environ['ELASTIC_URL'],
            }),
                 data=json.dumps({
                     "results": results,
                     "microseconds": microseconds,
                     "timestamp": end.isoformat(),
                     "success": success,
                     "test_count": test_count,
                 }),
                 auth=(environ['ELASTIC_USERNAME'], environ['ELASTIC_PASSWORD'])
            )

        sys.stderr.write(results)
        sys.exit(0 if success else 1)
