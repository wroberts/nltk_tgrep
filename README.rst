=================================
 tgrep2 Searching for NLTK Trees
=================================

TGrep search implementation for NLTK_ trees.

.. _NLTK:     http://www.nltk.org

Copyright (c) 16 March, 2013 Will Roberts <wildwilhelm@gmail.com>.

Licensed under the MIT License (see source file tgrep.py for details).

This module supports TGrep2 syntax for matching parts of NLTK_ Trees.
Note that many tgrep operators implemented here require the tree
passed to be a ``ParentedTree``.

   **NOTE: nltk_tgrep has been integrated into the NLTK_ project, and
   can now be found at `its new home`_.  This github repository
   will remain here, but will not be updated in future.**

.. _its new home: https://github.com/nltk/nltk/blob/develop/nltk/tgrep.py

Tgrep tutorial:
http://www.stanford.edu/dept/linguistics/corpora/cas-tut-tgrep.html

Tgrep2 manual:
http://tedlab.mit.edu/~dr/Tgrep2/tgrep2.pdf

Tgrep2 source:
http://tedlab.mit.edu/~dr/Tgrep2/

.. image:: https://travis-ci.org/wroberts/nltk_tgrep.svg?branch=master
    :target: https://travis-ci.org/wroberts/nltk_tgrep
    :alt: Travis CI build status

.. image:: https://coveralls.io/repos/wroberts/nltk_tgrep/badge.svg?branch=master
  :target: https://coveralls.io/r/wroberts/nltk_tgrep?branch=master
     :alt: Test code coverage

.. image:: https://img.shields.io/pypi/v/nltk_tgrep.svg
    :target: https://pypi.python.org/pypi/nltk_tgrep/
    :alt: Latest Version

Requirements:
-------------

- Python 2.6 or better, or Python 3.2 or better
- future_ (for Python 2)
- NLTK_, version 3.0.0 or better
- pyparsing

::

    $ sudo pip install nltk_tgrep

.. _future:     http://python-future.org

Usage:
------

::

    >>> from nltk.tree import ParentedTree
    >>> import nltk_tgrep
    >>> tree = ParentedTree.fromstring('(S (NP (DT the) (JJ big) (NN dog)) (VP bit) (NP (DT a) (NN cat)))')
    >>> nltk_tgrep.tgrep_nodes(tree, 'NN')
    [ParentedTree('NN', ['dog']), ParentedTree('NN', ['cat'])]
    >>> nltk_tgrep.tgrep_positions(tree, 'NN')
    [(0, 2), (2, 1)]
    >>> nltk_tgrep.tgrep_nodes(tree, 'DT')
    [ParentedTree('DT', ['the']), ParentedTree('DT', ['a'])]
    >>> nltk_tgrep.tgrep_nodes(tree, 'DT $ JJ')
    [ParentedTree('DT', ['the'])]

This implementation adds syntax to select nodes based on their NLTK_
tree position.  This syntax is ``N`` plus a Python tuple representing
the tree position.  For instance, ``N()``, ``N(0,)``, ``N(0,0)`` are
valid node selectors.  Example::

    >>> tree = ParentedTree.fromstring('(S (NP (DT the) (JJ big) (NN dog)) (VP bit) (NP (DT a) (NN cat)))')
    >>> tree[0,0]
    ParentedTree('DT', ['the'])
    >>> tree[0,0].treeposition()
    (0, 0)
    >>> nltk_tgrep.tgrep_nodes(tree, 'N(0,0)')
    [ParentedTree('DT', ['the'])]

Caveats:
--------

- Link modifiers: "?" and "=" are not implemented.
- Tgrep compatibility: Using "@" for "!", "{" for "<", "}" for ">" are
  not implemented.
- The "=" and "~" links are not implemented.

Known Issues:
-------------

- There are some issues with link relations involving leaf nodes
  (which are represented as bare strings in NLTK_ trees).  For
  instance, consider the tree::

      (S (A x))

  The search string ``* !>> S`` should select all nodes which are not
  dominated in some way by an ``S`` node (i.e., all nodes which are
  not descendants of an ``S``).  Clearly, in this tree, the only node
  which fulfills this criterion is the top node (since it is not
  dominated by anything).  However, the code here will find both the
  top node and the leaf node ``x``.  This is because we cannot recover
  the parent of the leaf, since it is stored as a bare string.

  A possible workaround, when performing this kind of search, would be
  to filter out all leaf nodes.
