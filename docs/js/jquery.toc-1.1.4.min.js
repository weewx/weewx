/*!
 * samaxesJS JavaScript Library
 * jQuery TOC Plugin v1.1.4
 * http://code.google.com/p/samaxesjs/
 *
 * Copyright (c) 2011 samaxes.com
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
(function(d){d.fn.toc=function(j){var l=d.extend({},d.fn.toc.defaults,j);var n=this.append("<ul></ul>").children("ul");var m={h1:0,h2:0,h3:0,h4:0,h5:0,h6:0};var h=0;var g={h1:0,h2:0,h3:0,h4:0,h5:0,h6:0};for(var k=1;k<=6;k++){g["h"+k]=(l.exclude.match(new RegExp("h"+k,"i"))===null&&d("h"+k).length>0)?++h:0}return this.each(function(){d(l.context+" :header").not(l.exclude).each(function(){var p=d(this);for(var o=6;o>=1;o--){if(p.is("h"+o)){if(l.numerate){b(m["h"+o],n);c(m,"h"+o);if(l.autoId&&!p.attr("id")){p.attr("id",a(p.text()))}p.text(f(m,"h"+o,p.text()))}e(n,g["h"+o],p.attr("id"),p.text())}}})})};function b(h,g){if(h===0&&g.find(":last").length!==0&&!g.find(":last").is("ul")){g.find("li:last").append("<ul></ul>")}}function c(g,h){d.each(g,function(j,k){if(j===h){++g[j]}else{if(j>h){g[j]=0}}})}function a(g){return g.replace(/[ <>#\/\\?&\n]/g,"_")}function f(i,j,h){var g="";d.each(i,function(k,l){if(k<=j&&i[k]>0){g+=i[k]+"."}});return g+" "+h}function e(m,g,l,k){var j=m;for(var h=1;h<g;h++){if(j.find("> li:last > ul").length===0){j.append("<li><ul></ul></li>")}j=j.find("> li:last > ul:first")}if(l===""){j.append("<li>"+k+"</li>")}else{j.append('<li><a href="#'+l+'">'+k+"</a></li>")}}d.fn.toc.defaults={exclude:"h1, h5, h6",context:"",autoId:false,numerate:true}})(jQuery);