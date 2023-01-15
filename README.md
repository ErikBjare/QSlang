QSlang
======

[![Build](https://github.com/ErikBjare/QSlang/actions/workflows/build.yml/badge.svg)](https://github.com/ErikBjare/QSlang/actions/workflows/build.yml)
[![codecov](https://codecov.io/gh/ErikBjare/qslang/branch/master/graph/badge.svg)](https://codecov.io/gh/ErikBjare/qslang)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Typechecking: Mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)

A text-based language for manual entry of quantified self data.

Useful for logging in a flexible textual format which allows for interleaving of partially structured data to later be structured. Input on phones/touch devices is surprisingly efficient when used with sentence-predicting keyboards (like Swiftkey etc).

Built with parsimonious (to parse notes) and pint (to handle units).

Pronounced: Q-Slang

Usage
=====

```
$ qslang --help
Usage: qslang [OPTIONS] COMMAND [ARGS]...

Options:
  -v, --verbose
  --help         Show this message and exit.

Commands:
  doses            print summary of doses for each substance
  effectspan       print effect spans
  events           print list of all doses
  plot             plot doses over time in a barchart
  plot-calendar    plot doses in a calendar
  plot-effectspan  plot effect spans in a barchart
  substances       print list of substances
```

For setup & configuration, copy `config.toml.example` to `config.toml` and edit as appropriate.

This repo can read data from:

 - Directory with plaintext-files (as created by [standardnotes-fs](https://github.com/tannercollin/standardnotes-fs))
 - Standard Notes export (unencrypted)
 - Evernote (enex files)

For Standard Notes exports: create an unencrypted export and unzip the `SN Archive.txt` file (keep its default name).  Set the `data.standardnotes` key to the folder path in config.

For directory/standardnotes-fs: Put your notes in a folder, or use standardnotes-fs (deprecated) to mount your notes the same directory. Set the `data.standardnotes_export` key to the file path in config.

For Evernote, export the notebooks you want to analyze as `.enex` file. Then put all the exported notebooks you want into `./data/private`. Then run `make data/private/Evernote` to extract the .enex into markdown files (which will be put into `data/private/Evernote/`).

Then run `python3 -m qslang --help` to get further usage instructions.

Input format
============

This is the expected format of notes, I've tried to make it lenient/flexible parser but might write a stricter one in the future to avoid ambiguous parsing.

Basic example:

```
# 2018-04-14

07:01 - Woke up

07:32 - 2000IU Vitamin D3 + 5g Creatine monohydrate + 200mg Magnesium (from citrate)

08:10 - ~2dl Green tea + 10g Cocoa

12:54 - ~2dl Green tea

16:30 - Started working on QSlang
```
