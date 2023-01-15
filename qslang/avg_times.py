# From: https://stackoverflow.com/a/44463260/965332

from datetime import datetime, time, timedelta
from typing import List, Union
import math
import numpy


def time_to_radians(time_of_day: time) -> float:
    # radians are calculated using a 24-hour circle, not 12-hour, starting at north and moving clockwise
    seconds_from_midnight = (
        3600 * time_of_day.hour + 60 * time_of_day.minute + time_of_day.second
    )
    radians = float(seconds_from_midnight) / float(12 * 60 * 60) * 2.0 * math.pi
    return radians


def average_angle(angles: List[float]) -> float:
    # angles measured in radians
    x_sum = numpy.sum([math.sin(x) for x in angles])
    y_sum = numpy.sum([math.cos(x) for x in angles])
    x_mean = x_sum / float(len(angles))
    y_mean = y_sum / float(len(angles))
    return numpy.arctan2(x_mean, y_mean)


def radians_to_time_of_day(x: float) -> time:
    # radians are measured clockwise from north and represent time in a 24-hour circle
    seconds_from_midnight = int(float(x) / (2.0 * math.pi) * 12.0 * 60.0 * 60.0)
    hour = seconds_from_midnight // 3600 % 24
    minute = (seconds_from_midnight % 3600) // 60
    second = seconds_from_midnight % 60
    return time(hour, minute, second)


# Based on: https://rosettacode.org/wiki/Averages/Mean_time_of_day#Python
from cmath import rect, phase
from math import radians, degrees


def mean_angle(deg):
    return degrees(phase(sum(rect(1, radians(d)) for d in deg) / len(deg)))


def mean_time(times: List[time]) -> time:
    seconds = (
        (float(t.second) + int(t.minute) * 60 + int(t.hour) * 3600) for t in times
    )
    day = 24 * 60 * 60
    to_angles = [s * 360.0 / day for s in seconds]
    mean_as_angle = mean_angle(to_angles)
    mean_seconds = mean_as_angle * day / 360.0
    if mean_seconds < 0:
        mean_seconds += day
    h, m = divmod(mean_seconds, 3600)
    m, s = divmod(m, 60)
    if h == 24:
        h = 0
    return time(int(h), int(m), int(s))


def test_mean_time():
    t = mean_time([datetime(2017, 6, 9, 0, 10), datetime(2017, 6, 9, 0, 20)])
    assert time(0, 14, 59) <= t <= time(0, 15)

    t = mean_time([datetime(2017, 6, 9, 23, 50), datetime(2017, 6, 9, 0, 10)])
    assert t == time(0, 0)

    t = mean_time([time(23, 0, 17), time(23, 40, 20), time(0, 12, 45), time(0, 17, 19)])
    assert t == time(23, 47, 43)
