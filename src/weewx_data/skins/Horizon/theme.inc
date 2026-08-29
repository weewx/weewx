## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## horizon.css defines the palette as custom properties. Anything set under
## [DisplayOptions] [[Theme]] in skin.conf is written out here and overrides it, so
## recolouring the skin is a configuration change, not a CSS edit. Nothing is emitted
## if nothing is configured.
##
#set $theme = $DisplayOptions.get('Theme', {})
#set $light = $theme.get('Light', {})
#set $dark = $theme.get('Dark', {})

#if len($light) or len($dark)
    <style>
  #if len($light)
      :root {
    #for $name in $light
        --$name: $light[$name];
    #end for
      }
  #end if
  #if len($dark)
      @media (prefers-color-scheme: dark) {
        :root:not([data-theme="light"]) {
    #for $name in $dark
          --$name: $dark[$name];
    #end for
        }
      }
      :root[data-theme="dark"] {
    #for $name in $dark
        --$name: $dark[$name];
    #end for
      }
  #end if
    </style>
#end if

## A stylesheet of your own, for whatever the custom properties do not reach. Editing
## horizon.css instead works until the next upgrade overwrites it. It comes last, so
## it wins over [[Theme]] as well. Name the file in 'custom_css' and add it to
## 'copy_once' in [CopyGenerator], or it will not be installed.
#set $custom_css = $DisplayOptions.get('custom_css')
#if $custom_css
    <link rel="stylesheet" href="$custom_css">
#end if
##
## And a script, for a look that needs the page arranged differently rather than
## only painted differently. Deferred, so it runs after horizon.js has wired up
## the elements it may move.
#set $custom_js = $DisplayOptions.get('custom_js')
#if $custom_js
    <script src="$custom_js" defer></script>
#end if
