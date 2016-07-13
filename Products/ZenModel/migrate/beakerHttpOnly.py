##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger("zen.migrate")

import Migrate
import servicemigration as sm
sm.require("1.0.0")


class BeakerHTTPOnly(Migrate.Step):
    """
    Set beaker session.httponly to true in config
    """

    version = Migrate.Version(5, 1, 4)

    def cutover(self, dmd):
        try:
            ctx = sm.ServiceContext()
        except sm.ServiceMigrationError:
            log.info("Couldn't generate service context, skipping.")
            return

        commit = False
        zproxy = ctx.getTopService()
        log.info("Top-level service is '%s'." % zproxy.name)
        configfiles = zproxy.originalConfigs + zproxy.configFiles
        for configfile in filter(lambda f: f.name == '/opt/zenoss/zproxy/conf/zproxy-nginx.conf', configfiles):
            config_text = configfile.content

            cookie_rewrite = '    # Force cookies to HTTPOnly\r\n    proxy_cookie_path / "/; HttpOnly";\r\n\r\n'
            if cookie_rewrite in config_text:
                continue

            insert_point = config_text.find('    proxy_read_timeout 600;\r\n')
            config_text = config_text[:insert_point] + cookie_rewrite + config_text[insert_point:]

            log.info("Adding cookie httponly rewrite rule to %s for '%s'." % (configfile.name, zproxy.name))
            configfile.content = config_text
            commit = True
        if commit:
            ctx.commit()

BeakerHTTPOnly()

