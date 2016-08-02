#!/usr/bin/env python
__title__ = 'glass-cli'
__version__ = '0.9.2a2'
__build__ = 0x000902
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
import logging

try:
    from json.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError

logger = logging.getLogger()

def mkdir_p(path):
    if path and not os.path.exists(path):
        os.makedirs(path)


class Glass(object):

    spec = None

    def __init__(self, email, password, domain=None, glass_url=None, config_path=None, **kwargs):
        self.email = email
        self.password = password
        self.glass_url = glass_url

        self.domain = domain
        self.site = {
            "domain": domain,
            "url": "http://{}.temp.servee.com".format(self.domain)
        }

        site = kwargs.pop('site', None)
        if site and site['domain'] and not self.domain:
            self.domain = site['domain']
            self.site['url'] = "http://{}.temp.servee.com".format(self.domain)

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


    @classmethod
    def load_config(cls, ctx, path=None):
        """
        Loads a config from a file, returns an instance of `Glass` from config file.
        """
        def _config_path(path):
            if os.path.exists(os.path.join(path, '.glass')):
                return path

            dir = os.path.dirname(path)
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

    click.echo('Getting File: {}'.format(remote_path))
    resp = glass.get_site_resource(remote_path)
    mkdir_p(os.path.dirname(remote_path))

    try:
        with open(remote_path, 'wb') as fb:
            for chunk in resp.iter_content(chunk_size=1024):
                if chunk: # filter out keep-alive new chunks
                    fb.write(chunk)
    except IOError:
        logger.error('IO Error in getting file', exc_info=True)


@cli.command()
@click.pass_context
def get_all(ctx):
    glass = ctx.obj['glass']

    remote_files = glass.list_files()
    glass.load_ignore()
    ignore_remote = set(glass.ignore_spec.match_files([f['path'] for f in remote_files]))

    for f in remote_files:
        if f['path'] in ignore_remote:
            click.echo("Skipping {} - ignored.".format(f["path"]))
            continue
        ctx.invoke(get_file, f["path"], f)


@cli.command()
@click.pass_context
def put_file(ctx, local_path):
    remote_path = local_path.replace("\\", '/')
    glass = ctx.obj['glass']
    click.echo('Putting File: {}'.format(remote_path))
    with open(local_path, 'rb') as fb:
        glass.put_file(remote_path, fb, mimetypes.guess_type(local_path)[0])



@cli.command()
@click.pass_context
def put_all(ctx):
    glass = ctx.obj['glass']

    remote_files = glass.list_files()
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
def watch(ctx):
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


if __name__ == '__main__':
    cli(obj={})