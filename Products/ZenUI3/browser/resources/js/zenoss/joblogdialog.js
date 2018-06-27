(function() {
    var router = Zenoss.remote.JobsRouter;
    /**
     * @class Zenoss.JobLog
     * @extends Ext.panel.Panel
     * @constructor
     *
     */
    Ext.define('Zenoss.JobLog', {
        extend: 'Zenoss.dialog.BaseDialog',
        alias: 'widget.joblog',
        constructor: function(config) {
            if (!config.job) {
                throw new Exception("You must specify a jobid for the joblog dialog");
            }
            Ext.applyIf(config, {
                height: 600,
                closeAction: 'destroy',
                width: 800,
                //maximized: true,
                title: Ext.String.format("Log for Add Device: {0}", config.deviceName),
                autoScroll: true,
                cls: 'x-window-job-log',
                layout: 'fit',
                items: [{
                    xtype: 'panel',
                    ref: 'logfilecontents',
                    cls: 'x-panel-log-file-contents',
                    autoScroll: true
                }],
                buttons: [{
                    xtype: 'DialogButton',
                    ui: 'dialog-dark',
                    text: _t('Close'),
                    handler: Ext.bind(this.cancelUpdateTask, this)
                }, {
                    xtype: 'button',
                    ui: 'dialog-dark',
                    text: _t('Download Log File'),
                    handler: Ext.bind(function(){
                        window.location = "joblog?job=" + this.jobid;
                    }, this)
                }]
            });
            this.jobid = config.job.uuid;
            this.callParent([config]);
        },
        initComponent: function() {
            this.poll();
            this.on('close', this.cancelUpdateTask, this);
            this.callParent(arguments);
        },
        refresh: function() {
            if (this.job == null) return;
            router.detail({jobid:this.jobid}, function(r){
                var limitMsg = _t("[!] Log file too large for job log screen (viewing last 100 lines). To view full log use link above.");
                var html = "<b>Log file: <a href='joblog?job=" + this.jobid + "'>" + r.logfile + "</a></b><br/><br/>";
                var isError;
                if(r.maxLimit){
                    html += "<b class='log-file-limit'>"+limitMsg+"</b>";
                }
                for (var i=0; i < r.content.length; i++) {
                    if (r.content[i].indexOf("ERROR zen.") !== -1) {
                        isError = true;
                    }
                    html += "<pre class='log-file-contents-item" + (isError ? " error" : '') + "'>" + Ext.htmlEncode(r.content[i]) + '</pre>';
                }
                // this window has been closed or destroyed, cancel the update task
                if (!this.logfilecontents) {
                    return this.cancelUpdateTask();
                }
                this.logfilecontents.update(html);
                var d = this.body.dom;
                d.scrollTop = d.scrollHeight - d.offsetHeight + 16;
                // check to see if we are finished, no need to keep polling if we are
                if (html.indexOf("Finished with result") !== -1) {
                    this.cancelUpdateTask();
                }
            }, this);
        },
        cancelUpdateTask: function() {
            if (this.updateTask) {
                this.updateTask.cancel();
                delete this.updateTask;
            }
        },
        poll: function() {
            if (!this.updateTask) {
                this.updateTask = new Ext.util.DelayedTask(this.poll, this);
            }
            this.refresh();
            var status = this.job.status;
            switch (status) {
              case "STARTED":
              case "PENDING":
                this.updateTask.delay(3000);
                break;
              case "ABORTED":
                // Might have updates but only a couple, so let's not
                // spam the server with requests on a dead job
                this.updateTask.delay(5000);
                break;
            }
        }

    });

}());
