## Copyright (c) 2026 the WeeWX contributors
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
