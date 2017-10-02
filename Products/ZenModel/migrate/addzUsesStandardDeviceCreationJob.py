##############################################################################
# 
# Copyright (C) Zenoss, Inc. 2017, all rights reserved.
# 
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
# 
##############################################################################


__doc__='''
Add zUsesStandardDeviceCreationJob z property.  Generally true.
'''

import Migrate


class addzUsesStandardDeviceCreationJob(Migrate.Step):

    version = Migrate.Version(114, 0, 0)

    def cutover(self, dmd):
        if not hasattr(dmd.Devices, 'zUsesStandardDeviceCreationJob'):
            dmd.Devices._setProperty('zUsesStandardDeviceCreationJob', True, type='boolean')


addzUsesStandardDeviceCreationJob()