"""Competitions made up of repeated matchups between specified players."""

from __future__ import division

from collections import defaultdict

from gomill import game_jobs
from gomill.competitions import Competition, NoGameAvailable, Matchup_config


class Matchup(object):
    """Internal description of a matchup from the configuration file.

    Public attributes:
      p1          -- player code
      p2          -- player code
      alternating -- bool
      description -- shortish string to show in reports

    If alternating is False, p1 plays black and p2 plays white; otherwise they
    alternate.

    """

def matchup_from_config(matchup_config):
    """Make a Matchup from a Matchup_config.

    Raises ValueError if there is an error in the configuration.

    Returns a Matchup with all attributes set.

    """
    args = matchup_config.args
    kwargs = matchup_config.kwargs
    matchup = Matchup()
    for key in kwargs:
        if key not in ('alternating', 'description'):
            raise ValueError("unknown argument '%s'" % key)
    if len(args) > 2:
        raise ValueError("too many arguments")
    if len(args) < 2:
        raise ValueError("not enough arguments")
    matchup.p1, matchup.p2 = args
    matchup.alternating = kwargs.get('alternating', True)
    matchup.description = kwargs.get('description')
    if matchup.description is None:
        matchup.description = "%s v %s" % (matchup.p1, matchup.p2)
    return matchup


class Tournament(Competition):
    """A Competition made up of repeated matchups between specified players."""

    def initialise_from_control_file(self, config):
        Competition.initialise_from_control_file(self, config)
        # Ought to validate.
        self.number_of_games = config.get('number_of_games')

        self.matchups = []
        for i, matchup in enumerate(config['matchups']):
            if not isinstance(matchup, Matchup_config):
                raise ValueError("matchup entry %d is not a Matchup" % i)
            try:
                m = matchup_from_config(matchup)
                if m.p1 not in self.players:
                    raise ValueError("unknown player %s" % m.p1)
                if m.p2 not in self.players:
                    raise ValueError("unknown player %s" % m.p2)
            except ValueError, e:
                raise ValueError("matchup entry %d: %s" % (i, e))
            m.id = i
            self.matchups.append(m)

    def get_status(self):
        return {
            'results' : self.results,
            'next_game_number' : self.next_game_number,
            'engine_names' : self.engine_names,
            'engine_descriptions' : self.engine_descriptions,
            }

    def set_status(self, status):
        self.results = status['results']
        self.next_game_number = status['next_game_number']
        self.engine_names = status['engine_names']
        self.engine_descriptions = status['engine_descriptions']

    def set_clean_status(self):
        self.results = []
        self.next_game_number = 0
        self.engine_names = {}
        self.engine_descriptions = {}

    def _games_played(self):
        return len(self.results)

    def find_players(self, game_number):
        """Find the players for the next game.

        Returns a tuple (matchup index, black player code, white player code)

        """
        quot, rem = divmod(game_number, len(self.matchups))
        matchup = self.matchups[rem]
        if matchup.alternating and (quot % 2):
            pb, pw = matchup.p2, matchup.p1
        else:
            pb, pw = matchup.p1, matchup.p2
        return rem, pb, pw

    def get_game(self):
        game_number = self.next_game_number
        if (self.number_of_games is not None and
            game_number >= self.number_of_games):
            return NoGameAvailable
        self.next_game_number += 1

        matchup_id, player_b, player_w = self.find_players(game_number)
        job = game_jobs.Game_job()
        job.game_id = str(game_number)
        job.player_b = self.players[player_b]
        job.player_w = self.players[player_w]
        job.board_size = self.board_size
        job.komi = self.komi
        job.move_limit = self.move_limit
        job.use_internal_scorer = self.use_internal_scorer
        job.preferred_scorers = self.preferred_scorers
        job.sgf_event = self.competition_code
        return job

    def process_game_result(self, response):
        self.engine_names.update(response.engine_names)
        self.engine_descriptions.update(response.engine_descriptions)
        game_number = int(response.game_id)
        matchup_id, player_b, player_w = self.find_players(game_number)
        assert player_b == response.game_result.player_b
        assert player_w == response.game_result.player_w
        self.results.append((matchup_id, response.game_result))
        # This will show results in order of games finishing rather than game
        # number, but never mind.
        self.log_history("%4s %s" %
                         (response.game_id, response.game_result.describe()))

    def write_static_description(self, out):
        def p(s):
            print >>out, s
        p("tournament: %s" % self.competition_code)
        for code, description in sorted(self.engine_descriptions.items()):
            p("player %s: %s" % (code, description))
        p("board size: %s" % self.board_size)
        p("komi: %s" % self.komi)
        p(self.description)

    def write_status_summary(self, out):
        if self.number_of_games is None:
            print >>out, "%d games played" % self._games_played()
        else:
            print >>out, "%d/%d games played" % (
                self._games_played(), self.number_of_games)
        print >>out
        results_by_matchup_id = defaultdict(list)
        for matchup_id, result in self.results:
            results_by_matchup_id[matchup_id].append(result)
        for (i, matchup) in enumerate(self.matchups):
            results = results_by_matchup_id[i]
            if results:
                self.write_matchup_report(out, matchup, results)

    def write_results_report(self, out):
        pass

    def write_matchup_report(self, out, matchup, results):
        def p(s):
            print >>out, s
        total = len(results)
        assert total != 0
        player_x = matchup.p1
        player_y = matchup.p2
        x_wins = len([1 for r in results if r.winning_player == player_x])
        y_wins = len([1 for r in results if r.winning_player == player_y])
        unknown = len([1 for r in results if r.winning_player is None])
        b_wins = len([1 for r in results if r.winning_colour == 'b'])
        w_wins = len([1 for r in results if r.winning_colour == 'w'])
        xb_wins = len([1 for r in results if
                       r.winning_player == player_x and
                       r.winning_colour == 'b'])
        xw_wins = len([1 for r in results if
                       r.winning_player == player_x and
                       r.winning_colour == 'w'])
        yb_wins = len([1 for r in results if
                       r.winning_player == player_y and
                       r.winning_colour == 'b'])
        yw_wins = len([1 for r in results if
                       r.winning_player == player_y and
                       r.winning_colour == 'w'])
        xb_played = len([1 for r in results if
                         r.player_b == player_x])
        xw_played = len([1 for r in results if
                         r.player_w == player_x])
        yb_played = len([1 for r in results if
                         r.player_b == player_y])
        yw_played = len([1 for r in results if
                         r.player_w == player_y])

        x_times = [r.cpu_times[player_x] for r in results]
        x_known_times = [t for t in x_times if t is not None and t != '?']
        if x_known_times:
            x_avg_time_s = "%7.2f" % (sum(x_known_times) / len(x_known_times))
        else:
            x_avg_time_s = "----"
        y_times = [r.cpu_times[player_y] for r in results]
        y_known_times = [t for t in y_times if t is not None and t != '?']
        if y_known_times:
            y_avg_time_s = "%7.2f" % (sum(y_known_times) / len(y_known_times))
        else:
            y_avg_time_s = "----"

        p("%s (%d games)" % (matchup.description, total))
        def pct(n, baseline):
            if baseline == 0:
                if n == 0:
                    return "--"
                else:
                    return "??"
            return "%.2f%%" % (100 * n/baseline)
        if unknown > 0:
            p("unknown results: %d %s" % (unknown, pct(unknown, total)))

        pad = max(len(player_x), len(player_y)) + 2
        xname = player_x.ljust(pad)
        yname = player_y.ljust(pad)

        p(" " * (pad+17) + "   black         white        avg cpu")
        p("%s %4d %7s    %4d %7s  %4d %7s  %s"
          % (xname, x_wins, pct(x_wins, total),
             xb_wins, pct(xb_wins, xb_played),
             xw_wins, pct(xw_wins, xw_played),
             x_avg_time_s))
        p("%s %4d %7s    %4d %7s  %4d %7s  %s"
          % (yname, y_wins, pct(y_wins, total),
             yb_wins, pct(yb_wins, yb_played),
             yw_wins, pct(yw_wins, yw_played),
             y_avg_time_s))
        p(" " * (pad+17) + "%4d %7s  %4d %7s"
          % (b_wins, pct(b_wins, total), w_wins, pct(w_wins, total)))
        p("")

