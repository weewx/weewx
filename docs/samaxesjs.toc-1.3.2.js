/*!
 * samaxesJS JavaScript Library
 * http://code.google.com/p/samaxesjs/
 *
 * Copyright (c) 2010 samaxes.com
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * @projectDescription samaxesJS JavaScript Library.
 * @author <a href="http://www.samaxes.com/">Samuel Santos</a>
 * @namespace samaxesJS
 * @type {Object}
 */
var samaxesJS = {
    /**
     * Logging and debugging.
     * @param {Object} obj The object to log.
     */
    debug: function(obj) {
        if (window.console && window.console.log) {
            window.console.log(obj);
        }
    },
    /**
     * Adds a load event handler to the target object.
     * @param {Function} func Function to add a load event handler.
     */
    addLoadEvent: function(func) {
        var oldonload = window.onload;
        if (typeof window.onload != 'function') {
            window.onload = func;
        } else {
            window.onload = function() {
                if (oldonload) {
                    oldonload();
                }
                func();
            };
        }
    },
    /**
     * Used for trimming whitespace.
     * @param {String} str The String to trim.
     * @return {String} The trimmed string.
     */
    trim: function(str) {
        return (str || '').replace(/^(\s|\u00A0)+|(\s|\u00A0)+$/g, '');
    },
    /**
     * Used for getting the size of an associative array.
     * @param {Object} obj Associative array to check size.
     * @return {Number} The size of the associative array.
     */
    size: function(obj) {
        var size = 0, key;

        for (key in obj) {
            if (obj.hasOwnProperty(key)) {
                size++;
            }
        }

        return size;
    },
    /**
     * Used for getting only the direct decendents of an element node by tag name.
     * @param {Object} parent The parent node element.
     * @param {String} node The node name.
     * @return {Array} The direct decendents of an element node.
     */
    getDirectElementsByTagName: function(parent, node) {
        var directElementsByTagName = [];
        var children = parent.childNodes;
        var length = children.length;

        for (var i = 0; i < length; i++) {
            // nodeType === 1 --> Node.ELEMENT_NODE
            if (children[i].nodeType === 1 && children[i].nodeName.match(new RegExp(node, 'i'))) {
                directElementsByTagName.push(children[i]);
            }
        }

        return directElementsByTagName;   
    }
};

/*!
 * TOC JavaScript Library v1.3.2
 */

/**
 * The TOC control dynamically builds a table of contents from the headings in
 * a document and prepends legal-style section numbers to each of the headings.
 * @namespace samaxesJS.toc
 */
samaxesJS.toc = function() {
    var document = this.document;

    /**
     * Creates a TOC element link.
     * @private
     * @param {String} nodeId The node id attribute.
     * @param {String} innerHTML The node text.
     * @return {HTMLElement} The element link.
     */
    function createLink(nodeId, innerHTML) {
        var a = document.createElement('a');
        if (nodeId !== '') {
            a.setAttribute('href', '#' + nodeId);
        }
        a.innerHTML = innerHTML;
        return a;
    }

    /**
     * Checks if the last node is a <code>ul</code> element. If not, a new one is created.
     * @private
     * @param {Number} header The heading counter.
     * @param {Object} toc The container element.
     */
    function checkContainer(header, toc) {
        if (header === 0 && toc.getElementsByTagName('li').length > 0 &&
                !toc.getElementsByTagName('li')[toc.getElementsByTagName('li').length - 1].lastChild.nodeName.match(new RegExp('ul', 'i'))) {
            toc.getElementsByTagName('li')[toc.getElementsByTagName('li').length - 1].appendChild(document.createElement('ul'));
        }
    }

    /**
     * Updates headers numeration.
     * @private
     * @param {Object} headers The heading counters associative array.
     * @param {String} header The heading element node name.
     */
    function updateNumeration(headers, header) {
        for (var i = 1; i <= samaxesJS.size(headers); i++) {
            if ('h' + i === header)  {
                ++headers['h' + i];
            } else if ('h' + i > header) {
                headers['h' + i] = 0;
            }
        }
    }

    /**
     * Generate an anchor id from a string by replacing unwanted characters.
     * @private
     * @param {String} text The original string.
     * @return {String} The string without any unwanted characters.
     */
    function generateId(text) {
        return text.replace(/[ <#\/\\?&]/g, '_');
    }

    /**
     * Prepends the numeration to a heading.
     * @private
     * @param {Object} headers The heading counters associative array.
     * @param {String} header The heading element node name.
     * @param {String} innerHTML The node text.
     * @return {String} The heading element with section heading prepended.
     */
    function addNumeration(headers, header, text) {
        var numeration = '';

        for (var i = 1; i <= samaxesJS.size(headers); i++) {
            if ('h' + i <= header && headers['h' + i] > 0)  {
                numeration += headers['h' + i] + '.';
            }
        }

        return numeration + ' ' + text;
    }

    /**
     * Appends a new node to the TOC.
     * @private
     * @param {Object} toc The container element.
     * @param {Number} index The heading element index.
     * @param {String} id The node id attribute.
     * @param {String} text The node text.
     */
    function appendToTOC(toc, index, id, text) {
        var parent = toc;

        for (var i = 1; i < index; i++) {
            if (samaxesJS.getDirectElementsByTagName(parent, 'li').length > 0) {
                /*if (samaxesJS.getDirectElementsByTagName(samaxesJS.getDirectElementsByTagName(parent, 'li')[samaxesJS.getDirectElementsByTagName(parent, 'li').length - 1], 'ul').length === 0) {
                    parent.appendChild(document.createElement('li')).appendChild(document.createElement('ul'));
                }*/
                parent = samaxesJS.getDirectElementsByTagName(parent, 'li')[samaxesJS.getDirectElementsByTagName(parent, 'li').length - 1].getElementsByTagName('ul')[0];
            }
        }

        if (id == null) {
            parent.appendChild(document.createElement('li')).innerHTML = text;
        } else {
            parent.appendChild(document.createElement('li')).appendChild(createLink(id, text));
        }
    }

    return function(options) {
        samaxesJS.addLoadEvent(function() {
            var headers = [];
            var context = (options && options.context) ? document.getElementById(options.context) : document.body;
            var autoId = options && options.autoId;
            var nodes = context.getElementsByTagName('*');
            var exclude = (!options || options.exclude === undefined) ? 'h1, h5, h6' : options.exclude;
            for (var node in nodes) {
                if (/h\d/i.test(nodes[node].nodeName) && !exclude.match(new RegExp(nodes[node].nodeName, 'i'))) {
                    headers.push(nodes[node]);
                }
            }

            if (headers.length > 0) {
                var toc = document.getElementById((options && options.container) || 'toc').appendChild(document.createElement('ul'));

                var index = 0;
                var headersNumber = {h1: 0, h2: 0, h3: 0, h4: 0, h5: 0, h6: 0};
                var indexes = {h1: 0, h2: 0, h3: 0, h4: 0, h5: 0, h6: 0};
                for (var i = 1; i <= 6; i++) {
                    indexes['h' + i] = (exclude.match(new RegExp('h' + i, 'i')) === null && document.getElementsByTagName('h' + i).length > 0) ? ++index : 0;
                }

                for (var header in headers) {
                    try {
                        for (var i = 6; i >= 1; i--) {
                            if (headers[header].nodeName.match(new RegExp('h' + i, 'i'))) {
                                checkContainer(headersNumber['h' + i], toc);
                                updateNumeration(headersNumber, 'h' + i);
                                if (autoId && !headers[header].getAttribute('id')) {
                                    headers[header].setAttribute('id', generateId(headers[header].innerHTML));
                                }
                                headers[header].innerHTML = addNumeration(headersNumber, 'h' + i, headers[header].innerHTML);
                                appendToTOC(toc, indexes['h' + i], headers[header].getAttribute('id'), headers[header].innerHTML);
                            }
                        }
                    } catch (error) {
                        samaxesJS.debug('Error message: ' + error.message);
                    }
                }
            }
        });
    };
}();
