/*
###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2010, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################
*/

(function(){

Zenoss.IFramePanel = Ext.extend(Ext.BoxComponent, {
    frameLoaded: false,
    constructor: function(config) {
        config = Ext.applyIf(config || {}, {
            timeout: 5000, // Wait 5s for iframe to initialize before failing
            pollInterval: 50,
            ignoreClassName: false,
            autoEl: {
                tag: 'iframe',
                id: Ext.id(),
                src: config.url || '',
                frameborder: 0
            }
        });
        Zenoss.IFramePanel.superclass.constructor.call(this, config);
        this.addEvents('frameload', 'framefailed');
        this.on('frameload', function(win) {
            // Load any messages that may have been created by the frame
            Zenoss.messenger.checkMessages();
        }, this);
    },
    onRender: function(ct, position) {
        Zenoss.IFramePanel.superclass.onRender.apply(this, arguments);
        // Hook up load events
        this.frame = this.getEl();
        this.waitForLoad();
    },
    afterRender: function(container) {
        Zenoss.IFramePanel.superclass.afterRender.apply(this, arguments);
        if (!this.ownerCt) {
            var pos = this.getPosition(),
                size = this.frame.parent().getViewSize();
            this.setSize(size.width - pos[0], size.height-pos[1]);
        }
    },
    waitForLoad: function() {
        var doc = this.getDocument(),
            currentUrl = doc ? doc.location.href : null,
            ready = false,
            body, dom, href,
            i = 0,
            timestocheck = this.timeout / this.pollInterval;
        (function do_check() {
            if (this.frameLoaded) {
                return;
            }
            body = this.getBody();
            if (currentUrl == 'about:blank' || currentUrl == '') {
                ready = !!body && (this.ignoreClassName || !!body.className);
            } else {
                dom = body ? body.dom : null,
                    href = this.getDocument().location.href;
                ready = href != currentUrl || (dom && dom.innerHTML);
            }
            if (ready || i++ > timestocheck) {
                this.frameLoaded = ready;
                this.fireEvent(ready ? 'frameload' : 'framefailed',
                        this.getWindow());
            } else {
                do_check.defer(this.pollInterval, this);
            }
        }).createDelegate(this)();
    },
    getBody: function() {
        var doc = this.getDocument();
        return doc.body || doc.documentElement;
    },
    getDocument: function() {
        var window = this.getWindow();
        return (Ext.isIE && window ? window.document : null) ||
                this.frame.dom.contentDocument ||
                window.frames[this.frame.dom.name].document ||
                null;
    },
    getWindow: function() {
        return this.frame.dom.contentWindow
                || window.frames[this.frame.dom.name];
    },
    setSrc: function(url) {
        this.frameLoaded = false;
        this.frame.dom.src = url;
        this.waitForLoad();
    }
});

Ext.reg('iframe', Zenoss.IFramePanel);


/**
 * Panel used for displaying old zenoss ui pages in an iframe. Set Context
 * should be called by page to initialze panel for viewing.
 *
 * NOTE: sets a cookie named "newui"; the presence of this cookie will cause the
 * old ui to render with out the old navigation panels and without the tabs.
 *
 * @class Zenoss.BackCompatPanel
 * @extends Zenoss.ContextualIFrame
 */
Zenoss.BackCompatPanel = Ext.extend(Zenoss.IFramePanel, {
    contextUid: null,
    refreshOnContextChange: false,
    constructor: function(config) {
        Zenoss.BackCompatPanel.superclass.constructor.call(this, config);
        Ext.util.Cookies.set('newui', 'yes');
        this.addEvents('frameloadfinished');
        this.on('frameload', function(win) {
            if (win.document && win.document.body) {
                this.fireEvent('frameloadfinished', win);
            } else {
                win.onload = function() {
                    this.fireEvent('frameloadfinished', win);
                }.createDelegate(this);
            }
        }, this);
        this.on('frameloadfinished', function(win) {
            win.document.body.className = win.document.body.className + ' z-bc';
        }, this);
    },
    setContext: function(uid) {
        if (this.refreshOnContextChange || this.contextUid!=uid) {
            this.contextUid = uid;
            var url = uid;
            if (Ext.isDefined(this.viewName) && this.viewName !== null) {
                url = uid + '/' + this.viewName;
            }
            this.setSrc(url);
        }
    }
});

Ext.reg('backcompat', Zenoss.BackCompatPanel);



Zenoss.util.registerBackCompatMenu = function(menu, btn, align, offsets){

    align = align || 'bl';
    offsets = offsets || [0, 0];

    var layer = new Ext.Panel({
        floating: true,
        contentEl: menu,
        border: false,
        shadow: !Ext.isIE,
        bodyCssClass: menu.id=='contextmenu_items' ? 'z-bc-z-menu z-bc-page-menu' : 'z-bc-z-menu'
    });

    layer.render(Ext.getBody());

    function showMenu() {
        var xy = layer.getEl().getAlignToXY(btn.getEl(), align, offsets);
        layer.setPagePosition(xy[0], xy[1]);
        menu.dom.style.display = 'block';
        layer.show();
    }

    function hideMenu() {
        layer.hide();
    }

    function menuClicked(e) {
        var link = e.getTarget('a');
        if (link) {
            // Fake a click
            location.href = link.href;
        }
    }

    btn.on('menushow', showMenu);
    btn.on('menuhide', hideMenu);
    menu.on('mousedown', menuClicked);

};

})();
