##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from zope.component import getGlobalSiteManager
from zope.component import adapts, subscribers
from zope.interface import implements

from .interfaces import IIndexed, IIndexedFields, IIndexedField


_gsm = getGlobalSiteManager()


class DefaultIndexedField(object):
    implements(IIndexedField)

    _name = ""

    def __init__(self, name):
        self._name = name

    def __call__(self, ob):
        return self

    @property
    def name(self):
        return self._name


class DefaultIndexable(object):
    """
    Default adapter that turns Indexed objects into IndexedFields objects.
    """
    adapts(IIndexed)
    implements(IIndexedFields)

    def __init__(self, ob):
        self._ob = ob

    def get_indexed_fields(self):
        """
        Look up the IIndexedField instances associated with the adapted object.
        This default implementation relies on ZCA subscription adapters.

        @return A list of objects providing IIndexedField
        """
        for field in subscribers([self._ob], IIndexedField):
            yield field

    def get_field_names(self):
        fields = [field.get_field_name() for field in
                  self.get_indexed_fields()]
        return fields


def indexed(class_method):
    """
    Decorator for methods the values of which you want to be indexed.
    """
    method = class_method.__name__
    _gsm.registerSubscriptionAdapter(DefaultIndexedField(method))
    return class_method
