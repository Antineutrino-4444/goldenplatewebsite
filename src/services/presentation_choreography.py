"""The reading order and timing of the native PowerPoint assembly layouts."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Entrance:
    name: str
    start: int
    movement: str
    duration: int


def _overview(at, shapes):
    at(80, 'all_clean', movement='settle')
    at(265, 'share')
    at(460, 'progress_track')
    at(560, 'fly', movement='fly', duration=1150)
    at(640, 'goal_label')
    at(800, 'Lunch detail rule')
    change_value, change_motion = ('signed_change', 'lunch') if 'signed_change' in shapes else ('latest_change', 'fade')
    sections = (
        ('latest_heading', 'latest_name', 'latest_date', 'lunch'),
        ('rate_heading', 'latest_rate', 'latest_counts', 'across'),
        ('change_heading', change_value, 'change_units', change_motion),
    )
    for index, (heading, value, detail, movement) in enumerate(sections):
        start = 930 + 170 * index
        at(start, heading)
        at(start + 100, value, movement=movement)
        at(start + 290, detail)
    at(1710, 'excess', movement='excess', duration=450)
    at(1880, 'stamp')


def _latest_lunch(at, shapes):
    at(80, 'title')
    at(155, 'latest_name', movement='settle')
    at(325, 'latest_date')
    at(365, 'rate', movement='across')
    at(470, 'latest_counts')
    at(540, 'distribution')

    at(610, 'stamp')


def _table(at, shapes):
    at(80, 'title', movement='settle')
    at(280, 'Previous lunch label')
    at(340, 'prev_name', movement='across')
    at(395, 'prev_date', 'Latest lunch label')
    at(455, 'curr_name', movement='across')
    at(510, 'curr_date', 'Change label')
    rows = (('clean', 'Clean plates rule'), ('total', 'Plates recorded rule'), ('rate', 'Clean-plate rate rule'))
    for index, (metric, rule) in enumerate(rows):
        start = 650 + index * 315
        at(start, rule, metric + ' label')
        at(start + 65, 'prev_' + metric)
        at(start + 105, 'curr_' + metric)
        at(start + 170, 'delta_' + metric, movement='across')
    at(1575, 'Table bottom rule')
    at(1720, 'stamp')


def _rate_chart(at, shapes):
    at(80, 'title', movement='settle')
    summary_start = 1510
    for prefix, label, start in [('prev', 'Previous lunch label', 345), ('curr', 'Latest lunch label', 865)]:
        at(start, label)
        at(start + 65, prefix + '_name', movement='across')
        at(start + 90, prefix + '_track')
        name = prefix + '_fill'
        if name in shapes and shapes[name].width:
            at(start + 155, name, movement='fly', duration=1150)
            summary_start = max(summary_start, start + 155 + 1150 + 10)
        else:
            at(start + 155, name)
        at(start + 220, prefix + '_rate', movement='across')
        at(start + 310, prefix + '_counts')
    at(summary_start, 'rate_comparison', movement='lift')
    at(summary_start + 140, 'stamp')


def _reminders(at, shapes):
    at(80, 'title')
    at(230, 'Serving line rule')
    at(270, 'Portion choice', movement='across')
    at(765, 'Dish return rule')
    at(890, 'Plate count', movement='across')
    at(1380, 'stamp')


def _closing(at, shapes):
    at(80, 'Be Green', movement='settle')
    at(760, 'Do Good', movement='lunch')


def _winner(at, shapes):
    at(80, 'winner_title')
    at(275, 'winner_detail', movement='settle')
    at(650, 'winner_role_student', 'winner_role_faculty', 'gp.winner.photo.left', 'gp.winner.photo.right')
    at(790, 'winner_name_student', 'winner_name_faculty', movement='lift')
    at(1000, 'winner_stats_student', 'winner_stats_faculty')
    at(1200, 'stamp')


def slide_entrances(template_index, shapes):
    cues = []

    def at(start, *names, movement='fade', duration=0):
        for name in names:
            if name in shapes:
                cues.append(Entrance(name, start, movement, duration))

    at(200, 'Plate mark', 'Publisher')
    at(320, 'Masthead rule')
    at(370, 'school')
    layouts = (_overview, _latest_lunch, _table, _rate_chart, _reminders, _closing, _winner)
    layouts[template_index](at, shapes)
    # New template objects should still start hidden. Give unscored additions
    # the last quiet beat until the layout assigns a more specific entrance.
    scheduled = {cue.name for cue in cues}
    last_start = max((cue.start for cue in cues), default=80)
    at(last_start, *(name for name in shapes if name not in scheduled))
    return sorted(cues, key=lambda cue: cue.start)
