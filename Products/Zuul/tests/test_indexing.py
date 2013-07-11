import unittest

from Products.AdvancedQuery import Eq, Or, And, Not, In, MatchRegexp, Between
from Products.AdvancedQuery import Ge, Le, MatchGlob, Generic

from Products.Zuul.catalog.index_service import AdvancedQueryToElastic


def samedict(a, b):
    for k, v in a.iteritems():
        if k not in b or v != b[k]:
            return False
        elif isinstance(v, dict):
            if not samedict(v, b[k]):
                return False
    return True


class TestAdvancedQueryToElastic(unittest.TestCase):

    def setUp(self):
        self.converter = AdvancedQueryToElastic()

    def assertSame(self, a, b):
        if not samedict(a, b):
            self.fail("%s != %s" % (a, b))

    def test_eq(self):
        query = Eq("a", "b")
        result = self.converter._convert(query)
        self.assertSame(result, {"term": {"a":"b"}})

    def test_in(self):
        query = In("a", [1, 2, 3])
        result = self.converter._convert(query)
        self.assertSame(result, {"in": {"a": [1, 2, 3]}})

    def test_matchregexp(self):
        query = MatchRegexp("a", "^[abc]?.*")
        result = self.converter._convert(query)
        self.assertSame(result, {"regexp":{"a":"^[abc]?.*"}})

        query = MatchRegexp("a", "(?i)^[abc]?.*")
        result = self.converter._convert(query)
        self.assertSame(result, {"regexp":{"a":"(?i)^[abc]?.*"}})

        query = MatchRegexp("a", "(?i)abc.*")
        result = self.converter._convert(query)
        self.assertSame(result, {"prefix":{"a":"abc"}})

        query = MatchRegexp("a", "(?i).*abc.*")
        result = self.converter._convert(query)
        self.assertSame(result, {"wildcard":{"a":"*abc*"}})

    def test_between(self):
        query = Between("a", 10, 20)
        result = self.converter._convert(query)
        self.assertSame(result, {
            "range" : {
                "a" : { 
                    "from" : 10, 
                    "to" : 20, 
                    "include_lower" : True, 
                    "include_upper": True,
                }
            }
        })

    def test_ge(self):
        query = Ge("a", 10)
        result = self.converter._convert(query)
        self.assertSame(result, {
            "range": {
                "a": {
                    "gte": 10
                }
            }
        })

    def test_le(self):
        query = Le("a", 10)
        result = self.converter._convert(query)
        self.assertSame(result, {
            "range": {
                "a": {
                    "lte": 10
                }
            }
        })

    def test_prefix(self):
        query = MatchGlob("a", "thingy*")
        result = self.converter._convert(query)
        self.assertSame(result, {
            "prefix" : {
                "a" : "thingy" 
            }
        })

    def test_glob(self):
        query = MatchGlob("a", "*thingy*")
        result = self.converter._convert(query)
        self.assertSame(result, {
            "wildcard" : {
                "a" : "*thingy*" 
            }
        })
        query = MatchGlob("a", "thi?ngy")
        result = self.converter._convert(query)
        self.assertSame(result, {
            "wildcard" : {
                "a" : "thi?ngy" 
            }
        })
        query = MatchGlob("a", "thi*ngy")
        result = self.converter._convert(query)
        self.assertSame(result, {
            "wildcard" : {
                "a" : "thi*ngy" 
            }
        })

    def test_path(self):
        query = Generic("path", {"query":('/a/b/c',)})
        result = self.converter._convert(query)
        self.assertSame(result, {
            "in" : {
                "path" : ("/a/b/c",)
            }
        })

    def test_and(self):
        query = And(Eq("a", "b"), Eq("b", "c"))
        result = self.converter._convert(query)
        self.assertSame(result, {
            "and": [
                {"term": {"a":"b"}},
                {"term": {"b":"c"}}
            ]
        })


    def test_or(self):
        query = Or(Eq("a", "b"), Eq("b", "c"))
        result = self.converter._convert(query)
        self.assertSame(result, {
            "or": [
                {"term": {"a":"b"}},
                {"term": {"b":"c"}}
            ]
        })

    def test_nesting(self):
        query = Or(And(Eq("a", "b"), Eq("b", "c")), 
                Or(MatchGlob("c", "thing*"), In("a", [1, 2, 3])))
        result = self.converter._convert(query)
        self.assertSame(result, {
            "or": [
                {"and": [
                    {"term":{"a":"b"}},
                    {"term":{"b":"c"}}
                ]},
                {"or": [
                    {"prefix" : {"c" : "thing"}},
                    {"in" : {"a" : [1, 2, 3]}},
                ]},
            ]
        })


if __name__ == "__main__":
    unittest.main()
