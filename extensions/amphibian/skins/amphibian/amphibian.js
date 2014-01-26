/* javascript for the amphibian skin */
/* copyright 2013 Matthew Wall, all rights reserved */
/* $Id: amphibian.js 798 2014-01-24 18:45:22Z mwall $ */

/* list of pages, must match tabs in header.inc */
var pages = ['hour','day','week','month','year'];
/* which page should be displayed by default? */
var default_page = 'hour.html';

function setURLs(period,format) {
    setTabURLs(period,format);
    setImgURLs(period);
}

function setTabURLs(period,format) {
    for(i=0; i<pages.length; i++) {
        var url = pages[i];
        /* no table links for hour or day */
        if(format == 'table' && pages[i] != 'hour' && pages[i] != 'day') {
            url += '-table';
        }
        url += '.html';
        if(url == default_page) {
            url = 'index.html';
        }
        var elem = document.getElementById(pages[i]+'-link');
        if(elem) {
            elem.setAttribute('href',url);
        }
    }
    document.getElementById(period).className += ' selected';
    if(format == 'table') {
        var url = period + '.html';
        if(url == default_page) {
            url = 'index.html';
        }
        document.getElementById('button-tables').className += ' selected';
        document.getElementById('button-tables-link').setAttribute('href','');
        document.getElementById('button-charts-link').setAttribute('href',url);
    } else {
        var url = period + '-table.html';
        if(url == default_page) {
            url = 'index.html';
        }
        if(period == 'hour' || period == 'day') {
            url = 'week-table.html';
        }
        document.getElementById('button-charts').className += ' selected';
        document.getElementById('button-charts-link').setAttribute('href','');
        document.getElementById('button-tables-link').setAttribute('href',url);
    }
}

function setImgURLs(period) {
    var elems = getElementsByClassName(document,'plot');
    var images = new Array();
    for(i=0; i<elems.length; i++) {
        var id = elems[i].id;
        id = id.replace('img_','');
        images[i] = id;
    }
    for(i=0; i<images.length; i++) {
        var url = period + images[i] + '.png';
        var id = 'img_' + images[i];
        var elem = document.getElementById(id);
        if(elem) {
            elem.setAttribute('src',url);
        }
    }
}

function getElementsByClassName(node,classname) {
    if(node.getElementsByClassName) {
        return node.getElementsByClassName(classname);
    } else {
        return (function getElementsByClass(searchClass,node) {
            if ( node == null )
                node = document;
            var classElements = [],
            els = node.getElementsByTagName("*"),
            elsLen = els.length,
            pattern = new RegExp("(^|\\s)"+searchClass+"(\\s|$)"), i, j;
            for (i = 0, j = 0; i < elsLen; i++) {
                if ( pattern.test(els[i].className) ) {
                    classElements[j] = els[i];
                    j++;
                }
            }
            return classElements;
        })(classname, node);
    }
}