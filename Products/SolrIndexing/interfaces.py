##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from zope.interface import Interface


class IIndexedDocument(Interface):
    """
    A document to be indexed.
    """
    def marshal():
        """
        Return a dictionary representation of the document.
        """


class IIndexedFields(Interface):
    """
    An object that is index
    """

    def get_indexed_fields():
        """
        Returns the IIndexedField instances associated with the adapted object.
        """

    def get_field_names():
        """
        Returns the names of the fields to be indexed as a list of strings.
        """


class IIndexedField(Interface):
    """
    Represents a field to be indexed.
    """

    def get_field_name():
        """
        Returns the name of the field to be indexed.
        """

    def get_indexed_value():
        """
        Returns the value of the indexed field.
        """


class IIndexed(Interface):
    """
    Marker interface against which field names to be indexed may be registered.
    """
