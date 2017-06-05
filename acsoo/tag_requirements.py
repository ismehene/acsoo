# -*- coding: utf-8 -*-
# Copyright 2016 ACSONE SA/NV (<http://acsone.eu>)
# License GPL-3.0 or later (http://www.gnu.org/licenses/gpl.html).

import logging
import re
import os

import click

from .main import main
from .tools import call, check_call, check_output, working_directory

_logger = logging.getLogger(__name__)


RE = re.compile(r"(?P<editable>-e )?(?P<vcs>(git|svn|hg))\+"
                r"(?P<url>(ssh|http|https)://.*?/.*?)@(?P<sha>[^?#&]+)"
                r".*?[#?&]egg=(?P<egg>[^?#&]+)")
NOTAG_RE = re.compile(r"([a-zA-Z0-9-_\.]+==)|"
                      r"(-f )|(--find-links )|"
                      r"(--extra-index-url )")


def _make_push_url(url):
    GIT_URL_RE = re.compile(r"(?P<scheme>ssh|http|https)://"
                            r"(?P<user>git@)?(?P<host>.*?)/"
                            r"(?P<rest>.*)")
    mo = GIT_URL_RE.match(url)
    if not mo:
        raise click.ClickException("Unsupported git url: %s" % url)
    return GIT_URL_RE.sub(r"ssh://git@\g<host>/\g<rest>", url)


def _get_last_sha(requirement):
    # find the short sha of the last commit to requirements.txt
    return check_output([
        'git', 'log', '-n', '1', '--format=%h', requirement
    ]).strip()


def _has_tag(series, trigram, egg, sha, repodir='.'):
    tag_re = re.compile(series + "[-_]" + trigram +
                        "[-_][a-fA-F0-9]+[-_]" + egg)
    tags = check_output(['git', 'tag', '--points-at', sha], cwd=repodir)
    for tag in tags.split():
        tag = tag.strip()
        if tag_re.match(tag):
            return tag
    return False


def _is_committed(requirement):
    out = check_output(['git', 'ls-files', requirement])
    if not out:
        return False
    r = call(['git', 'diff', '--exit-code', requirement])
    return r == 0


def do_tag_requirements(config, force, src, requirement, yes):
    if not _is_committed(requirement):
        raise click.ClickException("Please commit %s first." % (requirement, ))
    requirement_sha = _get_last_sha(requirement)
    base_tag = '{}-{}-{}'.format(
        config.series, config.trigram, requirement_sha)
    if not yes:
        click.confirm('Tag dependencies with {}?'.format(base_tag), abort=True)
    if force:
        force_cmd = ['-f']
    else:
        force_cmd = []
    for req in open(requirement):
        req = req.strip()
        mo = RE.match(req)
        if not mo:
            if not NOTAG_RE.match(req):
                _logger.warning("Cannot not tag %s (unrecognized req)", req)
            continue
        editable = bool(mo.group('editable'))
        vcs = mo.group('vcs')
        url = mo.group('url')
        egg = mo.group('egg')
        sha = mo.group('sha')
        if vcs != 'git':
            _logger.warning("Cannot tag %s (unsupported vcs)", (req))
            continue
        if not editable:
            _logger.warning("Cannot tag %s (non editable)", (req, ))
            continue
        repodir = os.path.join(src, egg.replace('_', '-'))
        if not os.path.isdir(os.path.join(repodir, '.git')):
            check_call(['git', 'clone', '-q', url, repodir])
        with working_directory(repodir):
            push_url = _make_push_url(url)
            check_call(['git', 'fetch', '-q', '--tags', url, sha])
            ex_tag = _has_tag(config.series, config.trigram, egg, sha)
            if ex_tag:
                click.echo('tag {ex_tag} already exists on {push_url}@{sha}'.
                           format(**locals()))
            else:
                eggtag = base_tag + '-' + egg
                click.echo('placing tag {eggtag} on {push_url}@{sha}'.
                           format(**locals()))
                check_call(['git', 'tag'] + force_cmd + [eggtag, sha])
                check_call(['git', 'push'] + force_cmd + [push_url, eggtag])


@click.command()
@click.option('-f', '--force', is_flag=True,
              help='Replace an existing tag (instead of failing)')
@click.option('--src', default='src', envvar='PIP_SRC',
              type=click.Path(file_okay=False),
              help='Directory where editable requirements are checked out')
@click.option('-r', '--requirement', default='requirements.txt',
              type=click.Path(dir_okay=False, exists=True),
              help='Requirements file to use (default=requirements.txt)')
@click.option('-y', '--yes', is_flag=True, default=False)
@click.pass_context
def tag_requirements(ctx, force, src, requirement, yes):
    """ Tag all VCS requirements found in requirements.txt.

    This is important to avoid that commits referenced in requirements.txt
    are lost in case of VCS garbage collection.

    Only git is supported for now.
    """
    do_tag_requirements(
        ctx.obj['config'], force, src, requirement, yes)


main.add_command(tag_requirements)
