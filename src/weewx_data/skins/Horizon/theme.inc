## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## The stylesheets and scripts named in 'custom_css' and 'custom_js', in the order
## given. They come after horizon.css and horizon.js, so a custom property set in
## one of them wins over the skin's own. Each file must also be in 'copy_once'
## under [CopyGenerator], or it is never installed.
#for $css in $to_list($DisplayOptions.get('custom_css', []))
  #if $css
    <link rel="stylesheet" href="$css">
  #end if
#end for
##
## Deferred, so a script runs after horizon.js has wired up the elements it may
## move.
#for $js in $to_list($DisplayOptions.get('custom_js', []))
  #if $js
    <script src="$js" defer></script>
  #end if
#end for
