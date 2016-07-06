#!/usr/bin/env python
__title__ = 'glass-cli'
__version__ = '0.9.0'
__build__ = 0x000900
__author__ = 'Servee LLC - Issac Kelly'
__license__ = 'Apache 2.0'
__copyright__ = 'Copyright 2016 Servee LLC'

import click
import requests
import os, os.path, json, mimetypes, fnmatch, hashlib, time, re
import pathspec
from pathspec.gitignore import GitIgnorePattern
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from opbeat import Client
from opbeat.handlers.logging import OpbeatHandler


### Please do not abuse these credentials. Please change them if you copy this work.
### For your own sake and mine...
client = Client(
    organization_id='80ea519a2fa64c9db8c6902d37f4c120',
    app_id='ca7c90603a',
    secret_token='9991f61aede8ddcfd1db4671085739312fa49852',
)
handler = OpbeatHandler(client)
import logging

logger = logging.getLogger()
logger.addHandler(handler)


def mkdir_p(path):
    if path and not os.path.exists(path):
        os.makedirs(path)

class Glass(object):

    spec = None

    def __init__(self, email, password, glass_url=None, site=None, config_path=None, **kwargs):
        self.email = email
        self.password = password
        self.glass_url = glass_url

        self.site = site
        self.exclude = kwargs.pop('exclude', [])
        self.exclude.append('.glass')

        self.config_path = config_path

        if not glass_url:
            self.glass_url = os.getenv('GLASS_PATROL_URL', 'https://glass.servee.com/')

        if self.glass_url[-1] != '/':
            self.glass_url += '/'

        if self.site and self.site.get("domain") and not self.site.get("url"):
            self.site["url"] = "http://{}.temp.servee.com".format(self.site["domain"])

        if self.site and self.site.get('url') and (self.site['url'][-1] != '/'):
            self.site['url'] += '/'

        if self.site and self.site.get('domain'):
            self.site['domain'].replace('temp.servee.com', '')
            self.site['domain'].replace('lvh.me:8000', '')

    def patrol_req(self, path, method="GET"):
        response = requests.request(
            method,
            "{}{}".format(self.glass_url, path),
            auth=(self.email, self.password),
        )
        try:
            return response.json()
        except Exception:
            logger.error('Error returning json response', exc_info=True)

    def site_req(self, path, method="GET", auth=True):
        response = requests.request(
            method,
            "{}{}".format(self.site["url"], path),
            auth=(self.email, self.password) if auth else None,

        )
        return response.json()

    def list_sites(self):
        return self.patrol_req('sites.json')

    def list_remote_staticfiles(self):
        return self.patrol_req('sites/{}/files.json'.format(self.site['domain']))

    def get_site_resource(self, path):
        return requests.get(
            "{}{}".format(self.site["url"], path),
        )

    @classmethod
    def load_config(cls, ctx, path=None):
        def _config_path(path):
            if os.path.exists(os.path.join(path, '.glass')):
                return path

            dir = os.path.dirname(path)
            print(dir)
            if dir == '/':
                return None
            
            # Windows
            if re.match(r'[A-Z]:\\', dir):
                return None

            return _config_path(dir)

        if not path:
            path = os.getcwd()

        config_path = _config_path(path)
        if not config_path:
            click.confirm("Could not find a .glass config folder. Would you like to make one now?", abort=True)
            ctx.invoke(configure)

        else:
            if not os.path.exists(os.path.join(config_path, ".glass", "config")):
                click.confirm("The path `.glass` path exists, but there is no config file. Would you like to make one now?", abort=True)
                ctx.invoke(configure)

            if os.getcwd() is not config_path:
                click.echo("Changing working directory to glass root at : {}".format(config_path))
                os.chdir(config_path)

            with open(os.path.join(config_path, ".glass", "config"), 'r') as fb:
                buffer = fb.read()
                try:
                    cfg_dict = json.loads(buffer)
                except ValueError:
                    logger.error('Error parsing json file', exc_info=True)
                    click.echo("Your glass config is not a valid json file. Maybe try checking it at: http://jsonlint.com/")
                    click.confirm("Would you like to send your config to jsonlint now?", abort=True)
                    import webbrowser
                    from urllib.parse import quote
                    webbrowser.open('http://jsonlint.com?json={}'.format(quote(buffer)), new=2, autoraise=True)
                    exit(1)

        return cls(config_path=config_path, **cfg_dict)

    def load_ignore(self):
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




@click.group()
@click.option('--debug/--no-debug', default=False)
@click.pass_context
def cli(ctx, debug):
    if getattr(ctx, 'obj', None) is None:
        ctx.obj = {}

    ctx.obj['DEBUG'] = debug

    ctx.obj['glass'] = Glass.load_config(ctx)

    if ctx.invoked_subcommand is None:
        click.echo('Glass CMS command line tool. Possible commands are:')
        click.echo('')
        click.echo('    config')
        click.echo('    sync')
        click.echo('    watch')
        click.echo('    put_all')
        click.echo('')

    click.echo('Debug mode is %s' % ('on' if debug else 'off'))
    if debug:
        from spectrum.handlers import Spectrum
        logger.setLevel(logging.DEBUG)
        spectrum = Spectrum('glass-cli')
        logger.addHandler(spectrum)



@cli.command()
@click.pass_context
def configure(ctx):
    config = {}
    config['email'] = click.prompt('What email did you use to sign up for glass?')
    config['password'] = click.prompt('What is your password for glass?')

    glass = Glass(config['email'], config['password'])
    click.echo('---')
    click.echo('Finding sites for you')

    sites = glass.list_sites()
    if sites:
        for index, s in enumerate(sites):
            click.echo('   {}. {}'.format(
                index + 1,
                s['name'] or s['domain']
            ))

        while True:
            ind = click.prompt("Which which site would you like to configure in this directory?", type=int)
            ind -= 1
            if 0 <= ind < len(sites):
                config['site'] = sites[ind]
                break
            elif ind == len(sites):
                new_site.invoke()
            else:
                raise click.UsageError('That was not one of the valid options, please choose from 1 to {}'.format(len(sites)))
    else:
        new_site.invoke()

    click.echo('Writing config file to .glass/config')
    mkdir_p('.glass')
    with open('.glass/config', 'w') as f:
        f.write(json.dumps(config, indent=4))

    exit(1)


@cli.command()
@click.pass_context
def new_site(ctx):
    click.echo('This command is not yet implemented.')
    exit(1)


@cli.command()
@click.pass_context
def get_file(ctx, remote_path, remote_context=None):
    glass = ctx.obj['glass']

    if remote_context and remote_context.get('sha', None):
        content_sha = hashlib.sha1()
        try:
            with open(remote_path, 'rb') as fb:
                content_sha.update(fb.read())
            if remote_context.get("sha", None) == content_sha.hexdigest():
                click.echo('Skipping File: {} - contents match'.format(remote_path))
                return
        except IOError:
            logger.error('IO Error in getting file, with sha', exc_info=True)
            #    click.echo(' * Error {}'.format(exc.message))

    click.echo('Getting File: {}'.format(remote_path))
    resp = glass.get_site_resource(remote_path)
    mkdir_p(os.path.dirname(remote_path))

    try:
        with open(remote_path, 'wb') as fb:
            for chunk in resp.iter_content(chunk_size=1024):
                if chunk: # filter out keep-alive new chunks
                    fb.write(chunk)
    except IOError as exc:
        logger.error('IO Error in getting file', exc_info=True)


@cli.command()
@click.pass_context
def get_all(ctx):
    glass = ctx.obj['glass']

    remote_files = glass.list_remote_staticfiles()
    glass.load_ignore()
    ignore_remote = set(glass.ignore_spec.match_files([f['path'] for f in remote_files]))

    for f in remote_files:
        if f['path'] in ignore_remote:
            click.echo("Skipping {} - ignored.".format(f["path"]))
            continue
        ctx.invoke(get_file, f["path"], f)


@cli.command()
@click.pass_context
def put_file(ctx, local_path, remote_file=None):
    remote_path = local_path.replace("\\", '/')
    glass = ctx.obj['glass']
    #resp = glass.get_site_resource(remote_path)

    #if remote_file:
    #    content_sha = hashlib.sha1()
    #    with open(local_path, 'rb') as fb:
    #        content_sha.update(fb.read())
    #    if remote_file.get("sha", None) == content_sha.hexdigest():
    #        click.echo('Skipping File: {} - contents match'.format(remote_path))
    #        return

    click.echo('Putting File: {}'.format(remote_path))
    with open(local_path, 'rb') as fb:
        resp = requests.post(
            "{}sites/{}/files/upload".format(glass.glass_url, glass.site["domain"]),
            files=[
                ('file', (os.path.basename(remote_path), fb, mimetypes.guess_type(local_path)[0])),
            ], data={
                "path": remote_path
            }, auth=(glass.email, glass.password))
        try:
            assert resp.status_code == 200
        except AssertionError as exc:
            logger.error('Response Code Error in putting file', exc_info=True)


@cli.command()
@click.pass_context
def put_all(ctx):
    glass = ctx.obj['glass']

    remote_files = glass.list_remote_staticfiles()
    glass.load_ignore()
    local_files = set([os.path.join(dp[2:], f) for dp, dn, filenames in os.walk('.') for f in filenames if not dn])

    ignore_local_files = set(glass.ignore_spec.match_tree('.'))

    for f in sorted(local_files - ignore_local_files):
        rf = {}
        for rf in remote_files:
            if f == rf['path']:
                break
        ctx.invoke(put_file, f, rf)


class FSEventHandler(FileSystemEventHandler):

    def __init__(self, ctx, *args, **kwargs):
        self.ctx = ctx
        self.glass = ctx.obj['glass']
        self.glass.load_ignore()

        super(FSEventHandler, self).__init__(*args, **kwargs)

    def on_created(self, evt):
        self.upload(evt)

    def on_modified(self, evt):
        self.upload(evt)

    def on_moved(self, evt):
        self.upload(evt)

    def upload(self, evt):
        if not evt.is_directory:
            ignore_remote = set(self.glass.ignore_spec.match_files([evt.src_path[2:]]))
            if not ignore_remote:
                self.ctx.invoke(put_file, evt.src_path[2:])


@cli.command()
@click.pass_context
def audit(ctx):
    glass = ctx.obj['glass']
    pages = glass.site_req('siteapi/pages.json')

    import datetime
    import webbrowser
    click.echo('starting audit: {}'.format( datetime.datetime.now().isoformat()))
    for p in pages:
        url = '/' + p['path']
        resp = requests.get("{}{}".format(glass.site['url'], url))
        click.echo("[{}] {} - {}".format(datetime.datetime.now().isoformat(), resp.status_code, url))
        webbrowser.open("{}{}?convert_chunks=true".format(glass.site['url'], url))

    click.echo('finished audit: {}'.format( datetime.datetime.now().isoformat()))

@cli.command()
@click.pass_context
def watch(ctx):
    glass = ctx.obj['glass']

    path = '.'
    observer = Observer()
    event_handler = FSEventHandler(ctx)
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()



#### Handlers
from django.shortcuts import render
from django.template.loader import get_template
from django.contrib.staticfiles.views import serve
from django.conf.urls import url


def view(request, path):
    from django.conf import settings
    if get_template(path):
        return render(request, path, {})
    return serve(os.path.join(settings.BASE_DIR, path))

urlpatterns = [
    url(r'^(.*)', view),
]

@cli.command()
@click.pass_context
def serve(ctx):
    glass = ctx.obj['glass']

    from django.conf import settings
    if not settings.configured:
        settings.configure(
            DEBUG = True,
            ROOT_URLCONF = 'glass',
            INSTALLED_APPS = [],
            BASE_DIR = glass.config_path,
            TEMPLATES = [
                {
                    'BACKEND': 'django.template.backends.django.DjangoTemplates',
                    'DIRS': [
                        os.path.join(glass.config_path),
                    ],
                    'APP_DIRS': True,
                    'OPTIONS': {
                        'context_processors': [
                            # Insert your TEMPLATE_CONTEXT_PROCESSORS here or use this
                            # list if you haven't customized them:
                            'django.template.context_processors.debug',
                            'django.template.context_processors.i18n',
                            'django.contrib.messages.context_processors.messages',
                        ],
                    },
                },
            ],
        )
    from django import setup
    setup()

    from django.template.engine import Engine
    engine = Engine.get_default()

    engine.builtins = engine.builtins + [
        'django.templatetags.i18n',
        'django.templatetags.l10n',
        'django.contrib.humanize.templatetags.humanize',
        'local_tags',
    ]
    engine.template_builtins = engine.get_template_builtins(engine.builtins)

    from django.core.management import execute_from_command_line
    execute_from_command_line(["glass.py", "runserver", "8999"])


if __name__ == '__main__':
    cli(obj={})