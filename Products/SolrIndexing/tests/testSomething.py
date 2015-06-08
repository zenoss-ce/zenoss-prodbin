##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import unittest
from zope.component import getGlobalSiteManager
from zope.component.testlayer import LayerBase

from zope.interface import implements

import Products.SolrIndexing
from Products.SolrIndexing.fields import indexed, DefaultIndexable
from Products.SolrIndexing.interfaces import IIndexedFields, IIndexed


class IndexingTestLayer(LayerBase):

    def setUp(self):
        super(IndexingTestLayer, self).setUp()
        gsm = getGlobalSiteManager()
        gsm.registerAdapter(DefaultIndexable)

    def tearDown(self):
        super(IndexingTestLayer, self).tearDown()


class TestObject(object):
    implements(IIndexed)

    @indexed
    def tobeindexed(self):
        return 1234


class FieldsTestCase(unittest.TestCase):
    layer = IndexingTestLayer(Products.SolrIndexing)

    def testFieldNames(self):
        ob = TestObject()
        fields = IIndexedFields(ob)
        self.assertIn("tobeindexed", fields.get_field_names())


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(FieldsTestCase))
    return suite
