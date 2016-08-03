import click
import os, os.path, json, mimetypes, hashlib, time, re
from sys import exit
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from glass.client import Glass
from glass import __version__, __build__
import logging
import requests
from distutils import version

try:
    from json.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError

logger = logging.getLogger()


def mkdir_p(path):
    #print("making dir ", path)
    if path and not os.path.exists(path):
        os.makedirs(path)


def load_config(ctx, path=None):
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

    return Glass(config_path=config_path, **cfg_dict)


@click.group()
@click.option('--debug/--no-debug', default=False)
@click.version_option(__version__)
@click.pass_context
def cli(ctx, debug):
    version_check()
    if getattr(ctx, 'obj', None) is None:
        ctx.obj = {}

    ctx.obj['DEBUG'] = debug

    ctx.obj['glass'] = load_config(ctx)

    if ctx.invoked_subcommand is None:
        click.echo('Glass CMS command line tool. Possible commands are:')
        click.echo('')
        click.echo('    config')
        click.echo('    sync')
        click.echo('    watch')
        click.echo('    put_all')
        click.echo('')

    click.echo('Debug mode is %s' % ('on' if debug else 'off'))


def version_check():
    response = requests.get("https://pypi.python.org/pypi/glass-api/json")
    try:
        assert response.status_code == 200
    except AssertionError:
        logger.warn("Unable to parse version check")

    data = response.json()
    if version.LooseVersion(data['info']['version']) > version.LooseVersion(__version__):
        click.echo("You're running an old version. Contact support@website.glass if you need help upgrading.")



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

    exit(0)


@cli.command()
@click.pass_context
def new_site(ctx):
    click.echo('This command is not yet implemented.')
    exit(1)


@cli.command()
@click.pass_context
def get_file(ctx, remote_path, remote_context=None):
    glass = ctx.obj['glass']
    if remote_path[0] == "/":
        remote_path = remote_path[1:]

    local_path = remote_path.replace('/', os.path.sep)

    if remote_context and remote_context.get('sha', None):
        content_sha = hashlib.sha1()
        try:
            with open(remote_path, 'rb') as fb:
                content_sha.update(fb.read())
            if remote_context.get("sha", None) == content_sha.hexdigest():
                click.echo('Skipping File: {} - contents match'.format(remote_path))
                return
        except IOError:
            click.echo('Local IO Error in getting file, with sha: {}'.format(content_sha.hexdigest()))

    click.echo('Getting File: {}'.format(remote_path))
    resp = glass.get_site_resource(remote_path)
    mkdir_p(os.path.dirname(remote_path))

    try:
        with open(remote_path, 'wb') as fb:
            for chunk in resp.iter_content(chunk_size=1024):
                if chunk: # filter out keep-alive new chunks
                    fb.write(chunk)
    except IOError:
        click.echo('Local IO Error in getting file {}'.format(remote_path))
    except PermissionError:
        click.echo('Permission Error in getting file {}'.format(remote_path))



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
