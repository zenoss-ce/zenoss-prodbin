/*****************************************************************************
 *
 * Copyright (C) Zenoss, Inc. 2013, all rights reserved.
 *
 * This content is made available according to terms specified in
 * License.zenoss under the directory where your Zenoss product is installed.
 *
 ****************************************************************************/
(function(){
    Ext.ns('Daemons');
    Daemons.states = {
        RUNNING: 'up',
        STARTING: 'up',
        STOPPED: 'down',
        RESTARTING: 'Restarting'
    };
    Ext.application({
        name: 'Daemons',
        appFolder: "/++resource++zenui/js/zenoss/daemons",
        controllers: ["DaemonsListController", "DetailsController"],
        launch: function() {
            var panel = Ext.create('Ext.Panel', {
                layout: 'border',
                items: [{
                    xtype: 'daemonslist',
                    id: 'daemonslist',
                    store: Ext.create('Daemons.store.Daemons', {}),
                    region: 'center'
                },{
                    xtype: 'daemonsdetails',
                    region: 'south',
                    height: "60%",
                    split: true,
                    resizable: true
                }]
            });
            Ext.getCmp('center_panel').add(panel);
            var store = Ext.getCmp('daemonslist').getStore();
            store.setRootNode({
                    id: 'monitors',
                    uuid: '12',
                    status: '1',
                    enabled: true,
                    uid: 'monitors',
                    name: 'Monitors'
            });
            // TODO: Add the 'Daemons' and 'Collectors' sub nodes.

            // this will trigger a router request to get the
            // subservices of localhost
            store.getRootNode().expand();
            this.registerRefreshHandler();
        },
        /**
         * The refresh button's handler is a method, not an event. So we
         * need explicitly wire this button to the controller instead of
         * using the Controller->control method.
         **/
        registerRefreshHandler: function() {
            var controller = this.getController('DaemonsListController');
            Ext.getCmp('refreshtreegrid').handler = Ext.bind(controller.onRefresh, controller);
        }
    });
})();
