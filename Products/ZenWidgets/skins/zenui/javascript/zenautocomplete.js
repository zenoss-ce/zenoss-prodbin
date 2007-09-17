YAHOO.namespace('zenoss.zenautocomplete');
YAHOO.namespace('zenoss.env');

YAHOO.zenoss.env.cache = new Object();
YAHOO.zenoss.getRemoteData = function(name, url, callback) {
    var o = YAHOO.zenoss.env.cache;
    var d = new Deferred();
    var e = new Deferred();
    d.addCallback(function(){return e;});
    d.addCallback(function(r){
        o[name] = r; 
        return r
    });
    d.addCallback(callback);
    e.addCallback(function(){
        if (o[name]) return o[name];
        else return loadJSONDoc(url);
    });
    d.callback();
    e.callback();
    return d;
}

YAHOO.zenoss.zenautocomplete.ZenAutoComplete = Class.create();
YAHOO.zenoss.zenautocomplete.ZenAutoComplete.prototype = {
    __init__: function(name, url, label, container) {
        bindMethods(this);
        this.target = $(container);
        this.label = label;
        this.setup();
        YAHOO.zenoss.getRemoteData(name, url, this.makeAutoCompleter);
    },
    setup: function() {
        this.input = INPUT({'id':'results'+new Date().getTime()}, null);
        this.results = DIV({'id':'results'+new Date().getTime()}, null);
        this.container = DIV({'class':'autocompleter-container'}, null);
        addElementClass(this.target, 'yui-skin-sam');
        wrapper = DIV(null, null);
        appendChildNodes(wrapper, this.input, this.results);
        appendChildNodes(this.container,
                         DIV({'class':'control-label'}, this.label), 
                         wrapper);
        appendChildNodes(this.target, this.container);
    },
    makeAutoCompleter: function(locarray) {
        this.oACDS = new YAHOO.widget.DS_JSArray(locarray, {
            queryMatchContains:true});
        this.oAutoComp = new YAHOO.widget.AutoComplete(this.input, 
            this.results, this.oACDS);
        this.oAutoComp.typeAhead = false;
        this.oAutoComp.useShadow = true;
        this.oAutoComp.minQueryLength = 0;
        var mythis = this;
        this.oAutoComp.textboxFocusEvent.subscribe(function(){
            var sInputValue = mythis.input.value;
            if(sInputValue.length===0) {
                var oSelf = this;
                setTimeout(function(){oSelf.sendQuery(sInputValue);},0);
            }
        });
    }
}

YAHOO.zenoss.getOrganizers = function(root, callback) {
    var url = '/zport/dmd/' + root + '/getOrganizerNames';
    function _prepare(orgarray) {
        orgarray = map(
            function(x){return '/'+root+(x=='/'?'':x)}, 
            orgarray);
        callback(orgarray);
    }
    var d = new YAHOO.zenoss.getRemoteData(root, url, _prepare);
}


YAHOO.zenoss.zenautocomplete.OrganizerBase = Subclass.create(
    YAHOO.zenoss.zenautocomplete.ZenAutoComplete);
YAHOO.zenoss.zenautocomplete.OrganizerBase.prototype = {
    __init__: function(organizer, label, container) {
        bindMethods(this);
        this.target = $(container);
        this.label = label;
        this.setup();
        YAHOO.zenoss.getOrganizers(organizer, this.makeAutoCompleter);
    }
}

var _getlivesearchwidget = function(organizer, label, container){
    return new YAHOO.zenoss.zenautocomplete.OrganizerBase(
        organizer,label,container)
};

YAHOO.zenoss.zenautocomplete.LocationSearch = partial(
    _getlivesearchwidget, "Locations");
YAHOO.zenoss.zenautocomplete.DevClassSearch = partial(
    _getlivesearchwidget, "Devices"); 
YAHOO.zenoss.zenautocomplete.SystemSearch = partial(
    _getlivesearchwidget, "Systems");
YAHOO.zenoss.zenautocomplete.GroupSearch = partial(
    _getlivesearchwidget, "Groups");

var _getAllOrganizers = function(callback) {
    orgs = ['Locations', 'Systems', 'Devices', 'Groups'];
    i = 0;
    var payload = []
    function getNextOrganizer(newpayload) {
        payload = concat(payload, newpayload);
        if (i<orgs.length) {
            org = orgs[i]; i++;
            YAHOO.zenoss.getOrganizers(org, getNextOrganizer);
        } else {
            payload.sort();
            callback(payload);
        }
    }
    getNextOrganizer([])
}
var _getOrganizersAndDevices = function(callback) {
    function getDevices(payload) {
        var d = loadJSONDoc('/zport/dmd/Devices/jsonGetDeviceNames');
        d.addCallback(function(p) {
            payload = concat(p, payload);
            mycallback(payload)
        });
    }
    function mycallback(payload) {
        payload.sort();
        callback(payload)
    }
    _getAllOrganizers(getDevices);
}

YAHOO.zenoss.zenautocomplete.OrganizerSearch = Subclass.create(
    YAHOO.zenoss.zenautocomplete.ZenAutoComplete);
YAHOO.zenoss.zenautocomplete.OrganizerSearch.prototype = {
    __init__: function(label, container) {
        bindMethods(this);
        this.target = $(container);
        this.label = label;
        this.setup();
        _getAllOrganizers(this.makeAutoCompleter);
    }
}

YAHOO.zenoss.zenautocomplete.DevObjectSearch = Subclass.create(
    YAHOO.zenoss.zenautocomplete.ZenAutoComplete);
YAHOO.zenoss.zenautocomplete.DevObjectSearch.prototype = {
    __init__: function(label, container) {
        bindMethods(this);
        this.target = $(container);
        this.label = label;
        this.setup();
        _getOrganizersAndDevices(this.makeAutoCompleter);
    }
}


YAHOO.register('zenautocomplete', YAHOO.zenoss.zenautocomplete, {});
