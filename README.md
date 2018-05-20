qslang
======

A text-based language for manual entry of quantified self data.

Useful for logging in an textual format which can be very flexible and allow for interleaving of partially structured data to later be structured. It can even be pretty efficient in combination with word-predicting keyboards on touch devices.

Usage
=====

This repo contains tools to import from:

 - Standard Notes export
 - ~~Evernote Export~~ (not yet)

For Standard Notes, create an unencrypted export and unzip the `SN Archive.txt` file into `./data/private` (keep its default name). 

(NOT SUPPORTED YET) For Evernote, export the notebooks you want to analyze as `.enex` file. Then put all the exported notebooks you want into `./data/private`.

Then simply run `./main.py` to get further usage instructions.

Format
======

Basic example:

```
# 2018-04-14

07:01 - Woke up

07:32 - 2000IU Vitamin D3 + 5g Creatine monohydrate + 200mg Magnesium (from citrate)

08:10 - ~2dl Green tea + 10g Cocoa

12:54 - ~2dl Green tea

16:30 - Started working on QSlang
```
