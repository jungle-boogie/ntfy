import argparse
import logging
import logging.config
from getpass import getuser
from os import environ, getcwd, path
from socket import gethostname
from subprocess import call
from sys import exit, stderr
from time import time

try:
    from emoji import emojize
except ImportError:
    emojize = None

from . import __version__, notify
from .config import load_config, DEFAULT_CONFIG, OLD_DEFAULT_CONFIG


def run_cmd(args):
    if not args.command:
        stderr.write('usage: ntfy done [-h|-L N] command\n'
                     'ntfy done: error: the following arguments '
                     'are required: command\n')
        exit(1)

    start_time = time()
    retcode = call(args.command)
    duration = time() - start_time
    if args.longer_than is not None and duration <= args.longer_than:
        return
    if emojize is not None and not args.no_emoji:
        prefix = ':white_check_mark: ' if retcode == 0 else ':x: '
    else:
        prefix = ''
    return '{}"{}" {} in {:d}:{:02d} minutes'.format(
        prefix, ' '.join(args.command), 'succeeded' if retcode == 0 else
        'failed', *map(int, divmod(duration, 60)))


def auto_done(args):
    shell_path = path.join(path.split(__file__)[0], 'shell_integration')
    if emojize is not None and not args.no_emoji:
        print('export AUTO_NTFY_DONE_EMOJI=true')
    if args.shell == 'bash':
        print('source {}/bash-preexec.sh'.format(shell_path))
    print('source {}/auto-ntfy-done.sh'.format(shell_path))
    print("# To use ntfy's shell integration, run "
          "this and and it to your shell's rc file:")
    print('# eval "$(ntfy shell-integration)"')


parser = argparse.ArgumentParser(
    description='Send push notification when command finishes')

parser.add_argument(
    '-c',
    '--config',
    help='config file to use (default: {})'.format(DEFAULT_CONFIG))
parser.add_argument('-b',
                    '--backend',
                    action='append',
                    help='override backend specified in config')
parser.add_argument('-o',
                    '--option',
                    nargs=2,
                    action='append',
                    metavar=('key', 'value'),
                    default=[],
                    help='backend specific options')
parser.add_argument('-l',
                    '--log-level',
                    action='store',
                    default='WARNING',
                    choices=[
                        'CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'
                    ],
                    help=('Specify the how verbose CLI output is '
                          '(default: WARNING)'))
parser.add_argument('-v',
                    '--verbose',
                    dest='log_level',
                    action='store_const',
                    const='DEBUG',
                    help='a shortcut for --log-level=DEBUG')
parser.add_argument('-q',
                    '--quiet',
                    dest='log_level',
                    action='store_const',
                    const='CRITICAL',
                    help='a shortcut for --log-level=CRITICAL')
parser.add_argument('--version', action='version', version=__version__)
if emojize is not None:
    parser.add_argument('-E',
                        '--no-emoji',
                        action='store_true',
                        help='Disable emoji support')

default_title = '{}@{}:{}'.format(getuser(), gethostname(), getcwd().replace(
    path.expanduser('~'), '~'))

parser.add_argument('-t',
                    '--title',
                    default=default_title,
                    help='a title for the notification (default: {})'
                    .format(default_title))

subparsers = parser.add_subparsers()

send_parser = subparsers.add_parser('send', help='send a notification')
send_parser.add_argument('message', help='notification message')
send_parser.set_defaults(func=lambda args: args.message)

done_parser = subparsers.add_parser(
    'done',
    help='run a command and send a notification when done')
done_parser.add_argument('command',
                         nargs=argparse.REMAINDER,
                         help='command to run')
done_parser.add_argument(
    '-L',
    '--longer-than',
    type=int,
    metavar='N',
    help="Only notify if the command runs longer than N seconds")
done_parser.set_defaults(func=run_cmd)

shell_integration_parser = subparsers.add_parser(
    'shell-integration',
    help='automatically get notifications when long running commands finish')
shell_integration_parser.add_argument(
    '-s',
    '--shell',
    default=path.split(environ.get('SHELL', ''))[1],
    choices=['bash', 'zsh'],
    help='The shell to integrate ntfy with (default: your login shell)')
shell_integration_parser.set_defaults(func=auto_done)


def main(cli_args=None):
    if cli_args is not None:
        args = parser.parse_args(cli_args)
    else:
        args = parser.parse_args()

    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'default': {
                'format': '%(levelname)s: %(message)s'
            },
        },
        'handlers': {
            'default': {
                'level': args.log_level,
                'class': 'logging.StreamHandler',
                'formatter': 'default',
            },
        },
        'loggers': {
            '': {
                'handlers': ['default'],
                'level': args.log_level,
                'propagate': True,
            }
        }
    })

    if args.config is not None:
        config = load_config(args.config)
    elif path.exists(path.expanduser(DEFAULT_CONFIG)):
        config = load_config(DEFAULT_CONFIG)
    elif path.exists(path.expanduser(OLD_DEFAULT_CONFIG)):
        config = load_config(OLD_DEFAULT_CONFIG)
    else:  # get default config and print message about missing file
        config = load_config()

    if args.backend:
        config['backends'] = args.backend

    if getattr(args, 'func', None) == run_cmd and args.longer_than is None and \
            'longer_than' in config:
        args.longer_than = config['longer_than']

    if hasattr(args, 'func'):
        message = args.func(args)
        if message is None:
            return 0
        if emojize is not None and not args.no_emoji:
            message = emojize(message, use_aliases=True)
        return notify(message, args.title, config, **dict(args.option))
    else:
        parser.print_help()


if __name__ == '__main__':
    exit(main())
