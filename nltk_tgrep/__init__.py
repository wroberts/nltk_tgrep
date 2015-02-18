#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
TGrep search implementation for NTLK trees.

(c) 16 March, 2013 Will Roberts <wildwilhelm@gmail.com>.
'''

from __future__ import absolute_import
from codecs import open
from os import path

# Version. For each new release, the version number should be updated
# in the file VERSION.
try:
    # If a VERSION file exists, use it!
    with open(path.join(path.dirname(__file__), 'VERSION'),
              encoding='utf-8') as infile:
        __version__ = infile.read().strip()
except NameError:
    __version__ = 'unknown (running code interactively?)'
except IOError as ex:
    __version__ = "unknown (%s)" % ex

# import top-level functionality
from .tgrep import tgrep_tokenize, tgrep_compile, treepositions_no_leaves, \
    tgrep_positions, tgrep_nodes

