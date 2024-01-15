# Extensions

A key feature of WeeWX is its ability to be extended by installing 3rd party
*extensions*. Extensions are a way to package one or more customizations so that
they can be installed and distributed as a functional group.

Customizations typically fall into one of these categories:

* search list extension
* template
* skin
* service
* generator
* driver

Take a look at the [WeeWX wiki](https://github.com/weewx/weewx/wiki) for a
sampling of some of the extensions that are available.

## Creating an extension

Now that you have made some customizations, you might want to share those
changes with other WeeWX users. Put your customizations into an extension to
make installation, removal, and distribution easier.

Here are a few guidelines for creating extensions:

* Extensions should not modify or depend upon existing skins. An extension
  should include its own, standalone skin to illustrate any templates, search
  list extension, or generator features.

* Extensions should not modify the database schemas. If it requires
  data not found in the default databases, an extension should provide its own
  database and schema.

Although one extension might use another extension, take care to write the
dependent extension so that it fails gracefully. For example, a skin might use
data from the forecast extension, but what happens if the forecast extension is
not installed? Make the skin display a message about "forecast not installed"
but otherwise continue to function.

## Packaging an extension

The structure of an extension mirrors that of WeeWX itself. If the
customizations include a skin, the extension will have a `skins` directory. If
the customizations include python code, the extension will have a `bin/user`
directory.

Each extension should also include:

* `readme.txt` or `readme.md` - a summary of what the extension does, a list of
  pre-requisites (if any), and instructions for installing the extension
  manually

* `changelog` - an enumeration of changes in each release

* `install.py` - python code used by the WeeWX `ExtensionInstaller`

For example, here is the structure of an extension called `basic`, which
installs a skin called `Basic`. You can find it in the `examples` subdirectory.

```
basic
├── changelog
├── install.py
├── readme.md
└── skins
    └── Basic
        ├── basic.css
        ├── current.inc
        ├── favicon.ico
        ├── hilo.inc
        ├── index.html.tmpl
        ├── lang
        │   ├── en.conf
        │   └── fr.conf
        └── skin.conf
```

Here is the structure of an extension called `xstats`, which implements a search
list extension, as well as a simple skin. You can also find it in the `examples`
subdirectory.

```
xstats
├── bin
│   └── user
│       └── xstats.py
├── changelog
├── install.py
├── readme.txt
└── skins
    └── xstats
        ├── index.html.tmpl
        └── skin.conf
```

To distribute an extension, simply create a compressed archive of the
extension directory.

For example, create the compressed archive for the `basic` skin
like this:

    tar cvfz basic.tar.gz basic

Once an extension has been packaged, it can be installed using `weectl`:

    weectl extension install EXTENSION-LOCATION

## Default values

Whenever possible, an extension should *just work*, with a minimum of input from
the user. At the same time, parameters for the most frequently requested options
should be easily accessible and easy to modify. For skins, this might mean
parameterizing strings into `[Labels]` for easier customization. Or it might
mean providing parameters in `[Extras]` to control skin behavior or to
parameterize links.

Some parameters *must* be specified, and no default value would be appropriate.
For example, an uploader may require a username and password, or a driver might
require a serial number or IP address. In these cases, use a default value in
the configuration that will obviously require modification. The *username* might
default to *REPLACE_ME*. Also be sure to add a log entry that indicates the
feature is disabled until the value has been specified.

In the case of drivers, use the configuration editor to prompt for this type of
required value.
