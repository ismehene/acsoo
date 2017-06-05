# -*- coding: utf-8 -*-
# Copyright 2016 ACSONE SA/NV (<http://acsone.eu>)
# License GPL-3.0 or later (http://www.gnu.org/licenses/gpl.html).

import click

from .main import main
from .tools import check_call, call, check_output


def do_tag(config, force, yes):
    tag = config.version
    if not yes:
        click.confirm('Tag project with {}?'.format(tag), abort=True)
    if force:
        force_cmd = ['-f']
    else:
        force_cmd = []
    if call(['git', 'diff', '--exit-code']) != 0:
        raise click.ClickException("Please commit first.")
    if call(['git', 'diff', '--exit-code', '--cached']) != 0:
        raise click.ClickException("Please commit first.")
    out = check_output(['git', 'ls-files', '--other', '--exclude-standard',
                        '--directory'])
    if out:
        click.echo(out)
        raise click.ClickException("Please commit first.")
    check_call(['git', 'tag'] + force_cmd + [tag])
    check_call(['git', 'push', '-q'] + force_cmd + ['origin', 'tag', tag])


@click.command(help='Tag the current project after ensuring '
                    'everything has been commited to git.')
@click.option('-f', '--force', is_flag=True,
              help='Replace an existing tag (instead of failing)')
@click.option('-y', '--yes', is_flag=True, default=False)
@click.pass_context
def tag(ctx, force, yes):
    do_tag(ctx.obj['config'], force, yes)


main.add_command(tag)
