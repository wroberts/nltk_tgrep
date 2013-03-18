=================================
 tgrep2 Searching for NLTK Trees
=================================

TGrep search implementation for NTLK trees.

(c) 16 March, 2013 Will Roberts <wildwilhelm@gmail.com>.

Licensed under the MIT License (see source file tgrep.py for details).

This module supports TGrep2 syntax for matching parts of NLTK Trees.
Note that many tgrep operators implemented here require the tree
passed to be a ``ParentedTree``.

Tgrep tutorial:
http://www.stanford.edu/dept/linguistics/corpora/cas-tut-tgrep.html

Tgrep2 manual:
http://tedlab.mit.edu/~dr/Tgrep2/tgrep2.pdf

Tgrep2 source:
http://tedlab.mit.edu/~dr/Tgrep2/

Requirements:
-------------

- Python 2.6 or better
- NLTK, version 2.0.4 recommended (``ParentedTree`` is broken in 2.0.2,
  and has a different interface in NLTK versions prior to 2.0)
- pyparsing

::

    $ sudo pip install nltk pyparsing

Usage:
------

::

    >>> from nltk.tree import ParentedTree
    >>> import tgrep
    >>> tree = ParentedTree('(S (NP (DT the) (JJ big) (NN dog)) (VP bit) (NP (DT a) (NN cat)))')
    >>> tgrep.tgrep_nodes(tree, 'NN')
    [ParentedTree('NN', ['dog']), ParentedTree('NN', ['cat'])]
    >>> tgrep.tgrep_positions(tree, 'NN')
    [(0, 2), (2, 1)]

Caveats:
--------

- Link modifiers: "?" and "=" are not implemented.
- Tgrep compatibility: Using "@" for "!", "{" for "<", "}" for ">" are
  not implemented.
- Labeled nodes are not implemented.
- The "=" and "~" links are not implemented.
- Segmented patterns using ":" are not implemented.
- Multiple patterns using ";" are not implemented.
- Macros are not implemented.

Known Issues:
-------------

- There are some issues with link relations involving leaf nodes
  (which are represented as bare strings in NLTK trees).  For
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