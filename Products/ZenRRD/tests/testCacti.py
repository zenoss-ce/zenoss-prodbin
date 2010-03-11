###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2008, 2009 Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 as published by
# the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################


from Products.ZenTestCase.BaseTestCase import BaseTestCase
from Products.ZenRRD.tests.BaseParsersTestCase import Object
from Products.ZenRRD.CommandParser import ParsedResults

from Products.ZenRRD.parsers.Cacti import Cacti

class TestCacti(BaseTestCase):

    def testCacti(self):
        deviceConfig = Object()
        deviceConfig.device = 'localhost'
        cmd = Object()
        cmd.deviceConfig = deviceConfig
        p1 = Object()
        p1.id = 'cacti_single_result'
        p1.data = dict(processName='someJob a b c',
                       ignoreParams=False,
                       alertOnRestart=True,
                       failSeverity=3)
        cmd.points = [p1]
        cmd.result = Object()
        cmd.result.output = "77"
        cmd.result.exitCode = 2
        cmd.severity = 2
        cmd.command = "testCactiPlugin"
        cmd.eventKey = "cactiKey"
        cmd.eventClass = "/Cmd"
        cmd.component = "zencommand"
        results = ParsedResults()
        parser = Cacti()
        parser.processResults(cmd, results)
        self.assertEquals( len(results.values), 1)
        self.assertEquals(77,  int(results.values[0][1]))

        # Now test multiple data points
        p2 = Object()
        p2.id = 'cacti_multi_result'
        p2.data = dict(processName='someJob a b c',
                       ignoreParams=False,
                       alertOnRestart=True,
                       failSeverity=3)
        cmd.points.append( p2 )
        cmd.result.output = "cacti_single_result:77 cacti_multi_result:21"
        results = ParsedResults()
        parser.processResults(cmd, results)
        self.assertEquals( len(results.values), 2)
        values = map(lambda x: x[1], results.values)
        self.assertTrue(77.0 in values)
        self.assertTrue(21.0 in values)

def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestCacti))
    return suite
