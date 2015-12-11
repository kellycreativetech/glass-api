#!/usr/bin/env python

import click
import requests
import os, os.path, json, mimetypes

def mkdir_p(path):
    if path and not os.path.exists(path):
        os.makedirs(path)

class Glass(object):

    def __init__(self, email, password, glass_url=None, site=None, **kwargs):
        self.email = email
        self.password = password
        self.glass_url = glass_url
        self.site = site

        if not glass_url:
            self.glass_patrol_url = os.getenv('GLASS_PATROL_URL', 'http://localhost:8001/')


    def patrol_req(self, path, method="GET"):
        response = requests.request(
            method,
            "{}{}".format(self.glass_patrol_url, path),
            auth=(self.email, self.password),
        )
        try:
            return response.json()
        except Exception, exc:
            import ipdb; ipdb.set_trace()

    def site_req(self, path, method="GET"):
        response = requests.request(
            method,
            "{}{}".format(self.site["url"], path),
        )
        return response.json()

    def list_sites(self):
        return self.patrol_req('sites.json')

    def list_remote_staticfiles(self):
        return self.patrol_req('sites/{}/files.json'.format(self.site['id']))

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
            if dir == '/':
                return None

            return _config_path(dir)

        if not path:
            path = os.getcwd()

        config_path = _config_path(path)
        if not config_path:
            click.confirm("Could not find a .glass config folder. Would you like to make one now?", abort=True)
            ctx.invoke(configure)

        if not os.path.exists(os.path.join(config_path, ".glass", "config")):
            click.confirm("The path `.glass` path exists, but there is no config file. Would you like to make one now?", abort=True)
            ctx.invoke(configure)

        if os.getcwd() is not config_path:
            click.echo("Changing working directory to glass root at : {}".format(config_path))
            os.chdir(config_path)

        with open(os.path.join(config_path, ".glass", "config"), 'rb') as fb:
            cfg_dict = json.loads(fb.read())

        return cls(**cfg_dict)





@click.group()
@click.option('--debug/--no-debug', default=False)
@click.pass_context
def cli(ctx, debug):
    ctx.obj['DEBUG'] = debug

    ctx.obj['glass']  = Glass.load_config(ctx)

    if ctx.invoked_subcommand is None:
        click.echo('Glass CMS command line tool. Possible commands are:')
        click.echo('')
        click.echo('    config')
        click.echo('    sync')

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
    with open('.glass/config', 'wb') as f:
        f.write(json.dumps(config, indent=4))

    ctx.obj['glass'] = Glass(
        **config
    )


@cli.command()
@click.pass_context
def new_site(ctx):
    click.echo('This command is not yet implemented.')
    exit(1)


@cli.command()
@click.pass_context
def get_file(ctx, remote_path):
    click.echo('Getting File: {}'.format(remote_path))
    glass = ctx.obj['glass']
    resp = glass.get_site_resource(remote_path)
    mkdir_p(os.path.dirname(remote_path))
    with open(remote_path, 'wb') as fb:
        for chunk in resp.iter_content(chunk_size=1024):
            if chunk: # filter out keep-alive new chunks
                fb.write(chunk)


@cli.command()
@click.pass_context
def get_all(ctx):
    glass = ctx.obj['glass']

    remote_files = glass.list_remote_staticfiles()
    for f in remote_files:
        #if not os.path.exists(f["path"]):
            ctx.invoke(get_file, f["path"])
        #else:
        #    #be clever?


@cli.command()
@click.pass_context
def put_file(ctx, local_path):
    remote_path = local_path[2:]
    click.echo('Putting File: {}'.format(remote_path))
    glass = ctx.obj['glass']
    resp = glass.get_site_resource(remote_path)
    mkdir_p(os.path.dirname(remote_path))
    with open(local_path, 'rb') as fb:
        #import ipdb; ipdb.set_trace()
        resp = requests.post(
            "{}sites/{}/files/upload".format(glass.glass_patrol_url, glass.site["id"]),
            files=[
                ('file', (os.path.basename(remote_path), fb, mimetypes.guess_type(local_path)[0])),
            ], data={
                "path": remote_path
            }, auth=(glass.email, glass.password))
        assert resp.status_code == 200


@cli.command()
@click.pass_context
def put_all(ctx):
    glass = ctx.obj['glass']

    remote_files = glass.list_remote_staticfiles()
    local_files = [os.path.join(dp, f) for dp, dn, filenames in os.walk('.') for f in filenames]

    for f in local_files:
        #import ipdb; ipdb.set_trace()
        #if os.path.exists(f["path"]):
            ctx.invoke(put_file, f)
        #else:
        #    #be clever?


if __name__ == '__main__':
    cli(obj={})