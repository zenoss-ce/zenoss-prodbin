##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import json
import logging
import os
import re
log = logging.getLogger("zen.migrate")

import Migrate
import servicemigration as sm
sm.require("1.1.0")

class ServiceValidationError(Exception):
    pass


class HBaseStorage(Migrate.Step):
    """
    Move HBase and opentsdb aside in preparation for HBase filesystem-to-HDFS 
      storage migration in Zenoss 5.2.0
    """

    version = Migrate.Version(5, 1, 70)

    def _findService(self, path):
        # Validate service presence
        svc = self.ctx.findServices('^[^/]+' + path)
        if len(svc) != 1:
            msg = 'Found %d services named "%s" when one was expected' 
            raise ServiceValidationError(msg % (len(svc), path))
        svc = svc[0]
        # Validate service version
        if svc.version != '':
            # Non-Empty version implies that this is a post-HDFS service
            msg = 'Service %s has unexpected version "%s"'
            raise ServiceValidationError(msg % (svc.name, svc.version))
        return svc


    def cutover(self, dmd):
        try:
            self.ctx = sm.ServiceContext()
        except sm.ServiceMigrationError:
            log.info("Couldn't generate service context, skipping.")
            return

        # Find/validate the services
        errors = []
        services = {}
        for path in ('HBase/HMaster', 'HBase/RegionServer', 
                'HBase/ZooKeeper', 'opentsdb'):
            path = '/Infrastructure/' + path
            try:
                svc = self._findService(path)
            except ServiceValidationError as e:
                errors.append(e[0])
            else:
                services[svc.name] = svc

        # Find/validate the opentsdb reader/writer services
        isLite = 'opentsdb' in services and services['opentsdb'].startup != ''
        if not isLite:
            for name in ('reader', 'writer'):
                path = '/Infrastructure/opentsdb/' + name
                try:
                    svc = self._findService(path)
                except ServiceValidationError as e:
                    errors.append(e[0])
                else:
                    services[svc.name] = svc
            del services['opentsdb']

        # Handle accumulated errors
        if errors:
            log.info('\n\t'.join(
		['Errors while validating current HBase services:'] + errors))
            return

        # Clone services
        new_services = dict((name, svc.clone()) 
                for name, svc in services.iteritems())

        # Migrate cloned services
        editRootDir = lambda x: re.sub(r'(\s*<value>)file:///var/hbase(</value>.*)', 
                                       r'\1hdfs:///localhost:8020/hbase\2', x)
        services['RegionServer'].prereqs = []
        for name in ('HMaster', 'RegionServer'):
            services[name].volumes = []
            services[name].endpoints.append(
                sm.Endpoint(
                    name='hdfs=namenode', 
                    application='hdfs-namenode',
                    portnumber=8020,
                    protocol='tcp',
                    purpose='import' ))
            for prop in ('configFiles', 'originalConfigs'):
                for config in getattr(services[name], prop):
                    if config.name == '/etc/hbase-site.xml':
                        content = config.content.split('/n')
                        content = [editRootDir(line) for line in content]
                        config.content = '/n'.join(content)
                        break
        self.ctx.services.extend(services.itervalues())
        
        # Add HDFS service
        templateFileName = 'lite' if isLite else 'full'
        templatePath =  os.path.join(os.path.dirname(__file__),
            "hdfsService", templateFileName + '.json')
        hdfsTemplate = open(templatePath, 'r').read()
        hdfsService = json.dumps(json.loads(hdfsTemplate)['Services'][0])
        infrastructure = self.ctx.findServices('^[^/]+/Infrastructure$')[0]
        self.ctx.deployService(hdfsService, infrastructure)

        # Set various properties for legacy services
        new_services['RegionServer'].prereqs = []
	prereq = new_services['HMaster'].prereqs[0]
        prereq.script = prereq.script.replace('ZooKeeper', 'ZooKeeperLegacy')
	prereq = new_services['opentsdb'].prereqs[0]
        prereq.script = prereq.script.replace('RegionServer', 'RegionServerLegacy')
        for svc in new_services.itervalues():
            svc.tags.append('HBaseMigration')
            svc.version = '1.0'
            svc.launch = sm.Launch.manual
            svc.name = svc.name + 'Legacy'
            svc.description = 'Legacy ' + svc.description
            for ep in svc.endpoints:
                ep.name = 'legacy-' + ep.name
                ep.application = 'legacy-' + ep.application
                for vHost in ep.vHostList:
                    vHost.name = 'legacy-' + vHost.name
            for lc in svc.logConfigs:
                lc.logType = 'legacy-' + lc.logType

        self.ctx.commit()


HBaseStorage()
