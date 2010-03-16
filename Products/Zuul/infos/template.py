###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2010, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 as published by
# the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################
from zope.interface import implements
from Acquisition import aq_parent
from Products.Zuul.infos import InfoBase, ProxyProperty
from Products.Zuul.utils import severityId
from Products.Zuul.interfaces.template import IRRDDataSourceInfo, IDataPointInfo, \
    IMinMaxThresholdInfo, IThresholdInfo, ISNMPDataSourceInfo, IBasicDataSourceInfo, ICommandDataSourceInfo

class TemplateNode(InfoBase):
    
    def __init__(self, template):
        self._object = template
        self._children = []

    @property
    def id(self):
        return self._object.id

    @property
    def text(self):
        return self._object.id

    @property
    def children(self):
        def caseInsensitive(x, y):
            return cmp(x.text.lower(), y.text.lower())
        self._children.sort(caseInsensitive)
        return self._children

    def _addChild(self, leaf):
        self._children.append(leaf)

class TemplateLeaf(InfoBase):

    def __init__(self, template):
        self._object = template

    @property
    def id(self):
        template = self._object.id
        parent = self._getParentPath('.')
        return '%s.%s' % (template, parent)
        
    @property
    def text(self):
        return self._getParentPath('/')

    @property
    def leaf(self):
        return True

    def _getParentPath(self, separator):
        obj = self._object.deviceClass()
        if obj is None:
            # this template is in a Device
            obj = aq_parent(self._object)
            path = list( obj.getPrimaryPath() )
            # remove the "devices" relationship
            path.pop(-2)
        else:
            # this template is in a DeviceClass.rrdTemplates relationship
            path = list( obj.getPrimaryPath() )
        parts = path[4:-1]
        parts.append(obj.titleOrId())
        return separator + separator.join(parts)

    
class RRDDataSourceInfo(InfoBase):
    implements(IRRDDataSourceInfo)
    """
    This is the default Schema/Info for every class that descends from RRDDataSource.
    Most of the zenpacks descend from this.
    """
    def __init__(self, dataSource):
        self._object = dataSource

    @property
    def id(self):
        return '/'.join( self._object.getPrimaryPath() )

    @property
    def name(self):
        return self._object.getId()
        
    @property
    def source(self):
        return self._object.getDescription()
    
    @property
    def type(self):
        return self._object.sourcetype
    
    # severity
    def _setSeverity(self, value):
        try:
            if isinstance(value, str):
                value = severityId(value)
        except ValueError:
            # they entered junk somehow (default to info if invalid)
            value = severityId('info')
        self._object.severity = value
        
    def _getSeverity(self):
        return self._object.getSeverityString()
    
    severity = property(_getSeverity, _setSeverity)
    enabled = ProxyProperty('enabled')
    component = ProxyProperty('component')
    eventClass = ProxyProperty('eventClass')
    eventKey = ProxyProperty('eventKey')

    
class BasicDataSourceInfo(InfoBase):
    implements(IBasicDataSourceInfo)
    """
    Not really used but SNMPDataSource and CommandDataSource both
    share common properties so I am using this subclass
    """
    def __init__(self, dataSource):
        self._object = dataSource

    @property
    def id(self):
        return '/'.join( self._object.getPrimaryPath() )

    @property
    def name(self):
        return self._object.getId()
        
    @property
    def source(self):
        return self._object.getDescription()
    
    @property
    def type(self):
        return self._object.sourcetype
    
    enabled = ProxyProperty('enabled')

    
class SNMPDataSourceInfo(BasicDataSourceInfo):
    implements(ISNMPDataSourceInfo)
    """
    DataSource for SNMP (Basic DataSource with a type of 'SNMP')
    """
    oid = ProxyProperty('oid')

    
class CommandDataSourceInfo(BasicDataSourceInfo):
    implements(ICommandDataSourceInfo)
    """
    Datasource for Commands (Basic DataSource with a type of 'COMMAND')
    """
    @property
    def availableParsers(self):
        """
        returns a list of all available parsers
        """
        if hasattr(self._object, 'parsers'):
            return self._object.parsers()
        return []
    
    # severity
    def _setSeverity(self, value):
        try:
            if isinstance(value, str):
                value = severityId(value)
        except ValueError:
            # they entered junk somehow (default to info if invalid)
            value = severityId('info')
        self._object.severity = value
        
    def _getSeverity(self):
        return self._object.getSeverityString()
    
    severity = property(_getSeverity, _setSeverity)
    usessh = ProxyProperty('usessh')
    component = ProxyProperty('component')
    eventClass = ProxyProperty('eventClass')
    eventKey = ProxyProperty('eventKey')
    commandTemplate = ProxyProperty('commandTemplate')
    cycletime = ProxyProperty('cycletime')
    parser = ProxyProperty('parser')
    
    
class DataPointInfo(InfoBase):
    implements(IDataPointInfo)
    def __init__(self, dataPoint):
        self._object = dataPoint

    @property
    def id(self):
        return '/'.join( self._object.getPrimaryPath() )

    @property
    def name(self):
        return self._object.getId()

    @property
    def type(self):
        return self._object.rrdtype

    @property
    def alias(self):
        return self._object.getAliasNames()
    
    @property
    def leaf(self):
        return True

    @property
    def availableRRDTypes(self):
        """
        """
        return self._object.rrdtypes

    rrdtype = ProxyProperty('rrdtype')
    createCmd = ProxyProperty('createCmd')
    isrow = ProxyProperty('isrow')
    rrdmin = ProxyProperty('rrdmin')
    rrdmax = ProxyProperty('rrdmax')
    
class ThresholdInfo(InfoBase):
    implements(IThresholdInfo)
    def __init__(self, threshold):
        self._object = threshold

    @property
    def id(self):
        return '/'.join( self._object.getPrimaryPath() )

    @property
    def name(self):
        return self._object.getId()

    @property
    def type(self):
        return self._object.getTypeName()

    @property
    def dataPoints(self):
        return self._object.getDataPointNamesString()

    # dsnames
    def _setDsnames(self, value):
        """
        dsnames can be either a list of valid names or a comma separated string
        """
        if value and isinstance(value, str):
            # strip out the empty chars (junk our ItemSelector gives us sometimes)
            value = [name for name in value.split(',') if name]
        self._object.dsnames = value
        
    def _getDsnames(self):
        return self._object.dsnames
        
    dsnames = property(_getDsnames, _setDsnames)

    # severity
    def _setSeverity(self, value):
        try:
            if isinstance(value, str):
                value = severityId(value)
        except ValueError:
            # they entered junk somehow (default to info if invalid)
            value = severityId('info')
        self._object.severity = value
        
    def _getSeverity(self):
        return self._object.getSeverityString()
    
    severity = property(_getSeverity, _setSeverity)

    enabled = ProxyProperty("enabled")

    
class MinMaxThresholdInfo(ThresholdInfo):
    implements(IMinMaxThresholdInfo)
    minval = ProxyProperty("minval")
    maxval = ProxyProperty("maxval")
    eventClass = ProxyProperty("eventClass")
    escalateCount = ProxyProperty("escalateCount")
    
            
class GraphInfo(InfoBase):

    def __init__(self, graph):
        self._object = graph

    @property
    def id(self):
        return self._object.getId()

    @property
    def graphPoints(self):
        return self._object.getGraphPointNamesString()

    @property
    def units(self):
        return self._object.units

    @property
    def height(self):
        return self._object.height

    @property
    def width(self):
        return self._object.width
    
