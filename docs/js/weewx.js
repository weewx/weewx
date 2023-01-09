/*  Javascript for the weewx documentation
 *
 *  Copyright (c) 2015-2020 Tom Keffer <tkeffer@gmail.com>
 * 
 *  See the file LICENSE.txt for your rights.
 */

function make_ids(contentSelector, headingSelector) {
    // Tocbot does not automatically add ids to all headings. We must do that.
    if (!headingSelector) headingSelector = 'h1, h2, h3, h4';
    const content = document.querySelector(contentSelector);
    const headings = content.querySelectorAll(headingSelector);
    const headingMap = {};

    Array.prototype.forEach.call(headings, function (heading) {
        // Use a hashing similar to the old tocify, to maintain backwards compatiblity with old links
        const id = heading.id ? heading.id : heading.textContent.trim().replace(/[ <>#\/\\?&\n]/g, '_');
        headingMap[id] = !isNaN(headingMap[id]) ? ++headingMap[id] : 0;
        if (headingMap[id]) {
            heading.id = id + '-' + headingMap[id]
        } else {
            heading.id = id
        }
    })

}

function set_cookie(name, value, days) {
    // Default duration of 30 days
    if (!days) days = 30;
    const expire = new Date(Date.now() + 24 * 3600000 * days);
    document.cookie = name + "=" + value + ";path=/;expires=" + expire.toUTCString();
}

function get_cookie(name) {
    if (!name) return "";
    const v = document.cookie.match('(^|;) ?' + name + '=([^;]*)(;|$)');
    return v ? v[2] : null;
}

function get_level_from_cookie() {
    let level = 3;
    const level_str = get_cookie("toc_level");
    if (level_str) {
        level = parseInt(level_str, 10)
    }
    return level;
}

function create_toc(level) {
    let headingSelector = "h1";
    for (let i = 2; i <= level; i++) {
        headingSelector += ", h" + i;
    }
    tocbot.init({
        // Where to render the table of contents.
        tocSelector: '#toc-location',
        // Where to grab the headings to build the table of contents.
        contentSelector: '#technical_content',
        // Which headings to grab inside of the contentSelector element.
        headingSelector: headingSelector,
        // At what depth should we start collapsing things? A depth of 6 shows everything.
        collapseDepth: 6,
    });
}

function create_toc_level_control(level) {
    // Create the TOC "select" control
    const c = document.getElementById('toc_controls');
    if (c) {
        let txt = "<select id='toc_level' onChange='change_toc_level()'>";

        txt += "<option value='1'";
        if (level === 1) {
            txt += " selected";
        }
        txt += ">Less detail</option>";

        txt += "<option value='2'";
        if (level === 2) {
            txt += " selected";
        }
        txt += ">Some detail</option>";

        txt += "<option value='3'";
        if (level === 3) {
            txt += " selected";
        }
        txt += ">More detail</option>";

        txt += "<option value='4'";
        if (level === 4) {
            txt += " selected";
        }
        txt += ">Very detailed</option>";

        txt += "</select>";
        c.innerHTML = txt;
    }
}

function change_toc_level() {
    let field = document.getElementById('toc_level');
    if (field) {
        set_cookie("toc_level", field.value);
        // Get the old TOC element
        const e = document.getElementById("toc-location");
        // Destroy it
        e.parentNode.removeChild(e);

        // Create a new element of type div
        const newToc = document.createElement('div');
        // Give it an id
        newToc.setAttribute('id', 'toc-location');
        // Set its class
        newToc.setAttribute('class', 'toc');
        // Find its parent
        let p = document.getElementById('toc_parent');
        // Attach it
        p.appendChild(newToc);

        // Build a new TOC inside it
        create_toc(field.value);
    }
}

/**
 * Respond to a click event by opening and closing tabs as appropriate.
 * @param evt - The event that created the click. The enclosing element will have the class "selected"
 * added to its list of classes. Its siblings will have it removed.
 * @param contentSelector - A selector for the content to be shown. Its siblings will be hidden.
 */
function openTab(evt, contentSelector) {

    // Hide the siblings of the selected content
    $(contentSelector).siblings(".tab-content").hide();
    // Show the current content:
    $(contentSelector).show();

    // Remove the class 'selected' from the siblings of the tab that was clicked on
    $(evt.currentTarget).siblings('.tab').removeClass('selected');
    // Add it to the selected tab:
    $(evt.currentTarget).addClass('selected');

}
