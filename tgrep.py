#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
TGrep search implementation for NTLK trees.

(c) 16 March, 2013 Will Roberts

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

import nltk.tree
import pyparsing
import re

def _ancestors(node):
    '''
    Returns the list of all nodes dominating the given tree node.
    This method will not work with leaf nodes, since there is no way
    to recover the parent.
    '''
    results = []
    # if node is a leaf, we cannot retrieve its parent
    if not hasattr(node, 'parent'):
        return []
    current = node.parent()
    while current:
        results.append(current)
        current = current.parent()
    return results

def _descendants(node):
    '''
    Returns the list of all nodes which are descended from the given
    tree node in some way.
    '''
    if not hasattr(node, 'treepositions'):
        return []
    return [node[x] for x in node.treepositions()[1:]]

def _leftmost_descendants(node):
    '''
    Returns the set of all nodes descended in some way through
    left branches from this node.
    '''
    if not hasattr(node, 'treepositions'):
        return []
    return [node[x] for x in node.treepositions()[1:] if all(y == 0 for y in x)]

def _rightmost_descendants(node):
    '''
    Returns the set of all nodes descended in some way through
    right branches from this node.
    '''
    if not hasattr(node, 'treepositions'):
        return []
    rightmost_leaf = max(node.treepositions())
    return [node[rightmost_leaf[:i]] for i in range(1, len(rightmost_leaf) + 1)]

def _immediately_before(node):
    '''
    Returns the set of all nodes that are immediately before the given
    node.
    '''
    if not hasattr(node, 'root') and hasattr(node, 'treeposition'):
        return []
    tree = node.root()
    pos = node.treeposition()
    largest_pos_before = set(x[:len(pos)]
                             for x in tree.treepositions() if x[:len(pos)] < pos[:len(x)])
    if not largest_pos_before:
        return []
    largest_pos_before = max(largest_pos_before)
    # find the index+1 of the first location where pos and
    # largest_pos_before are not equal
    height = [(i+1) for i,(x,y) in
              enumerate(zip(pos, largest_pos_before)) if x != y]
    if height:
        largest_pos_before = largest_pos_before[:min(height)]
    before = tree[largest_pos_before]
    return [before] + _rightmost_descendants(before)

def _immediately_after(node):
    '''
    Returns the set of all nodes that are immediately after the given
    node.
    '''
    if not hasattr(node, 'root') and hasattr(node, 'treeposition'):
        return []
    tree = node.root()
    pos = node.treeposition()
    smallest_pos_after = set(x[:len(pos)]
                             for x in tree.treepositions() if x[:len(pos)] > pos[:len(x)])
    if not smallest_pos_after:
        return []
    smallest_pos_after = min(smallest_pos_after)
    # find the index+1 of the first location where pos and
    # smallest_pos_after are not equal
    height = [(i+1) for i,(x,y) in
              enumerate(zip(pos, smallest_pos_after)) if x != y]
    if height:
        smallest_pos_after = smallest_pos_after[:min(height)]
    after = tree[smallest_pos_after]
    return [after] + _leftmost_descendants(after)

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
        tokens = [_tgrep_node_action(None, None, [node]) for node in tokens[::2]]
        # capture tokens and return the disjunction
        return (lambda t: lambda n: any(f(n) for f in t))(tokens)
    else:
        if hasattr(tokens[0], '__call__'):
            # this is a previously interpreted parenthetical node
            # definition (lambda function)
            return tokens[0]
        elif tokens[0] == '*' or tokens[0] == '__':
            return lambda n: True
        elif tokens[0].startswith('"'):
            return (lambda s: lambda n: (n.node if isinstance(n, nltk.tree.Tree)
                                         else n) == s)(tokens[0].strip('"'))
        elif tokens[0].startswith('/'):
            return (lambda r: lambda n:
                    r.match(n.node if isinstance(n, nltk.tree.Tree)
                            else n))(re.compile(tokens[0].strip('/')))
        elif tokens[0].startswith('i@'):
            return (lambda s: lambda n:
                    (n.node if isinstance(n, nltk.tree.Tree)
                     else n).lower() == s)(tokens[0][2:].lower())
        else:
            return (lambda s: lambda n: (n.node if isinstance(n, nltk.tree.Tree)
                                         else n) == s)(tokens[0])

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

def _tgrep_relation_action(_s, _l, tokens):
    '''
    Builds a lambda function representing a predicate on a tree node
    depending on its relation to other nodes in the tree.
    '''
    # print 'relation tokens: ', tokens
    if tokens[0] == '[' or (tokens[0] == '!' and tokens[1] == '['):
        assert False, 'parsing square brackets not yet implemented' # NYI
    else:
        negated = False
        if tokens[0] == '!':
            negated = True
            tokens = tokens[1:]
        assert len(tokens) == 2
        operator, predicate = tokens
        # A < B       A is the parent of (immediately dominates) B.
        if operator == '<':
            retval = lambda n: (isinstance(n, nltk.tree.Tree) and
                                any([predicate(x) for x in n]))
        # A > B       A is the child of B.
        elif operator == '>':
            retval = lambda n: (hasattr(n, 'parent') and
                                bool(n.parent()) and
                                predicate(n.parent()))
        # A <, B      Synonymous with A <1 B.
        elif operator == '<,' or operator == '<1':
            retval = lambda n: (isinstance(n, nltk.tree.Tree) and
                                bool(list(n)) and
                                predicate(n[0]))
        # A >, B      Synonymous with A >1 B.
        elif operator == '>,' or operator == '>1':
            retval = lambda n: (hasattr(n, 'parent') and
                                bool(n.parent()) and
                                (n is n.parent()[0]) and
                                predicate(n.parent()))
        # A <N B      B is the Nth child of A (the first child is <1).
        elif operator[0] == '<' and operator[1:].isdigit():
            idx = int(operator[1:])
            # capture the index parameter
            retval = (lambda i: lambda n: (isinstance(n, nltk.tree.Tree) and
                                           bool(list(n)) and
                                           0 <= i < len(n) and
                                           predicate(n[i])))(idx - 1)
        # A >N B      A is the Nth child of B (the first child is >1).
        elif operator[0] == '>' and operator[1:].isdigit():
            idx = int(operator[1:])
            # capture the index parameter
            retval = (lambda i: lambda n: (hasattr(n, 'parent') and
                                           bool(n.parent()) and
                                           0 <= i < len(n.parent()) and
                                           (n is n.parent()[i]) and
                                           predicate(n.parent())))(idx - 1)
        # A <' B      B is the last child of A (also synonymous with A <-1 B).
        # A <- B      B is the last child of A (synonymous with A <-1 B).
        elif operator == '<\'' or operator == '<-' or operator == '<-1':
            retval = lambda n: (isinstance(n, nltk.tree.Tree) and bool(list(n))
                                and predicate(n[-1]))
        # A >' B      A is the last child of B (also synonymous with A >-1 B).
        # A >- B      A is the last child of B (synonymous with A >-1 B).
        elif operator == '>\'' or operator == '>-' or operator == '>-1':
            retval = lambda n: (hasattr(n, 'parent') and
                                bool(n.parent()) and
                                (n is n.parent()[-1]) and
                                predicate(n.parent()))
        # A <-N B 	  B is the N th-to-last child of A (the last child is <-1).
        elif operator[:2] == '<-' and operator[2:].isdigit():
            idx = -int(operator[2:])
            # capture the index parameter
            retval = (lambda i: lambda n: (isinstance(n, nltk.tree.Tree) and
                                           bool(list(n)) and
                                           0 <= (i + len(n)) < len(n) and
                                           predicate(n[i + len(n)])))(idx)
        # A >-N B 	  A is the N th-to-last child of B (the last child is >-1).
        elif operator[:2] == '>-' and operator[2:].isdigit():
            idx = -int(operator[2:])
            # capture the index parameter
            retval = (lambda i: lambda n: (hasattr(n, 'parent') and
                                           bool(n.parent()) and
                                           0 <= (i + len(n.parent())) < len(n.parent()) and
                                           (n is n.parent()[i + len(n.parent())]) and
                                           predicate(n.parent())))(idx)
        # A <: B      B is the only child of A
        elif operator == '<:':
            retval = lambda n: (isinstance(n, nltk.tree.Tree) and
                                len(n) == 1 and
                                predicate(n[0]))
        # A >: B      A is the only child of B.
        elif operator == '>:':
            retval = lambda n: (hasattr(n, 'parent') and
                                bool(n.parent()) and
                                len(n.parent()) == 1 and
                                predicate(n.parent()))
        # A << B      A dominates B (A is an ancestor of B).
        elif operator == '<<':
            retval = lambda n: (isinstance(n, nltk.tree.Tree) and
                                any([predicate(x) for x in _descendants(n)]))
        # A >> B      A is dominated by B (A is a descendant of B).
        elif operator == '>>':
            retval = lambda n: any([predicate(x) for x in _ancestors(n)])
        # A <<, B     B is a left-most descendant of A.
        elif operator == '<<,' or operator == '<<1':
            retval = lambda n: (isinstance(n, nltk.tree.Tree) and
                                any([predicate(x)
                                     for x in _leftmost_descendants(n)]))
        # A >>, B     A is a left-most descendant of B.
        elif operator == '>>,':
            retval = lambda n: any([(predicate(x) and
                                     n in _leftmost_descendants(x))
                                    for x in _ancestors(n)])
        # A <<' B     B is a right-most descendant of A.
        elif operator == '<<\'':
            retval = lambda n: (isinstance(n, nltk.tree.Tree) and
                                any([predicate(x)
                                     for x in _rightmost_descendants(n)]))
        # A >>' B     A is a right-most descendant of B.
        elif operator == '>>\'':
            retval = lambda n: any([(predicate(x) and
                                     n in _rightmost_descendants(x))
                                    for x in _ancestors(n)])
        # A <<: B     There is a single path of descent from A and B is on it.
        elif operator == '<<:':
            assert False, 'operator "<<:" is not yet implemented' # NYI
        # A >>: B     There is a single path of descent from B and A is on it.
        elif operator == '>>:':
            assert False, 'operator ">>:" is not yet implemented' # NYI
        # A . B       A immediately precedes B.
        elif operator == '.':
            assert False, 'operator "." is not yet implemented' # NYI
        # A , B       A immediately follows B.
        elif operator == ',':
            assert False, 'operator "," is not yet implemented' # NYI
        # A .. B      A precedes B.
        elif operator == '..':
            assert False, 'operator ".." is not yet implemented' # NYI
        # A ,, B      A follows B.
        elif operator == ',,':
            assert False, 'operator ",," is not yet implemented' # NYI
        # A $ B       A is a sister of B (and A != B).
        elif operator == '$' or operator == '%':
            retval = lambda n: (hasattr(n, 'parent') and
                                bool(n.parent()) and
                                any([predicate(x)
                                     for x in n.parent() if x is not n]))
        # A $. B      A is a sister of and immediately precedes B.
        elif operator == '$.' or operator == '%.':
            retval = lambda n: (hasattr(n, 'right_sibling') and
                                bool(n.right_sibling()) and
                                predicate(n.right_sibling()))
        # A $, B      A is a sister of and immediately follows B.
        elif operator == '$,' or operator == '%,':
            retval = lambda n: (hasattr(n, 'left_sibling') and
                                bool(n.left_sibling()) and
                                predicate(n.left_sibling()))
        # A $.. B     A is a sister of and precedes B.
        elif operator == '$..' or operator == '%..':
            retval = lambda n: (hasattr(n, 'parent') and
                                hasattr(n, 'parent_index') and
                                bool(n.parent()) and
                                any([predicate(x) for x in
                                     n.parent()[n.parent_index() + 1:]]))
        # A $,, B     A is a sister of and follows B.
        elif operator == '$,,' or operator == '%,,':
            retval = lambda n: (hasattr(n, 'parent') and
                                hasattr(n, 'parent_index') and
                                bool(n.parent()) and
                                any([predicate(x) for x in
                                     n.parent()[:n.parent_index()]]))
        else:
            assert False, 'cannot interpret tgrep operator "{0}"'.format(
                operator)
        # now return the built function
        if negated:
            return (lambda r: (lambda n: not r(n)))(retval)
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
        return (lambda a, b: lambda n: a(n) and b(n))(tokens[0], tokens[1])

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
        return (lambda a, b: lambda n: a(n) or b(n))(tokens[0], tokens[1])

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
    tgrep_node_literal = pyparsing.Regex('[^][ \r\t\n;:.,&|<>()$!@%\'^=]+')
    tgrep_expr = pyparsing.Forward()
    tgrep_relations = pyparsing.Forward()
    tgrep_parens = pyparsing.Literal('(') + tgrep_expr + ')'
    tgrep_node_expr = (tgrep_qstring |
                       tgrep_node_regex |
                       '*' |
                       tgrep_node_literal)
    tgrep_node = (tgrep_parens |
                  (pyparsing.Optional("'") +
                   tgrep_node_expr + pyparsing.ZeroOrMore("|" + tgrep_node_expr)))
    tgrep_relation = pyparsing.Forward()
    tgrep_brackets = pyparsing.Optional('!') + '[' + tgrep_relations + ']'
    tgrep_relation = tgrep_brackets | tgrep_op + tgrep_node
    tgrep_rel_conjunction = pyparsing.Forward()
    tgrep_rel_conjunction << (tgrep_relation +
                              pyparsing.ZeroOrMore(pyparsing.Optional('&') +
                                                   tgrep_rel_conjunction))
    tgrep_relations << tgrep_rel_conjunction + pyparsing.ZeroOrMore(
        "|" + tgrep_relations)
    tgrep_expr << tgrep_node + pyparsing.Optional(tgrep_relations)
    if set_parse_actions:
        tgrep_node.setParseAction(_tgrep_node_action)
        tgrep_parens.setParseAction(_tgrep_parens_action)
        tgrep_relation.setParseAction(_tgrep_relation_action)
        tgrep_rel_conjunction.setParseAction(_tgrep_rel_conjunction_action)
        tgrep_relations.setParseAction(_tgrep_rel_disjunction_action)
        # the whole expression is also the conjunction of two
        # predicates: the first node predicate, and the remaining
        # relation predicates
        tgrep_expr.setParseAction(_tgrep_rel_conjunction_action)
    return tgrep_expr

def tgrep_tokenize(tgrep_string):
    '''
    Tokenizes a TGrep search string into separate tokens.
    '''
    parser = _build_tgrep_parser(False)
    return list(parser.parseString(tgrep_string))

def tgrep_compile(tgrep_string):
    '''
    Parses (and tokenizes, if necessary) a TGrep search string into a
    lambda function.
    '''
    parser = _build_tgrep_parser(True)
    return list(parser.parseString(tgrep_string))[0]

def tgrep_positions(tree, tgrep_string):
    '''
    Return all tree positions in the given tree which match the given
    tgrep string.
    '''
    if not hasattr(tree, 'treepositions'):
        return []
    if isinstance(tgrep_string, basestring):
        tgrep_string = tgrep_compile(tgrep_string)
    return [position for position in tree.treepositions()
            if tgrep_string(tree[position])]

def tgrep_nodes(tree, tgrep_string):
    '''
    Return all tree nodes in the given tree which match the given
    tgrep string.
    '''
    return [tree[position] for position in tgrep_positions(tree, tgrep_string)]
