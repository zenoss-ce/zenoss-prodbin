###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2007, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 as published by
# the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################
#   Copyright (c) 2005 Zentinel Systems, Inc. All rights reserved.

from OFS.PropertyManager import PropertyManager
from Products.ZenRelations.RelationshipManager import RelationshipManager as RM
from Products.ZenRelations.RelSchema import *
from Products.ZenRelations.Exceptions import *

class TestBaseClass(RM):
    pass
    
class DataRoot(TestBaseClass):

    def manage_afterAdd(self, item, container):
        self.zPrimaryBasePath = container.getPhysicalPath()
        TestBaseClass.manage_afterAdd(self, item, container)

TS = 'Products.ZenRelations.tests.TestSchema.'
class Device(TestBaseClass, PropertyManager):
    _properties = (
        {'id':'pingStatus', 'type':'int', 'mode':'w', 'setter':'setPingStatus'},
        {'id':'communities', 'type':'lines', 'mode':'w'},
        )
    _relations = (
        ("location", ToOne(ToMany, 
            TS + "Location", "devices")),
        ("groups", ToMany(ToMany, TS + "Group", "devices")),
        ("interfaces", ToManyCont(ToOne, TS + "IpInterface", "device")),
        )
    pingStatus = 0 
    communities = ()


class Server(Device):
    _relations = (
        ("admin", ToOne(ToOne, TS + "Admin", "server")),
        ) + Device._relations

class IpInterface(TestBaseClass):
    _relations = (
        ("device", ToOne(ToMany,TS + "Device","ipinterfaces")),
        )
    beforeDelete = False
    afterAdd = False
    def manage_beforeDelete(self, item, container):
        self.beforeDelete = True
    def manage_afterAdd(self, item, container):
        if (not hasattr(self, "__primary_parent__") or 
            item.__primary_parent__ != container):
            raise ZenRelationsError("__primary_parent__ not set in afterAdd")
        self.afterAdd = True

class Group(TestBaseClass):
    _relations = (
        ("devices", ToMany(ToMany, TS + "Device", "groups")),
        )
class Location(TestBaseClass):
    _relations = (
        ("devices", ToMany(ToOne, TS + "Device", "location")),
        )

class Admin(TestBaseClass):
    _relations = (
        ("server", ToOne(ToOne, 
            TS + "Server", "admin")),
        )

class Organizer(TestBaseClass):
    _relations = (
    ("parent", ToOne(ToManyCont, TS + "Organizer","children")),
    ("children", ToManyCont(ToOne, TS + "Organizer","parent")),
    )
    def buildOrgProps(self):
        self._setProperty("zFloat", -1.0, type="float")
        self._setProperty("zInt", -1, type="int")
        self._setProperty("zString", "", type="string")
        self._setProperty("zBool", True, type="boolean")
        self._setProperty("zLines", [], type="lines")

    def getZenRootNode(self):
        return self.unrestrictedTraverse("/zport/dmd/Orgs")


def create(context, klass, id):
    """create an instance and attach it to the context passed"""
    inst = klass(id)
    context._setObject(id, inst)
    inst = context._getOb(id)
    return inst

build = create
