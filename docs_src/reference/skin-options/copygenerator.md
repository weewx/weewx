# [CopyGenerator]

This section is used by generator `weewx.reportengine.CopyGenerator` and
controls which files are to be copied over from the skin directory to the
destination directory. Think of it as "file generation," except that rather
than going through the template engine, the files are simply copied over.
It is useful for making sure CSS and Javascript files are in place.

#### copy_once

This option controls which files get copied over on the first invocation
of the report engine service. Typically, this is things such as style
sheets or background GIFs. Wildcards can be used.

#### copy_always

This is a list of files that should be copied on every invocation.
Wildcards can be used.

Here is the `[CopyGenerator]` section from the Standard `skin.conf`

``` ini
[CopyGenerator]
    # This section is used by the generator CopyGenerator

    # List of files to be copied only the first time the generator runs
    copy_once = backgrounds/*, weewx.css, mobile.css, favicon.ico

    # List of files to be copied each time the generator runs
    # copy_always = 
```

The Standard skin includes some background images, CSS files, and icons
that need to be copied once. There are no files that need to be copied
every time the generator runs.
