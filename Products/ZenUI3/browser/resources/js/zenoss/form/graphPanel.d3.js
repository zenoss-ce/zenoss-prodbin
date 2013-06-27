/*****************************************************************************
 * 
 * Copyright (C) Zenoss, Inc. 2013, all rights reserved.
 *
 * This content is made available according to terms specified in
 * License.zenoss under the directory where your Zenoss product is installed.
 *
 *****************************************************************************/

var URL = "/proxy/query/performance"

request = new QueryRequest();
request.clientId = "Load Average"
query = new QueryData();
query.agg = "avg"
query.metric = "laLoadInt15"
query.tags['device_name'] = 'localhost.localdomain';
request.query.push(query);
query = new QueryData();
query.agg = "avg"
query.metric = "laLoadInt5"
query.tags['device_name'] = 'localhost.localdomain';
request.query.push(query);
query = new QueryData();
query.agg = "avg"
query.metric = "laLoadInt1"
query.tags['device_name'] = 'localhost.localdomain';
request.query.push(query);

function QueryRequest() {
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
                "values": data[key]
            };
            this.results.push(result)
        }

        return this;
        
    };
}

function PerformanceGraph(response, domId) {
    nv.addGraph(function () {
        var chart = nv.models.cumulativeLineChart()
                      .x(function(d) { return d[0]; })
                      .y(function(d) { return d[1]; })
                      .color(d3.scale.category10().range());

        chart.xAxis
             .tickFormat(function(d) {
                 return d3.time.format('%x')(new Date(d));
             });
        chart.yAxis
             .tickFormat(d3.format(',.3f'));

        d3.select("#" + domId + " " + "svg")
          .datum(response.results)
          .transition()
          .duration(500)
          .call(chart);

        nv.utils.windowResize(chart.update);

        return chart;
    });
}

function send(request) {
    var url = URL + "?" + request.toStr();
    var ajaxRequest = new AjaxRequest();
  
    ajaxRequest.onreadystatechange = function() {
        if (ajaxRequest.readyState == ajaxRequest.DONE) {
            load(ajaxRequest);
        }  
    };

    ajaxRequest.open("GET", url, true);
    ajaxRequest.send();
}

function load(REQ) {
    var rawData = eval( "(" + REQ.responseText + ")" );
    var response = (new QueryResponse()).convertFromJSON(rawData);
}
