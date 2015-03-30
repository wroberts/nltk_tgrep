#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

'''
TGrep search implementation for NTLK trees.

(c) 16 March, 2013 Will Roberts <wildwilhelm@gmail.com>.

This module supports TGrep2 syntax for matching parts of NLTK Trees.
Note that many tgrep operators require the tree passed to be a
ParentedTree.

Tgrep tutorial:
http://www.stanford.edu/dept/linguistics/corpora/cas-tut-tgrep.html
Tgrep2 manual:
http://tedlab.mit.edu/~dr/Tgrep2/tgrep2.pdf
Tgrep2 source:
http://tedlab.mit.edu/~dr/Tgrep2/
'''

from __future__ import unicode_literals
from builtins import bytes, range, str
import nltk.tree
import pyparsing
import re

class TgrepException(Exception):
    '''Tgrep exception type.'''
    pass

def ancestors(node):
    '''
    Returns the list of all nodes dominating the given tree node.
    This method will not work with leaf nodes, since there is no way
    to recover the parent.
    '''
    results = []
    try:
        current = node.parent()
    except AttributeError:
        # if node is a leaf, we cannot retrieve its parent
        return results
    while current:
        results.append(current)
        current = current.parent()
    return results

def unique_ancestors(node):
    '''
    Returns the list of all nodes dominating the given node, where
    there is only a single path of descent.
    '''
    results = []
    try:
        current = node.parent()
    except AttributeError:
        # if node is a leaf, we cannot retrieve its parent
        return results
    while current and len(current) == 1:
        results.append(current)
        current = current.parent()
    return results

def _descendants(node):
    '''
    Returns the list of all nodes which are descended from the given
    tree node in some way.
    '''
    try:
        treepos = node.treepositions()
    except AttributeError:
        return []
    return [node[x] for x in treepos[1:]]

def _leftmost_descendants(node):
    '''
    Returns the set of all nodes descended in some way through
    left branches from this node.
    '''
    try:
        treepos = node.treepositions()
    except AttributeError:
        return []
    return [node[x] for x in treepos[1:] if all(y == 0 for y in x)]

def _rightmost_descendants(node):
    '''
    Returns the set of all nodes descended in some way through
    right branches from this node.
    '''
    try:
        rightmost_leaf = max(node.treepositions())
    except AttributeError:
        return []
    return [node[rightmost_leaf[:i]] for i in range(1, len(rightmost_leaf) + 1)]

def _istree(obj):
    '''Predicate to check whether `obj` is a nltk.tree.Tree.'''
    return isinstance(obj, nltk.tree.Tree)

def _unique_descendants(node):
    '''
    Returns the list of all nodes descended from the given node, where
    there is only a single path of descent.
    '''
    results = []
    current = node
    while current and _istree(current) and len(current) == 1:
        current = current[0]
        results.append(current)
    return results

def _before(node):
    '''
    Returns the set of all nodes that are before the given node.
    '''
    try:
        pos = node.treeposition()
        tree = node.root()
    except AttributeError:
        return []
    return [tree[x] for x in tree.treepositions()
            if x[:len(pos)] < pos[:len(x)]]

def _immediately_before(node):
    '''
    Returns the set of all nodes that are immediately before the given
    node.

    Tree node A immediately precedes node B if the last terminal
    symbol (word) produced by A immediately precedes the first
    terminal symbol produced by B.
    '''
    try:
        pos = node.treeposition()
        tree = node.root()
    except AttributeError:
        return []
    # go "upwards" from pos until there is a place we can go to the left
    idx = len(pos) - 1
    while 0 <= idx and pos[idx] == 0:
        idx -= 1
    if idx < 0:
        return []
    pos = list(pos[:idx + 1])
    pos[-1] -= 1
    before = tree[pos]
    return [before] + _rightmost_descendants(before)

def _after(node):
    '''
    Returns the set of all nodes that are after the given node.
    '''
    try:
        pos = node.treeposition()
        tree = node.root()
    except AttributeError:
        return []
    return [tree[x] for x in tree.treepositions()
            if x[:len(pos)] > pos[:len(x)]]

def _immediately_after(node):
    '''
    Returns the set of all nodes that are immediately after the given
    node.

    Tree node A immediately follows node B if the first terminal
    symbol (word) produced by A immediately follows the last
    terminal symbol produced by B.
    '''
    try:
        pos = node.treeposition()
        tree = node.root()
        current = node.parent()
    except AttributeError:
        return []
    # go "upwards" from pos until there is a place we can go to the
    # right
    idx = len(pos) - 1
    while 0 <= idx and pos[idx] == len(current) - 1:
        idx -= 1
        current = current.parent()
    if idx < 0:
        return []
    pos = list(pos[:idx + 1])
    pos[-1] += 1
    after = tree[pos]
    return [after] + _leftmost_descendants(after)

def _tgrep_node_literal_value(node):
    '''
    Gets the string value of a given parse tree node, for comparison
    using the tgrep node literal predicates.
    '''
    return (node.label() if _istree(node) else str(node))

def _tgrep_macro_use_action(_s, _l, tokens):
    '''
    Builds a lambda function which looks up the macro name used.
    '''
    assert len(tokens) == 1
    assert tokens[0][0] == '@'
    macro_name = tokens[0][1:]
    def macro_use(n, m=None):
        if m is None or macro_name not in m:
            raise TgrepException('macro {0} not defined'.format(macro_name))
        return m[macro_name](n, m)
    return macro_use

def _tgrep_node_action(_s, _l, tokens):
    '''
    Builds a lambda function representing a predicate on a tree node
    depending on the name of its node.
    '''
    # print 'node tokens: ', tokens
    if tokens[0] == "'":
        # strip initial apostrophe (tgrep2 print command)
        tokens = tokens[1:]
    if len(tokens) > 1:
        # disjunctive definition of a node name
        assert list(set(tokens[1::2])) == ['|']
        # recursively call self to interpret each node name definition
        tokens = [_tgrep_node_action(None, None, [node])
                  for node in tokens[::2]]
        # capture tokens and return the disjunction
        return (lambda t: lambda n, m=None: any(f(n, m) for f in t))(tokens)
    else:
        if hasattr(tokens[0], '__call__'):
            # this is a previously interpreted parenthetical node
            # definition (lambda function)
            return tokens[0]
        elif tokens[0] == '*' or tokens[0] == '__':
            return lambda n, m=None: True
        elif tokens[0].startswith('"'):
            assert tokens[0].endswith('"')
            node_lit = tokens[0][1:-1].replace('\\"', '"').replace('\\\\', '\\')
            return (lambda s: lambda n, m=None: _tgrep_node_literal_value(n) == s)(node_lit)
        elif tokens[0].startswith('/'):
            assert tokens[0].endswith('/')
            node_lit = tokens[0][1:-1]
            return (lambda r: lambda n, m=None:
                    r.search(_tgrep_node_literal_value(n)))(re.compile(node_lit))
        elif tokens[0].startswith('i@'):
            node_func = _tgrep_node_action(_s, _l, [tokens[0][2:].lower()])
            return (lambda f: lambda n, m=None:
                    f(_tgrep_node_literal_value(n).lower()))(node_func)
        else:
            return (lambda s: lambda n, m=None: _tgrep_node_literal_value(n) == s)(tokens[0])

def _tgrep_parens_action(_s, _l, tokens):
    '''
    Builds a lambda function representing a predicate on a tree node
    from a parenthetical notation.
    '''
    # print 'parenthetical tokens: ', tokens
    assert len(tokens) == 3
    assert tokens[0] == '('
    assert tokens[2] == ')'
    return tokens[1]

def _tgrep_nltk_tree_pos_action(_s, _l, tokens):
    '''
    Builds a lambda function representing a predicate on a tree node
    which returns true if the node is located at a specific tree
    position.
    '''
    # recover the tuple from the parsed sting
    node_tree_position = tuple(int(x) for x in tokens if x.isdigit())
    # capture the node's tree position
    return (lambda i: lambda n, m=None: (hasattr(n, 'treeposition') and
                                         n.treeposition() == i))(node_tree_position)

def _tgrep_relation_action(_s, _l, tokens):
    '''
    Builds a lambda function representing a predicate on a tree node
    depending on its relation to other nodes in the tree.
    '''
    # print 'relation tokens: ', tokens
    # process negation first if needed
    negated = False
    if tokens[0] == '!':
        negated = True
        tokens = tokens[1:]
    if tokens[0] == '[':
        # process square-bracketed relation expressions
        assert len(tokens) == 3
        assert tokens[2] == ']'
        retval = tokens[1]
    else:
        # process operator-node relation expressions
        assert len(tokens) == 2
        operator, predicate = tokens
        # A < B       A is the parent of (immediately dominates) B.
        if operator == '<':
            retval = lambda n, m=None: (_istree(n) and
                                        any(predicate(x, m) for x in n))
        # A > B       A is the child of B.
        elif operator == '>':
            retval = lambda n, m=None: (hasattr(n, 'parent') and
                                        bool(n.parent()) and
                                        predicate(n.parent(), m))
        # A <, B      Synonymous with A <1 B.
        elif operator == '<,' or operator == '<1':
            retval = lambda n, m=None: (_istree(n) and
                                        bool(list(n)) and
                                        predicate(n[0], m))
        # A >, B      Synonymous with A >1 B.
        elif operator == '>,' or operator == '>1':
            retval = lambda n, m=None: (hasattr(n, 'parent') and
                                        bool(n.parent()) and
                                        (n is n.parent()[0]) and
                                        predicate(n.parent(), m))
        # A <N B      B is the Nth child of A (the first child is <1).
        elif operator[0] == '<' and operator[1:].isdigit():
            idx = int(operator[1:])
            # capture the index parameter
            retval = (lambda i: lambda n, m=None: (_istree(n) and
                                                   bool(list(n)) and
                                                   0 <= i < len(n) and
                                                   predicate(n[i], m)))(idx - 1)
        # A >N B      A is the Nth child of B (the first child is >1).
        elif operator[0] == '>' and operator[1:].isdigit():
            idx = int(operator[1:])
            # capture the index parameter
            retval = (lambda i: lambda n, m=None: (hasattr(n, 'parent') and
                                                   bool(n.parent()) and
                                                   0 <= i < len(n.parent()) and
                                                   (n is n.parent()[i]) and
                                                   predicate(n.parent(), m)))(idx - 1)
        # A <' B      B is the last child of A (also synonymous with A <-1 B).
        # A <- B      B is the last child of A (synonymous with A <-1 B).
        elif operator == '<\'' or operator == '<-' or operator == '<-1':
            retval = lambda n, m=None: (_istree(n) and bool(list(n))
                                        and predicate(n[-1], m))
        # A >' B      A is the last child of B (also synonymous with A >-1 B).
        # A >- B      A is the last child of B (synonymous with A >-1 B).
        elif operator == '>\'' or operator == '>-' or operator == '>-1':
            retval = lambda n, m=None: (hasattr(n, 'parent') and
                                        bool(n.parent()) and
                                        (n is n.parent()[-1]) and
                                        predicate(n.parent(), m))
        # A <-N B 	  B is the N th-to-last child of A (the last child is <-1).
        elif operator[:2] == '<-' and operator[2:].isdigit():
            idx = -int(operator[2:])
            # capture the index parameter
            retval = (lambda i: lambda n, m=None: (_istree(n) and
                                                   bool(list(n)) and
                                                   0 <= (i + len(n)) < len(n) and
                                                   predicate(n[i + len(n)], m)))(idx)
        # A >-N B 	  A is the N th-to-last child of B (the last child is >-1).
        elif operator[:2] == '>-' and operator[2:].isdigit():
            idx = -int(operator[2:])
            # capture the index parameter
            retval = (lambda i: lambda n, m=None:
                          (hasattr(n, 'parent') and
                           bool(n.parent()) and
                           0 <= (i + len(n.parent())) < len(n.parent()) and
                           (n is n.parent()[i + len(n.parent())]) and
                           predicate(n.parent(), m)))(idx)
        # A <: B      B is the only child of A
        elif operator == '<:':
            retval = lambda n, m=None: (_istree(n) and
                                        len(n) == 1 and
                                        predicate(n[0], m))
        # A >: B      A is the only child of B.
        elif operator == '>:':
            retval = lambda n, m=None: (hasattr(n, 'parent') and
                                        bool(n.parent()) and
                                        len(n.parent()) == 1 and
                                        predicate(n.parent(), m))
        # A << B      A dominates B (A is an ancestor of B).
        elif operator == '<<':
            retval = lambda n, m=None: (_istree(n) and
                                        any(predicate(x, m) for x in _descendants(n)))
        # A >> B      A is dominated by B (A is a descendant of B).
        elif operator == '>>':
            retval = lambda n, m=None: any(predicate(x, m) for x in ancestors(n))
        # A <<, B     B is a left-most descendant of A.
        elif operator == '<<,' or operator == '<<1':
            retval = lambda n, m=None: (_istree(n) and
                                        any(predicate(x, m)
                                            for x in _leftmost_descendants(n)))
        # A >>, B     A is a left-most descendant of B.
        elif operator == '>>,':
            retval = lambda n, m=None: any((predicate(x, m) and
                                            n in _leftmost_descendants(x))
                                           for x in ancestors(n))
        # A <<' B     B is a right-most descendant of A.
        elif operator == '<<\'':
            retval = lambda n, m=None: (_istree(n) and
                                        any(predicate(x, m)
                                            for x in _rightmost_descendants(n)))
        # A >>' B     A is a right-most descendant of B.
        elif operator == '>>\'':
            retval = lambda n, m=None: any((predicate(x, m) and
                                            n in _rightmost_descendants(x))
                                           for x in ancestors(n))
        # A <<: B     There is a single path of descent from A and B is on it.
        elif operator == '<<:':
            retval = lambda n, m=None: (_istree(n) and
                                        any(predicate(x, m)
                                            for x in _unique_descendants(n)))
        # A >>: B     There is a single path of descent from B and A is on it.
        elif operator == '>>:':
            retval = lambda n, m=None: any(predicate(x, m) for x in unique_ancestors(n))
        # A . B       A immediately precedes B.
        elif operator == '.':
            retval = lambda n, m=None: any(predicate(x, m)
                                   for x in _immediately_after(n))
        # A , B       A immediately follows B.
        elif operator == ',':
            retval = lambda n, m=None: any(predicate(x, m)
                                   for x in _immediately_before(n))
        # A .. B      A precedes B.
        elif operator == '..':
            retval = lambda n, m=None: any(predicate(x, m) for x in _after(n))
        # A ,, B      A follows B.
        elif operator == ',,':
            retval = lambda n, m=None: any(predicate(x, m) for x in _before(n))
        # A $ B       A is a sister of B (and A != B).
        elif operator == '$' or operator == '%':
            retval = lambda n, m=None: (hasattr(n, 'parent') and
                                        bool(n.parent()) and
                                        any(predicate(x, m)
                                            for x in n.parent() if x is not n))
        # A $. B      A is a sister of and immediately precedes B.
        elif operator == '$.' or operator == '%.':
            retval = lambda n, m=None: (hasattr(n, 'right_sibling') and
                                        bool(n.right_sibling()) and
                                        predicate(n.right_sibling(), m))
        # A $, B      A is a sister of and immediately follows B.
        elif operator == '$,' or operator == '%,':
            retval = lambda n, m=None: (hasattr(n, 'left_sibling') and
                                        bool(n.left_sibling()) and
                                        predicate(n.left_sibling(), m))
        # A $.. B     A is a sister of and precedes B.
        elif operator == '$..' or operator == '%..':
            retval = lambda n, m=None: (hasattr(n, 'parent') and
                                        hasattr(n, 'parent_index') and
                                        bool(n.parent()) and
                                        any(predicate(x, m) for x in
                                            n.parent()[n.parent_index() + 1:]))
        # A $,, B     A is a sister of and follows B.
        elif operator == '$,,' or operator == '%,,':
            retval = lambda n, m=None: (hasattr(n, 'parent') and
                                        hasattr(n, 'parent_index') and
                                        bool(n.parent()) and
                                        any(predicate(x, m) for x in
                                            n.parent()[:n.parent_index()]))
        else:
            raise TgrepException(
                'cannot interpret tgrep operator "{0}"'.format(operator))
    # now return the built function
    if negated:
        return (lambda r: (lambda n, m=None: not r(n, m)))(retval)
    else:
        return retval

def _tgrep_rel_conjunction_action(_s, _l, tokens):
    '''
    Builds a lambda function representing a predicate on a tree node
    from the conjunction of several other such lambda functions.
    '''
    # filter out the ampersand
    tokens = [x for x in tokens if x != '&']
    # print 'relation conjunction tokens: ', tokens
    if len(tokens) == 1:
        return tokens[0]
    elif len(tokens) == 2:
        return (lambda a, b: lambda n, m=None: a(n, m) and b(n, m))(tokens[0], tokens[1])

def _tgrep_rel_disjunction_action(_s, _l, tokens):
    '''
    Builds a lambda function representing a predicate on a tree node
    from the disjunction of several other such lambda functions.
    '''
    # filter out the pipe
    tokens = [x for x in tokens if x != '|']
    # print 'relation disjunction tokens: ', tokens
    if len(tokens) == 1:
        return tokens[0]
    elif len(tokens) == 2:
        return (lambda a, b: lambda n, m=None: a(n, m) or b(n, m))(tokens[0], tokens[1])

def _macro_defn_action(_s, _l, tokens):
    '''
    Builds a dictionary structure which defines the given macro.
    '''
    assert len(tokens) == 3
    assert tokens[0] == '@'
    return {tokens[1]: tokens[2]}

def _tgrep_exprs_action(_s, _l, tokens):
    '''
    Builds a lambda function representing a predicate on a tree node
    from the disjunction of several tgrep expressions.  Also handles
    macro definitions and macro name binding.
    '''
    if len(tokens) == 1:
        return tokens[0]
    assert list(set(tokens[1::2])) == [';']
    # collect all macro definitions
    macro_dict = {}
    macro_defs = [tok for tok in tokens[::2] if isinstance(tok, dict)]
    for macro_def in macro_defs:
        macro_dict.update(macro_def)
    # collect all tgrep expressions
    tgrep_exprs = [tok for tok in tokens[::2] if not isinstance(tok, dict)]
    # bind macro definitions and OR together all tgrep_exprs
    return lambda n, m=macro_dict: any(predicate(n, m) for predicate in tgrep_exprs)

def _build_tgrep_parser(set_parse_actions = True):
    '''
    Builds a pyparsing-based parser object for tokenizing and
    interpreting tgrep search strings.
    '''
    tgrep_op = (pyparsing.Optional('!') +
                pyparsing.Regex('[$%,.<>][%,.<>0-9-\':]*'))
    tgrep_qstring = pyparsing.QuotedString(quoteChar='"', escChar='\\',
                                           unquoteResults=False)
    tgrep_node_regex = pyparsing.QuotedString(quoteChar='/', escChar='\\',
                                              unquoteResults=False)
    tgrep_qstring_icase = pyparsing.Regex(
        'i@\\"(?:[^"\\n\\r\\\\]|(?:\\\\.))*\\"')
    tgrep_node_regex_icase = pyparsing.Regex(
        'i@\\/(?:[^/\\n\\r\\\\]|(?:\\\\.))*\\/')
    tgrep_node_literal = pyparsing.Regex('[^][ \r\t\n;:.,&|<>()$!@%\'^=]+')
    tgrep_expr = pyparsing.Forward()
    tgrep_relations = pyparsing.Forward()
    tgrep_parens = pyparsing.Literal('(') + tgrep_expr + ')'
    tgrep_nltk_tree_pos = (
        pyparsing.Literal('N(') +
        pyparsing.Optional(pyparsing.Word(pyparsing.nums) + ',' +
                           pyparsing.Optional(pyparsing.delimitedList(
                    pyparsing.Word(pyparsing.nums), delim=',') +
                                              pyparsing.Optional(','))) + ')')
    tgrep_node_expr = (tgrep_qstring_icase |
                       tgrep_node_regex_icase |
                       tgrep_qstring |
                       tgrep_node_regex |
                       '*' |
                       tgrep_node_literal)
    macro_name = pyparsing.Regex('[^];:.,&|<>()[$!@%\'^=\r\t\n ]+')
    macro_name.setWhitespaceChars('')
    macro_use = pyparsing.Combine('@' + macro_name)
    tgrep_node = (macro_use |
                  tgrep_parens |
                  tgrep_nltk_tree_pos |
                  (pyparsing.Optional("'") +
                   tgrep_node_expr +
                   pyparsing.ZeroOrMore("|" + tgrep_node_expr)))
    tgrep_brackets = pyparsing.Optional('!') + '[' + tgrep_relations + ']'
    tgrep_relation = tgrep_brackets | (tgrep_op + tgrep_node)
    tgrep_rel_conjunction = pyparsing.Forward()
    tgrep_rel_conjunction << (tgrep_relation +
                              pyparsing.ZeroOrMore(pyparsing.Optional('&') +
                                                   tgrep_rel_conjunction))
    tgrep_relations << tgrep_rel_conjunction + pyparsing.ZeroOrMore(
        "|" + tgrep_relations)
    tgrep_expr << tgrep_node + pyparsing.Optional(tgrep_relations)
    macro_defn = (pyparsing.Literal('@') +
                  pyparsing.White().suppress() +
                  macro_name +
                  tgrep_expr)
    tgrep_exprs = (pyparsing.ZeroOrMore((macro_defn | tgrep_expr) + ';') +
                   tgrep_expr +
                   pyparsing.ZeroOrMore(';' + (macro_defn | tgrep_expr)))
    if set_parse_actions:
        macro_use.setParseAction(_tgrep_macro_use_action)
        tgrep_node.setParseAction(_tgrep_node_action)
        tgrep_parens.setParseAction(_tgrep_parens_action)
        tgrep_nltk_tree_pos.setParseAction(_tgrep_nltk_tree_pos_action)
        tgrep_relation.setParseAction(_tgrep_relation_action)
        tgrep_rel_conjunction.setParseAction(_tgrep_rel_conjunction_action)
        tgrep_relations.setParseAction(_tgrep_rel_disjunction_action)
        macro_defn.setParseAction(_macro_defn_action)
        # the whole expression is also the conjunction of two
        # predicates: the first node predicate, and the remaining
        # relation predicates
        tgrep_expr.setParseAction(_tgrep_rel_conjunction_action)
        tgrep_exprs.setParseAction(_tgrep_exprs_action)
    return tgrep_exprs.ignore('#' + pyparsing.restOfLine)

def tgrep_tokenize(tgrep_string):
    '''
    Tokenizes a TGrep search string into separate tokens.
    '''
    parser = _build_tgrep_parser(False)
    if isinstance(tgrep_string, bytes):
        tgrep_string = tgrep_string.decode()
    return list(parser.parseString(tgrep_string))

def tgrep_compile(tgrep_string):
    '''
    Parses (and tokenizes, if necessary) a TGrep search string into a
    lambda function.
    '''
    parser = _build_tgrep_parser(True)
    if isinstance(tgrep_string, bytes):
        tgrep_string = tgrep_string.decode()
    return list(parser.parseString(tgrep_string, parseAll=True))[0]

def treepositions_no_leaves(tree):
    '''
    Returns all the tree positions in the given tree which are not
    leaf nodes.
    '''
    treepositions = tree.treepositions()
    # leaves are treeposition tuples that are not prefixes of any
    # other treeposition
    prefixes = set()
    for pos in treepositions:
        for length in range(len(pos)):
            prefixes.add(pos[:length])
    return [pos for pos in treepositions if pos in prefixes]

def tgrep_positions(tree, tgrep_string, search_leaves = True):
    '''
    Return all tree positions in the given tree which match the given
    `tgrep_string`.

    If `search_leaves` is False, the method will not return any
    results in leaf positions.
    '''
    try:
        if search_leaves:
            search_positions = tree.treepositions()
        else:
            search_positions = treepositions_no_leaves(tree)
    except AttributeError:
        return []
    if isinstance(tgrep_string, (bytes, str)):
        tgrep_string = tgrep_compile(tgrep_string)
    return [position for position in search_positions
            if tgrep_string(tree[position])]

def tgrep_nodes(tree, tgrep_string, search_leaves = True):
    '''
    Return all tree nodes in the given tree which match the given
    `tgrep_ string`.

    If `search_leaves` is False, the method will not return any
    results in leaf positions.
    '''
    return [tree[position] for position in tgrep_positions(tree, tgrep_string,
                                                           search_leaves)]
