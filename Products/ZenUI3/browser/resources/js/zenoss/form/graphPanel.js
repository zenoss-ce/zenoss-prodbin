/*****************************************************************************
 *
 * Copyright (C) Zenoss, Inc. 2010, all rights reserved.
 *
 * This content is made available according to terms specified in
 * License.zenoss under the directory where your Zenoss product is installed.
 *
 ****************************************************************************/


(function(){
    var DATE_RANGES =[
            [129600, _t('Hourly')],
            [864000, _t('Daily')],
            [3628800, _t('Weekly')],
            [41472000, _t('Monthly')],
            [62208000, _t('Yearly')]
    ],
    /*
     * If a given request is over GRAPHPAGESIZE then
     * the results will be paginated.
     * IE can't handle the higher number that compliant browsers can
     * so setting lower.
     **/
    GRAPHPAGESIZE = Ext.isIE ? 25 : 50;

    /**********************************************************************
     *
     * NVD3 Graph Display
     *
     */

    Ext.ns('Zenoss');

    function AjaxRequest() {
        var ACTIVEXMODES = ["Msxml2.XMLHTTP.6.0", "Msxml2.XMLHTTP.3.0",
                            "Msxml2.XMLHTTP"];
        if (window.ActiveXObject) {
            for (var i = 0; i < ACTIVEXMODES.length; i++) {
                try {
                    return new ActiveXObject(ACTIVEXMODES[i]);
                } catch (e) {}
            }
        } else if (window.XMLHttpRequest) {
            return new XMLHttpRequest();
        }

        return false;
    }

    function QueryRequest(){
        this.clientId = "";
        this.startDate = "";
        this.endDate = "";
        this.isExact = true;
        this.isSeries = false;
        this.query = [];

        this.toStr = function() {
            var clientId = this.clientId?"id=" + this.clientId + "&": "";
            var startDate = "start=" + this.startDate + "&";
            var endDate = "end=" + this.endDate + "&";
            var isExact = "exact=" + (this.isExact?"true":"false") + "&";
            var isSeries = "series=" + (this.isSeries?"true":"false") + "&";
            var query = "";

            for (var i = 0; i < this.query.length; i++) {
                query += this.query[i].toStr() + "&";
            }

            var ret = clientId + startDate + endDate + isExact + isSeries + query;
            ret = ret.substr(0, ret.length-1); // Strip the last ampersand (&)
            return ret;
        };
    }

    function QueryData() {
        this.agg = "" // min | max | sum | avg
        this.rate = "";
        this.downsample = "";
        this.metric = "";
        this.tags = {};

        this.toStr = function() {
            var agg = this.agg + ":";
            var rate = this.rate?this.rate + ":" : "";
            var downsample = this.downsample? this.downsample + ":" : "";
            var metric = this.metric;
            var tags = "";

            for (tag in this.tags) {
                tags += tag + "=" + this.tags[tag] + ",";
            }
            if (this.tags.length > 0) {
                tags = "{" + tags.substr(0, tags.length-1) + "}";
            }

            return "query=" + agg + rate + downsample + metric + tags;
        };
    }

    function QueryResponse() {
        this.clientId = "";
        this.source = "";
        this.startTime = "";
        this.startTimeActual = "";
        this.endTime = "";
        this.endTimeActual = "";
        this.isExact = true;
        this.isSeries = false;
        this.results = [];

        this.convertFromJSON = function(data) {
            this.clientId = data["clientId"];
            this.source = data["source"];
            this.startTime = data["startTime"];
            this.startTimeActual = data["startTimeActual"];
            this.endTime = data["endTime"];
            this.endTimeActual = data["endTimeActual"];
            this.isExact = data["exactTimeWindow"];
            this.isSeries = data["series"];

            var results = data["results"];
            var data = {};
            for (var i = 0; i < results.length; i++) {
                var metric = results[i]["metric"];
                var timestamp = results[i]["timestamp"] * 1000; // millisecs
                var value = results[i]["value"];

                if (!(metric in data)) {
                    data[metric] = [];
                }
                data[metric].push(new Array(timestamp, value));
            }
            for (var key in data) {
                var result = {
                    "key": key,
                    "values": data[key],
                };
                this.results.push(result);
            }

            return this;
        };
    }
 
    Zenoss.NVD3Graph = Ext.extend(Ext.Panel, {
        constructor: function(config) {
            config = Ext.applyIf(config||{}, {
                html: {
                    tag: 'svg',
                },
                width: 607,
            });
            Zenoss.NVD3Graph.superclass.constructor.call(this, config);            
            this.setRequest(config);
        },

        setRequest: function(config) {
            this.request = new QueryRequest();
            this.request.clientId = config.graphTitle;
            this.request.startDate = "24h-ago";
            this.request.endDate = "now";
            
            for (var i = 0; i < this.graphMetrics.length; i++) {
                var query = new QueryData();
                query.agg = "avg";
                query.metric = this.graphMetrics[i];
                query.tags['uuid'] = "*";
                this.request.query.push(query)
            }
        },

        sendRequest: function(url, request) {
            var ajaxRequest = new AjaxRequest();

            ajaxRequest.onreadystatechange = function() {
                if (ajaxRequest.readyState == ajaxRequest.DONE) {
                    var rawData = eval( "(" + ajaxRequest.responseText + ")" );
                    var response = (new QueryResponse()).convertFromJSON(rawData);
                    this.displayGraph(response);
                }
            };

            ajaxRequest.open("GET", url + "?" + request.toStr());
            ajaxRequest.send();            
        },

        displayGraph: function(response) {
            var domId = this.id;

            nv.addGraph(function () {
                var chart = nv.models.cumulativeLineChart()
                              .x(function(d) { return d[0]; })
                              .y(function(d) { return d[1]; })
                              .color(d3.scale.category10().range());
                chart.xAxis.tickFormat(function(d) {
                    return d3.time.format('%a %H:%M')(new Date(d));
                });
                chart.yAxis.tickFormat(d3.format(',.3f'));
            
                d3.select("#" + domId + " " + "svg")
                  .datum(response.results)
                  .transition()
                  .duration(500)
                  .call(chart);

                nv.utils.windowResize(chart.update);

                return chart;
            });
        },

    });

    /**********************************************************************
     *
     * Graph Panel
     *
     */
    var router = Zenoss.remote.DeviceRouter,
        GraphPanel,
        DRangeSelector,
        GraphRefreshButton,
        tbarConfig;

    Ext.define("Zenoss.form.GraphRefreshButton", {
        alias:['widget.graphrefreshbutton'],
        extend:"Zenoss.RefreshMenuButton",
        constructor: function(config) {
            config = config || {};
            var menu = {
                xtype: 'statefulrefreshmenu',
                id: config.stateId || Ext.id(),
                trigger: this,
                items: [{
                    cls: 'refreshevery',
                    text: 'Refresh every'
                },{
                    xtype: 'menucheckitem',
                    text: '1 minute',
                    value: 60,
                    group: 'refreshgroup'
                },{
                    xtype: 'menucheckitem',
                    text: '5 minutes',
                    value: 300,
                    group: 'refreshgroup'
                },{
                    xtype: 'menucheckitem',
                    text: '10 Minutes',
                    value: 600,
                    group: 'refreshgroup'
                },{
                    xtype: 'menucheckitem',
                    text: '30 Minutes',
                    checked: true,
                    value: 1800,
                    group: 'refreshgroup'
                },{
                    xtype: 'menucheckitem',
                    text: '1 Hour',
                    value: 3600,
                    group: 'refreshgroup'
                },{
                    xtype: 'menucheckitem',
                    text: 'Manually',
                    value: -1,
                    group: 'refreshgroup'
                }]
            };
            Ext.apply(config, {
                menu: menu
            });
            this.callParent(arguments);
        }
    });



    Ext.define("Zenoss.form.DRangeSelector", {
        alias:['widget.drangeselector'],
        extend:"Ext.form.ComboBox",
        constructor: function(config) {
            config = config || {};
            Ext.apply(config, {
                fieldLabel: _t('Range'),
                    name: 'ranges',
                    editable: false,
                    forceSelection: true,
                    autoSelect: true,
                    triggerAction: 'all',
                    value: 129600,
                    queryMode: 'local',
                    store: new Ext.data.ArrayStore({
                        id: 0,
                        model: 'Zenoss.model.IdName',
                        data: DATE_RANGES
                    }),
                    valueField: 'id',
                    displayField: 'name'
            });
            this.callParent(arguments);
        }
    });


    tbarConfig = [{
                    xtype: 'tbtext',
                    text: _t('Performance Graphs')

                }, '-', '->', {
                    xtype: 'drangeselector',
                    ref: '../drange_select',
                    listeners: {
                        select: function(combo, records, index){
                            var value = records[0].data.id,
                                panel = combo.refOwner;

                            panel.setDrange(value);
                        }
                    }
                },'-', {
                    xtype: 'button',
                    ref: '../resetBtn',
                    text: _t('Reset'),
                    handler: function(btn) {
                        var panel = btn.refOwner;
                        panel.setDrange();
                    }
                },'-',{
                    xtype: 'tbtext',
                    text: _t('Link Graphs?:')
                },{
                    xtype: 'checkbox',
                    ref: '../linkGraphs',
                    checked: true,
                    listeners: {
                        change: function(chkBx, checked) {
                            var panel = chkBx.refOwner;
                            panel.setLinked(checked);
                        }
                    }
                }, '-',{
                    xtype: 'graphrefreshbutton',
                    ref: '../refreshmenu',
                    stateId: 'graphRefresh',
                    iconCls: 'refresh',
                    text: _t('Refresh'),
                    handler: function(btn) {
                        if (btn) {
                            var panel = btn.refOwner;
                            panel.resetSwoopies();
                        }
                    }
                }];

    Ext.define("Zenoss.form.GraphPanel", {
        alias:['widget.graphpanel'],
        extend:"Ext.Panel",
        constructor: function(config) {
            config = config || {};
            // default to showing the toolbar
            if (!Ext.isDefined(config.showToolbar) ) {
                config.showToolbar = true;
            }
            if (config.showToolbar){
                config.tbar = tbarConfig;
            }
            Ext.applyIf(config, {
                drange: 129600,
                isLinked: true,
                // images show up after Ext has calculated the
                // size of the div
                bodyStyle: {
                    overflow: 'auto'
                },
                directFn: router.getGraphDefs
            });
            Zenoss.form.GraphPanel.superclass.constructor.apply(this, arguments);
        },
        setContext: function(uid) {
            // remove all the graphs
            this.removeAll();
            this.lastShown = 0;

            var params = {
                uid: uid,
                drange: this.drange
            };
            this.uid = uid;
            this.directFn(params, Ext.bind(this.loadGraphs, this));
        },
        loadGraphs: function(result){
            if (!result.success){
                return;
            }
            var data = result.data,
                panel = this,
                el = this.getEl();

            if (el.isMasked()) {
                el.unmask();
            }

            if (data.length > 0){
                this.addGraphs(data);
            }else{
                el.mask(_t('No Graph Data') , 'x-mask-msg-noicon');
            }
        },
        addGraphs: function(data) {
            var graphs = [],
                graph,
                graphId,
                me = this,
                start = this.lastShown,
                end = this.lastShown + GRAPHPAGESIZE,
                i;
            // load graphs until we have either completed the page or
            // we ran out of graphs
            for (i=start; i < Math.min(end, data.length); i++) {
                graphId = Ext.id();
                graph = data[i];
                graphs.push(new Zenoss.NVD3Graph({
                    graphUrl: graph.url,
                    graphTitle: graph.title,
                    graphId: graphId,
                    graphMetrics: graph.metrics,
                    isLinked: this.isLinked,
                    height: 250,
                    ref: graphId
                }));
            }

            // set up for the next page
            this.lastShown = end;

            // if we have more to show, add a button
            if (data.length > end) {
                graphs.push({
                    xtype: 'button',
                    text: _t('Show more results...'),
                    margin: '0 0 7 7',
                    handler: function(t) {
                        t.hide();
                        // will show the next page by looking at this.lastShown
                        me.addGraphs(data);
                    }
                });
            }

            // render the graphs
            this.add(graphs);
        },
        setDrange: function(drange) {
            drange = drange || this.drange;
            this.drange = drange;
            Ext.each(this.getGraphs(), function(g) {
                g.fireEvent("updateimage", {
                    drange: drange,
                    start: drange,
                    end: 0
                }, this);
            });
        },
        resetSwoopies: function() {
            Ext.each(this.getGraphs(), function(g) {
                g.fireEvent("updateimage", {
                }, this);
            });
        },
        getGraphs: function() {
            var graphs = Zenoss.util.filter(this.items.items, function(item){
                return item.graphUrl;
            });
            return graphs;
        },
        setLinked: function(isLinked) {
            this.isLinked = isLinked;
            Ext.each(this.getGraphs(), function(g){
                g.setLinked(isLinked);
            });
        }
    });



}());
