import re
from Products.AdvancedQuery import Eq, Or, And, Not, In, MatchRegexp, Between
from Products.AdvancedQuery import Ge, Le, MatchGlob, Generic


class AdvancedQueryToElastic(object):

    def _isRegexish(self, term):
        """
        We generally use glob matching for performance and a better user
        experience but if the query has regex characters in it then make it
        a regex object
        """
        value = term.replace("(?i)", "")
        return  "["  in value or "(" in value or "|" in value

    def _convert_Eq(self, query):
        return {"term": {query._idx: query._term}}

    def _convert_And(self, query):
        return {"and": map(self._convert, query._subqueries)}

    def _convert_Or(self, query):
        return {"or": map(self._convert, query._subqueries)}

    def _convert_In(self, query):
        return {"in": {query._idx: query._term}}

    def _convert_MatchRegexp(self, query):
        term = query._term
        if self._isRegexish(term):
            return {"regexp": {query._idx: term}}
        else:
            term = term.replace("(?i)", "").replace(".*", "*")
            return self._convert(MatchGlob(query._idx, term))

    def _convert_Between(self, query):
        from_, to_ = query._term
        return {"range": {
            query._idx: {
                "from": from_,
                "to": to_,
                "include_lower": True,
                "include_upper": True
            }
        }}

    def _convert_Ge(self, query):
        return {"range": {
            query._idx: {
                "gte": query._term
            }
        }}

    def _convert_Le(self, query):
        return {"range": {
            query._idx: {
                "lte": query._term
            }
        }}

    def _convert_Not(self, query):
        return {"not": {"filter":
            self._convert(query._query)
        }}

    _PREFIX_PATTERN = re.compile(r"^[^\*\?]+\*+$")
    def _convert_MatchGlob(self, query):
        term = query._term
        if self._PREFIX_PATTERN.match(term):
            return {
                "prefix": {
                    query._idx: term.rstrip("*")
                }
            }
        else:
            return {
                "wildcard": {
                    query._idx: term
                }
            }

    def _convert_Generic(self, query):
        # We only support path queries
        assert query._idx == "path"
        return {"in": {query._idx: query._term["query"]}}


    FUNCTORS = {
        Eq: _convert_Eq,
        In: _convert_In,
        MatchRegexp: _convert_MatchRegexp,
        Between: _convert_Between,
        Ge: _convert_Ge,
        Le: _convert_Le,
        MatchGlob: _convert_MatchGlob,
        Generic: _convert_Generic,
        And: _convert_And,
        Or: _convert_Or,
        Not: _convert_Not,
    }

    def _convert(self, query):
        functor = self.FUNCTORS[query.__class__]
        return functor.__get__(self, None)(query)

    def convert(self, query):
        return {
            "query": {
                "constant_score": {
                    "filter": self._convert(query)
                }
            }
        }
