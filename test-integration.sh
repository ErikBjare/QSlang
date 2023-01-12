#!/bin/bash
# Testing the QSlang cli

# fail on error
set -e

# print commands
set -x

# set environment variable to disable plotting
export MPLBACKEND=Agg

# print help
qslang --help

# list all substances
qslang substances

# list doses
qslang doses --substances caffeine

# list events
qslang events --substances caffeine

# list effectspans of common substance
qslang effectspan --substances caffeine

# plots
qslang plot --substances caffeine
qslang plot-calendar --substances caffeine
qslang plot-effectspan --substances caffeine
