# coding: utf-8
import re
from datetime import datetime
import logging
import asyncio
import irc3
from irc3.plugins.command import command
import pyinotify
from eval_arith import comp_expr, EvalConstant
from irc3.plugins.cron import cron
import os
import subprocess
import traceback
import sys

logging.basicConfig(filename='bot.log',level=logging.DEBUG)
logger = logging.getLogger("BACONBOT")

inotifymask = pyinotify.IN_DELETE | pyinotify.IN_CREATE  # watched events TODO FIXME should be EDITED

from regner_det import get_weather
import time

#wdd = wm.add_watch('/tmp', inotifymask, rec=True)

class Command(object):
    def __init__(self, name, target, func, loop, callback):
        logger.debug("command")
        wm = pyinotify.WatchManager()
        self.notifier = pyinotify.AsyncioNotifier(wm, loop, callback=callback)
        self.name = "".join(x for x in name if x.isalnum())
        self.target = target
        self.func = func
        try:
            os.mkdir("/tmp/outputs/{}".format(name))
        except FileExistsError:
            pass
        wm.add_watch("/tmp/outputs/{}/".format(name), inotifymask, rec=True)
    def ONDELETE(self): # TODO FIXME XXX CALL THIS
        wm.rm_watch(arg[0], bool(int(arg[2])), quiet=True)
        assert name
        os.system("rm -rf /tmp/outputs/{}".format(name))
    def __str__(self):
        return "Command({}, {}, {})".format(self.name, self.target, self.func)

@irc3.plugin
class SwitchControllerPlugin(object):
    @command
    def debug(self, mask, target, args):
        """ Debug

        %%debug
        """
        pdb.set_trace()

    @irc3.event(irc3.rfc.JOIN)
    @asyncio.coroutine
    def get_inotify(self, mask, channel):
        def fun():
          yield from asyncio.create_subprocess_shell(
            "python3 inotify.py /tmp/outputs",
            loop=self.bot.loop
          )
        yield from ("prefix{}".format(i) for i in fun())

    @command
    def calc(self, mask, target, args):
        """ Calc command

        %%calc <expr>
        """
        EvalConstant.vars_ = {'A': 0, 'B': 1.1, 'C': 2.2, 'D': 3.3, 'E': 4.4, 'F': 5.5, 'G': 6.6, 'H':7.7, 'I':8.8, 'J':9.9}
        res = comp_expr.parseString(args["<expr>"])[0].eval()
        self.bot.notice(target, str(res))

    @command
    def add_command(self, mask, target, args):
        """ Add cron command

        %%add_command <name> <shell> <shell>...
        """

        def callback(s):
            logger.debug(s)
            self.bot.notice(target, repr(s.proc_fun()))
            self.bot.notice(target, str(s.proc_fun()))
        self.jobs += [Command(args["<name>"], target, " ".join(args["<shell>"]), self.bot.loop, callback)]

    @command
    def rm_command(self, mask, target, args):
        """ Remove cron command

        %%rm_command <name>
        """
        self.jobs = list(filter(lambda x: x.name != args["<name>"], self.jobs))

    @command
    def list_commands(self, mask, target, args):
        """ List commands

        %%list_commands
        """
        for job in self.jobs:
             self.bot.notice(target, str(job))

    #@cron('0 */2 * * *')
    @cron('0 */12 * * *')
    @asyncio.coroutine
    def check_periodic(self):
        yield from self.run_jobs()

    @command
    def run_jobs(self, mask, target, args):
        """ Run jobs

        %%run_jobs
        """
        yield from self.do_run_jobs()

    @asyncio.coroutine
    def do_run_jobs(self):
        for j in self.jobs:
            i = j.func
            self.bot.notice(j.target, "now processing {}".format(j.name))
            stdout = None
            p = None
            try:
                if type(i) == str:
                    with open("/tmp/outputs/{}/output".format(j.name), "w") as f:
                        p = subprocess.Popen(i, shell=True, stdout=f, cwd="/tmp/outputs/{}".format(j.name))
                        p.wait(timeout=5)
                    user_stuff = "command {}, exit status {}".format(i, p.returncode)
                    stdout = p.stdout
                else:
                    user_stuff = i()
                    if user_stuff is None: user_stuff = "no rain"
                    assert type(user_stuff) == str, type(user_stuff)
            except Exception as e:
                print(e.__class__)
                traceback.print_exc()
                if p: p.terminate()
                stdout = str(e)
                user_stuff = str(e)
            self.bot.notice(j.target, "job {}: {}".format(j.name, user_stuff))

    @command
    def alarm(self, mask, target, args):
        """Alarm command
        %%alarm [ARG]
        """
        arg = args.get('ARG', None)
        if arg:
            logging.info('Starting alarm for {} seconds'.format(arg))
            # self.bot.notice(mask.nick, 'ALARM ALARM ALARM I {} SEKUNDER!'.format(arg))
        self.bot.loop.create_task(
            self.process_maybe_timed_command(
                target, 1, arg
            )
        )

    def __init__(self, bot):
        self.jobs = [ Command("raining", "#shelloutput", get_weather, asyncio.get_event_loop(), lambda s: bot.notice("#shelloutput", s.proc_fun())) ]
        self.bot = bot
        self.switches = self.bot.db.get('switches', None)
        if not self.switches:
            self.bot.db['switches'] = {}
            self.switches = self.bot.db['switches']

    @irc3.event((r':(?P<mask>\S+) PRIVMSG (?P<target>\S+) '
                 r':{re_cmd}(?P<cmd>\w+)(\s(?P<data>\S.*)|$)'))
    def on_command(self, cmd, mask=None, target=None, client=None, **kwargs):
        if cmd in self.switches:
            switch_args = self.switches[cmd]
            signal = int(switch_args.get('signal'))
            value = switch_args.get('value', None)

            if value:
                self.bot.loop.create_task(
                    self.send_signal(target, signal, value)
                )
            else:
                arg = kwargs.get('data', None)
                self.bot.loop.create_task(
                    self.process_maybe_timed_command(target, signal, arg)
                )

    @asyncio.coroutine
    def process_maybe_timed_command(self, target, unit, arg=None):
        OFF_WORDS = ['off', 'false', 'f']
        timed = False

        if not arg or arg not in OFF_WORDS:
            self.bot.loop.create_task(self.send_signal(target, unit, 't'))

        try:
            if int(arg) > 0:
                yield from asyncio.sleep(min(int(arg), 3600), loop=self.bot.loop)
                timed = True
        except ValueError:
            pass
        except TypeError:
            pass

        if arg in OFF_WORDS or timed:
            self.bot.loop.create_task(self.send_signal(target, unit, 'f'))

    @asyncio.coroutine
    def send_signal(self, target, code_id, state):
        switch_command = (
            'sudo pilight-send -p elro_800_switch -s 21 -u {} -{}'.format(
                code_id, state
            )
        )

        logging.debug(
            '{}: {}: {}'.format(datetime.now(), code_id, switch_command)
        )

        yield from asyncio.create_subprocess_shell(
            switch_command,
            loop=self.bot.loop
        )

    @command
    def switches(self, mask, target, args):
        """Switches command

        %%switches
        """
        self.bot.notice(target, '{:<15}| {:15}| {:<15}'.format(
            'Command', 'Signal', 'Value'
        ))
        for switch_name, switch_args in self.switches.items():
            signal = switch_args.get('signal', None)
            value = switch_args.get('value', None)
            if value:
                message = '{switch_name:<15}| {signal:<15}| {value:<15}'.format(
                    switch_name=switch_name,
                    signal=signal,
                    value=value
                )
            else:
                message = '{switch_name:<15}| {signal:<15}|'.format(
                    switch_name=switch_name,
                    signal=signal,
                )

            self.bot.notice(target, message)

    @command
    def setswitch(self, mask, target, args):
        """ Setswitch command

        %%setswitch <switch_name> <signal> [<value>]
        """
        switch_name = re.sub(r'\W+', '', args['<switch_name>'])
        signal = int(args['<signal>'])
        value = args['<value>'] if args['<value>'] in ['t', 'f'] else None

        if switch_name and signal:
            self.switches[switch_name] = {
                'signal': signal
            }
            if value:
                self.switches[switch_name]['value'] = value

    @command
    def delswitch(self, mask, target, args):
        """ Delswitch command

        %%delswitch <switch_name>
        """
        switch_name = args['<switch_name>']
        del self.switches[switch_name]
